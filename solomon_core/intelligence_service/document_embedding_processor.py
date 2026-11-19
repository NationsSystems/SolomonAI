# -------------------------------------------------------------------
# FILE: document_embedding_processor.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Durable document evidence embedding processor for the Solomon Intelligence
# Service.
#
# The processor consumes a content/version-bound Intelligence Job, extracts
# normalized textual evidence through the canonical DocIntel ingestor, chunks
# that evidence deterministically, executes the configured SIS embedding
# compute provider, and persists vectors into WorkspaceIntelligenceChunk. It owns no user
# permissions and never grants retrieval authority.
# -------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import time

from config import settings
from solomon_core.db import SessionLocal
from solomon_core.docintel.ingestion.docintel_ingestor import (
    DocIntelIngestError,
    ingest_documents_for_intent,
)
from solomon_core.logger import get_logger
from solomon_core.models import (
    FileRegistry,
    WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT,
    WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
    WorkspaceIntelligenceChunk,
    WorkspaceIntelligenceObject,
)
from solomon_core.workspace_intelligence.workspace_intelligence_index import (
    WORKSPACE_INTELLIGENCE_READY_STATUS,
    clean_multiline_text,
    record_supports_text_enrichment,
    safe_metadata_payload,
    select_docintel_document,
)

from .document_embedding_contract import (
    DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
    DOCUMENT_EMBEDDING_CHUNK_CHARS,
    DOCUMENT_EMBEDDING_CHUNK_OVERLAP,
    DOCUMENT_EMBEDDING_JOB_TYPE,
    DOCUMENT_EMBEDDING_PROCESSOR_KEY,
    DOCUMENT_INTELLIGENCE_MAP_CONTRACT,
    DOCUMENT_INTELLIGENCE_MAP_MAX_BANDS,
    DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
    DOCUMENT_EMBEDDING_REUSABLE_PROCESSOR_VERSIONS,
    DOCUMENT_EMBEDDING_PROGRESS_ARTIFACT_READY,
    DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_COMPLETE,
    DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_STARTED,
    DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_COMPLETE,
    DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_STARTED,
    DOCUMENT_EMBEDDING_PROGRESS_PERSISTENCE_STARTED,
    DOCUMENT_EMBEDDING_PROGRESS_SOURCE_VALIDATED,
    DOCUMENT_EMBEDDING_SOURCE,
)
from .portable_compute_dispatch import execute_embeddings_on_configured_compute
from .intelligence_spool_worker import (
    IntelligenceJobExecutionContext,
    IntelligenceJobProcessorResult,
    IntelligenceJobRetryableError,
    IntelligenceJobTerminalError,
)


logger = get_logger("intelligence_service.document_embedding_processor")

_PAGE_MARKER_RE = re.compile(
    r"(?m)^\[SOURCE PAGE\s+(\d+)\s+OF\s+(\d+)\]\s*$"
)


@dataclass(frozen=True)
class _SourceSnapshot:
    file_registry_id: int
    intelligence_object_id: int
    document_id: str
    original_name: str
    path: str
    version_number: int
    source_hash: str


@dataclass(frozen=True)
class _EvidenceChunk:
    chunk_order: int
    content: str
    content_hash: str
    start_char: int
    end_char: int
    page_number: int | None
    source_page_count: int | None


@dataclass(frozen=True)
class _ReusableChunk:
    chunk_order: int
    chunk_kind: str
    title: str | None
    content: str
    content_hash: str
    token_count: int | None
    source_locator_json: dict | None
    metadata_json: dict | None
    embedding_model: str
    embedding_vector: list[float]
    embedding_dimension: int
    embedding_checksum: str


def _utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _stable_hash(value: str) -> str:
    return hashlib.sha256(str(value or "").encode("utf-8")).hexdigest()


def _model_key() -> str:
    return str(settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME or "").strip()


def _make_docintel_progress_callback(
    context: IntelligenceJobExecutionContext,
):
    """Map full-document OCR page progress into the embedding job stage."""

    def _record(payload: dict) -> None:
        context.raise_if_execution_invalid()

        phase = str(payload.get("phase") or "").strip()
        if phase != "ocr_full":
            return

        completed = max(0, int(payload.get("completed_pages") or 0))
        planned = max(1, int(payload.get("planned_pages") or 1))
        fraction = min(1.0, completed / planned)
        progress_span = max(
            1,
            DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_COMPLETE
            - DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_STARTED
            - 1,
        )
        progress_percent = min(
            DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_COMPLETE - 1,
            DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_STARTED
            + int(round(fraction * progress_span)),
        )

        context.record_stage(
            "docintel_extraction",
            progress_percent=progress_percent,
            message=(
                "OCR scanning source pages for durable document intelligence "
                f"({completed}/{planned})."
            ),
            details=payload,
        )
        logger.info(
            "[SIS][DOCUMENT_EMBEDDING_OCR_PROGRESS] job_id=%s "
            "page=%s completed=%s/%s evidence_chars=%s elapsed_seconds=%s",
            context.job.job_id,
            payload.get("source_page") or "n/a",
            completed,
            planned,
            payload.get("evidence_chars") or 0,
            payload.get("elapsed_seconds") or 0,
        )

    return _record


def _record_is_available(record: FileRegistry) -> bool:
    metadata = safe_metadata_payload(record.meta)
    status = str(record.status or "active").strip().lower()
    document_status = str(
        metadata.get("document_status")
        or metadata.get("library_status")
        or "active"
    ).strip().lower()

    return bool(
        status == "active"
        and record.deleted_at is None
        and not metadata.get("trashed")
        and not metadata.get("trashed_at")
        and document_status not in {"trash", "trashed", "deleted"}
    )


def _source_matches_job(
    *,
    record: FileRegistry,
    intelligence_object: WorkspaceIntelligenceObject,
    context: IntelligenceJobExecutionContext,
) -> bool:
    job = context.job
    current_hash = str(record.checksum or "").strip()
    expected_hash = str(job.source_hash or "").strip()
    current_version = int(record.version_number or 1)
    expected_version = int(job.target_version or current_version)

    return bool(
        str(record.random_name or "").strip() == str(job.target_id or "").strip()
        and current_hash
        and expected_hash
        and current_hash == expected_hash
        and current_version == expected_version
        and str(intelligence_object.source_hash or "").strip() == expected_hash
    )


def _load_source_snapshot(
    context: IntelligenceJobExecutionContext,
) -> _SourceSnapshot:
    job = context.job

    if not job.file_registry_id or not job.intelligence_object_id:
        raise IntelligenceJobTerminalError(
            "Document embedding job is missing durable file or intelligence identity.",
            failure_code="document_embedding_identity_missing",
            stage="source_validation",
        )

    db_session = SessionLocal.session_factory()

    try:
        record = db_session.get(FileRegistry, int(job.file_registry_id))
        intelligence_object = db_session.get(
            WorkspaceIntelligenceObject,
            int(job.intelligence_object_id),
        )

        if record is None or intelligence_object is None:
            raise IntelligenceJobTerminalError(
                "Document embedding source record no longer exists.",
                failure_code="document_embedding_source_not_found",
                stage="source_validation",
            )

        if not _record_is_available(record):
            raise IntelligenceJobTerminalError(
                "Document embedding source is no longer active.",
                failure_code="document_embedding_source_unavailable",
                stage="source_validation",
            )

        if not _source_matches_job(
            record=record,
            intelligence_object=intelligence_object,
            context=context,
        ):
            raise IntelligenceJobTerminalError(
                "Document embedding source version or checksum no longer matches the job.",
                failure_code="document_embedding_source_superseded",
                stage="source_validation",
            )

        if not record_supports_text_enrichment(record):
            raise IntelligenceJobTerminalError(
                "Document embeddings do not support this file type.",
                failure_code="document_embedding_file_type_unsupported",
                stage="source_validation",
            )

        path = str(record.path or "").strip()
        if not path or not Path(path).is_file():
            raise IntelligenceJobRetryableError(
                "Document embedding source path is temporarily unavailable.",
                failure_code="document_embedding_source_path_missing",
                retry_delay_seconds=int(
                    settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
                ),
                stage="source_validation",
            )

        return _SourceSnapshot(
            file_registry_id=int(record.id),
            intelligence_object_id=int(intelligence_object.id),
            document_id=str(record.random_name),
            original_name=str(record.original_name or record.random_name),
            path=path,
            version_number=int(record.version_number or 1),
            source_hash=str(record.checksum or "").strip(),
        )
    finally:
        db_session.close()


def _embedding_metadata_matches(
    intelligence_object: WorkspaceIntelligenceObject,
    *,
    source_hash: str,
) -> bool:
    metadata = safe_metadata_payload(intelligence_object.metadata_json)
    embedding_metadata = metadata.get("document_embeddings")

    if not isinstance(embedding_metadata, dict):
        return False

    return bool(
        intelligence_object.embedding_status == WORKSPACE_INTELLIGENCE_READY_STATUS
        and str(intelligence_object.source_hash or "").strip() == source_hash
        and str(intelligence_object.embedding_model or "").strip() == _model_key()
        and str(embedding_metadata.get("source") or "").strip()
        == DOCUMENT_EMBEDDING_SOURCE
        and str(embedding_metadata.get("processor_key") or "").strip()
        == DOCUMENT_EMBEDDING_PROCESSOR_KEY
        and str(embedding_metadata.get("processor_version") or "").strip()
        in DOCUMENT_EMBEDDING_REUSABLE_PROCESSOR_VERSIONS
        and int(embedding_metadata.get("chunk_chars") or 0)
        == DOCUMENT_EMBEDDING_CHUNK_CHARS
        and int(embedding_metadata.get("chunk_overlap") or 0)
        == DOCUMENT_EMBEDDING_CHUNK_OVERLAP
    )


def _load_reusable_chunks(
    source: _SourceSnapshot,
) -> list[_ReusableChunk]:
    """Return vectors reusable for identical content without leaking file identity."""

    db_session = SessionLocal.session_factory()

    try:
        candidates = (
            db_session.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.object_type == "file",
                WorkspaceIntelligenceObject.source_hash == source.source_hash,
                WorkspaceIntelligenceObject.embedding_status
                == WORKSPACE_INTELLIGENCE_READY_STATUS,
                WorkspaceIntelligenceObject.deleted_at.is_(None),
            )
            .order_by(WorkspaceIntelligenceObject.id.asc())
            .all()
        )

        for candidate in candidates:
            if not _embedding_metadata_matches(
                candidate,
                source_hash=source.source_hash,
            ):
                continue

            rows = (
                db_session.query(WorkspaceIntelligenceChunk)
                .filter(
                    WorkspaceIntelligenceChunk.intelligence_object_id
                    == candidate.id,
                    WorkspaceIntelligenceChunk.embedding_status
                    == WORKSPACE_INTELLIGENCE_READY_STATUS,
                    WorkspaceIntelligenceChunk.embedding_model == _model_key(),
                )
                .order_by(WorkspaceIntelligenceChunk.chunk_order.asc())
                .all()
            )

            if not rows:
                continue

            reusable: list[_ReusableChunk] = []
            valid = True

            for row in rows:
                vector = row.embedding_vector
                dimension = int(row.embedding_dimension or 0)
                checksum = str(row.embedding_checksum or "").strip()
                content = clean_multiline_text(row.content)
                content_hash = str(row.content_hash or "").strip()

                if not (
                    content
                    and content_hash
                    and _stable_hash(content) == content_hash
                    and isinstance(vector, list)
                    and vector
                    and dimension == len(vector)
                    and dimension == int(settings.EMBED_DIM)
                    and checksum
                    and _embedding_checksum(
                        content_hash=content_hash,
                        model_key=str(row.embedding_model or "").strip(),
                        vector=[float(value) for value in vector],
                    ) == checksum
                ):
                    valid = False
                    break

                reusable.append(
                    _ReusableChunk(
                        chunk_order=int(row.chunk_order),
                        chunk_kind=str(row.chunk_kind or "body"),
                        title=row.title,
                        content=content,
                        content_hash=content_hash,
                        token_count=row.token_count,
                        source_locator_json=(
                            dict(row.source_locator_json)
                            if isinstance(row.source_locator_json, dict)
                            else None
                        ),
                        metadata_json=(
                            dict(row.metadata_json)
                            if isinstance(row.metadata_json, dict)
                            else None
                        ),
                        embedding_model=str(row.embedding_model or _model_key()),
                        embedding_vector=[float(value) for value in vector],
                        embedding_dimension=dimension,
                        embedding_checksum=checksum,
                    )
                )

            if valid and reusable:
                return reusable

        return []
    finally:
        db_session.close()


def _page_markers(text: str) -> list[tuple[int, int, int]]:
    return [
        (match.start(), int(match.group(1)), int(match.group(2)))
        for match in _PAGE_MARKER_RE.finditer(text)
    ]


def _page_for_offset(
    markers: list[tuple[int, int, int]],
    offset: int,
) -> tuple[int | None, int | None]:
    page_number = None
    page_count = None

    for marker_offset, marker_page, marker_count in markers:
        if marker_offset > offset:
            break
        page_number = marker_page
        page_count = marker_count

    return page_number, page_count


def _chunk_document_text(document_text: str) -> list[_EvidenceChunk]:
    clean_text = clean_multiline_text(document_text)
    if not clean_text:
        return []

    markers = _page_markers(clean_text)
    chunks: list[_EvidenceChunk] = []
    start = 0
    chunk_order = 0

    while start < len(clean_text):
        end = min(len(clean_text), start + DOCUMENT_EMBEDDING_CHUNK_CHARS)
        raw_chunk = clean_text[start:end]
        content = clean_multiline_text(raw_chunk)

        if content:
            page_number, source_page_count = _page_for_offset(markers, start)
            chunks.append(
                _EvidenceChunk(
                    chunk_order=chunk_order,
                    content=content,
                    content_hash=_stable_hash(content),
                    start_char=start,
                    end_char=end,
                    page_number=page_number,
                    source_page_count=source_page_count,
                )
            )
            chunk_order += 1

        if end >= len(clean_text):
            break

        start = max(0, end - DOCUMENT_EMBEDDING_CHUNK_OVERLAP)

    return chunks


def _embedding_checksum(
    *,
    content_hash: str,
    model_key: str,
    vector: list[float],
) -> str:
    payload = {
        "content_hash": content_hash,
        "embedding_contract": WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
        "model": model_key,
        "vector": [float(value) for value in vector],
    }
    return _stable_hash(
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )


def _manifest_checksum(
    chunks: list[tuple[str, str]],
    *,
    model_key: str,
) -> str:
    payload = {
        "chunk_contract": WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT,
        "embedding_contract": WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
        "model": model_key,
        "processor_key": DOCUMENT_EMBEDDING_PROCESSOR_KEY,
        "processor_version": DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
        "chunks": [
            {"content_hash": content_hash, "embedding_checksum": checksum}
            for content_hash, checksum in chunks
        ],
    }
    return _stable_hash(
        json.dumps(payload, sort_keys=True, separators=(",", ":"))
    )


def _validate_current_source(
    *,
    db_session,
    source: _SourceSnapshot,
    context: IntelligenceJobExecutionContext,
) -> tuple[FileRegistry, WorkspaceIntelligenceObject]:
    record = db_session.get(FileRegistry, source.file_registry_id)
    intelligence_object = db_session.get(
        WorkspaceIntelligenceObject,
        source.intelligence_object_id,
    )

    if record is None or intelligence_object is None:
        raise IntelligenceJobTerminalError(
            "Document embedding source disappeared before persistence.",
            failure_code="document_embedding_source_not_found",
            stage="embedding_persistence",
        )

    if not _record_is_available(record) or not _source_matches_job(
        record=record,
        intelligence_object=intelligence_object,
        context=context,
    ):
        raise IntelligenceJobTerminalError(
            "Document embedding source changed before persistence.",
            failure_code="document_embedding_source_superseded",
            stage="embedding_persistence",
        )

    return record, intelligence_object



def _build_document_intelligence_map(
    *,
    source: _SourceSnapshot,
    chunks,
) -> dict:
    """Build a bounded structural map over the complete persisted chunk manifest."""

    descriptors: list[dict] = []

    for index, chunk in enumerate(chunks):
        if isinstance(chunk, _EvidenceChunk):
            locator = {
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
                "page_number": chunk.page_number,
                "source_page_count": chunk.source_page_count,
            }
            chunk_order = int(chunk.chunk_order)
        else:
            locator = (
                dict(getattr(chunk, "source_locator_json", None) or {})
                if isinstance(getattr(chunk, "source_locator_json", None), dict)
                else {}
            )
            chunk_order = int(getattr(chunk, "chunk_order", index) or index)

        descriptors.append({
            "chunk_order": chunk_order,
            "start_char": (
                int(locator.get("start_char"))
                if locator.get("start_char") is not None
                else None
            ),
            "end_char": (
                int(locator.get("end_char"))
                if locator.get("end_char") is not None
                else None
            ),
            "page_number": (
                int(locator.get("page_number"))
                if locator.get("page_number") is not None
                else None
            ),
            "source_page_count": (
                int(locator.get("source_page_count"))
                if locator.get("source_page_count") is not None
                else None
            ),
        })

    if not descriptors:
        return {
            "contract": DOCUMENT_INTELLIGENCE_MAP_CONTRACT,
            "source_hash": source.source_hash,
            "target_version": source.version_number,
            "chunk_count": 0,
            "source_chars": 0,
            "page_count": None,
            "band_count": 0,
            "bands": [],
        }

    descriptors.sort(key=lambda item: int(item.get("chunk_order") or 0))
    chunk_count = len(descriptors)
    band_count = min(
        chunk_count,
        max(1, int(DOCUMENT_INTELLIGENCE_MAP_MAX_BANDS)),
    )
    band_size = max(1, (chunk_count + band_count - 1) // band_count)
    bands = []

    for band_index, start in enumerate(range(0, chunk_count, band_size)):
        band = descriptors[start:start + band_size]
        if not band:
            continue

        start_chars = [
            int(item["start_char"])
            for item in band
            if item.get("start_char") is not None
        ]
        end_chars = [
            int(item["end_char"])
            for item in band
            if item.get("end_char") is not None
        ]
        page_numbers = [
            int(item["page_number"])
            for item in band
            if item.get("page_number") is not None
        ]

        bands.append({
            "band_index": band_index,
            "chunk_start": int(band[0]["chunk_order"]),
            "chunk_end": int(band[-1]["chunk_order"]),
            "start_char": min(start_chars) if start_chars else None,
            "end_char": max(end_chars) if end_chars else None,
            "page_start": min(page_numbers) if page_numbers else None,
            "page_end": max(page_numbers) if page_numbers else None,
        })

    end_char_values = [
        int(item["end_char"])
        for item in descriptors
        if item.get("end_char") is not None
    ]
    source_page_counts = [
        int(item["source_page_count"])
        for item in descriptors
        if item.get("source_page_count") is not None
    ]
    observed_pages = [
        int(item["page_number"])
        for item in descriptors
        if item.get("page_number") is not None
    ]

    return {
        "contract": DOCUMENT_INTELLIGENCE_MAP_CONTRACT,
        "source_hash": source.source_hash,
        "target_version": source.version_number,
        "chunk_count": chunk_count,
        "source_chars": max(end_char_values) if end_char_values else 0,
        "page_count": (
            max(source_page_counts)
            if source_page_counts
            else (max(observed_pages) if observed_pages else None)
        ),
        "band_count": len(bands),
        "bands": bands,
        "coverage": "full_chunk_manifest",
    }


def _write_object_embedding_state(
    intelligence_object: WorkspaceIntelligenceObject,
    *,
    source: _SourceSnapshot,
    chunk_count: int,
    manifest_checksum: str,
    reused: bool,
    document_map: dict,
) -> None:
    now = _utc_now()
    metadata = safe_metadata_payload(intelligence_object.metadata_json)

    intelligence_object.embedding_status = WORKSPACE_INTELLIGENCE_READY_STATUS
    intelligence_object.embedding_contract = WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT
    intelligence_object.embedding_model = _model_key()
    intelligence_object.embedding_ref = (
        f"workspace_intelligence_chunks:{intelligence_object.id}"
    )
    intelligence_object.embedding_vector = None
    intelligence_object.embedding_dimension = int(settings.EMBED_DIM)
    intelligence_object.embedding_checksum = manifest_checksum
    intelligence_object.embedded_at = now
    intelligence_object.error_message = None
    intelligence_object.metadata_json = {
        **metadata,
        "document_embeddings": {
            "source": DOCUMENT_EMBEDDING_SOURCE,
            "artifact_type": DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
            "processor_key": DOCUMENT_EMBEDDING_PROCESSOR_KEY,
            "processor_version": DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
            "source_hash": source.source_hash,
            "target_version": source.version_number,
            "model": _model_key(),
            "dimension": int(settings.EMBED_DIM),
            "chunk_contract": WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT,
            "embedding_contract": WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
            "chunk_chars": DOCUMENT_EMBEDDING_CHUNK_CHARS,
            "chunk_overlap": DOCUMENT_EMBEDDING_CHUNK_OVERLAP,
            "chunk_count": chunk_count,
            "manifest_checksum": manifest_checksum,
            "reused_identical_content": bool(reused),
        },
        "document_intelligence_map": dict(document_map or {}),
    }


def _persist_reused_chunks(
    *,
    context: IntelligenceJobExecutionContext,
    source: _SourceSnapshot,
    reusable_chunks: list[_ReusableChunk],
) -> tuple[str, int]:
    db_session = SessionLocal.session_factory()

    try:
        _, intelligence_object = _validate_current_source(
            db_session=db_session,
            source=source,
            context=context,
        )
        context.raise_if_execution_invalid()

        db_session.query(WorkspaceIntelligenceChunk).filter(
            WorkspaceIntelligenceChunk.intelligence_object_id
            == intelligence_object.id
        ).delete(synchronize_session=False)

        manifest_parts: list[tuple[str, str]] = []
        for reusable in reusable_chunks:
            locator = dict(reusable.source_locator_json or {})
            locator.update({
                "file_registry_id": source.file_registry_id,
                "document_id": source.document_id,
                "source_hash": source.source_hash,
                "target_version": source.version_number,
            })
            metadata = dict(reusable.metadata_json or {})
            metadata.update({
                "source": DOCUMENT_EMBEDDING_SOURCE,
                "reused_identical_content": True,
            })

            row = WorkspaceIntelligenceChunk(
                intelligence_object_id=intelligence_object.id,
                chunk_contract=WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT,
                chunk_kind=reusable.chunk_kind,
                chunk_order=reusable.chunk_order,
                title=reusable.title,
                content=reusable.content,
                content_hash=reusable.content_hash,
                token_count=reusable.token_count,
                source_locator_json=locator,
                metadata_json=metadata,
                embedding_status=WORKSPACE_INTELLIGENCE_READY_STATUS,
                embedding_contract=WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
                embedding_model=reusable.embedding_model,
                embedding_ref=f"content_hash:{reusable.content_hash}",
                embedding_vector=reusable.embedding_vector,
                embedding_dimension=reusable.embedding_dimension,
                embedding_checksum=reusable.embedding_checksum,
                embedded_at=_utc_now(),
                error_message=None,
            )
            db_session.add(row)
            manifest_parts.append(
                (reusable.content_hash, reusable.embedding_checksum)
            )

        manifest_checksum = _manifest_checksum(
            manifest_parts,
            model_key=_model_key(),
        )
        document_map = _build_document_intelligence_map(
            source=source,
            chunks=reusable_chunks,
        )
        _write_object_embedding_state(
            intelligence_object,
            source=source,
            chunk_count=len(reusable_chunks),
            manifest_checksum=manifest_checksum,
            reused=True,
            document_map=document_map,
        )
        db_session.commit()
        return manifest_checksum, len(reusable_chunks)
    except (IntelligenceJobTerminalError, IntelligenceJobRetryableError):
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise IntelligenceJobRetryableError(
            "Reused document embedding persistence failed: "
            f"{type(exc).__name__}: {exc}",
            failure_code="document_embedding_persistence_failed",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="embedding_persistence",
        ) from exc
    finally:
        db_session.close()


def _persist_generated_chunks(
    *,
    context: IntelligenceJobExecutionContext,
    source: _SourceSnapshot,
    chunks: list[_EvidenceChunk],
    vectors: list[list[float]],
) -> tuple[str, int]:
    if len(chunks) != len(vectors):
        raise IntelligenceJobRetryableError(
            "Embedding runtime returned a vector count that does not match chunks.",
            failure_code="document_embedding_vector_count_mismatch",
            retry_delay_seconds=int(settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS),
            stage="embedding_generation",
        )

    db_session = SessionLocal.session_factory()

    try:
        _, intelligence_object = _validate_current_source(
            db_session=db_session,
            source=source,
            context=context,
        )
        context.raise_if_execution_invalid()

        db_session.query(WorkspaceIntelligenceChunk).filter(
            WorkspaceIntelligenceChunk.intelligence_object_id
            == intelligence_object.id
        ).delete(synchronize_session=False)

        manifest_parts: list[tuple[str, str]] = []
        for chunk, vector in zip(chunks, vectors):
            normalized_vector = [float(value) for value in vector]
            if len(normalized_vector) != int(settings.EMBED_DIM):
                raise IntelligenceJobRetryableError(
                    "Embedding runtime returned an unexpected vector dimension.",
                    failure_code="document_embedding_dimension_mismatch",
                    retry_delay_seconds=int(
                        settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
                    ),
                    stage="embedding_generation",
                )

            checksum = _embedding_checksum(
                content_hash=chunk.content_hash,
                model_key=_model_key(),
                vector=normalized_vector,
            )
            locator = {
                "file_registry_id": source.file_registry_id,
                "document_id": source.document_id,
                "source_hash": source.source_hash,
                "target_version": source.version_number,
                "start_char": chunk.start_char,
                "end_char": chunk.end_char,
            }
            if chunk.page_number is not None:
                locator["page_number"] = chunk.page_number
            if chunk.source_page_count is not None:
                locator["source_page_count"] = chunk.source_page_count

            row = WorkspaceIntelligenceChunk(
                intelligence_object_id=intelligence_object.id,
                chunk_contract=WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT,
                chunk_kind="body",
                chunk_order=chunk.chunk_order,
                title=source.original_name,
                content=chunk.content,
                content_hash=chunk.content_hash,
                token_count=None,
                source_locator_json=locator,
                metadata_json={
                    "source": DOCUMENT_EMBEDDING_SOURCE,
                    "processor_key": DOCUMENT_EMBEDDING_PROCESSOR_KEY,
                    "processor_version": DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
                    "reused_identical_content": False,
                },
                embedding_status=WORKSPACE_INTELLIGENCE_READY_STATUS,
                embedding_contract=WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
                embedding_model=_model_key(),
                embedding_ref=f"content_hash:{chunk.content_hash}",
                embedding_vector=normalized_vector,
                embedding_dimension=len(normalized_vector),
                embedding_checksum=checksum,
                embedded_at=_utc_now(),
                error_message=None,
            )
            db_session.add(row)
            manifest_parts.append((chunk.content_hash, checksum))

        manifest_checksum = _manifest_checksum(
            manifest_parts,
            model_key=_model_key(),
        )
        document_map = _build_document_intelligence_map(
            source=source,
            chunks=chunks,
        )
        _write_object_embedding_state(
            intelligence_object,
            source=source,
            chunk_count=len(chunks),
            manifest_checksum=manifest_checksum,
            reused=False,
            document_map=document_map,
        )
        db_session.commit()
        return manifest_checksum, len(chunks)
    except (IntelligenceJobTerminalError, IntelligenceJobRetryableError):
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise IntelligenceJobRetryableError(
            "Document embedding persistence failed: "
            f"{type(exc).__name__}: {exc}",
            failure_code="document_embedding_persistence_failed",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="embedding_persistence",
        ) from exc
    finally:
        db_session.close()


def _embed_chunks_bounded(
    *,
    context: IntelligenceJobExecutionContext,
    chunks: list[_EvidenceChunk],
) -> list[list[float]]:
    batch_size = max(1, int(settings.SIS_EMBEDDING_MAX_BATCH_SIZE))
    vectors: list[list[float]] = []
    total_batches = max(1, (len(chunks) + batch_size - 1) // batch_size)

    for batch_index, start in enumerate(
        range(0, len(chunks), batch_size),
        start=1,
    ):
        context.raise_if_execution_invalid()
        batch_started_at = time.perf_counter()
        batch = chunks[start : start + batch_size]
        batch_texts = [chunk.content for chunk in batch]
        prepared_at = time.perf_counter()
        logger.info(
            "[SIS][P2_BATCH_DISPATCH_TIMING] phase=prepared job_id=%s batch=%s/%s "
            "chunks=%s chars=%s prepare_ms=%.3f",
            str(context.job.job_id),
            batch_index,
            total_batches,
            len(batch),
            sum(len(text) for text in batch_texts),
            (prepared_at - batch_started_at) * 1000.0,
        )
        dispatch_started_at = time.perf_counter()
        batch_vectors = execute_embeddings_on_configured_compute(
            batch_texts,
            call_site="document_embedding_generation",
            priority="P2",
            request_id=str(context.job.job_id),
        )
        dispatch_completed_at = time.perf_counter()
        logger.info(
            "[SIS][P2_BATCH_DISPATCH_TIMING] phase=complete job_id=%s batch=%s/%s "
            "dispatch_ms=%.3f vectors=%s",
            str(context.job.job_id),
            batch_index,
            total_batches,
            (dispatch_completed_at - dispatch_started_at) * 1000.0,
            len(batch_vectors),
        )
        if len(batch_vectors) != len(batch):
            raise IntelligenceJobRetryableError(
                "Embedding runtime returned an incomplete bounded batch.",
                failure_code="document_embedding_vector_count_mismatch",
                retry_delay_seconds=int(
                    settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
                ),
                stage="embedding_generation",
            )
        vectors.extend(batch_vectors)

        progress_span = (
            DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_COMPLETE
            - DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_STARTED
        )
        progress_percent = (
            DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_STARTED
            + int(round(progress_span * batch_index / total_batches))
        )
        context.record_stage(
            "embedding_generation",
            progress_percent=min(
                DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_COMPLETE,
                progress_percent,
            ),
            message="Generating bounded durable document embedding batches.",
            details={
                "batch": batch_index,
                "batches": total_batches,
                "batch_chunks": len(batch),
                "embedded_chunks": len(vectors),
                "total_chunks": len(chunks),
            },
        )

    return vectors


def process_generate_document_embeddings(
    context: IntelligenceJobExecutionContext,
) -> IntelligenceJobProcessorResult:
    """Process one durable GENERATE_DOCUMENT_EMBEDDINGS job."""

    context.raise_if_execution_invalid()
    source = _load_source_snapshot(context)

    context.record_stage(
        "source_validated",
        progress_percent=DOCUMENT_EMBEDDING_PROGRESS_SOURCE_VALIDATED,
        message="Document embedding source identity validated.",
        details={
            "file_registry_id": source.file_registry_id,
            "document_id": source.document_id,
            "target_version": source.version_number,
            "source_hash": source.source_hash,
        },
    )

    reusable_chunks = _load_reusable_chunks(source)
    if reusable_chunks:
        context.record_stage(
            "embedding_reuse",
            progress_percent=DOCUMENT_EMBEDDING_PROGRESS_PERSISTENCE_STARTED,
            message="Reusing durable vectors for identical document content.",
            details={"chunk_count": len(reusable_chunks)},
        )
        manifest_checksum, chunk_count = _persist_reused_chunks(
            context=context,
            source=source,
            reusable_chunks=reusable_chunks,
        )
        context.record_stage(
            "embeddings_persisted",
            progress_percent=DOCUMENT_EMBEDDING_PROGRESS_ARTIFACT_READY,
            message="Reused document embeddings persisted for this file identity.",
            details={
                "chunk_count": chunk_count,
                "manifest_checksum": manifest_checksum,
                "reused": True,
            },
        )
        logger.info(
            "[SIS][DOCUMENT_EMBEDDINGS_REUSED] job_id=%s document_id=%s "
            "chunks=%s source_hash=%s",
            context.job.job_id,
            source.document_id,
            chunk_count,
            source.source_hash,
        )
        return IntelligenceJobProcessorResult(
            result={
                "artifact_type": DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
                "document_id": source.document_id,
                "source_hash": source.source_hash,
                "chunk_count": chunk_count,
                "manifest_checksum": manifest_checksum,
                "model": _model_key(),
                "dimension": int(settings.EMBED_DIM),
                "reused": True,
            },
            intelligence_object_id=source.intelligence_object_id,
            stage="embeddings_persisted",
        )

    context.record_stage(
        "docintel_extraction",
        progress_percent=DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_STARTED,
        message="Extracting source text for durable document embeddings.",
    )

    try:
        docintel_packet = ingest_documents_for_intent(
            intent=None,
            resolved_paths=[source.path],
            progress_callback=_make_docintel_progress_callback(context),
        )
    except DocIntelIngestError as exc:
        raise IntelligenceJobTerminalError(
            f"DocIntel extraction failed: {exc}",
            failure_code="document_embedding_docintel_failed",
            stage="docintel_extraction",
        ) from exc
    except Exception as exc:
        raise IntelligenceJobRetryableError(
            f"Unexpected DocIntel failure: {type(exc).__name__}: {exc}",
            failure_code="document_embedding_docintel_unavailable",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="docintel_extraction",
        ) from exc

    document = select_docintel_document(docintel_packet)
    document_text = clean_multiline_text(document.get("text"))
    if not document_text:
        raise IntelligenceJobTerminalError(
            "DocIntel returned no extracted text for document embeddings.",
            failure_code="document_embedding_source_text_empty",
            stage="docintel_extraction",
        )

    chunks = _chunk_document_text(document_text)
    if not chunks:
        raise IntelligenceJobTerminalError(
            "Document embedding chunking produced no textual evidence.",
            failure_code="document_embedding_chunks_empty",
            stage="docintel_extraction",
        )

    context.raise_if_execution_invalid()
    context.record_stage(
        "docintel_extracted",
        progress_percent=DOCUMENT_EMBEDDING_PROGRESS_EXTRACTION_COMPLETE,
        message="Source text extracted and deterministically chunked.",
        details={
            "source_chars": len(document_text),
            "chunk_count": len(chunks),
        },
    )
    context.record_stage(
        "embedding_generation",
        progress_percent=DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_STARTED,
        message="Generating durable document evidence embeddings through SIS.",
        details={
            "chunk_count": len(chunks),
            "model": _model_key(),
        },
    )

    try:
        vectors = _embed_chunks_bounded(
            context=context,
            chunks=chunks,
        )
    except (IntelligenceJobRetryableError, IntelligenceJobTerminalError):
        raise
    except Exception as exc:
        raise IntelligenceJobRetryableError(
            f"SIS embedding runtime failed: {type(exc).__name__}: {exc}",
            failure_code="document_embedding_runtime_failed",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="embedding_generation",
        ) from exc

    context.raise_if_execution_invalid()
    context.record_stage(
        "embeddings_generated",
        progress_percent=DOCUMENT_EMBEDDING_PROGRESS_EMBEDDING_COMPLETE,
        message="Document evidence embedding generation completed.",
        details={
            "chunk_count": len(chunks),
            "vector_count": len(vectors),
            "dimension": int(settings.EMBED_DIM),
        },
    )
    context.record_stage(
        "embedding_persistence",
        progress_percent=DOCUMENT_EMBEDDING_PROGRESS_PERSISTENCE_STARTED,
        message="Persisting durable document evidence embeddings.",
        details={"chunk_count": len(chunks)},
    )

    manifest_checksum, chunk_count = _persist_generated_chunks(
        context=context,
        source=source,
        chunks=chunks,
        vectors=vectors,
    )

    context.record_stage(
        "embeddings_persisted",
        progress_percent=DOCUMENT_EMBEDDING_PROGRESS_ARTIFACT_READY,
        message="Document embeddings persisted; finalizing durable job.",
        details={
            "chunk_count": chunk_count,
            "manifest_checksum": manifest_checksum,
            "reused": False,
        },
    )
    logger.info(
        "[SIS][DOCUMENT_EMBEDDINGS_COMPLETE] job_id=%s document_id=%s "
        "source_chars=%s chunks=%s model=%s dimension=%s source_hash=%s",
        context.job.job_id,
        source.document_id,
        len(document_text),
        chunk_count,
        _model_key(),
        int(settings.EMBED_DIM),
        source.source_hash,
    )

    return IntelligenceJobProcessorResult(
        result={
            "artifact_type": DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
            "document_id": source.document_id,
            "source_hash": source.source_hash,
            "chunk_count": chunk_count,
            "manifest_checksum": manifest_checksum,
            "model": _model_key(),
            "dimension": int(settings.EMBED_DIM),
            "reused": False,
        },
        intelligence_object_id=source.intelligence_object_id,
        stage="embeddings_persisted",
    )


__all__ = [
    "DOCUMENT_EMBEDDING_JOB_TYPE",
    "process_generate_document_embeddings",
]

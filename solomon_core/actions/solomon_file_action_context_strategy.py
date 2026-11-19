# -------------------------------------------------------------------
# FILE: solomon_file_action_context_strategy.py
# DIRECTORY: solomon_core/actions/
# -------------------------------------------------------------------
# Adaptive large-resource context selection for governed file Actions.
#
# Solomon does not equate file size with model context size. For large,
# version-bound resources this module consumes the existing durable
# WorkspaceIntelligenceChunk representation and deterministically chooses the
# smallest qualified context strategy for the registered Action:
#
#   direct                -> caller keeps the existing bounded/full-source path
#   hierarchical_global   -> distributed whole-document evidence for global work
#   exhaustive_signal     -> full persisted-chunk scan for coverage-sensitive work
#
# A future targeted Action can use the same durable chunk authority for hybrid
# lexical/semantic retrieval without changing the Action execution contract.
# This module performs no model calls and owns no authorization decisions.
# -------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import Any

from config import settings
from solomon_core.db import SessionLocal
from solomon_core.llm.llm_prompting import MAX_LLM_INPUT_CHARS
from solomon_core.models import (
    FileRegistry,
    WorkspaceIntelligenceChunk,
    WorkspaceIntelligenceObject,
)
from solomon_core.intelligence_service.document_embedding_contract import (
    DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
    DOCUMENT_EMBEDDING_JOB_TYPE,
    DOCUMENT_EMBEDDING_LAZY_TRIGGER_TYPE,
    DOCUMENT_EMBEDDING_PRIORITY,
    DOCUMENT_EMBEDDING_PROCESSOR_KEY,
    DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
    DOCUMENT_EMBEDDING_SOURCE,
    DOCUMENT_EMBEDDING_TARGET_TYPE,
    DOCUMENT_INTELLIGENCE_MAP_CONTRACT,
)
from solomon_core.intelligence_service.intelligence_job_repository import (
    IntelligenceJobEnqueueSpec,
    IntelligenceJobRepository,
    build_intelligence_job_idempotency_key,
)
from solomon_core.workspace_intelligence.workspace_intelligence_index import (
    WORKSPACE_INTELLIGENCE_READY_STATUS,
    clean_multiline_text,
    record_supports_text_enrichment,
    representative_document_lines,
    safe_metadata_payload,
    upsert_file_intelligence_object,
)


CONTEXT_STRATEGY_DIRECT = "direct"
CONTEXT_STRATEGY_HIERARCHICAL_GLOBAL = "hierarchical_global"
CONTEXT_STRATEGY_EXHAUSTIVE_SIGNAL = "exhaustive_signal"
CONTEXT_STRATEGY_TARGETED_HYBRID = "targeted_hybrid"

LARGE_RESOURCE_PREPARATION_CONTRACT = "solomon_large_resource_preparation_v1"
LARGE_RESOURCE_LAZY_FILE_SIZE_BYTES = 1_000_000

_INTELLIGENCE_JOB_REPOSITORY = IntelligenceJobRepository()

_GLOBAL_ACTION_IDS = frozenset({
    "key_points.extract",
    "document.explain",
})
_EXHAUSTIVE_ACTION_IDS = frozenset({
    "dates_deadlines.extract",
    "action_items.extract",
})

_TEMPORAL_SIGNAL_PATTERNS = (
    re.compile(
        r"\b(?:jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|jun(?:e)?|"
        r"jul(?:y)?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|"
        r"dec(?:ember)?)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b",
        re.IGNORECASE,
    ),
    re.compile(r"\b(?:19|20)\d{2}[-/.](?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])\b"),
    re.compile(r"\b(?:0?[1-9]|1[0-2])[-/.](?:0?[1-9]|[12]\d|3[01])[-/.](?:(?:19|20)?\d{2})\b"),
    re.compile(r"\b(?:[01]?\d|2[0-3]):[0-5]\d\b"),
    re.compile(r"\b(?:0?[1-9]|1[0-2])(?::[0-5]\d)?\s*[ap]\.?m\.?\b", re.IGNORECASE),
    re.compile(r"\b\d+\s+(?:business\s+)?(?:day|days|week|weeks|month|months|year|years|hour|hours)\b", re.IGNORECASE),
    re.compile(r"\b(?:today|tomorrow|tonight|noon|midnight|end of day|end of week|end of month|before close of business)\b", re.IGNORECASE),
)
_ACTION_SIGNAL_RE = re.compile(
    r"\b(?:must|shall|should|required to|needs? to|expected to|responsible for|"
    r"action required|approval required|due by|submit|provide|install|confirm|"
    r"review|approve|coordinate|complete|prepare|deliver|send|update|verify|"
    r"remove|replace|carry|inspect|notify|schedule|pay|respond|follow up)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class _PersistedChunk:
    chunk_order: int
    content: str
    start_char: int | None
    end_char: int | None
    page_number: int | None
    source_page_count: int | None


@dataclass(frozen=True)
class ActionContextResolution:
    text: str
    evidence: dict[str, Any]


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _context_budget() -> int:
    configured_limit = max(
        1200,
        int(settings.SIS_FILE_ACTION_SOURCE_MAX_CHARS),
    )
    transport_limit = max(
        1200,
        int(MAX_LLM_INPUT_CHARS * 0.55),
    )
    return min(configured_limit, transport_limit)


def _row_matches_current_source(
    row: WorkspaceIntelligenceChunk,
    *,
    source_hash: str,
    source_version: int,
) -> bool:
    locator = (
        dict(row.source_locator_json)
        if isinstance(row.source_locator_json, dict)
        else {}
    )
    locator_hash = _clean(locator.get("source_hash"))
    locator_version = _safe_int(locator.get("target_version"), source_version)

    return bool(
        row.embedding_status == WORKSPACE_INTELLIGENCE_READY_STATUS
        and row.content
        and (not locator_hash or locator_hash == source_hash)
        and locator_version == source_version
    )


def _load_current_persisted_chunks(
    entry: dict,
) -> tuple[list[_PersistedChunk], dict]:
    file_id = _safe_int(entry.get("file_id"))
    source_hash = _clean(entry.get("checksum"))
    source_version = _safe_int(entry.get("version_number"), 1)

    if not file_id or not source_hash:
        return [], {}

    db_session = SessionLocal()

    try:
        intelligence_object = (
            db_session.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.file_registry_id == file_id,
                WorkspaceIntelligenceObject.object_type == "file",
                WorkspaceIntelligenceObject.status == "active",
                WorkspaceIntelligenceObject.source_hash == source_hash,
            )
            .order_by(WorkspaceIntelligenceObject.id.desc())
            .first()
        )

        if not intelligence_object:
            return [], {}

        rows = (
            db_session.query(WorkspaceIntelligenceChunk)
            .filter(
                WorkspaceIntelligenceChunk.intelligence_object_id
                == intelligence_object.id,
                WorkspaceIntelligenceChunk.embedding_status
                == WORKSPACE_INTELLIGENCE_READY_STATUS,
            )
            .order_by(WorkspaceIntelligenceChunk.chunk_order.asc())
            .all()
        )

        chunks: list[_PersistedChunk] = []
        for row in rows:
            if not _row_matches_current_source(
                row,
                source_hash=source_hash,
                source_version=source_version,
            ):
                continue

            locator = (
                dict(row.source_locator_json)
                if isinstance(row.source_locator_json, dict)
                else {}
            )
            content = clean_multiline_text(row.content)
            if not content:
                continue

            chunks.append(
                _PersistedChunk(
                    chunk_order=int(row.chunk_order or 0),
                    content=content,
                    start_char=(
                        _safe_int(locator.get("start_char"))
                        if locator.get("start_char") is not None
                        else None
                    ),
                    end_char=(
                        _safe_int(locator.get("end_char"))
                        if locator.get("end_char") is not None
                        else None
                    ),
                    page_number=(
                        _safe_int(locator.get("page_number"))
                        if locator.get("page_number") is not None
                        else None
                    ),
                    source_page_count=(
                        _safe_int(locator.get("source_page_count"))
                        if locator.get("source_page_count") is not None
                        else None
                    ),
                )
            )

        metadata = (
            dict(intelligence_object.metadata_json)
            if isinstance(intelligence_object.metadata_json, dict)
            else {}
        )
        document_map = metadata.get("document_intelligence_map")
        if not isinstance(document_map, dict):
            document_map = {}

        if document_map:
            if (
                _clean(document_map.get("contract"))
                != DOCUMENT_INTELLIGENCE_MAP_CONTRACT
                or _clean(document_map.get("source_hash")) != source_hash
                or _safe_int(document_map.get("target_version")) != source_version
            ):
                document_map = {}

        return chunks, document_map
    finally:
        db_session.close()


def _source_char_extent(chunks: list[_PersistedChunk]) -> int:
    end_values = [
        int(chunk.end_char)
        for chunk in chunks
        if chunk.end_char is not None and int(chunk.end_char) > 0
    ]
    if end_values:
        return max(end_values)

    if not chunks:
        return 0

    # Fixed overlap means sum(content) slightly overstates unique source size,
    # which is conservative for choosing the large-resource path.
    return sum(len(chunk.content) for chunk in chunks)


def _page_label(chunk: _PersistedChunk) -> str:
    if chunk.page_number is not None:
        return f"Page {chunk.page_number}"
    return f"Chunk {chunk.chunk_order + 1}"


def _clip(value: str, limit: int) -> str:
    clean = clean_multiline_text(value)
    if len(clean) <= limit:
        return clean

    clipped = clean[: max(1, limit + 1)].rsplit(" ", 1)[0].strip()
    return clipped or clean[:limit].strip()


def _chunk_salience_text(chunk: _PersistedChunk, limit: int) -> str:
    lines = representative_document_lines(chunk.content, limit=4)
    if lines:
        candidate = "\n".join(lines)
    else:
        candidate = chunk.content

    return _clip(candidate, limit)


def _hierarchical_global_context(
    chunks: list[_PersistedChunk],
    *,
    budget: int,
    document_map: dict | None = None,
) -> ActionContextResolution:
    if not chunks:
        return ActionContextResolution(text="", evidence={})

    # Use enough bands to distribute evidence across the whole document while
    # reserving useful room for each span. This is deterministic and bounded.
    desired_bands = max(4, min(18, budget // 340))
    band_count = min(len(chunks), desired_bands)
    per_band_budget = max(180, int((budget - (band_count * 52)) / band_count))

    parts: list[str] = []
    selected_orders: list[int] = []

    for band_index in range(band_count):
        start = int((band_index * len(chunks)) / band_count)
        end = int(((band_index + 1) * len(chunks)) / band_count)
        end = max(start + 1, end)
        band = chunks[start:min(len(chunks), end)]
        if not band:
            continue

        # Prefer the middle of each contiguous band. It avoids systematic
        # head-only bias and gives every document region representation.
        selected = band[len(band) // 2]
        snippet = _chunk_salience_text(
            selected,
            limit=per_band_budget,
        )
        if not snippet:
            continue

        first_page = next(
            (c.page_number for c in band if c.page_number is not None),
            None,
        )
        last_page = next(
            (c.page_number for c in reversed(band) if c.page_number is not None),
            None,
        )
        if first_page is not None and last_page is not None:
            span_label = (
                f"pages {first_page}-{last_page}"
                if first_page != last_page
                else f"page {first_page}"
            )
        else:
            span_label = f"chunks {band[0].chunk_order + 1}-{band[-1].chunk_order + 1}"

        parts.append(
            f"[Document span {band_index + 1} of {band_count} | {span_label}]\n"
            f"{snippet}"
        )
        selected_orders.append(selected.chunk_order)

    context = clean_multiline_text("\n\n".join(parts))
    if len(context) > budget:
        context = context[:budget].rstrip()

    map_contract = _clean((document_map or {}).get("contract"))
    return ActionContextResolution(
        text=context,
        evidence={
            "evidence_source": "persisted_workspace_intelligence_chunks",
            "context_strategy": CONTEXT_STRATEGY_HIERARCHICAL_GLOBAL,
            "complete_source_coverage": False,
            "complete_document_map_coverage": True,
            "source_chunk_count": len(chunks),
            "selected_chunk_count": len(selected_orders),
            "selected_chunk_orders": selected_orders,
            "document_map_contract": map_contract or None,
        },
    )


def _line_matches_exhaustive_action(action_id: str, line: str) -> bool:
    if action_id == "dates_deadlines.extract":
        return any(
            pattern.search(line or "")
            for pattern in _TEMPORAL_SIGNAL_PATTERNS
        )

    if action_id == "action_items.extract":
        return bool(_ACTION_SIGNAL_RE.search(line or ""))

    return False


def _exhaustive_signal_context(
    chunks: list[_PersistedChunk],
    *,
    action_id: str,
    budget: int,
    document_map: dict | None = None,
) -> ActionContextResolution:
    if not chunks:
        return ActionContextResolution(text="", evidence={})

    candidate_lines: list[tuple[_PersistedChunk, str]] = []
    seen: set[str] = set()

    # Scan every persisted chunk. Overlap is deduplicated before budgeting, so
    # coverage-sensitive Actions are not reduced to arbitrary top-K retrieval.
    for chunk in chunks:
        for raw_line in chunk.content.splitlines():
            line = _clip(raw_line, 420)
            key = re.sub(r"\s+", " ", line).strip().casefold()

            if (
                not line
                or len(line) < 8
                or key in seen
                or not _line_matches_exhaustive_action(action_id, line)
            ):
                continue

            seen.add(key)
            candidate_lines.append((chunk, line))

    if not candidate_lines:
        fallback = _hierarchical_global_context(
            chunks,
            budget=budget,
            document_map=document_map,
        )
        evidence = {
            **fallback.evidence,
            "context_strategy": CONTEXT_STRATEGY_EXHAUSTIVE_SIGNAL,
            "complete_source_scan": True,
            "candidate_line_count": 0,
            "candidate_lines_in_context": 0,
            "candidate_coverage_complete": True,
            "fallback_context_strategy": CONTEXT_STRATEGY_HIERARCHICAL_GLOBAL,
        }
        return ActionContextResolution(
            text=fallback.text,
            evidence=evidence,
        )

    formatted_candidates = [
        (chunk, f"[{_page_label(chunk)}] {line}")
        for chunk, line in candidate_lines
    ]

    # When every candidate cannot fit, sample evenly across the complete
    # candidate set instead of taking only the beginning of the document.
    approximate_line_budget = max(1, budget // 180)
    if len(formatted_candidates) <= approximate_line_budget:
        selected_candidates = formatted_candidates
    elif approximate_line_budget == 1:
        selected_candidates = [formatted_candidates[len(formatted_candidates) // 2]]
    else:
        selected_indices = []
        for index in range(approximate_line_budget):
            selected_index = round(
                index
                * (len(formatted_candidates) - 1)
                / (approximate_line_budget - 1)
            )
            if selected_index not in selected_indices:
                selected_indices.append(selected_index)
        selected_candidates = [
            formatted_candidates[index]
            for index in selected_indices
        ]

    parts: list[str] = []
    consumed_chunks: set[int] = set()

    for chunk, candidate in selected_candidates:
        addition = candidate if not parts else f"\n{candidate}"
        current_length = sum(len(part) for part in parts)

        if current_length + len(addition) > budget:
            continue

        parts.append(addition)
        consumed_chunks.add(chunk.chunk_order)

    consumed = len(parts)
    context = clean_multiline_text("".join(parts))
    map_contract = _clean((document_map or {}).get("contract"))

    return ActionContextResolution(
        text=context,
        evidence={
            "evidence_source": "persisted_workspace_intelligence_chunks",
            "context_strategy": CONTEXT_STRATEGY_EXHAUSTIVE_SIGNAL,
            "complete_source_coverage": False,
            "complete_source_scan": True,
            "source_chunk_count": len(chunks),
            "selected_chunk_count": len(consumed_chunks),
            "candidate_line_count": len(candidate_lines),
            "candidate_lines_in_context": consumed,
            "candidate_coverage_complete": consumed == len(candidate_lines),
            "document_map_contract": map_contract or None,
        },
    )



def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _large_resource_preparation_required(
    *,
    entry: dict,
    intelligence_object: WorkspaceIntelligenceObject | None,
) -> bool:
    """Return whether a missing chunk set needs durable large-resource preparation."""

    file_size_bytes = _safe_int(entry.get("size_bytes"))
    extension = _clean(entry.get("extension")).lower()
    budget = _context_budget()

    # Raw text-like formats have a reasonably direct byte-to-context relationship.
    if extension in {".txt", ".csv"} and file_size_bytes > max(24000, budget * 2):
        return True

    # Compressed/binary office/PDF resources are less directly comparable to
    # model context. A conservative one-megabyte floor avoids turning ordinary
    # small documents into lazy-preparation work solely because they are binary.
    if file_size_bytes >= LARGE_RESOURCE_LAZY_FILE_SIZE_BYTES:
        return True

    if intelligence_object is None:
        return False

    metadata = (
        dict(intelligence_object.metadata_json)
        if isinstance(intelligence_object.metadata_json, dict)
        else {}
    )
    cache = metadata.get("summary_evidence_cache")
    if not isinstance(cache, dict):
        return False

    extraction = cache.get("extraction")
    if not isinstance(extraction, dict):
        return False

    if extraction.get("complete_source_coverage") is False:
        return True

    source_page_count = _safe_int(extraction.get("source_page_count"))
    evidence_pages = extraction.get("evidence_pages")
    if (
        source_page_count > 0
        and isinstance(evidence_pages, list)
        and len(evidence_pages) < source_page_count
    ):
        return True

    return False


def _current_ready_chunk_count(
    db_session,
    *,
    intelligence_object_id: int,
    source_hash: str,
    source_version: int,
) -> int:
    rows = (
        db_session.query(WorkspaceIntelligenceChunk)
        .filter(
            WorkspaceIntelligenceChunk.intelligence_object_id
            == intelligence_object_id,
            WorkspaceIntelligenceChunk.embedding_status
            == WORKSPACE_INTELLIGENCE_READY_STATUS,
        )
        .all()
    )
    return sum(
        1
        for row in rows
        if _row_matches_current_source(
            row,
            source_hash=source_hash,
            source_version=source_version,
        )
    )




def _current_document_map_ready(
    intelligence_object: WorkspaceIntelligenceObject,
    *,
    source_hash: str,
    source_version: int,
) -> bool:
    metadata = (
        dict(intelligence_object.metadata_json)
        if isinstance(intelligence_object.metadata_json, dict)
        else {}
    )
    document_map = metadata.get("document_intelligence_map")
    if not isinstance(document_map, dict):
        return False

    return bool(
        _clean(document_map.get("contract")) == DOCUMENT_INTELLIGENCE_MAP_CONTRACT
        and _clean(document_map.get("source_hash")) == source_hash
        and _safe_int(document_map.get("target_version")) == source_version
        and _safe_int(document_map.get("chunk_count")) > 0
    )


def ensure_large_resource_action_preparation(
    *,
    definition,
    entry: dict,
    request_id: str = "",
) -> dict[str, Any]:
    """Ensure one current large resource has durable chunks/map preparation queued.

    This is a lazy requalification path for governed files that predate the
    current embedding/document-map contract. It uses the existing durable
    Intelligence Spool and P2 embedding processor; it never performs model/SIS
    work synchronously in the foreground Action request.
    """

    action_id = _clean(getattr(definition, "action_id", ""))
    if action_id not in _GLOBAL_ACTION_IDS and action_id not in _EXHAUSTIVE_ACTION_IDS:
        return {}

    file_id = _safe_int(entry.get("file_id"))
    source_hash = _clean(entry.get("checksum"))
    source_version = _safe_int(entry.get("version_number"), 1)

    if not file_id or not source_hash:
        return {}

    db_session = SessionLocal()

    try:
        record = db_session.get(FileRegistry, file_id)
        if (
            record is None
            or _clean(getattr(record, "checksum", "")) != source_hash
            or _safe_int(getattr(record, "version_number", 1), 1) != source_version
        ):
            return {
                "large_resource_preparation_contract": LARGE_RESOURCE_PREPARATION_CONTRACT,
                "large_resource_preparation_required": True,
                "large_resource_preparation_state": "unavailable",
                "large_resource_preparation_reason": "source_identity_changed",
            }

        intelligence_object = (
            db_session.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.file_registry_id == file_id,
                WorkspaceIntelligenceObject.object_type == "file",
                WorkspaceIntelligenceObject.status == "active",
                WorkspaceIntelligenceObject.source_hash == source_hash,
            )
            .order_by(WorkspaceIntelligenceObject.id.desc())
            .first()
        )

        if intelligence_object is None:
            intelligence_object = upsert_file_intelligence_object(
                db_session=db_session,
                record=record,
                metadata=safe_metadata_payload(getattr(record, "meta", None)),
            )
            db_session.flush()

        if not _large_resource_preparation_required(
            entry=entry,
            intelligence_object=intelligence_object,
        ):
            return {}

        ready_chunk_count = _current_ready_chunk_count(
            db_session,
            intelligence_object_id=int(intelligence_object.id),
            source_hash=source_hash,
            source_version=source_version,
        )
        document_map_ready = _current_document_map_ready(
            intelligence_object,
            source_hash=source_hash,
            source_version=source_version,
        )
        if ready_chunk_count > 0 and document_map_ready:
            return {
                "large_resource_preparation_contract": LARGE_RESOURCE_PREPARATION_CONTRACT,
                "large_resource_preparation_required": True,
                "large_resource_preparation_state": "ready",
                "large_resource_preparation_chunk_count": ready_chunk_count,
                "large_resource_preparation_document_map_ready": True,
            }

        if not bool(settings.SIS_EMBEDDING_ENABLED):
            return {
                "large_resource_preparation_contract": LARGE_RESOURCE_PREPARATION_CONTRACT,
                "large_resource_preparation_required": True,
                "large_resource_preparation_state": "unavailable",
                "large_resource_preparation_reason": "embedding_disabled",
            }

        if not record_supports_text_enrichment(record):
            return {
                "large_resource_preparation_contract": LARGE_RESOURCE_PREPARATION_CONTRACT,
                "large_resource_preparation_required": True,
                "large_resource_preparation_state": "unavailable",
                "large_resource_preparation_reason": "unsupported_file_type",
            }

        model_key = _clean(settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME) or None
        idempotency_key = build_intelligence_job_idempotency_key(
            job_type=DOCUMENT_EMBEDDING_JOB_TYPE,
            artifact_type=DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
            target_type=DOCUMENT_EMBEDDING_TARGET_TYPE,
            target_id=_clean(record.random_name),
            target_version=source_version,
            source_hash=source_hash,
            processor_key=DOCUMENT_EMBEDDING_PROCESSOR_KEY,
            processor_version=DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
            model_key=model_key,
        )

        job = _INTELLIGENCE_JOB_REPOSITORY.enqueue(
            IntelligenceJobEnqueueSpec(
                job_type=DOCUMENT_EMBEDDING_JOB_TYPE,
                artifact_type=DOCUMENT_EMBEDDING_ARTIFACT_TYPE,
                target_type=DOCUMENT_EMBEDDING_TARGET_TYPE,
                target_id=_clean(record.random_name),
                target_version=source_version,
                source_hash=source_hash,
                trigger_type=DOCUMENT_EMBEDDING_LAZY_TRIGGER_TYPE,
                trigger_ref=_clean(record.random_name),
                idempotency_key=idempotency_key,
                priority=DOCUMENT_EMBEDDING_PRIORITY,
                user_id=getattr(record, "uploader_id", None),
                organization_id=getattr(intelligence_object, "organization_id", None),
                file_registry_id=file_id,
                intelligence_object_id=int(intelligence_object.id),
                request_id=_clean(request_id) or None,
                payload={
                    "document_id": _clean(record.random_name),
                    "original_name": _clean(record.original_name),
                    "extension": _clean(record.extension),
                    "preparation_contract": LARGE_RESOURCE_PREPARATION_CONTRACT,
                },
                processor_key=DOCUMENT_EMBEDDING_PROCESSOR_KEY,
                processor_version=DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
                model_key=model_key,
                max_attempts=3,
            ),
            session=db_session,
        )

        job_status = _clean(job.status).lower() or "pending"
        object_metadata = safe_metadata_payload(intelligence_object.metadata_json)
        intelligence_object.embedding_status = (
            WORKSPACE_INTELLIGENCE_READY_STATUS
            if job_status == "succeeded" and ready_chunk_count > 0
            else "pending"
        )
        intelligence_object.error_message = None
        intelligence_object.metadata_json = {
            **object_metadata,
            "embedding_source": DOCUMENT_EMBEDDING_SOURCE,
            "embedding_status": intelligence_object.embedding_status,
            "embedding_job_id": job.job_id,
            "embedding_source_hash": source_hash,
            "embedding_target_version": source_version,
            "embedding_processor_key": DOCUMENT_EMBEDDING_PROCESSOR_KEY,
            "embedding_processor_version": DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
            "large_resource_preparation": {
                "contract": LARGE_RESOURCE_PREPARATION_CONTRACT,
                "state": (
                    "ready"
                    if intelligence_object.embedding_status
                    == WORKSPACE_INTELLIGENCE_READY_STATUS
                    else "pending"
                ),
                "job_id": job.job_id,
                "job_status": job_status,
                "requested_at": _utc_now_iso(),
                "source_hash": source_hash,
                "target_version": source_version,
                "trigger_type": DOCUMENT_EMBEDDING_LAZY_TRIGGER_TYPE,
            },
        }

        record_metadata = safe_metadata_payload(getattr(record, "meta", None))
        record.meta = {
            **record_metadata,
            "workspace_intelligence_embedding_status": intelligence_object.embedding_status,
            "workspace_intelligence_embedding_job_id": job.job_id,
            "workspace_intelligence_embedding_job_status": job_status,
        }

        db_session.commit()

        return {
            "large_resource_preparation_contract": LARGE_RESOURCE_PREPARATION_CONTRACT,
            "large_resource_preparation_required": True,
            "large_resource_preparation_state": (
                "ready"
                if intelligence_object.embedding_status
                == WORKSPACE_INTELLIGENCE_READY_STATUS
                else "pending"
            ),
            "large_resource_preparation_job_id": job.job_id,
            "large_resource_preparation_job_status": job_status,
            "large_resource_preparation_processor_version": (
                DOCUMENT_EMBEDDING_PROCESSOR_VERSION
            ),
        }
    except Exception as exc:
        db_session.rollback()
        return {
            "large_resource_preparation_contract": LARGE_RESOURCE_PREPARATION_CONTRACT,
            "large_resource_preparation_required": True,
            "large_resource_preparation_state": "error",
            "large_resource_preparation_reason": (
                f"{type(exc).__name__}: {exc}"
            )[:320],
        }
    finally:
        db_session.close()

def resolve_large_resource_action_context(
    *,
    definition,
    entry: dict,
) -> ActionContextResolution | None:
    """Return a prepared large-resource Action context, or None for direct mode."""

    action_id = _clean(getattr(definition, "action_id", ""))
    if action_id not in _GLOBAL_ACTION_IDS and action_id not in _EXHAUSTIVE_ACTION_IDS:
        return None

    chunks, document_map = _load_current_persisted_chunks(entry)
    if not chunks:
        return None

    # Existing ready v1.0 chunks are already qualified evidence. If their
    # structural map predates v1.1, enqueue a content-bound metadata
    # requalification in the background while using those chunks immediately.
    if not document_map:
        ensure_large_resource_action_preparation(
            definition=definition,
            entry=entry,
            request_id="",
        )

    budget = _context_budget()
    source_chars = _source_char_extent(chunks)

    # Small resources retain the existing direct/cached evidence behavior.
    if source_chars and source_chars <= budget:
        return None

    if action_id in _EXHAUSTIVE_ACTION_IDS:
        result = _exhaustive_signal_context(
            chunks,
            action_id=action_id,
            budget=budget,
            document_map=document_map,
        )
    else:
        result = _hierarchical_global_context(
            chunks,
            budget=budget,
            document_map=document_map,
        )

    if not result.text:
        return None

    return ActionContextResolution(
        text=result.text,
        evidence={
            **result.evidence,
            "source_chars": source_chars,
            "context_budget_chars": budget,
            "large_resource": True,
        },
    )


__all__ = [
    "ActionContextResolution",
    "CONTEXT_STRATEGY_DIRECT",
    "CONTEXT_STRATEGY_EXHAUSTIVE_SIGNAL",
    "CONTEXT_STRATEGY_HIERARCHICAL_GLOBAL",
    "CONTEXT_STRATEGY_TARGETED_HYBRID",
    "DOCUMENT_INTELLIGENCE_MAP_CONTRACT",
    "LARGE_RESOURCE_PREPARATION_CONTRACT",
    "ensure_large_resource_action_preparation",
    "resolve_large_resource_action_context",
]

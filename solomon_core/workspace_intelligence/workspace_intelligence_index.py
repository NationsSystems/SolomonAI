# -------------------------------------------------------------------
# FILE: workspace_intelligence_index.py
# DIRECTORY: solomon_core/workspace_intelligence/
# -------------------------------------------------------------------
# Workspace Intelligence Index helpers for searchable and AI-queryable
# workspace objects.
# -------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib.parse import quote

from solomon_core.docintel.ingestion.docintel_ingestor import (
    DocIntelIngestError,
    ingest_documents_for_intent,
)
from solomon_core.logger import get_logger
from solomon_core.models import (
    FileRegistry,
    WorkspaceIntelligenceChunk,
    WorkspaceIntelligenceFact,
    WorkspaceIntelligenceObject,
)


logger = get_logger("workspace_intelligence.index")


WORKSPACE_INTELLIGENCE_FILE_OBJECT_TYPE = "file"
WORKSPACE_INTELLIGENCE_FILE_ICON = "description"
WORKSPACE_INTELLIGENCE_FILE_VISIBILITY_SCOPE = "owner"
WORKSPACE_INTELLIGENCE_INITIAL_STATUS = "pending"
WORKSPACE_INTELLIGENCE_READY_STATUS = "ready"
WORKSPACE_INTELLIGENCE_FAILED_STATUS = "failed"
WORKSPACE_INTELLIGENCE_SKIPPED_STATUS = "skipped"
WORKSPACE_INTELLIGENCE_SOURCE_CHANGED_REASON = "source_changed"
WORKSPACE_INTELLIGENCE_FILE_REGISTRATION_SOURCE = (
    "files_bp.create_file_registry_record"
)
WORKSPACE_INTELLIGENCE_FILE_ENRICHMENT_SOURCE = (
    "workspace_intelligence_index.docintel_enrichment"
)

SUPPORTED_FILE_ENRICHMENT_SUFFIXES = frozenset({
    ".pdf",
    ".docx",
    ".txt",
    ".csv",
    ".xlsx",
    ".xls",
})

MAX_SHORT_SUMMARY_CHARS = 320
MAX_DETAILED_SUMMARY_CHARS = 1800
MAX_SEARCH_TEXT_CHARS = 24000
MAX_REPRESENTATIVE_LINES = 10
MAX_KEYWORDS = 44
MAX_STRUCTURED_FACTS = 80

_EVIDENCE_KEYWORD_RE = re.compile(
    r"\b("
    r"agreement|amount|addenda|alternate|allowance|approval|attachment|"
    r"bid|budget|change|clarification|condition|contract|cost|date|deadline|"
    r"deliverable|drawing|exclusion|fee|file|form|instruction|invoice|"
    r"letter|mobilization|notice|payment|permit|price|pricing|proposal|"
    r"requirement|review|schedule|scope|section|specification|submittal|"
    r"summary|total|work"
    r")\b",
    re.IGNORECASE,
)
_VALUE_TOKEN_RE = re.compile(
    r"(\$[\s\u00a0]*[\d,]+(?:\.\d{2})?|\b\d+(?:\.\d+)?\s?%)",
    re.IGNORECASE,
)
_WORD_TOKEN_RE = re.compile(r"\b[a-z][a-z0-9]{2,}\b", re.IGNORECASE)


def utc_now() -> datetime:
    """Return a database-safe UTC timestamp."""

    return datetime.now(timezone.utc).replace(tzinfo=None)


def clean_search_token(value) -> str:
    """Return a compact search-safe token."""

    return " ".join(
        str(value or "")
        .replace("\x00", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    ).strip()


def clean_multiline_text(value: Any) -> str:
    """Return normalized multiline text while preserving readable breaks."""

    text = str(value or "").replace("\x00", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def truncate_text(value: Any, max_chars: int) -> str:
    """Return text capped at a readable boundary."""

    clean_value = clean_search_token(value)

    if max_chars <= 0 or len(clean_value) <= max_chars:
        return clean_value

    clipped = clean_value[: max_chars + 1].rsplit(" ", 1)[0].strip()

    return clipped or clean_value[:max_chars].strip()


def stable_hash(value: Any) -> str:
    """Return a stable SHA-256 hash for text-like values."""

    clean_value = str(value or "").encode(
        "utf-8",
        errors="ignore",
    )

    return hashlib.sha256(clean_value).hexdigest()


def build_reader_url(file_handle: str) -> str:
    """Build the canonical first-party Reader URL for a file handle."""

    safe_handle = quote(
        str(file_handle or "").strip(),
        safe="",
    )

    return (
        f"/workspace/file/"
        f"{safe_handle}/reader"
    )


def safe_metadata_payload(value) -> dict:
    """Return a metadata payload dictionary."""

    if isinstance(value, dict):
        return dict(value)

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}

        if isinstance(parsed, dict):
            return dict(parsed)

    return {}


def merge_search_texts(*values: Any) -> str:
    """Merge search text blocks without repeating identical compact lines."""

    output_lines = []
    seen = set()

    for value in values:
        text = clean_multiline_text(value)

        if not text:
            continue

        for raw_line in text.splitlines():
            clean_line = clean_search_token(raw_line)
            clean_key = clean_line.casefold()

            if not clean_line or clean_key in seen:
                continue

            output_lines.append(clean_line)
            seen.add(clean_key)

            if sum(len(line) for line in output_lines) >= MAX_SEARCH_TEXT_CHARS:
                break

        if sum(len(line) for line in output_lines) >= MAX_SEARCH_TEXT_CHARS:
            break

    return "\n".join(output_lines)[:MAX_SEARCH_TEXT_CHARS].strip()


def build_file_intelligence_search_text(
    *,
    record: FileRegistry,
    metadata: dict,
    existing_text: str | None = None,
    enriched_text: str | None = None,
) -> str:
    """Build searchable text for a registered file."""

    search_tokens = [
        record.original_name,
        record.random_name,
        record.extension,
        record.checksum,
        metadata.get("document_status"),
        metadata.get("workflow_status"),
        metadata.get("analysis_status"),
        metadata.get("storage_contract"),
        metadata.get("workspace_intelligence_status"),
    ]

    baseline_tokens = []

    for token in search_tokens:
        clean_token = clean_search_token(token)

        if clean_token and clean_token not in baseline_tokens:
            baseline_tokens.append(clean_token)

    return merge_search_texts(
        "\n".join(baseline_tokens),
        existing_text,
        enriched_text,
    )


def build_file_intelligence_subtitle(
    record: FileRegistry,
) -> str:
    """Return a compact file type label."""

    extension = clean_search_token(record.extension)

    if not extension:
        return "File"

    if extension.startswith("."):
        return f"{extension[1:].upper()} file"

    return f"{extension.upper()} file"


def reset_stale_file_intelligence_children(
    db_session,
    intelligence_object: WorkspaceIntelligenceObject,
) -> None:
    """Delete stale chunk and fact rows when a file's source changes."""

    if not intelligence_object or not intelligence_object.id:
        return

    db_session.query(
        WorkspaceIntelligenceChunk
    ).filter(
        WorkspaceIntelligenceChunk.intelligence_object_id
        == intelligence_object.id
    ).delete(
        synchronize_session=False
    )

    db_session.query(
        WorkspaceIntelligenceFact
    ).filter(
        WorkspaceIntelligenceFact.intelligence_object_id
        == intelligence_object.id
    ).delete(
        synchronize_session=False
    )


def reset_stale_file_intelligence_object(
    *,
    db_session,
    intelligence_object: WorkspaceIntelligenceObject,
) -> None:
    """Reset stale file-level intelligence fields after source change."""

    reset_stale_file_intelligence_children(
        db_session,
        intelligence_object,
    )

    intelligence_object.short_summary = None
    intelligence_object.detailed_summary = None
    intelligence_object.search_text = None
    intelligence_object.keywords_json = None
    intelligence_object.structured_facts_json = None

    intelligence_object.extracted_text_hash = None
    intelligence_object.summary_hash = None
    intelligence_object.facts_hash = None

    intelligence_object.embedding_ref = None
    intelligence_object.embedding_vector = None
    intelligence_object.embedding_dimension = None
    intelligence_object.embedding_checksum = None

    intelligence_object.indexed_at = None
    intelligence_object.extracted_at = None
    intelligence_object.summarized_at = None
    intelligence_object.facts_extracted_at = None
    intelligence_object.embedded_at = None

    intelligence_object.extraction_status = (
        WORKSPACE_INTELLIGENCE_INITIAL_STATUS
    )
    intelligence_object.summary_status = (
        WORKSPACE_INTELLIGENCE_INITIAL_STATUS
    )
    intelligence_object.facts_status = (
        WORKSPACE_INTELLIGENCE_INITIAL_STATUS
    )
    intelligence_object.embedding_status = (
        WORKSPACE_INTELLIGENCE_INITIAL_STATUS
    )
    intelligence_object.index_status = (
        WORKSPACE_INTELLIGENCE_INITIAL_STATUS
    )
    intelligence_object.stale_reason = (
        WORKSPACE_INTELLIGENCE_SOURCE_CHANGED_REASON
    )
    intelligence_object.error_message = None


def find_file_intelligence_object(
    *,
    db_session,
    file_registry_id: int,
):
    """Return the file intelligence object for a FileRegistry id."""

    return (
        db_session.query(
            WorkspaceIntelligenceObject
        )
        .filter(
            WorkspaceIntelligenceObject.object_type
            == WORKSPACE_INTELLIGENCE_FILE_OBJECT_TYPE,
            WorkspaceIntelligenceObject.file_registry_id
            == file_registry_id,
        )
        .first()
    )


def create_file_intelligence_object(
    *,
    db_session,
    record: FileRegistry,
) -> WorkspaceIntelligenceObject:
    """Create the searchable intelligence shell for a FileRegistry row."""

    intelligence_object = WorkspaceIntelligenceObject(
        object_type=WORKSPACE_INTELLIGENCE_FILE_OBJECT_TYPE,
        user_id=record.uploader_id,
        file_registry_id=record.id,
        title=(
            clean_search_token(record.original_name)
            or clean_search_token(record.random_name)
            or "Uploaded file"
        ),
        canonical_url=build_reader_url(record.random_name),
        icon_key=WORKSPACE_INTELLIGENCE_FILE_ICON,
        status="active",
        visibility_scope=WORKSPACE_INTELLIGENCE_FILE_VISIBILITY_SCOPE,
        is_discoverable=True,
        allow_ai_query=True,
        extraction_status=WORKSPACE_INTELLIGENCE_INITIAL_STATUS,
        summary_status=WORKSPACE_INTELLIGENCE_INITIAL_STATUS,
        facts_status=WORKSPACE_INTELLIGENCE_INITIAL_STATUS,
        embedding_status=WORKSPACE_INTELLIGENCE_INITIAL_STATUS,
        index_status=WORKSPACE_INTELLIGENCE_INITIAL_STATUS,
    )

    db_session.add(intelligence_object)

    return intelligence_object


def update_file_intelligence_object_fields(
    *,
    intelligence_object: WorkspaceIntelligenceObject,
    record: FileRegistry,
    metadata: dict,
) -> WorkspaceIntelligenceObject:
    """Refresh stable file intelligence fields from FileRegistry."""

    source_hash = clean_search_token(record.checksum)
    existing_search_text = intelligence_object.search_text

    intelligence_object.object_type = WORKSPACE_INTELLIGENCE_FILE_OBJECT_TYPE
    intelligence_object.user_id = record.uploader_id
    intelligence_object.file_registry_id = record.id
    intelligence_object.title = (
        clean_search_token(record.original_name)
        or clean_search_token(record.random_name)
        or "Uploaded file"
    )
    intelligence_object.subtitle = build_file_intelligence_subtitle(record)
    intelligence_object.canonical_url = build_reader_url(record.random_name)
    intelligence_object.icon_key = WORKSPACE_INTELLIGENCE_FILE_ICON
    intelligence_object.status = "active"
    intelligence_object.visibility_scope = (
        WORKSPACE_INTELLIGENCE_FILE_VISIBILITY_SCOPE
    )
    intelligence_object.is_discoverable = True
    intelligence_object.allow_ai_query = True
    intelligence_object.search_text = build_file_intelligence_search_text(
        record=record,
        metadata=metadata,
        existing_text=existing_search_text,
    )
    intelligence_object.source_hash = source_hash or None
    intelligence_object.source_locator_json = {
        "file_registry_id": record.id,
        "random_name": record.random_name,
        "path": record.path,
        "reader_url": build_reader_url(record.random_name),
    }

    previous_metadata = safe_metadata_payload(
        intelligence_object.metadata_json
    )
    intelligence_object.metadata_json = {
        **previous_metadata,
        "index_source": WORKSPACE_INTELLIGENCE_FILE_REGISTRATION_SOURCE,
        "file_registry_id": record.id,
        "random_name": record.random_name,
        "original_name": record.original_name,
        "extension": record.extension,
        "size_bytes": record.size_bytes,
        "checksum": record.checksum,
        "storage_contract": metadata.get("storage_contract"),
        "document_status": metadata.get("document_status"),
        "workflow_status": metadata.get("workflow_status"),
        "analysis_status": metadata.get("analysis_status"),
    }
    intelligence_object.error_message = None

    if not intelligence_object.extraction_status:
        intelligence_object.extraction_status = (
            WORKSPACE_INTELLIGENCE_INITIAL_STATUS
        )

    if not intelligence_object.summary_status:
        intelligence_object.summary_status = (
            WORKSPACE_INTELLIGENCE_INITIAL_STATUS
        )

    if not intelligence_object.facts_status:
        intelligence_object.facts_status = (
            WORKSPACE_INTELLIGENCE_INITIAL_STATUS
        )

    if not intelligence_object.embedding_status:
        intelligence_object.embedding_status = (
            WORKSPACE_INTELLIGENCE_INITIAL_STATUS
        )

    if not intelligence_object.index_status:
        intelligence_object.index_status = (
            WORKSPACE_INTELLIGENCE_INITIAL_STATUS
        )

    return intelligence_object


def upsert_file_intelligence_object(
    *,
    db_session,
    record: FileRegistry,
    metadata: dict | None = None,
):
    """Create or refresh the workspace intelligence shell for a file."""

    if not record or not record.id or not record.uploader_id:
        return None

    metadata_payload = safe_metadata_payload(metadata)

    if not metadata_payload:
        metadata_payload = safe_metadata_payload(record.meta)

    intelligence_object = find_file_intelligence_object(
        db_session=db_session,
        file_registry_id=record.id,
    )

    source_hash = clean_search_token(record.checksum)
    source_changed = bool(
        intelligence_object
        and source_hash
        and intelligence_object.source_hash
        and str(intelligence_object.source_hash).strip() != source_hash
    )

    if not intelligence_object:
        intelligence_object = create_file_intelligence_object(
            db_session=db_session,
            record=record,
        )

    if source_changed:
        reset_stale_file_intelligence_object(
            db_session=db_session,
            intelligence_object=intelligence_object,
        )

    return update_file_intelligence_object_fields(
        intelligence_object=intelligence_object,
        record=record,
        metadata=metadata_payload,
    )


def record_supports_text_enrichment(
    record: FileRegistry,
) -> bool:
    """Return whether the registered file type can be text-enriched."""

    path_suffix = Path(
        str(record.path or "")
    ).suffix.lower()
    original_suffix = Path(
        str(record.original_name or "")
    ).suffix.lower()
    extension = clean_search_token(
        record.extension
    ).lower()

    suffix = path_suffix or original_suffix or extension

    return suffix in SUPPORTED_FILE_ENRICHMENT_SUFFIXES


def resolve_record_path(record: FileRegistry) -> Path | None:
    """Return a safe existing path for a FileRegistry row."""

    clean_path = str(record.path or "").strip()

    if not clean_path:
        return None

    path = Path(clean_path)

    if not path.is_file():
        return None

    return path


def select_docintel_document(docintel_packet: dict) -> dict:
    """Return the first extracted document from a DocIntel packet."""

    inputs = (
        docintel_packet.get("inputs")
        if isinstance(docintel_packet, dict)
        else {}
    )
    documents = (
        inputs.get("documents")
        if isinstance(inputs, dict)
        else []
    )

    if not isinstance(documents, list):
        return {}

    for document in documents:
        if not isinstance(document, dict):
            continue

        if clean_multiline_text(document.get("text")):
            return document

    return {}


def select_docintel_signals(docintel_packet: dict) -> dict:
    """Return the DocIntel signal payload."""

    inputs = (
        docintel_packet.get("inputs")
        if isinstance(docintel_packet, dict)
        else {}
    )
    signals = (
        inputs.get("signals")
        if isinstance(inputs, dict)
        else {}
    )

    return signals if isinstance(signals, dict) else {}


def line_score(line: str) -> int:
    """Return a deterministic usefulness score for one extracted line."""

    clean_line = clean_search_token(line)
    lower_line = clean_line.casefold()

    if len(clean_line) < 28:
        return 0

    score = min(len(clean_line), 220) // 18
    score += len(_EVIDENCE_KEYWORD_RE.findall(clean_line)) * 6
    score += len(_VALUE_TOKEN_RE.findall(clean_line)) * 8

    if lower_line.endswith(":"):
        score += 3

    if len(clean_line) > 360:
        score -= 6

    return score


def representative_document_lines(
    document_text: str,
    *,
    limit: int = MAX_REPRESENTATIVE_LINES,
) -> list[str]:
    """Return representative source lines without inventing content."""

    clean_text = clean_multiline_text(document_text)

    if not clean_text:
        return []

    candidates = []
    seen = set()

    for index, raw_line in enumerate(clean_text.splitlines()):
        clean_line = truncate_text(raw_line, 360)
        clean_key = clean_line.casefold()

        if not clean_line or clean_key in seen:
            continue

        seen.add(clean_key)

        score = line_score(clean_line)
        if score <= 0:
            continue

        candidates.append({
            "index": index,
            "line": clean_line,
            "score": score,
        })

    if not candidates:
        for raw_line in clean_text.splitlines():
            clean_line = truncate_text(raw_line, 260)
            clean_key = clean_line.casefold()

            if (
                len(clean_line) >= 28
                and clean_key not in seen
            ):
                candidates.append({
                    "index": len(candidates),
                    "line": clean_line,
                    "score": 1,
                })
                seen.add(clean_key)

            if len(candidates) >= limit:
                break

    selected = sorted(
        candidates,
        key=lambda item: (
            -item["score"],
            item["index"],
        ),
    )[:limit]

    selected.sort(key=lambda item: item["index"])

    return [
        item["line"]
        for item in selected
        if item.get("line")
    ]


def build_file_short_summary(
    *,
    record: FileRegistry,
    document_text: str,
) -> str:
    """Build a compact deterministic summary for search cards."""

    representative_lines = representative_document_lines(
        document_text,
        limit=3,
    )

    if representative_lines:
        return truncate_text(
            f"Contains: {representative_lines[0]}",
            MAX_SHORT_SUMMARY_CHARS,
        )

    title = (
        clean_search_token(record.original_name)
        or clean_search_token(record.random_name)
        or "Uploaded file"
    )

    return truncate_text(
        f"{title} is indexed for workspace search.",
        MAX_SHORT_SUMMARY_CHARS,
    )


def build_file_detailed_summary(
    *,
    record: FileRegistry,
    document_text: str,
    signals: dict,
) -> str:
    """Build a deterministic evidence-backed file summary."""

    title = (
        clean_search_token(record.original_name)
        or clean_search_token(record.random_name)
        or "Uploaded file"
    )
    subtitle = build_file_intelligence_subtitle(record)
    clean_text = clean_multiline_text(document_text)
    representative_lines = representative_document_lines(clean_text)

    signal_counts = {
        key: len(value)
        for key, value in signals.items()
        if isinstance(value, list)
    }

    sections = [
        f"Document: {title}",
        f"Type: {subtitle}",
        f"Extracted text: {len(clean_text)} characters",
    ]

    if signal_counts:
        signal_text = ", ".join(
            f"{key}: {count}"
            for key, count in sorted(signal_counts.items())
            if count
        )

        if signal_text:
            sections.append(f"Detected signals: {signal_text}")

    if representative_lines:
        sections.append("Representative extracted lines:")
        sections.extend(
            f"- {line}"
            for line in representative_lines
        )

    return truncate_text(
        "\n".join(sections),
        MAX_DETAILED_SUMMARY_CHARS,
    )


def build_keyword_payload(
    *,
    record: FileRegistry,
    metadata: dict,
    document_text: str,
    signals: dict,
) -> dict:
    """Build deterministic keywords from metadata and extracted text."""

    keywords = []
    seen = set()

    def add_keyword(value: Any) -> None:
        clean_value = clean_search_token(value).casefold()

        if (
            not clean_value
            or clean_value in seen
            or len(clean_value) < 2
        ):
            return

        keywords.append(clean_value)
        seen.add(clean_value)

    for value in (
        record.original_name,
        record.random_name,
        record.extension,
        metadata.get("document_status"),
        metadata.get("workflow_status"),
        metadata.get("analysis_status"),
    ):
        for token in re.split(r"[^A-Za-z0-9_.-]+", str(value or "")):
            add_keyword(token)

    for match in _EVIDENCE_KEYWORD_RE.finditer(document_text or ""):
        add_keyword(match.group(0))

    for value in signals.values():
        if not isinstance(value, list):
            continue

        for item in value[:12]:
            if not isinstance(item, dict):
                continue

            add_keyword(
                item.get("signal_type")
                or item.get("type")
                or item.get("label")
                or item.get("section")
            )

    return {
        "keywords": keywords[:MAX_KEYWORDS],
        "source": WORKSPACE_INTELLIGENCE_FILE_ENRICHMENT_SOURCE,
    }


def compact_signal_fact(
    *,
    group_name: str,
    item: dict,
) -> dict:
    """Return one compact structured fact from a DocIntel signal."""

    if not isinstance(item, dict):
        return {}

    fact = {
        "group": clean_search_token(group_name),
    }

    for source_key, target_key in (
        ("signal_type", "signal_type"),
        ("type", "type"),
        ("label", "label"),
        ("section", "section"),
        ("value", "value"),
        ("text", "text"),
        ("snippet", "snippet"),
        ("evidence", "evidence"),
        ("document_id", "document_id"),
    ):
        clean_value = clean_search_token(item.get(source_key))

        if clean_value:
            fact[target_key] = truncate_text(clean_value, 500)

    return fact


def build_structured_facts_payload(
    *,
    record: FileRegistry,
    document_text: str,
    signals: dict,
) -> dict:
    """Build compact structured facts for search and future RAG indexing."""

    facts = []
    signal_counts = {}

    for group_name, group_items in signals.items():
        if not isinstance(group_items, list):
            continue

        signal_counts[group_name] = len(group_items)

        for item in group_items:
            fact = compact_signal_fact(
                group_name=group_name,
                item=item,
            )

            if fact:
                facts.append(fact)

            if len(facts) >= MAX_STRUCTURED_FACTS:
                break

        if len(facts) >= MAX_STRUCTURED_FACTS:
            break

    return {
        "contract": "workspace_file_intelligence_v1",
        "source": WORKSPACE_INTELLIGENCE_FILE_ENRICHMENT_SOURCE,
        "document": {
            "file_registry_id": record.id,
            "random_name": record.random_name,
            "original_name": record.original_name,
            "extension": record.extension,
            "text_chars": len(clean_multiline_text(document_text)),
        },
        "signal_counts": signal_counts,
        "facts": facts,
    }


def build_enriched_search_text(
    *,
    record: FileRegistry,
    metadata: dict,
    document_text: str,
    short_summary: str,
    detailed_summary: str,
    signals: dict,
) -> str:
    """Build enriched full-text search content from extracted evidence."""

    representative_lines = "\n".join(
        representative_document_lines(
            document_text,
            limit=MAX_REPRESENTATIVE_LINES,
        )
    )
    value_tokens = "\n".join(
        sorted(set(_VALUE_TOKEN_RE.findall(document_text or "")))[:80]
    )
    signal_terms = []

    for group_name, group_items in signals.items():
        if not isinstance(group_items, list):
            continue

        signal_terms.append(group_name)

        for item in group_items[:20]:
            if not isinstance(item, dict):
                continue

            for key in (
                "signal_type",
                "type",
                "label",
                "section",
                "value",
            ):
                token = clean_search_token(item.get(key))

                if token:
                    signal_terms.append(token)

    enriched_text = merge_search_texts(
        short_summary,
        detailed_summary,
        representative_lines,
        value_tokens,
        "\n".join(signal_terms),
        document_text[:MAX_SEARCH_TEXT_CHARS],
    )

    return build_file_intelligence_search_text(
        record=record,
        metadata=metadata,
        enriched_text=enriched_text,
    )


def mark_file_intelligence_enrichment_failed(
    *,
    intelligence_object: WorkspaceIntelligenceObject,
    reason: str,
) -> WorkspaceIntelligenceObject:
    """Mark an intelligence object as failed without hiding metadata search."""

    now = utc_now()

    intelligence_object.extraction_status = WORKSPACE_INTELLIGENCE_FAILED_STATUS
    intelligence_object.summary_status = WORKSPACE_INTELLIGENCE_FAILED_STATUS
    intelligence_object.facts_status = WORKSPACE_INTELLIGENCE_FAILED_STATUS
    intelligence_object.index_status = WORKSPACE_INTELLIGENCE_FAILED_STATUS
    intelligence_object.indexed_at = now
    intelligence_object.error_message = truncate_text(reason, 900)

    return intelligence_object


def mark_file_intelligence_enrichment_skipped(
    *,
    intelligence_object: WorkspaceIntelligenceObject,
    reason: str,
) -> WorkspaceIntelligenceObject:
    """Mark unsupported files as metadata-indexed but text-skipped."""

    now = utc_now()

    intelligence_object.extraction_status = WORKSPACE_INTELLIGENCE_SKIPPED_STATUS
    intelligence_object.summary_status = WORKSPACE_INTELLIGENCE_SKIPPED_STATUS
    intelligence_object.facts_status = WORKSPACE_INTELLIGENCE_SKIPPED_STATUS
    intelligence_object.index_status = WORKSPACE_INTELLIGENCE_READY_STATUS
    intelligence_object.indexed_at = now
    intelligence_object.error_message = truncate_text(reason, 900)

    metadata = safe_metadata_payload(intelligence_object.metadata_json)
    intelligence_object.metadata_json = {
        **metadata,
        "enrichment_source": WORKSPACE_INTELLIGENCE_FILE_ENRICHMENT_SOURCE,
        "enrichment_status": WORKSPACE_INTELLIGENCE_SKIPPED_STATUS,
        "enrichment_reason": reason,
    }

    return intelligence_object


def enrich_file_intelligence_object(
    *,
    db_session,
    record: FileRegistry,
    metadata: dict | None = None,
):
    """
    Enrich a registered file intelligence object from authorized extracted text.

    This function is intentionally explicit. Upload registration can create the
    searchable shell without forcing document analysis as a side effect.
    """

    intelligence_object = upsert_file_intelligence_object(
        db_session=db_session,
        record=record,
        metadata=metadata,
    )

    if not intelligence_object:
        return None

    db_session.flush()

    metadata_payload = safe_metadata_payload(metadata)

    if not metadata_payload:
        metadata_payload = safe_metadata_payload(record.meta)

    if not record_supports_text_enrichment(record):
        return mark_file_intelligence_enrichment_skipped(
            intelligence_object=intelligence_object,
            reason=(
                "File type is not supported for deterministic text "
                "enrichment."
            ),
        )

    resolved_path = resolve_record_path(record)

    if not resolved_path:
        return mark_file_intelligence_enrichment_failed(
            intelligence_object=intelligence_object,
            reason="Registered file path is missing or unreadable.",
        )

    try:
        docintel_packet = ingest_documents_for_intent(
            intent=None,
            resolved_paths=[str(resolved_path)],
        )
    except DocIntelIngestError as exc:
        logger.warning(
            "[workspace_intelligence.enrichment_docintel_failed]",
            extra={
                "file_registry_id": record.id,
                "random_name": record.random_name,
                "error": str(exc),
            },
        )

        return mark_file_intelligence_enrichment_failed(
            intelligence_object=intelligence_object,
            reason=f"DocIntel extraction failed: {exc}",
        )
    except Exception as exc:
        logger.exception(
            "[workspace_intelligence.enrichment_unhandled_failure]",
            extra={
                "file_registry_id": record.id,
                "random_name": record.random_name,
            },
        )

        return mark_file_intelligence_enrichment_failed(
            intelligence_object=intelligence_object,
            reason=f"Unexpected enrichment failure: {type(exc).__name__}",
        )

    document = select_docintel_document(docintel_packet)
    document_text = clean_multiline_text(document.get("text"))
    signals = select_docintel_signals(docintel_packet)

    if not document_text:
        return mark_file_intelligence_enrichment_failed(
            intelligence_object=intelligence_object,
            reason="DocIntel returned no extracted text.",
        )

    now = utc_now()
    short_summary = build_file_short_summary(
        record=record,
        document_text=document_text,
    )
    detailed_summary = build_file_detailed_summary(
        record=record,
        document_text=document_text,
        signals=signals,
    )
    structured_facts = build_structured_facts_payload(
        record=record,
        document_text=document_text,
        signals=signals,
    )
    keywords = build_keyword_payload(
        record=record,
        metadata=metadata_payload,
        document_text=document_text,
        signals=signals,
    )
    search_text = build_enriched_search_text(
        record=record,
        metadata=metadata_payload,
        document_text=document_text,
        short_summary=short_summary,
        detailed_summary=detailed_summary,
        signals=signals,
    )

    intelligence_object.short_summary = short_summary
    intelligence_object.detailed_summary = detailed_summary
    intelligence_object.search_text = search_text
    intelligence_object.keywords_json = keywords
    intelligence_object.structured_facts_json = structured_facts

    intelligence_object.extracted_text_hash = stable_hash(document_text)
    intelligence_object.summary_hash = stable_hash(
        f"{short_summary}\n\n{detailed_summary}"
    )
    intelligence_object.facts_hash = stable_hash(
        json.dumps(
            structured_facts,
            sort_keys=True,
            default=str,
        )
    )

    intelligence_object.extracted_at = now
    intelligence_object.summarized_at = now
    intelligence_object.facts_extracted_at = now
    intelligence_object.indexed_at = now

    intelligence_object.extraction_status = WORKSPACE_INTELLIGENCE_READY_STATUS
    intelligence_object.summary_status = WORKSPACE_INTELLIGENCE_READY_STATUS
    intelligence_object.facts_status = WORKSPACE_INTELLIGENCE_READY_STATUS
    intelligence_object.index_status = WORKSPACE_INTELLIGENCE_READY_STATUS

    if not intelligence_object.embedding_status:
        intelligence_object.embedding_status = (
            WORKSPACE_INTELLIGENCE_INITIAL_STATUS
        )

    intelligence_object.stale_reason = None
    intelligence_object.error_message = None

    previous_metadata = safe_metadata_payload(
        intelligence_object.metadata_json
    )
    intelligence_object.metadata_json = {
        **previous_metadata,
        "enrichment_source": WORKSPACE_INTELLIGENCE_FILE_ENRICHMENT_SOURCE,
        "enrichment_status": WORKSPACE_INTELLIGENCE_READY_STATUS,
        "enriched_at": now.isoformat(),
        "extracted_text_chars": len(document_text),
        "representative_line_count": len(
            representative_document_lines(document_text)
        ),
        "signal_counts": structured_facts.get("signal_counts", {}),
    }

    logger.info(
        "[workspace_intelligence.enrichment_complete]",
        extra={
            "file_registry_id": record.id,
            "random_name": record.random_name,
            "text_chars": len(document_text),
            "search_text_chars": len(search_text),
            "facts": len(structured_facts.get("facts", [])),
        },
    )

    return intelligence_object


__all__ = [
    "WORKSPACE_INTELLIGENCE_FILE_OBJECT_TYPE",
    "WORKSPACE_INTELLIGENCE_INITIAL_STATUS",
    "WORKSPACE_INTELLIGENCE_READY_STATUS",
    "enrich_file_intelligence_object",
    "upsert_file_intelligence_object",
]
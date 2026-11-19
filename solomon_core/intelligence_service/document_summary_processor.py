# -------------------------------------------------------------------
# FILE: document_summary_processor.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Durable Auto Summary processor for the Solomon Intelligence Service.
#
# The processor consumes a content/version-bound Intelligence Job, extracts
# normalized source text through the canonical DocIntel ingestor, enters the
# V3 Investigator/CaseFile/Orchestrator drivetrain for background model work,
# and persists the summary
# into the current WorkspaceIntelligenceObject. It owns no user permissions and
# never grants source authority.
# -------------------------------------------------------------------

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from config import settings
from solomon_core.db import SessionLocal
from solomon_core.docintel.ingestion.docintel_ingestor import (
    DocIntelExtractionPolicy,
    DocIntelIngestError,
    ingest_documents_for_intent,
)
from solomon_core.logger import get_logger
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
    LLMFailureReason,
    LLMResponseFormat,
    LLMRuntimeProfile,
)
from solomon_core.llm.llm_prompting import MAX_LLM_INPUT_CHARS
from solomon_core.models import FileRegistry, WorkspaceIntelligenceObject
from solomon_core.actions.solomon_file_actions import (
    get_solomon_file_action_definition,
)
from solomon_core.actions.solomon_file_action_results import (
    link_ready_solomon_file_action_result,
    persist_ready_solomon_file_action_result,
    resolve_ready_solomon_file_action_result,
)
from .document_summary_contract import (
    AUTO_SUMMARY_ARTIFACT_TYPE,
    AUTO_SUMMARY_CALL_SITE,
    AUTO_SUMMARY_CONTEXT_CONTRACT,
    AUTO_SUMMARY_JOB_TYPE,
    AUTO_SUMMARY_PROCESSOR_KEY,
    AUTO_SUMMARY_PROCESSOR_VERSION,
    AUTO_SUMMARY_PROGRESS_ARTIFACT_READY,
    AUTO_SUMMARY_PROGRESS_EXTRACTION_COMPLETE,
    AUTO_SUMMARY_PROGRESS_EXTRACTION_STARTED,
    AUTO_SUMMARY_PROGRESS_GENERATION_COMPLETE,
    AUTO_SUMMARY_PROGRESS_GENERATION_STARTED,
    AUTO_SUMMARY_PROGRESS_PERSISTENCE_STARTED,
    AUTO_SUMMARY_PROGRESS_SOURCE_VALIDATED,
    AUTO_SUMMARY_SOURCE,
)

from solomon_core.workspace_intelligence.workspace_intelligence_index import (
    MAX_DETAILED_SUMMARY_CHARS,
    MAX_SHORT_SUMMARY_CHARS,
    WORKSPACE_INTELLIGENCE_READY_STATUS,
    clean_multiline_text,
    merge_search_texts,
    record_supports_text_enrichment,
    representative_document_lines,
    safe_metadata_payload,
    select_docintel_document,
    stable_hash,
    truncate_text,
    utc_now,
)

from solomon_core.orchestrator_runtime import (
    execute_governed_llm_operation,
)
from .intelligence_spool_worker import (
    IntelligenceJobExecutionContext,
    IntelligenceJobProcessorResult,
    IntelligenceJobRetryableError,
    IntelligenceJobTerminalError,
)


logger = get_logger("intelligence_service.document_summary")

# inject_document_grounding reserves 60% of MAX_LLM_INPUT_CHARS for source
# material. Stay slightly below that boundary so our own section labels cannot
# cause the grounding helper to clip the constructed representative context.
AUTO_SUMMARY_SOURCE_CHAR_BUDGET = max(
    1200,
    int(MAX_LLM_INPUT_CHARS * 0.55),
)

_AUTO_SUMMARY_INSTRUCTION = (
    "Create a factual, source-grounded summary of the provided document material. "
    "Return plain text only. Prioritize the document's purpose or subject first, "
    "then its major structure, sections, themes, and the key content that is "
    "material to that purpose. Mention dates, amounts, publisher details, or other "
    "incidental metadata only when they are materially important to what the "
    "document is for. Do not invent facts, infer availability or intent, or create "
    "relationships between separate facts unless the source explicitly supports "
    "that relationship. Use concise paragraphs. If the supplied evidence is "
    "representative rather than exhaustive, summarize only what the evidence "
    "supports and do not imply that every page was reviewed."
)

_TABULAR_AUTO_SUMMARY_INSTRUCTION = (
    " The supplied evidence is tabular. Preserve source-row boundaries and the "
    "relationship between each cell and its column. Source row numbers are position "
    "metadata only; they are never counts. Do not calculate or state an exact number "
    "of rows, records, items, entries, categories, or sheets from source-row positions "
    "or from the number of rendered evidence lines. State an exact count only when a "
    "source cell explicitly provides that count; otherwise omit the count entirely. "
    "Do not treat a header row as a data record, and do not count blank rendered grid "
    "rows. Status fields such as Included, Excluded, No, Yes, or Partial govern scope "
    "meaning and must not be collapsed into a generic statement that an item is "
    "included. A Partial value remains partial. Amounts or impacts attached to an "
    "excluded or No row are associated with that row and must not be described as "
    "included proposal cost unless the source explicitly says so. Preserve row-level "
    "qualifiers and responsibility notes. Do not invent category counts, totals, or "
    "relationships that are not directly supported by source-cell values."
)


def _auto_summary_instruction(evidence_metadata: dict) -> str:
    """Return the source-grounded summary instruction for this evidence shape."""

    instruction = _AUTO_SUMMARY_INSTRUCTION
    spreadsheet_format = str(
        evidence_metadata.get("spreadsheet_format") or ""
    ).strip().lower()

    if spreadsheet_format in {"csv", "xls", "xlsx"}:
        instruction += _TABULAR_AUTO_SUMMARY_INSTRUCTION

    return instruction


_TABULAR_STRUCTURAL_COUNT_RE = re.compile(
    r"\b(?:"
    r"\d[\d,]*|zero|one|two|three|four|five|six|seven|eight|nine|ten|"
    r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|"
    r"nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety"
    r")\s+(?P<label>(?:(?:data\s+)?(?:rows?|records?|items?|entries?|categories|sheets?)|data\s+points?))\b",
    re.IGNORECASE,
)


def _sanitize_unsupported_tabular_structural_counts(
    generated_text: str,
    *,
    source_context: str,
    evidence_metadata: dict,
) -> tuple[str, int]:
    """Remove unsupported exact structural counts from tabular narration.

    Row positions and rendered evidence-line counts are presentation metadata, not
    business facts. Exact structural counts survive only when the same count phrase
    is explicitly present in source evidence. This deterministic guard complements
    the LLM instruction so a model cannot turn row labels such as ``Source row 7``
    into an unsupported claim such as ``seven data rows``.
    """

    spreadsheet_format = str(
        evidence_metadata.get("spreadsheet_format") or ""
    ).strip().lower()
    if spreadsheet_format not in {"csv", "xls", "xlsx"}:
        return generated_text, 0

    normalized_source = " ".join(str(source_context or "").lower().split())

    def _replace(match: re.Match) -> str:
        exact_phrase = " ".join(match.group(0).lower().split())
        if exact_phrase and exact_phrase in normalized_source:
            return match.group(0)
        return str(match.group("label") or "").strip()

    return _TABULAR_STRUCTURAL_COUNT_RE.subn(_replace, generated_text)

_AUTO_SUMMARY_EVIDENCE_CACHE_CONTRACT = "auto_summary_evidence_cache_v2"

_SUMMARY_STRUCTURE_RE = re.compile(
    r"\b("
    r"contents?|introduction|overview|purpose|chapter|part|section|sections|"
    r"category|categories|divided|structure|structured|theme|themes|focus|designed|"
    r"teaches|skills?|ability|summary|conclusion|recommendation|covers?|"
    r"includes?"
    r")\b",
    re.IGNORECASE,
)
_SUMMARY_MATERIAL_RE = re.compile(
    r"\b("
    r"amount|budget|cost|date|deadline|decision|obligation|payment|price|"
    r"requirement|risk|schedule|scope|term|total|work"
    r")\b",
    re.IGNORECASE,
)
_SUMMARY_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]{2,}\b")


def _auto_summary_extraction_policy() -> DocIntelExtractionPolicy:
    return DocIntelExtractionPolicy(
        name="auto_summary_representative_v1",
        max_pdf_pages=int(settings.SIS_AUTO_SUMMARY_EVIDENCE_MAX_PDF_PAGES),
        leading_pdf_pages=int(
            settings.SIS_AUTO_SUMMARY_EVIDENCE_LEADING_PDF_PAGES
        ),
        trailing_pdf_pages=int(
            settings.SIS_AUTO_SUMMARY_EVIDENCE_TRAILING_PDF_PAGES
        ),
        min_pdf_pages=int(settings.SIS_AUTO_SUMMARY_EVIDENCE_MIN_PDF_PAGES),
        target_extracted_chars=int(
            settings.SIS_AUTO_SUMMARY_EVIDENCE_TARGET_CHARS
        ),
        max_pdf_seconds=float(
            settings.SIS_AUTO_SUMMARY_EVIDENCE_MAX_PDF_SECONDS
        ),
        ocr_dpi=int(settings.SIS_AUTO_SUMMARY_EVIDENCE_OCR_DPI),
    )


def _clean_evidence_metadata(value) -> dict:
    if not isinstance(value, dict):
        return {
            "coverage_mode": "complete",
            "complete_source_coverage": True,
        }

    return dict(value)


def _auto_summary_policy_fingerprint(
    policy: DocIntelExtractionPolicy,
) -> str:
    return stable_hash(
        "|".join([
            str(policy.name),
            str(int(policy.max_pdf_pages)),
            str(int(policy.leading_pdf_pages)),
            str(int(policy.trailing_pdf_pages)),
            str(int(policy.min_pdf_pages)),
            str(int(policy.target_extracted_chars)),
            str(float(policy.max_pdf_seconds)),
            str(int(policy.ocr_dpi)),
        ])
    )


def _existing_auto_summary_evidence(
    intelligence_object: WorkspaceIntelligenceObject,
    *,
    source_hash: str,
    version_number: int,
    policy: DocIntelExtractionPolicy,
) -> tuple[str, dict, str]:
    object_metadata = safe_metadata_payload(
        intelligence_object.metadata_json
    )
    cache = object_metadata.get("summary_evidence_cache")

    if not isinstance(cache, dict):
        return "", {}, ""

    try:
        cached_version = int(cache.get("target_version") or 0)
    except (TypeError, ValueError):
        return "", {}, ""

    if not (
        cache.get("contract") == _AUTO_SUMMARY_EVIDENCE_CACHE_CONTRACT
        and str(cache.get("source_hash") or "").strip() == source_hash
        and cached_version == int(version_number)
        and str(cache.get("policy") or "").strip() == policy.name
        and str(cache.get("policy_fingerprint") or "").strip()
        == _auto_summary_policy_fingerprint(policy)
    ):
        return "", {}, ""

    evidence_text = clean_multiline_text(cache.get("text"))
    evidence_hash = str(cache.get("text_hash") or "").strip()
    evidence_metadata = _clean_evidence_metadata(cache.get("extraction"))

    if not (
        evidence_text
        and evidence_hash
        and stable_hash(evidence_text) == evidence_hash
    ):
        return "", {}, ""

    return evidence_text, evidence_metadata, evidence_hash


def _evidence_coverage_note(evidence: dict) -> str:
    coverage_mode = str(
        evidence.get("coverage_mode") or "complete"
    ).strip()
    source_page_count = evidence.get("source_page_count")
    evidence_pages = evidence.get("evidence_pages") or []

    if coverage_mode == "complete":
        return "Evidence coverage: complete source coverage."

    page_fragment = ""
    if source_page_count and evidence_pages:
        page_fragment = (
            f" Representative source pages acquired: {evidence_pages} "
            f"of {source_page_count}."
        )

    return (
        "Evidence coverage: bounded representative evidence only; this is not "
        "an exhaustive page-by-page analysis."
        + page_fragment
    )


def _make_evidence_progress_callback(
    context: IntelligenceJobExecutionContext,
):
    def _record(payload: dict) -> None:
        context.raise_if_execution_invalid()
        phase = str(payload.get("phase") or "evidence_acquisition")
        completed = max(0, int(payload.get("completed_pages") or 0))
        planned = max(1, int(payload.get("planned_pages") or 1))
        fraction = min(1.0, completed / planned)

        if phase == "native_text_probe":
            progress_percent = 25 + int(round(fraction * 4))
            message = "Probing representative PDF pages for native text."
        elif phase == "ocr_evidence":
            progress_percent = 30 + int(round(fraction * 14))
            message = "Acquiring bounded OCR evidence for Auto Summary."
        else:
            progress_percent = 25
            message = "Acquiring representative evidence for Auto Summary."

        context.record_stage(
            "evidence_acquisition",
            progress_percent=min(44, progress_percent),
            message=message,
            details=payload,
        )
        logger.info(
            "[SIS][AUTO_SUMMARY_EVIDENCE] job_id=%s phase=%s "
            "page=%s completed=%s/%s source_pages=%s evidence_chars=%s "
            "elapsed_seconds=%s",
            context.job.job_id,
            phase,
            payload.get("source_page") or "n/a",
            completed,
            planned,
            payload.get("source_page_count") or "n/a",
            payload.get("evidence_chars") or 0,
            payload.get("elapsed_seconds") or 0,
        )

    return _record


@dataclass(frozen=True)
class _SourceSnapshot:
    file_registry_id: int
    intelligence_object_id: int
    document_id: str
    original_name: str
    path: str
    version_number: int
    source_hash: str
    reusable_summary_hash: str = ""
    reusable_summary_chars: int = 0
    reusable_evidence_text: str = ""
    reusable_evidence_metadata: dict | None = None
    reusable_evidence_hash: str = ""

    @property
    def has_reusable_summary(self) -> bool:
        return bool(self.reusable_summary_hash)

    @property
    def has_reusable_evidence(self) -> bool:
        return bool(
            self.reusable_evidence_text
            and self.reusable_evidence_hash
            and isinstance(self.reusable_evidence_metadata, dict)
        )


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


def _existing_auto_summary(
    intelligence_object: WorkspaceIntelligenceObject,
    *,
    source_hash: str,
) -> tuple[str, int]:
    metadata = safe_metadata_payload(intelligence_object.metadata_json)
    detailed_summary = clean_multiline_text(
        intelligence_object.detailed_summary
    )
    summary_hash = str(intelligence_object.summary_hash or "").strip()

    if not (
        intelligence_object.summary_status == WORKSPACE_INTELLIGENCE_READY_STATUS
        and str(intelligence_object.source_hash or "").strip() == source_hash
        and metadata.get("summary_source") == AUTO_SUMMARY_SOURCE
        and metadata.get("summary_processor_key") == AUTO_SUMMARY_PROCESSOR_KEY
        and str(metadata.get("summary_processor_version") or "").strip()
        == AUTO_SUMMARY_PROCESSOR_VERSION
        and detailed_summary
        and summary_hash
    ):
        return "", 0

    return summary_hash, len(detailed_summary)


def _load_source_snapshot(
    context: IntelligenceJobExecutionContext,
) -> _SourceSnapshot:
    job = context.job

    if not job.file_registry_id or not job.intelligence_object_id:
        raise IntelligenceJobTerminalError(
            "Auto Summary job is missing durable file or intelligence identity.",
            failure_code="summary_identity_missing",
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
                "Auto Summary source record no longer exists.",
                failure_code="summary_source_not_found",
                stage="source_validation",
            )

        if not _record_is_available(record):
            raise IntelligenceJobTerminalError(
                "Auto Summary source is no longer active.",
                failure_code="summary_source_unavailable",
                stage="source_validation",
            )

        if not _source_matches_job(
            record=record,
            intelligence_object=intelligence_object,
            context=context,
        ):
            raise IntelligenceJobTerminalError(
                "Auto Summary source version or checksum no longer matches the job.",
                failure_code="summary_source_superseded",
                stage="source_validation",
            )

        if not record_supports_text_enrichment(record):
            raise IntelligenceJobTerminalError(
                "Auto Summary does not support this file type.",
                failure_code="summary_file_type_unsupported",
                stage="source_validation",
            )

        path = str(record.path or "").strip()
        if not path or not Path(path).is_file():
            raise IntelligenceJobRetryableError(
                "Auto Summary source path is temporarily unavailable.",
                failure_code="summary_source_path_missing",
                retry_delay_seconds=int(
                    settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
                ),
                stage="source_validation",
            )

        reusable_hash, reusable_chars = _existing_auto_summary(
            intelligence_object,
            source_hash=str(job.source_hash or "").strip(),
        )
        evidence_policy = _auto_summary_extraction_policy()
        (
            reusable_evidence_text,
            reusable_evidence_metadata,
            reusable_evidence_hash,
        ) = _existing_auto_summary_evidence(
            intelligence_object,
            source_hash=str(job.source_hash or "").strip(),
            version_number=int(record.version_number or 1),
            policy=evidence_policy,
        )

        return _SourceSnapshot(
            file_registry_id=int(record.id),
            intelligence_object_id=int(intelligence_object.id),
            document_id=str(record.random_name),
            original_name=str(record.original_name or record.random_name),
            path=path,
            version_number=int(record.version_number or 1),
            source_hash=str(record.checksum or "").strip(),
            reusable_summary_hash=reusable_hash,
            reusable_summary_chars=reusable_chars,
            reusable_evidence_text=reusable_evidence_text,
            reusable_evidence_metadata=reusable_evidence_metadata,
            reusable_evidence_hash=reusable_evidence_hash,
        )
    finally:
        db_session.close()


def _split_source_page_sections(document_text: str) -> list[tuple[int, int, str]]:
    clean_text = clean_multiline_text(document_text)
    marker_pattern = re.compile(
        r"(?m)^\[SOURCE PAGE\s+(\d+)\s+OF\s+(\d+)\]\s*$"
    )
    matches = list(marker_pattern.finditer(clean_text))

    if not matches:
        return []

    sections: list[tuple[int, int, str]] = []
    for index, match in enumerate(matches):
        body_start = match.end()
        body_end = (
            matches[index + 1].start()
            if index + 1 < len(matches)
            else len(clean_text)
        )
        body = clean_multiline_text(clean_text[body_start:body_end])
        if not body:
            continue
        sections.append((int(match.group(1)), int(match.group(2)), body))

    return sections


def _clip_context_text(value: str, max_chars: int) -> str:
    clean_value = clean_multiline_text(value)
    if max_chars <= 0 or len(clean_value) <= max_chars:
        return clean_value

    clipped = clean_value[: max_chars + 1]
    boundary = max(
        clipped.rfind("\n"),
        clipped.rfind(". "),
        clipped.rfind(" "),
    )
    if boundary >= max(80, int(max_chars * 0.60)):
        clipped = clipped[:boundary]
    else:
        clipped = clipped[:max_chars]
    return clipped.strip()


def _summary_line_score(line: str) -> int:
    clean_line = " ".join(str(line or "").split()).strip()
    if len(clean_line) < 32:
        return 0

    words = _SUMMARY_WORD_RE.findall(clean_line)
    if len(words) < 5:
        return 0

    nonspace = [character for character in clean_line if not character.isspace()]
    alpha_count = sum(character.isalpha() for character in nonspace)
    digit_count = sum(character.isdigit() for character in nonspace)
    symbol_count = max(0, len(nonspace) - alpha_count - digit_count)
    total_count = max(1, len(nonspace))

    alpha_ratio = alpha_count / total_count
    symbol_ratio = symbol_count / total_count
    digit_ratio = digit_count / total_count
    if alpha_ratio < 0.48 or symbol_ratio > 0.34:
        return 0

    score = min(len(words), 32)
    score += len(_SUMMARY_STRUCTURE_RE.findall(clean_line)) * 8
    score += len(_SUMMARY_MATERIAL_RE.findall(clean_line)) * 4
    if clean_line.endswith(('.', ':', ';')):
        score += 2
    if digit_ratio > 0.22:
        score -= 6

    return max(0, score)


def _representative_summary_lines(page_text: str, *, limit: int = 8) -> list[str]:
    clean_text = clean_multiline_text(page_text)
    raw_lines = [line.strip() for line in clean_text.splitlines()]
    candidates: list[dict] = []
    seen: set[str] = set()

    for index, raw_line in enumerate(raw_lines):
        if not raw_line:
            continue

        parts = [raw_line]
        if not raw_line.endswith((".", "!", "?", ":", ";")):
            for lookahead in range(index + 1, min(len(raw_lines), index + 3)):
                next_line = raw_lines[lookahead]
                if not next_line:
                    break
                parts.append(next_line)
                if next_line.endswith((".", "!", "?", ":", ";")):
                    break

        clean_line = " ".join(" ".join(parts).split()).strip()
        clean_key = clean_line.casefold()
        if not clean_line or clean_key in seen:
            continue
        seen.add(clean_key)

        score = _summary_line_score(clean_line)
        if score <= 0:
            continue
        candidates.append({
            "index": index,
            "line": _clip_context_text(clean_line, 360),
            "score": score,
        })

    ranked = sorted(
        candidates,
        key=lambda item: (-item["score"], item["index"]),
    )
    selected: list[dict] = []
    selected_word_sets: list[set[str]] = []
    for item in ranked:
        item_words = {
            word.casefold()
            for word in _SUMMARY_WORD_RE.findall(str(item["line"]))
        }
        is_duplicate = any(
            item_words
            and prior_words
            and (
                len(item_words & prior_words)
                / max(1, min(len(item_words), len(prior_words)))
            )
            >= 0.68
            for prior_words in selected_word_sets
        )
        if is_duplicate:
            continue

        selected.append(item)
        selected_word_sets.append(item_words)
        if len(selected) >= limit:
            break

    return [str(item["line"]) for item in selected if item.get("line")]


def _representative_page_context(page_text: str, max_chars: int) -> str:
    clean_text = clean_multiline_text(page_text)
    if len(clean_text) <= max_chars:
        return clean_text

    head_budget = max(120, int(max_chars * 0.62))
    head = _clip_context_text(clean_text, head_budget)
    remaining_source = clean_text[len(head):].lstrip()
    representative = _representative_summary_lines(
        remaining_source,
        limit=8,
    )

    if not representative:
        return _clip_context_text(clean_text, max_chars)

    remaining = max(0, max_chars - len(head) - 2)
    representative_text = _clip_context_text(
        "\n".join(representative),
        remaining,
    )
    return clean_multiline_text(
        "\n\n".join(part for part in (head, representative_text) if part)
    )[:max_chars].strip()


def _balanced_page_context(document_text: str, budget: int) -> str:
    pages = _split_source_page_sections(document_text)
    if not pages:
        return ""

    marker_overhead = sum(
        len(f"[SOURCE PAGE {page_number} OF {source_page_count}]\n\n")
        for page_number, source_page_count, _ in pages
    )
    content_budget = max(400, budget - marker_overhead)

    # Leading evidence pages are intentionally weighted as structural anchors.
    # Auto Summary acquisition always selects the beginning of a PDF first, where
    # titles, contents, introductions, executive summaries, and purpose statements
    # most often live. Later representative pages remain present, but cannot consume
    # the context simply because they contain dense OCR or incidental back matter.
    weights: list[float] = []
    for index, (_, _, body) in enumerate(pages):
        weight = 2.0 if index < 4 else 1.0
        if len(body) < 240:
            weight *= 0.55
        weights.append(weight)

    total_weight = sum(weights) or 1.0
    quotas = [
        max(180, int(content_budget * (weight / total_weight)))
        for weight in weights
    ]

    used = [min(len(pages[index][2]), quota) for index, quota in enumerate(quotas)]
    remaining = max(0, content_budget - sum(used))

    # Redistribute budget left unused by short cover/back-matter pages to the
    # highest-value structural anchors first, then to the remaining evidence.
    expansion_order = sorted(
        range(len(pages)),
        key=lambda index: (weights[index], len(pages[index][2])),
        reverse=True,
    )
    while remaining > 0:
        progressed = False
        for index in expansion_order:
            capacity = len(pages[index][2]) - used[index]
            if capacity <= 0:
                continue
            grant = min(capacity, remaining, 240)
            used[index] += grant
            remaining -= grant
            progressed = True
            if remaining <= 0:
                break
        if not progressed:
            break

    sections: list[str] = []
    for index, (page_number, source_page_count, body) in enumerate(pages):
        excerpt = _representative_page_context(body, used[index])
        if not excerpt:
            continue
        sections.append(
            f"[SOURCE PAGE {page_number} OF {source_page_count}]\n{excerpt}"
        )

    return clean_multiline_text("\n\n".join(sections))[:budget].strip()


def _bounded_source_context(document_text: str) -> str:
    clean_text = clean_multiline_text(document_text)
    budget = AUTO_SUMMARY_SOURCE_CHAR_BUDGET

    if len(clean_text) <= budget:
        return clean_text

    page_context = _balanced_page_context(clean_text, budget)
    if page_context:
        return page_context

    representative = "\n".join(
        representative_document_lines(
            clean_text,
            limit=10,
        )
    )
    head_budget = int(budget * 0.42)
    tail_budget = int(budget * 0.20)
    representative_budget = max(
        0,
        budget - head_budget - tail_budget - 160,
    )

    sections = [
        "[DOCUMENT BEGINNING]",
        _clip_context_text(clean_text, head_budget),
    ]

    if representative:
        sections.extend([
            "[REPRESENTATIVE MATERIAL]",
            _clip_context_text(representative, representative_budget),
        ])

    sections.extend([
        "[DOCUMENT ENDING]",
        _clip_context_text(clean_text[-tail_budget:], tail_budget),
    ])

    return clean_multiline_text("\n\n".join(sections))[:budget].strip()


def _truncate_multiline(value: str, max_chars: int) -> str:
    clean_value = clean_multiline_text(value)

    if max_chars <= 0 or len(clean_value) <= max_chars:
        return clean_value

    clipped = clean_value[: max_chars + 1]
    boundary = max(
        clipped.rfind("\n"),
        clipped.rfind(". "),
        clipped.rfind(" "),
    )

    if boundary >= max(200, int(max_chars * 0.65)):
        clipped = clipped[: boundary + (1 if clipped[boundary:boundary + 2] == ". " else 0)]
    else:
        clipped = clipped[:max_chars]

    return clipped.strip()


def _persist_evidence_cache(
    *,
    context: IntelligenceJobExecutionContext,
    source: _SourceSnapshot,
    document_text: str,
    evidence_metadata: dict,
) -> str:
    """Persist source/version-bound evidence before model generation."""

    context.raise_if_execution_invalid()
    policy = _auto_summary_extraction_policy()
    evidence_text = clean_multiline_text(document_text)
    evidence_hash = stable_hash(evidence_text)
    now = utc_now()
    cache_payload = {
        "contract": _AUTO_SUMMARY_EVIDENCE_CACHE_CONTRACT,
        "source_hash": source.source_hash,
        "target_version": source.version_number,
        "policy": policy.name,
        "policy_fingerprint": _auto_summary_policy_fingerprint(policy),
        "text": evidence_text,
        "text_hash": evidence_hash,
        "extraction": dict(evidence_metadata),
        "cached_at": now.isoformat(),
    }

    db_session = SessionLocal.session_factory()

    try:
        record = (
            db_session.query(FileRegistry)
            .filter(FileRegistry.id == source.file_registry_id)
            .with_for_update()
            .one_or_none()
        )
        intelligence_object = (
            db_session.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.id
                == source.intelligence_object_id
            )
            .with_for_update()
            .one_or_none()
        )

        if record is None or intelligence_object is None:
            raise IntelligenceJobTerminalError(
                "Auto Summary source disappeared before evidence persistence.",
                failure_code="summary_source_not_found",
                stage="evidence_persistence",
            )

        if not _record_is_available(record):
            raise IntelligenceJobTerminalError(
                "Auto Summary source became unavailable before evidence persistence.",
                failure_code="summary_source_unavailable",
                stage="evidence_persistence",
            )

        if not _source_matches_job(
            record=record,
            intelligence_object=intelligence_object,
            context=context,
        ):
            raise IntelligenceJobTerminalError(
                "Auto Summary source changed before evidence persistence.",
                failure_code="summary_source_superseded",
                stage="evidence_persistence",
            )

        object_metadata = safe_metadata_payload(
            intelligence_object.metadata_json
        )
        intelligence_object.metadata_json = {
            **object_metadata,
            "summary_evidence_cache": cache_payload,
        }
        intelligence_object.extracted_text_hash = evidence_hash
        intelligence_object.extracted_at = now
        intelligence_object.extraction_status = (
            WORKSPACE_INTELLIGENCE_READY_STATUS
        )
        db_session.commit()
        return evidence_hash
    except (IntelligenceJobTerminalError, IntelligenceJobRetryableError):
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise IntelligenceJobRetryableError(
            (
                "Auto Summary evidence persistence failed: "
                f"{type(exc).__name__}: {exc}"
            ),
            failure_code="summary_evidence_persistence_failed",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="evidence_persistence",
        ) from exc
    finally:
        db_session.close()


def _generate_summary(
    *,
    context: IntelligenceJobExecutionContext,
    source: _SourceSnapshot,
    document_text: str,
    evidence_metadata: dict,
) -> tuple[str, str]:
    source_context = _bounded_source_context(document_text)

    if not source_context:
        raise IntelligenceJobTerminalError(
            "DocIntel returned no usable text for Auto Summary.",
            failure_code="summary_source_text_empty",
            stage="docintel_extraction",
        )

    prompt = (
        f"Document: {source.original_name}\n\n"
        f"{_evidence_coverage_note(evidence_metadata)}\n\n"
        f"{_auto_summary_instruction(evidence_metadata)}"
    )
    input_packet = LLMExecutionInput(
        user_query=prompt,
        mode=LLMExecutionMode.INFORMATIONAL_ONLY,
        context={
            "document_context": {
                "document_text": source_context,
            }
        },
        response_format=LLMResponseFormat.TEXT,
        call_site=AUTO_SUMMARY_CALL_SITE,
        max_new_tokens=int(settings.SIS_AUTO_SUMMARY_MAX_NEW_TOKENS),
        runtime_profile=LLMRuntimeProfile.STATIC_CACHE,
        timeout_seconds=int(settings.SIS_AUTO_SUMMARY_TIMEOUT_SECONDS),
    )

    result = execute_governed_llm_operation(
        input_packet,
        operation_kind="automatic_intelligence",
        operation_id="auto_summary.generate",
        contract_version=AUTO_SUMMARY_PROCESSOR_VERSION,
        actor_id="system:auto_summary",
        request_id=str(context.job.job_id),
        trigger_type="auto_summary",
        source_resource={
            "document_id": source.document_id,
            "file_id": source.file_registry_id,
            "original_name": source.original_name,
            "path": source.path,
            "version_number": source.version_number,
            "checksum": source.source_hash,
        },
        priority="P3",
        request_class="background",
    )

    if result.is_failure():
        failure = result.failure
        reason = (
            failure.reason
            if failure is not None
            else LLMFailureReason.INTERNAL_ERROR
        )
        message = str(
            getattr(failure, "message", "")
            or "Auto Summary model execution failed."
        )

        if reason == LLMFailureReason.REFUSED:
            raise IntelligenceJobTerminalError(
                message,
                failure_code="summary_generation_refused",
                stage="summary_generation",
                details={"llm_failure_reason": reason.value},
            )

        raise IntelligenceJobRetryableError(
            message,
            failure_code=f"summary_generation_{reason.value}",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="summary_generation",
            details={"llm_failure_reason": reason.value},
        )

    generated_text = clean_multiline_text(
        result.output.text if result.output is not None else ""
    )

    generated_text, sanitized_count_claims = (
        _sanitize_unsupported_tabular_structural_counts(
            generated_text,
            source_context=source_context,
            evidence_metadata=evidence_metadata,
        )
    )
    if sanitized_count_claims:
        logger.info(
            "[SIS][AUTO_SUMMARY_TABULAR_COUNT_SANITIZED] document_id=%s "
            "removed_claims=%s",
            source.document_id,
            sanitized_count_claims,
        )

    if not generated_text:
        raise IntelligenceJobRetryableError(
            "Auto Summary model returned an empty summary.",
            failure_code="summary_generation_empty",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="summary_generation",
        )

    detailed_summary = _truncate_multiline(
        generated_text,
        MAX_DETAILED_SUMMARY_CHARS,
    )
    short_summary = truncate_text(
        detailed_summary.split("\n\n", 1)[0],
        MAX_SHORT_SUMMARY_CHARS,
    )

    return detailed_summary, short_summary


def _materialize_reusable_summary_action_result(
    *,
    context: IntelligenceJobExecutionContext,
    source: _SourceSnapshot,
    stored: dict,
) -> tuple[str, int]:
    """Materialize content-hash-reused Summary intelligence onto this file version."""

    result_payload = (
        dict(stored.get("result"))
        if isinstance(stored.get("result"), dict)
        else {}
    )
    detailed_summary = clean_multiline_text(
        stored.get("result_text")
        or result_payload.get("content")
    )

    if not detailed_summary:
        raise IntelligenceJobRetryableError(
            "Reusable Summary Action result did not contain summary content.",
            failure_code="summary_reuse_result_empty",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="summary_reuse",
        )

    short_summary = clean_multiline_text(
        result_payload.get("short_summary")
    )
    if not short_summary:
        short_summary = truncate_text(
            detailed_summary.split("\n\n", 1)[0],
            MAX_SHORT_SUMMARY_CHARS,
        )

    stored_evidence = (
        dict(stored.get("evidence"))
        if isinstance(stored.get("evidence"), dict)
        else {}
    )
    cached_evidence = (
        dict(stored_evidence.get("summary_evidence_cache"))
        if isinstance(
            stored_evidence.get("summary_evidence_cache"),
            dict,
        )
        else {}
    )
    cached_text = clean_multiline_text(
        cached_evidence.get("text")
    )
    cached_text_hash = str(
        cached_evidence.get("text_hash")
        or ""
    ).strip()
    reusable_evidence = bool(
        cached_text
        and cached_text_hash
        and stable_hash(cached_text) == cached_text_hash
    )
    evidence_metadata = (
        dict(cached_evidence.get("extraction"))
        if isinstance(cached_evidence.get("extraction"), dict)
        else {}
    )

    db_session = SessionLocal.session_factory()

    try:
        record = (
            db_session.query(FileRegistry)
            .filter(FileRegistry.id == source.file_registry_id)
            .with_for_update()
            .one_or_none()
        )
        intelligence_object = (
            db_session.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.id
                == source.intelligence_object_id
            )
            .with_for_update()
            .one_or_none()
        )

        if record is None or intelligence_object is None:
            raise IntelligenceJobTerminalError(
                "Auto Summary source disappeared before reusable-result persistence.",
                failure_code="summary_source_not_found",
                stage="summary_reuse",
            )

        if not _record_is_available(record):
            raise IntelligenceJobTerminalError(
                "Auto Summary source became unavailable before reusable-result persistence.",
                failure_code="summary_source_unavailable",
                stage="summary_reuse",
            )

        if not _source_matches_job(
            record=record,
            intelligence_object=intelligence_object,
            context=context,
        ):
            raise IntelligenceJobTerminalError(
                "Auto Summary source changed before reusable-result persistence.",
                failure_code="summary_source_superseded",
                stage="summary_reuse",
            )

        existing_hash, existing_chars = _existing_auto_summary(
            intelligence_object,
            source_hash=source.source_hash,
        )
        if existing_hash:
            db_session.rollback()
            return existing_hash, existing_chars

        now = utc_now()
        summary_hash = stable_hash(
            f"{short_summary}\n\n{detailed_summary}"
        )

        intelligence_object.short_summary = short_summary
        intelligence_object.detailed_summary = detailed_summary
        intelligence_object.search_text = merge_search_texts(
            detailed_summary,
            intelligence_object.search_text,
        )
        intelligence_object.summary_hash = summary_hash
        intelligence_object.summarized_at = now
        intelligence_object.summary_status = (
            WORKSPACE_INTELLIGENCE_READY_STATUS
        )
        intelligence_object.stale_reason = None
        intelligence_object.error_message = None

        object_metadata = safe_metadata_payload(
            intelligence_object.metadata_json
        )

        if reusable_evidence:
            current_cache = {
                **cached_evidence,
                "source_hash": source.source_hash,
                "target_version": source.version_number,
                "text": cached_text,
                "text_hash": cached_text_hash,
                "cached_at": now.isoformat(),
            }
            object_metadata["summary_evidence_cache"] = current_cache
            intelligence_object.extracted_text_hash = cached_text_hash
            intelligence_object.extracted_at = now
            intelligence_object.extraction_status = (
                WORKSPACE_INTELLIGENCE_READY_STATUS
            )

        stored_metadata = (
            dict(stored.get("metadata"))
            if isinstance(stored.get("metadata"), dict)
            else {}
        )
        summary_context = (
            _bounded_source_context(cached_text)
            if reusable_evidence
            else ""
        )

        intelligence_object.metadata_json = {
            **object_metadata,
            "summary_source": AUTO_SUMMARY_SOURCE,
            "summary_status": WORKSPACE_INTELLIGENCE_READY_STATUS,
            "summary_job_id": context.job.job_id,
            "summary_source_hash": source.source_hash,
            "summary_target_version": source.version_number,
            "summary_processor_key": AUTO_SUMMARY_PROCESSOR_KEY,
            "summary_processor_version": AUTO_SUMMARY_PROCESSOR_VERSION,
            "summary_model_key": (
                str(stored.get("model_key") or "").strip()
                or context.job.model_key
            ),
            "summary_source_chars": (
                len(cached_text)
                if reusable_evidence
                else stored_metadata.get("summary_source_chars")
            ),
            "summary_context_contract": AUTO_SUMMARY_CONTEXT_CONTRACT,
            "summary_context_chars": len(summary_context),
            "summary_context_hash": (
                stable_hash(summary_context)
                if summary_context
                else ""
            ),
            "summary_evidence_policy": evidence_metadata.get("policy"),
            "summary_evidence_coverage_mode": evidence_metadata.get(
                "coverage_mode"
            ),
            "summary_evidence_complete_source_coverage": bool(
                evidence_metadata.get("complete_source_coverage")
            ),
            "summary_evidence_source_page_count": evidence_metadata.get(
                "source_page_count"
            ),
            "summary_evidence_selected_pages": evidence_metadata.get(
                "selected_pages"
            ),
            "summary_evidence_pages": evidence_metadata.get(
                "evidence_pages"
            ),
            "summary_evidence_ocr_pages": evidence_metadata.get(
                "ocr_pages_processed"
            ),
            "summary_evidence_ocr_used": bool(
                evidence_metadata.get("ocr_used")
            ),
            "summary_evidence_stop_reason": evidence_metadata.get(
                "stop_reason"
            ),
            "summary_tabular_evidence_contract": evidence_metadata.get(
                "tabular_evidence_contract"
            ),
            "summary_reused_action_result_id": str(
                stored.get("result_id")
                or ""
            ).strip(),
            "summary_reused_result_hash": str(
                stored.get("result_hash")
                or ""
            ).strip(),
            "summarized_at": now.isoformat(),
        }

        record_metadata = safe_metadata_payload(record.meta)
        record.meta = {
            **record_metadata,
            "workspace_intelligence_extraction_status": (
                intelligence_object.extraction_status
                or record_metadata.get(
                    "workspace_intelligence_extraction_status"
                )
            ),
            "workspace_intelligence_summary_status": (
                WORKSPACE_INTELLIGENCE_READY_STATUS
            ),
            "workspace_intelligence_summary_job_id": context.job.job_id,
            "workspace_intelligence_summary_job_status": (
                "artifact_reused_by_content_hash"
            ),
            "workspace_intelligence_summary_source": AUTO_SUMMARY_SOURCE,
        }

        link_ready_solomon_file_action_result(
            result_id=str(stored.get("result_id") or "").strip(),
            file_registry_id=source.file_registry_id,
            source_version=source.version_number,
            source_hash=source.source_hash,
            linked_by_user_id=0,
            trigger_type="automatic_summary_reuse",
            request_id=context.job.job_id,
            db_session=db_session,
        )

        db_session.commit()
        return summary_hash, len(detailed_summary)
    except (IntelligenceJobTerminalError, IntelligenceJobRetryableError):
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise IntelligenceJobRetryableError(
            (
                "Reusable Auto Summary persistence failed: "
                f"{type(exc).__name__}: {exc}"
            ),
            failure_code="summary_reuse_persistence_failed",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="summary_reuse",
        ) from exc
    finally:
        db_session.close()


def _persist_summary(
    *,
    context: IntelligenceJobExecutionContext,
    source: _SourceSnapshot,
    document_text: str,
    evidence_metadata: dict,
    detailed_summary: str,
    short_summary: str,
) -> tuple[str, int]:
    db_session = SessionLocal.session_factory()

    try:
        record = (
            db_session.query(FileRegistry)
            .filter(FileRegistry.id == source.file_registry_id)
            .with_for_update()
            .one_or_none()
        )
        intelligence_object = (
            db_session.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.id
                == source.intelligence_object_id
            )
            .with_for_update()
            .one_or_none()
        )

        if record is None or intelligence_object is None:
            raise IntelligenceJobTerminalError(
                "Auto Summary source disappeared before persistence.",
                failure_code="summary_source_not_found",
                stage="summary_persistence",
            )

        if not _record_is_available(record):
            raise IntelligenceJobTerminalError(
                "Auto Summary source became unavailable before persistence.",
                failure_code="summary_source_unavailable",
                stage="summary_persistence",
            )

        if not _source_matches_job(
            record=record,
            intelligence_object=intelligence_object,
            context=context,
        ):
            raise IntelligenceJobTerminalError(
                "Auto Summary source changed before persistence.",
                failure_code="summary_source_superseded",
                stage="summary_persistence",
            )

        reusable_hash, reusable_chars = _existing_auto_summary(
            intelligence_object,
            source_hash=source.source_hash,
        )
        if reusable_hash:
            db_session.rollback()
            return reusable_hash, reusable_chars

        now = utc_now()
        summary_hash = stable_hash(
            f"{short_summary}\n\n{detailed_summary}"
        )

        intelligence_object.short_summary = short_summary
        intelligence_object.detailed_summary = detailed_summary
        intelligence_object.search_text = merge_search_texts(
            detailed_summary,
            intelligence_object.search_text,
        )
        intelligence_object.extracted_text_hash = stable_hash(document_text)
        intelligence_object.summary_hash = summary_hash
        intelligence_object.extracted_at = now
        intelligence_object.summarized_at = now
        intelligence_object.extraction_status = WORKSPACE_INTELLIGENCE_READY_STATUS
        intelligence_object.summary_status = WORKSPACE_INTELLIGENCE_READY_STATUS
        intelligence_object.stale_reason = None
        intelligence_object.error_message = None

        object_metadata = safe_metadata_payload(
            intelligence_object.metadata_json
        )
        summary_context = _bounded_source_context(document_text)
        intelligence_object.metadata_json = {
            **object_metadata,
            "summary_source": AUTO_SUMMARY_SOURCE,
            "summary_status": WORKSPACE_INTELLIGENCE_READY_STATUS,
            "summary_job_id": context.job.job_id,
            "summary_source_hash": source.source_hash,
            "summary_target_version": source.version_number,
            "summary_processor_key": AUTO_SUMMARY_PROCESSOR_KEY,
            "summary_processor_version": AUTO_SUMMARY_PROCESSOR_VERSION,
            "summary_model_key": context.job.model_key,
            "summary_source_chars": len(document_text),
            "summary_context_contract": AUTO_SUMMARY_CONTEXT_CONTRACT,
            "summary_context_chars": len(summary_context),
            "summary_context_hash": stable_hash(summary_context),
            "summary_evidence_policy": evidence_metadata.get("policy"),
            "summary_evidence_coverage_mode": evidence_metadata.get(
                "coverage_mode"
            ),
            "summary_evidence_complete_source_coverage": bool(
                evidence_metadata.get("complete_source_coverage")
            ),
            "summary_evidence_source_page_count": evidence_metadata.get(
                "source_page_count"
            ),
            "summary_evidence_selected_pages": evidence_metadata.get(
                "selected_pages"
            ),
            "summary_evidence_pages": evidence_metadata.get("evidence_pages"),
            "summary_evidence_ocr_pages": evidence_metadata.get(
                "ocr_pages_processed"
            ),
            "summary_evidence_ocr_used": bool(
                evidence_metadata.get("ocr_used")
            ),
            "summary_evidence_stop_reason": evidence_metadata.get(
                "stop_reason"
            ),
            "summary_tabular_evidence_contract": evidence_metadata.get(
                "tabular_evidence_contract"
            ),
            "summarized_at": now.isoformat(),
        }

        record_metadata = safe_metadata_payload(record.meta)
        record.meta = {
            **record_metadata,
            "workspace_intelligence_extraction_status": (
                WORKSPACE_INTELLIGENCE_READY_STATUS
            ),
            "workspace_intelligence_summary_status": (
                WORKSPACE_INTELLIGENCE_READY_STATUS
            ),
            "workspace_intelligence_summary_job_id": context.job.job_id,
            "workspace_intelligence_summary_job_status": "artifact_persisted",
            "workspace_intelligence_summary_source": AUTO_SUMMARY_SOURCE,
        }

        action_definition = get_solomon_file_action_definition(
            "summary.view"
        )
        if action_definition is not None:
            evidence_cache = (
                dict(object_metadata.get("summary_evidence_cache"))
                if isinstance(
                    object_metadata.get("summary_evidence_cache"),
                    dict,
                )
                else {}
            )
            persist_ready_solomon_file_action_result(
                action_id=action_definition.action_id,
                action_contract_version=(
                    action_definition.action_contract_version
                ),
                source_hash=source.source_hash,
                result_type=action_definition.result_type,
                result_text=detailed_summary,
                result_json={
                    "type": action_definition.result_type,
                    "title": "Summary",
                    "content": detailed_summary,
                    "short_summary": short_summary,
                    "generated_at": now.isoformat(),
                },
                parameters={},
                processor_key=AUTO_SUMMARY_PROCESSOR_KEY,
                processor_version=AUTO_SUMMARY_PROCESSOR_VERSION,
                model_key=context.job.model_key or "",
                provenance={
                    "source_hash": source.source_hash,
                    "summary_hash": summary_hash,
                },
                evidence={
                    "summary_evidence_cache": evidence_cache,
                },
                metadata={
                    "auto_summary_job_id": context.job.job_id,
                    "summary_source_chars": len(document_text),
                    "summary_context_contract": AUTO_SUMMARY_CONTEXT_CONTRACT,
                    "summary_hash": summary_hash,
                },
                file_registry_id=source.file_registry_id,
                source_version=source.version_number,
                linked_by_user_id=0,
                trigger_type="automatic_summary",
                request_id=context.job.job_id,
                db_session=db_session,
            )

        db_session.commit()
        return summary_hash, len(detailed_summary)
    except (IntelligenceJobTerminalError, IntelligenceJobRetryableError):
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()
        raise IntelligenceJobRetryableError(
            f"Auto Summary persistence failed: {type(exc).__name__}: {exc}",
            failure_code="summary_persistence_failed",
            retry_delay_seconds=int(
                settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
            ),
            stage="summary_persistence",
        ) from exc
    finally:
        db_session.close()


def process_generate_document_summary(
    context: IntelligenceJobExecutionContext,
) -> IntelligenceJobProcessorResult:
    """Process one durable GENERATE_DOCUMENT_SUMMARY job."""

    context.raise_if_execution_invalid()
    source = _load_source_snapshot(context)

    context.record_stage(
        "source_validated",
        progress_percent=AUTO_SUMMARY_PROGRESS_SOURCE_VALIDATED,
        message="Auto Summary source identity validated.",
        details={
            "file_registry_id": source.file_registry_id,
            "document_id": source.document_id,
            "target_version": source.version_number,
            "source_hash": source.source_hash,
        },
    )

    if source.has_reusable_summary:
        context.record_stage(
            "summary_reused",
            progress_percent=AUTO_SUMMARY_PROGRESS_ARTIFACT_READY,
            message="Existing persisted Auto Summary is reusable.",
            details={
                "summary_hash": source.reusable_summary_hash,
                "summary_chars": source.reusable_summary_chars,
            },
        )
        logger.info(
            "[SIS][AUTO_SUMMARY_REUSED] job_id=%s document_id=%s summary_hash=%s",
            context.job.job_id,
            source.document_id,
            source.reusable_summary_hash,
        )
        return IntelligenceJobProcessorResult(
            result={
                "artifact_type": AUTO_SUMMARY_ARTIFACT_TYPE,
                "document_id": source.document_id,
                "source_hash": source.source_hash,
                "summary_hash": source.reusable_summary_hash,
                "summary_chars": source.reusable_summary_chars,
                "reused": True,
            },
            intelligence_object_id=source.intelligence_object_id,
            stage="summary_reused",
        )

    action_definition = get_solomon_file_action_definition(
        "summary.view"
    )
    reusable_action_result = None

    if action_definition is not None:
        reusable_action_result = (
            resolve_ready_solomon_file_action_result(
                action_id=action_definition.action_id,
                action_contract_version=(
                    action_definition.action_contract_version
                ),
                source_hash=source.source_hash,
                parameters={},
            )
        )

    if reusable_action_result:
        context.record_stage(
            "summary_content_reuse",
            progress_percent=AUTO_SUMMARY_PROGRESS_PERSISTENCE_STARTED,
            message=(
                "Reusing a persisted Summary for identical governed content."
            ),
            details={
                "result_id": reusable_action_result.get("result_id"),
                "result_hash": reusable_action_result.get("result_hash"),
                "source_hash": source.source_hash,
            },
        )
        summary_hash, summary_chars = (
            _materialize_reusable_summary_action_result(
                context=context,
                source=source,
                stored=reusable_action_result,
            )
        )
        context.record_stage(
            "summary_reused",
            progress_percent=AUTO_SUMMARY_PROGRESS_ARTIFACT_READY,
            message=(
                "Persisted Summary reused by content identity; "
                "no model generation was required."
            ),
            details={
                "summary_hash": summary_hash,
                "summary_chars": summary_chars,
                "result_id": reusable_action_result.get("result_id"),
            },
        )
        logger.info(
            "[SIS][AUTO_SUMMARY_CONTENT_REUSED] "
            "job_id=%s document_id=%s source_hash=%s result_id=%s",
            context.job.job_id,
            source.document_id,
            source.source_hash,
            reusable_action_result.get("result_id"),
        )
        return IntelligenceJobProcessorResult(
            result={
                "artifact_type": AUTO_SUMMARY_ARTIFACT_TYPE,
                "document_id": source.document_id,
                "source_hash": source.source_hash,
                "summary_hash": summary_hash,
                "summary_chars": summary_chars,
                "reused": True,
                "reuse_scope": "content_hash",
                "action_result_id": reusable_action_result.get(
                    "result_id"
                ),
            },
            intelligence_object_id=source.intelligence_object_id,
            stage="summary_reused",
        )

    evidence_reused = source.has_reusable_evidence

    if evidence_reused:
        document_text = clean_multiline_text(source.reusable_evidence_text)
        evidence_metadata = _clean_evidence_metadata(
            source.reusable_evidence_metadata
        )
        context.raise_if_execution_invalid()
        context.record_stage(
            "evidence_reused",
            progress_percent=AUTO_SUMMARY_PROGRESS_EXTRACTION_COMPLETE,
            message=(
                "Reusing persisted Auto Summary evidence for the current "
                "source version."
            ),
            details={
                "source_chars": len(document_text),
                "evidence_hash": source.reusable_evidence_hash,
                "coverage_mode": evidence_metadata.get("coverage_mode"),
                "source_page_count": evidence_metadata.get(
                    "source_page_count"
                ),
                "evidence_pages": evidence_metadata.get("evidence_pages"),
                "stop_reason": evidence_metadata.get("stop_reason"),
            },
        )
        logger.info(
            "[SIS][AUTO_SUMMARY_EVIDENCE_REUSED] job_id=%s document_id=%s "
            "source_chars=%s evidence_hash=%s coverage=%s evidence_pages=%s/%s",
            context.job.job_id,
            source.document_id,
            len(document_text),
            source.reusable_evidence_hash,
            evidence_metadata.get("coverage_mode"),
            len(evidence_metadata.get("evidence_pages") or []),
            evidence_metadata.get("source_page_count") or "n/a",
        )
    else:
        context.record_stage(
            "docintel_extraction",
            progress_percent=AUTO_SUMMARY_PROGRESS_EXTRACTION_STARTED,
            message="Extracting source text for Auto Summary.",
        )

        try:
            docintel_packet = ingest_documents_for_intent(
                intent=None,
                resolved_paths=[source.path],
                extraction_policy=_auto_summary_extraction_policy(),
                progress_callback=_make_evidence_progress_callback(context),
            )
        except DocIntelIngestError as exc:
            raise IntelligenceJobTerminalError(
                f"DocIntel extraction failed: {exc}",
                failure_code="summary_docintel_failed",
                stage="docintel_extraction",
            ) from exc
        except Exception as exc:
            raise IntelligenceJobRetryableError(
                f"Unexpected DocIntel failure: {type(exc).__name__}: {exc}",
                failure_code="summary_docintel_unavailable",
                retry_delay_seconds=int(
                    settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
                ),
                stage="docintel_extraction",
            ) from exc

        document = select_docintel_document(docintel_packet)
        document_text = clean_multiline_text(document.get("text"))
        evidence_metadata = _clean_evidence_metadata(
            document.get("extraction")
        )

        if not document_text:
            raise IntelligenceJobTerminalError(
                "DocIntel returned no extracted text for Auto Summary.",
                failure_code="summary_source_text_empty",
                stage="docintel_extraction",
            )

        context.raise_if_execution_invalid()
        evidence_hash = _persist_evidence_cache(
            context=context,
            source=source,
            document_text=document_text,
            evidence_metadata=evidence_metadata,
        )
        context.record_stage(
            "docintel_extracted",
            progress_percent=AUTO_SUMMARY_PROGRESS_EXTRACTION_COMPLETE,
            message=(
                "Auto Summary evidence acquisition completed and was "
                "persisted for retry reuse."
            ),
            details={
                "source_chars": len(document_text),
                "evidence_hash": evidence_hash,
                "evidence_cached": True,
                "coverage_mode": evidence_metadata.get("coverage_mode"),
                "complete_source_coverage": evidence_metadata.get(
                    "complete_source_coverage"
                ),
                "source_page_count": evidence_metadata.get(
                    "source_page_count"
                ),
                "selected_pages": evidence_metadata.get("selected_pages"),
                "evidence_pages": evidence_metadata.get("evidence_pages"),
                "ocr_pages_processed": evidence_metadata.get(
                    "ocr_pages_processed"
                ),
                "stop_reason": evidence_metadata.get("stop_reason"),
            },
        )

    context.record_stage(
        "summary_generation",
        progress_percent=AUTO_SUMMARY_PROGRESS_GENERATION_STARTED,
        message="Generating persisted Auto Summary through SIS.",
        details={
            "source_chars": len(document_text),
            "context_chars": len(_bounded_source_context(document_text)),
            "evidence_reused": evidence_reused,
        },
    )

    detailed_summary, short_summary = _generate_summary(
        context=context,
        source=source,
        document_text=document_text,
        evidence_metadata=evidence_metadata,
    )

    context.raise_if_execution_invalid()
    context.record_stage(
        "summary_generated",
        progress_percent=AUTO_SUMMARY_PROGRESS_GENERATION_COMPLETE,
        message="Auto Summary model generation completed.",
        details={"generated_summary_chars": len(detailed_summary)},
    )
    context.record_stage(
        "summary_persistence",
        progress_percent=AUTO_SUMMARY_PROGRESS_PERSISTENCE_STARTED,
        message="Persisting Auto Summary artifact state.",
        details={"generated_summary_chars": len(detailed_summary)},
    )

    summary_hash, summary_chars = _persist_summary(
        context=context,
        source=source,
        document_text=document_text,
        evidence_metadata=evidence_metadata,
        detailed_summary=detailed_summary,
        short_summary=short_summary,
    )

    context.record_stage(
        "summary_persisted",
        progress_percent=AUTO_SUMMARY_PROGRESS_ARTIFACT_READY,
        message="Auto Summary artifact persisted; finalizing durable job.",
        details={
            "summary_hash": summary_hash,
            "summary_chars": summary_chars,
        },
    )

    logger.info(
        "[SIS][AUTO_SUMMARY_COMPLETE] job_id=%s document_id=%s "
        "source_chars=%s summary_chars=%s summary_hash=%s coverage=%s "
        "evidence_pages=%s/%s stop_reason=%s",
        context.job.job_id,
        source.document_id,
        len(document_text),
        summary_chars,
        summary_hash,
        evidence_metadata.get("coverage_mode"),
        len(evidence_metadata.get("evidence_pages") or []),
        evidence_metadata.get("source_page_count") or "n/a",
        evidence_metadata.get("stop_reason") or "n/a",
    )

    return IntelligenceJobProcessorResult(
        result={
            "artifact_type": AUTO_SUMMARY_ARTIFACT_TYPE,
            "document_id": source.document_id,
            "source_hash": source.source_hash,
            "summary_hash": summary_hash,
            "summary_chars": summary_chars,
            "evidence": evidence_metadata,
            "reused": False,
        },
        intelligence_object_id=source.intelligence_object_id,
        stage="summary_persisted",
    )


__all__ = [
    "AUTO_SUMMARY_JOB_TYPE",
    "process_generate_document_summary",
]

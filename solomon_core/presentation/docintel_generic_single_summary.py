# ---------------------------------------------------------------------------
# FILE: docintel_generic_single_summary.py
# DIRECTORY: solomon_core/presentation/
# ---------------------------------------------------------------------------
# Generic DocIntel — Explicit Source Operation Presenter
#
# Purpose:
#   Adapt already-ingested DocIntel evidence into the established SolomonAI
#   source-operation response contract.
#
# Hard Rules:
#   - No estimator framing
#   - No BEI vocabulary
#   - Evidence-bound
#   - No file reads or ownership resolution
#   - Only explicit server-approved source operations are accepted
#   - Single-document summaries use an authorized structured evidence brief as LLM input
#   - Deterministic DocIntel summary output remains the failure fallback
#   - Shared V3 wrapper owns non-summary LLM execution, validation, and fallback
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Tuple

from solomon_core.logger import get_logger
from solomon_core.presentation.docintel_summary_narration import (
    narrate_docintel_summary,
)
from solomon_workspace.context.workspace_solomon_llm import (
    generate_workspace_solomon_answer,
)
from solomon_workspace.context.workspace_solomon_prompt import (
    WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES,
    WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS,
    WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES,
    normalize_workspace_solomon_request_action,
)
from solomon_workspace.context.workspace_solomon_source_preview import (
    WORKSPACE_SOLOMON_SOURCE_PREVIEW_PER_FILE_CHARS,
    WORKSPACE_SOLOMON_SOURCE_PREVIEW_TOTAL_CHARS,
    normalize_workspace_solomon_source_text,
)


logger = get_logger("docintel_generic_single_summary")

_SUMMARY_NARRATION_ENABLED = True

_CURRENCY_PATTERN = re.compile(r"\$[\d,]+(?:\.\d{2})?", re.IGNORECASE)
_DATE_PATTERN = re.compile(
    r"(\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"[a-z]*\.?\s+\d{1,2},?\s+\d{2,4}\b)",
    re.IGNORECASE,
)
_PERCENT_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s?%", re.IGNORECASE)
_DURATION_PATTERN = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:days?|weeks?|months?|years?)\b",
    re.IGNORECASE,
)
_VALUE_PATTERN = re.compile(
    r"(\$[\d,]+(?:\.\d{2})?|\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b|"
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)"
    r"[a-z]*\.?\s+\d{1,2},?\s+\d{2,4}\b|\b\d+(?:\.\d+)?\s?%|"
    r"\b\d+(?:\.\d+)?\s?(?:days?|weeks?|months?|years?)\b)",
    re.IGNORECASE,
)
_SECTION_PATTERN = re.compile(
    r"\b\d{2,6}(?:\.\d{2,6})+(?:\s*[-–—]\s*[A-Za-z].*)?",
    re.IGNORECASE,
)
_EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
    re.IGNORECASE,
)
_PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?1[-.\s]?)?(?:\(?\d{3}\)?[-.\s]?)\d{3}[-.\s]?\d{4}(?!\d)",
    re.IGNORECASE,
)

_DOCUMENT_PROFILES: Dict[str, Dict[str, Any]] = {
    "proposal_or_bid": {
        "label": "proposal or bid document",
        "terms": (
            "bid",
            "proposal",
            "scope of work",
            "addenda",
            "addendum",
            "exclusions",
            "qualifications",
            "unit price",
            "unit rate",
            "alternate",
            "submitted",
        ),
        "review_note": (
            "This is a summary, not a full bid review or recommendation. Ask for "
            "a bid review when you want exclusions, qualifications, comparisons, "
            "or pricing risk evaluated."
        ),
        "pricing_prefix": "Pricing shown includes",
        "adder_prefix": "Adders, escalation, or unit items include",
        "scope_prefix": "Scope language references",
        "review_prefix": "Items to review include",
        "fallback_prefix": "The main captured proposal details include",
    },
    "contract": {
        "label": "contract or agreement",
        "terms": (
            "contract",
            "agreement",
            "party",
            "parties",
            "term",
            "termination",
            "indemnify",
            "warranty",
            "liability",
            "obligation",
        ),
        "review_note": (
            "This is a summary, not a legal review or recommendation. Ask for a "
            "contract review when you want obligations, risk, or unusual terms evaluated."
        ),
        "pricing_prefix": "Financial or payment terms shown include",
        "adder_prefix": "Additional cost or timing terms include",
        "scope_prefix": "Agreement language references",
        "review_prefix": "Items to review include",
        "fallback_prefix": "The main captured contract details include",
    },
    "specification": {
        "label": "specification or requirements document",
        "terms": (
            "specification",
            "section",
            "division",
            "submittal",
            "astm",
            "ansi",
            "ul ",
            "execution",
            "products",
            "quality assurance",
        ),
        "review_note": (
            "This is a summary, not a compliance review or recommendation. Ask for "
            "a specification review when you want requirements, exceptions, or conflicts evaluated."
        ),
        "pricing_prefix": "Cost-related references include",
        "adder_prefix": "Alternate or add items include",
        "scope_prefix": "Requirements reference",
        "review_prefix": "Items to review include",
        "fallback_prefix": "The main captured specification details include",
    },
    "report": {
        "label": "report or memo",
        "terms": (
            "report",
            "memo",
            "memorandum",
            "findings",
            "recommendation",
            "conclusion",
            "analysis",
            "executive summary",
            "background",
        ),
        "review_note": (
            "This is a summary, not an independent review or recommendation. Ask "
            "for a deeper review when you want findings, risks, or action items evaluated."
        ),
        "pricing_prefix": "Quantified details include",
        "adder_prefix": "Additional quantified items include",
        "scope_prefix": "The report references",
        "review_prefix": "Items to review include",
        "fallback_prefix": "The main captured report details include",
    },
    "invoice": {
        "label": "invoice or payment document",
        "terms": (
            "invoice",
            "receipt",
            "amount due",
            "subtotal",
            "tax",
            "balance",
            "remit",
            "payment",
            "paid",
        ),
        "review_note": (
            "This is a summary, not a payment approval or accounting decision. "
            "Verify the source document before relying on amounts, dates, or balances."
        ),
        "pricing_prefix": "Amounts shown include",
        "adder_prefix": "Additional charges or line items include",
        "scope_prefix": "Payment record language references",
        "review_prefix": "Items to verify include",
        "fallback_prefix": "The main captured invoice details include",
    },
    "correspondence": {
        "label": "letter or correspondence",
        "terms": (
            "dear ",
            "sincerely",
            "regards",
            "subject:",
            "to:",
            "from:",
            "email",
            "phone",
            "contact",
        ),
        "review_note": (
            "This is a summary, not a response draft or decision. Ask for a reply "
            "or action review when you want follow-up steps prepared."
        ),
        "pricing_prefix": "Amounts mentioned include",
        "adder_prefix": "Additional cost or timing details include",
        "scope_prefix": "Message content references",
        "review_prefix": "Items to follow up on include",
        "fallback_prefix": "The main captured message details include",
    },
    "general": {
        "label": "general document",
        "terms": (),
        "review_note": (
            "This is a summary, not a full review, recommendation, or decision. "
            "Ask for a deeper review when you want risks, comparisons, or action items evaluated."
        ),
        "pricing_prefix": "Amounts or values mentioned include",
        "adder_prefix": "Additional quantified details include",
        "scope_prefix": "The document references",
        "review_prefix": "Items to review include",
        "fallback_prefix": "The main captured details include",
    },
}

_DETAIL_SIGNAL_GROUPS: Tuple[Tuple[str, Tuple[str, ...]], ...] = (
    (
        "pricing details",
        (
            "$",
            "price",
            "pricing",
            "cost",
            "amount",
            "total",
            "allowance",
            "unit rate",
            "rate",
            "subtotal",
            "balance",
        ),
    ),
    (
        "timing language",
        (
            "schedule",
            "duration",
            "days",
            "weeks",
            "months",
            "date",
            "deadline",
            "lead time",
            "mobilization",
            "valid",
        ),
    ),
    (
        "scope language",
        (
            "scope",
            "work",
            "included",
            "includes",
            "furnish",
            "install",
            "provide",
            "labor",
            "material",
            "requirement",
            "shall",
        ),
    ),
    (
        "conditions or exclusions",
        (
            "exclude",
            "excluded",
            "exclusion",
            "not included",
            "by others",
            "clarification",
            "qualification",
            "condition",
            "unless",
            "except",
        ),
    ),
    (
        "formal references",
        (
            "contract",
            "proposal",
            "agreement",
            "terms",
            "addendum",
            "addenda",
            "specification",
            "drawing",
            "section",
            "revision",
        ),
    ),
    (
        "contact or signature information",
        (
            "email",
            "phone",
            "signature",
            "signed",
            "submitted",
            "prepared by",
            "contact",
        ),
    ),
)

_CONTINUATION_ENDINGS = (
    " of",
    " for",
    " with",
    " from",
    " to",
    " by",
    " and",
    " or",
    " the",
    " a",
    " an",
    " per",
    " before",
    " after",
    " unless",
    " including",
    " related to",
    " based on",
    " due to",
    " in",
    " on",
    " at",
    " as",
)
_CONTINUATION_STARTS = (
    "and ",
    "or ",
    "of ",
    "for ",
    "with ",
    "from ",
    "to ",
    "by ",
    "the ",
    "a ",
    "an ",
    "per ",
    "before ",
    "after ",
    "unless ",
    "including ",
    "related ",
    "material ",
    "system ",
    "receipt ",
    "approval ",
    "completion ",
    "escalation ",
)

_MAX_SUMMARY_SOURCE_CHARS = 60000
_MAX_NARRATION_BRIEF_CHARS = 12000
_MAX_KEY_DETAILS = 12
_MIN_USABLE_TEXT_CHARS = 80
_SMALL_DOCUMENT_FULL_TEXT_CHARS = 3500
_SMALL_DOCUMENT_LINE_LIMIT = 55
_SMALL_DOCUMENT_NARRATION_BRIEF_CHARS = 4500
_NARRATION_LEAD_LINE_LIMIT = 10
_NARRATION_HEADING_LINE_LIMIT = 8
_NARRATION_KEY_DETAIL_LIMIT = 14
_NARRATION_REVIEW_LINE_LIMIT = 6
_NARRATION_SCOPE_LINE_LIMIT = 6
_NARRATION_CONTACT_LINE_LIMIT = 4
_NARRATION_TAIL_LINE_LIMIT = 6


# ============================================================================
# Basic helpers
# ============================================================================


def _safe_text(value: Any) -> str:
    """Return normalized non-empty text."""

    if isinstance(value, str):
        return value.strip()

    return ""


def _compact_text(value: str) -> str:
    """Return text with internal whitespace collapsed."""

    return re.sub(r"\s+", " ", str(value or "")).strip()


def _clean_display_line(value: str) -> str:
    """Return a user-facing evidence line with common OCR artifacts reduced."""

    line = _compact_text(value)
    line = re.sub(r"^[•\-\u2022\*]+\s*", "", line)
    line = re.sub(r"\s+([,.;:])", r"\1", line)
    line = re.sub(r"\bto(?=\d)", "to ", line)
    line = re.sub(r"\b([A-Z]{1,6})\s*\-\s*(\d+)\b", r"\1-\2", line)
    line = re.sub(r"(\d)\s+([\"”])", r"\1\2", line)
    line = re.sub(r"\s+&\s+", " & ", line)
    line = re.sub(r"\s+[-–—]\s+", " - ", line)
    line = re.sub(r"\s{2,}", " ", line)

    return line.strip(" \t|")


def _plain_detail_fragment(line: str) -> str:
    """Return one evidence line without extraction labels or list numbering."""

    fragment = _clean_display_line(line)
    fragment = re.sub(
        r"^(?:value|date / timing|percentage|addenda|reference|contact|"
        r"scope / requirement|condition|detail):\s*",
        "",
        fragment,
        flags=re.IGNORECASE,
    )
    fragment = re.sub(r"^\d+[.)]\s*", "", fragment)
    fragment = fragment.strip(" -–—")

    return fragment.rstrip(".")


def _format_human_list(values: List[str]) -> str:
    """Return a readable comma-separated list."""

    clean_values = [value for value in values if value]

    if not clean_values:
        return ""

    if len(clean_values) == 1:
        return clean_values[0]

    if len(clean_values) == 2:
        return f"{clean_values[0]} and {clean_values[1]}"

    return ", ".join(clean_values[:-1]) + f", and {clean_values[-1]}"


def _dedupe_preserve_order(lines: List[str]) -> List[str]:
    """Return de-duplicated cleaned lines while preserving original order."""

    selected: List[str] = []
    seen: set[str] = set()

    for line in lines:
        clean_line = _plain_detail_fragment(line)
        key = clean_line.casefold()

        if not clean_line or key in seen:
            continue

        seen.add(key)
        selected.append(clean_line)

    return selected


def _is_standalone_date_fragment(line: str) -> bool:
    """Return True when a fragment is only a date."""

    clean_line = _plain_detail_fragment(line)

    if not clean_line:
        return False

    return _DATE_PATTERN.fullmatch(clean_line) is not None


def _is_bare_heading_fragment(line: str) -> bool:
    """Return True when a fragment is a heading without summary substance."""

    clean_line = _plain_detail_fragment(line)
    lower_line = clean_line.casefold().strip(":")

    if not clean_line:
        return True

    if clean_line.endswith(":"):
        return True

    return lower_line in {
        "bid includes",
        "included",
        "includes",
        "exclusions",
        "qualifications",
        "clarifications",
        "pricing",
        "scope",
        "terms",
        "conditions",
    }


def _subject_without_trailing_amount(line: str) -> Tuple[str, str]:
    """Return a subject phrase and its first currency amount, when present."""

    clean_line = _plain_detail_fragment(line)
    amount_match = _CURRENCY_PATTERN.search(clean_line)

    if not amount_match:
        return clean_line, ""

    amount = amount_match.group(0)
    subject = _CURRENCY_PATTERN.sub("", clean_line, count=1)
    subject = _compact_text(subject).strip(" -–—:;,.")
    subject = re.sub(r"\btotal\b$", "", subject, flags=re.IGNORECASE).strip(" -–—:;,.")

    return subject or clean_line, amount


def _normalize_acknowledged_addenda(line: str) -> str:
    """Return natural wording for acknowledged addenda fragments."""

    clean_line = _plain_detail_fragment(line)
    lower_line = clean_line.casefold()

    if "acknowledge addenda" not in lower_line and "acknowledge addendum" not in lower_line:
        return ""

    remainder = re.sub(
        r"^acknowledge addenda\s*:?\s*",
        "",
        clean_line,
        flags=re.IGNORECASE,
    )
    remainder = re.sub(
        r"^acknowledge addendum\s*:?\s*",
        "",
        remainder,
        flags=re.IGNORECASE,
    )
    remainder = _compact_text(remainder).strip(" -–—:;,.").casefold()

    if remainder in {"one", "1", "no. 1", "number 1"}:
        return "one acknowledged addendum"

    if remainder:
        return f"acknowledged addenda {remainder}"

    return "acknowledged addenda"


def _review_fragment_to_summary(line: str) -> str:
    """Return a clean review item without bare headings or isolated dates."""

    addenda_summary = _normalize_acknowledged_addenda(line)

    if addenda_summary:
        return addenda_summary

    clean_line = _plain_detail_fragment(line)
    lower_line = clean_line.casefold().strip(":")

    if not clean_line or _is_standalone_date_fragment(clean_line):
        return ""

    if lower_line in {"bid includes", "included", "includes"}:
        return ""

    if "project and system" in lower_line and "exclusion" in lower_line:
        return "project and system-specific exclusions"

    if lower_line in {"exclusions", "specific exclusions", "project exclusions"}:
        return "exclusions"

    if lower_line.startswith("currently lead times"):
        return _compact_text(clean_line[len("Currently "):]).rstrip(".")

    if clean_line.endswith(":"):
        return ""

    return clean_line.rstrip(".")


# ============================================================================
# Source adaptation
# ============================================================================


def _get_documents(decision: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Return normalized document records from the Decision Object."""

    raw_documents = decision.get("documents")

    if not isinstance(raw_documents, list):
        return []

    return [document for document in raw_documents if isinstance(document, dict)]


def _get_document_extension(display_name: str) -> str:
    """Return the display-name extension for source metadata."""

    return Path(str(display_name or "")).suffix.lower().lstrip(".")


def _get_document_text(
    *,
    evidence: Dict[str, Any],
    decision: Dict[str, Any],
    document: Dict[str, Any],
    document_index: int,
) -> str:
    """Return already-ingested evidence text for one authorized document."""

    document_id = _safe_text(document.get("document_id"))
    display_name = _safe_text(document.get("display_name"))

    for key in (display_name, document_id):
        if not key:
            continue

        document_evidence = evidence.get(key)

        if not isinstance(document_evidence, dict):
            continue

        raw_text = _safe_text(document_evidence.get("raw_text"))

        if raw_text:
            return raw_text

    if document_index == 0:
        primary_raw_text = _safe_text(evidence.get("raw_text"))

        if primary_raw_text:
            return primary_raw_text

        decision_raw_text = _safe_text(decision.get("raw_text"))

        if decision_raw_text:
            return decision_raw_text

    return ""


def _normalize_summary_source_text(raw_text: str) -> Tuple[str, bool]:
    """Return text available to deterministic summaries without LLM prompt limits."""

    clean_text = str(raw_text or "").replace("\r", "\n").strip()

    if len(clean_text) <= _MAX_SUMMARY_SOURCE_CHARS:
        return clean_text, False

    return clean_text[:_MAX_SUMMARY_SOURCE_CHARS], True


def _build_standard_source_previews(
    *,
    documents: List[Dict[str, Any]],
    evidence: Dict[str, Any],
    decision: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build bounded source previews for existing non-summary source operations."""

    source_previews: List[Dict[str, Any]] = []
    remaining_chars = WORKSPACE_SOLOMON_SOURCE_PREVIEW_TOTAL_CHARS

    for document_index, document in enumerate(documents):
        if remaining_chars <= 0:
            break

        document_id = _safe_text(document.get("document_id"))
        display_name = _safe_text(document.get("display_name")) or document_id or "Selected document"
        preview_limit = min(WORKSPACE_SOLOMON_SOURCE_PREVIEW_PER_FILE_CHARS, remaining_chars)
        raw_text = _get_document_text(
            evidence=evidence,
            decision=decision,
            document=document,
            document_index=document_index,
        )
        preview_text = (
            normalize_workspace_solomon_source_text(raw_text, limit=preview_limit)
            if raw_text
            else ""
        )

        source_previews.append({
            "document_id": document_id,
            "name": display_name,
            "extension": _get_document_extension(display_name),
            "status": "ready" if preview_text else "unavailable",
            "text": preview_text,
            "chars": len(preview_text),
        })
        remaining_chars -= len(preview_text)

    return source_previews


def _build_summary_source_records(
    *,
    documents: List[Dict[str, Any]],
    evidence: Dict[str, Any],
    decision: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Build source records for deterministic summaries from ingested text."""

    summary_sources: List[Dict[str, Any]] = []

    for document_index, document in enumerate(documents):
        document_id = _safe_text(document.get("document_id"))
        display_name = _safe_text(document.get("display_name")) or document_id or "Selected document"
        raw_text = _get_document_text(
            evidence=evidence,
            decision=decision,
            document=document,
            document_index=document_index,
        )
        summary_text, truncated = _normalize_summary_source_text(raw_text)

        summary_sources.append({
            "document_id": document_id,
            "name": display_name,
            "extension": _get_document_extension(display_name),
            "text": summary_text,
            "chars": len(summary_text),
            "raw_chars": len(raw_text),
            "truncated": truncated,
        })

    return summary_sources


def _build_sources_and_previews(
    *,
    decision: Dict[str, Any],
    evidence: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Adapt DocIntel evidence into the canonical SolomonAI source-preview shape."""

    documents = _get_documents(decision)
    sources: List[Dict[str, Any]] = []

    for document in documents:
        document_id = _safe_text(document.get("document_id"))
        display_name = _safe_text(document.get("display_name")) or document_id or "Selected document"

        sources.append({
            "document_id": document_id,
            "name": display_name,
            "extension": _get_document_extension(display_name),
        })

    source_previews = _build_standard_source_previews(
        documents=documents,
        evidence=evidence,
        decision=decision,
    )

    return sources, source_previews


def _get_request_action(decision: Dict[str, Any]) -> str:
    """Return the approved response action."""

    raw_action = _safe_text(decision.get("request_action"))

    if not raw_action:
        raw_action = WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES

    return normalize_workspace_solomon_request_action(raw_action)


def _build_default_user_task(*, request_action: str, source_count: int) -> str:
    """Return a compatibility task only when no user question was supplied."""

    if request_action == WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES:
        return "Compare the selected files."

    if request_action == WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS:
        return "Identify the key details in the selected files."

    if source_count == 1:
        return "Summarize the selected document."

    return "Summarize the selected files."


# ============================================================================
# Text selection
# ============================================================================


def _is_heading_like(line: str) -> bool:
    """Return True when a line is likely a heading rather than a detail."""

    compact = _clean_display_line(line)

    if not compact or len(compact) > 90:
        return False

    words = [
        word
        for word in compact.split()
        if any(character.isalpha() for character in word)
    ]

    if not words:
        return False

    uppercase_words = sum(
        1
        for word in words
        if word.upper() == word and len(word) > 1
    )

    return uppercase_words / max(len(words), 1) >= 0.65 and not _VALUE_PATTERN.search(compact)


def _is_noisy_summary_line(line: str) -> bool:
    """Return True when a line is not suitable for user-facing summary output."""

    compact = _clean_display_line(line)

    if len(compact) < 4:
        return True

    if not any(character.isalpha() for character in compact):
        return True

    if len(compact) > 320:
        return True

    punctuation_count = sum(
        1
        for character in compact
        if not character.isalnum() and not character.isspace()
    )
    punctuation_ratio = punctuation_count / max(len(compact), 1)

    return punctuation_ratio > 0.50 and not _VALUE_PATTERN.search(compact)


def _is_probable_continuation(previous: str, current: str) -> bool:
    """Return True when current line should be joined to previous line."""

    previous_clean = _clean_display_line(previous)
    current_clean = _clean_display_line(current)

    if not previous_clean or not current_clean:
        return False

    if len(previous_clean) + len(current_clean) > 260:
        return False

    if _CURRENCY_PATTERN.search(previous_clean) and _CURRENCY_PATTERN.search(current_clean):
        return False

    if _is_heading_like(previous_clean):
        return False

    if previous_clean.endswith((".", "!", "?", ";")):
        return False

    previous_lower = previous_clean.casefold()
    current_lower = current_clean.casefold()

    if previous_lower.endswith(_CONTINUATION_ENDINGS):
        return True

    if current_lower.startswith(_CONTINUATION_STARTS):
        return True

    return bool(current_clean[:1]) and current_clean[:1].islower() and len(previous_clean) < 180


def _split_summary_lines(text: str) -> List[str]:
    """Return deterministic, stitched, de-duplicated evidence lines."""

    lines: List[str] = []
    seen: set[str] = set()

    for raw_line in str(text or "").replace("\r", "\n").split("\n"):
        line = _clean_display_line(raw_line)

        if _is_noisy_summary_line(line):
            continue

        if lines and _is_probable_continuation(lines[-1], line):
            lines[-1] = _clean_display_line(f"{lines[-1]} {line}")
            continue

        key = line.casefold()

        if key in seen:
            continue

        seen.add(key)
        lines.append(line)

    return lines


def _line_contains_any(line: str, terms: Tuple[str, ...]) -> bool:
    """Return True when a cleaned line contains any supplied term."""

    lower_line = line.casefold()

    return any(term in lower_line for term in terms)


def _line_has_known_signal(line: str) -> bool:
    """Return True when a line contains a deterministic document signal."""

    if _VALUE_PATTERN.search(line):
        return True

    return any(
        _line_contains_any(line, terms)
        for _label, terms in _DETAIL_SIGNAL_GROUPS
    )


def _score_document_type(*, name: str, lines: List[str], terms: Tuple[str, ...]) -> int:
    """Return deterministic keyword score for a document type."""

    sample = "\n".join([name, *lines[:120]]).casefold()

    return sum(sample.count(term) for term in terms)


def _detect_document_profile(*, source_name: str, lines: List[str]) -> Tuple[str, Dict[str, Any]]:
    """Return the deterministic document profile for the selected source."""

    best_key = "general"
    best_score = 0

    for key, profile in _DOCUMENT_PROFILES.items():
        if key == "general":
            continue

        score = _score_document_type(
            name=source_name,
            lines=lines,
            terms=tuple(profile.get("terms") or ()),
        )

        if score > best_score:
            best_key = key
            best_score = score

    return best_key, _DOCUMENT_PROFILES.get(best_key, _DOCUMENT_PROFILES["general"])


def _score_detail_line(line: str) -> int:
    """Return a deterministic usefulness score for one evidence line."""

    score = 0

    if _CURRENCY_PATTERN.search(line):
        score += 10

    if _DATE_PATTERN.search(line):
        score += 6

    if _PERCENT_PATTERN.search(line):
        score += 6

    if _DURATION_PATTERN.search(line):
        score += 5

    if _SECTION_PATTERN.search(line):
        score += 4

    if _EMAIL_PATTERN.search(line) or _PHONE_PATTERN.search(line):
        score += 4

    for _label, terms in _DETAIL_SIGNAL_GROUPS:
        if _line_contains_any(line, terms):
            score += 2

    if ":" in line:
        score += 1

    if 24 <= len(line) <= 190:
        score += 2
    elif 12 <= len(line) < 24:
        score += 1
    elif len(line) > 240:
        score -= 4

    if _is_heading_like(line):
        score -= 3

    return score


def _is_good_subject_line(line: str) -> bool:
    """Return True when line can serve as a primary visible subject."""

    if _is_heading_like(line):
        return False

    if len(line) < 18 or len(line) > 170:
        return False

    if _EMAIL_PATTERN.search(line) or _PHONE_PATTERN.search(line):
        return False

    if _is_bare_heading_fragment(line) or _is_standalone_date_fragment(line):
        return False

    return any(character.isalpha() for character in line)


def _select_subject_line(lines: List[str]) -> str:
    """Return the clearest early subject line from extracted text."""

    for line in lines[:80]:
        if _is_good_subject_line(line) and _line_has_known_signal(line):
            return line

    for line in lines[:40]:
        if _is_good_subject_line(line):
            return line

    return ""


def _select_key_detail_lines(lines: List[str]) -> List[str]:
    """Return high-signal lines while preserving original document order."""

    ranked: List[Tuple[int, int, str]] = []

    for index, line in enumerate(lines):
        score = _score_detail_line(line)

        if score > 2:
            ranked.append((index, score, line))

    top_ranked = sorted(ranked, key=lambda item: (-item[1], item[0]))[:_MAX_KEY_DETAILS]

    return [
        line
        for _index, _score, line in sorted(top_ranked, key=lambda item: item[0])
    ]


def _is_add_or_escalation_line(line: str) -> bool:
    """Return True when a line appears to be an add, escalation, or unit item."""

    lower_line = line.casefold()

    return (
        "add after" in lower_line
        or "per quarter" in lower_line
        or "ea unit" in lower_line
        or "unit price" in lower_line
        or "unit rate" in lower_line
        or " add $" in lower_line
        or lower_line.startswith("add ")
    )


def _is_scope_line(line: str) -> bool:
    """Return True when a line appears to describe work or requirements."""

    return _line_contains_any(
        line,
        (
            "scope",
            "provide",
            "install",
            "furnish",
            "work",
            "system",
            "material",
            "labor",
            "requirements",
            "shall",
            "include",
            "party",
            "parties",
            "obligation",
            "finding",
            "recommendation",
            "conclusion",
        ),
    )


def _is_review_line(line: str) -> bool:
    """Return True when a line appears to describe timing, limits, or review items."""

    lower_line = line.casefold()

    return (
        _DATE_PATTERN.search(line) is not None
        or _DURATION_PATTERN.search(line) is not None
        or _PERCENT_PATTERN.search(line) is not None
        or _line_contains_any(
            lower_line,
            (
                "acknowledge addenda",
                "acknowledge addendum",
                "exclude",
                "excluded",
                "exclusion",
                "condition",
                "qualification",
                "clarification",
                "addenda",
                "addendum",
                "lead time",
                "valid",
                "unless",
                "by others",
                "termination",
                "warranty",
                "liability",
                "tax",
                "balance",
                "amount due",
            ),
        )
    )


def _select_natural_lines(
    *,
    lines: List[str],
    predicate: Callable[[str], bool],
    limit: int,
    excluded: set[str] | None = None,
) -> List[str]:
    """Select natural user-facing evidence lines by predicate."""

    selected: List[str] = []
    seen: set[str] = set(excluded or set())

    for line in lines:
        clean_line = _plain_detail_fragment(line)
        key = clean_line.casefold()

        if not clean_line or key in seen:
            continue

        if len(clean_line) < 12 or len(clean_line) > 220:
            continue

        if _is_heading_like(clean_line):
            continue

        if _is_bare_heading_fragment(clean_line) or _is_standalone_date_fragment(clean_line):
            continue

        if not predicate(clean_line):
            continue

        seen.add(key)
        selected.append(clean_line)

        if len(selected) >= limit:
            break

    return selected


def _select_review_items(
    *,
    lines: List[str],
    limit: int,
    excluded: set[str] | None = None,
) -> List[str]:
    """Select clean review items without isolated dates or bare headings."""

    selected: List[str] = []
    seen: set[str] = set(excluded or set())

    for line in lines:
        if not _is_review_line(line):
            continue

        clean_line = _review_fragment_to_summary(line)
        key = clean_line.casefold()

        if not clean_line or key in seen:
            continue

        if len(clean_line) < 8 or len(clean_line) > 220:
            continue

        selected.append(clean_line)
        seen.add(key)

        if len(selected) >= limit:
            break

    return selected


def _join_detail_fragments(lines: List[str], *, max_items: int) -> str:
    """Return a compact natural-language list of selected evidence fragments."""

    fragments = _dedupe_preserve_order(lines)[:max_items]

    if not fragments:
        return ""

    return _format_human_list(fragments)


def _sentence_from_fragments(
    *,
    prefix: str,
    lines: List[str],
    max_items: int,
) -> str:
    """Build one natural summary sentence from evidence fragments."""

    joined = _join_detail_fragments(lines, max_items=max_items)

    if not joined:
        return ""

    return f"{prefix} {joined}."


# ============================================================================
# Summary presentation
# ============================================================================


def _build_document_summary_paragraph(
    *,
    source_name: str,
    profile_label: str,
    subject_line: str,
) -> str:
    """Return a natural document-summary paragraph."""

    subject, amount = _subject_without_trailing_amount(subject_line)

    if subject and amount:
        return (
            f"{source_name} appears to be a {profile_label} centered on "
            f"{subject}, with a captured value of {amount}."
        )

    if subject:
        return (
            f"{source_name} appears to be a {profile_label} centered on "
            f"{subject}."
        )

    return f"{source_name} appears to be a {profile_label}."


def _build_natural_key_points(
    *,
    profile: Dict[str, Any],
    lines: List[str],
    key_detail_lines: List[str],
) -> List[str]:
    """Return a small set of human-facing key points without extraction labels."""

    source_lines = lines if lines else key_detail_lines
    used: set[str] = set()
    points: List[str] = []

    base_pricing_lines = _select_natural_lines(
        lines=source_lines,
        predicate=lambda line: bool(_CURRENCY_PATTERN.search(line))
        and not _is_add_or_escalation_line(line),
        limit=4,
        excluded=used,
    )
    used.update(line.casefold() for line in base_pricing_lines)

    base_pricing_sentence = _sentence_from_fragments(
        prefix=str(profile.get("pricing_prefix") or "Amounts or values mentioned include"),
        lines=base_pricing_lines,
        max_items=4,
    )

    if base_pricing_sentence:
        points.append(base_pricing_sentence)

    add_or_escalation_lines = _select_natural_lines(
        lines=source_lines,
        predicate=lambda line: bool(_CURRENCY_PATTERN.search(line))
        and _is_add_or_escalation_line(line),
        limit=3,
        excluded=used,
    )
    used.update(line.casefold() for line in add_or_escalation_lines)

    add_or_escalation_sentence = _sentence_from_fragments(
        prefix=str(profile.get("adder_prefix") or "Additional quantified details include"),
        lines=add_or_escalation_lines,
        max_items=3,
    )

    if add_or_escalation_sentence:
        points.append(add_or_escalation_sentence)

    review_items = _select_review_items(
        lines=source_lines,
        limit=2,
        excluded=used,
    )

    if review_items:
        review_sentence = _sentence_from_fragments(
            prefix=str(profile.get("review_prefix") or "Items to review include"),
            lines=review_items,
            max_items=2,
        )

        if review_sentence:
            points.append(review_sentence)

    else:
        scope_lines = _select_natural_lines(
            lines=source_lines,
            predicate=lambda line: _is_scope_line(line)
            and not bool(_CURRENCY_PATTERN.search(line)),
            limit=2,
            excluded=used,
        )

        scope_sentence = _sentence_from_fragments(
            prefix=str(profile.get("scope_prefix") or "The document references"),
            lines=scope_lines,
            max_items=2,
        )

        if scope_sentence:
            points.append(scope_sentence)

    if points:
        return points[:3]

    fallback_lines = _dedupe_preserve_order(key_detail_lines)[:3]
    fallback_sentence = _sentence_from_fragments(
        prefix=str(profile.get("fallback_prefix") or "The main captured details include"),
        lines=fallback_lines,
        max_items=3,
    )

    return [fallback_sentence] if fallback_sentence else []


def _format_detail_bullets(lines: List[str]) -> str:
    """Return user-facing bullets without deterministic extraction labels."""

    bullets: List[str] = []

    for line in _dedupe_preserve_order(lines)[:3]:
        sentence = _plain_detail_fragment(line)

        if sentence and not sentence.endswith((".", "!", "?")):
            sentence += "."

        if sentence:
            bullets.append(f"- {sentence}")

    return "\n".join(bullets)


def _build_review_note(*, truncated: bool, profile: Dict[str, Any]) -> str:
    """Return a natural review boundary without internal system labels."""

    note = str(profile.get("review_note") or _DOCUMENT_PROFILES["general"]["review_note"])

    if truncated:
        note += (
            " The document text was long, so the summary used the first "
            f"{_MAX_SUMMARY_SOURCE_CHARS:,} extracted characters."
        )

    return note


def _build_unavailable_summary(source_name: str) -> str:
    """Return a deterministic response when no source text is available."""

    return (
        f"### {source_name}\n\n"
        "**Document summary**\n\n"
        "I could not summarize this document because no extracted text was "
        "available for the selected source.\n\n"
        "**Review note**\n"
        "- Re-open or re-process the file, then try the summary again. If the "
        "document is scanned or image-heavy, text extraction may need review."
    )


def _build_weak_text_summary(source_name: str, source_chars: int) -> str:
    """Return a professional fallback for weak extracted text."""

    return (
        f"### {source_name}\n\n"
        "**Document summary**\n\n"
        "The extracted text is too limited or noisy to produce a reliable "
        "summary.\n\n"
        "**Review note**\n"
        f"- Only {source_chars} characters of extracted text were available. Verify "
        "the original file and re-run the summary after improving text extraction "
        "or OCR quality."
    )


def _build_source_summary(summary_source: Dict[str, Any]) -> str:
    """Return a deterministic source-grounded summary for one source."""

    source_name = _safe_text(summary_source.get("name")) or "Selected document"
    source_text = _safe_text(summary_source.get("text"))
    source_chars = int(summary_source.get("chars") or 0)
    truncated = bool(summary_source.get("truncated"))

    if not source_text:
        return _build_unavailable_summary(source_name)

    lines = _split_summary_lines(source_text)

    if source_chars < _MIN_USABLE_TEXT_CHARS or len(lines) < 2:
        return _build_weak_text_summary(source_name, source_chars)

    _profile_key, profile = _detect_document_profile(
        source_name=source_name,
        lines=lines,
    )
    profile_label = str(profile.get("label") or "general document")
    subject_line = _select_subject_line(lines)
    key_detail_lines = _select_key_detail_lines(lines)
    overview_paragraph = _build_document_summary_paragraph(
        source_name=source_name,
        profile_label=profile_label,
        subject_line=subject_line,
    )
    natural_key_points = _build_natural_key_points(
        profile=profile,
        lines=lines,
        key_detail_lines=key_detail_lines,
    )

    sections: List[str] = [
        f"### {source_name}",
        "",
        "**Document summary**",
        "",
        overview_paragraph,
    ]

    if natural_key_points:
        sections.extend([
            "",
            "**Key information**",
            _format_detail_bullets(natural_key_points),
        ])

    sections.extend([
        "",
        "**Review note**",
        f"- {_build_review_note(truncated=truncated, profile=profile)}",
    ])

    return "\n".join(sections)


def _build_deterministic_summary_answer(
    *,
    summary_sources: List[Dict[str, Any]],
) -> str:
    """Return the deterministic DocIntel summary answer."""

    ready_sources = [
        summary_source
        for summary_source in summary_sources
        if isinstance(summary_source, dict)
    ]

    if not ready_sources:
        return (
            "I could not summarize the selected source because no authorized "
            "document evidence was available to DocIntel."
        )

    answer_parts: List[str] = []

    for summary_source in ready_sources:
        answer_parts.append(_build_source_summary(summary_source))
        answer_parts.append("")

    return "\n".join(answer_parts).strip()


def _deterministic_summary_confidence(summary_sources: List[Dict[str, Any]]) -> str:
    """Return a simple confidence label for deterministic summary output."""

    total_chars = _summary_source_char_count(summary_sources)

    if total_chars >= 2500:
        return "HIGH"

    if total_chars >= 1000:
        return "MEDIUM"

    return "LOW"


def _summary_source_char_count(summary_sources: List[Dict[str, Any]]) -> int:
    """Return total deterministic-summary character count."""

    return sum(
        int(summary_source.get("chars") or 0)
        for summary_source in summary_sources
        if isinstance(summary_source, dict)
    )


def _brief_line_key(line: str) -> str:
    """Return a stable key for cross-block evidence de-duplication."""

    clean_line = _plain_detail_fragment(line).casefold()
    clean_line = re.sub(
        r"[^a-z0-9]+",
        " ",
        clean_line,
    )
    clean_line = _compact_text(clean_line)

    return clean_line


def _append_unique_evidence_line(
    *,
    selected: List[str],
    seen: set[str],
    line: str,
) -> None:
    """Append one cleaned evidence line without duplicating content."""

    clean_line = _plain_detail_fragment(line)
    key = _brief_line_key(clean_line)

    if not clean_line or key in seen:
        return

    if _is_noisy_summary_line(clean_line):
        return

    seen.add(key)
    selected.append(clean_line)


def _select_heading_evidence_lines(lines: List[str]) -> List[str]:
    """Return heading-like structure lines useful for a summary brief."""

    selected: List[str] = []
    seen: set[str] = set()

    for line in lines:
        clean_line = _plain_detail_fragment(line)

        if not clean_line or len(clean_line) > 120:
            continue

        if not _is_heading_like(clean_line):
            continue

        _append_unique_evidence_line(
            selected=selected,
            seen=seen,
            line=clean_line,
        )

        if len(selected) >= _NARRATION_HEADING_LINE_LIMIT:
            break

    return selected


def _select_contact_evidence_lines(lines: List[str]) -> List[str]:
    """Return contact, source, or footer lines without overfilling the brief."""

    selected: List[str] = []
    seen: set[str] = set()

    for line in lines:
        clean_line = _plain_detail_fragment(line)
        lower_line = clean_line.casefold()

        has_contact_signal = (
            _EMAIL_PATTERN.search(clean_line) is not None
            or _PHONE_PATTERN.search(clean_line) is not None
            or "www." in lower_line
            or "http" in lower_line
            or "email" in lower_line
            or "phone" in lower_line
            or "contact" in lower_line
        )

        if not has_contact_signal:
            continue

        _append_unique_evidence_line(
            selected=selected,
            seen=seen,
            line=clean_line,
        )

        if len(selected) >= _NARRATION_CONTACT_LINE_LIMIT:
            break

    return selected


def _select_tail_evidence_lines(lines: List[str]) -> List[str]:
    """Return final document lines that may contain notices or metadata."""

    selected: List[str] = []
    seen: set[str] = set()

    for line in lines[-_NARRATION_TAIL_LINE_LIMIT:]:
        _append_unique_evidence_line(
            selected=selected,
            seen=seen,
            line=line,
        )

    return selected


def _format_brief_block(
    *,
    title: str,
    lines: List[str],
    limit: int,
    seen: set[str] | None = None,
) -> str:
    """Return one compact evidence block with optional global de-duplication."""

    block_seen = seen if seen is not None else set()
    clean_lines: List[str] = []

    for line in lines:
        clean_line = _plain_detail_fragment(line)
        key = _brief_line_key(clean_line)

        if not clean_line or key in block_seen:
            continue

        if _is_noisy_summary_line(clean_line):
            continue

        block_seen.add(key)
        clean_lines.append(clean_line)

        if len(clean_lines) >= limit:
            break

    if not clean_lines:
        return ""

    block_lines = [
        title,
    ]

    block_lines.extend(
        f"- {line.rstrip('.')}"
        for line in clean_lines
        if line
    )

    return "\n".join(block_lines)


def _limit_brief_text(text: str, *, max_chars: int | None = None) -> str:
    """Bound the structured narration brief without cutting mid-sentence."""

    clean_text = str(text or "").strip()
    char_limit = int(max_chars or _MAX_NARRATION_BRIEF_CHARS)

    if len(clean_text) <= char_limit:
        return clean_text

    clipped = clean_text[:char_limit].rstrip()
    last_period = max(
        clipped.rfind("."),
        clipped.rfind("!"),
        clipped.rfind("?"),
    )

    if last_period >= int(char_limit * 0.75):
        clipped = clipped[:last_period + 1]

    return clipped.strip()


def _is_small_document_narration_candidate(
    *,
    source_text: str,
    lines: List[str],
    truncated: bool,
) -> bool:
    """Return True when clean full text is a better narration packet than a brief."""

    if truncated:
        return False

    if len(source_text) > _SMALL_DOCUMENT_FULL_TEXT_CHARS:
        return False

    if len(lines) > _SMALL_DOCUMENT_LINE_LIMIT:
        return False

    return True


def _build_small_document_narration_text(
    *,
    source_name: str,
    profile_label: str,
    subject_line: str,
    lines: List[str],
) -> str:
    """
    Return a compact full-text packet for small clean documents.

    For short documents, the most accurate narration source is usually the
    cleaned text itself, with only minimal metadata. This avoids expanding a
    one-page document into several repeated evidence blocks.
    """

    clean_lines = _dedupe_preserve_order(lines)
    sections: List[str] = [
        f"Document: {source_name}",
        f"Document type signal: {profile_label}",
    ]

    if subject_line:
        sections.extend([
            "",
            "Central subject evidence",
            f"- {_plain_detail_fragment(subject_line).rstrip('.')}",
        ])

    sections.extend([
        "",
        "Complete clean source text",
        "\n".join(clean_lines),
    ])

    return _limit_brief_text(
        "\n".join(
            section
            for section in sections
            if section
        ),
        max_chars=_SMALL_DOCUMENT_NARRATION_BRIEF_CHARS,
    )


def _build_structured_summary_brief(summary_source: Dict[str, Any]) -> str:
    """
    Build the authorized evidence packet for LLM narration.

    The full extracted source remains available to deterministic DocIntel
    fallback. Short clean documents use compact full text for best accuracy;
    larger documents use selected, de-duplicated evidence blocks so narration
    does not depend on a full raw/OCR dump.
    """

    source_name = _safe_text(summary_source.get("name")) or "Selected document"
    source_text = _safe_text(summary_source.get("text"))

    if not source_text:
        return ""

    lines = _split_summary_lines(source_text)

    if not lines:
        return _limit_brief_text(source_text)

    _profile_key, profile = _detect_document_profile(
        source_name=source_name,
        lines=lines,
    )
    profile_label = str(
        profile.get("label") or "general document"
    )
    subject_line = _select_subject_line(lines)
    key_detail_lines = _select_key_detail_lines(lines)
    truncated = bool(summary_source.get("truncated"))

    if _is_small_document_narration_candidate(
        source_text=source_text,
        lines=lines,
        truncated=truncated,
    ):
        return _build_small_document_narration_text(
            source_name=source_name,
            profile_label=profile_label,
            subject_line=subject_line,
            lines=lines,
        )

    opening_lines = _dedupe_preserve_order(
        lines[:_NARRATION_LEAD_LINE_LIMIT]
    )
    heading_lines = _select_heading_evidence_lines(lines)
    review_lines = _select_review_items(
        lines=lines,
        limit=_NARRATION_REVIEW_LINE_LIMIT,
    )
    scope_lines = _select_natural_lines(
        lines=lines,
        predicate=lambda line: _is_scope_line(line)
        and not bool(_CURRENCY_PATTERN.search(line)),
        limit=_NARRATION_SCOPE_LINE_LIMIT,
    )
    contact_lines = _select_contact_evidence_lines(lines)
    tail_lines = (
        _select_tail_evidence_lines(lines)
        if truncated
        else []
    )

    sections: List[str] = [
        f"Document: {source_name}",
        f"Document type signal: {profile_label}",
    ]
    global_seen: set[str] = set()

    if subject_line:
        subject = _plain_detail_fragment(subject_line).rstrip(".")
        subject_key = _brief_line_key(subject)

        if subject and subject_key:
            global_seen.add(subject_key)
            sections.extend([
                "",
                "Central subject evidence",
                f"- {subject}",
            ])

    evidence_blocks = [
        _format_brief_block(
            title="Opening evidence",
            lines=opening_lines,
            limit=_NARRATION_LEAD_LINE_LIMIT,
            seen=global_seen,
        ),
        _format_brief_block(
            title="Structure evidence",
            lines=heading_lines,
            limit=_NARRATION_HEADING_LINE_LIMIT,
            seen=global_seen,
        ),
        _format_brief_block(
            title="High-signal evidence",
            lines=key_detail_lines,
            limit=_NARRATION_KEY_DETAIL_LIMIT,
            seen=global_seen,
        ),
        _format_brief_block(
            title="Conditions, timing, or review evidence",
            lines=review_lines,
            limit=_NARRATION_REVIEW_LINE_LIMIT,
            seen=global_seen,
        ),
        _format_brief_block(
            title="Scope or requirement evidence",
            lines=scope_lines,
            limit=_NARRATION_SCOPE_LINE_LIMIT,
            seen=global_seen,
        ),
        _format_brief_block(
            title="Contact or publication evidence",
            lines=contact_lines,
            limit=_NARRATION_CONTACT_LINE_LIMIT,
            seen=global_seen,
        ),
        _format_brief_block(
            title="Closing evidence from available text",
            lines=tail_lines,
            limit=_NARRATION_TAIL_LINE_LIMIT,
            seen=global_seen,
        ),
    ]

    sections.extend(
        block
        for block in evidence_blocks
        if block
    )

    return _limit_brief_text(
        "\n\n".join(
            section
            for section in sections
            if section
        )
    )


def _build_narration_source_records(
    summary_sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return summary sources with compact structured text for LLM narration."""

    narration_sources: List[Dict[str, Any]] = []

    for summary_source in summary_sources:
        if not isinstance(summary_source, dict):
            continue

        brief_text = _build_structured_summary_brief(summary_source)

        narration_source = dict(summary_source)
        narration_source["text"] = brief_text
        narration_source["chars"] = len(brief_text)
        narration_source["source_text_chars"] = int(
            summary_source.get("chars") or 0
        )
        narration_source["narration_brief"] = True

        narration_sources.append(narration_source)

    return narration_sources


def _build_summary_answer(
    *,
    deterministic_answer: str,
    summary_sources: List[Dict[str, Any]],
    narration_sources: List[Dict[str, Any]],
    user_task: str,
    request_id: str,
) -> Tuple[str, str]:
    """Return the final single-document response and source label."""

    if not _SUMMARY_NARRATION_ENABLED:
        logger.info(
            "[DOCINTEL][SUMMARY][NARRATION_SKIPPED] "
            "request_id=%s reason=deterministic_presenter_enabled",
            request_id,
        )
        return deterministic_answer, "deterministic"

    if len(narration_sources) != 1:
        logger.info(
            "[DOCINTEL][SUMMARY][NARRATION_SKIPPED] "
            "request_id=%s reason=single_document_required sources=%s",
            request_id,
            len(narration_sources),
        )
        return deterministic_answer, "deterministic"

    return narrate_docintel_summary(
        deterministic_answer=deterministic_answer,
        summary_sources=narration_sources,
        user_request=user_task,
        request_id=request_id,
        logger=logger,
    )


# ============================================================================
# Public Builder
# ============================================================================


def build_generic_single_summary(context: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a source-aware generic DocIntel response.

    The function name remains unchanged for compatibility with the established
    ESL import contract, but the presenter supports explicit summaries,
    key-detail extraction, and comparisons across selected sources.
    """

    decision = context.get("decision") if isinstance(context.get("decision"), dict) else {}
    evidence = context.get("evidence") if isinstance(context.get("evidence"), dict) else {}
    request_action = _get_request_action(decision)
    user_task = _safe_text(decision.get("user_task"))
    documents = _get_documents(decision)
    document_count = len(documents)

    if not user_task:
        user_task = _build_default_user_task(
            request_action=request_action,
            source_count=document_count,
        )

    sources, source_previews = _build_sources_and_previews(
        decision=decision,
        evidence=evidence,
    )
    request_id = (
        _safe_text(decision.get("request_id"))
        or _safe_text(decision.get("decision_id"))
        or "docintel-generic"
    )

    if request_action == WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES:
        summary_sources = _build_summary_source_records(
            documents=documents,
            evidence=evidence,
            decision=decision,
        )
        deterministic_answer = _build_deterministic_summary_answer(
            summary_sources=summary_sources,
        )

        logger.info(
            "[DOCINTEL][SUMMARY][DETERMINISTIC] request_id=%s sources=%s chars=%s",
            request_id,
            len(summary_sources),
            _summary_source_char_count(summary_sources),
        )

        narration_sources = _build_narration_source_records(
            summary_sources
        )

        logger.info(
            "[DOCINTEL][SUMMARY][BRIEF_READY] "
            "request_id=%s sources=%s source_chars=%s brief_chars=%s",
            request_id,
            len(narration_sources),
            _summary_source_char_count(summary_sources),
            _summary_source_char_count(narration_sources),
        )

        answer, answer_source = _build_summary_answer(
            deterministic_answer=deterministic_answer,
            summary_sources=summary_sources,
            narration_sources=narration_sources,
            user_task=user_task,
            request_id=request_id,
        )

        logger.info(
            "[DOCINTEL][SUMMARY][ANSWER_READY] request_id=%s source=%s chars=%s",
            request_id,
            answer_source,
            len(answer),
        )

        used_fallback = answer_source == "deterministic_fallback"

        return {
            "answer": answer,
            "sections": {},
            "posture": "REVIEW",
            "confidence": _deterministic_summary_confidence(summary_sources),
            "answer_source": answer_source,
            "summary_source": answer_source,
            "summary_mode": answer_source,
            "used_fallback": used_fallback,
            "fallback_used": used_fallback,
            "raw_narration_success": answer_source == "raw_document_narrator",
            "narration_brief_chars": _summary_source_char_count(narration_sources),
            "source_text_chars": _summary_source_char_count(summary_sources),
            "llm_error_present": used_fallback,
            "llm_error_signals": (
                "docintel_summary_narration_returned_deterministic_fallback"
                if used_fallback
                else ""
            ),
        }

    answer, _answer_source = generate_workspace_solomon_answer(
        user_task,
        sources,
        context_mode="workspace",
        source_previews=source_previews,
        request_action=request_action,
        logger=logger,
        request_id=request_id,
    )

    return {
        "answer": answer,
        "sections": {},
        "posture": "REVIEW",
        "confidence": "LOW",
    }
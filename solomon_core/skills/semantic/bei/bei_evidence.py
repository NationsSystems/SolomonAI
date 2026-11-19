# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_evidence.py
# DIRECTORY: solomon_core/skills/semantic/bei/
# ---------------------------------------------------------------------------
# BEI Evidence
#
# PURPOSE
#   Extract explicit estimator-grade facts and source evidence from already
#   admitted Bid & Scope Review documents.
#
# CONTRACT
#   This module does not route.
#   This module does not authorize execution.
#   This module does not generate findings or presentation language.
#   This module only builds a structured evidence packet from document text,
#   reconciliation output, and deterministic extractors.
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from solomon_core.logger import get_logger

from .bei_extractors import (
    extract_drawing_references,
    extract_floor_preparation_terms,
    extract_gpr_scanning_terms,
    extract_hidden_condition_terms,
    extract_make_safe_terms,
    extract_mobilization_notes,
    extract_pricing_validity_days,
    extract_salvage_rights,
    extract_schedule_basis,
    extract_scope_summary,
    extract_temporary_protection_terms,
)
from .bei_format_helpers import _normalize_currency_display
from .bei_reconciliation_helpers import (
    _extract_base_bid_hint,
    _first_excerpt_for_doc,
)
from .bei_text_probes import (
    _bulletize_excerpt,
    _extract_below_grade_limit,
    _extract_extra_mobilization_price,
    _extract_mobilization_count,
    _extract_work_week_assumption,
)

logger = get_logger("bei_evidence")

_MAX_SCOPE_LINES = 30
_MAX_EXCLUSION_LINES = 26
_MAX_NOTE_LINES = 10
_MAX_CLARIFICATION_LINES = 10

_OCR_PREFIX_RE = re.compile(
    r"^(?:ao|o&|aÂ«|oÂ«|Â©|Â«|[ao]|&|@|•|-|–|—)\s+",
    re.I,
)

_CURRENCY_RE = re.compile(r"\$\s*[\d,]+(?:\.\d{2})?", re.I)
_BASE_BID_LINE_RE = re.compile(r"\bbase\s+bid\b", re.I)
_UNIT_PRICE_RE = re.compile(r"(/\s*ea\b|\bea\.?\b|\beach\b)", re.I)
_MOBILIZATION_RE = re.compile(r"\bmobilization(?:s)?\b", re.I)


# ---------------------------------------------------------------------------
# Local Text Helpers
# ---------------------------------------------------------------------------

def clean_bei_line(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    cleaned = value.replace("\u00a0", " ").strip()

    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _OCR_PREFIX_RE.sub("", cleaned).strip()

    cleaned = cleaned.replace("Â©", "").replace("Â«", "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def append_unique(items: List[str], value: Any, limit: Optional[int] = None) -> None:
    cleaned = clean_bei_line(value)

    if not cleaned or cleaned in items:
        return

    if limit is not None and len(items) >= limit:
        return

    items.append(cleaned)


def coerce_string_list(value: Any, limit: int) -> List[str]:
    items: List[str] = []

    if isinstance(value, str):
        append_unique(items, value, limit)

    if isinstance(value, list):
        for item in value:
            append_unique(items, item, limit)

    return items


# ---------------------------------------------------------------------------
# Section Evidence Extraction
# ---------------------------------------------------------------------------

def _extract_lines_between(
    text: str,
    start_pattern: str,
    stop_patterns: List[str],
    limit: int,
) -> List[str]:
    lines = text.splitlines() if isinstance(text, str) else []
    output: List[str] = []
    capture = False
    start_re = re.compile(start_pattern, re.I)
    stop_res = [re.compile(pattern, re.I) for pattern in stop_patterns]

    for raw in lines:
        line = clean_bei_line(raw)

        if not line:
            continue

        if not capture and start_re.search(line):
            capture = True
            continue

        if not capture:
            continue

        if any(stop_re.search(line) for stop_re in stop_res):
            break

        append_unique(output, line, limit)

        if len(output) >= limit:
            break

    return output


def _extract_work_scope_lines(text: str) -> List[str]:
    return _extract_lines_between(
        text=text,
        start_pattern=r"^work\s+included\s+in\s+our\s+scope\s*:?\s*$",
        stop_patterns=[
            r"^additional\s+notes\s*:?\s*$",
            r"^clarifications?\s*:?\s*$",
            r"^general\s+exclusions?\s*:?\s*$",
        ],
        limit=_MAX_SCOPE_LINES,
    )


def _extract_additional_notes(text: str) -> List[str]:
    return _extract_lines_between(
        text=text,
        start_pattern=r"^additional\s+notes\s*:?\s*$",
        stop_patterns=[
            r"^please\s+let\s+me\s+know\b",
            r"^thanks\b",
            r"^clarifications?\s*:?\s*$",
        ],
        limit=_MAX_NOTE_LINES,
    )


def _extract_clarifications(text: str) -> List[str]:
    return _extract_lines_between(
        text=text,
        start_pattern=r"^clarifications?\s*:?\s*$",
        stop_patterns=[r"^general\s+exclusions?\s*:?\s*$"],
        limit=_MAX_CLARIFICATION_LINES,
    )


def _extract_general_exclusions(text: str) -> List[str]:
    return _extract_lines_between(
        text=text,
        start_pattern=r"^general\s+exclusions?\s*:?\s*$",
        stop_patterns=[r"^thanks\b", r"^please\s+let\s+me\s+know\b"],
        limit=_MAX_EXCLUSION_LINES,
    )


def _scope_display_items(scope_lines: List[str]) -> List[str]:
    display: List[str] = []
    skip_re = re.compile(
        r"^(drawings\s+dated|addenda|base\s+bid|\d{3}\s+[a-z]|work\s+included)",
        re.I,
    )

    for line in scope_lines:
        cleaned = clean_bei_line(line)

        if not cleaned or skip_re.search(cleaned):
            continue

        append_unique(display, cleaned, 18)

    return display


def _extract_scope_evidence(
    text: str,
    reconciliation: dict | None,
    doc: dict,
) -> List[str]:
    scope_items: List[str] = []

    for item in _extract_work_scope_lines(text):
        append_unique(scope_items, item, _MAX_SCOPE_LINES)

    if len(scope_items) < 8:
        try:
            for item in extract_scope_summary(text) or []:
                append_unique(scope_items, item, _MAX_SCOPE_LINES)
        except Exception as exc:
            logger.warning("[BEI_SCOPE][EXTRACT_FAIL] %s", exc)

    if len(scope_items) < 8:
        scope_excerpt = _first_excerpt_for_doc(reconciliation, doc, "scope")
        if scope_excerpt:
            try:
                for item in _bulletize_excerpt(scope_excerpt) or []:
                    append_unique(scope_items, item, _MAX_SCOPE_LINES)
            except Exception as exc:
                logger.warning("[BEI_SCOPE][EXCERPT_FAIL] %s", exc)

    return _scope_display_items(scope_items)


# ---------------------------------------------------------------------------
# Explicit Commercial Fact Extraction
# ---------------------------------------------------------------------------

def _currency_to_number(value: str) -> Optional[float]:
    cleaned = value.replace("$", "").replace(",", "").strip()

    try:
        return float(cleaned)
    except Exception:
        return None


def _clean_currency(value: str) -> str:
    return value.replace("$ ", "$").strip()


def _currency_from_line(line: str) -> Optional[str]:
    match = _CURRENCY_RE.search(line or "")

    if not match:
        return None

    return _clean_currency(match.group(0))


def _is_unit_or_mobilization_price_context(line: str) -> bool:
    return bool(_UNIT_PRICE_RE.search(line) or _MOBILIZATION_RE.search(line))


def _extract_base_bid_from_text(text: str) -> Optional[str]:
    if not isinstance(text, str) or not text.strip():
        return None

    lines = [clean_bei_line(line) for line in text.splitlines()]
    candidates: List[str] = []

    for idx, line in enumerate(lines):
        if not line or not _BASE_BID_LINE_RE.search(line):
            continue

        for candidate_line in lines[idx: idx + 4]:
            if not candidate_line:
                continue

            currency = _currency_from_line(candidate_line)

            if not currency:
                continue

            if _is_unit_or_mobilization_price_context(candidate_line):
                continue

            append_unique(candidates, currency)

    if not candidates:
        inline_pattern = r"\bbase\s+bid\b[^\n\r$]{0,160}(\$\s*[\d,]+(?:\.\d{2})?)"
        match = re.search(inline_pattern, text, re.I)
        if match:
            return _clean_currency(match.group(1))

    if not candidates:
        return None

    best_value = None
    best_number = 0.0

    for candidate in candidates:
        number = _currency_to_number(candidate)

        if number is not None and number > best_number:
            best_value = candidate
            best_number = number

    return best_value


def _normalize_base_bid(
    value: Any,
    additional_mobilization_price: Optional[str],
) -> Optional[str]:
    if not isinstance(value, str) or not value.strip():
        return None

    normalized = _clean_currency(value)

    if additional_mobilization_price:
        additional_clean = _clean_currency(
            additional_mobilization_price.replace(" each", "")
        )

        if normalized == additional_clean:
            return None

    number = _currency_to_number(normalized)

    if number is None or number < 10000:
        return None

    return normalized


def _resolve_base_bid(
    *,
    text: str,
    doc: dict,
    reconciliation: dict | None,
    additional_mobilization_price: Optional[str],
) -> Optional[str]:
    base_bid_raw = _extract_base_bid_hint(reconciliation, doc)
    base_bid = _normalize_currency_display(base_bid_raw) if base_bid_raw else None
    base_bid = _normalize_base_bid(base_bid, additional_mobilization_price)

    if base_bid:
        return base_bid

    return _normalize_base_bid(
        _extract_base_bid_from_text(text),
        additional_mobilization_price,
    )


# ---------------------------------------------------------------------------
# Public Packet Builder
# ---------------------------------------------------------------------------

def build_evidence_packet(
    *,
    display_name: str,
    text: str,
    doc: dict,
    reconciliation: dict | None,
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    additional_mobilization_price = _extract_extra_mobilization_price(text)
    base_bid = _resolve_base_bid(
        text=text,
        doc=doc,
        reconciliation=reconciliation,
        additional_mobilization_price=additional_mobilization_price,
    )
    gpr_terms = extract_gpr_scanning_terms(text)

    return {
        "document_name": display_name,
        "facts": {
            "base_bid": base_bid,
            "bid_date": evidence.get("bid_date"),
            "drawing_references_present": bool(extract_drawing_references(text)),
            "schedule_basis": extract_schedule_basis(text),
            "work_week": _extract_work_week_assumption(text),
            "pricing_validity_days": extract_pricing_validity_days(text),
            "mobilizations_included": _extract_mobilization_count(text),
            "additional_mobilization_price": additional_mobilization_price,
            "below_grade_limit": _extract_below_grade_limit(text),
            "salvage_rights_present": bool(extract_salvage_rights(text)),
            "mobilization_language_present": bool(extract_mobilization_notes(text)),
        },
        "evidence": {
            "scope": _extract_scope_evidence(text, reconciliation, doc),
            "included": _extract_additional_notes(text),
            "clarifications": _extract_clarifications(text),
            "exclusions": _extract_general_exclusions(text),
            "gpr_included": (gpr_terms or {}).get("included") or [],
            "gpr_excluded": (gpr_terms or {}).get("excluded") or [],
            "make_safe": extract_make_safe_terms(text),
            "hidden_or_hazardous": extract_hidden_condition_terms(text),
            "floor_preparation": extract_floor_preparation_terms(text),
            "temporary_protection": extract_temporary_protection_terms(text),
        },
    }
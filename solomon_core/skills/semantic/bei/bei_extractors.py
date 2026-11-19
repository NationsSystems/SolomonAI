# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_extractors.py
# DIRECTORY: solomon_core/skills/semantic/bei/
# ---------------------------------------------------------------------------

import re
from typing import Any, Dict, List, Optional, Tuple

from .bei_helpers import (
    stable_list,
    looks_like_section_break,
    is_pure_date,
    is_scope_noise,
    is_term_noise,
)

# ---------------------------------------------------------------------------
# Header and value patterns
# ---------------------------------------------------------------------------

_SCOPE_HEADER_RE = re.compile(
    r"^(Work Included in our Scope|Scope of Work)\s*:?\s*$",
    re.I,
)

_BASE_BID_HEADER_RE = re.compile(r"\bbase\s+bid\b", re.I)
_CURRENCY_RE = re.compile(r"\$\s*[\d,]+(?:\.\d{2})?", re.I)

_SCOPE_LINE_HINT_RE = re.compile(
    r"\b(remove existing|demolition|demo)\b",
    re.I,
)

_SCOPE_TEXTURE_HINT_RE = re.compile(
    r"\b(remove|removal|demolition|demo|partition|ceiling|floor|millwork|storefront|hvac|stairs?)\b",
    re.I,
)

_SALVAGE_RE = re.compile(r"\bsalvage\s+rights?\b", re.I)
_SCHEDULE_RE = re.compile(
    r"\b(mon(day)?\s*[-–]\s*fri(day)?|40\s*hour|standard\s+work\s+week)\b",
    re.I,
)
_VALIDITY_RE = re.compile(r"\b(valid|validity)\b.*?\b(\d{1,3})\s*day", re.I)
_MOBILIZATION_RE = re.compile(r"\bmobilization(s)?\b", re.I)
_DRAWING_REF_RE = re.compile(r"\b[A-Z]{1,3}\d{1,2}\.\d{2}\b", re.I)

_EXCLUSION_HEADER_RE = re.compile(r"^general\s+exclusions?\s*:?\s*$", re.I)

_GPR_RE = re.compile(r"\b(gpr|laser\s+scanning|scanning)\b", re.I)
_MAKE_SAFE_RE = re.compile(
    r"\b(made\s+safe|make[-\s]?safe|cut\s*&\s*capped|cut\s+and\s+capped|by\s+others)\b",
    re.I,
)
_HIDDEN_CONDITION_RE = re.compile(
    r"\b(hidden\s+conditions?|concealed|hazardous\s+material|contaminated\s+soils?)\b",
    re.I,
)
_FLOOR_PREP_RE = re.compile(
    r"\b(floor\s+preparation|adhesives?|mastics?|mud\s+beds?|additional\s+layers?\s+of\s+(drywall|gypsum|sheetrock))\b",
    re.I,
)
_TEMP_PROTECTION_RE = re.compile(
    r"\b(temporary\s+protection|temporary\s+weatherproofing)\b",
    re.I,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _clean_evidence_line(line: str) -> str:
    cleaned = str(line or "").strip()
    cleaned = cleaned.lstrip("•-–—ao&@Â©« ").strip()
    return re.sub(r"\s+", " ", cleaned)


def _document_lines(text: str) -> List[str]:
    if not isinstance(text, str) or not text.strip():
        return []

    lines: List[str] = []
    for raw in text.splitlines():
        cleaned = _clean_evidence_line(raw)
        if cleaned:
            lines.append(cleaned)

    return lines


def _exclusion_line_flags(lines: List[str]) -> List[bool]:
    flags: List[bool] = []
    in_exclusions = False

    for line in lines:
        if _EXCLUSION_HEADER_RE.match(line):
            in_exclusions = True
            flags.append(False)
            continue

        flags.append(in_exclusions)

    return flags


def _collect_matching_lines(
    lines: List[str],
    pattern: re.Pattern,
    *,
    exclusion_flags: Optional[List[bool]] = None,
    require_exclusion: Optional[bool] = None,
    limit: int = 8,
) -> List[str]:
    out: List[str] = []

    for idx, line in enumerate(lines):
        if not pattern.search(line):
            continue

        if require_exclusion is not None:
            is_exclusion = bool(exclusion_flags and exclusion_flags[idx])
            if is_exclusion != require_exclusion:
                continue

        out.append(line)

        if len(out) >= limit:
            break

    return stable_list(out)


# ============================================================================
# Generic section extraction
# ============================================================================

def extract_section(text: str, header: str) -> Optional[List[str]]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    out: List[str] = []
    capture = False

    for ln in lines:
        if re.match(rf"^{re.escape(header)}\s*:?\s*$", ln, re.I):
            capture = True
            continue

        if capture:
            stripped = ln.strip()
            if not stripped:
                break
            if looks_like_section_break(stripped):
                break
            out.append(stripped.lstrip("-• ").strip())

    return stable_list(out) if out else None


# ============================================================================
# Base bid extraction
# ============================================================================

def extract_base_bid(text: str, scout: Optional[Dict[str, Any]] = None) -> Optional[str]:
    if not text:
        return None

    lines = text.splitlines()

    for idx, ln in enumerate(lines):
        if not _BASE_BID_HEADER_RE.search(ln):
            continue

        window = lines[idx: idx + 10]

        for w in window:
            if looks_like_section_break(w):
                break

            m = _CURRENCY_RE.search(w)
            if m:
                return m.group(0).strip()

    if scout:
        price_lines = scout.get("price_lines") or []
        totals = scout.get("totals") or []

        if price_lines or totals:
            tail = lines[-50:] if len(lines) > 50 else lines
            best_val: Optional[Tuple[float, str]] = None

            for ln in tail:
                m = _CURRENCY_RE.search(ln)
                if not m:
                    continue

                val = m.group(0)
                try:
                    num = float(re.sub(r"[^\d.]", "", val))
                except Exception:
                    continue

                if not best_val or num > best_val[0]:
                    best_val = (num, val)

            if best_val:
                return best_val[1]

    return None


# ============================================================================
# Scope summary
# ============================================================================

def extract_scope_summary(text: str) -> Optional[List[str]]:
    lines = [ln.rstrip() for ln in text.splitlines()]
    out: List[str] = []
    capture = False
    saw_header = False

    for ln in lines:
        stripped = ln.strip()

        if _SCOPE_HEADER_RE.match(stripped):
            capture = True
            saw_header = True
            continue

        if capture:
            if not stripped:
                if out:
                    break
                continue

            if is_pure_date(stripped):
                continue

            if stripped.upper() == "BASE BID":
                continue

            if looks_like_section_break(stripped):
                break

            if is_scope_noise(stripped):
                continue

            out.append(stripped.lstrip("-• ").strip())

    if saw_header and len(out) < 3:
        fallback: List[str] = []

        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                continue

            if _SCOPE_LINE_HINT_RE.search(stripped):
                if is_scope_noise(stripped):
                    continue
                fallback.append(stripped.lstrip("-• ").strip())

            if len(fallback) >= 12:
                break

        if fallback:
            return stable_list(fallback[:12])

    if len(out) < 2:
        texture_hits: List[str] = []

        for ln in lines:
            stripped = ln.strip()
            if not stripped:
                continue

            if _SCOPE_TEXTURE_HINT_RE.search(stripped):
                if is_scope_noise(stripped) or is_term_noise(stripped):
                    continue

                texture_hits.append(stripped.lstrip("-• ").strip())

            if len(texture_hits) >= 8:
                break

        if texture_hits:
            return stable_list(texture_hits[:8])

    return stable_list(out) if out else None


# ============================================================================
# Commercial qualifier extraction
# ============================================================================

def extract_salvage_rights(text: str) -> bool:
    if not text:
        return False
    return bool(_SALVAGE_RE.search(text))


def extract_schedule_basis(text: str) -> Optional[str]:
    if not text:
        return None

    m = _SCHEDULE_RE.search(text)
    if not m:
        return None

    return m.group(0).strip()


def extract_pricing_validity_days(text: str) -> Optional[int]:
    if not text:
        return None

    m = _VALIDITY_RE.search(text)
    if not m:
        return None

    try:
        return int(m.group(2))
    except Exception:
        return None


def extract_mobilization_notes(text: str) -> bool:
    if not text:
        return False
    return bool(_MOBILIZATION_RE.search(text))


def extract_drawing_references(text: str) -> Optional[List[str]]:
    if not text:
        return None

    refs = _DRAWING_REF_RE.findall(text)
    if not refs:
        return None

    return stable_list(refs[:20])


def extract_gpr_scanning_terms(text: str) -> Dict[str, Any]:
    lines = _document_lines(text)
    if not lines:
        return {"detected": False, "included": [], "excluded": [], "has_conflict": False}

    exclusion_flags = _exclusion_line_flags(lines)
    included = _collect_matching_lines(
        lines,
        _GPR_RE,
        exclusion_flags=exclusion_flags,
        require_exclusion=False,
        limit=5,
    )
    excluded = _collect_matching_lines(
        lines,
        _GPR_RE,
        exclusion_flags=exclusion_flags,
        require_exclusion=True,
        limit=5,
    )

    return {
        "detected": bool(included or excluded),
        "included": included,
        "excluded": excluded,
        "has_conflict": bool(included and excluded),
    }


def extract_make_safe_terms(text: str) -> List[str]:
    lines = _document_lines(text)
    return _collect_matching_lines(lines, _MAKE_SAFE_RE, limit=10)


def extract_hidden_condition_terms(text: str) -> List[str]:
    lines = _document_lines(text)
    flags = _exclusion_line_flags(lines)
    return _collect_matching_lines(
        lines,
        _HIDDEN_CONDITION_RE,
        exclusion_flags=flags,
        require_exclusion=True,
        limit=8,
    )


def extract_floor_preparation_terms(text: str) -> List[str]:
    lines = _document_lines(text)
    flags = _exclusion_line_flags(lines)
    return _collect_matching_lines(
        lines,
        _FLOOR_PREP_RE,
        exclusion_flags=flags,
        require_exclusion=True,
        limit=8,
    )


def extract_temporary_protection_terms(text: str) -> List[str]:
    lines = _document_lines(text)
    return _collect_matching_lines(lines, _TEMP_PROTECTION_RE, limit=8)


# ============================================================================
# Existing utilities
# ============================================================================

def currency_to_float(raw: str) -> Optional[float]:
    try:
        cleaned = re.sub(r"[^\d.\-]", "", raw)
        return float(cleaned)
    except Exception:
        return None


def looks_like_unit_price(line: str) -> bool:
    return bool(re.search(r"\b(each|/ea|ea\.?)\b", line, re.I))


def extract_bid_date(text: str) -> Optional[str]:
    m = re.search(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b", text)
    return m.group(0) if m else None
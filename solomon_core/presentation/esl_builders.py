# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/esl_builders.py
# ---------------------------------------------------------------------------
# ESL Section Builders — Deterministic (Phase-85 Compact Professional)
#
# Purpose:
#   Provide estimator-grade section construction using ONLY admissible data.
#
# Hard Rules:
#   - No LLM
#   - Evidence-bound
#   - Safe degradation
#   - Single-document scope
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Dict, Any, List
import re

from solomon_core.skills.semantic.bei.bei_presentation import bulletize


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_signal_types(decision: Dict[str, Any]) -> set:
    findings = decision.get("findings") or []
    return {f.get("signal_type") for f in findings if f.get("signal_type")}


def _get_base_bid(decision: Dict[str, Any]) -> str | None:
    findings = decision.get("findings") or []

    for f in findings:
        if f.get("signal_type") != "base_bid":
            continue

        for fact in f.get("facts") or []:
            val = fact.get("value")

            if not isinstance(val, str):
                continue

            v = val.strip()

            if "$" in v and any(ch.isdigit() for ch in v):
                return v

    return None


def _get_scope_excerpt(decision: Dict[str, Any]) -> str | None:
    findings = decision.get("findings") or []
    for f in findings:
        if f.get("signal_type") != "scope":
            continue
        for fact in f.get("facts") or []:
            val = fact.get("value")
            if isinstance(val, dict):
                excerpt = val.get("excerpt")
                if excerpt:
                    return excerpt
    return None


def _get_working_text(context: Dict[str, Any]) -> str:
    evidence = context.get("evidence") or {}
    raw = evidence.get("raw_text") or context.get("raw_text") or ""
    if not isinstance(raw, str):
        return ""
    return raw.lower()


# ---------------------------------------------------------------------------
# Dynamic intelligence helpers
# ---------------------------------------------------------------------------

_DEMO_RE = re.compile(r"\b(remove existing|demolition|demo)\b", re.I)
_RENO_RE = re.compile(r"\b(renovation|remodel|tenant improvement)\b", re.I)
_REMOVE_LINE_RE = re.compile(r"\bremove existing\b", re.I)

_SCOPE_ACTION_RE = re.compile(
    r"\b(remove|install|provide|furnish|demo|demolish|replace|construct|patch|cut|cap)\b",
    re.I,
)

_HEADER_NOISE_RE = re.compile(
    r"^(scope\b|job name\b|acknowledge addenda\b|bid includes\b)",
    re.I,
)

_DATE_LINE_RE = re.compile(
    r"^\s*[A-Za-z]+\s+\d{1,2},\s+\d{4}\s*$"
)

_LEADING_ARTIFACT_RE = re.compile(r"^[a-z0-9]{0,3}[\)\.\-\s]+", re.I)
_MULTI_SPACE_RE = re.compile(r"\s+")


def _derive_work_type(scope_excerpt: str | None) -> str | None:
    if not scope_excerpt:
        return None

    if _DEMO_RE.search(scope_excerpt):
        return "Interior demolition scope identified"

    if _RENO_RE.search(scope_excerpt):
        return "Interior renovation scope identified"

    return None


# ---------------------------------------------------------------------------
# NEW — bullet normalization
# ---------------------------------------------------------------------------

def _normalize_bullet_text(line: str) -> str:
    if not line:
        return line

    line = line.strip()
    line = _LEADING_ARTIFACT_RE.sub("", line)
    line = re.sub(r"^[a-z]{1,3}\s+", "", line, flags=re.I)
    line = _MULTI_SPACE_RE.sub(" ", line)

    if line:
        line = line[0].upper() + line[1:]

    return line.strip()


def _clean_scope_line(line: str) -> str:
    line = line.replace("Â«", "")
    line = line.replace("*", "")
    line = re.sub(r"\s+", " ", line)
    line = line.strip()
    line = _normalize_bullet_text(line)
    return line


# ---------------------------------------------------------------------------
# QUALITY GATE
# ---------------------------------------------------------------------------

def _is_estimator_grade_scope(bullets: List[str]) -> bool:
    if not bullets or len(bullets) < 2:
        return False

    verb_hits = 0
    valid_lines = 0

    for b in bullets:
        if not b:
            continue

        lower = b.lower()

        if _HEADER_NOISE_RE.search(lower):
            continue

        if _DATE_LINE_RE.search(b):
            continue

        valid_lines += 1

        if _SCOPE_ACTION_RE.search(lower):
            verb_hits += 1

    if valid_lines < 2:
        return False

    if verb_hits == 0:
        return False

    return True


def _extract_scope_bullets(scope_excerpt: str | None) -> List[str]:
    if not scope_excerpt:
        return []

    lines = scope_excerpt.splitlines()
    cleaned: List[str] = []

    for ln in lines:
        ln = ln.strip()
        if not ln:
            continue

        ln = _clean_scope_line(ln)
        lower = ln.lower()

        if lower.startswith("scope of work"):
            continue
        if lower.startswith("commercial terms"):
            continue

        if len(ln) < 6:
            continue

        cleaned.append(ln)

    return cleaned[:6]


def _harvest_scope_from_raw(context: Dict[str, Any]) -> List[str]:
    text = _get_working_text(context)
    if not text:
        return []

    lines = text.splitlines()
    hits: List[str] = []

    for ln in lines:
        stripped = ln.strip()
        if not stripped:
            continue

        if _REMOVE_LINE_RE.search(stripped):
            cleaned = _clean_scope_line(stripped)
            if len(cleaned) >= 10:
                hits.append(cleaned)

        if len(hits) >= 6:
            break

    if len(hits) < 3:
        return []

    return hits[:6]


# ---------------------------------------------------------------------------
# Executive Section
# ---------------------------------------------------------------------------

def build_executive_section(context: Dict[str, Any]) -> Dict[str, Any]:
    display_name = context.get("display_name") or "Document"
    evidence = context.get("evidence") or {}
    decision = context.get("decision") or {}

    bid_date = evidence.get("bid_date")
    base_bid = _get_base_bid(decision)
    scope_excerpt = _get_scope_excerpt(decision)
    work_type = _derive_work_type(scope_excerpt)

    lines: List[str] = ["Executive Snapshot", ""]

    if base_bid:
        lines.append(f"Base Bid: {base_bid}")
        lines.append("")
    else:
        signal_types = _get_signal_types(decision)
        if "base_bid" in signal_types:
            lines.append("Base Bid: Detected but value not reliably extracted")
            lines.append("")

    lines.append(display_name)
    lines.append("")

    if bid_date:
        lines.append(f"Bid Date: {bid_date}")
        lines.append("")

    if work_type:
        lines.append(f"Work Type: {work_type}")

    return {"text": "\n".join(lines).strip()}


# ---------------------------------------------------------------------------
# Scope Summary
# ---------------------------------------------------------------------------

def build_scope_summary(context: Dict[str, Any]) -> Dict[str, Any]:
    decision = context.get("decision") or {}
    display_name = context.get("display_name") or "Document"

    scope_excerpt = _get_scope_excerpt(decision)
    bullets = _extract_scope_bullets(scope_excerpt)

    if not _is_estimator_grade_scope(bullets):
        bullets = _harvest_scope_from_raw(context)

    lines: List[str] = ["Scope Summary (Estimator View)", ""]

    if bullets:
        lines.append("The proposal covers the following scope elements:")
        lines.append("")
        lines.extend(bulletize(bullets))
        lines.append("")
        lines.append(display_name)
    else:
        lines.append(
            "Scope section detected but detailed line items were not reliably extracted."
        )

    return {"text": "\n".join(lines).strip()}


# ---------------------------------------------------------------------------
# Risk Section
# ---------------------------------------------------------------------------

def build_risk_section(context: Dict[str, Any]) -> Dict[str, Any]:
    decision = context.get("decision") or {}
    display_name = context.get("display_name") or "Document"

    signal_types = _get_signal_types(decision)
    base_bid = _get_base_bid(decision)

    risk_items: List[str] = []

    if "exclusions" in signal_types:
        risk_items.append("Exclusions present — review scope boundaries carefully")

    if "structural" in signal_types:
        risk_items.append("Document structure is non-standard — manual review advised")

    if not base_bid and "base_bid" in signal_types:
        risk_items.append("Base bid referenced but value not reliably extracted")

    lines: List[str] = ["Risk Review", ""]

    if risk_items:
        lines.extend(bulletize(risk_items))
        lines.append("")
        lines.append(display_name)
    else:
        lines.append("No material risk signals detected in the submitted document.")

    return {"text": "\n".join(lines).strip()}


# ---------------------------------------------------------------------------
# ✅ NEW — Exclusion Posture (stub, deterministic)
# ---------------------------------------------------------------------------

def build_exclusion_posture(context: Dict[str, Any]) -> Dict[str, Any]:
    decision = context.get("decision") or {}
    display_name = context.get("display_name") or "Document"

    signal_types = _get_signal_types(decision)

    lines: List[str] = ["Exclusion Posture", ""]

    if "exclusions" in signal_types:
        lines.append("Exclusions are present in the proposal and should be reviewed.")
        lines.append("")
        lines.append(display_name)
    else:
        lines.append("No explicit exclusions were detected in the submitted document.")

    return {"text": "\n".join(lines).strip()}


# ---------------------------------------------------------------------------
# ✅ NEW — Commercial Terms (stub)
# ---------------------------------------------------------------------------

def build_commercial_terms(context: Dict[str, Any]) -> Dict[str, Any]:
    evidence = context.get("evidence") or {}
    display_name = context.get("display_name") or "Document"

    bid_date = evidence.get("bid_date")

    lines: List[str] = ["Commercial Terms", ""]

    if bid_date:
        lines.append(f"Bid dated: {bid_date}")
        lines.append("")
        lines.append(display_name)
    else:
        lines.append("No commercial timing signals were reliably extracted.")

    return {"text": "\n".join(lines).strip()}


# ---------------------------------------------------------------------------
# ✅ NEW — Bottom Line (stub)
# ---------------------------------------------------------------------------

def synthesize_bottom_line(context: Dict[str, Any]) -> Dict[str, Any]:
    decision = context.get("decision") or {}

    signal_types = _get_signal_types(decision)

    posture = "REVIEW"
    confidence = "LOW"

    if "exclusions" in signal_types:
        posture = "CAUTION"
        confidence = "MEDIUM"

    text = "Bottom Line\n\nEstimator review recommended."

    return {
        "text": text,
        "posture": posture,
        "confidence": confidence,
    }
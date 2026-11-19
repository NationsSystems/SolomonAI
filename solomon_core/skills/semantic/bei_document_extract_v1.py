# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei_document_extract_v1.py
# DIRECTORY: solomon_core/skills/semantic/
# ---------------------------------------------------------------------------
# BEI Document Extract v1
#
# PURPOSE
#   Compatibility wrapper for the restored deterministic BEI execution path.
#
# CONTRACT
#   Deterministic evidence extraction is delegated to BEI evidence modules.
#   Admission behavior is delegated to BEI admission modules.
#   Multi-document comparison is delegated to the BEI compare module.
#   This wrapper preserves the legacy public entrypoint expected by V3.
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from html import escape
from typing import Any, Dict, List, Optional

from solomon_core.docintel.validation.evidence_validator import validate
from solomon_core.logger import get_logger

from .bei.bei_admission import (
    build_requires_action_packet,
    has_reviewable_bei_evidence,
)
from .bei.bei_evidence import build_evidence_packet
from .bei.bei_extractors import extract_bid_date
from .bei.bei_helpers import resolve_doc_name, safe_text, select_document_set
from .bei.bei_presentation import render_structured_block
from .bei.bei_text_probes import _p_block
from .bei_multi_compare import build_multi_compare as build_bei_multi_compare

logger = get_logger("skill_bei_document_extract_v1")

_MAX_SCOPE_ITEMS = 8
_MAX_REVIEW_ITEMS = 8
_MAX_EXCLUSION_ITEMS = 9
_MAX_COMMERCIAL_ITEMS = 8

_OCR_PREFIX_RE = re.compile(
    r"^(?:ao|o&|aÂ«|oÂ«|Â©|Â«|[ao]|&|@|•|-|–|—)\s+",
    re.I,
)

_ARTIFACT_ONLY_RE = re.compile(r"^[^\w$]+$")

_TEXT_REPAIRS = (
    (re.compile(r"\bu\s+nless\b", re.I), "unless"),
    (re.compile(r"\bn\s+oted\b", re.I), "noted"),
    (re.compile(r"\bu\s+no\b", re.I), "UNO"),
    (re.compile(r"\bmobili\s+zations\b", re.I), "mobilizations"),
    (re.compile(r"\bde\s+emed\b", re.I), "deemed"),
    (re.compile(r"\bpro\s+posal\b", re.I), "proposal"),
    (re.compile(r"\babov\s+e\b", re.I), "above"),
    (re.compile(r"\blimi\s+ts\b", re.I), "limits"),
    (re.compile(r"\bceil\s+ing\b", re.I), "ceiling"),
    (re.compile(r"\bad h?esives\b", re.I), "adhesives"),
    (re.compile(r"\bshee\s+trock\b", re.I), "sheetrock"),
)


# ---------------------------------------------------------------------------
# Local Presentation Helpers
# ---------------------------------------------------------------------------

def _clean_line(value: Any) -> str:
    if not isinstance(value, str):
        return ""

    cleaned = value.replace("\u00a0", " ").strip()

    previous = None
    while previous != cleaned:
        previous = cleaned
        cleaned = _OCR_PREFIX_RE.sub("", cleaned).strip()

    cleaned = cleaned.replace("Â©", "").replace("Â«", "").strip()

    for pattern, replacement in _TEXT_REPAIRS:
        cleaned = pattern.sub(replacement, cleaned)

    cleaned = re.sub(r"\(\s+(\d+)\s+\)", r"(\1)", cleaned)
    cleaned = re.sub(r"\s+([,.;:])", r"\1", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    if not cleaned or _ARTIFACT_ONLY_RE.fullmatch(cleaned):
        return ""

    return cleaned


def _append_unique(
    items: List[str],
    value: Any,
    limit: Optional[int] = None,
) -> None:
    cleaned = _clean_line(value)

    if not cleaned or cleaned in items:
        return

    if limit is not None and len(items) >= limit:
        return

    items.append(cleaned)


def _is_scope_noise(line: str) -> bool:
    low = line.lower().strip()

    if re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", low):
        return True
    if re.fullmatch(r"\d+", low):
        return True
    if low.startswith("bid #"):
        return True
    if low.startswith("drawings dated"):
        return True
    if low.startswith("addenda"):
        return True

    return False


def _is_exclusion_noise(line: str) -> bool:
    low = line.lower().strip()

    if low.startswith("drawings dated"):
        return True
    if low.startswith("addenda"):
        return True
    if re.match(r"^\d{2,4}\s+[a-z]{1,4}\d", low):
        return True

    return False


def _coerce_string_list(
    value: Any,
    limit: int,
    *,
    reject_scope_noise: bool = False,
    reject_exclusion_noise: bool = False,
) -> List[str]:
    items: List[str] = []
    source = value if isinstance(value, list) else [value]

    for item in source:
        cleaned = _clean_line(item)

        if not cleaned:
            continue
        if reject_scope_noise and _is_scope_noise(cleaned):
            continue
        if reject_exclusion_noise and _is_exclusion_noise(cleaned):
            continue

        _append_unique(items, cleaned, limit)

    return items


def _format_items(items: List[str], limit: int) -> str:
    cleaned = _coerce_string_list(items, limit)

    if not cleaned:
        return ""

    if len(cleaned) == 1:
        return cleaned[0]

    if len(cleaned) == 2:
        return f"{cleaned[0]} and {cleaned[1]}"

    return f"{', '.join(cleaned[:-1])}, and {cleaned[-1]}"


def _has_any_text(value: Any) -> bool:
    return bool(_coerce_string_list(value, 1))


# ---------------------------------------------------------------------------
# Deterministic Estimator Derivations
# ---------------------------------------------------------------------------

def _scope_categories(scope_items: List[str]) -> List[str]:
    categories: List[str] = []

    checks = [
        ("Flooring removals", ("floor", "vct", "carpet", "ceramic")),
        ("Partition and wall removals", ("partition", "drywall", "cmu")),
        ("Door, frame, and hardware removal", ("door", "frame", "hardware")),
        ("Plumbing fixture removals", ("plumbing fixture", "fixtures")),
        ("Millwork removal", ("millwork",)),
        ("Storefront removal", ("storefront",)),
        ("Steel stair removal", ("steel stair", "stairs")),
        ("Slab or SOG removal", ("sog", "slab")),
        ("Ceiling system removals", ("ceiling", "act", "gyp")),
        ("Mechanical or HVAC removals", ("hvac", "mechanical")),
    ]

    joined = " ".join(scope_items).lower()

    for label, needles in checks:
        if any(needle in joined for needle in needles):
            _append_unique(categories, label, _MAX_SCOPE_ITEMS)

    if not categories:
        for item in scope_items:
            _append_unique(categories, item, _MAX_SCOPE_ITEMS)

    return categories


def _work_type(scope_items: List[str]) -> str:
    joined = " ".join(scope_items).lower()

    if "demo" in joined or "remove existing" in joined:
        return "Selective demolition / removal scope"

    if scope_items:
        return "Construction scope evidence detected"

    return "Work type not determined from extracted scope evidence"


def _commercial_posture(packet: Dict[str, Any]) -> str:
    facts = packet.get("facts") or {}
    evidence = packet.get("evidence") or {}
    exclusion_count = len(_coerce_string_list(
        evidence.get("exclusions"),
        50,
        reject_exclusion_noise=True,
    ))

    if exclusion_count >= 8 and facts.get("salvage_rights_present"):
        return "Extensive exclusions and contractor-retained salvage rights present"

    if exclusion_count >= 8:
        return "Extensive exclusion posture detected"

    if facts.get("salvage_rights_present") or _has_any_text(evidence.get("clarifications")):
        return "Commercial qualifications present"

    return "Limited commercial qualification evidence detected"


# ---------------------------------------------------------------------------
# Report Composition
# ---------------------------------------------------------------------------

def _compose_executive_snapshot(packet: Dict[str, Any]) -> List[str]:
    facts = packet.get("facts") or {}
    evidence = packet.get("evidence") or {}
    scope_items = _coerce_string_list(
        evidence.get("scope"),
        _MAX_SCOPE_ITEMS,
        reject_scope_noise=True,
    )

    items: List[str] = []

    if facts.get("base_bid"):
        _append_unique(items, f"Base Bid: {facts['base_bid']}")
    if facts.get("bid_date"):
        _append_unique(items, f"Bid Date: {facts['bid_date']}")

    _append_unique(items, f"Work Type: {_work_type(scope_items)}")
    _append_unique(items, f"Notable Posture: {_commercial_posture(packet)}")

    return items


def _compose_scope_summary(packet: Dict[str, Any]) -> Dict[str, List[str]]:
    facts = packet.get("facts") or {}
    evidence = packet.get("evidence") or {}
    scope_items = _coerce_string_list(
        evidence.get("scope"),
        _MAX_SCOPE_ITEMS,
        reject_scope_noise=True,
    )
    categories = _scope_categories(scope_items)
    paragraphs: List[str] = []

    if categories:
        paragraphs.append(
            "The extracted scope evidence indicates a structured demolition "
            "proposal covering multiple removal categories. The scope should be "
            "leveled against the drawing set, bid form, and any addenda before "
            "award reliance."
        )
    else:
        paragraphs.append(
            "The current extraction path found limited scope detail. A complete "
            "bid package may be needed for stronger estimator-grade review."
        )

    if facts.get("drawing_references_present"):
        paragraphs.append(
            "Drawing references were detected, so the listed scope should be "
            "cross-checked against the referenced sheets rather than reviewed "
            "from the proposal language alone."
        )

    return {
        "paragraphs": paragraphs,
        "items": categories,
    }


def _compose_included_items(packet: Dict[str, Any]) -> List[str]:
    facts = packet.get("facts") or {}
    evidence = packet.get("evidence") or {}
    items = _coerce_string_list(evidence.get("included"), 5)

    if facts.get("mobilizations_included"):
        _append_unique(
            items,
            f"{facts['mobilizations_included']} mobilization(s) included",
            6,
        )

    return items


def _compose_risk_items(packet: Dict[str, Any]) -> List[str]:
    facts = packet.get("facts") or {}
    evidence = packet.get("evidence") or {}
    findings: List[str] = []

    exclusions = _coerce_string_list(
        evidence.get("exclusions"),
        50,
        reject_exclusion_noise=True,
    )

    if len(exclusions) >= 8:
        _append_unique(
            findings,
            "Qualification density is high: the proposal carries a broad "
            "exclusion set that may leave material carry scope with the owner "
            "or general contractor.",
            _MAX_REVIEW_ITEMS,
        )

    if facts.get("salvage_rights_present"):
        _append_unique(
            findings,
            "Contractor-retained salvage rights are present and should be "
            "checked against owner requirements.",
            _MAX_REVIEW_ITEMS,
        )

    if facts.get("below_grade_limit"):
        _append_unique(
            findings,
            f"Below-grade removal is limited to {facts['below_grade_limit']}, "
            "which may create downstream scope exposure if deeper removal is required.",
            _MAX_REVIEW_ITEMS,
        )

    if facts.get("additional_mobilization_price"):
        _append_unique(
            findings,
            "Additional mobilizations are separately priced at "
            f"{facts['additional_mobilization_price']}, making schedule "
            "assumptions important during leveling.",
            _MAX_REVIEW_ITEMS,
        )

    if _has_any_text(evidence.get("make_safe")):
        _append_unique(
            findings,
            "Utility or MEP make-safe responsibility appears limited or qualified "
            "and should be reconciled against the prime scope.",
            _MAX_REVIEW_ITEMS,
        )

    if _has_any_text(evidence.get("hidden_or_hazardous")):
        _append_unique(
            findings,
            "Hidden conditions or hazardous material language is present and may "
            "represent cost exposure outside the base bid.",
            _MAX_REVIEW_ITEMS,
        )

    if _has_any_text(evidence.get("temporary_protection")):
        _append_unique(
            findings,
            "Temporary protection language is present and should be reviewed for "
            "responsibility ambiguity.",
            _MAX_REVIEW_ITEMS,
        )

    if not findings:
        _append_unique(
            findings,
            "No major exclusion, mobilization, protection, or responsibility "
            "signals were extracted by the current deterministic review path.",
            _MAX_REVIEW_ITEMS,
        )

    return findings


def _compose_exclusion_posture(packet: Dict[str, Any]) -> List[str]:
    evidence = packet.get("evidence") or {}
    return _coerce_string_list(
        evidence.get("exclusions"),
        _MAX_EXCLUSION_ITEMS,
        reject_exclusion_noise=True,
    )


def _compose_commercial_terms(packet: Dict[str, Any]) -> List[str]:
    facts = packet.get("facts") or {}
    evidence = packet.get("evidence") or {}
    items: List[str] = []

    schedule = facts.get("schedule_basis") or facts.get("work_week")
    if schedule:
        _append_unique(items, f"Schedule basis: {schedule}", _MAX_COMMERCIAL_ITEMS)

    if facts.get("pricing_validity_days"):
        _append_unique(
            items,
            f"Pricing valid for {facts['pricing_validity_days']} days",
            _MAX_COMMERCIAL_ITEMS,
        )

    if facts.get("mobilizations_included"):
        _append_unique(
            items,
            f"Mobilizations included: {facts['mobilizations_included']}",
            _MAX_COMMERCIAL_ITEMS,
        )

    if facts.get("additional_mobilization_price"):
        _append_unique(
            items,
            f"Additional mobilizations: {facts['additional_mobilization_price']}",
            _MAX_COMMERCIAL_ITEMS,
        )

    if facts.get("below_grade_limit"):
        _append_unique(
            items,
            f"Below-grade removal limit: {facts['below_grade_limit']}",
            _MAX_COMMERCIAL_ITEMS,
        )

    if facts.get("salvage_rights_present"):
        _append_unique(
            items,
            "Salvage rights retained by contractor unless otherwise noted",
            _MAX_COMMERCIAL_ITEMS,
        )

    temporary = _coerce_string_list(evidence.get("temporary_protection"), 1)
    if temporary:
        _append_unique(
            items,
            f"Temporary protection qualifier: {temporary[0]}",
            _MAX_COMMERCIAL_ITEMS,
        )

    return items


def _compose_bottom_line(packet: Dict[str, Any]) -> str:
    evidence = packet.get("evidence") or {}
    facts = packet.get("facts") or {}
    scope = _coerce_string_list(
        evidence.get("scope"),
        _MAX_SCOPE_ITEMS,
        reject_scope_noise=True,
    )
    exclusions = _coerce_string_list(
        evidence.get("exclusions"),
        50,
        reject_exclusion_noise=True,
    )

    if scope and len(exclusions) >= 8:
        return (
            "This is a qualified demolition proposal with meaningful scope "
            "detail and a broad exclusion posture. The price should not be "
            "relied on as award-ready until exclusions, mobilization assumptions, "
            "temporary protection, utility or MEP responsibility, and below-grade "
            "limits are reconciled against the required project scope."
        )

    if scope and (
        exclusions
        or facts.get("salvage_rights_present")
        or facts.get("mobilization_language_present")
    ):
        return (
            "The proposal contains usable scope evidence and commercial "
            "qualification evidence. It should be used for bid leveling only "
            "after the listed qualifications and responsibility limits are "
            "reconciled against the required scope."
        )

    if scope:
        return (
            "The proposal contains extractable scope evidence. Additional review "
            "should confirm whether exclusions, alternates, assumptions, and "
            "responsibility limits are present elsewhere in the bid package."
        )

    return (
        "The current deterministic review found limited estimator-grade scope "
        "evidence. Upload the complete bid, proposal, scope, exclusions, "
        "alternates, and pricing documents for a stronger Bid & Scope Review."
    )


def _build_deterministic_report(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "executive_snapshot": _compose_executive_snapshot(packet),
        "scope_summary": _compose_scope_summary(packet),
        "included_items": _compose_included_items(packet),
        "risk_items": _compose_risk_items(packet),
        "exclusion_posture": _compose_exclusion_posture(packet),
        "commercial_terms": _compose_commercial_terms(packet),
        "bottom_line": _compose_bottom_line(packet),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _render_section(lines: List[str], title: str, items: List[str]) -> None:
    if not items:
        return

    lines.append(f"<b>{escape(title, quote=False)}</b>")
    lines.extend(render_structured_block(items))


def _render_report(
    display_name: str,
    packet: Dict[str, Any],
    report: Dict[str, Any],
) -> str:
    del packet

    lines: List[str] = ['<div class="bei-single-summary">']
    safe_name = escape(display_name, quote=False)
    scope_summary = report.get("scope_summary") or {}

    lines.append(f"<b>Bid Summary — {safe_name}</b>")

    _render_section(lines, "Executive Snapshot", report.get("executive_snapshot") or [])

    if scope_summary.get("paragraphs") or scope_summary.get("items"):
        lines.append("<b>Scope Summary (Estimator View)</b>")

        for paragraph in scope_summary.get("paragraphs") or []:
            lines.extend(_p_block(paragraph))

        lines.extend(render_structured_block(scope_summary.get("items") or []))

    _render_section(
        lines,
        "Included Operational Items",
        report.get("included_items") or [],
    )
    _render_section(
        lines,
        "Immediate Risk Signals",
        report.get("risk_items") or [],
    )
    _render_section(
        lines,
        "Exclusion Posture",
        report.get("exclusion_posture") or [],
    )
    _render_section(
        lines,
        "Commercial Terms",
        report.get("commercial_terms") or [],
    )

    if report.get("bottom_line"):
        lines.append("<b>Bottom Line</b>")
        lines.extend(_p_block(report["bottom_line"]))

    lines.append("</div>")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Single Document
# ---------------------------------------------------------------------------

def _build_packet(
    doc: dict,
    evidence: dict,
    reconciliation: dict | None,
) -> Dict[str, Any]:
    display_name = resolve_doc_name(doc) or "Document"
    text = safe_text(doc) or ""

    return build_evidence_packet(
        display_name=display_name,
        text=text,
        doc=doc,
        reconciliation=reconciliation,
        evidence=evidence,
    )


def _build_answer(packet: Dict[str, Any]) -> str:
    display_name = packet.get("document_name") or "Document"
    report = _build_deterministic_report(packet)

    logger.info("[BEI_PRESENTATION][DETERMINISTIC_REPORT_RENDERED]")
    return _render_report(display_name, packet, report)


def _public_evidence(packet: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "facts": packet.get("facts") or {},
        "source_evidence": packet.get("evidence") or {},
    }


# ---------------------------------------------------------------------------
# Public Execution
# ---------------------------------------------------------------------------

def execute(arguments: dict) -> dict:
    docs = select_document_set(arguments)

    if not docs:
        return {
            "ok": False,
            "packet_type": "docintel",
            "payload": {"answer": "Bid extraction requires a document set."},
            "verdict": "REQUIRES_ACTION",
        }

    reconciliation = arguments.get("reconciliation")
    derivations = arguments.get("presentation_derivations")

    if len(docs) >= 2:
        answer = build_bei_multi_compare(
            docs=docs,
            reconciliation=reconciliation,
            derivations=derivations,
        )
        return {
            "ok": True,
            "packet_type": "docintel",
            "payload": {"answer": answer},
            "verdict": "AUTHORIZED",
        }

    doc = docs[0]
    text = safe_text(doc) or ""
    display_name = resolve_doc_name(doc) or "Document"
    evidence: Dict[str, Any] = {"bid_date": extract_bid_date(text)}

    validation = validate(evidence)
    if not validation.get("passed"):
        logger.error("[BEI][VALIDATION_BLOCK] violations=%s", validation.get("violations"))
        return {
            "ok": False,
            "packet_type": "docintel",
            "payload": {"answer": "Evidence validation failed."},
            "verdict": "REQUIRES_ACTION",
        }

    packet = _build_packet(doc, evidence, reconciliation)

    if not has_reviewable_bei_evidence(packet):
        logger.info("[BEI_ADMISSION][REQUIRES_ACTION] document=%s", display_name)
        return build_requires_action_packet(display_name)

    answer = _build_answer(packet)

    return {
        "ok": True,
        "packet_type": "docintel",
        "payload": {"answer": answer, "evidence": _public_evidence(packet)},
        "verdict": "AUTHORIZED",
    }


def run_bei_document_extract_v1(reasoning_payload: dict, raw_text: str):
    del raw_text

    documents = (reasoning_payload.get("inputs", {}) or {}).get("documents") or []
    execution_context = reasoning_payload.get("execution_context") or {}
    reconciliation = reasoning_payload.get("reconciliation")
    derivations = reasoning_payload.get("presentation_derivations")

    return execute(
        {
            "documents": documents,
            "execution_context": execution_context,
            "reconciliation": reconciliation,
            "presentation_derivations": derivations,
        }
    )
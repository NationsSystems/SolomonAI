# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei_multi_compare.py
# DIRECTORY: solomon_core/skills/semantic/
# ---------------------------------------------------------------------------
# BEI Multi Compare
#
# PURPOSE
#   Render deterministic multi-document Bid & Scope Review comparison output.
#
# CONTRACT
#   This module does not route.
#   This module does not authorize execution.
#   Deterministic compare facts remain authoritative.
#   Default rendering must remain fast and usable without LLM wording.
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from html import escape
from typing import Any, Dict, List, Optional

from solomon_core.logger import get_logger

from .bei.bei_format_helpers import _normalize_currency_display
from .bei.bei_helpers import resolve_doc_name
from .bei.bei_reconciliation_helpers import (
    _count_signal_for_doc,
    _extract_base_bid_hint,
    _presentation_derivations,
)

logger = get_logger("skill_bei_multi_compare")

_MAX_PREVIEW_ITEMS = 5
_MAX_SECTION_ITEMS = 14

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
    (re.compile(r"\bshee\s+trock\b", re.I), "sheetrock"),
    (re.compile(r"\bf\s+reon\b", re.I), "freon"),
    (re.compile(r"\bo\s+r\s+capping\b", re.I), "or capping"),
    (re.compile(r"\btem\s+porary\b", re.I), "temporary"),
    (re.compile(r"\bad h?esives\b", re.I), "adhesives"),
)


# ---------------------------------------------------------------------------
# Basic Helpers
# ---------------------------------------------------------------------------

def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_documents(docs: Any) -> List[dict]:
    return [doc for doc in docs if isinstance(doc, dict)] if isinstance(docs, list) else []


def _safe_text(value: Any) -> str:
    return value if isinstance(value, str) else ""


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


def _append_unique(items: List[str], value: Any, limit: Optional[int] = None) -> None:
    cleaned = _clean_line(value)

    if not cleaned or cleaned in items:
        return

    if limit is not None and len(items) >= limit:
        return

    items.append(cleaned)


def _format_preview(items: List[str], limit: int = _MAX_PREVIEW_ITEMS) -> str:
    cleaned: List[str] = []

    for item in items:
        _append_unique(cleaned, item, limit)

    return "; ".join(cleaned) if cleaned else "Not extracted"


def _has_text_items(value: Any) -> bool:
    return isinstance(value, list) and any(_clean_line(item) for item in value)


def _contains(text: str, *needles: str) -> bool:
    low = text.lower()
    return any(needle.lower() in low for needle in needles)


def _display_name(source_name: str) -> str:
    clean = source_name.replace(".pdf", "").strip()
    upper = clean.upper()

    if "TDC" in upper:
        return "TDC"

    if "ROBLES" in upper:
        return "Robles1"

    if "R1" in upper:
        return "Robles1"

    clean = re.sub(r"^BID\s*\d+\s*[-–]\s*", "", clean, flags=re.I).strip()
    return clean or source_name


def _html_list(items: List[str]) -> List[str]:
    cleaned = [_clean_line(item) for item in items if _clean_line(item)]

    if not cleaned:
        return []

    body = "".join(f"<li>{escape(item, quote=False)}</li>" for item in cleaned)
    return [f'<ul class="bei-list">{body}</ul>']


def _paragraph(text: str) -> str:
    return f"<p>{escape(_clean_line(text), quote=False)}</p>"


# ---------------------------------------------------------------------------
# Price Helpers
# ---------------------------------------------------------------------------

def _currency_to_float(value: Any) -> Optional[float]:
    if not isinstance(value, str):
        return None

    cleaned = value.replace("$", "").replace(",", "").strip()

    try:
        return float(cleaned)
    except Exception:
        return None


def _format_currency(value: float) -> str:
    return f"${value:,.2f}"


def _normalize_bid_value(value: Any) -> Optional[str]:
    if value is None:
        return None

    try:
        normalized = _normalize_currency_display(value)
    except Exception:
        normalized = str(value or "").strip()

    if not isinstance(normalized, str) or not normalized.strip():
        return None

    return normalized.replace("$ ", "$").strip()


# ---------------------------------------------------------------------------
# Section / Signal Extraction
# ---------------------------------------------------------------------------

def _extract_lines_between(
    text: str,
    start_pattern: str,
    stop_patterns: List[str],
    limit: int = _MAX_SECTION_ITEMS,
) -> List[str]:
    lines = text.splitlines() if isinstance(text, str) else []
    output: List[str] = []
    capture = False
    start_re = re.compile(start_pattern, re.I)
    stop_res = [re.compile(pattern, re.I) for pattern in stop_patterns]

    for raw in lines:
        line = _clean_line(raw)

        if not line:
            continue

        if not capture and start_re.search(line):
            capture = True
            continue

        if not capture:
            continue

        if any(stop_re.search(line) for stop_re in stop_res):
            break

        _append_unique(output, line, limit)

    return output


def _extract_exclusions(text: str) -> List[str]:
    return _extract_lines_between(
        text=text,
        start_pattern=r"^(general\s+)?exclusions?\s*:?\s*$",
        stop_patterns=[
            r"^clarifications?\s*:?\s*$",
            r"^additional\s+notes\s*:?\s*$",
            r"^thanks\b",
            r"^please\s+let\s+me\s+know\b",
            r"^accepted\b",
            r"^signature\b",
        ],
    )


def _extract_clarifications(text: str) -> List[str]:
    return _extract_lines_between(
        text=text,
        start_pattern=r"^clarifications?\s*:?\s*$",
        stop_patterns=[
            r"^(general\s+)?exclusions?\s*:?\s*$",
            r"^additional\s+notes\s*:?\s*$",
        ],
    )


def _extract_additional_notes(text: str) -> List[str]:
    return _extract_lines_between(
        text=text,
        start_pattern=r"^additional\s+notes\s*:?\s*$",
        stop_patterns=[
            r"^clarifications?\s*:?\s*$",
            r"^(general\s+)?exclusions?\s*:?\s*$",
            r"^thanks\b",
            r"^please\s+let\s+me\s+know\b",
        ],
    )


def _extract_mobilization(text: str) -> Dict[str, Any]:
    low = text.lower()
    count = None
    price = None

    patterns = [
        r"\(\s*(\d+)\s*\)\s+mobilizations?\s+included",
        r"\b(\d+)\s+mobilizations?\s+included",
        r"based\s+on\s+\(?\s*(\d+)\s*\)?\s+mobilizations?",
        r"\b(\d+)\s+mobilizations?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, low, re.I)
        if match:
            count = int(match.group(1))
            break

    price_match = re.search(r"\$[\s]*([\d,]+(?:\.\d{2})?)\s*/?\s*(?:ea|each)", text, re.I)
    if price_match:
        price = _normalize_bid_value(f"${price_match.group(1)} each")

    return {"count": count, "price": price}


def _extract_validity(text: str) -> Optional[str]:
    match = re.search(r"valid\s+for\s+(\d+)\s+days", text, re.I)
    return f"{match.group(1)} days" if match else None


def _extract_schedule(text: str) -> Optional[str]:
    if re.search(r"monday\s*[-–]\s*friday", text, re.I):
        return "Monday - Friday"
    if re.search(r"\bweekday\b|\bweekdays\b", text, re.I):
        return "Weekday work"
    return None


def _extract_below_grade(text: str) -> Optional[str]:
    match = re.search(r"(\d+)\s*['’]?\s+below\s+grade", text, re.I)
    return f"{match.group(1)}' below grade" if match else None


def _sheet_reference_count(text: str) -> int:
    patterns = [
        r"\bA[D]?\d+\.\d+[A-Z]?\b",
        r"\bM[D]?\d+\.\d+[A-Z]?\b",
        r"\bAD\d+\.\d+[A-Z]?\b",
        r"\bMD\d+\.\d+[A-Z]?\b",
    ]
    found = set()

    for pattern in patterns:
        for match in re.findall(pattern, text, re.I):
            found.add(match.upper())

    return len(found)


def _scope_strengths(text: str) -> List[str]:
    strengths: List[str] = []

    checks = [
        ("flooring removals", ("vct", "carpet", "ceramic", "flooring")),
        ("partition and wall removals", ("partition", "drywall", "cmu", "wall")),
        ("door, frame, and hardware removal", ("doors", "frames", "hardware")),
        ("millwork and storefront removal", ("millwork", "storefront")),
        ("structural or slab-related demolition", ("sog", "slab", "concrete")),
        ("ceiling system removal", ("ceiling", "act", "gyp")),
        ("HVAC or mechanical removal", ("hvac", "mechanical", "rtu")),
        ("exterior or roofing demolition", ("roof", "canopy", "exterior")),
        ("debris haul-off or disposal", ("haul off", "haul-off", "disposal", "landfill")),
    ]

    for label, needles in checks:
        if _contains(text, *needles):
            _append_unique(strengths, label, 7)

    return strengths


def _scope_posture(text: str, strengths: List[str]) -> str:
    sheet_count = _sheet_reference_count(text)

    if sheet_count >= 4:
        return "drawing-referenced / sheet-indexed scope"

    if _contains(text, "including but not limited", "scope of work", "demolition of"):
        return "broader narrative scope"

    if strengths:
        return "category-supported scope"

    return "limited extracted scope detail"


# ---------------------------------------------------------------------------
# Document Records
# ---------------------------------------------------------------------------

def _doc_label(doc: dict, index: int) -> str:
    return resolve_doc_name(doc) or f"Document {index}"


def _doc_bid_record(
    *,
    doc: dict,
    index: int,
    reconciliation: Optional[dict],
) -> Dict[str, Any]:
    text = _safe_text(doc.get("text"))
    source_name = _doc_label(doc, index)
    display = _display_name(source_name)
    bid = _normalize_bid_value(_extract_base_bid_hint(reconciliation, doc))
    amount = _currency_to_float(bid) if bid else None
    exclusions = _extract_exclusions(text)
    clarifications = _extract_clarifications(text)
    notes = _extract_additional_notes(text)
    mobilization = _extract_mobilization(text)
    strengths = _scope_strengths(text)

    reconciled_exclusion_count = _count_signal_for_doc(
        reconciliation,
        doc,
        "exclusions",
    )

    return {
        "name": display,
        "source_name": source_name,
        "text": text,
        "bid": bid,
        "amount": amount,
        "exclusion_count": max(len(exclusions), reconciled_exclusion_count),
        "exclusions": exclusions,
        "clarifications": clarifications,
        "notes": notes,
        "mobilization_count": mobilization.get("count"),
        "mobilization_price": mobilization.get("price"),
        "validity": _extract_validity(text),
        "schedule": _extract_schedule(text),
        "below_grade": _extract_below_grade(text),
        "scope_strengths": strengths,
        "scope_posture": _scope_posture(text, strengths),
        "sheet_reference_count": _sheet_reference_count(text),
        "salvage_present": _contains(text, "salvage rights", "contractor property"),
        "make_safe_present": _contains(text, "make-safe", "made safe", "dropped by others"),
        "temporary_present": _contains(text, "temporary protection", "temporary fencing"),
        "hazardous_present": _contains(text, "hazardous", "contaminated soils", "freon", "lead paint"),
    }


# ---------------------------------------------------------------------------
# Pricing Position
# ---------------------------------------------------------------------------

def _price_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [r for r in records if isinstance(r.get("amount"), (int, float))]


def _spread_facts(records: List[Dict[str, Any]]) -> Dict[str, Any]:
    priced = _price_records(records)

    if len(priced) < 2:
        return {}

    low = min(priced, key=lambda item: item["amount"])
    high = max(priced, key=lambda item: item["amount"])
    spread = high["amount"] - low["amount"]
    spread_percent = (spread / low["amount"]) * 100 if low["amount"] else 0

    return {
        "low": low,
        "high": high,
        "spread": spread,
        "spread_percent": spread_percent,
    }


def _build_derivation_price_summary(
    *,
    reconciliation: Optional[dict],
    derivations: Optional[dict],
) -> List[str]:
    derived = _safe_dict(derivations) or _safe_dict(_presentation_derivations(reconciliation))
    price_deriv = _safe_dict(derived.get("price"))
    summary: List[str] = []

    if price_deriv.get("low_bidder"):
        summary.append(f"Low Bidder: {price_deriv['low_bidder']}")
    if price_deriv.get("high_bidder"):
        summary.append(f"High Bidder: {price_deriv['high_bidder']}")
    if price_deriv.get("spread"):
        summary.append(f"Bid Spread: {price_deriv['spread']}")

    return summary


# ---------------------------------------------------------------------------
# Commercial Report Composition
# ---------------------------------------------------------------------------

def _executive_snapshot(records: List[Dict[str, Any]]) -> List[str]:
    facts = _spread_facts(records)

    if facts:
        low = facts["low"]
        high = facts["high"]
        spread = _format_currency(facts["spread"])
        percent = facts["spread_percent"]

        if percent <= 1:
            return [
                (
                    f"Both bidders are effectively at price parity. {low['name']} "
                    f"is lower than {high['name']} by {spread} ({percent:.2f}%). "
                    "The key leveling issue is not price; it is whether scope, "
                    "exclusions, mobilization assumptions, and commercial qualifiers "
                    "are truly comparable."
                )
            ]

        return [
            (
                f"{low['name']} is the apparent low bidder with a spread of "
                f"{spread} ({percent:.2f}%). The lower number should still be "
                "leveled against exclusions, mobilizations, and responsibility limits."
            )
        ]

    return [
        "Pricing comparison is incomplete because one or more submitted bids did not produce extractable base bid evidence."
    ]


def _pricing_items(records: List[Dict[str, Any]]) -> List[str]:
    facts = _spread_facts(records)
    items: List[str] = []

    for record in records:
        bid = record.get("bid") or "Not extracted"
        _append_unique(items, f"{record['name']} ({record['source_name']}): {bid}")

    if facts:
        _append_unique(items, f"Spread: {_format_currency(facts['spread'])}")
        if facts["spread_percent"] <= 1:
            _append_unique(items, "Price alone does not meaningfully differentiate these bids.")
        else:
            _append_unique(items, f"Spread percentage: {facts['spread_percent']:.2f}%")

    return items


def _scope_coverage_items(records: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []

    for record in records:
        strengths = _format_preview(record.get("scope_strengths") or [], 6)
        posture = record.get("scope_posture") or "scope evidence detected"

        if strengths == "Not extracted":
            _append_unique(items, f"{record['name']}: {posture}.")
            continue

        _append_unique(
            items,
            f"{record['name']}: {posture}; extracted categories include {strengths}.",
        )

    if len(records) >= 2:
        first = records[0]
        second = records[1]
        if first.get("scope_posture") != second.get("scope_posture"):
            _append_unique(
                items,
                (
                    f"{first['name']} reads as {first.get('scope_posture')}, while "
                    f"{second['name']} reads as {second.get('scope_posture')}; this "
                    "difference should be checked against the drawings and scope matrix."
                ),
            )

    return items


def _mobilization_items(records: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []

    for record in records:
        count = record.get("mobilization_count")
        price = record.get("mobilization_price")

        if count and price:
            text = f"{record['name']}: {count} mobilization(s) indicated; additional mobilizations {price}."
        elif count:
            text = f"{record['name']}: {count} mobilization(s) indicated."
        else:
            text = f"{record['name']}: mobilization count was not extracted."

        _append_unique(items, text)

    counts = {r.get("mobilization_count") for r in records if r.get("mobilization_count")}
    if len(counts) > 1:
        _append_unique(
            items,
            "Mobilization assumptions differ and should be leveled before award reliance.",
        )

    return items


def _exclusion_risk_items(records: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []

    for record in records:
        count = record.get("exclusion_count", 0)
        preview = _format_preview(record.get("exclusions") or [], 5)

        if count and preview != "Not extracted":
            _append_unique(
                items,
                f"{record['name']}: {count} exclusion evidence item(s); key items include {preview}.",
            )
        elif count:
            _append_unique(
                items,
                f"{record['name']}: {count} exclusion evidence item(s) detected, but detailed exclusion text was limited in the extracted report view.",
            )
        else:
            _append_unique(items, f"{record['name']}: no exclusion evidence was extracted.")

    counts = [r.get("exclusion_count", 0) for r in records]
    if counts and max(counts) >= 8:
        _append_unique(
            items,
            "At least one bid carries a broad exclusion posture; exclusion carry scope should be reviewed before treating these bids as commercially equal.",
        )

    return items


def _commercial_condition_items(records: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []

    for record in records:
        parts: List[str] = []

        if record.get("schedule"):
            parts.append(f"schedule basis {record['schedule']}")
        if record.get("validity"):
            parts.append(f"pricing valid {record['validity']}")
        if record.get("below_grade"):
            parts.append(f"below-grade limit {record['below_grade']}")
        if record.get("salvage_present"):
            parts.append("salvage/material ownership language present")
        if record.get("temporary_present"):
            parts.append("temporary protection language present")
        if record.get("make_safe_present"):
            parts.append("utility/MEP make-safe language present")
        if record.get("hazardous_present"):
            parts.append("hazardous material language present")

        if parts:
            _append_unique(items, f"{record['name']}: {'; '.join(parts)}.")
        else:
            _append_unique(items, f"{record['name']}: no major commercial condition signals were extracted.")

    return items


def _key_risk_difference_items(records: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []

    for record in records:
        flags: List[str] = []

        if record.get("exclusion_count", 0) >= 8:
            flags.append("broad exclusion posture")
        if record.get("below_grade"):
            flags.append("below-grade removal limit")
        if record.get("mobilization_price"):
            flags.append("separately priced additional mobilizations")
        if record.get("make_safe_present"):
            flags.append("utility/MEP responsibility qualification")
        if record.get("temporary_present"):
            flags.append("temporary protection qualification")
        if record.get("scope_posture") == "broader narrative scope":
            flags.append("less sheet-specific scope posture")

        if flags:
            _append_unique(items, f"{record['name']}: {', '.join(flags)}.")

    if len(records) >= 2:
        first = records[0]
        second = records[1]
        if first.get("below_grade") and not second.get("below_grade"):
            _append_unique(
                items,
                f"{first['name']} carries a below-grade limit that was not extracted for {second['name']}.",
            )
        if first.get("mobilization_count") != second.get("mobilization_count"):
            _append_unique(
                items,
                f"{first['name']} and {second['name']} use different mobilization assumptions.",
            )

    if not items:
        _append_unique(
            items,
            "No major bid-specific risk differences were extracted by the current deterministic comparison path.",
        )

    return items


def _leveling_checklist(records: List[Dict[str, Any]]) -> List[str]:
    items: List[str] = []

    if any(r.get("below_grade") for r in records):
        _append_unique(items, "Verify exact below-grade demolition requirements.")
    if any(r.get("mobilization_count") for r in records):
        _append_unique(items, "Confirm required mobilization count and schedule phasing.")
    if any(r.get("make_safe_present") for r in records):
        _append_unique(items, "Confirm who owns utility and MEP make-safe responsibility.")
    if any(r.get("temporary_present") for r in records):
        _append_unique(items, "Clarify temporary protection expectations.")
    if any(r.get("exclusion_count", 0) for r in records):
        _append_unique(items, "Level exclusions against the prime scope and owner requirements.")
    if any(r.get("salvage_present") for r in records):
        _append_unique(items, "Confirm salvage/material ownership requirements.")

    if not items:
        _append_unique(items, "Confirm pricing, scope coverage, and exclusions against the bid documents.")

    return items


def _bottom_line(records: List[Dict[str, Any]]) -> str:
    facts = _spread_facts(records)

    if not facts:
        return (
            "This comparison should be treated as incomplete until base bid pricing "
            "is extracted for each submitted bidder."
        )

    low = facts["low"]
    high = facts["high"]
    spread = _format_currency(facts["spread"])
    percent = facts["spread_percent"]

    if percent <= 1:
        return (
            f"Price is effectively equal. {low['name']} is lower than {high['name']} "
            f"by only {spread} ({percent:.2f}%). Award risk is likely to be driven "
            "by scope completeness, exclusion carry scope, mobilization assumptions, "
            "temporary protection, utility/MEP responsibility, and other commercial "
            "qualifiers rather than base bid alone."
        )

    return (
        f"{low['name']} is the apparent low bidder by {spread} ({percent:.2f}%). "
        "The next review should confirm that the lower price is supported by comparable "
        "scope coverage and does not rely on unresolved exclusions or qualifications."
    )


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------

def _render_section(lines: List[str], title: str, items: List[str]) -> None:
    if not _has_text_items(items):
        return

    lines.append(f"<b>{escape(title, quote=False)}</b>")
    lines.extend(_html_list(items))


def _render_compare(records: List[Dict[str, Any]]) -> str:
    title = "Bid Comparison"

    if len(records) >= 2:
        title = f"Bid Comparison — {records[0]['name']} vs. {records[1]['name']}"

    lines: List[str] = ['<div class="bei-compare">']
    lines.append(f"<b>{escape(title, quote=False)}</b>")

    lines.append("<b>Executive Snapshot</b>")
    for item in _executive_snapshot(records):
        lines.append(_paragraph(item))

    _render_section(lines, "Pricing", _pricing_items(records))
    _render_section(lines, "Scope Coverage", _scope_coverage_items(records))
    _render_section(lines, "Mobilization Assumptions", _mobilization_items(records))
    _render_section(lines, "Exclusions / Risk Review", _exclusion_risk_items(records))
    _render_section(lines, "Commercial Conditions", _commercial_condition_items(records))
    _render_section(lines, "Key Risk Differences", _key_risk_difference_items(records))
    _render_section(lines, "Leveling Checklist", _leveling_checklist(records))

    lines.append("<b>Bottom-Line Read</b>")
    lines.append(_paragraph(_bottom_line(records)))

    lines.append("</div>")
    return "\n".join(lines).strip()


# ---------------------------------------------------------------------------
# Public Renderer
# ---------------------------------------------------------------------------

def build_multi_compare(
    docs: List[dict],
    reconciliation: dict | None,
    helpers: Optional[dict] = None,
    derivations: Optional[dict] = None,
) -> str:
    """
    Build deterministic multi-document BEI comparison output.

    The helpers argument is retained for compatibility with older callers.
    The derivations argument is retained for compatibility and future use.
    """

    del helpers

    safe_docs = _safe_documents(docs)

    if len(safe_docs) < 2:
        return (
            '<div class="bei-compare">'
            "<p>Compare requires at least two documents.</p>"
            "</div>"
        )

    records = [
        _doc_bid_record(
            doc=doc,
            index=index,
            reconciliation=reconciliation,
        )
        for index, doc in enumerate(safe_docs[:2], start=1)
    ]

    if not _spread_facts(records):
        derived_summary = _build_derivation_price_summary(
            reconciliation=reconciliation,
            derivations=derivations,
        )
        if derived_summary:
            logger.info("[BEI_COMPARE] used derivation price summary fallback")

    logger.info(
        "[BEI_COMPARE] rendered commercial deterministic compare docs=%s llm_wording=disabled",
        len(records),
    )

    return _render_compare(records)
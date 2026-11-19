# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/estimator_decision_signals.py
# DIRECTORY: solomon_core/presentation/
# ---------------------------------------------------------------------------
# Estimator Decision Signals Witness Layer
#
# PURPOSE
#   Surface explicit commercial term markers from an existing BEI / DocIntel
#   packet for presentation support.
#
# AUTHORITY CONTRACT
#   This module is witness-only. It may provide counts, observations, and
#   presentation hints. It must not create findings, classify risk, route work,
#   authorize execution, or alter BEI / DocIntel determinations.
#
# ALLOWED
#   - Count explicitly configured term markers.
#   - Surface the source field and excerpt where a marker was observed.
#   - Return presentation hints for downstream UI/narrative layers.
#
# NOT ALLOWED
#   - Routing authority.
#   - Risk classification authority.
#   - BEI finding authority.
#   - Final report conclusion authority.
#   - New facts beyond observed packet text.
#   - Fuzzy matching or semantic expansion.
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List, Tuple


# ---------------------------------------------------------------------------
# Witness Contract Constants
# ---------------------------------------------------------------------------

AUTHORITY_LEVEL = "presentation_witness_only"

PROHIBITED_USES = (
    "routing_authority",
    "risk_classification_authority",
    "bei_finding_authority",
    "final_report_conclusion_authority",
    "execution_authority",
)

# ---------------------------------------------------------------------------
# Explicit Term Marker Surfaces
# ---------------------------------------------------------------------------

CHANGE_ORDER_TERM_MARKERS = (
    "hidden condition",
    "hidden conditions",
    "concealed",
    "allowance",
    "unit price",
    "additional mobilization",
    "additional mobilizations",
    "per mobilization",
)

COMMERCIAL_CONDITION_TERM_MARKERS = (
    "pricing is only valid",
    "price is only valid",
    "valid for",
    "salvage rights",
    "proposal is based on",
    "work week",
)

TEXT_SOURCE_FIELDS = (
    "inclusions",
    "exclusions",
    "qualifiers",
    "conditions",
    "notes",
    "clarifications",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_lower(text: Any) -> str:
    if not isinstance(text, str):
        return ""

    return text.lower()


def _safe_excerpt(text: str, limit: int = 220) -> str:
    cleaned = " ".join(str(text or "").split())

    if len(cleaned) <= limit:
        return cleaned

    return f"{cleaned[:limit].rstrip()}..."


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value

    return []


def _read_payload(doc: Any) -> Dict[str, Any]:
    if not isinstance(doc, dict):
        return {}

    payload = doc.get("payload")

    if isinstance(payload, dict):
        return payload

    return doc


def _iter_text_sources(doc: Dict[str, Any]) -> List[Dict[str, str]]:
    """
    Collects text-bearing fields that already exist in the packet.

    This does not infer new data. It only surfaces strings already present
    under known text-bearing packet fields.
    """

    payload = _read_payload(doc)
    collected: List[Dict[str, str]] = []

    for field_name in TEXT_SOURCE_FIELDS:
        value = payload.get(field_name)

        if isinstance(value, str):
            collected.append({
                "field": field_name,
                "text": value,
            })
            continue

        if not isinstance(value, list):
            continue

        for item in value:
            if isinstance(item, str):
                collected.append({
                    "field": field_name,
                    "text": item,
                })
                continue

            if not isinstance(item, dict):
                continue

            text = item.get("text") or item.get("value") or item.get("description")

            if isinstance(text, str):
                collected.append({
                    "field": field_name,
                    "text": text,
                })

    return collected


def _observe_term_markers(
    *,
    text_sources: List[Dict[str, str]],
    marker_group: str,
    markers: Tuple[str, ...],
) -> List[Dict[str, str]]:
    observations: List[Dict[str, str]] = []

    for source in text_sources:
        raw_text = source.get("text") or ""
        lowered = _safe_lower(raw_text)

        if not lowered:
            continue

        for marker in markers:
            if marker not in lowered:
                continue

            observations.append({
                "group": marker_group,
                "marker": marker,
                "source_field": source.get("field") or "unknown",
                "excerpt": _safe_excerpt(raw_text),
            })

    return observations


def _document_count_items(payload: Dict[str, Any], key: str) -> int:
    value = payload.get(key)

    if isinstance(value, list):
        return len(value)

    return 0


def _derive_commercial_posture_hint(
    *,
    qualifier_count: int,
    commercial_condition_marker_count: int,
) -> str:
    """
    Produces a presentation hint only.

    The returned value is not a risk classification and must not be used as a
    decision authority. Thresholds are intentionally simple and transparent.
    """

    signal_weight = qualifier_count + commercial_condition_marker_count

    if signal_weight >= 8:
        return "qualification_heavy"

    if signal_weight >= 3:
        return "moderate_conditions"

    return "low_conditioning"


def _derive_scope_coverage_hint(exclusion_count: int) -> str:
    """
    Produces a presentation hint only.

    The returned value is not a scope determination and must not be used as a
    BEI finding. Thresholds are intentionally simple and transparent.
    """

    if exclusion_count >= 12:
        return "narrow_scope_bias"

    if exclusion_count >= 5:
        return "standard_scope"

    return "broad_scope"


def _build_empty_result() -> Dict[str, Any]:
    return {
        "authority_level": AUTHORITY_LEVEL,
        "prohibited_uses": list(PROHIBITED_USES),
        "commercial_posture": "low_conditioning",
        "change_order_risk": False,
        "scope_coverage": "broad_scope",
        "observations": [],
        "metrics": {
            "document_count": 0,
            "total_exclusions": 0,
            "total_qualifiers": 0,
            "change_order_marker_hits": 0,
            "commercial_condition_marker_hits": 0,
            "text_source_count": 0,
        },
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def derive_estimator_decision_signals(packet: Dict[str, Any]) -> Dict[str, Any]:
    """
    Derive witness-only estimator presentation signals.

    Returns a machine-readable bundle that preserves the historical keys used
    by downstream presentation code while making authority limits explicit:

    {
        "authority_level": "presentation_witness_only",
        "prohibited_uses": [...],
        "commercial_posture": "...",
        "change_order_risk": bool,
        "scope_coverage": "...",
        "observations": [...],
        "metrics": {...}
    }
    """

    if not isinstance(packet, dict):
        return _build_empty_result()

    documents = packet.get("documents") or packet.get("document_set") or []

    if not isinstance(documents, list):
        documents = []

    total_exclusions = 0
    total_qualifiers = 0
    text_source_count = 0
    observations: List[Dict[str, str]] = []

    for doc in documents:
        payload = _read_payload(doc)

        total_exclusions += _document_count_items(payload, "exclusions")
        total_qualifiers += _document_count_items(payload, "qualifiers")

        text_sources = _iter_text_sources(doc)
        text_source_count += len(text_sources)

        observations.extend(
            _observe_term_markers(
                text_sources=text_sources,
                marker_group="change_order_marker",
                markers=CHANGE_ORDER_TERM_MARKERS,
            )
        )

        observations.extend(
            _observe_term_markers(
                text_sources=text_sources,
                marker_group="commercial_condition_marker",
                markers=COMMERCIAL_CONDITION_TERM_MARKERS,
            )
        )

    change_order_marker_hits = sum(
        1 for item in observations
        if item.get("group") == "change_order_marker"
    )

    commercial_condition_marker_hits = sum(
        1 for item in observations
        if item.get("group") == "commercial_condition_marker"
    )

    commercial_posture = _derive_commercial_posture_hint(
        qualifier_count=total_qualifiers,
        commercial_condition_marker_count=commercial_condition_marker_hits,
    )

    scope_coverage = _derive_scope_coverage_hint(
        exclusion_count=total_exclusions,
    )

    return {
        "authority_level": AUTHORITY_LEVEL,
        "prohibited_uses": list(PROHIBITED_USES),
        "commercial_posture": commercial_posture,
        "change_order_risk": change_order_marker_hits > 0,
        "scope_coverage": scope_coverage,
        "observations": observations,
        "metrics": {
            "document_count": len(documents),
            "total_exclusions": total_exclusions,
            "total_qualifiers": total_qualifiers,
            "change_order_marker_hits": change_order_marker_hits,
            "commercial_condition_marker_hits": commercial_condition_marker_hits,
            "text_source_count": text_source_count,
        },
    }
# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/estimator_narrative_builder.py
# DIRECTORY: solomon_core/presentation/
# ---------------------------------------------------------------------------
# Estimator Narrative Builder
#
# PURPOSE
#   Convert witness-only estimator presentation signals into restrained
#   narrative fragments suitable for UI support.
#
# AUTHORITY CONTRACT
#   This module does not create BEI findings, classify risk, route work,
#   authorize execution, or make final report conclusions. It only translates
#   already-observed presentation markers into cautious UI language.
#
# GUARANTEES
#   - Consumes witness-only signal bundles.
#   - No LLM usage.
#   - No routing authority.
#   - No risk classification authority.
#   - No BEI finding authority.
#   - No final conclusion authority.
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List


# ---------------------------------------------------------------------------
# Witness Contract Constants
# ---------------------------------------------------------------------------

EXPECTED_AUTHORITY_LEVEL = "presentation_witness_only"

PROHIBITED_USES = (
    "routing_authority",
    "risk_classification_authority",
    "bei_finding_authority",
    "final_report_conclusion_authority",
    "execution_authority",
)


# ---------------------------------------------------------------------------
# Presentation Phrase Maps
# ---------------------------------------------------------------------------

COMMERCIAL_POSTURE_HINTS = {
    "qualification_heavy": (
        "The packet contains multiple commercial-condition markers that may "
        "deserve review during bid leveling."
    ),
    "moderate_conditions": (
        "The packet contains some commercial-condition markers that should be "
        "reviewed against the intended scope and award requirements."
    ),
    "low_conditioning": (
        "Few commercial-condition markers were surfaced by the presentation "
        "witness layer."
    ),
}

SCOPE_COVERAGE_HINTS = {
    "narrow_scope_bias": (
        "The packet contains a higher count of exclusion entries, which may "
        "warrant focused scope-boundary review."
    ),
    "standard_scope": (
        "The packet contains a moderate count of exclusion entries for review."
    ),
    "broad_scope": (
        "The packet contains a lower count of exclusion entries in the fields "
        "available to the presentation witness layer."
    ),
}

CHANGE_ORDER_HINT = (
    "Explicit term markers associated with possible change-order exposure were "
    "observed in the packet text."
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _empty_result(reason: str = "") -> Dict[str, Any]:
    ui_hints = {
        "authority_level": EXPECTED_AUTHORITY_LEVEL,
        "prohibited_uses": list(PROHIBITED_USES),
        "change_order_watch": False,
        "metrics": {},
        "observations": [],
    }

    if reason:
        ui_hints["narrative_status"] = reason

    return {
        "summary_flags": [],
        "risk_flags": [],
        "ui_hints": ui_hints,
    }


def _is_expected_witness_bundle(signals: Dict[str, Any]) -> bool:
    authority_level = signals.get("authority_level")

    if authority_level is None:
        return True

    return authority_level == EXPECTED_AUTHORITY_LEVEL


def _as_dict(value: Any) -> Dict[str, Any]:
    if isinstance(value, dict):
        return value

    return {}


def _as_list(value: Any) -> List[Any]:
    if isinstance(value, list):
        return value

    return []


def _clean_observation(item: Any) -> Dict[str, str]:
    if not isinstance(item, dict):
        return {}

    cleaned = {}

    for key in ("group", "marker", "source_field", "excerpt"):
        value = item.get(key)

        if isinstance(value, str) and value.strip():
            cleaned[key] = value.strip()

    return cleaned


def _clean_observations(observations: Any, limit: int = 12) -> List[Dict[str, str]]:
    cleaned: List[Dict[str, str]] = []

    for item in _as_list(observations):
        observation = _clean_observation(item)

        if observation:
            cleaned.append(observation)

        if len(cleaned) >= limit:
            break

    return cleaned


def _append_hint(target: List[str], phrase_map: Dict[str, str], key: Any) -> None:
    if not isinstance(key, str):
        return

    phrase = phrase_map.get(key)

    if phrase:
        target.append(phrase)


def _build_ui_hints(signals: Dict[str, Any]) -> Dict[str, Any]:
    metrics = _as_dict(signals.get("metrics"))
    observations = _clean_observations(signals.get("observations"))

    return {
        "authority_level": signals.get("authority_level") or EXPECTED_AUTHORITY_LEVEL,
        "prohibited_uses": list(signals.get("prohibited_uses") or PROHIBITED_USES),
        "change_order_watch": signals.get("change_order_risk") is True,
        "metrics": metrics,
        "observations": observations,
        "narrative_status": "witness_only",
    }


# ---------------------------------------------------------------------------
# Public Builder
# ---------------------------------------------------------------------------

def build_estimator_narrative(signals: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert witness-only estimator signals into presentation fragments.

    Returns the historical structure expected by downstream UI code:

    {
        "summary_flags": [...],
        "risk_flags": [...],
        "ui_hints": {...}
    }

    The returned strings are presentation hints only. They must not be treated
    as BEI findings, risk classifications, routing decisions, or final report
    conclusions.
    """

    if not isinstance(signals, dict):
        return _empty_result("invalid_signal_bundle")

    if not _is_expected_witness_bundle(signals):
        return _empty_result("unsupported_authority_level")

    summary_flags: List[str] = []
    risk_flags: List[str] = []

    _append_hint(
        summary_flags,
        COMMERCIAL_POSTURE_HINTS,
        signals.get("commercial_posture"),
    )

    _append_hint(
        summary_flags,
        SCOPE_COVERAGE_HINTS,
        signals.get("scope_coverage"),
    )

    if signals.get("change_order_risk") is True:
        risk_flags.append(CHANGE_ORDER_HINT)

    return {
        "summary_flags": summary_flags,
        "risk_flags": risk_flags,
        "ui_hints": _build_ui_hints(signals),
    }
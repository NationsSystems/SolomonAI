"""
solomon_core/ingress/rsm_classifier.py

Phase 48 — RSM Classifier (Pure, Declarative)

PURPOSE
-------
Provide a deterministic, side-effect-free classifier that maps ingress
metadata to a Routing Scenario Matrix (RSM) scenario ID and declarative
routing posture — or returns UNKNOWN.

This module:
- DOES NOT route
- DOES NOT execute
- DOES NOT invoke planners or skills
- DOES NOT modify UX
- DOES NOT persist state
- DOES NOT observe payload content

It is safe to import, safe to not import, and safe to remove.

AUTHORITATIVE NOTES
-------------------
- Classification is structural and invariant-based.
- Unknowns are first-class and must be returned explicitly.
- No authority escalation is permitted here.
"""

from typing import Dict, Optional, Tuple

# ---------------------------------------------------------------------------
# Public constants (LOCKED)
# ---------------------------------------------------------------------------

UNKNOWN_SCENARIO_ID = "RSM-UNK"

# Declarative routing postures (classification only; no execution semantics)
POSTURE_ASSISTIVE = {
    "authority": "assistive",
    "determinism": "open",
    "presentation": "raw",
    "execution_eligible": False,
}

POSTURE_OPERATOR_ONLY = {
    "authority": "operator",
    "determinism": "deterministic",
    "presentation": "raw",
    "execution_eligible": False,
}

POSTURE_DISALLOWED = {
    "authority": "assistive",
    "determinism": "open",
    "presentation": "raw",
    "execution_eligible": False,
    "disallowed": True,
}

# ---------------------------------------------------------------------------
# RSM canonical scenarios (v1.0)
# Each entry is purely declarative.
# ---------------------------------------------------------------------------

_RSM_SCENARIOS = [
    {
        "id": "RSM-01",
        "artifact": "none",
        "intent": "query",
        "determinism": "open",
        "authority": "assistive",
        "presentation": "summarized",
        "posture": {
            "authority": "assistive",
            "determinism": "open",
            "presentation": "summarized",
            "execution_eligible": False,
        },
    },
    {
        "id": "RSM-02",
        "artifact": "single",
        "intent": "transform",
        "determinism": "deterministic",
        "authority": "assistive",
        "presentation": "structured",
        "posture": {
            "authority": "assistive",
            "determinism": "deterministic",
            "presentation": "structured",
            "execution_eligible": False,
        },
    },
    {
        "id": "RSM-03",
        "artifact": "multi",
        "intent": "compare",
        "determinism": "bounded",
        "authority": "assistive",
        "presentation": "structured",
        "posture": {
            "authority": "assistive",
            "determinism": "bounded",
            "presentation": "structured",
            "execution_eligible": False,
        },
    },
    {
        "id": "RSM-04",
        "artifact": "none",
        "intent": "diagnostic",
        "determinism": "deterministic",
        "authority": "operator",
        "presentation": "raw",
        "posture": POSTURE_OPERATOR_ONLY,
    },
    {
        # Operator-only control
        "id": "RSM-05",
        "artifact": "any",
        "intent": "control",
        "determinism": "any",
        "authority": "operator",
        "presentation": "raw",
        "posture": POSTURE_OPERATOR_ONLY,
    },
    {
        # Explicitly disallowed: assistive control
        "id": "RSM-06",
        "artifact": "any",
        "intent": "control",
        "determinism": "any",
        "authority": "assistive",
        "presentation": "any",
        "posture": POSTURE_DISALLOWED,
    },
]


# ---------------------------------------------------------------------------
# Helper functions (private)
# ---------------------------------------------------------------------------

def _value_matches(rule_value: str, actual_value: Optional[str]) -> bool:
    """
    Returns True if the rule_value matches the actual_value.
    The special value 'any' matches any non-None value.
    """
    if rule_value == "any":
        return actual_value is not None
    return rule_value == actual_value


def _scenario_matches(scenario: Dict[str, str], meta: Dict[str, Optional[str]]) -> bool:
    """
    Determine whether a scenario matches the provided metadata.
    All dimensions must match; no inference or coercion is allowed.
    """
    return (
        _value_matches(scenario["artifact"], meta.get("artifact")) and
        _value_matches(scenario["intent"], meta.get("intent")) and
        _value_matches(scenario["determinism"], meta.get("determinism")) and
        _value_matches(scenario["authority"], meta.get("authority")) and
        _value_matches(scenario["presentation"], meta.get("presentation"))
    )


def _has_unknowns(meta: Dict[str, Optional[str]]) -> bool:
    """
    Returns True if any required dimension is missing or None.
    """
    required = ("artifact", "intent", "determinism", "authority", "presentation")
    for key in required:
        if key not in meta or meta.get(key) is None:
            return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def classify_ingress(
    *,
    artifact: Optional[str],
    intent: Optional[str],
    determinism: Optional[str],
    authority: Optional[str],
    presentation: Optional[str],
) -> Tuple[str, Dict[str, object]]:
    """
    Classify ingress metadata against RSM v1.0.

    Parameters are metadata ONLY. Payload content must never be provided here.

    Returns:
        (scenario_id, posture_dict)

    If classification fails or is ambiguous, returns:
        (RSM-UNK, POSTURE_ASSISTIVE)

    This function is:
    - Deterministic
    - Side-effect free
    - Safe to call in diagnostics only
    """

    meta = {
        "artifact": artifact,
        "intent": intent,
        "determinism": determinism,
        "authority": authority,
        "presentation": presentation,
    }

    # Unknowns are first-class
    if _has_unknowns(meta):
        return UNKNOWN_SCENARIO_ID, POSTURE_ASSISTIVE

    # Exact scenario match (first match wins; table order is canonical)
    for scenario in _RSM_SCENARIOS:
        if _scenario_matches(scenario, meta):
            return scenario["id"], dict(scenario["posture"])

    # No scenario matched → UNKNOWN collapse
    return UNKNOWN_SCENARIO_ID, POSTURE_ASSISTIVE

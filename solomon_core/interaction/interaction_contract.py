# solomon_core/interaction/interaction_contract.py
# ---------------------------------------------------------------------
# Phase 31 — Interaction Contract (Semantic Boundary)
#
# PURPOSE:
#   • Define the canonical structure for interaction requests
#   • Enforce "no language in core" invariant
#   • Provide validation for follow-up interactions
#
# THIS MODULE:
#   • Does NOT render text
#   • Does NOT ask questions
#   • Does NOT infer intent
#   • Does NOT mutate state
#
# It defines WHAT an interaction is — not how it is presented.
# ---------------------------------------------------------------------

from typing import Dict, Any


# ---------------------------------------------------------------------
# Interaction Types (Phase 31)
# ---------------------------------------------------------------------

INTERACTION_FOLLOWUP = "FOLLOWUP"


# ---------------------------------------------------------------------
# Required Fields Per Interaction Type
# ---------------------------------------------------------------------

_REQUIRED_FIELDS = {
    INTERACTION_FOLLOWUP: {
        "interaction_type",
        "intent",
        "field",
        "conversation_id",
        "turn_index",
    }
}


# ---------------------------------------------------------------------
# Public Validation API
# ---------------------------------------------------------------------

def validate_interaction_contract(payload: Dict[str, Any]) -> None:
    """
    Validate that an interaction payload conforms to the Phase 31 contract.

    Raises:
        ValueError if the payload is invalid.
    """

    if not isinstance(payload, dict):
        raise ValueError("Interaction payload must be a dict")

    interaction_type = payload.get("interaction_type")
    if interaction_type not in _REQUIRED_FIELDS:
        raise ValueError(f"Unknown interaction_type: {interaction_type}")

    required = _REQUIRED_FIELDS[interaction_type]
    missing = required - payload.keys()

    if missing:
        raise ValueError(
            f"Interaction payload missing required fields: {sorted(missing)}"
        )

    # Explicit invariant: no language allowed in core interaction payloads
    for key, value in payload.items():
        if isinstance(value, str):
            # Allow semantic identifiers only
            # Reject obvious language leakage
            if " " in value and key not in {"interaction_type"}:
                raise ValueError(
                    f"Language detected in interaction field '{key}': '{value}'"
                )

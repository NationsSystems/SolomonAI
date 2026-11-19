# solomon_core/intent_expansion.py
# ---------------------------------------------------------------
# Phase 31 — Intent Expansion Controller (Hybrid, Semantic Only)
#
# PURPOSE:
#   • Decide whether an intent may request additional constraints
#   • Emit semantic interaction contracts ONLY (no language)
#   • Never perform ambiguity repair
#   • Never mutate intent or entities
#
# GUARANTEES:
#   • Deterministic
#   • No LLM usage
#   • No phrasing or UI logic
#   • No inference or guessing
#   • Safe to call pre-execution
#
# NOTE:
#   This module does NOT ask questions.
#   It only declares *what* information is needed, if any.
# ---------------------------------------------------------------

from typing import Dict, Any, Optional, List


# ----------------------------------------------------------------
# Intent Expansion Registry (Phase 31 v2 — Rules & Limits Enabled)
#
# IMPORTANT:
#   • This registry defines EXPANDABILITY only
#   • No language, no phrasing, no presentation details
#   • Field order is EXPLICIT and DETERMINISTIC
# ----------------------------------------------------------------

INTENT_EXPANSION_REGISTRY: Dict[str, Dict[str, Any]] = {
    "compare_documents": {
        "expandable": True,
        "max_followups": 2,  # hard limit per task
        "field_order": [
            "comparison_focus",
        ],
        "fields": {
            "comparison_focus": {
                "type": "enum",
                "values": ["scope", "cost", "schedule"],
                "required": False,
            },
        },
    },
    # Additional intents may be added here deliberately
}


# ----------------------------------------------------------------
# Public API
# ----------------------------------------------------------------

def maybe_expand_intent(
    intent: str,
    entities: Dict[str, Any],
    conversation_id: str,
    turn_index: int,
) -> Optional[Dict[str, Any]]:
    """
    Decide whether the current intent requires an expansion interaction.

    Returns:
        None
            → No expansion needed; execution may proceed.

        Dict[str, Any]
            → Semantic interaction contract describing the required follow-up.
              This must be rendered by the presentation layer.
    """

    spec = INTENT_EXPANSION_REGISTRY.get(intent)
    if not spec:
        return None

    if not spec.get("expandable", False):
        return None

    # ------------------------------------------------------------
    # Phase 31.6 — Follow-up limit enforcement
    # ------------------------------------------------------------
    max_followups = spec.get("max_followups", 0)
    if max_followups <= 0:
        return None

    if turn_index >= max_followups:
        return None

    fields = spec.get("fields", {})
    if not fields:
        return None

    field_order: List[str] = spec.get("field_order", [])
    if not field_order:
        return None

    # ------------------------------------------------------------
    # Phase 31.10 — Explicit grounding validation
    #
    # A field is considered "present" ONLY if:
    #   • It exists in entities
    #   • Its value is valid per the field enum (if defined)
    # ------------------------------------------------------------
    missing_fields: List[str] = []

    for field_name in field_order:
        field_spec = fields.get(field_name, {})
        value = entities.get(field_name)

        # Missing entirely
        if value is None:
            missing_fields.append(field_name)
            continue

        # Enum validation (explicit grounding required)
        allowed = field_spec.get("values")
        if allowed and value not in allowed:
            missing_fields.append(field_name)
            continue

    if not missing_fields:
        return None

    # Phase 31 rule:
    #   • Ask about ONE field only per turn
    field_to_request = missing_fields[0]

    # ------------------------------------------------------------
    # Emit semantic interaction contract (NO LANGUAGE)
    # ------------------------------------------------------------
    return {
        "interaction_type": "FOLLOWUP",
        "intent": intent,
        "field": field_to_request,
        "conversation_id": conversation_id,
        "turn_index": turn_index,
    }

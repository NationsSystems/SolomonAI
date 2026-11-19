# solomon_core/solomon_tools/clarification_selector.py — Phase-38 GUI-Ready
# ---------------------------------------------------------------------------
# PURPOSE:
#   • Select an appropriate clarification prompt
#   • Based ONLY on epistemic + structural signals
#   • Provide human-feeling clarification for GUI display
#   • No routing, no execution, no state decisions
# ---------------------------------------------------------------------------

from typing import Optional, Dict
from solomon_core.logger import get_logger
from solomon_core.epistemic_layer import EpistemicDecision, EpistemicState

logger = get_logger("clarification_selector")


# ============================================================================
# Clarification Prompt Library (NON-SEMANTIC, NON-AUTHORITATIVE)
# ============================================================================
_CLARIFICATION_PROMPTS = {
    "multi_doc_present": "What would you like me to do with the documents you’ve provided?",
    "single_doc_present": "What would you like me to do with this document?",
    "prototype_telemetry_present": "Can you clarify what you’d like me to do?",
    "no_structural_signal": "Could you clarify what you’d like help with?",
    "docs_missing": "I don’t see any documents attached. Please upload the documents you want me to work with.",
    "default": "Could you provide a bit more direction so I can help?",
}


# ============================================================================
# Public API — GUI-Compatible
# ============================================================================
def select_clarification_prompt(
    *,
    epistemic_decision: EpistemicDecision,
    router_signal: Optional[str],
    entities: Dict,
) -> Optional[str]:
    """
    Selects a clarification prompt for GUI display based on signals only.

    Assumes clarification is ALREADY required. Performs no decision-making or
    state transitions.
    Returns a string prompt or None if not applicable.
    """

    # ------------------------------------------------------------
    # Guard: clarification must already be required
    # ------------------------------------------------------------
    if epistemic_decision.state not in (
        EpistemicState.UNCERTAIN,
        EpistemicState.PARTIALLY_CONFIDENT,
        EpistemicState.BLOCKED,
    ):
        return None

    if not epistemic_decision.followup_required:
        return None

    # ------------------------------------------------------------
    # Factual grounding check
    # ------------------------------------------------------------
    docs = entities.get("docs")
    docs_count = len(docs) if isinstance(docs, list) else 0

    if docs_count == 0:
        logger.info("ClarificationPrompt | source=docs_missing")
        return _CLARIFICATION_PROMPTS["docs_missing"]

    # ------------------------------------------------------------
    # Router signal driven phrasing
    # ------------------------------------------------------------
    if router_signal and router_signal in _CLARIFICATION_PROMPTS:
        prompt = _CLARIFICATION_PROMPTS[router_signal]
        logger.info("ClarificationPrompt | source=router_signal | signal=%s", router_signal)
        return prompt

    # ------------------------------------------------------------
    # Structural inference from entities
    # ------------------------------------------------------------
    if docs_count >= 2:
        return _CLARIFICATION_PROMPTS["multi_doc_present"]
    if docs_count == 1:
        return _CLARIFICATION_PROMPTS["single_doc_present"]

    # ------------------------------------------------------------
    # Default safe clarification
    # ------------------------------------------------------------
    logger.info("ClarificationPrompt | source=default")
    return _CLARIFICATION_PROMPTS["default"]


__all__ = ["select_clarification_prompt"]

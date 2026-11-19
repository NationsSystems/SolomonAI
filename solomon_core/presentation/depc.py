# solomon_core/presentation/depc.py
# ---------------------------------------------------------------------------
# Phase 51 — Direct-Execution Presentation Contract (DEPC)
# ---------------------------------------------------------------------------
# PURPOSE:
#   Enforce a binary presentation contract ensuring that all user-facing
#   DIRECT_EXECUTION outputs are actual executed answers, not meta-descriptions.
#
# PROPERTIES:
#   • Post-LLM, Pre-HUD
#   • Deterministic
#   • Model-agnostic
#   • Non-authoritative
#   • Fully removable
#   • Zero state mutation
#
# STATUS:
#   Phase 51 — ACTIVE
# ---------------------------------------------------------------------------

from enum import Enum


class DEPCDecision(Enum):
    ACCEPT = "accept"
    REJECT = "reject"


# ---------------------------------------------------------------------------
# Locked Phrase Sets (Phase 51 Scope — Do Not Expand)
# ---------------------------------------------------------------------------

META_PHRASES = [
    "this answer should",
    "the answer should",
    "the response should",
    "should include",
    "would include",
    "an explanation would",
    "here’s what to mention",
    "here is what to mention",
    "this response will",
    "this answer will",
    "based on the provided context",
    "a possible summary",
    "the summary should",
]

CLEAN_REFUSALS = [
    "i can’t help with that",
    "i cannot help with that",
    "i’m not able to provide that",
    "i am not able to provide that",
    "i can’t provide that",
    "i cannot provide that",
]


# ---------------------------------------------------------------------------
# DEPC Evaluation Function
# ---------------------------------------------------------------------------

def evaluate_direct_execution(text: str, presentation_intent: str) -> DEPCDecision:
    """
    Evaluate whether the provided LLM output satisfies the Direct-Execution
    Presentation Contract (DEPC).

    This function is:
      • Pure
      • Stateless
      • Deterministic
      • Side-effect free

    Parameters:
        text (str): Candidate output text from LLM execution.
        presentation_intent (str): Intent flag for presentation routing.

    Returns:
        DEPCDecision.ACCEPT or DEPCDecision.REJECT
    """

    # Scope gate — DEPC applies ONLY to DIRECT_EXECUTION
    if presentation_intent != "DIRECT_EXECUTION":
        return DEPCDecision.ACCEPT

    if not text or not isinstance(text, str):
        return DEPCDecision.REJECT

    normalized = text.strip().lower()

    # Allow clean refusals verbatim
    if normalized in CLEAN_REFUSALS:
        return DEPCDecision.ACCEPT

    # Reject known meta-descriptive execution modes
    for phrase in META_PHRASES:
        if phrase in normalized:
            return DEPCDecision.REJECT

    # Reject purely structural or placeholder responses
    if normalized.endswith(":") and len(normalized.split()) <= 3:
        return DEPCDecision.REJECT

    if all(
        line.strip().startswith(("-", "*")) or not line.strip()
        for line in normalized.splitlines()
    ):
        return DEPCDecision.REJECT

    return DEPCDecision.ACCEPT

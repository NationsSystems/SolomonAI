"""
Lexicon Subsystem — Orchestrator Boundary Bridge

Location: solomon_core/presentation/lexicon/lexicon_orchestrator_bridge.py
Status: Phase 43 — Passive Integration (AUTHORITATIVE)
Authority: NON-AUTHORITATIVE (SASE-Governed)

This module defines the sole, explicit boundary bridge between
authority-bearing orchestrator code and the non-authoritative
Lexicon presentation subsystem.

Phase 43 CHANGE:
- Lexicon is PASSIVE by default
- Lexicon is ONLY applied when Solomon itself constructs language
- LLM-emitted language bypasses Lexicon entirely

Lexicon:
- Never self-invokes
- Never selects itself
- Never runs implicitly
- Never rewrites LLM output

All invocation must be deliberate, explicit, and orchestrator-controlled.
"""

from .lexicon_interface_contracts import (
    LexiconInputPayload,
    LexiconOutputPayload,
)
from .lexicon_deterministic_renderer import (
    DeterministicLexiconRenderer,
)


# ---------------------------------------------------------------------------
# Orchestrator → Lexicon Boundary Call
# ---------------------------------------------------------------------------

def apply_lexicon_presentation(
    payload: LexiconInputPayload,
    *,
    enabled: bool,
) -> LexiconOutputPayload:
    """
    Explicitly apply Lexicon presentation logic to a finalized response payload.

    PHASE 43 CONTRACT:
    - Caller MUST be the execution authority
    - Caller MUST explicitly opt in
    - Payload MUST originate from Solomon-authored language
    - LLM-authored language MUST NOT be passed here

    SAFETY GUARANTEES:
    - If disabled, payload passes through unchanged
    - If enabled, Lexicon applies deterministic presentation only
    - No authority, routing, or planning influence is possible

    FAIL-CLOSED POLICY:
    - Any error results in original payload being returned unchanged
    """

    # Lexicon is opt-in only (PASSIVE by default)
    if not enabled:
        return {
            "user_output": payload["user_output"],
            "presentation": None,
        }

    try:
        renderer = DeterministicLexiconRenderer()
        return renderer.apply(payload)

    except Exception:
        # Fail closed: never block execution, never alter meaning
        return {
            "user_output": payload["user_output"],
            "presentation": None,
        }


# ---------------------------------------------------------------------------
# Canonical Statement
# ---------------------------------------------------------------------------

# This file represents a one-way, authority-safe boundary.
#
# Orchestrator → Lexicon
# Never the reverse.
#
# Lexicon shapes Solomon-authored expression only.
# LLM language passes through untouched.
#
# Authority remains singular and untouched.

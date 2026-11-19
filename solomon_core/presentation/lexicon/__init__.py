"""
Solomon Lexicon Subsystem

Location: solomon_core/presentation/lexicon/__init__.py
Status: Phase 44 — Header-Gated Construction (AUTHORITATIVE)
Authority: NON-AUTHORITATIVE (SASE-Governed)

This package defines the sealed public boundary of the Lexicon subsystem.
Lexicon is a deterministic, presentation-only sub-machine that controls
HOW Solomon communicates, never WHAT Solomon decides.

Phase 44 CHANGE:
• Lexicon activates ONLY when PacketHeader.presentation_mode == "constructed"
• Lexicon is bypassed entirely for "emitted" and "suppressed" packets

No execution authority, inference, routing, or autonomy is permitted.
"""

# ---------------------------------------------------------------------------
# Public Interface Contracts (LOCKED)
# ---------------------------------------------------------------------------

from .lexicon_interface_contracts import (
    LexiconInputPayload,
    LexiconOutputPayload,
    LexiconInterface,
)

# ---------------------------------------------------------------------------
# Presentation Policy Declarations (LOCKED)
# ---------------------------------------------------------------------------

from .lexicon_presentation_policy import (
    RuleType,
    LexiconRulePolicy,
    LexiconPackPolicy,
    BASE_LEXICON_PACK,
    DOCINTEL_LEXICON_PACK,
    REVIEWER_LEXICON_PACK,
)

# ---------------------------------------------------------------------------
# Safety Invariants & Guardrails (LOCKED)
# ---------------------------------------------------------------------------

from .lexicon_safety_invariants import (
    AUTHORITY_INVARIANTS,
    SEMANTIC_INVARIANTS,
    DETERMINISM_INVARIANTS,
    BOUNDARY_INVARIANTS,
    PHASE_42_CONSTRAINTS,
)

# ---------------------------------------------------------------------------
# Deterministic Presentation Implementation
# ---------------------------------------------------------------------------

from .lexicon_deterministic_renderer import (
    DeterministicLexiconRenderer,
)

# ---------------------------------------------------------------------------
# Orchestrator Boundary Bridge (HEADER-GATED)
# ---------------------------------------------------------------------------

from .lexicon_orchestrator_bridge import (
    apply_lexicon_presentation as _apply_lexicon_presentation,
)

def apply_lexicon_presentation(*, packet_header: dict, payload):
    """
    Phase 44:
    Lexicon activates ONLY for constructed presentation.
    Header is read-only. Payload is presentation-only mutable.
    """

    if not isinstance(packet_header, dict):
        return payload

    presentation_mode = packet_header.get("presentation_mode")

    if presentation_mode != "constructed":
        # Explicit bypass — emitted and suppressed payloads pass through
        return payload

    return _apply_lexicon_presentation(
        packet_header=packet_header,
        payload=payload,
    )

# ---------------------------------------------------------------------------
# Subsystem Identity (INFORMATIONAL ONLY)
# ---------------------------------------------------------------------------

LEXICON_SUBSYSTEM_NAME = "Lexicon"
LEXICON_SUBSYSTEM_VERSION = "2.1"
LEXICON_AUTHORITY_LEVEL = "non-authoritative"
LEXICON_SEALED = True


# ---------------------------------------------------------------------------
# Explicit Non-Goals (HARD STOPS)
# ---------------------------------------------------------------------------

# This package MUST NEVER:
# - Execute logic autonomously
# - Select or activate lexicon packs
# - Modify execution payloads beyond presentation
# - Influence planning, execution, or autonomy
# - Access memory, tools, or system state
# - Emit signals, events, or side effects
#
# Any violation constitutes a SASE breach.


# ---------------------------------------------------------------------------
# Canonical Statement
# ---------------------------------------------------------------------------

# Lexicon is a machine within the machine.
# It shapes expression, not intent.
# Authority remains singular and untouched.

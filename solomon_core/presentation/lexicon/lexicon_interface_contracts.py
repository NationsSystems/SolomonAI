"""
Lexicon Subsystem — Interface Contracts (LOCKED)

Location: solomon_core/presentation/lexicon/lexicon_interface_contracts.py
Status: Phase 42 — Contract Finalization (AUTHORITATIVE & LOCKED)
Authority: NON-AUTHORITATIVE (SASE-Governed)

This module defines the explicit, frozen interface contracts for the Lexicon
presentation subsystem.

Lexicon is a sealed, deterministic presentation machine. It may restructure,
label, and format content, but it must never alter meaning, introduce inference,
or exert authority.

NO executable behavior is permitted in this file.

Governing Documents (AUTHORITATIVE):
- docs/SASE_LAWS.md
- Solomon_Phase_41_Charter.docx
- Lexicon v2 Design Document
- docs/ideology/Epistemic_Output_Typing.md
- docs/ideology/Meta_Observation_Doctrine.md
"""

from typing import TypedDict, Literal, Optional, Dict, Any, List


# ---------------------------------------------------------------------------
# Epistemic & Contextual Types (READ-ONLY INPUTS)
# ---------------------------------------------------------------------------

EvidenceState = Literal[
    "explicit",        # Claims directly supported by provided materials
    "not_found",       # No information found
    "out_of_scope",    # Information intentionally not evaluated
    "uncertain"        # Evidence present but incomplete or ambiguous
]

TaskType = Literal[
    "general",
    "docintel",
    "analysis",
    "review"
]


# ---------------------------------------------------------------------------
# Allowed Presentation Operations (EXHAUSTIVE)
# ---------------------------------------------------------------------------

AllowedPresentationOperation = Literal[
    "relabel",         # Rename headings or labels without changing meaning
    "reorder",         # Deterministic reordering via explicit rules
    "group",           # Group related sections without prioritization
    "frame",           # Apply neutral framing templates
    "format"           # Whitespace, bullets, numbering, headings
]


# ---------------------------------------------------------------------------
# Presentation Metadata (OUTPUT-ONLY)
# ---------------------------------------------------------------------------

class PresentationMetadata(TypedDict, total=False):
    """
    Presentation-only annotations.

    These annotations are visible to presentation layers only and MUST NOT
    influence execution, planning, memory, routing, or autonomy.

    This metadata exists solely for auditability and human inspection.
    """

    lexicon_pack: str
    applied_rules: List[str]
    operations_applied: List[AllowedPresentationOperation]


# ---------------------------------------------------------------------------
# Lexicon Input Payload (IMMUTABLE)
# ---------------------------------------------------------------------------

class LexiconInputPayload(TypedDict):
    """
    Canonical read-only input payload for Lexicon operations.

    REQUIRED PROPERTIES:
    - Produced by execution authority
    - Fully resolved prior to Lexicon invocation
    - Treated as immutable by Lexicon

    SASE MAPPING:
    - LAW 1: No authority granted
    - LAW 3: Signals consumed only, never acted upon
    """

    # Final user-facing content (authoritative meaning already resolved)
    user_output: str

    # Epistemic signals (read-only)
    evidence_state: EvidenceState
    task_type: TaskType

    # Optional contextual flags (read-only)
    citations_present: bool
    reviewer_mode: Optional[bool]
    scope_flags: Optional[Dict[str, Any]]


# ---------------------------------------------------------------------------
# Lexicon Output Payload (STRICTLY LIMITED)
# ---------------------------------------------------------------------------

class LexiconOutputPayload(TypedDict):
    """
    Canonical Lexicon output payload.

    ALLOWED MUTATIONS:
    - user_output (presentation-only transformation)
    - presentation (optional metadata)

    FORBIDDEN MUTATIONS:
    - Any field not explicitly listed
    - Any semantic alteration of meaning
    - Any modification of epistemic signals

    SASE MAPPING:
    - LAW 2: No implicit authority
    - LAW 4: No cross-layer influence
    - LAW 5: Deterministic transformation only
    """

    # Presentation-transformed user-facing content
    user_output: str

    # Optional presentation-only annotations
    presentation: Optional[PresentationMetadata]


# ---------------------------------------------------------------------------
# Lexicon Interface Definition (DECLARATIVE ONLY)
# ---------------------------------------------------------------------------

class LexiconInterface:
    """
    Abstract interface contract for Lexicon implementations.

    IMPLEMENTATION CONSTRAINTS:
    - MUST be deterministic
    - MUST be stateless
    - MUST be content-agnostic (rule-based only)
    - MUST NOT infer, decide, evaluate, or recommend
    - MUST NOT access system state, memory, tools, logs, or signals

    NOTE:
    This interface is declarative only. Concrete implementations
    are explicitly out of scope for Phase 42 contract definition.
    """

    def apply(self, payload: LexiconInputPayload) -> LexiconOutputPayload:
        """
        Apply presentation-only transformations to a finalized response payload.

        CONTRACT GUARANTEES:
        - Input payload is treated as read-only
        - Output preserves semantic meaning exactly
        - Absence, uncertainty, and scope limits are preserved verbatim
        - All operations must be explainable via explicit rules

        FORBIDDEN:
        - Strengthening or weakening claims
        - Resolving uncertainty
        - Introducing recommendations or advice
        - Ranking, prioritization, or emphasis signaling
        - Altering or emitting execution-relevant fields
        """
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Explicit Non-Goals (HARD STOPS)
# ---------------------------------------------------------------------------

# The Lexicon subsystem MUST NEVER:
# - Decide or recommend actions
# - Rank, prioritize, score, or evaluate content
# - Introduce inference, implication, or interpretation
# - Influence planning, execution, or autonomy
# - Emit signals, events, or side effects
# - Modify memory, state, or logs
# - Call upstream or downstream systems
#
# Any violation of the above constitutes a SASE breach.

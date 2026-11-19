"""
Lexicon Subsystem — Policy Definitions (LOCKED)

Location: solomon_core/presentation/lexicon/lexicon_presentation_policy.py
Status: Phase 43 — UX-Calibrated Policy Finalization
Authority: NON-AUTHORITATIVE (SASE-Governed)

Phase 43 Update:
- Default policy no longer injects compliance framing
- Lexicon packs reflect user-facing reality
- Strict framing is preserved for DocIntel and Reviewer modes
- No logic added, no authority changed

This file remains DECLARATIVE ONLY.
"""

from typing import TypedDict, Literal, List


# ---------------------------------------------------------------------------
# Lexicon Rule Categories (EXHAUSTIVE & CLOSED)
# ---------------------------------------------------------------------------

RuleType = Literal[
    "evidence_framing",        # Explicit framing tied to evidence_state
    "tone_normalization",      # Removal of urgency, bias, or confidence inflation
    "structural_formatting",   # Headings, bullets, spacing, ordering
    "scope_disclosure",        # Explicit declaration of scope limits or omissions
    "uncertainty_preservation" # Callouts that preserve uncertainty verbatim
]


# ---------------------------------------------------------------------------
# Lexicon Rule Policy (DECLARATIVE ONLY)
# ---------------------------------------------------------------------------

class LexiconRulePolicy(TypedDict):
    """
    Declarative description of a single Lexicon rule.

    REQUIRED GUARANTEES:
    - Semantic meaning preserved
    - Uncertainty never reduced
    - Non-directive language
    - Deterministic behavior
    """

    rule_id: str
    rule_type: RuleType
    description: str
    intent: str

    preserves_semantics: bool
    preserves_uncertainty: bool
    non_directive: bool
    deterministic: bool


# ---------------------------------------------------------------------------
# Lexicon Pack Policy (DESIGN-TIME GROUPING ONLY)
# ---------------------------------------------------------------------------

class LexiconPackPolicy(TypedDict):
    """
    Declarative grouping of Lexicon rules.

    Ordering implies presentation sequence only.
    No execution semantics.
    """

    pack_id: str
    description: str
    applicable_task_types: List[str]
    rule_ids: List[str]


# ---------------------------------------------------------------------------
# Canonical Lexicon Packs (PHASE 43 CALIBRATED)
# ---------------------------------------------------------------------------

BASE_LEXICON_PACK: LexiconPackPolicy = {
    "pack_id": "base",
    "description": (
        "Minimal presentation rules for general user interaction. "
        "Allows natural language flow without mandatory compliance framing."
    ),
    "applicable_task_types": ["general", "analysis"],
    "rule_ids": [
        # Phase 43: no default evidence framing
        "neutral_tone_enforcement",
    ],
}


DOCINTEL_LEXICON_PACK: LexiconPackPolicy = {
    "pack_id": "docintel",
    "description": (
        "Strict presentation rules for document intelligence outputs. "
        "Ensures evidence transparency, scope clarity, and omission disclosure."
    ),
    "applicable_task_types": ["docintel"],
    "rule_ids": [
        "evidence_state_header",
        "scope_boundary_notice",
        "structural_section_normalization",
    ],
}


REVIEWER_LEXICON_PACK: LexiconPackPolicy = {
    "pack_id": "reviewer",
    "description": (
        "Reviewer-oriented rules emphasizing conservative framing, "
        "traceability, and explicit uncertainty preservation."
    ),
    "applicable_task_types": ["analysis", "review"],
    "rule_ids": [
        "evidence_state_header",
        "explicit_uncertainty_callout",
    ],
}


# ---------------------------------------------------------------------------
# Explicit Non-Goals (HARD STOPS — UNCHANGED)
# ---------------------------------------------------------------------------

# This module MUST NEVER:
# - Contain execution or matching logic
# - Select or activate lexicon packs
# - Apply rules to text
# - Infer evidence state, task type, or intent
# - Modify payloads or outputs
# - Influence planning, execution, or autonomy
#
# Any violation of the above constitutes a SASE breach.

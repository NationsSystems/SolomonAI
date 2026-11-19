"""
Lexicon Subsystem — Phrase Bank (CANONICAL)

Location: solomon_core/presentation/lexicon/lexicon_phrase_bank.py
Status: Phase 43 — UX-Calibrated Lexicon Core
Authority: NON-AUTHORITATIVE (SASE-Governed)

This module defines the approved language Lexicon MAY use.

Phase 43 Update:
- Default phrases are now USER-NATURAL
- Defensive disclosures are retained but NOT default
- Language supports conversational LLM output
- Compliance remains opt-in, not forced

NO logic. NO conditionals. NO runtime decisions.
"""

# ---------------------------------------------------------------------------
# Evidence Framing Phrases (OPTIONAL / NON-DEFAULT)
# ---------------------------------------------------------------------------

EVIDENCE_STATE_HEADERS = {
    # Used ONLY when explicitly requested by orchestrator or reviewer mode
    "explicit": "Based on the available information:",
    "not_found": "No relevant information was found in the reviewed materials.",
    "out_of_scope": "This topic was not covered by the materials reviewed.",
    "uncertain": "The available information is incomplete or unclear.",
}


# ---------------------------------------------------------------------------
# Scope & Limitation Phrases (OPTIONAL)
# ---------------------------------------------------------------------------

SCOPE_LIMITATION_PHRASE = (
    "This response is limited to the context and information evaluated."
)


# ---------------------------------------------------------------------------
# Uncertainty Disclosure Phrase (OPTIONAL)
# ---------------------------------------------------------------------------

UNCERTAINTY_DISCLOSURE_PHRASE = (
    "Some details may vary depending on additional context."
)


# ---------------------------------------------------------------------------
# Reviewer-Oriented Conservative Framing (STRICTLY OPT-IN)
# ---------------------------------------------------------------------------

REVIEWER_MODE_FRAMING_PHRASE = (
    "The following reflects a conservative interpretation of the available information."
)


# ---------------------------------------------------------------------------
# Neutral Transition Phrase (LIGHTWEIGHT)
# ---------------------------------------------------------------------------

NEUTRAL_TRANSITION_PHRASE = "Additional context:"


# ---------------------------------------------------------------------------
# Structural Section Labels (UNCHANGED)
# ---------------------------------------------------------------------------

SECTION_LABELS = {
    "findings": "Findings",
    "limitations": "Limitations",
    "notes": "Notes",
    "context": "Context",
}


# ---------------------------------------------------------------------------
# Explicit Non-Goals (HARD STOPS — UNCHANGED)
# ---------------------------------------------------------------------------

# This module MUST NEVER:
# - Contain logic or conditionals
# - Select phrases dynamically
# - Inspect or interpret content
# - Introduce new language at runtime
# - Include persuasive, evaluative, or directive wording
#
# Any violation of the above constitutes a SASE breach.


# ---------------------------------------------------------------------------
# Canonical Statement
# ---------------------------------------------------------------------------

# Phase 43 Canonical Position:
# - Lexicon language supports natural conversation
# - Compliance language is preserved but optional
# - The LLM speaks first; Lexicon only frames when asked
# - Authority remains singular and untouched

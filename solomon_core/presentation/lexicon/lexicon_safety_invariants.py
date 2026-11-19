"""
Lexicon Subsystem — Guardrails & Invariants (LOCKED)

Location: solomon_core/presentation/lexicon/lexicon_safety_invariants.py
Status: Phase 42 — Guard Finalization (AUTHORITATIVE & LOCKED)
Authority: NON-AUTHORITATIVE (SASE-Governed)

This module defines the explicit guardrails, invariants, and hard-stop rules
that govern the Lexicon subsystem.

It exists to make violations unmistakable at design, review, and audit time,
and to permanently remove ambiguity about what Lexicon is allowed to do.

This file contains NO executable enforcement logic.
It is a declarative safety artifact.

Governing Documents (AUTHORITATIVE):
- docs/SASE_LAWS.md
- Solomon_Phase_41_Charter.docx
- Lexicon v2 Design Document
- docs/ideology/Epistemic_Output_Typing.md
- docs/ideology/Meta_Observation_Doctrine.md
"""

# ---------------------------------------------------------------------------
# Canonical Authority Invariants (ABSOLUTE)
# ---------------------------------------------------------------------------

# The Lexicon subsystem is a PRESENTATION-ONLY component.
# It possesses ZERO execution, planning, or evaluative authority.

AUTHORITY_INVARIANTS = [
    "Lexicon does not decide",
    "Lexicon does not recommend",
    "Lexicon does not prioritize",
    "Lexicon does not rank or score",
    "Lexicon does not evaluate quality, importance, or risk",
    "Lexicon does not infer intent or meaning",
    "Lexicon does not influence execution flow",
    "Lexicon does not influence planning or autonomy",
    "Lexicon does not modify system state",
    "Lexicon does not write to memory or persistence layers",
    "Lexicon does not emit signals, events, or side effects",
]


# ---------------------------------------------------------------------------
# Semantic Preservation Invariants (NON-NEGOTIABLE)
# ---------------------------------------------------------------------------

# Lexicon transformations MUST preserve semantic meaning exactly.
# Presentation may change; meaning may not.

SEMANTIC_INVARIANTS = [
    "No strengthening of claims",
    "No weakening or resolution of uncertainty",
    "No merging, splitting, or reinterpreting facts",
    "No introduction of comparative judgment",
    "No implication of completeness where none exists",
    "No removal or softening of explicit scope limits",
    "No removal of declared omissions or absences",
]


# ---------------------------------------------------------------------------
# Determinism & Predictability Invariants
# ---------------------------------------------------------------------------

# Lexicon behavior must be predictable, auditable, and reversible.

DETERMINISM_INVARIANTS = [
    "Stateless operation only",
    "Identical input yields identical output",
    "No hidden configuration",
    "No environment- or context-dependent behavior",
    "No randomness or probabilistic behavior",
    "No time-based or session-based variation",
]


# ---------------------------------------------------------------------------
# Boundary & Isolation Invariants
# ---------------------------------------------------------------------------

# Lexicon must remain strictly isolated from all authority-bearing systems.

BOUNDARY_INVARIANTS = [
    "No access to planner modules",
    "No access to cognition modules",
    "No access to autonomy modules",
    "No access to execution modules",
    "No access to memory, databases, or persistence layers",
    "No access to tool invocation",
    "No cross-layer imports",
    "No backchannels or callbacks",
]


# ---------------------------------------------------------------------------
# Phase 42 Construction Constraints
# ---------------------------------------------------------------------------

# During Phase 42, the following constraints apply in addition to all invariants.

PHASE_42_CONSTRAINTS = [
    "Lexicon logic may be implemented only as deterministic presentation code",
    "All behavior must be explainable via explicit rules",
    "All rule application must be auditable and inspectable",
    "Guards must fail closed, never permissive",
    "No experimental or provisional logic",
    "No feature flags or hidden toggles",
]


# ---------------------------------------------------------------------------
# SASE Violation Definition
# ---------------------------------------------------------------------------

# Any of the following constitutes an immediate SASE breach:
#
# - Violation of any authority invariant
# - Violation of any semantic invariant
# - Violation of any determinism invariant
# - Violation of any boundary invariant
# - Violation of Phase 42 construction constraints
#
# SASE breaches require immediate stop-work and remediation.


# ---------------------------------------------------------------------------
# Canonical Statement
# ---------------------------------------------------------------------------

# The Lexicon subsystem is governed, sealed, and permanently non-authoritative.
# These guards are mandatory constraints, not guidance.
# No future phase may weaken or bypass them.

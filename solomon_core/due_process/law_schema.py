# solomon_core/due_process/law_schema.py
# ------------------------------------------------------------------
# Solomon AI — Due Process Engine (DPE)
# Law Authoring Schema (Declarative / JSON-First)
#
# PURPOSE:
#   Define the canonical schema for human-authored Due Process laws.
#   Laws are authored as JSON and validated against these structures
#   at build time. Runtime never reads source JSON directly.
#
# CONTRACT:
#   • Declarative only — no logic, no inference
#   • One law → one verdict
#   • Conditions are explicit and conjunctive (ALL must match)
#   • No defaults, no fallbacks
#   • UX language is non-authoritative and descriptive only
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Mapping, Literal


# ============================================================================
# Verdict Type (Constitutionally Fixed)
# ============================================================================

VerdictType = Literal[
    "AUTHORIZED",
    "REQUIRES_ACTION",
    "PROHIBITED",
]


# ============================================================================
# Law Conditions
# ============================================================================

@dataclass(frozen=True, slots=True)
class LawConditions:
    """
    Declarative condition block.

    Rules:
      - Keys are canonical EvidenceKeys (string)
      - Values are required TriState values expressed as strings
      - ALL conditions must be satisfied for the law to match
    """

    requires: Mapping[str, str]


# ============================================================================
# Law Definition
# ============================================================================

@dataclass(frozen=True, slots=True)
class LawDefinition:
    """
    Canonical law definition as authored in JSON.
    """

    # Governance identity
    law_id: str
    version: str
    status: Literal["ACTIVE", "DEPRECATED"]
    description: str

    # Matching surface
    conditions: LawConditions

    # Authority output
    verdict: VerdictType

    # Non-authoritative explanation surface (UX / audit only)
    basis_summary: str

    # Governance metadata
    author: str
    created_at: str


# ============================================================================
# Law Book (Authoring Unit)
# ============================================================================

@dataclass(frozen=True, slots=True)
class LawBook:
    """
    Container for a set of authored laws.
    Typically corresponds to a single JSON file.
    """

    laws: List[LawDefinition]


# ============================================================================
# Structural Validation (Build-Time Only)
# ============================================================================

def validate_law_definition(law: LawDefinition) -> None:
    """
    Structural validation only.
    Raises if required fields are missing or malformed.
    """
    if not law.law_id:
        raise ValueError("law_id is required")

    if not law.conditions or not law.conditions.requires:
        raise ValueError(f"Law '{law.law_id}' must define at least one condition")

    if law.verdict not in ("AUTHORIZED", "REQUIRES_ACTION", "PROHIBITED"):
        raise ValueError(f"Invalid verdict for law '{law.law_id}'")

    if not law.basis_summary:
        raise ValueError(f"Law '{law.law_id}' must define basis_summary")


def validate_law_book(book: LawBook) -> None:
    """
    Validate an entire law book.
    """
    seen = set()
    for law in book.laws:
        if law.law_id in seen:
            raise ValueError(f"Duplicate law_id detected: {law.law_id}")
        seen.add(law.law_id)
        validate_law_definition(law)

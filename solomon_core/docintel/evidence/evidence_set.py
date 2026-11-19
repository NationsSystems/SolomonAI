"""
File: solomon_core/docintel/evidence/evidence_set.py
Phase: 54 — Document Intelligence System Completion
Purpose: Governed grouping of evidence references

This module defines EvidenceSet, which represents a bounded collection
of EvidenceReference objects that are treated as a unit for validation,
binding, and result construction.

CRITICAL INVARIANTS:
- EvidenceSets are explicit and finite
- EvidenceSets do NOT imply sufficiency or truth
- EvidenceSets must be fully valid before use
- No execution, authorization, or inference logic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from solomon_core.docintel.evidence.evidence_reference import EvidenceReference


@dataclass(frozen=True)
class EvidenceSet:
    """
    Immutable grouping of EvidenceReference objects.

    An EvidenceSet answers only:
        "Which pieces of document evidence are being cited?"

    It does NOT answer:
        - Whether the evidence is sufficient
        - Whether the evidence supports a conclusion
    """

    references: Tuple[EvidenceReference, ...]

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def from_iterable(
        references: Iterable[EvidenceReference],
    ) -> "EvidenceSet":
        refs = tuple(references)
        if not refs:
            raise ValueError("EvidenceSet must contain at least one EvidenceReference")

        for ref in refs:
            ref.assert_valid()

        return EvidenceSet(references=refs)

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.references:
            raise ValueError("EvidenceSet contains no references")
        for ref in self.references:
            ref.assert_valid()

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    def document_ids(self) -> Tuple[str, ...]:
        """Return the set of document_ids referenced."""
        return tuple({ref.document_id for ref in self.references})

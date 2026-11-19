"""
File: solomon_core/docintel/evidence/evidence_policy.py
Phase: 54 — Document Intelligence System Completion
Purpose: Declarative evidence requirement policies

This module defines EvidencePolicy, which describes *what evidence must
exist* for an operation to be considered structurally valid.

CRITICAL INVARIANTS:
- Policies declare requirements, not judgments
- Policies do NOT inspect evidence content
- Policies do NOT infer sufficiency or correctness
- No execution, authorization, or intelligence logic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple


@dataclass(frozen=True)
class EvidencePolicy:
    """
    Declarative evidence requirement policy.

    This answers:
        "What kinds of evidence references must be present?"

    It does NOT answer:
        - Whether the evidence supports a claim
        - Whether the evidence is correct
    """

    required_anchor_types: Tuple[type, ...]
    minimum_references: int = 1

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def require(
        *,
        anchor_types: Iterable[type],
        minimum_references: int = 1,
    ) -> "EvidencePolicy":
        anchor_types_tuple = tuple(anchor_types)

        if not anchor_types_tuple:
            raise ValueError("EvidencePolicy must specify at least one anchor type")
        if minimum_references <= 0:
            raise ValueError("minimum_references must be > 0")

        return EvidencePolicy(
            required_anchor_types=anchor_types_tuple,
            minimum_references=minimum_references,
        )

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.required_anchor_types:
            raise ValueError("EvidencePolicy missing required_anchor_types")
        if self.minimum_references <= 0:
            raise ValueError("EvidencePolicy minimum_references must be > 0")

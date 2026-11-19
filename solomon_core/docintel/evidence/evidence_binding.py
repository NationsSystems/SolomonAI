"""
File: solomon_core/docintel/evidence/evidence_binding.py
Phase: 54 — Document Intelligence System Completion
Purpose: Explicit binding of validated evidence to outputs

This module defines EvidenceBinding, which represents the mechanical
attachment of an EvidenceSet to an output artifact (analysis or execution).

CRITICAL INVARIANTS:
- Evidence must be structurally validated before binding
- Binding is explicit and immutable
- Binding does NOT assert correctness or sufficiency
- No execution, authorization, or intelligence logic
"""

from __future__ import annotations

from dataclasses import dataclass

from solomon_core.docintel.evidence.evidence_set import EvidenceSet
from solomon_core.docintel.evidence.evidence_policy import EvidencePolicy
from solomon_core.docintel.evidence.evidence_validation import (
    validate_evidence_set,
    EvidenceValidationError,
)


@dataclass(frozen=True)
class EvidenceBinding:
    """
    Immutable binding between an EvidenceSet and its governing policy.

    This answers only:
        "Which evidence was bound, and under what declared requirements?"
    """

    evidence: EvidenceSet
    policy: EvidencePolicy

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def bind(
        *,
        evidence: EvidenceSet,
        policy: EvidencePolicy,
    ) -> "EvidenceBinding":
        """
        Validate and bind evidence according to policy.

        Raises EvidenceValidationError on any violation.
        """

        try:
            validate_evidence_set(evidence=evidence, policy=policy)
        except EvidenceValidationError:
            raise

        return EvidenceBinding(
            evidence=evidence,
            policy=policy,
        )

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if self.evidence is None:
            raise ValueError("EvidenceBinding missing evidence")
        if self.policy is None:
            raise ValueError("EvidenceBinding missing policy")

        # Re-validate defensively
        validate_evidence_set(
            evidence=self.evidence,
            policy=self.policy,
        )

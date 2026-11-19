"""
File: solomon_core/docintel/evidence/evidence_validation.py
Phase: 54 — Document Intelligence System Completion
Purpose: Structural validation of evidence against declared policy

This module enforces that required evidence *exists* and is structurally
valid according to an EvidencePolicy. It does NOT inspect content, infer
meaning, or judge correctness.

CRITICAL INVARIANTS:
- Validation is structural only
- No semantic inspection or interpretation
- No execution, authorization, or intelligence logic
- Fail-closed on any violation
"""

from __future__ import annotations

from typing import Iterable, Type

from solomon_core.docintel.evidence.evidence_reference import EvidenceReference
from solomon_core.docintel.evidence.evidence_policy import EvidencePolicy
from solomon_core.docintel.evidence.evidence_set import EvidenceSet


class EvidenceValidationError(Exception):
    """Raised when evidence fails structural validation."""


def validate_evidence_set(
    *,
    evidence: EvidenceSet,
    policy: EvidencePolicy,
) -> None:
    """
    Validate that an EvidenceSet satisfies an EvidencePolicy.

    Args:
        evidence: EvidenceSet to validate
        policy: EvidencePolicy defining required structure

    Raises:
        EvidenceValidationError on any violation
    """

    if evidence is None:
        raise EvidenceValidationError("EvidenceSet is required")

    if policy is None:
        raise EvidenceValidationError("EvidencePolicy is required")

    evidence.assert_valid()
    policy.assert_valid()

    references = evidence.references

    if len(references) < policy.minimum_references:
        raise EvidenceValidationError(
            f"EvidenceSet contains {len(references)} references, "
            f"but policy requires at least {policy.minimum_references}"
        )

    _validate_anchor_types(
        references=references,
        required_types=policy.required_anchor_types,
    )


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _validate_anchor_types(
    *,
    references: Iterable[EvidenceReference],
    required_types: Iterable[Type],
) -> None:
    """
    Ensure that at least one reference exists for each required anchor type.
    """

    for anchor_type in required_types:
        if not any(isinstance(ref.anchor, anchor_type) for ref in references):
            raise EvidenceValidationError(
                f"EvidenceSet missing required anchor type: {anchor_type.__name__}"
            )

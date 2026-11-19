"""
File: solomon_core/docintel/execution/execution_verifier.py
Phase: 54 — Document Intelligence System Completion
Purpose: Structural verification of execution legality

This module defines ExecutionVerifier, which performs *pre-execution*
legality checks without performing execution, emitting output, or
recovering from failure.

CRITICAL INVARIANTS:
- Verification is structural only
- No execution, retries, or inference
- Fail-closed on any violation
- No side effects
"""

from __future__ import annotations

from solomon_core.docintel.execution.execution_authorization import ExecutionAuthorization
from solomon_core.docintel.execution.execution_constraints import ExecutionConstraints
from solomon_core.docintel.evidence.evidence_binding import EvidenceBinding


class ExecutionVerificationError(Exception):
    """Raised when execution fails verification."""


class ExecutionVerifier:
    """
    Performs structural verification prior to execution.
    """

    @staticmethod
    def verify(
        *,
        authorization: ExecutionAuthorization,
        constraints: ExecutionConstraints,
        evidence: EvidenceBinding,
    ) -> None:
        """
        Verify that execution inputs are structurally valid.

        Raises ExecutionVerificationError on any violation.
        """

        if authorization is None:
            raise ExecutionVerificationError("Missing ExecutionAuthorization")
        if constraints is None:
            raise ExecutionVerificationError("Missing ExecutionConstraints")
        if evidence is None:
            raise ExecutionVerificationError("Missing EvidenceBinding")

        authorization.assert_valid()
        constraints.assert_valid()
        evidence.assert_valid()

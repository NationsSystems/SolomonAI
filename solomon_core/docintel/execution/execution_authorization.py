"""
File: solomon_core/docintel/execution/execution_authorization.py
Phase: 54 — Document Intelligence System Completion
Purpose: Immutable authorization token for controlled execution

This module defines ExecutionAuthorization, the *only* object that permits
execution to occur inside DocIntel. It is created by the Orchestrator and
consumed by the Execution Gate.

CRITICAL INVARIANTS:
- Authorization is explicit and immutable
- Authorization is never inferred or synthesized
- Authorization does NOT execute anything
- Authorization carries no intent or workflow semantics
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from solomon_core.docintel.evidence.evidence_policy import EvidencePolicy


@dataclass(frozen=True)
class ExecutionAuthorization:
    """
    Immutable authorization descriptor for a single execution.

    This answers:
        "Is this specific operation permitted to execute?"

    It does NOT answer:
        - How execution occurs
        - What the result should be
    """

    authorization_id: str
    primitive_name: str
    primitive_version: str
    evidence_policy: EvidencePolicy
    issued_by: str
    issued_utc: str
    expires_utc: Optional[str] = None

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.authorization_id:
            raise ValueError("ExecutionAuthorization missing authorization_id")
        if not self.primitive_name:
            raise ValueError("ExecutionAuthorization missing primitive_name")
        if not self.primitive_version:
            raise ValueError("ExecutionAuthorization missing primitive_version")
        if self.evidence_policy is None:
            raise ValueError("ExecutionAuthorization missing evidence_policy")
        if not self.issued_by:
            raise ValueError("ExecutionAuthorization missing issued_by")
        if not self.issued_utc:
            raise ValueError("ExecutionAuthorization missing issued_utc")

        self.evidence_policy.assert_valid()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create(
        *,
        authorization_id: str,
        primitive_name: str,
        primitive_version: str,
        evidence_policy: EvidencePolicy,
        issued_by: str,
        expires_utc: Optional[str] = None,
    ) -> "ExecutionAuthorization":
        auth = ExecutionAuthorization(
            authorization_id=authorization_id,
            primitive_name=primitive_name,
            primitive_version=primitive_version,
            evidence_policy=evidence_policy,
            issued_by=issued_by,
            issued_utc=datetime.now(timezone.utc).isoformat(),
            expires_utc=expires_utc,
        )

        auth.assert_valid()
        return auth

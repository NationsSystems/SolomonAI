"""
File: solomon_core/docintel/execution/execution_identity.py
Phase: 54 — Document Intelligence System Completion
Purpose: Canonical identity for a single execution instance

This module defines ExecutionIdentity, which uniquely identifies one
authorized execution for audit, observability, and result binding.

CRITICAL INVARIANTS:
- ExecutionIdentity is immutable
- Identity is deterministic at creation time
- No authority, execution, or workflow logic
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import uuid


@dataclass(frozen=True)
class ExecutionIdentity:
    """
    Immutable identity for a single execution instance.
    """

    execution_id: str
    created_utc: str

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create() -> "ExecutionIdentity":
        """
        Create a new ExecutionIdentity.

        Returns:
            ExecutionIdentity
        """
        return ExecutionIdentity(
            execution_id=f"exec:{uuid.uuid4()}",
            created_utc=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.execution_id.startswith("exec:"):
            raise ValueError("Invalid execution_id prefix")
        if not self.created_utc:
            raise ValueError("ExecutionIdentity missing created_utc")

"""
explicit_intent.py
Explicit Intent Runtime Model
Phase 55 — Explicit Intent Materialization

AUTHORITATIVE NOTES
-------------------
• ExplicitIntent is the ONLY artifact that authorizes execution
• ExplicitIntent is immutable and single-use
• ExplicitIntent is created ONLY from a SUFFICIENT CBIC
• ExplicitIntent is accepted ONLY by the Orchestrator
• No inference, no defaults, no mutation
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List


# ---------------------------------------------------------------------------
# Explicit Intent Model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ExplicitIntent:
    """
    ExplicitIntent represents a fully-resolved, user-confirmed,
    authoritative execution request.

    This object is the ONLY lawful input to the Orchestrator
    for document intelligence execution.
    """

    # Identity
    intent_id: str
    created_at: datetime

    # Operation
    operation: str
    operation_version: str

    # Artifacts
    document_ids: List[str]

    # Fully resolved constraints
    constraints: Dict[str, object]

    # Execution identity (for audit + traceability)
    execution_id: str

    # Authority marker (hard-coded)
    authority: str = "explicit_intent"

    # -------------------------------------------------------------------
    # Safety Assertions
    # -------------------------------------------------------------------

    def assert_authoritative(self) -> None:
        """
        Fail fast if ExplicitIntent is malformed or downgraded.
        """
        if self.authority != "explicit_intent":
            raise RuntimeError("ExplicitIntent authority marker is invalid")

        if not self.operation:
            raise RuntimeError("ExplicitIntent must specify an operation")

        if not self.document_ids:
            raise RuntimeError("ExplicitIntent must reference at least one document")

        if not self.constraints:
            raise RuntimeError("ExplicitIntent must contain resolved constraints")

    def is_executable(self) -> bool:
        """
        ExplicitIntent is always executable if it exists and is valid.
        """
        return True

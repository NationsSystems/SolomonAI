"""
File: solomon_core/docintel/execution/execution_audit.py
Phase: 54 — Document Intelligence System Completion
Purpose: Immutable audit records for DocIntel execution

This module defines ExecutionAuditRecord, which captures factual,
non-interpretive records of execution events for observability,
compliance, and post-mortem inspection.

CRITICAL INVARIANTS:
- Audit records are descriptive, never prescriptive
- No execution control or recovery logic
- No inference, summarization, or intent attribution
- Records are append-only once created
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class ExecutionAuditRecord:
    """
    Immutable audit record for a single execution event.
    """

    execution_id: str
    authorization_id: str
    primitive_name: str
    primitive_version: str
    status: str
    recorded_utc: str
    message: Optional[str] = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create(
        *,
        execution_id: str,
        authorization_id: str,
        primitive_name: str,
        primitive_version: str,
        status: str,
        message: Optional[str] = None,
    ) -> "ExecutionAuditRecord":
        if not execution_id:
            raise ValueError("execution_id is required")
        if not authorization_id:
            raise ValueError("authorization_id is required")
        if not primitive_name:
            raise ValueError("primitive_name is required")
        if not primitive_version:
            raise ValueError("primitive_version is required")
        if not status:
            raise ValueError("status is required")

        return ExecutionAuditRecord(
            execution_id=execution_id,
            authorization_id=authorization_id,
            primitive_name=primitive_name,
            primitive_version=primitive_version,
            status=status,
            recorded_utc=datetime.now(timezone.utc).isoformat(),
            message=message,
        )

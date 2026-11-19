"""
File: solomon_core/docintel/execution/execution_observability.py
Phase: 54 — Document Intelligence System Completion
Purpose: Emission of execution observability records

This module defines a minimal observability emitter for DocIntel execution.
It records execution lifecycle events without influencing control flow,
authorization, or execution behavior.

CRITICAL INVARIANTS:
- Observability is passive and side-effect free
- No retries, recovery, or inference
- No authority or execution logic
- Emission failures must not alter execution outcome
"""

from __future__ import annotations

from typing import Callable, Optional

from solomon_core.docintel.execution.execution_audit import ExecutionAuditRecord


class ExecutionObservability:
    """
    Passive emitter for execution audit records.

    A sink may be provided to route records to logs, databases,
    or diagnostic tooling.
    """

    def __init__(self, sink: Optional[Callable[[ExecutionAuditRecord], None]] = None):
        self._sink = sink

    # ------------------------------------------------------------------
    # Emission
    # ------------------------------------------------------------------

    def emit(self, record: ExecutionAuditRecord) -> None:
        """
        Emit an ExecutionAuditRecord.

        Emission failures are swallowed to preserve execution determinism.
        """

        if record is None:
            return

        if self._sink is None:
            return

        try:
            self._sink(record)
        except Exception:
            # Observability must never interfere with execution
            pass

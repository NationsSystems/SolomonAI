"""
File: solomon_core/docintel/results/execution_result_envelope.py
Phase: 54 — Document Intelligence System Completion
Purpose: Transport-safe envelope for governed execution results

This module defines ExecutionResultEnvelope, which packages an
EvidenceBoundResult together with minimal execution metadata for
transport across CLI and GUI boundaries.

CRITICAL INVARIANTS:
- Envelope contains governed results only
- No raw or unbound output may be transported
- No execution, authorization, or inference logic
- Immutable once created
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from solomon_core.docintel.results.evidence_bound_result import EvidenceBoundResult


@dataclass(frozen=True)
class ExecutionResultEnvelope:
    """
    Transport-safe wrapper for an EvidenceBoundResult.
    """

    result: EvidenceBoundResult
    emitted_utc: str

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create(result: EvidenceBoundResult) -> "ExecutionResultEnvelope":
        if result is None:
            raise ValueError("ExecutionResultEnvelope requires EvidenceBoundResult")

        result.assert_valid()

        return ExecutionResultEnvelope(
            result=result,
            emitted_utc=datetime.now(timezone.utc).isoformat(),
        )

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if self.result is None:
            raise ValueError("ExecutionResultEnvelope missing result")
        if not self.emitted_utc:
            raise ValueError("ExecutionResultEnvelope missing emitted_utc")

        self.result.assert_valid()

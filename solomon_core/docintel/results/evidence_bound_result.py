"""
File: solomon_core/docintel/results/evidence_bound_result.py
Phase: 54 — Document Intelligence System Completion
Purpose: Governed result bound to validated document evidence

This module defines EvidenceBoundResult, the *only* result type that may
leave the DocIntel execution core and be rendered by CLI or GUI.

CRITICAL INVARIANTS:
- Every result is explicitly bound to validated evidence
- No raw or unbound results may be exposed
- Results are immutable and auditable
- No execution, authorization, or inference logic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from solomon_core.docintel.primitives.primitive_result import PrimitiveResult
from solomon_core.docintel.evidence.evidence_binding import EvidenceBinding
from solomon_core.docintel.execution.execution_identity import ExecutionIdentity


@dataclass(frozen=True)
class EvidenceBoundResult:
    """
    Governed execution result with explicit evidence binding.

    This answers:
        "What was produced, and what document evidence supports it?"

    It does NOT answer:
        - Whether the result is correct
        - What actions should follow
    """

    execution_identity: ExecutionIdentity
    primitive_result: PrimitiveResult
    evidence_binding: EvidenceBinding

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if self.execution_identity is None:
            raise ValueError("EvidenceBoundResult missing execution_identity")
        if self.primitive_result is None:
            raise ValueError("EvidenceBoundResult missing primitive_result")
        if self.evidence_binding is None:
            raise ValueError("EvidenceBoundResult missing evidence_binding")

        self.execution_identity.assert_valid()
        self.primitive_result.assert_valid()
        self.evidence_binding.assert_valid()

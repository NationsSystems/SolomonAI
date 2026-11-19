"""
File: solomon_core/docintel/primitives/primitive_context.py
Phase: 54 — Document Intelligence System Completion
Purpose: Controlled execution context provided to DocIntel primitives

This module defines PrimitiveContext, the *only* object a primitive
receives at execution time. It provides access to governed documents,
validated evidence, and immutable execution metadata — without exposing
authority, authorization, or workflow state.

CRITICAL INVARIANTS:
- Context contains NO authorization objects
- Context contains NO execution controls
- Context contains NO workflow or planner state
- Context is immutable and read-only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from solomon_core.docintel.documents.document_identity import DocumentIdentity
from solomon_core.docintel.evidence.evidence_binding import EvidenceBinding
from solomon_core.docintel.execution.execution_identity import ExecutionIdentity


@dataclass(frozen=True)
class PrimitiveContext:
    """
    Immutable execution context passed to a primitive.

    This answers only:
        "What data and evidence is available?"

    It does NOT answer:
        - Why the primitive was invoked
        - Who authorized execution
        - What should happen next
    """

    execution_identity: ExecutionIdentity
    documents: Tuple[DocumentIdentity, ...]
    evidence: EvidenceBinding

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if self.execution_identity is None:
            raise ValueError("PrimitiveContext missing execution_identity")
        if not self.documents:
            raise ValueError("PrimitiveContext must contain documents")
        if self.evidence is None:
            raise ValueError("PrimitiveContext missing evidence")

        self.execution_identity.assert_valid()
        self.evidence.assert_valid()

        for doc in self.documents:
            doc.assert_valid()

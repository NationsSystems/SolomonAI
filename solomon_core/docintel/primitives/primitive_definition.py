"""
File: solomon_core/docintel/primitives/primitive_definition.py
Phase: 54 — Document Intelligence System Completion
Purpose: Canonical definition for certified DocIntel primitives

This module defines PrimitiveDefinition, the authoritative, declarative
description of a DocIntel primitive. It describes *what the primitive is*
without granting authority or enabling execution.

CRITICAL INVARIANTS:
- Definitions are declarative, not executable
- No authority, authorization, or execution logic
- No workflow or chaining semantics
- Definitions are static and versioned
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from solomon_core.docintel.evidence.evidence_policy import EvidencePolicy


@dataclass(frozen=True)
class PrimitiveDefinition:
    """
    Declarative definition of a DocIntel primitive.

    This answers:
        "What is this primitive, and what does it require?"

    It does NOT answer:
        - Whether it may execute
        - How it executes
        - Why it was invoked
    """

    name: str
    version: str
    description: str
    evidence_policy: EvidencePolicy
    supported_document_types: Tuple[str, ...]

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.name:
            raise ValueError("PrimitiveDefinition missing name")
        if not self.version:
            raise ValueError("PrimitiveDefinition missing version")
        if not self.description:
            raise ValueError("PrimitiveDefinition missing description")
        if self.evidence_policy is None:
            raise ValueError("PrimitiveDefinition missing evidence_policy")
        if not self.supported_document_types:
            raise ValueError("PrimitiveDefinition missing supported_document_types")

        self.evidence_policy.assert_valid()

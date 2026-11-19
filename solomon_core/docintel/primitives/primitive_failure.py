"""
File: solomon_core/docintel/primitives/primitive_failure.py
Phase: 54 — Document Intelligence System Completion
Purpose: Explicit, non-recoverable failure semantics for primitives

This module defines structured failure types for primitive execution.
Failures are terminal, descriptive, and never trigger retries,
fallbacks, or alternative execution paths.

CRITICAL INVARIANTS:
- Failures are explicit and typed
- No recovery, retry, or improvisation
- No authority or workflow semantics
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class PrimitiveFailure:
    """
    Structured description of a primitive failure.

    This answers:
        "What failed, and why?"

    It does NOT answer:
        - What to do next
        - Whether to retry
        - How to recover
    """

    primitive_name: str
    primitive_version: str
    reason: str
    details: Optional[str] = None

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.primitive_name:
            raise ValueError("PrimitiveFailure missing primitive_name")
        if not self.primitive_version:
            raise ValueError("PrimitiveFailure missing primitive_version")
        if not self.reason:
            raise ValueError("PrimitiveFailure missing reason")

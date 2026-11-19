"""
File: solomon_core/docintel/primitives/primitive_result.py
Phase: 54 — Document Intelligence System Completion
Purpose: Neutral result container for successful primitive execution

This module defines PrimitiveResult, a non-authoritative container
returned by a primitive upon successful execution. It contains raw
output only and is NOT evidence-bound, authorized, or user-visible.

CRITICAL INVARIANTS:
- Results contain no evidence binding
- Results contain no authorization
- Results contain no execution control
- Results are immutable and descriptive only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class PrimitiveResult:
    """
    Raw result produced by a primitive.

    This answers:
        "What did the primitive produce?"

    It does NOT answer:
        - Whether the result is valid
        - Whether it may be shown to a user
        - What should happen next
    """

    primitive_name: str
    primitive_version: str
    payload: Any

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.primitive_name:
            raise ValueError("PrimitiveResult missing primitive_name")
        if not self.primitive_version:
            raise ValueError("PrimitiveResult missing primitive_version")

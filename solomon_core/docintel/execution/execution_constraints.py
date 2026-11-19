"""
File: solomon_core/docintel/execution/execution_constraints.py
Phase: 54 — Document Intelligence System Completion
Purpose: Mechanical constraints applied to authorized execution

This module defines ExecutionConstraints, which impose explicit,
fail-closed limits on how an authorized execution may occur.

CRITICAL INVARIANTS:
- Constraints restrict execution; they never enable it
- No intent, planning, or workflow semantics
- No retries, recovery, or improvisation
- No authority or authorization logic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ExecutionConstraints:
    """
    Mechanical limits on execution behavior.

    These constraints answer:
        "What must execution NOT do?"

    They do NOT answer:
        - How execution is performed
        - Whether execution is authorized
    """

    allow_side_effects: bool = False
    read_only: bool = True
    max_runtime_ms: Optional[int] = None
    allow_network: bool = False

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if self.max_runtime_ms is not None and self.max_runtime_ms <= 0:
            raise ValueError("max_runtime_ms must be > 0 if specified")

        # Enforce consistency
        if self.read_only and self.allow_side_effects:
            raise ValueError(
                "ExecutionConstraints invalid: read_only cannot allow side effects"
            )

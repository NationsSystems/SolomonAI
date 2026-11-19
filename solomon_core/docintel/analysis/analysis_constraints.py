"""
File: solomon_core/docintel/analysis/analysis_constraints.py
Phase: 54 — Document Intelligence System Completion
Purpose: Structural constraints applied to analysis requests

This module defines AnalysisConstraints, which impose explicit, mechanical
limits on how analysis may be performed. These constraints restrict scope;
they do not grant authority or permit execution.

CRITICAL INVARIANTS:
- Constraints restrict behavior; they never enable it
- No execution, authorization, or workflow logic
- No intent inference or recovery semantics
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AnalysisConstraints:
    """
    Mechanical limits applied to analysis behavior.

    These constraints answer:
        "What analysis must NOT do?"

    They do NOT answer:
        - How to perform the analysis
        - Whether analysis is authorized
    """

    allow_cross_document: bool = False
    max_tokens: Optional[int] = None
    require_evidence_declaration: bool = True

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if self.max_tokens is not None and self.max_tokens <= 0:
            raise ValueError("max_tokens must be > 0 if specified")

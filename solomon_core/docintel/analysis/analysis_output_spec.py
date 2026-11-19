"""
File: solomon_core/docintel/analysis/analysis_output_spec.py
Phase: 54 — Document Intelligence System Completion
Purpose: Declarative specification of expected analysis output

This module defines AnalysisOutputSpec, which describes the *shape* and
requirements of analysis output without producing or authorizing results.

CRITICAL INVARIANTS:
- Output specifications are declarative only
- No execution or result creation
- No evidence binding or validation
- No workflow or intent semantics
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class AnalysisOutputSpec:
    """
    Declarative specification of analysis output expectations.

    This answers:
        "What form should the analysis output take?"

    It does NOT answer:
        - Whether output is authorized
        - Whether output is correct
        - How output should be generated
    """

    output_type: str
    require_evidence: bool = True
    max_items: Optional[int] = None

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.output_type:
            raise ValueError("AnalysisOutputSpec missing output_type")
        if self.max_items is not None and self.max_items <= 0:
            raise ValueError("max_items must be > 0 if specified")

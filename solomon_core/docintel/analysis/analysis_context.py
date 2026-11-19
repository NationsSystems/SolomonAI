"""
File: solomon_core/docintel/analysis/analysis_context.py
Phase: 54 — Document Intelligence System Completion
Purpose: Non-authoritative container binding analysis request and constraints

This module defines AnalysisContext, which groups an AnalysisRequest with
explicit AnalysisConstraints. It carries no authority, performs no execution,
and produces no results.

CRITICAL INVARIANTS:
- Context is descriptive only
- No execution or authorization
- No evidence binding or result creation
- No workflow sequencing
"""

from __future__ import annotations

from dataclasses import dataclass

from solomon_core.docintel.analysis.analysis_request import AnalysisRequest
from solomon_core.docintel.analysis.analysis_constraints import AnalysisConstraints


@dataclass(frozen=True)
class AnalysisContext:
    """
    Immutable container for an analysis request and its constraints.

    This object may be passed through planners or analysis primitives,
    but it does not authorize or execute anything.
    """

    request: AnalysisRequest
    constraints: AnalysisConstraints

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if self.request is None:
            raise ValueError("AnalysisContext missing request")
        if self.constraints is None:
            raise ValueError("AnalysisContext missing constraints")

        self.request.assert_valid()
        self.constraints.assert_valid()

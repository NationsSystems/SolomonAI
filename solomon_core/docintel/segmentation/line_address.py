"""
File: solomon_core/docintel/segmentation/line_address.py
Phase: 54 — Document Intelligence System Completion
Purpose: Canonical line-level addressability for document evidence

This module defines LineAddress, which allows evidence to reference
exact line ranges within a document page without semantic interpretation.

CRITICAL INVARIANTS:
- Line addresses are positional and deterministic
- No interpretation, relevance scoring, or intelligence
- No execution or authorization logic
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LineAddress:
    """
    Represents a contiguous range of lines on a document page.
    """

    document_id: str
    page_index: int
    start_line: int
    end_line: int

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.document_id:
            raise ValueError("LineAddress missing document_id")
        if self.page_index < 0:
            raise ValueError("page_index must be >= 0")
        if self.start_line < 0:
            raise ValueError("start_line must be >= 0")
        if self.end_line < self.start_line:
            raise ValueError("end_line must be >= start_line")

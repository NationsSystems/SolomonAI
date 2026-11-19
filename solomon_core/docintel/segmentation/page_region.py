"""
File: solomon_core/docintel/segmentation/page_region.py
Phase: 54 — Document Intelligence System Completion
Purpose: Canonical page-region addressing for evidence anchoring

This module defines a PageRegion, which allows evidence to reference a
specific bounded region on a document page without interpreting meaning.

CRITICAL INVARIANTS:
- Regions are structural and positional only
- No semantic interpretation or relevance scoring
- No execution, authorization, or intelligence logic
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageRegion:
    """
    Represents a bounded region on a single page of a document.

    Coordinates are normalized floats in the range [0.0, 1.0].
    """

    document_id: str
    page_index: int
    x_min: float
    y_min: float
    x_max: float
    y_max: float

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.document_id:
            raise ValueError("PageRegion missing document_id")
        if self.page_index < 0:
            raise ValueError("page_index must be >= 0")

        for name, value in {
            "x_min": self.x_min,
            "y_min": self.y_min,
            "x_max": self.x_max,
            "y_max": self.y_max,
        }.items():
            if not (0.0 <= value <= 1.0):
                raise ValueError(f"{name} must be between 0.0 and 1.0")

        if self.x_max <= self.x_min:
            raise ValueError("x_max must be > x_min")
        if self.y_max <= self.y_min:
            raise ValueError("y_max must be > y_min")

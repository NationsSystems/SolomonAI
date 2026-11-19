"""
File: solomon_core/docintel/evidence/evidence_reference.py
Phase: 54 — Document Intelligence System Completion
Purpose: Canonical reference to document evidence

This module defines EvidenceReference, the atomic pointer used to bind
claims, analysis, and execution results to *verifiable document facts*.

CRITICAL INVARIANTS:
- Evidence references are structural, not semantic
- Evidence references never assert truth or meaning
- Evidence references must be fully addressable
- No execution, authorization, or inference logic
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Union

from solomon_core.docintel.segmentation.chunk import Chunk
from solomon_core.docintel.segmentation.page_region import PageRegion
from solomon_core.docintel.segmentation.line_address import LineAddress


EvidenceAnchor = Union[Chunk, PageRegion, LineAddress]


@dataclass(frozen=True)
class EvidenceReference:
    """
    Canonical reference to a piece of document evidence.

    An EvidenceReference answers only:
        "Where in the document is this fact located?"

    It does NOT answer:
        - What the fact means
        - Whether the fact is sufficient
        - How the fact should be interpreted
    """

    document_id: str
    anchor: EvidenceAnchor
    description: Optional[str] = None

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.document_id:
            raise ValueError("EvidenceReference missing document_id")

        if self.anchor is None:
            raise ValueError("EvidenceReference missing anchor")

        # Anchor-specific validation
        if hasattr(self.anchor, "assert_valid"):
            self.anchor.assert_valid()
        else:
            raise ValueError("EvidenceReference anchor is not a valid anchor type")

        # Ensure anchor document matches reference document
        anchor_doc_id = getattr(self.anchor, "document_id", None)
        if anchor_doc_id and anchor_doc_id != self.document_id:
            raise ValueError(
                "EvidenceReference document_id does not match anchor document_id"
            )

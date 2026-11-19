"""
File: solomon_core/docintel/analysis/analysis_request.py
Phase: 54 — Document Intelligence System Completion
Purpose: Non-authoritative analysis request descriptor

This module defines AnalysisRequest, which describes *what analysis is being
asked for* without granting authority, permission, or execution capability.

CRITICAL INVARIANTS:
- AnalysisRequest is descriptive only
- It does NOT authorize execution
- It does NOT imply intent or workflow
- It does NOT bind evidence or results
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

from solomon_core.docintel.documents.document_identity import DocumentIdentity


@dataclass(frozen=True)
class AnalysisRequest:
    """
    Describes a requested analysis over one or more documents.

    This object may be consumed by analysis primitives or planners,
    but it carries NO authority and performs NO execution.
    """

    analysis_type: str
    documents: Tuple[DocumentIdentity, ...]
    parameters: Tuple[tuple, ...] = ()

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.analysis_type:
            raise ValueError("AnalysisRequest missing analysis_type")
        if not self.documents:
            raise ValueError("AnalysisRequest must reference at least one document")
        for doc in self.documents:
            doc.assert_valid()

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create(
        *,
        analysis_type: str,
        documents: Iterable[DocumentIdentity],
        parameters: Iterable[tuple] = (),
    ) -> "AnalysisRequest":
        docs = tuple(documents)
        if not docs:
            raise ValueError("AnalysisRequest requires at least one document")

        request = AnalysisRequest(
            analysis_type=analysis_type,
            documents=docs,
            parameters=tuple(parameters),
        )

        request.assert_valid()
        return request

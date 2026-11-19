"""
File: solomon_core/docintel/parsing/extraction_metadata.py
Phase: 54 — Document Intelligence System Completion
Purpose: Immutable metadata describing mechanical document extraction

This module records *how* raw text blocks were extracted from a document.
It is strictly descriptive and must never influence interpretation,
authorization, or execution.

CRITICAL INVARIANTS:
- Metadata is descriptive, not normative
- No intelligence, inference, or execution logic
- Immutable once created
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class ExtractionMetadata:
    """
    Describes the mechanical extraction process for a document.

    This answers:
        "How was this content mechanically extracted?"

    It does NOT answer:
        - Whether extraction was correct
        - How content should be interpreted
        - Whether content is sufficient for analysis
    """

    document_id: str
    extractor_name: str
    extractor_version: str
    extracted_utc: str
    notes: Optional[str] = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create(
        *,
        document_id: str,
        extractor_name: str,
        extractor_version: str,
        notes: Optional[str] = None,
    ) -> "ExtractionMetadata":
        if not document_id:
            raise ValueError("document_id is required for ExtractionMetadata")
        if not extractor_name:
            raise ValueError("extractor_name is required for ExtractionMetadata")
        if not extractor_version:
            raise ValueError("extractor_version is required for ExtractionMetadata")

        return ExtractionMetadata(
            document_id=document_id,
            extractor_name=extractor_name,
            extractor_version=extractor_version,
            extracted_utc=datetime.now(timezone.utc).isoformat(),
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.document_id:
            raise ValueError("ExtractionMetadata missing document_id")
        if not self.extractor_name:
            raise ValueError("ExtractionMetadata missing extractor_name")
        if not self.extractor_version:
            raise ValueError("ExtractionMetadata missing extractor_version")
        if not self.extracted_utc:
            raise ValueError("ExtractionMetadata missing extracted_utc")

"""
File: solomon_core/docintel/documents/document_provenance.py
Phase: 54 — Document Intelligence System Completion
Purpose: Immutable provenance record for governed documents

DocumentProvenance records *how* a document entered DocIntel, without
interpreting intent, authority, or purpose. Provenance is factual,
append-only, and never used to make decisions.

CRITICAL INVARIANTS:
- Provenance is descriptive, never normative
- Provenance does NOT imply authorization
- Provenance is immutable once created
- No execution, parsing, or analysis logic exists here
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional


@dataclass(frozen=True)
class DocumentProvenance:
    """
    Immutable provenance metadata for a document.

    This answers only:
        "Where did this document come from?"

    It explicitly does NOT answer:
        - Who is allowed to use it
        - Why it was provided
        - What should be done with it
    """

    document_id: str
    ingested_utc: str
    ingested_by: str
    ingestion_channel: str
    original_filename: Optional[str] = None
    external_reference: Optional[str] = None
    notes: Optional[str] = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def create(
        *,
        document_id: str,
        ingested_by: str,
        ingestion_channel: str,
        original_filename: Optional[str] = None,
        external_reference: Optional[str] = None,
        notes: Optional[str] = None,
    ) -> "DocumentProvenance":
        """
        Create a new immutable provenance record.

        Args:
            document_id: Canonical document_id
            ingested_by: Operator or system identifier
            ingestion_channel: upload, operator, import, etc.
            original_filename: Optional filename at ingestion
            external_reference: Optional external system reference
            notes: Optional freeform notes (non-authoritative)

        Returns:
            DocumentProvenance
        """

        if not document_id:
            raise ValueError("document_id is required for provenance")

        if not ingested_by:
            raise ValueError("ingested_by is required for provenance")

        if not ingestion_channel:
            raise ValueError("ingestion_channel is required for provenance")

        return DocumentProvenance(
            document_id=document_id,
            ingested_utc=datetime.now(timezone.utc).isoformat(),
            ingested_by=ingested_by,
            ingestion_channel=ingestion_channel,
            original_filename=original_filename,
            external_reference=external_reference,
            notes=notes,
        )

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        """Validate required provenance fields."""
        if not self.document_id:
            raise ValueError("Invalid provenance: document_id missing")
        if not self.ingested_utc:
            raise ValueError("Invalid provenance: ingested_utc missing")
        if not self.ingested_by:
            raise ValueError("Invalid provenance: ingested_by missing")
        if not self.ingestion_channel:
            raise ValueError("Invalid provenance: ingestion_channel missing")

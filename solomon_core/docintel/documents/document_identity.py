"""
File: solomon_core/docintel/documents/document_identity.py
Phase: 54 — Document Intelligence System Completion
Purpose: Canonical, immutable identity for governed documents

This module defines the DocumentIdentity object, which provides a
stable, content-derived identity for any document entering DocIntel.

CRITICAL INVARIANTS:
- Identity is deterministic and content-derived
- Identity is immutable once created
- No execution, parsing, or analysis logic exists here
- No authority, intent, or workflow concepts are permitted
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional
import hashlib


@dataclass(frozen=True)
class DocumentIdentity:
    """
    Canonical identity for a document.

    A DocumentIdentity represents *what* a document is, not how it is used.
    It is safe to reference, store, and bind as evidence.

    Once created, a DocumentIdentity MUST NOT change.
    """

    document_id: str
    content_hash: str
    byte_length: int
    created_utc: str
    source_type: str
    source_reference: Optional[str] = None

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @staticmethod
    def from_bytes(
        raw_bytes: bytes,
        *,
        source_type: str,
        source_reference: Optional[str] = None
    ) -> "DocumentIdentity":
        """
        Create a DocumentIdentity from raw document bytes.

        This is the ONLY supported way to create a DocumentIdentity.

        Args:
            raw_bytes: Exact byte content of the document
            source_type: Origin classification (e.g. upload, operator, db)
            source_reference: Optional external reference (filename, id, etc.)

        Returns:
            DocumentIdentity (immutable)
        """

        if not raw_bytes:
            raise ValueError("DocumentIdentity cannot be created from empty bytes")

        if not source_type:
            raise ValueError("source_type is required to create DocumentIdentity")

        content_hash = hashlib.sha256(raw_bytes).hexdigest()

        document_id = f"doc:{content_hash}"

        created_utc = datetime.now(timezone.utc).isoformat()

        return DocumentIdentity(
            document_id=document_id,
            content_hash=content_hash,
            byte_length=len(raw_bytes),
            created_utc=created_utc,
            source_type=source_type,
            source_reference=source_reference,
        )

    # ------------------------------------------------------------------
    # Safety Guarantees
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        """
        Defensive validation hook for invariants.
        Intended for registry or ingestion-time checks.
        """

        if not self.document_id.startswith("doc:"):
            raise ValueError("Invalid document_id prefix")

        if len(self.content_hash) != 64:
            raise ValueError("Invalid SHA-256 content hash length")

        if self.byte_length <= 0:
            raise ValueError("Invalid byte_length for document")

        if not self.created_utc:
            raise ValueError("created_utc timestamp missing")

        if not self.source_type:
            raise ValueError("source_type missing")


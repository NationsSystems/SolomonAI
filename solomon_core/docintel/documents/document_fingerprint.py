"""
File: solomon_core/docintel/documents/document_fingerprint.py
Phase: 54 — Document Intelligence System Completion
Purpose: Canonical content fingerprinting for governed documents

This module produces deterministic, structural fingerprints for document
content. Fingerprints are used for comparison, evidence anchoring, and
integrity checks — never for authorization or inference.

CRITICAL INVARIANTS:
- Fingerprints are deterministic and content-derived
- Fingerprints do NOT imply semantic meaning
- No execution, parsing, or analysis logic exists here
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List
import hashlib


@dataclass(frozen=True)
class PageFingerprint:
    """
    Fingerprint for a single page or logical unit of a document.
    """
    index: int
    content_hash: str
    byte_length: int


@dataclass(frozen=True)
class DocumentFingerprint:
    """
    Structural fingerprint of an entire document.

    This captures the shape of the document without interpretation.
    """
    document_id: str
    total_bytes: int
    page_fingerprints: List[PageFingerprint]

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.document_id:
            raise ValueError("DocumentFingerprint missing document_id")
        if self.total_bytes <= 0:
            raise ValueError("Invalid total_bytes for DocumentFingerprint")
        if not self.page_fingerprints:
            raise ValueError("DocumentFingerprint must contain page_fingerprints")


# ----------------------------------------------------------------------
# Fingerprinting Helpers
# ----------------------------------------------------------------------

def fingerprint_pages(pages: Iterable[bytes]) -> List[PageFingerprint]:
    """
    Generate PageFingerprint objects for an iterable of page byte blocks.

    Args:
        pages: Iterable of raw page bytes in canonical order

    Returns:
        List[PageFingerprint]
    """

    fingerprints: List[PageFingerprint] = []

    for index, page_bytes in enumerate(pages):
        if not page_bytes:
            raise ValueError(f"Empty page content at index {index}")

        content_hash = hashlib.sha256(page_bytes).hexdigest()
        fingerprints.append(
            PageFingerprint(
                index=index,
                content_hash=content_hash,
                byte_length=len(page_bytes),
            )
        )

    return fingerprints


def fingerprint_document(
    *,
    document_id: str,
    raw_bytes: bytes,
    pages: Iterable[bytes],
) -> DocumentFingerprint:
    """
    Produce a DocumentFingerprint from raw document bytes and page segments.

    Args:
        document_id: Canonical document_id
        raw_bytes: Full document byte content
        pages: Iterable of page-level byte content

    Returns:
        DocumentFingerprint
    """

    if not raw_bytes:
        raise ValueError("Cannot fingerprint empty document bytes")

    page_fingerprints = fingerprint_pages(pages)

    fingerprint = DocumentFingerprint(
        document_id=document_id,
        total_bytes=len(raw_bytes),
        page_fingerprints=page_fingerprints,
    )

    fingerprint.assert_valid()
    return fingerprint

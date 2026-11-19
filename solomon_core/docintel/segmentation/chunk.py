"""
File: solomon_core/docintel/segmentation/chunk.py
Phase: 54 — Document Intelligence System Completion
Purpose: Canonical, addressable text chunk for evidence anchoring

This module defines the Chunk object, which represents the smallest
addressable unit of document content used by DocIntel.

CRITICAL INVARIANTS:
- Chunks are mechanically derived, not interpreted
- Chunks are immutable and addressable
- Chunks do NOT imply meaning or intent
- Chunks exist solely to support evidence anchoring
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class Chunk:
    """
    Canonical addressable text chunk.

    A Chunk represents a bounded region of text within a document that
    can be referenced as evidence.
    """

    document_id: str
    page_index: int
    chunk_index: int
    text: str
    start_offset: int
    end_offset: int
    source_block_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Defensive Validation
    # ------------------------------------------------------------------

    def assert_valid(self) -> None:
        if not self.document_id:
            raise ValueError("Chunk missing document_id")
        if self.page_index < 0:
            raise ValueError("Chunk page_index must be >= 0")
        if self.chunk_index < 0:
            raise ValueError("Chunk chunk_index must be >= 0")
        if self.start_offset < 0:
            raise ValueError("Chunk start_offset must be >= 0")
        if self.end_offset < self.start_offset:
            raise ValueError("Chunk end_offset must be >= start_offset")
        if not isinstance(self.text, str):
            raise ValueError("Chunk text must be a string")

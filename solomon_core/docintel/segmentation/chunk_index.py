"""
File: solomon_core/docintel/segmentation/chunk_index.py
Phase: 54 — Document Intelligence System Completion
Purpose: Deterministic indexing and lookup for document chunks

This module provides a minimal, non-intelligent index over Chunk objects.
It exists to make chunks discoverable and referenceable without implying
semantic relevance or priority.

CRITICAL INVARIANTS:
- Indexing is deterministic and order-preserving
- No scoring, ranking, or semantic interpretation
- No execution, authorization, or analysis logic
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Tuple
from threading import RLock

from solomon_core.docintel.segmentation.chunk import Chunk


class ChunkIndex:
    """
    Deterministic index for Chunk objects.

    The ChunkIndex answers only structural questions:
        - What chunks exist?
        - Where are they located?
    """

    def __init__(self) -> None:
        self._by_document: Dict[str, List[Chunk]] = {}
        self._by_location: Dict[Tuple[str, int, int], Chunk] = {}
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Indexing
    # ------------------------------------------------------------------

    def index_chunks(self, chunks: Iterable[Chunk]) -> None:
        """
        Index a collection of chunks.

        Args:
            chunks: Iterable of Chunk objects
        """

        with self._lock:
            for chunk in chunks:
                chunk.assert_valid()

                doc_chunks = self._by_document.setdefault(chunk.document_id, [])
                doc_chunks.append(chunk)

                key = (chunk.document_id, chunk.page_index, chunk.chunk_index)
                if key in self._by_location:
                    raise ValueError(f"Duplicate chunk location detected: {key}")

                self._by_location[key] = chunk

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_document_chunks(self, document_id: str) -> List[Chunk]:
        """
        Retrieve all chunks for a document in insertion order.
        """
        with self._lock:
            return list(self._by_document.get(document_id, []))

    def get_chunk(
        self,
        *,
        document_id: str,
        page_index: int,
        chunk_index: int
    ) -> Chunk:
        """
        Retrieve a single chunk by exact location.
        """
        key = (document_id, page_index, chunk_index)
        with self._lock:
            return self._by_location[key]

    # ------------------------------------------------------------------
    # Introspection (Operator / Diagnostic Only)
    # ------------------------------------------------------------------

    def count(self) -> int:
        """Return total number of indexed chunks."""
        with self._lock:
            return len(self._by_location)

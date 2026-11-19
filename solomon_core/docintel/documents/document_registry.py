"""
File: solomon_core/docintel/documents/document_registry.py
Phase: 54 — Document Intelligence System Completion
Purpose: Authoritative registry for governed documents

The DocumentRegistry is the single source of truth for which documents
exist inside DocIntel. It enforces identity uniqueness, immutability,
and prevents duplicate or ambiguous document presence.

CRITICAL INVARIANTS:
- A document is registered exactly once per content hash
- Registration is explicit and deterministic
- Registry performs NO parsing, execution, or analysis
- Registry does NOT infer intent or recover from errors
"""

from __future__ import annotations

from typing import Dict, Iterable
from threading import RLock

from solomon_core.docintel.documents.document_identity import DocumentIdentity


class DocumentRegistry:
    """
    In-memory authoritative registry of DocumentIdentity objects.

    This registry answers one question only:
        "Is this document known and governed?"

    Persistence, parsing, and execution are explicitly out of scope.
    """

    def __init__(self) -> None:
        self._by_id: Dict[str, DocumentIdentity] = {}
        self._by_hash: Dict[str, DocumentIdentity] = {}
        self._lock = RLock()

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, identity: DocumentIdentity) -> DocumentIdentity:
        """
        Register a DocumentIdentity.

        If a document with the same content hash already exists,
        the existing identity is returned and no mutation occurs.

        Args:
            identity: DocumentIdentity to register

        Returns:
            Canonical DocumentIdentity stored in the registry
        """

        identity.assert_valid()

        with self._lock:
            existing = self._by_hash.get(identity.content_hash)
            if existing is not None:
                return existing

            self._by_id[identity.document_id] = identity
            self._by_hash[identity.content_hash] = identity
            return identity

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get_by_id(self, document_id: str) -> DocumentIdentity:
        """
        Retrieve a DocumentIdentity by document_id.

        Raises KeyError if not found.
        """

        with self._lock:
            return self._by_id[document_id]

    def get_by_hash(self, content_hash: str) -> DocumentIdentity:
        """
        Retrieve a DocumentIdentity by content hash.

        Raises KeyError if not found.
        """

        with self._lock:
            return self._by_hash[content_hash]

    def contains(self, document_id: str) -> bool:
        """Check if a document_id is registered."""
        with self._lock:
            return document_id in self._by_id

    # ------------------------------------------------------------------
    # Introspection (Operator / Diagnostic Only)
    # ------------------------------------------------------------------

    def all_documents(self) -> Iterable[DocumentIdentity]:
        """Return an immutable snapshot of all registered documents."""
        with self._lock:
            return tuple(self._by_id.values())

    def count(self) -> int:
        """Return number of registered documents."""
        with self._lock:
            return len(self._by_id)

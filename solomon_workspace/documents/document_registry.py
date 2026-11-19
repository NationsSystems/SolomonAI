# -------------------------------------------------------------------
# FILE: document_registry.py
# DIRECTORY: solomon_workspace/documents/
# -------------------------------------------------------------------
# In-memory workspace document registry.
# -------------------------------------------------------------------

from typing import Any, Dict, Iterable, List, Optional

from solomon_workspace.documents.document_metadata import (
    WorkspaceDocumentMetadata,
    build_workspace_document_metadata,
)


class WorkspaceDocumentRegistry:
    """Small registry for documents known to a workspace session."""

    def __init__(self) -> None:
        self._documents: Dict[str, WorkspaceDocumentMetadata] = {}

    def add(self, metadata: WorkspaceDocumentMetadata) -> WorkspaceDocumentMetadata:
        """Register or replace a workspace document."""

        self._documents[metadata.document_id] = metadata
        return metadata

    def get(self, document_id: str) -> Optional[WorkspaceDocumentMetadata]:
        """Return a registered document by id."""

        return self._documents.get(str(document_id or "").strip())

    def remove(self, document_id: str) -> Optional[WorkspaceDocumentMetadata]:
        """Remove and return a registered document by id."""

        return self._documents.pop(str(document_id or "").strip(), None)

    def contains(self, document_id: str) -> bool:
        """Return whether the registry contains a document id."""

        return self.get(document_id) is not None

    def list_documents(self) -> List[WorkspaceDocumentMetadata]:
        """Return all registered documents in insertion order."""

        return list(self._documents.values())

    def list_ids(self) -> List[str]:
        """Return all registered document ids."""

        return list(self._documents.keys())

    def clear(self) -> None:
        """Remove all registered documents."""

        self._documents.clear()

    def extend(
        self,
        documents: Iterable[WorkspaceDocumentMetadata],
    ) -> List[WorkspaceDocumentMetadata]:
        """Register multiple workspace documents."""

        registered = []

        for metadata in documents:
            registered.append(self.add(metadata))

        return registered

    def replace_from_list(self, documents: Iterable[Dict[str, Any]]) -> List[WorkspaceDocumentMetadata]:
        """Replace registry contents from JSON-safe document metadata."""

        self.clear()
        restored = []

        for payload in documents or []:
            metadata = build_workspace_document_metadata_from_dict(payload)

            if metadata:
                restored.append(self.add(metadata))

        return restored

    def to_list(self) -> List[dict]:
        """Return a JSON-safe list of registered documents."""

        return [metadata.to_dict() for metadata in self.list_documents()]


def build_workspace_document_metadata_from_dict(
    payload: Any,
) -> Optional[WorkspaceDocumentMetadata]:
    """Rebuild workspace document metadata from a JSON-safe payload."""

    if isinstance(payload, WorkspaceDocumentMetadata):
        return payload

    if not isinstance(payload, dict):
        return None

    source_path = str(payload.get("source_path", "")).strip()

    if not source_path:
        return None

    return build_workspace_document_metadata(
        source_path,
        document_id=payload.get("document_id"),
        title=payload.get("title"),
        source_name=payload.get("source_name"),
        created_by=payload.get("created_by"),
        workspace_id=payload.get("workspace_id"),
        size_bytes=payload.get("size_bytes"),
        extra=payload.get("extra") if isinstance(payload.get("extra"), dict) else None,
    )


__all__ = [
    "WorkspaceDocumentRegistry",
    "build_workspace_document_metadata_from_dict",
]
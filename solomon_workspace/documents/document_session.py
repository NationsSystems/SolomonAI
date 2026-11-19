# -------------------------------------------------------------------
# FILE: document_session.py
# DIRECTORY: solomon_workspace/documents/
# -------------------------------------------------------------------
# Workspace document session state.
# -------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from solomon_workspace.documents.document_metadata import WorkspaceDocumentMetadata
from solomon_workspace.documents.document_registry import WorkspaceDocumentRegistry


@dataclass
class WorkspaceDocumentSession:
    """Tracks open and active documents for a workspace session."""

    workspace_id: str
    registry: WorkspaceDocumentRegistry = field(default_factory=WorkspaceDocumentRegistry)
    active_document_id: Optional[str] = None

    def open_document(
        self,
        metadata: WorkspaceDocumentMetadata,
    ) -> WorkspaceDocumentMetadata:
        """Register a document and set it active."""

        self.registry.add(metadata)
        self.active_document_id = metadata.document_id
        return metadata

    def close_document(self, document_id: str) -> Optional[WorkspaceDocumentMetadata]:
        """Close a document and adjust active document state."""

        clean_id = str(document_id or "").strip()
        removed = self.registry.remove(clean_id)

        if self.active_document_id == clean_id:
            remaining = self.registry.list_documents()
            self.active_document_id = remaining[-1].document_id if remaining else None

        return removed

    def set_active_document(
        self,
        document_id: str,
    ) -> Optional[WorkspaceDocumentMetadata]:
        """Set the active document when it exists in the session."""

        metadata = self.registry.get(document_id)

        if not metadata:
            return None

        self.active_document_id = metadata.document_id
        return metadata

    def get_active_document(self) -> Optional[WorkspaceDocumentMetadata]:
        """Return the active document metadata."""

        if not self.active_document_id:
            return None

        return self.registry.get(self.active_document_id)

    def list_open_documents(self) -> List[WorkspaceDocumentMetadata]:
        """Return all open workspace documents."""

        return self.registry.list_documents()

    def replace_from_dict(self, payload: Any) -> None:
        """Replace this session state from a JSON-safe payload."""

        if not isinstance(payload, dict):
            self.registry.clear()
            self.active_document_id = None
            return

        workspace_id = str(payload.get("workspace_id") or self.workspace_id).strip()
        if workspace_id:
            self.workspace_id = workspace_id

        documents = payload.get("documents")
        self.registry.replace_from_list(documents if isinstance(documents, list) else [])

        requested_active_id = str(payload.get("active_document_id") or "").strip()
        if requested_active_id and self.registry.contains(requested_active_id):
            self.active_document_id = requested_active_id
            return

        remaining = self.registry.list_documents()
        self.active_document_id = remaining[-1].document_id if remaining else None

    def to_dict(self) -> dict:
        """Return a JSON-safe representation of the document session."""

        active = self.get_active_document()

        return {
            "workspace_id": self.workspace_id,
            "active_document_id": self.active_document_id,
            "active_document": active.to_dict() if active else None,
            "documents": self.registry.to_list(),
        }


def build_workspace_document_session_from_dict(
    payload: Any,
    *,
    workspace_id: str,
) -> WorkspaceDocumentSession:
    """Build a workspace document session from JSON-safe state."""

    session = WorkspaceDocumentSession(workspace_id=str(workspace_id or "workspace").strip())
    session.replace_from_dict(payload)
    return session


__all__ = [
    "WorkspaceDocumentSession",
    "build_workspace_document_session_from_dict",
]
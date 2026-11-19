# -------------------------------------------------------------------
# FILE: active_document_context.py
# DIRECTORY: solomon_workspace/context/
# -------------------------------------------------------------------
# Active document context exposed to SolomonAI.
# -------------------------------------------------------------------

from dataclasses import dataclass
from typing import Optional

from solomon_workspace.documents.document_metadata import WorkspaceDocumentMetadata


@dataclass(frozen=True)
class ActiveDocumentContext:
    """Controlled context for the currently active workspace document."""

    document_id: Optional[str]
    title: Optional[str]
    document_type: Optional[str]
    viewer_type: Optional[str]
    type_label: Optional[str]
    supported: bool
    source_name: Optional[str] = None

    def to_dict(self) -> dict:
        """Return a JSON-safe active document context packet."""

        return {
            "document_id": self.document_id,
            "title": self.title,
            "document_type": self.document_type,
            "viewer_type": self.viewer_type,
            "type_label": self.type_label,
            "supported": self.supported,
            "source_name": self.source_name,
        }


def build_active_document_context(
    metadata: Optional[WorkspaceDocumentMetadata],
) -> ActiveDocumentContext:
    """Build active document context from metadata."""

    if not metadata:
        return ActiveDocumentContext(
            document_id=None,
            title=None,
            document_type=None,
            viewer_type=None,
            type_label=None,
            supported=False,
            source_name=None,
        )

    return ActiveDocumentContext(
        document_id=metadata.document_id,
        title=metadata.title,
        document_type=metadata.document_type.value,
        viewer_type=metadata.viewer_type.value,
        type_label=metadata.type_label,
        supported=metadata.supported,
        source_name=metadata.source_name,
    )


__all__ = [
    "ActiveDocumentContext",
    "build_active_document_context",
]
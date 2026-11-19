# -------------------------------------------------------------------
# FILE: document_metadata.py
# DIRECTORY: solomon_workspace/documents/
# -------------------------------------------------------------------
# Immutable metadata contract for Solomon workspace documents.
# -------------------------------------------------------------------

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional
from uuid import uuid4

from solomon_workspace.documents.document_types import (
    WorkspaceDocumentType,
    WorkspaceViewerType,
    get_document_type_for_path,
    get_document_type_label,
    get_extension_from_path,
    get_viewer_type_for_document_type,
    is_supported_workspace_document,
)


@dataclass(frozen=True)
class WorkspaceDocumentMetadata:
    """Canonical metadata for a document opened inside a Solomon workspace."""

    document_id: str
    title: str
    source_path: str
    extension: str
    document_type: WorkspaceDocumentType
    viewer_type: WorkspaceViewerType
    type_label: str
    supported: bool
    size_bytes: Optional[int] = None
    source_name: Optional[str] = None
    created_by: Optional[str] = None
    workspace_id: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe representation of the metadata."""

        payload = asdict(self)
        payload["document_type"] = self.document_type.value
        payload["viewer_type"] = self.viewer_type.value
        return payload


def build_workspace_document_metadata(
    source_path: str,
    *,
    document_id: Optional[str] = None,
    title: Optional[str] = None,
    source_name: Optional[str] = None,
    created_by: Optional[str] = None,
    workspace_id: Optional[str] = None,
    size_bytes: Optional[int] = None,
    extra: Optional[Dict[str, Any]] = None,
) -> WorkspaceDocumentMetadata:
    """Build metadata for a document path or uploaded file reference."""

    clean_path = str(source_path or "").strip()
    path = Path(clean_path)
    extension = get_extension_from_path(clean_path)
    document_type = get_document_type_for_path(clean_path)
    viewer_type = get_viewer_type_for_document_type(document_type)
    resolved_title = str(title or path.name or "Untitled Document").strip()

    return WorkspaceDocumentMetadata(
        document_id=str(document_id or uuid4()),
        title=resolved_title,
        source_path=clean_path,
        extension=extension,
        document_type=document_type,
        viewer_type=viewer_type,
        type_label=get_document_type_label(document_type),
        supported=is_supported_workspace_document(clean_path),
        size_bytes=size_bytes,
        source_name=source_name,
        created_by=created_by,
        workspace_id=workspace_id,
        extra=dict(extra or {}),
    )


__all__ = [
    "WorkspaceDocumentMetadata",
    "build_workspace_document_metadata",
]
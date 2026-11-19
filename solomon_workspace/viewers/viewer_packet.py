# -------------------------------------------------------------------
# FILE: viewer_packet.py
# DIRECTORY: solomon_workspace/viewers/
# -------------------------------------------------------------------
# Shared viewer packet contract for Solomon workspace document viewers.
# -------------------------------------------------------------------

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from solomon_workspace.documents.document_metadata import WorkspaceDocumentMetadata


@dataclass(frozen=True)
class WorkspaceViewerPacket:
    """Canonical render packet for a workspace document viewer."""

    document_id: str
    viewer_type: str
    title: str
    supported: bool
    source_path: str
    document_type: str
    type_label: str
    actions: List[str] = field(default_factory=list)
    display: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Return a JSON-safe viewer packet."""

        return asdict(self)


def build_workspace_viewer_packet(
    metadata: WorkspaceDocumentMetadata,
    *,
    actions: Optional[List[str]] = None,
    display: Optional[Dict[str, Any]] = None,
    message: Optional[str] = None,
) -> WorkspaceViewerPacket:
    """Build a standard viewer packet from workspace document metadata."""

    return WorkspaceViewerPacket(
        document_id=metadata.document_id,
        viewer_type=metadata.viewer_type.value,
        title=metadata.title,
        supported=metadata.supported,
        source_path=metadata.source_path,
        document_type=metadata.document_type.value,
        type_label=metadata.type_label,
        actions=list(actions or []),
        display=dict(display or {}),
        metadata=metadata.to_dict(),
        message=message,
    )


def build_unsupported_viewer_packet(
    metadata: WorkspaceDocumentMetadata,
    *,
    message: Optional[str] = None,
) -> WorkspaceViewerPacket:
    """Build a standard unsupported-document viewer packet."""

    return build_workspace_viewer_packet(
        metadata,
        actions=[],
        display={
            "mode": "unsupported",
            "extension": metadata.extension,
        },
        message=message or "This document type is not supported by the workspace viewer.",
    )


__all__ = [
    "WorkspaceViewerPacket",
    "build_workspace_viewer_packet",
    "build_unsupported_viewer_packet",
]
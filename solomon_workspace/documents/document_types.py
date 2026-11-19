# -------------------------------------------------------------------
# FILE: document_types.py
# DIRECTORY: solomon_workspace/documents/
# -------------------------------------------------------------------
# Canonical workspace document type definitions.
# These are Solomon-native document categories, not vendor app names.
# -------------------------------------------------------------------

from enum import Enum
from pathlib import Path
from typing import Dict, FrozenSet, Optional


class WorkspaceDocumentType(str, Enum):
    """Supported high-level document categories for Solomon workspaces."""

    PDF = "pdf"
    IMAGE = "image"
    TEXT_DOCUMENT = "text_document"
    SPREADSHEET = "spreadsheet"
    UNKNOWN = "unknown"


class WorkspaceViewerType(str, Enum):
    """Viewer families available to the workspace substrate."""

    PDF_VIEWER = "pdf_viewer"
    IMAGE_VIEWER = "image_viewer"
    TEXT_DOCUMENT_VIEWER = "text_document_viewer"
    SPREADSHEET_VIEWER = "spreadsheet_viewer"
    UNSUPPORTED_VIEWER = "unsupported_viewer"


PDF_EXTENSIONS: FrozenSet[str] = frozenset({
    ".pdf",
})

IMAGE_EXTENSIONS: FrozenSet[str] = frozenset({
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".bmp",
    ".webp",
    ".tif",
    ".tiff",
})

TEXT_DOCUMENT_EXTENSIONS: FrozenSet[str] = frozenset({
    ".docx",
    ".doc",
    ".txt",
    ".rtf",
    ".md",
})

SPREADSHEET_EXTENSIONS: FrozenSet[str] = frozenset({
    ".xlsx",
    ".xls",
    ".csv",
})

SUPPORTED_EXTENSIONS: FrozenSet[str] = frozenset(
    PDF_EXTENSIONS
    | IMAGE_EXTENSIONS
    | TEXT_DOCUMENT_EXTENSIONS
    | SPREADSHEET_EXTENSIONS
)

_EXTENSION_TYPE_MAP: Dict[str, WorkspaceDocumentType] = {
    **{extension: WorkspaceDocumentType.PDF for extension in PDF_EXTENSIONS},
    **{extension: WorkspaceDocumentType.IMAGE for extension in IMAGE_EXTENSIONS},
    **{
        extension: WorkspaceDocumentType.TEXT_DOCUMENT
        for extension in TEXT_DOCUMENT_EXTENSIONS
    },
    **{
        extension: WorkspaceDocumentType.SPREADSHEET
        for extension in SPREADSHEET_EXTENSIONS
    },
}

_VIEWER_TYPE_MAP: Dict[WorkspaceDocumentType, WorkspaceViewerType] = {
    WorkspaceDocumentType.PDF: WorkspaceViewerType.PDF_VIEWER,
    WorkspaceDocumentType.IMAGE: WorkspaceViewerType.IMAGE_VIEWER,
    WorkspaceDocumentType.TEXT_DOCUMENT: WorkspaceViewerType.TEXT_DOCUMENT_VIEWER,
    WorkspaceDocumentType.SPREADSHEET: WorkspaceViewerType.SPREADSHEET_VIEWER,
    WorkspaceDocumentType.UNKNOWN: WorkspaceViewerType.UNSUPPORTED_VIEWER,
}


def normalize_extension(value: str) -> str:
    """Return a normalized lowercase extension with a leading dot."""

    clean_value = str(value or "").strip().lower()

    if not clean_value:
        return ""

    if clean_value.startswith("."):
        return clean_value

    return f".{clean_value}"


def get_extension_from_path(path: str) -> str:
    """Return the normalized extension from a file path or filename."""

    return normalize_extension(Path(str(path or "")).suffix)


def get_document_type_for_extension(extension: str) -> WorkspaceDocumentType:
    """Resolve a workspace document type from an extension."""

    normalized = normalize_extension(extension)
    return _EXTENSION_TYPE_MAP.get(normalized, WorkspaceDocumentType.UNKNOWN)


def get_document_type_for_path(path: str) -> WorkspaceDocumentType:
    """Resolve a workspace document type from a path or filename."""

    return get_document_type_for_extension(get_extension_from_path(path))


def get_viewer_type_for_document_type(
    document_type: WorkspaceDocumentType,
) -> WorkspaceViewerType:
    """Resolve the workspace viewer family for a document type."""

    return _VIEWER_TYPE_MAP.get(
        document_type,
        WorkspaceViewerType.UNSUPPORTED_VIEWER,
    )


def get_viewer_type_for_path(path: str) -> WorkspaceViewerType:
    """Resolve the workspace viewer family from a path or filename."""

    document_type = get_document_type_for_path(path)
    return get_viewer_type_for_document_type(document_type)


def is_supported_extension(extension: str) -> bool:
    """Return whether the extension is supported by the workspace substrate."""

    return normalize_extension(extension) in SUPPORTED_EXTENSIONS


def is_supported_workspace_document(path: str) -> bool:
    """Return whether a path or filename maps to a supported document type."""

    return get_document_type_for_path(path) != WorkspaceDocumentType.UNKNOWN


def get_supported_extensions_for_type(
    document_type: WorkspaceDocumentType,
) -> FrozenSet[str]:
    """Return supported extensions for a workspace document type."""

    if document_type == WorkspaceDocumentType.PDF:
        return PDF_EXTENSIONS

    if document_type == WorkspaceDocumentType.IMAGE:
        return IMAGE_EXTENSIONS

    if document_type == WorkspaceDocumentType.TEXT_DOCUMENT:
        return TEXT_DOCUMENT_EXTENSIONS

    if document_type == WorkspaceDocumentType.SPREADSHEET:
        return SPREADSHEET_EXTENSIONS

    return frozenset()


def get_document_type_label(document_type: WorkspaceDocumentType) -> str:
    """Return a user-facing label for a workspace document type."""

    labels = {
        WorkspaceDocumentType.PDF: "PDF Document",
        WorkspaceDocumentType.IMAGE: "Image Document",
        WorkspaceDocumentType.TEXT_DOCUMENT: "Text Document",
        WorkspaceDocumentType.SPREADSHEET: "Spreadsheet",
        WorkspaceDocumentType.UNKNOWN: "Unsupported Document",
    }

    return labels.get(document_type, "Unsupported Document")


__all__ = [
    "WorkspaceDocumentType",
    "WorkspaceViewerType",
    "PDF_EXTENSIONS",
    "IMAGE_EXTENSIONS",
    "TEXT_DOCUMENT_EXTENSIONS",
    "SPREADSHEET_EXTENSIONS",
    "SUPPORTED_EXTENSIONS",
    "normalize_extension",
    "get_extension_from_path",
    "get_document_type_for_extension",
    "get_document_type_for_path",
    "get_viewer_type_for_document_type",
    "get_viewer_type_for_path",
    "is_supported_extension",
    "is_supported_workspace_document",
    "get_supported_extensions_for_type",
    "get_document_type_label",
]
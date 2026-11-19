# -------------------------------------------------------------------
# FILE: workspace_reader_urls.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# URL builders for first-party Solomon workspace reader routes.
# -------------------------------------------------------------------

from urllib.parse import quote


def normalize_document_id(document_id: str) -> str:
    """Return a normalized document id for registry lookup."""

    return str(document_id or "").strip()


def encode_document_id(document_id: str) -> str:
    """Return a URL-safe document id."""

    return quote(normalize_document_id(document_id), safe="")


def build_workspace_document_reader_url(document_id: str) -> str:
    """Build the canonical first-party reader URL for a workspace file."""

    return f"/workspace/file/{encode_document_id(document_id)}/reader"


def build_workspace_document_page_image_url(
    document_id: str,
    page_number: int,
) -> str:
    """Build a first-party rendered page image URL."""

    return (
        f"/workspace/file/{encode_document_id(document_id)}"
        f"/reader/page/{int(page_number)}.png"
    )
# -------------------------------------------------------------------
# FILE: __init__.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# First-party Solomon workspace reader package.
# -------------------------------------------------------------------

from solomon_core.workspace_reader.workspace_reader_urls import (
    build_workspace_document_page_image_url,
    build_workspace_document_reader_url,
)

__all__ = [
    "build_workspace_document_page_image_url",
    "build_workspace_document_reader_url",
]
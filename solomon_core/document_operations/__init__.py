# -------------------------------------------------------------------
# FILE: __init__.py
# DIRECTORY: solomon_core/document_operations/
# -------------------------------------------------------------------
# Document operation registry exports.
# -------------------------------------------------------------------

from .operation_registry import (
    DocumentOperation,
    get_document_operation,
    list_document_operations,
)

__all__ = [
    "DocumentOperation",
    "get_document_operation",
    "list_document_operations",
]
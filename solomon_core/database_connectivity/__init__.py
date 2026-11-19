# ------------------------------------------------------------------
# FILE: __init__.py
# DIRECTORY: solomon_core/database_connectivity/
# ------------------------------------------------------------------
# Governed external relational-database connectivity substrate.
#
# Engine adapters remain below this package. Source/application adapters map
# approved external-system surfaces into generic Solomon semantic evidence.
# ------------------------------------------------------------------

from .contracts import (
    ApprovedReadQuery,
    DatabaseAdapterError,
    DatabaseHealth,
    ReadFilter,
    ReadOrder,
    StructuredEvidencePacket,
    StructuredEvidenceRecord,
)

__all__ = [
    "ApprovedReadQuery",
    "DatabaseAdapterError",
    "DatabaseHealth",
    "ReadFilter",
    "ReadOrder",
    "StructuredEvidencePacket",
    "StructuredEvidenceRecord",
]

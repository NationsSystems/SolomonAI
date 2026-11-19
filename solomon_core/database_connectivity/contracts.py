# ------------------------------------------------------------------
# FILE: contracts.py
# DIRECTORY: solomon_core/database_connectivity/
# ------------------------------------------------------------------
# Database-engine-neutral contracts for governed external structured evidence.
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional, Sequence


STRUCTURED_EVIDENCE_AUTHORITY = "solomon_structured_evidence_v1"


class DatabaseAdapterError(RuntimeError):
    """Stable external-database adapter failure with a bounded error code."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = str(code or "EXTERNAL_DATABASE_ERROR").strip()
        self.message = str(
            message or "External database operation failed."
        ).strip()


@dataclass(frozen=True)
class DatabaseHealth:
    ok: bool
    engine: str
    source_id: str
    database: str
    server: str
    status: str
    detail: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReadFilter:
    """One engine-neutral predicate owned by a source adapter."""

    column: str
    operator: str
    value: Any


@dataclass(frozen=True)
class ReadOrder:
    """One engine-neutral ordering term."""

    column: str
    direction: str = "asc"


@dataclass(frozen=True)
class ApprovedReadQuery:
    """
    One source-adapter-owned bounded relational read plan.

    This contract intentionally contains no raw SQL text. Source/application
    adapters describe approved relations, columns, predicates, ordering, and a
    row ceiling. The physical engine adapter owns SQL dialect compilation and
    parameter binding. Browser input and LLM output never construct this plan.
    """

    operation_id: str
    dataset_id: str
    relation: str
    columns: Sequence[str]
    required_filters: Sequence[ReadFilter] = field(default_factory=tuple)
    match_any_filters: Sequence[ReadFilter] = field(default_factory=tuple)
    order_by: Sequence[ReadOrder] = field(default_factory=tuple)
    max_rows: int = 100


@dataclass(frozen=True)
class StructuredEvidenceRecord:
    record_id: str
    semantic_entity: str
    facts: Dict[str, Any]
    provenance: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class StructuredEvidencePacket:
    source_id: str
    source_type: str
    engine: str
    semantic_operation: str
    dataset_id: str
    retrieved_at: str
    records: List[StructuredEvidenceRecord]
    authority: str = STRUCTURED_EVIDENCE_AUTHORITY
    status: str = "ready"
    error_code: Optional[str] = None
    user_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_id": self.source_id,
            "source_type": self.source_type,
            "engine": self.engine,
            "semantic_operation": self.semantic_operation,
            "dataset_id": self.dataset_id,
            "retrieved_at": self.retrieved_at,
            "records": [record.to_dict() for record in self.records],
            "authority": self.authority,
            "status": self.status,
            "error_code": self.error_code,
            "user_message": self.user_message,
        }

# -------------------------------------------------------------------
# FILE: operation_registry.py
# DIRECTORY: solomon_core/document_operations/
# -------------------------------------------------------------------
# Registry for reusable document operations exposed from the workspace.
# -------------------------------------------------------------------

from dataclasses import asdict, dataclass
from typing import Dict, List, Optional


@dataclass(frozen=True)
class DocumentOperation:
    """Describe one backend operation available for selected documents."""

    key: str
    label: str
    description: str
    workflow_id: str
    requested_action: str
    module: str
    module_label: str
    result_packet_type: str
    requires_documents: bool = True

    def to_dict(self) -> dict:
        """Return a JSON-safe operation description."""

        return asdict(self)


DOCUMENT_ANALYSIS_OPERATION_KEY = "document_analysis"
BEI_WORKFLOW_ID = "pre_award_risk_review"
BEI_REQUESTED_ACTION = "document_review"
BEI_MODULE = "preconstruction"

_OPERATION_ALIASES = {
    "bid_scope_review": DOCUMENT_ANALYSIS_OPERATION_KEY,
}

DOCUMENT_OPERATIONS: Dict[str, DocumentOperation] = {
    DOCUMENT_ANALYSIS_OPERATION_KEY: DocumentOperation(
        key=DOCUMENT_ANALYSIS_OPERATION_KEY,
        label="Analyze document",
        description=(
            "Analyze selected documents for key details, notable issues, "
            "missing information, assumptions, and decision-ready risk signals."
        ),
        workflow_id=BEI_WORKFLOW_ID,
        requested_action=BEI_REQUESTED_ACTION,
        module=BEI_MODULE,
        module_label="Document Intelligence",
        result_packet_type="document_operation_result",
        requires_documents=True,
    ),
}


def normalize_operation_key(value: str) -> str:
    """Return a normalized registry key."""

    clean_value = str(value or "").strip().lower()

    return _OPERATION_ALIASES.get(
        clean_value,
        clean_value,
    )


def get_document_operation(key: str) -> Optional[DocumentOperation]:
    """Return a registered document operation by key."""

    return DOCUMENT_OPERATIONS.get(normalize_operation_key(key))


def list_document_operations() -> List[dict]:
    """Return all registered document operations."""

    return [
        operation.to_dict()
        for operation in DOCUMENT_OPERATIONS.values()
    ]


__all__ = [
    "DocumentOperation",
    "get_document_operation",
    "list_document_operations",
]
# ------------------------------------------------------------------
# FILE: structured_evidence_service.py
# DIRECTORY: solomon_core/database_connectivity/
# ------------------------------------------------------------------
# Request-scoped resolver for approved external structured evidence.
#
# AUTHORITY CONTRACT
#   - Browser input and LLM output never supply SQL, relation names, datasets,
#     credentials, or connection parameters.
#   - Only configured, authenticated Solomon requests may invoke this resolver.
#   - Explicit selected files and explicit public-web selection retain priority.
#   - A source adapter may resolve only a registered semantic operation.
#   - Physical database reads remain bounded and read-only in the engine adapter.
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from config import settings
from solomon_core.logger import get_logger

from .contracts import DatabaseAdapterError, StructuredEvidencePacket
from .generic_business_source import (
    GenericBusinessSourceAdapter,
    SOURCE_ID,
    SOURCE_TYPE,
)
from .mssql_adapter import MssqlExternalDatabaseAdapter


logger = get_logger("structured_evidence_service")


@dataclass(frozen=True)
class StructuredEvidenceResolution:
    matched: bool
    packet: Optional[StructuredEvidencePacket]


def _unavailable_packet(
    *,
    operation,
    error_code: str,
    message: str,
) -> StructuredEvidencePacket:
    return StructuredEvidencePacket(
        source_id=SOURCE_ID,
        source_type=SOURCE_TYPE,
        engine="mssql",
        semantic_operation=str(
            operation.get("operation_id")
            or ""
        ).strip(),
        dataset_id=str(
            operation.get("dataset_id")
            or ""
        ).strip(),
        retrieved_at=datetime.now(
            timezone.utc
        ).isoformat(),
        records=[],
        status="unavailable",
        error_code=error_code,
        user_message=message,
    )


def resolve_structured_evidence_for_request(
    *,
    task_text: str,
    user_id: int,
    request_id: str,
    explicit_source_count: int = 0,
    public_web_selected: bool = False,
) -> StructuredEvidenceResolution:
    """
    Resolve one approved structured-data semantic operation, if applicable.

    This function is deliberately not a natural-language-to-SQL system. It
    delegates deterministic semantic matching to the configured source adapter,
    which emits an ApprovedReadQuery consumed by the engine adapter.
    """

    if not bool(
        settings.EXTERNAL_DATABASE_CONNECTIVITY_ENABLED
    ):
        return StructuredEvidenceResolution(
            False,
            None,
        )

    clean_user_id = int(
        user_id
        or 0
    )

    if clean_user_id <= 0:
        return StructuredEvidenceResolution(
            False,
            None,
        )

    if (
        int(explicit_source_count or 0) > 0
        or bool(public_web_selected)
    ):
        return StructuredEvidenceResolution(
            False,
            None,
        )

    authorization_mode = str(
        settings.EXTERNAL_DATABASE_AUTHORIZATION_MODE
        or ""
    ).strip().lower()

    if authorization_mode != "authenticated_user":
        logger.warning(
            "[STRUCTURED_DB][AUTHORIZATION_MODE_DENIED] "
            "request_id=%s user_id=%s mode=%s",
            request_id,
            clean_user_id,
            authorization_mode,
        )
        return StructuredEvidenceResolution(
            False,
            None,
        )

    configured_source_id = str(
        settings.EXTERNAL_DATABASE_DEFAULT_SOURCE_ID
        or ""
    ).strip()

    if configured_source_id != SOURCE_ID:
        logger.warning(
            "[STRUCTURED_DB][SOURCE_CONFIG_MISMATCH] "
            "request_id=%s configured_source=%s adapter_source=%s",
            request_id,
            configured_source_id,
            SOURCE_ID,
        )
        return StructuredEvidenceResolution(
            False,
            None,
        )

    adapter = MssqlExternalDatabaseAdapter(
        source_id=SOURCE_ID
    )
    source = GenericBusinessSourceAdapter(
        adapter
    )
    operation = source.resolve_operation(
        task_text
    )

    if not operation:
        return StructuredEvidenceResolution(
            False,
            None,
        )

    dataset_id = str(
        operation.get("dataset_id")
        or ""
    ).strip()

    approved_datasets = {
        str(value or "").strip()
        for value in (
            settings.EXTERNAL_DATABASE_ALLOWED_DATASETS
            or ()
        )
        if str(value or "").strip()
    }

    if dataset_id not in approved_datasets:
        logger.warning(
            "[STRUCTURED_DB][DATASET_DENIED] "
            "request_id=%s user_id=%s dataset_id=%s",
            request_id,
            clean_user_id,
            dataset_id,
        )
        return StructuredEvidenceResolution(
            True,
            _unavailable_packet(
                operation=operation,
                error_code=(
                    "EXTERNAL_DATABASE_DATASET_DENIED"
                ),
                message=(
                    "The requested external dataset is not "
                    "approved for Solomon access."
                ),
            ),
        )

    try:
        packet = source.execute(
            operation
        )
    except DatabaseAdapterError as exc:
        logger.warning(
            "[STRUCTURED_DB][READ_FAILED] "
            "request_id=%s user_id=%s operation=%s code=%s",
            request_id,
            clean_user_id,
            operation.get("operation_id"),
            exc.code,
        )
        packet = _unavailable_packet(
            operation=operation,
            error_code=exc.code,
            message=exc.message,
        )

    logger.info(
        "[STRUCTURED_DB][RESOLVED] "
        "request_id=%s user_id=%s operation=%s dataset=%s "
        "status=%s records=%s",
        request_id,
        clean_user_id,
        packet.semantic_operation,
        packet.dataset_id,
        packet.status,
        len(packet.records),
    )

    return StructuredEvidenceResolution(
        True,
        packet,
    )

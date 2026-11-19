# solomon_core/governance/due_process_audit.py
# ------------------------------------------------------------------
# Phase 62 — Due Process Audit Recorder
#
# PURPOSE:
#   Record authoritative Due Process Engine (DPE) rulings.
#   A ruling without a record is legally void.
#
# AUTHORITY:
#   • Write-only
#   • Deterministic
#   • No execution logic
#   • No UX semantics
# ------------------------------------------------------------------

from datetime import datetime
from solomon_core.logger import get_logger
from solomon_core.error_sentinel import record_error

logger = get_logger("due_process_audit")


class DueProcessAuditFailure(Exception):
    """Raised when a DPE ruling cannot be audited."""


def record_dpe_ruling(
    *,
    evidence_hash: str,
    law_artifact_version: str,
    verdict: str,
    matched_law_ids: list[str],
    request_id: str | None = None,
    session_id: str | None = None,
    user_id: str | None = None,
):
    """
    Record a Due Process Engine ruling.

    This function MUST succeed for execution to be considered lawful.
    Failure to record invalidates the ruling.
    """

    try:
        audit_event = {
            "timestamp": datetime.utcnow().isoformat(),
            "evidence_hash": evidence_hash,
            "law_artifact_version": law_artifact_version,
            "verdict": verdict,
            "matched_law_ids": matched_law_ids,
            "request_id": request_id,
            "session_id": session_id,
            "user_id": user_id,
        }

        logger.info(
            "[DPE][RULING_RECORDED]",
            extra=audit_event,
        )

    except Exception as e:
        record_error(
            "due_process_audit_failure",
            type(e).__name__,
            str(e),
        )
        raise DueProcessAuditFailure(
            "Due Process ruling could not be recorded"
        ) from e

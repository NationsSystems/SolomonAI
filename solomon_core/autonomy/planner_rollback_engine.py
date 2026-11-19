# planner_rollback_engine.py — Phase 21 Safe Stub
# -------------------------------------------------------------------
# Phase 21 removes the old llm_planner folder (planner.py).
#
# BUT:
#   • The HFLO system still calls a rollback endpoint.
#   • Admin UI expects rollback logs to exist.
#   • We must preserve DB logging and structure.
#
# So this becomes a SAFE STUB:
#   • Performs NO filesystem restore
#   • Logs rollback requests
#   • Validates patch IDs
#   • Records rollback events in PlannerRollbackLog
#   • Returns a Phase-21-compliant message
# -------------------------------------------------------------------

from datetime import datetime
from pathlib import Path

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from solomon_core.models import PlannerPatchLog, PlannerRollbackLog
from config import settings

logger = get_logger("planner_rollback_engine")


# -------------------------------------------------------------------
# Validation helper: ensure patch exists
# -------------------------------------------------------------------
def _validate_patch_id(session, patch_id: int):
    """
    Confirm the patch exists, even though Phase 21 does not use backups.
    """
    patch = session.query(PlannerPatchLog).filter_by(id=patch_id).first()

    if not patch:
        return None, "Patch ID does not exist."

    # In Phase 21, backup_path is kept only for historical purposes
    return patch, None


# -------------------------------------------------------------------
# PUBLIC ENTRYPOINT — Phase 21 Rollback Stub
# -------------------------------------------------------------------
def rollback_planner_to_patch(patch_id: int, reason: str = None) -> dict:
    """
    Phase 21:
        • No planner code exists to rollback.
        • Instead, log rollback events and return “strict mode” message.
    """

    logger.info(f"[Rollback] Request to rollback patch #{patch_id}")

    # Check if rollbacks are permitted
    if not settings.HFLO_ALLOW_ROLLBACKS:
        return {"ok": False, "error": "Planner rollback disabled in config"}

    session = SessionLocal()

    try:
        patch, err = _validate_patch_id(session, patch_id)
        if err:
            return {"ok": False, "error": err}

        # Phase 21: No actual backup path used
        backup_path = patch.backup_path or "phase21-strict-mode"

        # Log rollback event ONLY — no file restore
        log_entry = PlannerRollbackLog(
            rollback_at=datetime.utcnow(),
            patch_id=patch_id,
            reason=reason or "Manual rollback (Phase 21 strict mode)",
            backup_path=str(backup_path),
            restored_to_version="strict-mode-no-restore",
        )

        session.add(log_entry)
        session.commit()

        logger.info(
            f"[Rollback] Rollback logged in planner_rollback_log (id={log_entry.id})"
        )

        return {
            "ok": False,
            "phase21": True,
            "error": "Planner rollback disabled under Phase 21 strict mode",
        }

    except Exception as e:
        logger.error(f"[Rollback] Internal error: {e}")
        session.rollback()
        return {"ok": False, "error": "Internal rollback failure"}

    finally:
        session.close()


__all__ = ["rollback_planner_to_patch"]

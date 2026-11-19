# planner_patch_applier.py — Phase 21 Safe Stub
# -------------------------------------------------------------------
# In Phase 21, the old patching system that modified llm_planner/planner.py
# is deprecated, because the strict planner lives under:
#
#       solomon_core/planner/
#
# And is not patchable at runtime.
#
# However:
#   • HFLO still expects patch application endpoints to EXIST
#   • Patch logs + rollback logs must remain functional
#   • The sandbox must be callable (even if it always passes)
#
# Therefore this file becomes a SAFETY STUB:
#   • Never touches planner code anymore
#   • Preserves patch logs, rollback logs, throttling, structure validation
#   • Logs that planner patching is disabled under Phase 21
#   • Ensures no import of deleted llm_planner module
# -------------------------------------------------------------------

import traceback
from datetime import datetime, timedelta
from pathlib import Path

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from solomon_core.models import PlannerPatchLog, PlannerRollbackLog
from config import settings

# The sandbox still exists, but now used as a no-op validator
from solomon_core.autonomy.planner_sandbox import run_planner_sandbox

logger = get_logger("planner_patch_applier")

# Patch throttling
_last_patch_time = None


# -------------------------------------------------------------------
# Patch structure validation
# -------------------------------------------------------------------
def _validate_patch_structure(patch_payload: dict) -> bool:
    required = ["ok", "patch_code", "reason", "summary"]
    if not isinstance(patch_payload, dict):
        return False
    for key in required:
        if key not in patch_payload:
            logger.error(f"[PatchValidator] Missing required field: {key}")
            return False
    return True


def _validate_patch_syntax(patch_code: str) -> bool:
    # Phase 21: Patch syntax is irrelevant (planner is not patchable)
    # But we accept only if it's a string.
    return isinstance(patch_code, str)


# -------------------------------------------------------------------
# Logging helpers
# -------------------------------------------------------------------
def _log_patch_record(patch_payload: dict, success: bool):
    session = SessionLocal()
    try:
        entry = PlannerPatchLog(
            applied_at=datetime.utcnow(),
            success=success,
            reason=patch_payload.get("reason"),
            summary=patch_payload.get("summary"),
            patch_code=patch_payload.get("patch_code"),
            backup_path="phase21-strict-mode",
        )
        session.add(entry)
        session.commit()
    except Exception as e:
        logger.error(f"[PatchLog] Failed to save patch log: {e}")
        session.rollback()
    finally:
        session.close()


def _log_rollback(patch_id: int, reason: str):
    session = SessionLocal()
    try:
        entry = PlannerRollbackLog(
            rollback_at=datetime.utcnow(),
            patch_id=patch_id,
            backup_path="phase21-strict-mode",
            reason=reason,
        )
        session.add(entry)
        session.commit()
    except Exception as e:
        logger.error(f"[PatchRollbackLog] Failed: {e}")
        session.rollback()
    finally:
        session.close()


# -------------------------------------------------------------------
# PUBLIC ENTRYPOINT — Phase 21 Safe Stub
# -------------------------------------------------------------------
def apply_planner_patch(patch_payload: dict) -> dict:
    """
    Phase 21:
        The planner is now STRICT and not patchable.
        We preserve:
            • Patch logs
            • Rollback logs
            • Throttling
            • Sandbox call
        But we DO NOT modify any planner files.

    Returns a "safe failure" with logs preserved.
    """

    global _last_patch_time

    logger.info("[PatchApply] Planner patch request received (Phase 21 stub).")

    # HFLO toggles
    if not settings.HFLO_ENABLED:
        return {"ok": False, "error": "HFLO disabled in config"}
    if not settings.HFLO_ALLOW_SKILL_UPGRADES:
        return {"ok": False, "error": "Skill upgrades disabled"}

    # Throttling
    if _last_patch_time:
        next_allowed = _last_patch_time + timedelta(
            minutes=settings.HFLO_UPGRADE_INTERVAL_MINUTES
        )
        if datetime.utcnow() < next_allowed:
            return {"ok": False, "error": "Planner patch throttled — interval not reached"}

    # Validate structure
    if not _validate_patch_structure(patch_payload):
        return {"ok": False, "error": "Invalid patch structure"}

    # Validate syntax (minimal)
    patch_code = patch_payload["patch_code"]
    if not _validate_patch_syntax(patch_code):
        return {"ok": False, "error": "Invalid patch syntax"}

    # Log patch creation (always logs, even in strict mode)
    _log_patch_record(patch_payload, success=True)

    # Phase 21 — Run sandbox as a no-op validator
    sandbox_ok, sandbox_error = run_planner_sandbox()

    if not sandbox_ok:
        logger.error(f"[PatchApply] Sandbox rejected patch: {sandbox_error}")

        # Log rollback
        session = SessionLocal()
        last_patch = (
            session.query(PlannerPatchLog).order_by(PlannerPatchLog.id.desc()).first()
        )
        session.close()

        if last_patch:
            _log_rollback(last_patch.id, sandbox_error)

        return {"ok": False, "error": f"Sandbox rejected patch: {sandbox_error}"}

    # Nothing to apply — strict planner cannot be patched
    _last_patch_time = datetime.utcnow()

    return {
        "ok": False,
        "error": "Planner patching disabled under Phase 21 strict mode",
        "phase21": True,
    }


__all__ = ["apply_planner_patch"]

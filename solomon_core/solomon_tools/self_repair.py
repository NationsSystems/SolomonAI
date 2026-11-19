# self_repair.py — Phase 7.3 (standalone runner enabled)
# -----------------------------------------------------------
# Autonomous integrity repair and recovery system for Solomon.
# This module can repair missing database tables, recreate columns,
# and fix corrupted JSON memory files safely.
#
# It is sandboxed: it never touches reasoning, user logic, or uploads.

import os
import json
import traceback
from datetime import datetime
from solomon_core.logger import get_logger
from solomon_core.db import engine, init_db   # ✅ UPDATED: import init_db for ORM-based repair
from solomon_core.solomon_tools import diagnostics
from solomon_core.reinforcement_store import normalize_reinforcement
from config import settings

logger = get_logger("self_repair")


# -------------------------------------------------------
# Utility helpers
# -------------------------------------------------------
def _safe_execute(sql: str):
    """Safely execute SQL statements with rollback protection."""
    try:
        with engine.begin() as conn:
            conn.execute(sql)
        return True
    except Exception as e:
        logger.error(f"[SQL Repair] Failed executing: {sql} | {e}")
        return False


def _ensure_dir(path):
    """Ensure directory exists (used for memory/logs)."""
    try:
        os.makedirs(path, exist_ok=True)
    except Exception as e:
        logger.warning(f"[Repair] Could not create directory {path}: {e}")


# -------------------------------------------------------
# 1️⃣ Database repair routines
# -------------------------------------------------------
def repair_database():
    """
    Check and recreate missing core tables if needed.

    ✅ Phase 9.6 update:
      - Prefer SQLAlchemy metadata via init_db() instead of raw CREATE TABLE SQL.
      - This ensures new ORM models (TaskHistory, Skill, etc.) are created
        correctly for MySQL and future schema changes.
    """
    logger.info("[Repair] Checking database integrity...")
    report = diagnostics.check_database()

    # If diagnostics says everything is fine, we still return success
    if report.get("ok") and not report.get("missing"):
        logger.info("[Repair] Database already healthy.")
        return {"ok": True, "message": "All tables exist."}

    missing = report.get("missing", [])
    logger.warning(f"[Repair] Database reported missing or invalid tables: {missing}")

    # Use ORM-based initialization instead of raw SQL DDL
    try:
        init_db()
        logger.info("[Repair] Ran init_db() to sync ORM models to database.")

        # Optional: re-run diagnostics for confirmation
        confirm = diagnostics.check_database()
        if confirm.get("ok") and not confirm.get("missing"):
            return {
                "ok": True,
                "message": "Database repaired via init_db().",
                "missing_before": missing,
            }
        else:
            return {
                "ok": False,
                "error": "init_db() completed but diagnostics still report issues.",
                "missing_before": missing,
                "missing_after": confirm.get("missing"),
            }
    except Exception as e:
        logger.error(f"[Repair] init_db() failed during DB repair: {e}")
        return {"ok": False, "error": str(e), "missing": missing}


# -------------------------------------------------------
# 2️⃣ Memory & log file repair
# -------------------------------------------------------
def repair_memory_files():
    """Validate and repair corrupted or missing memory.json."""
    base_dir = getattr(settings, "DATA_DIR", "./data")
    mem_dir = os.path.join(base_dir, "memory")
    _ensure_dir(mem_dir)

    mem_file = os.path.join(mem_dir, "memory.json")
    if not os.path.exists(mem_file):
        logger.warning(f"[Repair] Missing memory.json → recreating.")
        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        return {"ok": True, "action": "created", "path": mem_file}

    try:
        with open(mem_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, (list, dict)):
            raise ValueError("Invalid format")
        return {"ok": True, "action": "validated", "entries": len(data) if isinstance(data, list) else 1}
    except Exception as e:
        logger.warning(f"[Repair] Corrupted memory.json → reset: {e}")
        backup = mem_file + ".bak"
        try:
            os.rename(mem_file, backup)
        except Exception:
            pass
        with open(mem_file, "w", encoding="utf-8") as f:
            json.dump([], f, indent=2)
        return {"ok": True, "action": "reset", "backup": backup}


def repair_logs():
    """Ensure logs directory exists and writable."""
    logs_dir = getattr(settings, "LOG_DIR", os.path.join(getattr(settings, "DATA_DIR", "./data"), "logs"))
    _ensure_dir(logs_dir)
    test_file = os.path.join(logs_dir, f"repair_test_{datetime.now().strftime('%H%M%S')}.log")
    try:
        with open(test_file, "w", encoding="utf-8") as f:
            f.write("log test ok\n")
        os.remove(test_file)
        return {"ok": True, "message": f"Logs writable at {logs_dir}"}
    except Exception as e:
        return {"ok": False, "error": f"Logs not writable: {e}", "path": logs_dir}


# -------------------------------------------------------
# 3️⃣ Unified repair entrypoint
# -------------------------------------------------------
def run_self_repair():
    """Runs all safe repair routines in sequence."""
    logger.info("[Repair] Starting full self-repair cycle…")

    results = {
        "timestamp": datetime.now().isoformat(),
        "database": repair_database(),
        "memory": repair_memory_files(),
        "logs": repair_logs(),
        "status": "ok"
    }

    # ✅ Phase 7.2 — Normalize reinforcement weights automatically
    try:
        norm_result = normalize_reinforcement()
        results["reinforcement"] = norm_result
        logger.info("[Repair] Reinforcement normalization included in self-repair.")
    except Exception as e:
        logger.warning(f"[Repair] Reinforcement normalization failed: {e}")
        results["reinforcement"] = {"ok": False, "error": str(e)}

    # Mark degraded if any issue
    if not results["database"].get("ok") or not results["logs"].get("ok"):
        results["status"] = "degraded"

    # ✅ Always use LOG_DIR from config for the final report
    log_dir = getattr(settings, "LOG_DIR", os.path.join(getattr(settings, "DATA_DIR", "./data"), "logs"))
    _ensure_dir(log_dir)
    summary_path = os.path.join(log_dir, "self_repair_report.json")

    try:
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        logger.info(f"[Repair] Report saved → {summary_path}")
    except Exception as e:
        logger.warning(f"[Repair] Could not write self-repair report: {e}")

    logger.info(f"[Repair] Self-repair cycle complete ({results['status']})")
    return results


# -------------------------------------------------------
# 4️⃣ Standalone runner
# -------------------------------------------------------
if __name__ == "__main__":
    """Allow running directly via: python -m solomon_core.self_repair"""
    print(json.dumps(run_self_repair(), indent=2))

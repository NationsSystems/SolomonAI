# solomon_core/solomon_tools/diagnostics.py — Phase-38 SAFE
# -----------------------------------------------------------
# Safe diagnostics layer for Solomon.
#
# Phase 38 GUARANTEES:
#   • NO task execution
#   • NO calls to execute_task()
#   • INSPECTION ONLY
#   • Orchestrator remains sole execution authority
#
# PHASE 47.1 ADDITION:
#   • Diagnostic Isolation Invariant
#   • Operator-only, LLM-opaque, non-consumable signals
#   • Diagnostics may never be routed into execution, packets, or prompts
# -----------------------------------------------------------

import os
import time
import json
import traceback
import datetime
from solomon_core.logger import get_logger
from solomon_core.db import engine
from config import settings
from sqlalchemy import text

logger = get_logger("diagnostics")

START_TIME = time.time()

# ---------------------------------------------------------------------------
# Phase-47 Diagnostic Isolation Declaration (STRUCTURAL)
# ---------------------------------------------------------------------------
IS_DIAGNOSTIC_MODULE = True        # Machine-readable marker
OPERATOR_ONLY = True              # Must never be called by planner/skills/LLM
LLM_OPAQUE = True                 # Diagnostic data is non-consumable by LLM
EXECUTION_AUTHORITY = False       # Diagnostics may NEVER execute tasks

# Unified logs directory
LOGS_DIR = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "..", "logs"
))
os.makedirs(LOGS_DIR, exist_ok=True)

# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------
def _safe_json_load(path):
    try:
        if not os.path.exists(path):
            return {"ok": False, "error": f"File not found: {path}"}
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {"ok": True, "entries": len(data) if isinstance(data, list) else "dict"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def _format_duration(seconds):
    mins, sec = divmod(int(seconds), 60)
    hrs, mins = divmod(mins, 60)
    days, hrs = divmod(hrs, 24)
    return f"{days}d {hrs}h {mins}m {sec}s"


# -------------------------------------------------------
# Database check (inspection only)
# -------------------------------------------------------
def check_database():
    try:
        with engine.connect() as conn:
            try:
                result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
                tables = [row[0] for row in result.fetchall()]
            except Exception:
                result = conn.execute(text("SHOW TABLES"))
                tables = [r[0] for r in result]

        required = {"task_history", "memory", "reinforcement_log", "evaluation_log"}
        missing = required - set(tables)

        return {
            "is_diagnostic": True,
            "ok": not missing,
            "existing": list(tables),
            "missing": list(missing),
            "checked_at": datetime.datetime.now().isoformat(),
        }
    except Exception as e:
        return {"is_diagnostic": True, "ok": False, "error": str(e)}


# -------------------------------------------------------
# Memory checks (inspection only)
# -------------------------------------------------------
def check_memory_files():
    base_dir = os.path.join(settings.DATA_DIR, "memory")
    mem_file = os.path.join(base_dir, "memory.json")

    return {
        "is_diagnostic": True,
        "memory_file": _safe_json_load(mem_file),
        "log_dir_exists": os.path.exists(LOGS_DIR),
        "log_count": len(os.listdir(LOGS_DIR)) if os.path.exists(LOGS_DIR) else 0,
    }


def check_memory():
    path = os.path.join(settings.DATA_DIR, "memory", "memory.json")

    if not os.path.exists(path):
        return {
            "is_diagnostic": True,
            "ok": False,
            "message": "memory.json missing",
            "path": path
        }

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        count = len(data) if isinstance(data, list) else 1
        return {
            "is_diagnostic": True,
            "ok": True,
            "entries": count,
            "path": path
        }
    except Exception as e:
        return {
            "is_diagnostic": True,
            "ok": False,
            "message": f"Corrupted memory.json: {e}",
            "path": path
        }


# -------------------------------------------------------
# Phase-38 Core Integrity Check (NO EXECUTION)
# -------------------------------------------------------
def check_core():
    """
    Phase-38 SAFE core check:
        • Verify orchestrator presence
        • Verify callable signature
        • DO NOT execute anything
    """
    try:
        from solomon_core import solomon_core

        if not hasattr(solomon_core, "execute_task"):
            return {
                "is_diagnostic": True,
                "ok": False,
                "message": "execute_task missing from solomon_core"
            }

        if not callable(solomon_core.execute_task):
            return {
                "is_diagnostic": True,
                "ok": False,
                "message": "execute_task exists but is not callable"
            }

        return {
            "is_diagnostic": True,
            "ok": True,
            "message": "Orchestrator present and callable (execution not tested)",
        }

    except Exception as e:
        return {"is_diagnostic": True, "ok": False, "message": str(e)}


# -------------------------------------------------------
# Log tail (read-only)
# -------------------------------------------------------
def get_last_error():
    try:
        log = os.path.join(LOGS_DIR, "solomon.log")
        if not os.path.exists(log):
            return "No log file found."
        with open(log, "r", encoding="utf-8", errors="ignore") as f:
            return "".join(f.readlines()[-5:])
    except Exception as e:
        return f"[Error reading log]: {e}"


def get_uptime():
    return _format_duration(time.time() - START_TIME)


# -------------------------------------------------------
# Full diagnostic suite (inspection only)
# -------------------------------------------------------
def run_diagnostics():
    """
    Phase-38 SAFE diagnostics:
        • inspection only
        • NO task execution
        • returns structured health report
    """
    logger.info("[Diagnostics] Running inspection-only health check")

    try:
        report = {
            "is_diagnostic": True,
            "timestamp": datetime.datetime.now().isoformat(),
            "uptime": get_uptime(),
            "core": check_core(),
            "database": check_database(),
            "memory": check_memory(),
            "last_error": get_last_error(),
            "status": "ok",
        }

        if not report["core"]["ok"] or not report["database"]["ok"] or not report["memory"]["ok"]:
            report["status"] = "degraded"

        # Write report safely (diagnostic artifact only)
        try:
            with open(os.path.join(LOGS_DIR, "integrity_report.json"), "w", encoding="utf-8") as f:
                json.dump(report, f, indent=2)
        except Exception as e:
            logger.warning(f"[Diagnostics] Failed to write integrity report: {e}")

        return report

    except Exception as e:
        trace = traceback.format_exc(limit=3)
        logger.error(f"[Diagnostics] Unexpected failure: {e}")
        return {
            "is_diagnostic": True,
            "ok": False,
            "error": str(e),
            "trace": trace,
            "status": "error",
        }

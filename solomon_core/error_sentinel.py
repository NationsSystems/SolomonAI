# error_sentinel.py — Phase 44 Packet-Compatible Error Sentinel
# -------------------------------------------------------------
# Global Error Sentinel (GES) — JSON-safe, deterministic
#
# Phase 21–38 GUARANTEES (PRESERVED):
#   • Persistence with dedupe
#   • Global exception capture
#   • No authority, no routing, no gating
#   • No schema changes
#
# Phase 44 CHANGE:
#   • Emits PAYLOAD-ONLY error records
#   • Orchestrator wraps errors into PacketEnvelope
# -------------------------------------------------------------

import sys
import traceback
import threading
from datetime import datetime
from sqlalchemy import text

from solomon_core.db import engine, SessionLocal
from solomon_core.logger import get_logger

logger = get_logger("error_sentinel")


# -------------------------------------------------------------
# Thread-safe lock (prevents concurrent writes)
# -------------------------------------------------------------
_write_lock = threading.Lock()


# -------------------------------------------------------------
# JSON-safe sanitizer
# -------------------------------------------------------------
def _safe(obj):
    """Convert any unsupported JSON type into a safe string."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


# -------------------------------------------------------------
# Initialize DB table (if missing)
# -------------------------------------------------------------
def init_error_table():
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS error_events (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    phase VARCHAR(128),
                    error_type VARCHAR(255),
                    message TEXT,
                    traceback TEXT,
                    dedupe_hash VARCHAR(64),
                    count INT DEFAULT 1
                )
            """))
        logger.info("[GES] error_events table verified/ready")
    except Exception as e:
        logger.error(f"[GES] Failed to init table: {e}")


# -------------------------------------------------------------
# Compute a simple dedupe hash (type + message)
# -------------------------------------------------------------
def _dedupe_hash(error_type: str, message: str) -> str:
    try:
        import hashlib
        key = f"{error_type}:{message}"
        return hashlib.sha256(key.encode("utf-8")).hexdigest()[:64]
    except Exception:
        return None


# -------------------------------------------------------------
# Persist one error event (deduplicated)
# -------------------------------------------------------------
def record_error(
    phase: str,
    error_type: str,
    message: str,
    tb: str,
    *,
    orchestrator_event_id: str | None = None,
    orchestrator_violation: str | None = None,
) -> dict:
    """
    Phase 44:
    • Records error deterministically
    • Returns PAYLOAD-ONLY dict for packet wrapping upstream
    """

    # ---------------------------------------------------------
    # Embed orchestrator labels (LABEL ONLY, NO AUTHORITY)
    # ---------------------------------------------------------
    if orchestrator_event_id or orchestrator_violation:
        prefix = []
        if orchestrator_event_id:
            prefix.append(f"event_id={orchestrator_event_id}")
        if orchestrator_violation:
            prefix.append(f"violation={orchestrator_violation}")
        message = f"[ORCHESTRATOR {' '.join(prefix)}] {message}"

    dedupe = _dedupe_hash(error_type, message)

    # SANITIZE BEFORE RECORDING
    message_safe = _safe(message)
    tb_safe = _safe(tb)
    phase_safe = _safe(phase)
    error_type_safe = _safe(error_type)

    with _write_lock:
        session = SessionLocal()
        try:
            row = session.execute(text("""
                SELECT id, count FROM error_events
                WHERE dedupe_hash = :h
                ORDER BY id DESC
                LIMIT 1
            """), {"h": dedupe}).fetchone()

            if row:
                session.execute(text("""
                    UPDATE error_events
                    SET count = count + 1,
                        traceback = :tb,
                        created_at = NOW()
                    WHERE id = :id
                """), {"tb": tb_safe, "id": row.id})
            else:
                session.execute(text("""
                    INSERT INTO error_events (
                        phase, error_type, message, traceback, dedupe_hash
                    ) VALUES (:p, :t, :m, :tb, :h)
                """), {
                    "p": phase_safe,
                    "t": error_type_safe,
                    "m": message_safe,
                    "tb": tb_safe,
                    "h": dedupe,
                })

            session.commit()

        except Exception as e:
            logger.error(f"[GES] Failed to record error: {e}")
            session.rollback()
        finally:
            session.close()

    # ---------------------------------------------------------
    # Payload-only error result (for Orchestrator)
    # ---------------------------------------------------------
    return {
        "error": True,
        "phase": phase_safe,
        "error_type": error_type_safe,
        "message": message_safe,
        "traceback": tb_safe,
    }


# -------------------------------------------------------------
# Phase 20 Compatibility Wrapper (UNCHANGED)
# -------------------------------------------------------------
def get_error_history(limit: int = 200):
    session = SessionLocal()
    try:
        rows = session.execute(text(f"""
            SELECT id, created_at, phase, error_type, message, traceback, count
            FROM error_events
            ORDER BY id DESC
            LIMIT {limit}
        """)).fetchall()

        safe_rows = []
        for r in rows:
            safe_rows.append({
                "id": r.id,
                "created_at": _safe(r.created_at),
                "phase": _safe(r.phase),
                "error_type": _safe(r.error_type),
                "message": _safe(r.message),
                "traceback": _safe(r.traceback),
                "count": r.count,
            })

        return safe_rows

    except Exception as e:
        logger.error(f"[GES] Failed to fetch error history: {e}")
        return []
    finally:
        session.close()


# -------------------------------------------------------------
# GLOBAL HOOK — Captures ALL uncaught exceptions (PAYLOAD-ONLY)
# -------------------------------------------------------------
def _global_exception_hook(exc_type, exc_value, exc_tb):
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.error(f"[GES] Uncaught exception: {exc_type.__name__}: {exc_value}")
    record_error(
        "global-exception",
        exc_type.__name__,
        str(exc_value),
        tb_str,
    )
    # Do NOT re-raise — prevents crash


# -------------------------------------------------------------
# Activate at import
# -------------------------------------------------------------
init_error_table()
sys.excepthook = _global_exception_hook

logger.info("[GES] Global Error Sentinel active")

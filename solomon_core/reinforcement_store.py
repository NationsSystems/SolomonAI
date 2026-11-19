# reinforcement_store.py — Solomon Autonomous Reinforcement Layer (Phase 18)
# --------------------------------------------------------------------
# Phase 18 Upgrades:
#   • Unified reinforcement signal path
#   • HFLO-compatible update_reinforcement(task_id, delta)
#   • Planner confidence hooks
#   • Stability + logging improvements
# --------------------------------------------------------------------

import json
from datetime import datetime
from sqlalchemy import text
from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal, engine
from config import settings
import os

logger = get_logger("reinforcement_store")


# --------------------------------------------------------------------
#  Init table if missing
# --------------------------------------------------------------------
def init_reinforcement_table():
    """Ensure reinforcement_log exists and includes Phase 18 fields."""
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS reinforcement_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    intent VARCHAR(128),
                    reasoning_source VARCHAR(64),
                    total_runs INT DEFAULT 0,
                    success_count INT DEFAULT 0,
                    fail_count INT DEFAULT 0,
                    success_weight FLOAT DEFAULT 0,
                    avg_confidence FLOAT DEFAULT 0,
                    planner_confidence_last FLOAT DEFAULT 0,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                        ON UPDATE CURRENT_TIMESTAMP
                )
            """))
        logger.info("[MySQL] reinforcement_log verified.")
    except Exception as e:
        logger.error(f"[init_reinforcement_table] Failed: {e}")


# --------------------------------------------------------------------
#  Default bootstrap weights
# --------------------------------------------------------------------
def bootstrap_default_weights():
    """Seed baseline weights without overwriting existing rows."""
    defaults = [
        ("autonomous_reflection", "deterministic", 2.0),
        ("autonomous_reflection", "internal",      3.0),
        ("autonomous_reflection", "semantic",      1.0),
        ("autonomous_reflection", "llm",           1.0),
        ("autonomous_reflection", "cognitive_loop", 0.0),

        ("unknown", "deterministic", 1.5),
        ("unknown", "semantic",      1.0),
        ("unknown", "llm",           1.0),
        ("unknown", "internal",      0.5),
        ("unknown", "cognitive_loop", 0.0),
    ]

    db = SessionLocal()
    try:
        for intent, source, initial_weight in defaults:

            row = db.execute(text("""
                SELECT id FROM reinforcement_log
                WHERE intent=:i AND reasoning_source=:s
            """), {"i": intent, "s": source}).fetchone()

            if row:
                continue

            db.execute(text("""
                INSERT INTO reinforcement_log
                    (intent, reasoning_source, total_runs, success_count,
                     fail_count, success_weight, avg_confidence,
                     planner_confidence_last, last_seen)
                VALUES
                    (:i, :s, 1, 1, 0, :w, 0.75, 0, NOW())
            """), {"i": intent, "s": source, "w": initial_weight})

        db.commit()
        logger.info("[Reinforce] Baseline weights bootstrapped.")

    except Exception as e:
        db.rollback()
        logger.error(f"[bootstrap_default_weights] Failed: {e}")
    finally:
        db.close()


# Initialize
init_reinforcement_table()
bootstrap_default_weights()


# --------------------------------------------------------------------
#  Core reinforcement logger
# --------------------------------------------------------------------
def record_signal(intent: str, reasoning_source: str, success: bool,
                  confidence: float = None, planner_confidence: float = None):
    """
    Log a reinforcement signal for (intent + reasoning_source).
    Updates counters, confidence averages, and last planner confidence.
    """
    db = SessionLocal()
    try:
        intent = intent or "unknown"
        reasoning_source = reasoning_source or "unspecified"
        conf = float(confidence or 0.0)
        plan_conf = float(planner_confidence or 0.0)

        logger.debug(
            f"[Reinforcement] signal: {intent}/{reasoning_source} "
            f"success={success} conf={conf} planner_conf={plan_conf}"
        )

        # Ensure row exists
        db.execute(text("""
            INSERT INTO reinforcement_log (intent, reasoning_source)
            VALUES (:i, :s)
            ON DUPLICATE KEY UPDATE last_seen = NOW()
        """), {"i": intent, "s": reasoning_source})

        row = db.execute(text("""
            SELECT total_runs, success_count, fail_count, avg_confidence
            FROM reinforcement_log
            WHERE intent=:i AND reasoning_source=:s
        """), {"i": intent, "s": reasoning_source}).fetchone()

        total_runs = row.total_runs if row else 0
        success_count = row.success_count if row else 0
        fail_count = row.fail_count if row else 0
        avg_conf = row.avg_confidence if row else 0.0

        total_runs += 1
        if success:
            success_count += 1
        else:
            fail_count += 1

        new_avg = ((avg_conf * (total_runs - 1)) + conf) / total_runs
        delta = 1 if success else -1

        db.execute(text("""
            UPDATE reinforcement_log
            SET total_runs = :tr,
                success_count = :sc,
                fail_count = :fc,
                success_weight = success_weight + :delta,
                avg_confidence = :ac,
                planner_confidence_last = :pc,
                last_seen = NOW()
            WHERE intent=:i AND reasoning_source=:s
        """), {
            "tr": total_runs,
            "sc": success_count,
            "fc": fail_count,
            "delta": delta,
            "ac": new_avg,
            "pc": plan_conf,
            "i": intent,
            "s": reasoning_source
        })

        db.commit()
        logger.info(
            f"[Reinforce] Updated {intent}/{reasoning_source} → "
            f"Δ={delta}, conf={new_avg:.2f}, plan_conf={plan_conf:.2f}"
        )

    except Exception as e:
        db.rollback()
        logger.error(f"[record_signal] Failed: {e}")
    finally:
        db.close()


# --------------------------------------------------------------------
#  HFLO-Compatible reinforcement: update_reinforcement(task_id, delta)
# --------------------------------------------------------------------
def update_reinforcement(task_id: str, delta: int):
    """
    HFLO-style reinforcement update.
    Converts simple (task_id + +/-1) signal into a unified reinforcement entry.
    """
    try:
        intent = f"hflo_{task_id}"
        reasoning_source = "hflo"

        success = delta > 0
        conf = 1.0 if success else 0.0

        record_signal(
            intent=intent,
            reasoning_source=reasoning_source,
            success=success,
            confidence=conf,
            planner_confidence=None
        )

        logger.info(f"[HFLO→Reinforcement] task={task_id} delta={delta}")

    except Exception as e:
        logger.error(f"[update_reinforcement] HFLO failed: {e}")


# --------------------------------------------------------------------
#  Retrieval utilities
# --------------------------------------------------------------------
def get_stats(intent: str = None, reasoning_source: str = None):
    """Fetch reinforcement stats."""
    try:
        db = SessionLocal()
        if intent and reasoning_source:
            query = text("""
                SELECT * FROM reinforcement_log
                WHERE intent=:i AND reasoning_source=:s
            """)
            params = {"i": intent, "s": reasoning_source}
        elif intent:
            query = text("""
                SELECT * FROM reinforcement_log WHERE intent=:i
            """)
            params = {"i": intent}
        else:
            query = text("""
                SELECT intent, reasoning_source, total_runs, success_count,
                       fail_count, success_weight, avg_confidence,
                       planner_confidence_last, last_seen
                FROM reinforcement_log
                ORDER BY success_weight DESC, avg_confidence DESC
                LIMIT 50
            """)
            params = {}

        rows = db.execute(query, params).fetchall()
        return [dict(row._mapping) for row in rows]

    except Exception as e:
        logger.error(f"[get_stats] Failed: {e}")
        return []
    finally:
        db.close()


# --------------------------------------------------------------------
#  Weight retrieval (legacy API)
# --------------------------------------------------------------------
def get_weight(intent: str, reasoning_source: str) -> float:
    """Return current success_weight."""
    try:
        db = SessionLocal()
        row = db.execute(text("""
            SELECT success_weight FROM reinforcement_log
            WHERE intent=:i AND reasoning_source=:s
        """), {"i": intent, "s": reasoning_source}).fetchone()
        return float(row[0]) if row else 0.0
    except Exception as e:
        logger.error(f"[get_weight] Error: {e}")
        return 0.0
    finally:
        db.close()


# --------------------------------------------------------------------
#  ⭐ NEW — Phase 18: get_reinforcement_weight(skill_name)
# --------------------------------------------------------------------
def get_reinforcement_weight(skill_name: str) -> float:
    """
    Phase 18-compatible version of the historical API.
    Returns the strongest reinforcement signal associated with this skill.
    """
    try:
        skill_name = (skill_name or "").strip().lower()
        if not skill_name:
            return 0.0

        db = SessionLocal()
        rows = db.execute(text("""
            SELECT intent, reasoning_source, success_weight
            FROM reinforcement_log
            WHERE LOWER(intent) LIKE :pattern
               OR LOWER(intent) = :exact
        """), {
            "pattern": f"%{skill_name}%",
            "exact": skill_name,
        }).fetchall()

        if not rows:
            return 0.0

        return max(float(r.success_weight) for r in rows)

    except Exception as e:
        logger.error(f"[get_reinforcement_weight] Failed: {e}")
        return 0.0
    finally:
        db.close()


# --------------------------------------------------------------------
#  Weight normalization
# --------------------------------------------------------------------
def normalize_reinforcement(min_weight=-10.0, max_weight=10.0):
    """Clamp runaway weights."""
    try:
        db = SessionLocal()

        db.execute(text("""
            UPDATE reinforcement_log
            SET success_weight = CASE
                WHEN success_weight < :minw THEN :minw
                WHEN success_weight > :maxw THEN :maxw
                ELSE success_weight END
        """), {"minw": min_weight, "maxw": max_weight})

        rows = db.execute(text("""
            SELECT intent, reasoning_source, total_runs,
                   success_count, fail_count, success_weight
            FROM reinforcement_log
        """)).fetchall()

        for r in rows:
            total = max(r.total_runs, 1)
            pct = (r.success_count / total) * 100
            logger.debug(
                f"[Normalize] {r.intent}/{r.reasoning_source} "
                f"→ weight={r.success_weight}, success={pct:.1f}%"
            )

        db.commit()
        return {"ok": True}

    except Exception as e:
        logger.error(f"[normalize_reinforcement] Failed: {e}")
        return {"ok": False, "error": str(e)}
    finally:
        db.close()


# --------------------------------------------------------------------
#  Adaptive Decay
# --------------------------------------------------------------------
def adaptive_tune_weights(decay_rate: float = 0.98):
    """Gradual decay for long-term stability."""
    try:
        db = SessionLocal()
        db.execute(text("""
            UPDATE reinforcement_log
            SET success_weight = ROUND(success_weight * :d, 3)
        """), {"d": decay_rate})
        db.commit()
        logger.debug(f"[Reinforce] Decay applied.")
    except Exception as e:
        logger.error(f"[adaptive_tune_weights] Failed: {e}")
    finally:
        db.close()


# --------------------------------------------------------------------
#  Snapshot for cognition loop
# --------------------------------------------------------------------
def get_reinforcement_snapshot():
    """Return reinforcement state for cognitive_loop."""
    try:
        db = SessionLocal()
        rows = db.execute(text("""
            SELECT intent, reasoning_source, success_weight,
                   avg_confidence, planner_confidence_last,
                   total_runs, success_count, fail_count, last_seen
            FROM reinforcement_log
        """)).fetchall()

        return {
            f"{r.intent}/{r.reasoning_source}": {
                "weight": r.success_weight,
                "avg_confidence": r.avg_confidence,
                "planner_confidence_last": r.planner_confidence_last,
                "total_runs": r.total_runs,
                "success_count": r.success_count,
                "fail_count": r.fail_count,
                "last_seen": r.last_seen.isoformat() if r.last_seen else None,
            }
            for r in rows
        }

    except Exception as e:
        logger.error(f"[Reinforcement] Snapshot failed: {e}")
        return {}
    finally:
        db.close()


# --------------------------------------------------------------------
#  Weight History
# --------------------------------------------------------------------
def get_weight_history():
    """Load historical weight data for graphs."""
    try:
        path = os.path.join(settings.DATA_DIR, "weights_history.json")
        if not os.path.exists(path):
            return {"history": []}

        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)

        if isinstance(data, dict):
            return data
        if isinstance(data, list):
            return {"history": data}

        return {"history": []}

    except Exception as e:
        logger.error(f"[get_weight_history] Failed: {e}")
        return {"history": []}

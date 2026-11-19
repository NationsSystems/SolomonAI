# evaluator.py — Solomon Evaluation + Reinforcement Integration (Phase 7.1)
# --------------------------------------------------------------------
# Evaluates each task result, logs performance metrics, and integrates
# reinforcement signals for adaptive reasoning weight tuning.
# --------------------------------------------------------------------
import json
from datetime import datetime
from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal, engine
from solomon_core.reinforcement_store import record_signal, get_stats
from sqlalchemy import text

logger = get_logger("evaluator")


# --------------------------------------------------------------------
# Ensure evaluation table exists (MySQL-safe)
# --------------------------------------------------------------------
def _init_eval_table():
    try:
        with engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS evaluation_log (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    task_id VARCHAR(64),
                    intent VARCHAR(128),
                    reasoning_source VARCHAR(128),
                    success BOOLEAN,
                    confidence FLOAT,
                    summary TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """))
        logger.info("[Evaluator] evaluation_log table verified.")
    except Exception as e:
        logger.error(f"[Evaluator] Table initialization failed: {e}")


# ✅ Initialize at import
_init_eval_table()


# --------------------------------------------------------------------
# Core evaluation summary
# --------------------------------------------------------------------
def evaluate_task(task_id: str, intent: str, reasoning_source: str,
                  success: bool, confidence: float = None,
                  summary: str = None):
    """
    Store an evaluation record in DB and propagate reinforcement signal.
    Compatible with autonomous task loop feedback.
    """
    try:
        db = SessionLocal()
        db.execute(text("""
            INSERT INTO evaluation_log (task_id, intent, reasoning_source, success,
                                        confidence, summary, created_at)
            VALUES (:task_id, :intent, :reasoning_source, :success,
                    :confidence, :summary, NOW())
        """), {
            "task_id": task_id,
            "intent": intent,
            "reasoning_source": reasoning_source,
            "success": 1 if success else 0,
            "confidence": confidence,
            "summary": summary
        })
        db.commit()
        db.close()

        logger.info(f"[Evaluator] Recorded evaluation: {intent} | success={success} | src={reasoning_source}")

        # ✅ Propagate reinforcement signal
        record_signal(intent, reasoning_source, success, confidence)

    except Exception as e:
        logger.error(f"[evaluate_task] Failed: {e}")


# --------------------------------------------------------------------
# Optional: aggregate summary for analytics or autonomous feedback
# --------------------------------------------------------------------
def summarize_performance(limit: int = 100):
    """Return performance statistics across recent evaluations."""
    try:
        db = SessionLocal()
        result = db.execute(text(f"""
            SELECT reasoning_source,
                   COUNT(*) AS total,
                   SUM(success) AS success_count,
                   ROUND(SUM(success)/COUNT(*)*100,2) AS success_rate
            FROM evaluation_log
            GROUP BY reasoning_source
            ORDER BY success_rate DESC
            LIMIT {limit}
        """))
        rows = result.fetchall()
        db.close()

        summary = [dict(row._mapping) for row in rows]
        reinforcement = get_stats()

        # ✅ Combine results for autonomous performance introspection
        return {
            "summary": summary,
            "reinforcement": reinforcement,
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"[summarize_performance] Failed: {e}")
        return {
            "summary": [],
            "reinforcement": [],
            "timestamp": datetime.now().isoformat()
        }

# skill_threshold.py — Phase 9.10 Step 4
# -----------------------------------------------------------
# Computes the adaptive threshold used to determine
# whether Solomon should auto-install a learned skill.
#
# The threshold depends on:
#   • recent LLM usage
#   • failure rate
#   • backlog size
#   • time since last skill install
#   • average relevance score of pending candidates
#
# Output: float between 0.40 and 0.90
# -----------------------------------------------------------

from datetime import datetime, timedelta
import statistics
from solomon_core.logger import get_logger

from solomon_core.db import SessionLocal, Skill
from solomon_core.solomon_tools.skill_ranker import rank_skill_candidates
from solomon_core.solomon_tools.relevance_engine import compute_relevance
from solomon_core.solomon_tools.faiss_store import search as faiss_search

logger = get_logger("skill_threshold")


# -----------------------------------------------------------
# Helper: recent LLM load (last 50 tasks)
# -----------------------------------------------------------
def _recent_llm_load():
    session = SessionLocal()
    try:
        rows = session.execute("""
            SELECT reasoning_source
            FROM task_history
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()
    finally:
        session.close()

    if not rows:
        return 0.0

    llm_count = sum(1 for r in rows if r[0] == "llm")
    return llm_count / len(rows)


# -----------------------------------------------------------
# Helper: recent failure rate (last 50 tasks)
# -----------------------------------------------------------
def _recent_failure_rate():
    session = SessionLocal()
    try:
        rows = session.execute("""
            SELECT success
            FROM task_history
            ORDER BY id DESC
            LIMIT 50
        """).fetchall()
    finally:
        session.close()

    if not rows:
        return 0.0

    fails = sum(1 for r in rows if r[0] == 0)
    return fails / len(rows)


# -----------------------------------------------------------
# Helper: time since last installed skill
# -----------------------------------------------------------
def _hours_since_last_skill_install():
    session = SessionLocal()
    try:
        rec = session.execute("""
            SELECT created_at
            FROM skills
            ORDER BY id DESC
            LIMIT 1
        """).fetchone()
    finally:
        session.close()

    if not rec or not rec[0]:
        return 999  # treat as "very long ago"

    last = rec[0]
    now = datetime.utcnow()
    delta = now - last
    return delta.total_seconds() / 3600.0


# -----------------------------------------------------------
# Main adaptive threshold computation
# -----------------------------------------------------------
def compute_skill_install_threshold():
    """
    Output range: 0.40 (very eager to install)
                  to 0.90 (very conservative)
    """

    llm_load = _recent_llm_load()              # 0.00 – 1.00
    fail_rate = _recent_failure_rate()         # 0.00 – 1.00
    backlog = len(rank_skill_candidates())     # arbitrary
    hours_since = _hours_since_last_skill_install()

    # Base threshold
    threshold = 0.75

    # 1. LLM load — heavy load → raise threshold
    threshold += (llm_load * 0.10)

    # 2. Failure rate — high failures → lower threshold
    threshold -= (fail_rate * 0.25)

    # 3. Candidate backlog — more candidates → more selective
    if backlog > 10:
        threshold += 0.08
    elif backlog > 5:
        threshold += 0.04

    # 4. Time since last install — long time → lower threshold
    if hours_since > 48:
        threshold -= 0.10
    elif hours_since > 24:
        threshold -= 0.05

    # Clamp final range
    threshold = max(0.40, min(0.90, threshold))

    logger.debug(f"[skill_threshold] LLM load={llm_load:.2f}, fail={fail_rate:.2f}, "
                 f"backlog={backlog}, hours={hours_since:.1f} → threshold={threshold:.2f}")

    return threshold


# -----------------------------------------------------------
# Human-readable test output
# -----------------------------------------------------------
def quick_test():
    th = compute_skill_install_threshold()
    print(f"Adaptive skill threshold: {th:.3f}")

if __name__ == "__main__":
    quick_test()

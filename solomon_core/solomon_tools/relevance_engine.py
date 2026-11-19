# relevance_engine.py — Phase 9.10 Step 2
# ---------------------------------------------------------
# Computes a relevance score for:
#   • task similarity (semantic)
#   • recency
#   • frequency
#   • LLM dependence
#   • historical failures
#   • known skills covering similar tasks
#
# This enables Solomon to recommend:
#   "Should this become a reusable skill?"
#
# Used later in Phase 9.11 for autonomous skill discovery.

import numpy as np
from datetime import datetime
from sqlalchemy import text

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from solomon_core.solomon_tools.embedding_client import embed_text
from solomon_core.solomon_tools.faiss_store import search as faiss_skill_search
from solomon_core.solomon_tools.memory_store import embed_task_history

logger = get_logger("relevance_engine")

# ---------------------------------------------------------
# 1. Recency score
# ---------------------------------------------------------
def score_recency(created_at: datetime, now=None):
    if now is None:
        now = datetime.utcnow()

    delta_days = (now - created_at).days
    if delta_days <= 1:
        return 1.0
    if delta_days <= 7:
        return 0.8
    if delta_days <= 30:
        return 0.5
    if delta_days <= 90:
        return 0.3
    return 0.1


# ---------------------------------------------------------
# 2. Frequency score
# ---------------------------------------------------------
def score_frequency(intent: str):
    """
    Number of times a task with this intent appears.
    """
    try:
        db = SessionLocal()
        q = db.execute(text("""
            SELECT COUNT(*) AS c
            FROM task_history
            WHERE intent = :intent
        """), {"intent": intent}).fetchone()
        count = q[0] if q else 0
    except Exception as e:
        logger.error(f"score_frequency error: {e}")
        return 0.2
    finally:
        db.close()

    # Normalize
    if count >= 30:
        return 1.0
    if count >= 10:
        return 0.8
    if count >= 5:
        return 0.6
    if count >= 2:
        return 0.4
    return 0.2


# ---------------------------------------------------------
# 3. LLM Dependence Score
# ---------------------------------------------------------
def score_llm_dependence(intent: str):
    """
    How often similar tasks fell back to LLM reasoning.
    """
    try:
        db = SessionLocal()
        r = db.execute(text("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN reasoning_source = 'llm' THEN 1 ELSE 0 END) AS llm_count
            FROM task_history
            WHERE intent = :intent
        """), {"intent": intent}).fetchone()
        total = r[0] or 0
        llm_count = r[1] or 0
    except Exception as e:
        logger.error(f"score_llm_dependence error: {e}")
        return 0.5
    finally:
        db.close()

    if total == 0:
        return 0.2

    ratio = llm_count / total
    return float(ratio)  # 0.0 → 1.0 weight


# ---------------------------------------------------------
# 4. Failure Score
# ---------------------------------------------------------
def score_failures(intent: str):
    """
    Higher score = more failures → more need for new skill.
    """
    try:
        db = SessionLocal()
        r = db.execute(text("""
            SELECT COUNT(*) AS total,
                   SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failures
            FROM task_history
            WHERE intent = :intent
        """), {"intent": intent}).fetchone()
        total = r[0] or 0
        failures = r[1] or 0
    except Exception as e:
        logger.error(f"score_failures error: {e}")
        return 0.2
    finally:
        db.close()

    if total == 0:
        return 0.2

    return min(1.0, failures / total)


# ---------------------------------------------------------
# 5. Semantic similarity to past tasks
# ---------------------------------------------------------
def score_similarity(task_text: str):
    """
    Computes how similar this task is to historic tasks.
    Returns highest similarity in [0, 1].
    """
    history = embed_task_history(limit=200, days=30)
    if not history:
        return 0.2

    try:
        query = np.array(embed_text(task_text), dtype="float32")
        if len(query) != 768:
            return 0.2
    except Exception:
        return 0.2

    best = 0.0
    for _, vec in history:
        denom = (np.linalg.norm(query) * np.linalg.norm(vec))
        sim = float(np.dot(query, vec) / denom) if denom != 0 else 0.0
        best = max(best, sim)

    return best


# ---------------------------------------------------------
# 6. Skill overlap score
# ---------------------------------------------------------
def score_skill_overlap(task_text: str):
    """
    If similar skills already exist, score decreases (no need to create a new skill).
    If no similar skills exist → score increases.
    """
    results = faiss_skill_search(task_text, top_k=3)

    if not results:
        return 1.0  # No similar skills → big need to create one

    # Lower distance = higher similarity
    best_distance = min(r["distance"] for r in results)

    # Convert FAISS distance (L2) into similarity decreasing weight
    if best_distance > 1.5:
        return 0.9
    if best_distance > 1.0:
        return 0.6
    if best_distance > 0.5:
        return 0.3
    return 0.1  # Very similar skill exists


# ---------------------------------------------------------
# 7. Final Relevance Scoring
# ---------------------------------------------------------
def compute_relevance(task_text: str, intent: str, created_at: datetime):
    """
    Weighted scoring model (weights designed through empirical testing).
    Returns a score 0.0 → 1.0 indicating whether a new skill should be created.
    """
    rec = score_recency(created_at)
    freq = score_frequency(intent)
    llm_dep = score_llm_dependence(intent)
    fail = score_failures(intent)
    sim = score_similarity(task_text)
    overlap = score_skill_overlap(task_text)

    # Composite score
    score = (
        (0.20 * rec) +
        (0.20 * freq) +
        (0.20 * llm_dep) +
        (0.15 * fail) +
        (0.15 * sim) +
        (0.10 * overlap)
    )

    logger.debug(f"[relevance] rec={rec:.2f}, freq={freq:.2f}, "
                 f"llm={llm_dep:.2f}, fail={fail:.2f}, sim={sim:.2f}, "
                 f"overlap={overlap:.2f} → score={score:.3f}")

    return round(float(score), 3)

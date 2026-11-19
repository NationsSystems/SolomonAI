# skill_ranker.py — Phase 9.10 Step 3
# ---------------------------------------------------------------
# Ranks LLM-generated skill candidates using:
#   • relevance score (recency, failures, frequency, etc.)
#   • semantic similarity to existing skills (FAISS)
#   • candidate quality (steps, code length, completeness)
#   • dedupe protection (avoid duplicates)
#
# Output:
#   List of ranked candidates → to be consumed by Phase 9.11
#   (Autonomous Skill Discovery Pipeline)
# ---------------------------------------------------------------

from datetime import datetime
import numpy as np
from solomon_core.logger import get_logger

from solomon_core.db import SessionLocal, Skill
from solomon_core.solomon_tools.relevance_engine import compute_relevance
from solomon_core.solomon_tools.faiss_store import search as faiss_skill_search

# ✅ FIXED IMPORT
from solomon_core.skill_registry import list_skill_candidates

logger = get_logger("skill_ranker")


# ---------------------------------------------------------------
# 1. Compute completeness / quality of a skill candidate
# ---------------------------------------------------------------
def score_candidate_quality(candidate: dict):
    """
    Reward structured, well-formed candidates.
    """
    score = 0.0

    # Code completeness
    code = candidate.get("code", "")
    if code:
        if "def" in code or "skill(" in code:
            score += 0.3
        if len(code) > 200:
            score += 0.2
        if "import" in code:
            score += 0.1

    # Steps completeness
    steps = candidate.get("steps", [])
    if steps:
        if len(steps) >= 2:
            score += 0.2
        if len(steps) >= 4:
            score += 0.2

    # Intent clarity
    intent = candidate.get("intent", "")
    if isinstance(intent, str) and len(intent) > 3:
        score += 0.1

    return min(1.0, score)


# ---------------------------------------------------------------
# 2. Check if a similar skill already exists in DB
# ---------------------------------------------------------------
def score_existing_skill_overlap(candidate_name: str):
    """
    If similar skill exists → reduce motivation to create a new one.
    If no overlap → encourage creation.
    """
    results = faiss_skill_search(candidate_name, top_k=3)

    if not results:
        return 1.0  # No similar skills → strong need

    best = min(r["distance"] for r in results)

    # Convert semantic distance → score
    if best > 1.5:
        return 0.9
    if best > 1.0:
        return 0.6
    if best > 0.5:
        return 0.3
    return 0.1  # Very similar skill exists → discourage


# ---------------------------------------------------------------
# 3. Final ranking pipeline
# ---------------------------------------------------------------
def rank_skill_candidates():
    """
    Returns:
        [
          {
            "candidate": candidate_metadata,
            "relevance": 0.00–1.00,
            "quality": 0.00–1.00,
            "overlap": 0.00–1.00,
            "final_score": weighted
          }
        ]
    """

    candidates = list_skill_candidates()
    if not candidates:
        logger.info("[skill_ranker] No skill candidates found.")
        return []

    results = []

    for cand in candidates:
        try:
            created_at = cand.get("created_at")
            if isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at.replace("Z", ""))

            intent = cand.get("intent", "unknown")
            task_text = cand.get("task_text", "")

            # Phase 9.10 Step 2 relevance score
            relevance = compute_relevance(task_text, intent, created_at)

            # Quality score (code + steps)
            quality = score_candidate_quality(cand)

            # Skill overlap score (FAISS)
            overlap = score_existing_skill_overlap(cand["name"])

            # Composite weighted rank
            final = round(
                (0.50 * relevance) +
                (0.30 * quality) +
                (0.20 * overlap),
                3
            )

            results.append({
                "candidate": cand,
                "relevance": relevance,
                "quality": quality,
                "overlap": overlap,
                "final_score": final
            })

        except Exception as e:
            logger.error(f"[skill_ranker] Failed scoring candidate: {e}")

    # Sort by descending score
    results.sort(key=lambda x: x["final_score"], reverse=True)

    return results


# ---------------------------------------------------------------
# 4. Debug helper
# ---------------------------------------------------------------
def quick_test():
    """Print ranked skill candidates."""
    ranked = rank_skill_candidates()
    for r in ranked:
        print("-" * 40)
        print(f"Name:   {r['candidate']['name']}")
        print(f"Score:  {r['final_score']}")
        print(f"Rel:    {r['relevance']}")
        print(f"Qual:   {r['quality']}")
        print(f"Ovlp:   {r['overlap']}")

if __name__ == "__main__":
    quick_test()

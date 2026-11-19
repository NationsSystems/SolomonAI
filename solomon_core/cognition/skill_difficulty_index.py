# skill_difficulty_index.py — Phase 20 Step 6
# ---------------------------------------------------------
# Unified Skill Difficulty Index (USDI)
#
# Purpose:
#   Provide a stable “difficulty strain” signal that identifies
#   which skills are:
#       • hot_window  = heavily strained / unstable
#       • warm_window = borderline / watchlist
#       • cool_window = stable / no concern
#
# USDI does NOT mutate data.
# It is a pure read-only view derived from:
#       - Weakness engine scores
#       - Drift patterns
#       - Reinforcement negative signals
#       - Error affinity spikes
# ---------------------------------------------------------

import math

from solomon_core.knowledge.skill_weakness_engine import get_global_skill_weaknesses
from solomon_core.knowledge.knowledge_graph import compute_error_affinity
from solomon_core.reinforcement_store import get_reinforcement_snapshot


# ============================================================
# INTERNAL HELPERS
# ============================================================

def _normalize(v):
    try:
        return float(v)
    except:
        return 0.0


def _score_from_weakness(w):
    """Weakness score 0–100, normalized via logistic curve."""
    val = _normalize(w.get("score", 0))
    return 1 / (1 + math.exp(-(val - 20) / 8))  # smooth curve


def _score_from_error_affinity(skill, err_affinity):
    """Error affinity is a dict of {(skill, err): weight}."""
    score = 0.0
    for (s, err), weight in err_affinity.items():
        if s == skill:
            score += float(weight)
    return min(score / 10.0, 1.0)


def _score_from_reinforcement(skill, snapshot):
    total = 0.0
    for key, row in snapshot.items():
        if key.startswith(skill + "/"):
            total += float(row.get("weight", 0.0))
    # negative weights = pressure
    if total < 0:
        return min(abs(total) / 5.0, 1.0)
    return 0.0


# ============================================================
# MAIN API
# ============================================================

def get_skill_difficulty_windows():
    """
    Returns:
        {
            "hot_window": [skills],
            "warm_window": [skills],
            "cool_window": [skills],
            "difficulty_scores": {skill: score}
        }
    """

    weak = get_global_skill_weaknesses()
    err_aff = compute_error_affinity()
    reinf = get_reinforcement_snapshot()

    scores = {}

    for entry in weak:
        skill = entry.get("skill")
        if not skill:
            continue

        s = 0.0
        s += _score_from_weakness(entry)
        s += _score_from_error_affinity(skill, err_aff)
        s += _score_from_reinforcement(skill, reinf)

        # clamp 0–3
        s = max(0.0, min(3.0, s * 3.0))
        scores[skill] = s

    # Classify
    hot = [k for k, v in scores.items() if v >= 2.0]
    warm = [k for k, v in scores.items() if 0.8 <= v < 2.0]
    cool = [k for k, v in scores.items() if v < 0.8]

    return {
        "hot_window": hot,
        "warm_window": warm,
        "cool_window": cool,
        "difficulty_scores": scores,
    }

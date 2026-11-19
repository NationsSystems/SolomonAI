# strategic_skill_selector.py — Phase 40 Authority-Safe Strategic Skill Scoring
# -------------------------------------------------------------------------------
# PURPOSE (Phase 40):
#   Score and rank strategic skill options ONLY.
#   No selection, no outcome collapse, no semantic conclusions.
#
#   Orchestrator is the sole decision-maker.
# -------------------------------------------------------------------------------

import datetime

from solomon_core.knowledge.knowledge_graph import (
    get_kg_insights,
    get_kg_clusters,
    get_kg_scores,
)

from solomon_core.knowledge.skill_weakness_engine import (
    get_global_skill_weaknesses,
)

from solomon_core.cognition.meta.meta_context import MetaContext

# USDI Imports
from solomon_core.cognition.skill_difficulty_index import get_skill_difficulty_windows
from solomon_core.cognition.usdi_normalizer import get_normalized_usdi


# -------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------
def _now():
    return datetime.datetime.utcnow().isoformat()


def _safe(obj):
    import datetime as _dt

    if obj is None or isinstance(obj, (int, float, str, bool)):
        return obj

    if isinstance(obj, _dt.datetime):
        return obj.isoformat()

    if hasattr(obj, "as_dict"):
        try:
            return _safe(obj.as_dict())
        except Exception:
            return str(obj)

    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}

    if isinstance(obj, (list, tuple)):
        return [_safe(x) for x in obj]

    return str(obj)


def _score_from_weakness(skill, weak_list):
    for item in weak_list:
        if item.get("skill") == skill:
            return float(item.get("weakness_score", 1.0))
    return 0.0


def _score_from_importance(skill, importance_scores):
    return float(importance_scores.get(skill, 0.0))


def _score_from_error_affinity(skill, error_scores):
    return float(error_scores.get(skill, 0.0))


def _extract_meta_block(entry):
    if isinstance(entry, dict):
        return entry.get("metadata", {})
    meta = getattr(entry, "metadata", None)
    return meta if isinstance(meta, dict) else {}


def _score_from_recent_failures(skill, meta: MetaContext):
    count = 0
    for entry in meta.recent_outcomes:
        meta_block = _extract_meta_block(entry)
        if meta_block.get("skill") != skill:
            continue

        sim = meta_block.get("simulation", {})
        drift = meta_block.get("drift", {})
        reinforcement = meta_block.get("reinforcement", {})

        if drift.get("drift_score", 0) > 0.5:
            count += 1
        elif reinforcement.get("value", 0) < 0:
            count += 1

    return float(count)


def _score_from_cluster_influence(skill, clusters):
    inf = 0
    for _, members in clusters.items():
        if isinstance(members, list) and skill in members:
            inf += 1
    return float(inf)


def _score_from_usdi_window(skill, windows):
    if skill in windows.get("hot_window", []):
        return 3.0
    if skill in windows.get("warm_window", []):
        return 1.0
    return 0.0


def _score_from_normalized_usdi(skill, normalized):
    raw = normalized.get("normalized_scores", {}).get(skill)
    if raw is None:
        return 0.0
    return (raw / 100.0) * 3.0


# -------------------------------------------------------------------
# MAIN — SIGNAL-ONLY SCORING
# -------------------------------------------------------------------
def score_strategic_skill_options():
    kg_insights = get_kg_insights()
    kg_clusters = get_kg_clusters()
    kg_scores = get_kg_scores()

    weak_list = get_global_skill_weaknesses()
    weak_skills = [w.get("skill") for w in weak_list]

    meta = MetaContext.build()

    try:
        difficulty_windows = get_skill_difficulty_windows()
    except Exception:
        difficulty_windows = {}

    try:
        normalized_usdi = get_normalized_usdi()
    except Exception:
        normalized_usdi = {"normalized_scores": {}}

    candidate_skills = set()
    candidate_skills.update(weak_skills)
    candidate_skills.update(kg_scores.get("skill_importance", {}).keys())
    candidate_skills.update(kg_scores.get("error_affinity", {}).keys())

    for window in ["hot_window", "warm_window", "cool_window"]:
        candidate_skills.update(difficulty_windows.get(window, []))

    if not candidate_skills:
        return {
            "signal_code": "NO_CANDIDATES",
            "ranked_options": [],
            "timestamp": _now(),
            "drivers": {},
        }

    ranked = []
    for skill in candidate_skills:
        score = 0.0
        score += _score_from_weakness(skill, weak_list)
        score += _score_from_importance(skill, kg_scores.get("skill_importance", {}))
        score += _score_from_error_affinity(skill, kg_scores.get("error_affinity", {}))
        score += _score_from_recent_failures(skill, meta)
        score += _score_from_cluster_influence(skill, kg_clusters)
        score += _score_from_usdi_window(skill, difficulty_windows)
        score += _score_from_normalized_usdi(skill, normalized_usdi)

        ranked.append({"skill": skill, "score": float(score)})

    ranked.sort(key=lambda x: x["score"], reverse=True)

    drivers = {
        "weak_list": _safe(weak_list),
        "clusters": _safe(kg_clusters),
        "kg_scores": _safe(kg_scores),
        "meta_summary": {
            "recent_outcomes": _safe(meta.recent_outcomes[-10:]),
            "pattern_flags": _safe(meta.pattern_flags),
            "trend_summary": _safe(meta.trend_summary),
        },
        "difficulty_windows": _safe(difficulty_windows),
        "normalized_usdi": _safe(normalized_usdi),
    }

    return {
        "signal_code": "RANKED_OPTIONS",
        "ranked_options": ranked,
        "timestamp": _now(),
        "drivers": drivers,
    }


# -------------------------------------------------------------------
# Phase-40G Signal-Only choose_strategic_skill Stub
# -------------------------------------------------------------------
def choose_strategic_skill(*args, **kwargs):
    """
    Phase-40G compliant stub to satisfy imports.
    Signal-only, advisory, deterministic, no authority.
    """
    return {
        "available": True,
        "chosen_skill": None,
        "reason": "Phase-40G stub",
        "timestamp": _now(),
    }


# -------------------------------------------------------------------
# Diagnostics passthrough (SIGNAL-ONLY)
# -------------------------------------------------------------------
def get_strategic_skill_diagnostics():
    result = score_strategic_skill_options()
    return {
        "available": True,
        "signal_code": result.get("signal_code"),
        "ranked": _safe(result.get("ranked_options", []))[:10],
        "timestamp": _now(),
        "drivers": _safe(result.get("drivers", {})),
    }


# EOF

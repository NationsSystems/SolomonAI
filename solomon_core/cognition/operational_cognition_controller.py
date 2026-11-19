# operational_cognition_controller.py
# ------------------------------------------------------------
# Phase 16 — Modular Split
# Phase 18 — Stability Upgrade (Option B4-A)
# Phase 18 Step 7 — KG-aware diagnostics expansion
# Phase 19 Step 7 — Error Trend Fusion (Option C)
# Phase 20 Step 16 — USDI Integration for Operational Layer
# Phase 20 Step 17 — USDI Normalization (USDI v2)
# ------------------------------------------------------------

import datetime
from solomon_core.logger import get_logger

from solomon_core.autonomy.strict_autonomy_controller import should_autonomy_run
from solomon_core.memory_store import (
    log_memory_entry,
    get_recent_tasks,
    get_recent_memory,
)

# Knowledge Graph (Phase 18)
from solomon_core.knowledge.knowledge_graph import (
    get_kg_snapshot,
    get_kg_insights,
    get_kg_scores,
    get_kg_clusters,
    compute_error_affinity,
)

# Phase 18: KG sync
from solomon_core.knowledge.knowledge_sync import sync_knowledge_graph

# Reinforcement store
from solomon_core.reinforcement_store import (
    get_reinforcement_snapshot,
    get_reinforcement_weight,
)

# Skill analysis
from solomon_core.knowledge.skill_weakness_engine import (
    get_global_skill_weaknesses,
    score_skill_stability,
)

from solomon_core.knowledge.skill_patching_engine import (
    autonomous_skill_patch_cycle,
)

from solomon_core.knowledge.skill_lifecycle_manager import (
    autonomous_promotion_cycle,
)

# Internal introspection
from solomon_core.autonomy.internal_tasks import (
    summarize_recent_activity,
    summarize_reinforcement_trends,
    reflect_on_internal_patterns,
)

# Phase 19 — Error Trend Analyzer
from solomon_core.cognition.error_trend_analyzer import get_error_trend_summary

# ⭐ UPDATED — Phase 20 Step 17
# Replace raw USDI with normalized USDI
from solomon_core.cognition.usdi_normalizer import get_normalized_usdi

logger = get_logger("operational_cognition")


def _now():
    return datetime.datetime.utcnow().isoformat()


# ------------------------------------------------------------
# Stability + Weakness Checks (Phase 18 + Phase 19 Fusion)
# ------------------------------------------------------------
def evaluate_skill_stability():
    """
    Phase 18:
        - incorporate reinforcement weighting
        - stable ordering of weak skills
        - expose stability objects for diagnostics
    Phase 19:
        - influence stability score using error trend data
        - attach error_pressure flag (+ degrade stability if needed)
    """
    raw = get_global_skill_weaknesses()

    trends = get_error_trend_summary() or {}
    recent_error_pressure = trends.get("regressions", [])
    error_cluster_count = trends.get("error_count", 0)

    error_multiplier = 1.0
    if error_cluster_count > 0 and recent_error_pressure:
        error_multiplier = 0.85

    for entry in raw:
        skill = entry.get("skill")

        entry["reinforcement_weight"] = get_reinforcement_weight(skill) or 0.0

        st = score_skill_stability(skill)

        if isinstance(st, dict) and "total" in st:
            st["total"] = round(st["total"] * error_multiplier, 4)

        entry["stability"] = st

    raw = sorted(raw, key=lambda r: (r["score"], -r["reinforcement_weight"]))

    return {
        "weak_skills": raw[:10],
        "error_influence": {
            "errors_detected": error_cluster_count,
            "regressions": recent_error_pressure,
            "multiplier_applied": error_multiplier,
        },
        "timestamp": _now(),
    }


def evaluate_autonomy_triggers():
    gating = should_autonomy_run()
    gating["timestamp"] = _now()
    return gating


# ------------------------------------------------------------
# Operational Cognitive Cycle
# ------------------------------------------------------------
def run_operational_cognitive_cycle():
    logger.info("[Cognition] Starting operational cognitive cycle")

    gating = should_autonomy_run()
    if not gating["allowed"]:
        return {
            "success": False,
            "reason": "autonomy_blocked",
            "mode": gating["mode"],
            "details": gating["reason"],
        }

    try:
        sync_knowledge_graph()
    except Exception as e:
        logger.error(f"[Cognition] KG sync warning (ignored): {e}")

    error_trends = get_error_trend_summary()

    kg_insights = get_kg_insights()
    kg_clusters = get_kg_clusters()
    kg_scores = get_kg_scores()

    stability = evaluate_skill_stability()
    weak_list = stability["weak_skills"]

    # When no weak skills exist
    if not weak_list:
        try:
            usdi = get_normalized_usdi()
        except Exception:
            usdi = {}

        return {
            "success": True,
            "reason": "no_skills_to_improve",
            "kg": kg_insights,
            "clusters": kg_clusters,
            "scores": kg_scores,
            "stability": stability,
            "error_trends": error_trends,
            "reinforcement": get_reinforcement_snapshot(),
            "usdi": usdi,      # ⭐ NEW (normalized USDI)
            "mode": gating["mode"],
            "timestamp": _now(),
        }

    weakest_skill = weak_list[0]["skill"]

    patch_cycle = autonomous_skill_patch_cycle(weakest_skill)
    promotion = autonomous_promotion_cycle(weakest_skill)

    introspection = {
        "recent_activity": summarize_recent_activity(limit=20),
        "reinforcement": summarize_reinforcement_trends(),
        "reflection": reflect_on_internal_patterns(),
        "error_regressions": error_trends.get("regressions", []),
    }

    log_memory_entry(
        f"Operational cognition cycle on skill '{weakest_skill}' — "
        f"promotion={promotion.get('success')} "
        f"| error_clusters={error_trends.get('error_count', 0)}",
        intent="operational_cognition",
        entities={},
        result=promotion,
        summary="Operational cognition cycle executed",
        context_hint="operational_cycle",
    )

    logger.info("[Cognition] Completed operational cognitive cycle")

    # ⭐ Phase 20 Step 17 — Normalized USDI
    try:
        usdi = get_normalized_usdi()
    except Exception:
        usdi = {}

    return {
        "success": True,
        "mode": gating["mode"],
        "weakest_skill": weakest_skill,
        "patch_cycle": patch_cycle,
        "promotion": promotion,
        "kg_insights": kg_insights,
        "kg_clusters": kg_clusters,
        "kg_scores": kg_scores,
        "stability": stability,
        "reinforcement": get_reinforcement_snapshot(),
        "error_trends": error_trends,
        "usdi": usdi,        # ⭐ NEW
        "introspection": introspection,
        "timestamp": _now(),
    }


# ------------------------------------------------------------
# Diagnostics — Phase 18 + Phase 19 + Phase 20 Step 17
# ------------------------------------------------------------
def get_operational_diagnostics():
    """
    Phase 20 Step 17:
        • Inject NORMALIZED USDI (usdi_normalizer)
        • Keep error trends + stability + KG snapshot
    """
    try:
        sync_knowledge_graph()
    except Exception as e:
        logger.error(f"[Diagnostics] KG sync warning (ignored): {e}")

    try:
        reinforcement_snapshot = get_reinforcement_snapshot()
    except Exception:
        reinforcement_snapshot = {}

    stability = evaluate_skill_stability()

    recent_tasks = get_recent_tasks(limit=15)
    recent_memory = get_recent_memory(limit=15)

    try:
        error_aff = compute_error_affinity()
    except Exception:
        error_aff = {}

    error_trends = get_error_trend_summary()

    # ⭐ USDI v2 normalized output
    try:
        usdi = get_normalized_usdi()
    except Exception:
        usdi = {}

    return {
        "timestamp": _now(),
        "autonomy": evaluate_autonomy_triggers(),
        "skills": stability,
        "reinforcement": reinforcement_snapshot,
        "error_trends": error_trends,
        "usdi": usdi,        # ⭐ NEW normalized USDI
        "kg": {
            "insights": get_kg_insights(),
            "clusters": get_kg_clusters(),
            "scores": get_kg_scores(),
            "snapshot": get_kg_snapshot(),
        },
        "recent": {
            "tasks": recent_tasks,
            "memory": recent_memory,
            "error_affinity": error_aff,
            "error_regressions": error_trends.get("regressions", []),
        },
    }


__all__ = [
    "run_operational_cognitive_cycle",
    "get_operational_diagnostics",
]

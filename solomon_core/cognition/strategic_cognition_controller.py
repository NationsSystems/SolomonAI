# strategic_cognition_controller.py
# ------------------------------------------------------------
# Phase 18 — Strategic Cognition Stability Upgrade (Option B1)
# Phase 19 — Error Trend Integration (Diagnostics + Context)
# Phase 20 Step 12 — USDI Integration (Difficulty Windows)
# Phase 20 Step 13 — USDI Classification in Postmortem
# Phase 20 Step 17 — USDI Normalization (USDI v2)
# ------------------------------------------------------------

import datetime
from solomon_core.logger import get_logger

from solomon_core.autonomy.strict_autonomy_controller import should_autonomy_run

# KG Sync (safe)
from solomon_core.knowledge.knowledge_sync import sync_knowledge_graph

# Reinforcement
from solomon_core.reinforcement_store import get_reinforcement_snapshot

# Planner & simulation
from solomon_core.planner.strategic_planner import StrategicPlanner, StrategyContext
from solomon_core.planner.plan_scoring_engine import score_plan
from solomon_core.planner.plan_simulation_engine import simulate_plan
from solomon_core.planner.strategic_memory import (
    record_plan_outcome,
    get_strategic_memory_snapshot,
)

# KG
from solomon_core.knowledge.knowledge_graph import (
    get_kg_insights,
    get_kg_scores,
    get_kg_clusters,
    get_strategic_kg_summary,
)

# Skills
from solomon_core.knowledge.skill_weakness_engine import get_global_skill_weaknesses

# Actionization/execution/drift
from solomon_core.cognition.strategic_action_engine import actionize_plan
from solomon_core.cognition.strategic_action_executor import (
    execute_action_chain,
    prepare_execution_feedback,
    compute_reinforcement_signal,
)
from solomon_core.cognition.strategic_drift_detector import compare_expected_vs_actual

# Outcome analysis
from solomon_core.cognition.strategic_outcome_analyzer import analyze_strategic_outcome

# Meta
from solomon_core.cognition.meta.meta_context import MetaContext
from solomon_core.cognition.meta.meta_snapshot_engine import generate_meta_snapshot
from solomon_core.cognition.meta.meta_summary_printer import render_meta_summary

# Priority skill selection
from solomon_core.cognition.strategic_skill_selector import (
    choose_strategic_skill,
    get_strategic_skill_diagnostics,
)

# Normalizer
from solomon_core.cognition.strategic_summary_normalizer import (
    normalize_strategic_summary,
)

# Error Trends
from solomon_core.cognition.error_trend_analyzer import get_error_trend_summary

# ⭐ UPDATED — Phase 20 Step 17: Normalized USDI
from solomon_core.cognition.usdi_normalizer import get_normalized_usdi

logger = get_logger("strategic_cognition")


def _now():
    return datetime.datetime.utcnow().isoformat()


def _safe_dict(o):
    try:
        if hasattr(o, "as_dict"):
            return o.as_dict()
        return dict(o)
    except Exception:
        return {}


# ------------------------------------------------------------
# Strategic Planning Cycle
# ------------------------------------------------------------
def run_strategic_cognitive_cycle():
    logger.info("[Cognition] Starting strategic planning cycle")

    gating = should_autonomy_run()
    if not gating["allowed"]:
        result = {
            "success": False,
            "mode": gating["mode"],
            "reason": "autonomy_blocked",
            "details": gating["reason"],
            "timestamp": _now(),
        }
        result["normalized_strategic_summary"] = normalize_strategic_summary(result)
        return result

    try:
        sync_knowledge_graph()
    except Exception as e:
        logger.error(f"[Cognition] Strategic KG sync warning: {e}")

    # Error trends
    try:
        error_trends = get_error_trend_summary()
    except Exception:
        error_trends = {}

    # ⭐ UPDATED — Normalized USDI (Step 17)
    try:
        difficulty_windows = get_normalized_usdi()
    except Exception:
        difficulty_windows = {}

    # Priority selection
    priority_selection = choose_strategic_skill()
    priority_skill = priority_selection.get("priority_skill")
    ranked_list = priority_selection.get("ranked") or []

    # Build context
    context = StrategyContext(
        kg_insights=get_kg_insights(),
        kg_scores=get_kg_scores(),
        kg_clusters=get_kg_clusters(),
        weak_skills=get_global_skill_weaknesses(),
        autonomy_status=gating,
        strategic_priority=priority_skill,
        error_trends=error_trends,
        timestamp=_now(),
    )

    planner = StrategicPlanner()
    plans = planner.generate_candidate_plans(context)

    if not plans:
        result = {
            "success": True,
            "mode": gating["mode"],
            "reason": "no_plans_available",
            "priority_skill": priority_skill,
            "priority_ranking": ranked_list,
            "context": context.as_dict(),
            "timestamp": _now(),
            "error_trends": error_trends,
            "difficulty_windows": difficulty_windows,
        }
        result["normalized_strategic_summary"] = normalize_strategic_summary(result)
        return result

    evaluated = []
    for plan in plans:
        try:
            score = score_plan(plan, context)
            sim = simulate_plan(plan, context)
            evaluated.append({"plan": plan, "score": score, "simulation": sim})
        except Exception as e:
            logger.error(f"[Cognition] Plan evaluation error: {e}")

    if not evaluated:
        result = {
            "success": False,
            "reason": "evaluation_failed",
            "priority_skill": priority_skill,
            "context": context.as_dict(),
            "timestamp": _now(),
            "error_trends": error_trends,
            "difficulty_windows": difficulty_windows,
        }
        result["normalized_strategic_summary"] = normalize_strategic_summary(result)
        return result

    # Ranking
    try:
        ranked = sorted(evaluated, key=lambda x: x["score"].final_score, reverse=True)
        best = ranked[0]
    except Exception:
        result = {
            "success": False,
            "reason": "ranking_failed",
            "priority_skill": priority_skill,
            "context": context.as_dict(),
            "timestamp": _now(),
            "error_trends": error_trends,
            "difficulty_windows": difficulty_windows,
        }
        result["normalized_strategic_summary"] = normalize_strategic_summary(result)
        return result

    best_plan = best["plan"]
    best_score = best["score"]
    best_sim = best["simulation"]

    # Execution
    try:
        actionization = actionize_plan(best_plan, context)
        execution_results = execute_action_chain(actionization.actions, context)
        drift = compare_expected_vs_actual(best_sim, execution_results, context)
        execution_feedback = prepare_execution_feedback(execution_results, context)
        reinforcement_signal = compute_reinforcement_signal(execution_feedback, context)

        outcome_analysis = analyze_strategic_outcome(
            simulation=_safe_dict(best_sim),
            execution_feedback=execution_feedback.as_dict(),
            drift=drift.as_dict(),
            reinforcement=reinforcement_signal.as_dict(),
        )
    except Exception:
        result = {
            "success": False,
            "reason": "execution_failed",
            "priority_skill": priority_skill,
            "context": context.as_dict(),
            "timestamp": _now(),
            "error_trends": error_trends,
            "difficulty_windows": difficulty_windows,
        }
        result["normalized_strategic_summary"] = normalize_strategic_summary(result)
        return result

    # Meta and memory
    meta_ctx = MetaContext.build()
    meta_snapshot = generate_meta_snapshot(meta_ctx)
    meta_summary = render_meta_summary(meta_snapshot)

    try:
        record_plan_outcome(
            best_plan.objective.objective,
            {
                "score": best_score.final_score,
                "timestamp": _now(),
                "simulation": best_sim.as_dict(),
                "drift": drift.as_dict(),
                "feedback": execution_feedback.as_dict(),
                "reinforcement": reinforcement_signal.as_dict(),
                "outcome_analysis": outcome_analysis.as_dict(),
                "meta_snapshot": meta_snapshot,
                "priority_skill": priority_skill,
                "priority_ranking": ranked_list,
                "error_trends": error_trends,
                "difficulty_windows": difficulty_windows,
            },
        )
    except Exception:
        logger.error("[Cognition] Memory write error")

    # Final result
    result = {
        "success": True,
        "mode": gating["mode"],
        "priority_skill": priority_skill,
        "priority_ranking": ranked_list,
        "best_plan": best_plan.as_dict(),
        "best_score": best_score.to_dict(),
        "best_simulation": best_sim.as_dict(),
        "actionization": actionization.as_dict(),
        "execution_results": [r.as_dict() for r in execution_results],
        "execution_feedback": execution_feedback.as_dict(),
        "reinforcement_signal": reinforcement_signal.as_dict(),
        "outcome_analysis": outcome_analysis.as_dict(),
        "drift": drift.as_dict(),
        "meta_snapshot": meta_snapshot,
        "meta_summary": meta_summary,
        "context": context.as_dict(),
        "all_plans": [
            {
                "plan": x["plan"].as_dict(),
                "score": x["score"].to_dict(),
                "simulation": x["simulation"].as_dict(),
            }
            for x in ranked
        ],
        "timestamp": _now(),
        "error_trends": error_trends,
        "difficulty_windows": difficulty_windows,
    }

    result["normalized_strategic_summary"] = normalize_strategic_summary(result)
    return result


# ------------------------------------------------------------
# Strategic Diagnostics
# ------------------------------------------------------------
def get_strategic_diagnostics():
    try:
        reinforcement_snapshot = get_reinforcement_snapshot()
    except Exception:
        reinforcement_snapshot = {}

    try:
        error_trends = get_error_trend_summary()
    except Exception:
        error_trends = {}

    # ⭐ Replace with normalized USDI
    try:
        difficulty_windows = get_normalized_usdi()
    except Exception:
        difficulty_windows = {}

    return {
        "kg": {
            "insights": get_kg_insights(),
            "clusters": get_kg_clusters(),
            "scores": get_kg_scores(),
            "strategic_summary": get_strategic_kg_summary(),
        },
        "reinforcement": reinforcement_snapshot,
        "weak_skills": {"weak_skills": get_global_skill_weaknesses()},
        "strategic_skill_selector": get_strategic_skill_diagnostics(),
        "error_trends": error_trends,
        "difficulty_windows": difficulty_windows,
        "timestamp": _now(),
    }


# ------------------------------------------------------------
# Strategic Postmortem (USDI Classification v2)
# ------------------------------------------------------------
def generate_strategic_postmortem():
    outcomes = get_strategic_memory_snapshot()
    if not outcomes:
        return {
            "available": False,
            "reason": "no_outcomes_recorded",
            "timestamp": _now(),
        }

    last = outcomes[-1]
    meta = last.get("metadata", {})

    difficulty_windows = meta.get("difficulty_windows", {})

    obj = last.get("objective") or {}
    skill = None
    try:
        skill = obj.get("metadata", {}).get("skill")
    except Exception:
        skill = None

    if skill:
        if skill in difficulty_windows.get("hot_window", []):
            usdi_class = "hot"
        elif skill in difficulty_windows.get("warm_window", []):
            usdi_class = "warm"
        else:
            usdi_class = "cool"
    else:
        usdi_class = None

    return {
        "available": True,
        "objective": last.get("objective"),
        "score": meta.get("score"),
        "simulation": meta.get("simulation"),
        "drift": meta.get("drift"),
        "feedback": meta.get("feedback"),
        "reinforcement": meta.get("reinforcement"),
        "analysis": meta.get("outcome_analysis"),
        "error_trends": meta.get("error_trends"),
        "difficulty_windows": difficulty_windows,
        "usdi_classification": usdi_class,
        "timestamp": _now(),
    }

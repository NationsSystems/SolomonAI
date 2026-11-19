# skill_weakness_engine.py — Phase 20 Step 3 (Option A: SQS Framework)
# ---------------------------------------------------------------------------
# Replaces unstable “stability score” with the Skill Quality Score (SQS)
# SQS = (Usage + Performance + KG Importance + Planner Conf + Reinforcement)
#       − (Error Pressure + Complexity + HFLO Pending + Fallback Penalty)
#
# Adds:
#   • SQS normalization (0–100)
#   • Tiering: healthy / caution / at_risk / critical
#   • Trend damping (prevents oscillation)
#   • Error-pressure influence from Phase 19
# ---------------------------------------------------------------------------

import re
import ast
import inspect
from collections import defaultdict

from solomon_core.logger import get_logger
from solomon_core.knowledge.knowledge_graph import (
    get_skill_usage,
    compute_error_affinity,
    KG,
)
from solomon_core.memory_store import get_recent_tasks
from solomon_core.skill_registry import lookup_skill
from solomon_core.reinforcement_store import get_reinforcement_snapshot

from solomon_core.models import HfloPendingUpgrade
from solomon_core.db import SessionLocal

# NEW — Error trend injection (Phase 20 uses Phase 19 data)
from solomon_core.cognition.error_trend_analyzer import get_error_trend_summary

logger = get_logger("skill_weakness_engine")


# =============================================================
# Utilities
# =============================================================
def _canon(val):
    return str(val).strip().lower() if val else None


def _get_skill_source(skill_func):
    try:
        return inspect.getsource(skill_func)
    except Exception:
        return ""


# =============================================================
# Usage + Performance
# =============================================================
def analyze_skill_usage(skill_name):
    skill_name = _canon(skill_name)
    return len(get_skill_usage(skill_name))


def compute_skill_success_rates(skill_name, window=100):
    tasks = get_recent_tasks(limit=window)
    success = fail = fallback = 0

    for t in tasks:
        skills = t.get("skills", [])
        if not skills:
            continue

        if skill_name in [s.lower() for s in skills]:
            if t.get("error"):
                fail += 1
            else:
                success += 1

            if t.get("reasoning_source") == "llm":
                fallback += 1

    total = success + fail

    # smoothing prevents oscillation
    success_rate = (success + 1) / (total + 2)
    fail_rate = (fail + 1) / (total + 2)

    return {
        "success_rate": success_rate,
        "fail_rate": fail_rate,
        "fallback_count": fallback,
        "success_count": success,
        "fail_count": fail,
        "total": total,
    }


def compute_skill_error_rates(skill_name):
    affinity = compute_error_affinity()
    skill_name = _canon(skill_name)
    return {
        err: w for (skill, err), w in affinity.items()
        if skill == skill_name
    }


# =============================================================
# Complexity
# =============================================================
def detect_skill_complexity(skill_name):
    skill = lookup_skill(skill_name)
    if not skill:
        return {"lines": 0, "max_depth": 0, "complexity": 0}

    func = skill.get("callable")
    src = _get_skill_source(func)
    if not src:
        return {"lines": 0, "max_depth": 0, "complexity": 0}

    lines = src.count("\n")
    max_depth = 0

    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            depth = len(list(ast.iter_child_nodes(node)))
            max_depth = max(max_depth, depth)
    except Exception:
        max_depth = 0

    return {
        "lines": lines,
        "max_depth": max_depth,
        "complexity": lines + max_depth,
    }


# =============================================================
# Weights (KG + planner + HFLO + reinforcement)
# =============================================================
def _get_hflo_pending(skill_name):
    db = SessionLocal()
    try:
        return db.query(HfloPendingUpgrade).filter_by(
            skill_name=skill_name, reviewed=False
        ).count()
    finally:
        db.close()


def _planner_confidence_avg(skill_name, window=100):
    tasks = get_recent_tasks(limit=window)
    vals = []
    for t in tasks:
        if skill_name in [s.lower() for s in (t.get("skills") or [])]:
            c = t.get("confidence")
            if isinstance(c, (float, int)):
                vals.append(float(c))
    if not vals:
        return 0.0
    return sum(vals) / max(len(vals), 3)


def _kg_skill_importance(skill_name):
    skill_name = _canon(skill_name)
    score = 0
    for (src, sid, rel, dst, did), w in KG["weights"].items():
        if src == "task" and rel == "invokes_skill" and did == skill_name:
            score += w
        if src == "skill" and sid == skill_name and rel == "touches_file":
            score += w * 0.5
    return score


def _reinforcement_weight(skill_name):
    snapshot = get_reinforcement_snapshot() or {}
    total = 0.0
    for key, val in snapshot.items():
        if key.startswith(skill_name + "/"):
            total += float(val.get("weight", 0.0))
    return total


# =============================================================
# ★ Phase 20 — Skill Quality Score (SQS)
# =============================================================
def score_skill_stability(skill_name):
    """
    Option A — SQS Framework
    Produces:
        • normalized score (0–100)
        • tier label
        • full metrics package
    """
    skill = _canon(skill_name)

    usage = analyze_skill_usage(skill)
    perf = compute_skill_success_rates(skill)
    errors = compute_skill_error_rates(skill)
    complexity = detect_skill_complexity(skill)

    kg_imp = _kg_skill_importance(skill)
    planner_conf = _planner_confidence_avg(skill)
    reinforcement = _reinforcement_weight(skill)
    hflo = _get_hflo_pending(skill)

    # Phase 19 error trends influence
    trends = get_error_trend_summary() or {}
    recent_error_pressure = len(trends.get("regressions", []))

    # ----------------------------
    # Raw weighted score
    # ----------------------------
    raw = 0
    raw += usage * 2
    raw += perf["success_rate"] * 40
    raw -= perf["fail_rate"] * 40
    raw -= len(errors) * 3
    raw -= complexity["complexity"] / 55
    raw -= perf["fallback_count"] * 4

    raw += planner_conf * 10
    raw += reinforcement * 3
    raw += kg_imp * 0.3

    raw -= hflo * 5
    raw -= recent_error_pressure * 2  # NEW Phase 20 influence

    # ----------------------------
    # Normalize → 0–100
    # smooth damping prevents jitter
    # ----------------------------
    normalized = max(0, min(100, round((raw + 50) / 1.5, 2)))

    # ----------------------------
    # Tiering
    # ----------------------------
    if normalized >= 70:
        tier = "healthy"
    elif normalized >= 45:
        tier = "caution"
    elif normalized >= 25:
        tier = "at_risk"
    else:
        tier = "critical"

    return {
        "skill": skill,
        "score": normalized,
        "tier": tier,
        "raw_score": raw,
        "usage": usage,
        "performance": perf,
        "errors": errors,
        "complexity": complexity,
        "reinforcement": reinforcement,
        "planner_confidence": planner_conf,
        "kg_importance": kg_imp,
        "hflo_pending": hflo,
        "error_pressure": recent_error_pressure,
    }


# =============================================================
# Skill Weakness Reports
# =============================================================
def get_skill_weakness_report(skill_name):
    skill_name = _canon(skill_name)
    analysis = score_skill_stability(skill_name)

    issues = []
    perf = analysis["performance"]

    if perf["fail_rate"] > 0.45: issues.append("High failure rate")
    if perf["fallback_count"] > 0: issues.append("LLM fallback detected")
    if len(analysis["errors"]) >= 3: issues.append("Strong error affinity")
    if analysis["complexity"]["complexity"] > 250: issues.append("High complexity")
    if analysis["reinforcement"] < -0.2: issues.append("Negative reinforcement")
    if analysis["planner_confidence"] < 0.25: issues.append("Low planner confidence")
    if analysis["tier"] == "critical": issues.append("Critical SQS")
    if analysis["tier"] == "at_risk": issues.append("At-risk SQS")

    return {
        "skill": skill_name,
        "score": analysis["score"],
        "tier": analysis["tier"],
        "issues": issues,
        "analysis": analysis,
        "recommendation": (
            "patch" if analysis["tier"] in ["critical", "at_risk"]
            else "monitor" if analysis["tier"] == "caution"
            else "healthy"
        )
    }


def get_global_skill_weaknesses():
    out = []
    for skill in KG["skills"].keys():
        out.append(get_skill_weakness_report(skill))

    # Lowest score first
    return sorted(out, key=lambda x: x["score"])

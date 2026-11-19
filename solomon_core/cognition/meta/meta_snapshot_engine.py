# meta_snapshot_engine.py — Phase 15 Step 4 + Phase 16 Step 21 + Phase 18 Upgrade + Phase 20 Error-Trend Integration
# ------------------------------------------------------------
# META SNAPSHOT ENGINE (Upgraded through Phase 20)
# ------------------------------------------------------------
# Purpose:
#   Convert a fully populated MetaContext into a unified read-only
#   meta snapshot used by:
#       • meta-analysis
#       • diagnostics
#       • stability interpretation
#       • strategic meta-evaluation
#       • Phase 20 USDI Integration tests
#
# Phase 20 Adds:
#   • error_trends block (required by USDI Integration test)
#   • Must be JSON-safe
# ------------------------------------------------------------

from typing import Dict, Any
from solomon_core.cognition.meta.meta_context import MetaContext

# Phase 18 additions
from solomon_core.reinforcement_store import get_reinforcement_snapshot

# Phase 20 — Error trend analyzer (REQUIRED)
from solomon_core.cognition.error_trend_analyzer import get_error_trend_summary


# ------------------------------------------------------------
# Helpers from Phase 16 (unchanged)
# ------------------------------------------------------------
def _compute_drift_band_distribution(outcomes):
    bands = {"stable": 0, "low": 0, "moderate": 0, "high": 0}

    for o in outcomes:
        band = getattr(o, "drift_band", None)
        if band in bands:
            bands[band] += 1

    total = sum(bands.values())
    if total == 0:
        return bands

    return {k: v / total for k, v in bands.items()}


def _compute_confidence_profile(outcomes):
    confidences = []
    for o in outcomes:
        c = getattr(o, "confidence", None)
        if isinstance(c, (float, int)):
            confidences.append(c)

    if not confidences:
        return {
            "average": None,
            "min": None,
            "max": None,
            "trend": "no_data",
        }

    avg = sum(confidences) / len(confidences)

    if avg > 0.65:
        trend = "high_confidence"
    elif avg < 0.25:
        trend = "low_confidence"
    else:
        trend = "moderate"

    return {
        "average": avg,
        "min": min(confidences),
        "max": max(confidences),
        "trend": trend,
    }


def _compute_priority_alignment(ctx: MetaContext):
    priority = ctx.priority_skill
    if not priority:
        return {"priority_skill": None, "alignment_signal": "none"}

    alignments = []
    for o in ctx.recent_outcomes[-10:]:
        if hasattr(o, "priority_alignment"):
            alignments.append(o.priority_alignment)

    if not alignments:
        return {
            "priority_skill": priority,
            "alignment_signal": "insufficient_data",
        }

    ratio = sum(1 for x in alignments if x) / len(alignments)

    if ratio > 0.7:
        signal = "strong_alignment"
    elif ratio > 0.3:
        signal = "partial_alignment"
    else:
        signal = "weak_alignment"

    return {
        "priority_skill": priority,
        "alignment_signal": signal,
        "alignment_ratio": ratio,
    }


# ------------------------------------------------------------
# Phase 18 Upgrade — KG Echo + Weak Skill Stability
# ------------------------------------------------------------
def _extract_kg_stability(kg_summary):
    if not kg_summary:
        return {"kg_stability": "unknown"}

    stability = kg_summary.get("stability")
    if not stability:
        return {"kg_stability": "unknown"}

    score = stability.get("score")
    if score is None:
        return {"kg_stability": "unknown"}

    if score > 0.75:
        return {"kg_stability": "high"}
    if score < 0.25:
        return {"kg_stability": "low"}
    return {"kg_stability": "moderate"}


def _extract_weak_skill_echo(skill_list):
    if not skill_list:
        return []
    trimmed = sorted(
        skill_list,
        key=lambda x: (x.get("score", 0), -x.get("reinforcement_weight", 0)),
    )
    return trimmed[:5]


# ------------------------------------------------------------
# MAIN SNAPSHOT (Phase 20 Upgraded)
# ------------------------------------------------------------
def generate_meta_snapshot(ctx: MetaContext) -> Dict[str, Any]:

    recent_outcomes = ctx.recent_outcomes[-10:]

    drift_band_dist = _compute_drift_band_distribution(recent_outcomes)
    confidence_profile = _compute_confidence_profile(recent_outcomes)
    priority_alignment = _compute_priority_alignment(ctx)

    # Phase 18: reinforcement + KG + weak-skill echo
    reinforcement_snapshot = get_reinforcement_snapshot() or {}
    kg_stability = _extract_kg_stability(ctx.kg_summary)
    weak_skill_echo = _extract_weak_skill_echo(ctx.skill_weaknesses)

    # Phase 20: error trend summary (JSON-SAFE)
    error_trends = get_error_trend_summary()

    # -------------------------------------------------------
    # Base snapshot structure
    # -------------------------------------------------------
    snapshot = {
        "timestamp": ctx.timestamp,

        "meta": {
            "drift_profile": ctx.drift_profile,
            "reinforcement_profile": ctx.reinforcement_profile,
            "reinforcement_snapshot": reinforcement_snapshot,
            "kg_summary": ctx.kg_summary,
            "kg_stability": kg_stability,
            "skill_weaknesses": ctx.skill_weaknesses,
            "weak_skill_echo": weak_skill_echo,
            "autonomy_status": ctx.autonomy_status,

            "priority_skill": ctx.priority_skill,
            "priority_alignment": priority_alignment,
            "drift_band_distribution": drift_band_dist,
            "confidence_profile": confidence_profile,

            # Phase 20 REQUIRED FIELD
            "error_trends": error_trends,
        },

        "recent_activity": {
            "outcomes": [
                o.as_dict() if hasattr(o, "as_dict") else str(o)
                for o in recent_outcomes
            ],
            "scores": ctx.recent_scores[-10:],
            "simulations": ctx.recent_simulations[-10:],
        },

        "patterns": ctx.pattern_flags,
    }

    # -------------------------------------------------------
    # Phase 18 Stability Logic
    # -------------------------------------------------------
    drift_val = ctx.drift_profile.get("overall_drift") if ctx.drift_profile else None
    reinforce_avg = ctx.reinforcement_profile.get("average_signal") if ctx.reinforcement_profile else None
    conf_avg = confidence_profile.get("average")
    priority_sig = priority_alignment.get("alignment_signal")
    kg_state = kg_stability.get("kg_stability")

    stability = "insufficient_data"

    if drift_val is not None and reinforce_avg is not None and conf_avg is not None:

        if (
            drift_val < 0.15
            and reinforce_avg > 0.6
            and conf_avg and conf_avg > 0.5
            and priority_sig == "strong_alignment"
            and kg_state == "high"
        ):
            stability = "high_stability"

        elif (
            drift_val > 0.6
            or priority_sig == "weak_alignment"
            or (conf_avg and conf_avg < 0.2)
            or kg_state == "low"
        ):
            stability = "instability_detected"

        else:
            stability = "mixed"

    snapshot["meta"]["stability_signal"] = stability

    # -------------------------------------------------------
    # Enhanced Pattern synthesis (unchanged)
    # -------------------------------------------------------
    synthesis = []
    pat = ctx.pattern_flags

    if pat.get("reinforcement_trend") == "strong_positive":
        synthesis.append("reinforcement improving strongly")

    if pat.get("drift_state") == "high_drift":
        synthesis.append("drift rising - investigate stability")

    if pat.get("objective_repetition") == "same_objective_repeated":
        synthesis.append("possible objective fixation detected")

    if pat.get("simulation_consistency") == "high_consistency":
        synthesis.append("simulation space stable and predictable")

    if pat.get("score_trend") == "improving":
        synthesis.append("plan quality trending upward")

    if priority_alignment.get("alignment_signal") == "strong_alignment":
        synthesis.append("priority skill strongly aligned with strategic behavior")

    if confidence_profile.get("trend") == "low_confidence":
        synthesis.append("low confidence reinforcement detected")

    if drift_band_dist.get("high", 0) > 0.3:
        synthesis.append("significant frequency of high drift events detected")

    if kg_state == "low":
        synthesis.append("knowledge graph instability detected")

    if weak_skill_echo:
        synthesis.append("weak skill cluster contributing to instability")

    snapshot["pattern_synthesis"] = synthesis

    return snapshot


# ----------------------------------------------------------
# COMPATIBILITY WRAPPER
# ----------------------------------------------------------
def build_meta_snapshot(ctx: MetaContext) -> Dict[str, Any]:
    return generate_meta_snapshot(ctx)

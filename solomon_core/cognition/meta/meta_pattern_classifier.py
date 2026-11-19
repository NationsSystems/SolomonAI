# meta_pattern_classifier.py — Phase 15 Step 3 + Phase 16 Enhancements
# + Phase 18 Stability Upgrade (Option B1)
# -------------------------------------------------------------------
# META PATTERN CLASSIFIER
#
# Purpose:
#   Inspect MetaContext and compute qualitative pattern flags:
#       • drift patterns
#       • reinforcement patterns
#       • simulation consistency
#       • score clusters
#       • outcome structure trends
#       • priority alignment signals
#       • weak-skill persistence patterns
#       • cross-signal correlations
#       • KG stability echoes                        (NEW — Phase 18)
#       • multi-domain stability patterns            (NEW — Phase 18)
#       • reinforcement-snapshot meta patterns       (NEW — Phase 18)
#
# Notes:
#   Pure read-only pattern generation.
#   No scoring updates, no memory writes, no mutations
#   outside ctx.pattern_flags.
# -------------------------------------------------------------------

from typing import Dict, Any
from solomon_core.cognition.meta.meta_context import MetaContext
from solomon_core.reinforcement_store import get_reinforcement_snapshot


def classify_meta_patterns(ctx: MetaContext) -> Dict[str, Any]:
    """
    Evaluate internal patterns and assign high-level qualitative pattern flags.
    All results go into ctx.pattern_flags.
    """

    patterns: Dict[str, Any] = {}

    # ------------------------------------------------------
    # SAFETY: local variables for clarity
    # ------------------------------------------------------
    rprof = ctx.reinforcement_profile or {}
    drift = ctx.drift_profile or {}
    outcomes = ctx.recent_outcomes or []
    sims = ctx.recent_simulations or []
    scores = ctx.recent_scores or []
    weaknesses = ctx.skill_weaknesses or []
    kg_summary = ctx.kg_summary or {}

    # ------------------------------------------------------
    # Phase 18: Reinforcement Snapshot Awareness
    # ------------------------------------------------------
    try:
        reinforcement_snapshot = get_reinforcement_snapshot() or {}
        patterns["reinforcement_snapshot_state"] = (
            "healthy" if reinforcement_snapshot else "no_snapshot"
        )
    except Exception:
        patterns["reinforcement_snapshot_state"] = "snapshot_error"

    # ------------------------------------------------------
    # 1. Reinforcement pattern check
    # ------------------------------------------------------
    avg = rprof.get("average_signal", None)
    if avg is not None:
        if avg > 0.7:
            patterns["reinforcement_trend"] = "strong_positive"
        elif avg > 0.4:
            patterns["reinforcement_trend"] = "moderate_positive"
        elif avg < 0.1:
            patterns["reinforcement_trend"] = "weak"
        else:
            patterns["reinforcement_trend"] = "neutral"

    # ------------------------------------------------------
    # 2. Drift profile pattern check
    # ------------------------------------------------------
    d_level = drift.get("overall_drift", None)
    if d_level is not None:
        if d_level > 0.7:
            patterns["drift_state"] = "high_drift"
        elif d_level > 0.3:
            patterns["drift_state"] = "moderate_drift"
        elif d_level <= 0.1:
            patterns["drift_state"] = "stable"
        else:
            patterns["drift_state"] = "low_drift"

    # ------------------------------------------------------
    # 3. Outcome repetition patterns
    # ------------------------------------------------------
    if len(outcomes) >= 3:
        last3 = [o.get("objective") for o in outcomes[-3:]]
        if len(set(last3)) == 1:
            patterns["objective_repetition"] = "same_objective_repeated"
        else:
            patterns["objective_repetition"] = "diverse"

    # ------------------------------------------------------
    # 4. Simulation consistency
    # ------------------------------------------------------
    if len(sims) >= 3:
        try:
            improvements = [
                s.get("expected_total_improvement", 0) for s in sims[-3:]
            ]
            variance = max(improvements) - min(improvements)

            if variance < 0.05:
                patterns["simulation_consistency"] = "high_consistency"
            elif variance < 0.20:
                patterns["simulation_consistency"] = "moderate_consistency"
            else:
                patterns["simulation_consistency"] = "inconsistent"
        except Exception:
            patterns["simulation_consistency"] = "unknown"

    # ------------------------------------------------------
    # 5. Score trend direction
    # ------------------------------------------------------
    if len(scores) >= 2:
        last = (
            scores[-1].get("final_score", 0)
            if isinstance(scores[-1], dict)
            else scores[-1]
        )
        prev = (
            scores[-2].get("final_score", 0)
            if isinstance(scores[-2], dict)
            else scores[-2]
        )

        if last > prev:
            patterns["score_trend"] = "improving"
        elif last < prev:
            patterns["score_trend"] = "declining"
        else:
            patterns["score_trend"] = "flat"

    # ------------------------------------------------------
    # 6. Weak-skill persistence (Phase 16)
    # ------------------------------------------------------
    if weaknesses:
        skill_names = [w.get("skill") for w in weaknesses]
        persistent = len(set(skill_names)) == 1

        if persistent:
            patterns["weak_skill_persistence"] = "persistent_single_weakness"
        else:
            patterns["weak_skill_persistence"] = "distributed_weaknesses"

    # ------------------------------------------------------
    # 7. Priority alignment signals (Phase 16)
    # ------------------------------------------------------
    priority = (
        ctx.autonomy_status.get("priority_skill")
        if isinstance(ctx.autonomy_status, dict)
        else None
    )

    if priority:
        occurrences = sum(
            1 for o in outcomes if priority in (o.get("objective") or "")
        )
        if occurrences >= 3:
            patterns["priority_focus_pattern"] = "strong_alignment"
        elif occurrences >= 1:
            patterns["priority_focus_pattern"] = "moderate_alignment"
        else:
            patterns["priority_focus_pattern"] = "weak_alignment"

    # ------------------------------------------------------
    # Phase 18 — KG stability pattern integration
    # ------------------------------------------------------
    kg_stable = None
    try:
        stability = kg_summary.get("stability", {})
        score = stability.get("score", None)
        if score is not None:
            if score > 0.75:
                kg_stable = "high"
            elif score < 0.25:
                kg_stable = "low"
            else:
                kg_stable = "moderate"
    except Exception:
        kg_stable = "unknown"

    patterns["kg_stability_pattern"] = kg_stable

    # ------------------------------------------------------
    # Phase 18 — Multi-domain correlation reasoning
    # ------------------------------------------------------
    reinforcement = patterns.get("reinforcement_trend")
    drift_state = patterns.get("drift_state")
    score_trend = patterns.get("score_trend")

    if reinforcement and drift_state:
        if (
            reinforcement in {"strong_positive", "moderate_positive"}
            and drift_state == "stable"
            and kg_stable == "high"
        ):
            patterns["cross_domain_stability"] = "high"
        elif (
            reinforcement == "weak"
            or drift_state == "high_drift"
            or kg_stable == "low"
        ):
            patterns["cross_domain_stability"] = "instability_risk"
        else:
            patterns["cross_domain_stability"] = "mixed"

    # ------------------------------------------------------
    # 9. System-level meta-summary (enhanced Phase 18)
    # ------------------------------------------------------
    if "drift_state" in patterns and "reinforcement_trend" in patterns:
        if (
            patterns["drift_state"] == "stable"
            and patterns["reinforcement_trend"]
            in {"strong_positive", "moderate_positive"}
            and kg_stable == "high"
        ):
            patterns["system_stability"] = "strong"
        elif (
            patterns["drift_state"] == "high_drift"
            or kg_stable == "low"
        ):
            patterns["system_stability"] = "unstable"
        else:
            patterns["system_stability"] = "mixed"

    # ------------------------------------------------------
    # Finalize
    # ------------------------------------------------------
    ctx.pattern_flags = patterns
    return patterns

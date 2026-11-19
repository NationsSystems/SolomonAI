# meta_trend_engine.py — Phase 15 Step 1 + Phase 16 Trend Expansion
# + Phase 18 Stability Upgrade (Option B1)
# -----------------------------------------------------------------
# Purpose:
#   Detect trends across strategic cycles, including:
#       • reinforcement trends
#       • drift trends
#       • score trajectories
#       • simulation stability
#       • weak-skill progression
#       • priority alignment trends
#       • correlation mapping
#       • KG stability echo (Phase 18)
#       • stability-weighted meta-trend score (Phase 18)
#
# Notes:
#   Pure read-only analysis.
#   No writes, no updates to memory, no learning.
# -----------------------------------------------------------------

from typing import Dict, Any, List
from solomon_core.reinforcement_store import get_reinforcement_snapshot
from solomon_core.knowledge.knowledge_graph import get_strategic_kg_summary


class MetaTrendEngine:
    """
    Enhanced Phase 18 meta-trend engine.
    Produces a richer, stability-aware meta-trend summary.
    """

    @staticmethod
    def _rolling_average(values: List[float]) -> float:
        return sum(values) / len(values) if values else None

    @staticmethod
    def _volatility(values: List[float]) -> float:
        if len(values) < 2:
            return 0.0
        return max(values) - min(values)

    @staticmethod
    def _extract_kg_stability(kg_summary):
        """
        Mirrors Phase 18 stability rollup in meta_snapshot_engine.
        """
        if not kg_summary:
            return "unknown"

        stability = kg_summary.get("stability")
        if not stability:
            return "unknown"

        score = stability.get("score")
        if score is None:
            return "unknown"

        if score > 0.75:
            return "high"
        if score < 0.25:
            return "low"
        return "moderate"

    @staticmethod
    def compute(ctx) -> Dict[str, Any]:
        """
        Context-aware trend extraction.
        Consumes:
            ctx.reinforcement_profile
            ctx.drift_profile
            ctx.pattern_flags
            ctx.recent_scores
            ctx.recent_simulations
            ctx.skill_weaknesses
            ctx.autonomy_status
        """

        # ------------------------------------------------------
        # Reinforcement & drift trends
        # ------------------------------------------------------
        reinforcement_avg = (
            ctx.reinforcement_profile.get("average_signal")
            if ctx.reinforcement_profile else None
        )
        drift_avg = (
            ctx.drift_profile.get("overall_drift")
            if ctx.drift_profile else None
        )

        # Correlation signal
        if reinforcement_avg is not None and drift_avg is not None:
            if reinforcement_avg > 0.6 and drift_avg < 0.15:
                reinforcement_drift_correlation = "strengthening"
            elif reinforcement_avg < 0.2 and drift_avg > 0.5:
                reinforcement_drift_correlation = "weakening"
            else:
                reinforcement_drift_correlation = "mixed"
        else:
            reinforcement_drift_correlation = "unknown"

        # ------------------------------------------------------
        # Score trajectory
        # ------------------------------------------------------
        scores = []
        for s in ctx.recent_scores:
            if isinstance(s, dict):
                scores.append(s.get("final_score", 0))
            else:
                scores.append(s)

        score_avg = MetaTrendEngine._rolling_average(scores)
        score_volatility = MetaTrendEngine._volatility(scores)

        # ------------------------------------------------------
        # Simulation stability
        # ------------------------------------------------------
        sims = []
        for s in ctx.recent_simulations:
            if isinstance(s, dict):
                sims.append(s.get("expected_improvement", 0))
            else:
                sims.append(0)

        sim_volatility = MetaTrendEngine._volatility(sims)

        # ------------------------------------------------------
        # Weak-skill trend (Phase 18 deterministic ordering)
        # ------------------------------------------------------
        weaknesses = ctx.skill_weaknesses or []
        weak_skill_names = [w.get("skill") for w in weaknesses]

        if len(set(weak_skill_names)) == 1 and len(weak_skill_names) > 0:
            weak_skill_trend = "persistent_single_weakness"
        elif len(weak_skill_names) > 1:
            weak_skill_trend = "distributed_weaknesses"
        else:
            weak_skill_trend = "no_data"

        # ------------------------------------------------------
        # Priority alignment (last 20 outcomes)
        # ------------------------------------------------------
        priority = None
        if isinstance(ctx.autonomy_status, dict):
            priority = ctx.autonomy_status.get("priority_skill")

        if priority:
            occurrences = sum(
                1 for o in ctx.recent_outcomes
                if hasattr(o, "priority_alignment") and o.priority_alignment
            )
            if occurrences >= 4:
                priority_alignment = "strong_alignment"
            elif occurrences >= 1:
                priority_alignment = "moderate_alignment"
            else:
                priority_alignment = "weak_alignment"
        else:
            priority_alignment = "no_priority"

        # ------------------------------------------------------
        # Phase 18 – Reinforcement Snapshot Echo
        # ------------------------------------------------------
        reinforcement_snapshot = get_reinforcement_snapshot() or {}

        # ------------------------------------------------------
        # Phase 18 – KG Stability Echo
        # ------------------------------------------------------
        kg_summary = get_strategic_kg_summary() or {}
        kg_stability = MetaTrendEngine._extract_kg_stability(kg_summary)

        # ------------------------------------------------------
        # Phase 18 Meta-Trend Scoring (new stability-weighted model)
        # ------------------------------------------------------
        meta_trend_score = 0.0

        # reinforcement
        if reinforcement_avg is not None:
            meta_trend_score += reinforcement_avg * 2.0

        # drift (inverse)
        if drift_avg is not None:
            meta_trend_score += (1 - drift_avg) * 1.8

        # score volatility penalty
        meta_trend_score -= min(score_volatility, 3.0) * 0.3

        # simulation stability bonus
        meta_trend_score += max(0, 1.0 - sim_volatility) * 0.5

        # weak-skill penalty
        if weak_skill_trend == "persistent_single_weakness":
            meta_trend_score -= 1.0

        # priority alignment
        if priority_alignment == "strong_alignment":
            meta_trend_score += 1.0
        elif priority_alignment == "moderate_alignment":
            meta_trend_score += 0.4

        # KG echo (Phase 18)
        if kg_stability == "high":
            meta_trend_score += 0.8
        elif kg_stability == "low":
            meta_trend_score -= 1.2

        # Reinforcement snapshot volatility penalty (Phase 18)
        rsig = reinforcement_snapshot.get("recent_signals", [])
        if isinstance(rsig, list) and len(rsig) > 1:
            vol = MetaTrendEngine._volatility(rsig)
            meta_trend_score -= min(vol, 3.0) * 0.2

        # ------------------------------------------------------
        # Output meta-trend dictionary
        # ------------------------------------------------------
        return {
            "reinforcement_avg": reinforcement_avg,
            "drift_avg": drift_avg,
            "reinforcement_drift_correlation": reinforcement_drift_correlation,

            "score_avg": score_avg,
            "score_volatility": score_volatility,
            "simulation_volatility": sim_volatility,

            "weak_skill_trend": weak_skill_trend,
            "priority_alignment": priority_alignment,

            # Phase 18 additions
            "kg_stability": kg_stability,
            "reinforcement_snapshot": reinforcement_snapshot,

            "pattern_summary": ctx.pattern_flags,
            "meta_trend_score": meta_trend_score,
        }


# ------------------------------------------------------------
# Public API for tests
# ------------------------------------------------------------
def compute_meta_trends(ctx) -> Dict[str, Any]:
    return MetaTrendEngine.compute(ctx)

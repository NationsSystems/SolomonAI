# plan_scoring_engine.py — Phase 40 Authority-Safe Scoring Signals
# ---------------------------------------------------------------------------
# PURPOSE (Phase 40):
#   Emit scoring COMPONENT SIGNALS ONLY.
#   • No final_score
#   • No weighting decisions
#   • No ranking or recommendations
#
# Orchestrator is the sole authority.
# ---------------------------------------------------------------------------

import datetime
from dataclasses import dataclass, field
from typing import Dict, Any

from solomon_core.logger import get_logger
from solomon_core.planner.strategic_planner import (
    StrategicPlan,
    StrategyContext,
)

from solomon_core.planner.strategic_memory import (
    get_plan_success_rate,
    get_objective_trends,
    get_skill_target_trends,
    evaluate_plan_novelty,
)

from solomon_core.planner.plan_simulation_engine import simulate_plan

logger = get_logger("plan_scoring_engine")


# ============================================================
# Data Structure (SIGNAL-ONLY)
# ============================================================

@dataclass
class PlanScoreSignals:
    weak_skill_impact: float = 0.0
    cluster_priority: float = 0.0
    error_reduction: float = 0.0
    reinforcement_alignment: float = 0.0
    autonomy_alignment: float = 0.0
    complexity_penalty: float = 0.0

    novelty_score: float = 0.0
    recency_score: float = 0.0

    success_history_score: float = 0.0
    recurrence_penalty: float = 0.0
    skill_trend_boost: float = 0.0

    simulation_improvement_signal: float = 0.0
    simulation_risk_signal: float = 0.0

    priority_alignment_signal: float = 0.0

    timestamp: str = field(default_factory=lambda: datetime.datetime.utcnow().isoformat())

    def as_dict(self):
        return {
            "weak_skill_impact": self.weak_skill_impact,
            "cluster_priority": self.cluster_priority,
            "error_reduction": self.error_reduction,
            "reinforcement_alignment": self.reinforcement_alignment,
            "autonomy_alignment": self.autonomy_alignment,
            "complexity_penalty": self.complexity_penalty,
            "novelty_score": self.novelty_score,
            "recency_score": self.recency_score,
            "success_history_score": self.success_history_score,
            "recurrence_penalty": self.recurrence_penalty,
            "skill_trend_boost": self.skill_trend_boost,
            "simulation_improvement_signal": self.simulation_improvement_signal,
            "simulation_risk_signal": self.simulation_risk_signal,
            "priority_alignment_signal": self.priority_alignment_signal,
            "timestamp": self.timestamp,
        }


# ============================================================
# Component Signal Extractors
# ============================================================

def _weak_skill_impact(plan: StrategicPlan, context: StrategyContext) -> float:
    target = plan.objective.metadata.get("skill")
    for ws in context.weak_skills:
        if ws.get("skill") == target:
            return min(float(ws.get("weakness_score", 1)) * 2.0, 10.0)
    return 0.0


def _cluster_priority(plan: StrategicPlan, context: StrategyContext) -> float:
    cname = plan.objective.metadata.get("cluster")
    cluster = context.kg_clusters.get(cname) if cname else None
    return min(len(cluster) * 1.5, 12.0) if cluster else 0.0


def _error_reduction(plan: StrategicPlan, context: StrategyContext) -> float:
    skill = plan.objective.metadata.get("skill")
    scores = context.kg_scores.get("error_hotspots", {})
    return min(scores.get(skill, 0.0) * 1.2, 8.0) if skill else 0.0


def _reinforcement_alignment(plan: StrategicPlan, context: StrategyContext) -> float:
    skill = plan.objective.metadata.get("skill")
    reinf = context.kg_scores.get("reinforcement_signals", {})
    return abs(reinf.get(skill, 0.0)) if skill else 0.0


def _autonomy_alignment(plan: StrategicPlan) -> float:
    return 5.0 if "autonomy" in plan.objective.objective.lower() else 0.0


def _complexity_penalty(plan: StrategicPlan) -> float:
    return -min(len(plan.steps) * 0.75, 8.0)


def _recency_score() -> float:
    return 1.0


def _success_history_score(plan: StrategicPlan) -> float:
    return get_plan_success_rate(plan.objective.objective) * 5.0


def _recurrence_penalty(plan: StrategicPlan) -> float:
    history = get_objective_trends()
    return -min(history.get(plan.objective.objective, 0) * 0.7, 5.0)


def _skill_trend_boost(plan: StrategicPlan) -> float:
    skill = plan.objective.metadata.get("skill")
    hits = get_skill_target_trends().get(skill, 0) if skill else 0
    return min(hits * 0.5, 4.0)


def _novelty_score(plan: StrategicPlan) -> float:
    return evaluate_plan_novelty(plan)


def _priority_alignment(plan: StrategicPlan, context: StrategyContext) -> float:
    priority = context.strategic_priority
    if not priority:
        return 0.0

    if plan.objective.metadata.get("skill") == priority:
        return 6.0

    cluster = plan.objective.metadata.get("cluster")
    if cluster and priority in context.kg_clusters.get(cluster, []):
        return 3.0

    if priority in plan.objective.objective:
        return 2.0

    return 0.0


# ============================================================
# Signal-Only Scoring Interface
# ============================================================

def score_plan(plan: StrategicPlan, context: StrategyContext) -> PlanScoreSignals:
    signals = PlanScoreSignals()

    signals.weak_skill_impact = _weak_skill_impact(plan, context)
    signals.cluster_priority = _cluster_priority(plan, context)
    signals.error_reduction = _error_reduction(plan, context)
    signals.reinforcement_alignment = _reinforcement_alignment(plan, context)
    signals.autonomy_alignment = _autonomy_alignment(plan)
    signals.complexity_penalty = _complexity_penalty(plan)

    signals.recency_score = _recency_score()
    signals.success_history_score = _success_history_score(plan)
    signals.recurrence_penalty = _recurrence_penalty(plan)
    signals.skill_trend_boost = _skill_trend_boost(plan)
    signals.novelty_score = _novelty_score(plan)

    sim = simulate_plan(plan, context)
    signals.simulation_improvement_signal = sim.expected_total_improvement
    signals.simulation_risk_signal = sim.total_risk

    signals.priority_alignment_signal = _priority_alignment(plan, context)

    return signals


# EOF

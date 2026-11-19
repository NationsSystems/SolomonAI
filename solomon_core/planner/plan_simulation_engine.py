# plan_simulation_engine.py — Phase 40 Authority-Safe Plan Simulation Signals
# ---------------------------------------------------------------------------
# PURPOSE (Phase 40):
#   Simulate and score plan effects ONLY.
#   No recommendations, no decisions, no semantic outcome collapse.
#
#   Orchestrator is the sole decision-maker.
# ---------------------------------------------------------------------------

import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any

from solomon_core.logger import get_logger
from solomon_core.planner.strategic_planner import (
    StrategicPlan,
    StrategyContext,
)

logger = get_logger("plan_simulation_engine")

# =====================================================================
# Utility
# =====================================================================

def _now():
    return datetime.datetime.utcnow().isoformat()


# =====================================================================
# Data Structures (SIGNAL-ONLY)
# =====================================================================

@dataclass
class StepSimulationResult:
    step: str
    improvement: float
    risk: float
    dependencies: List[str]
    rationale_code: str

    drift_adjustment: float = 0.0
    error_trend_adjustment: float = 0.0
    kg_importance_adjustment: float = 0.0


@dataclass
class PlanSimulationSummary:
    steps: List[StepSimulationResult] = field(default_factory=list)
    expected_total_improvement: float = 0.0
    total_risk: float = 0.0

    priority_improvement: float = 0.0
    priority_risk: float = 0.0
    priority_alignment: float = 0.0

    error_trend_factor: float = 1.0
    drift_factor: float = 1.0
    kg_importance_factor: float = 1.0

    timestamp: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "steps": [
                {
                    "step": s.step,
                    "improvement": s.improvement,
                    "risk": s.risk,
                    "dependencies": s.dependencies,
                    "rationale_code": s.rationale_code,
                    "drift_adjustment": s.drift_adjustment,
                    "error_trend_adjustment": s.error_trend_adjustment,
                    "kg_importance_adjustment": s.kg_importance_adjustment,
                }
                for s in self.steps
            ],
            "expected_total_improvement": self.expected_total_improvement,
            "total_risk": self.total_risk,
            "priority_improvement": self.priority_improvement,
            "priority_risk": self.priority_risk,
            "priority_alignment": self.priority_alignment,
            "error_trend_factor": self.error_trend_factor,
            "drift_factor": self.drift_factor,
            "kg_importance_factor": self.kg_importance_factor,
            "timestamp": self.timestamp,
        }


# =====================================================================
# Step Classification
# =====================================================================

def classify_step(step: str) -> str:
    s = step.lower()
    if "analyze" in s and "kg" in s:
        return "KG_ANALYSIS"
    if "error" in s:
        return "ERROR_ANALYSIS"
    if "patch" in s:
        return "PATCH_SIM"
    if "promotion" in s:
        return "PROMOTION_SIM"
    if "cluster" in s:
        return "CLUSTER_SCAN"
    if "autonomy" in s:
        return "AUTONOMY_REVIEW"
    return "GENERIC_STEP"


# =====================================================================
# Base Step Simulation (SIGNAL-ONLY)
# =====================================================================

def simulate_step(step: str, context: StrategyContext) -> StepSimulationResult:
    stype = classify_step(step)

    improvement = 1.0
    risk = 0.1
    deps: List[str] = []
    rationale_code = "GENERIC_LOW_IMPACT"

    if stype == "KG_ANALYSIS":
        improvement, risk = 3.0, 0.2
        deps = ["knowledge_graph"]
        rationale_code = "KG_STRUCTURE_INSIGHT"

    elif stype == "ERROR_ANALYSIS":
        improvement, risk = 4.0, 0.3
        deps = ["knowledge_graph"]
        rationale_code = "ERROR_CLUSTER_STABILIZATION"

    elif stype == "PATCH_SIM":
        improvement, risk = 6.0, 0.5
        deps = ["patch_engine", "skill_registry"]
        rationale_code = "PATCH_IMPACT_SIMULATION"

    elif stype == "PROMOTION_SIM":
        improvement, risk = 2.5, 0.15
        deps = ["skill_lifecycle"]
        rationale_code = "PROMOTION_STABILITY_GAIN"

    elif stype == "CLUSTER_SCAN":
        improvement, risk = 2.0, 0.1
        deps = ["knowledge_graph"]
        rationale_code = "CLUSTER_STRUCTURE_SCAN"

    elif stype == "AUTONOMY_REVIEW":
        improvement, risk = 2.0, 0.05
        deps = ["autonomy_controller"]
        rationale_code = "AUTONOMY_CONFIGURATION_REVIEW"

    return StepSimulationResult(
        step=step,
        improvement=improvement,
        risk=risk,
        dependencies=deps,
        rationale_code=rationale_code,
    )


# =====================================================================
# Priority Adjustments (SIGNAL-ONLY)
# =====================================================================

def _compute_priority_adjustments(plan: StrategicPlan, context: StrategyContext):
    priority = context.strategic_priority
    if not priority:
        return 0.0, 0.0, 0.0

    skill = plan.objective.metadata.get("skill")
    if skill == priority:
        return 5.0, 0.5, 1.0

    cluster = plan.objective.metadata.get("cluster")
    if cluster:
        members = context.kg_clusters.get(cluster, [])
        if priority in members:
            return 3.0, 0.3, 0.7

    return 0.0, 0.0, 0.0


# =====================================================================
# A2 / B2 / C2 Modulation (SIGNAL-ONLY)
# =====================================================================

def _compute_error_trend_factor(error_trends: dict) -> float:
    if not error_trends or not error_trends.get("summary"):
        return 1.0
    recent = error_trends["summary"].get("recent_errors", 0)
    if recent > 15:
        return 0.85
    if recent > 5:
        return 0.92
    return 1.05


def _compute_drift_factor(drift: dict) -> float:
    if not drift:
        return 1.0
    score = drift.get("drift_score", 0)
    if score > 0.7:
        return 0.88
    if score > 0.4:
        return 0.95
    return 1.05


def _compute_kg_importance_factor(plan: StrategicPlan, context: StrategyContext) -> float:
    imp = context.kg_scores.get("skill_importance", {})
    skill = plan.objective.metadata.get("skill")
    if skill and skill in imp:
        score = imp[skill]
        if score > 25:
            return 1.12
        if score > 10:
            return 1.06
    return 1.0


# =====================================================================
# Full Plan Simulation (NO DECISIONS)
# =====================================================================

def simulate_plan(plan: StrategicPlan, context: StrategyContext) -> PlanSimulationSummary:
    summary = PlanSimulationSummary()

    for step in plan.steps:
        summary.steps.append(simulate_step(step, context))

    base_improvement = sum(s.improvement for s in summary.steps)
    base_risk = sum(s.risk for s in summary.steps)

    summary.error_trend_factor = _compute_error_trend_factor(context.error_trends)
    summary.drift_factor = _compute_drift_factor(context.recent_drift)
    summary.kg_importance_factor = _compute_kg_importance_factor(plan, context)

    adjusted_improvement = base_improvement
    adjusted_risk = base_risk

    adjusted_improvement *= summary.kg_importance_factor * summary.error_trend_factor
    adjusted_risk *= (2 - summary.error_trend_factor)

    adjusted_improvement *= summary.drift_factor
    adjusted_risk *= (2 - summary.drift_factor)

    pr_imp, pr_risk, pr_align = _compute_priority_adjustments(plan, context)
    summary.priority_improvement = pr_imp
    summary.priority_risk = pr_risk
    summary.priority_alignment = pr_align

    adjusted_improvement += pr_imp
    adjusted_risk += pr_risk

    summary.expected_total_improvement = adjusted_improvement
    summary.total_risk = adjusted_risk

    return summary


# EOF

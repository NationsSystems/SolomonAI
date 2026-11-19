# strategic_planner.py — Phase 13.1 + Phase 16 Step 15 + Phase 16 Step 18A (Drift-Aware)
# Clean, Circular-Safe, Stable

import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from solomon_core.logger import get_logger

# Phase 12 data sources
from solomon_core.knowledge.knowledge_graph import (
    get_kg_insights,
    get_kg_scores,
    get_kg_clusters,
)
from solomon_core.knowledge.skill_weakness_engine import (
    get_global_skill_weaknesses,
)

logger = get_logger("strategic_planner")


def _now():
    return datetime.datetime.utcnow().isoformat()


# ============================================================
# Data Classes
# ============================================================

@dataclass
class PlanReasoning:
    rationale: str = ""
    contributing_factors: Dict[str, Any] = field(default_factory=dict)
    score_components: Dict[str, float] = field(default_factory=dict)

    def as_dict(self):
        return {
            "rationale": self.rationale,
            "contributing_factors": self.contributing_factors,
            "score_components": self.score_components,
        }


@dataclass
class StrategicObjective:
    objective: str
    priority: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "objective": self.objective,
            "priority": self.priority,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class StrategicPlan:
    objective: StrategicObjective
    steps: List[str]
    reasoning: PlanReasoning
    created_at: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "objective": self.objective.as_dict(),
            "steps": self.steps,
            "reasoning": self.reasoning.as_dict(),
            "created_at": self.created_at,
        }


@dataclass
class CandidatePlan:
    plan: StrategicPlan
    score: float
    factors: Dict[str, float] = field(default_factory=dict)


@dataclass
class StrategyContext:
    kg_insights: Dict[str, Any]
    kg_scores: Dict[str, Any]
    kg_clusters: Dict[str, Any]
    weak_skills: List[Dict[str, Any]]
    autonomy_status: Dict[str, Any]
    strategic_priority: Optional[str] = None
    recent_drift: Dict[str, Any] = field(default_factory=dict)    # ⭐ EXISTING
    error_trends: Dict[str, Any] = field(default_factory=dict)    # ⭐ NEW Phase 19
    timestamp: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "kg_insights": self.kg_insights,
            "kg_scores": self.kg_scores,
            "kg_clusters": self.kg_clusters,
            "weak_skills": self.weak_skills,
            "autonomy_status": self.autonomy_status,
            "strategic_priority": self.strategic_priority,
            "recent_drift": self.recent_drift,
            "error_trends": self.error_trends,                    # ⭐ NEW
            "timestamp": self.timestamp,
        }


# ============================================================
# Objective generation
# ============================================================

def generate_strategic_objectives(priority_skill: Optional[str] = None,
                                  drift: Optional[Dict[str, Any]] = None
                                  ) -> List[StrategicObjective]:
    """
    Generates strategic objectives with:
        • priority-aware logic (Step 15)
        • drift-aware logic (Step 18A)
    """
    from solomon_core.cognitive_orchestrator import evaluate_autonomy_triggers

    weak_skills = get_global_skill_weaknesses()
    objectives = []

    drift_score = None
    drift_skill = None

    if drift:
        drift_score = drift.get("drift_score", 0.0)
        drift_skill = drift.get("priority_skill")

    # ---------------------------------------------------------
    # Standard weak-skill objectives (original Step 15 logic preserved)
    # ---------------------------------------------------------
    for entry in weak_skills[:5]:
        skill = entry.get("skill")
        score = entry.get("weakness_score", 1)

        base_priority = 10 - min(score, 9)

        # Step 15 priority boost
        if priority_skill and skill == priority_skill:
            base_priority += 4

        # Step 18 drift boost
        if drift_score and drift_score > 0.5:
            if drift_skill and skill == drift_skill:
                base_priority += 3  # stronger push for drift correction
            elif skill == priority_skill:
                base_priority += 1  # soft boost when aligned

        objectives.append(
            StrategicObjective(
                objective=f"Improve weak skill '{skill}'",
                priority=base_priority,
                metadata={"skill": skill, "weakness_score": score},
            )
        )

    # ---------------------------------------------------------
    # Cluster exploration (priority- and drift-aware)
    # ---------------------------------------------------------
    clusters = get_kg_clusters()
    for cname, members in clusters.items():
        if len(members) >= 4:
            base_priority = 5

            if priority_skill and priority_skill in members:
                base_priority += 3  # Step 15

            if drift_score and drift_score > 0.5 and drift_skill in members:
                base_priority += 2  # Step 18

            objectives.append(
                StrategicObjective(
                    objective=f"Investigate knowledge cluster '{cname}'",
                    priority=base_priority,
                    metadata={"cluster": cname, "members": members},
                )
            )

    # ---------------------------------------------------------
    # Drift-specific objective (Step 18A)
    # ---------------------------------------------------------
    if drift_score and drift_score > 0.5:
        if drift_skill:
            objectives.append(
                StrategicObjective(
                    objective=f"Correct drift deviation for '{drift_skill}'",
                    priority=12,
                    metadata={"drift_score": drift_score, "skill": drift_skill},
                )
            )
        else:
            objectives.append(
                StrategicObjective(
                    objective="Reduce overall drift deviation",
                    priority=10,
                    metadata={"drift_score": drift_score},
                )
            )

    # ---------------------------------------------------------
    # Autonomy stability objective (unchanged)
    # ---------------------------------------------------------
    gating = evaluate_autonomy_triggers()
    if not gating.get("allowed", True):
        objectives.append(
            StrategicObjective(
                objective="Improve autonomy gating stability",
                priority=8,
                metadata=gating,
            )
        )

    return objectives


# ============================================================
# Plan generation (Step 15 logic unchanged)
# ============================================================

def formulate_candidate_plans(objectives: List[StrategicObjective],
                              priority_skill: Optional[str] = None) -> List[StrategicPlan]:

    plans = []
    for obj in objectives:
        steps = []

        if "Improve weak skill" in obj.objective:
            skill = obj.metadata["skill"]
            steps = [
                f"Analyze KG usage patterns for '{skill}'",
                f"Examine error clusters for '{skill}'",
                f"Simulate patch cycle for '{skill}'",
                f"Evaluate promotion path for '{skill}'",
            ]

            if priority_skill and skill == priority_skill:
                steps.append(f"Deep strategic analysis for priority skill '{skill}'")
                steps.append(f"Cross-reference all KG clusters for '{skill}'")

        elif "Investigate knowledge cluster" in obj.objective:
            cname = obj.metadata["cluster"]
            steps = [
                f"Analyze cluster '{cname}'",
                f"Identify dominant skills in '{cname}'",
                f"Cross-reference with weak skills",
                f"Propose KG structural improvements",
            ]

            if priority_skill and priority_skill in obj.metadata.get("members", []):
                steps.append(f"Deep analysis of cluster '{cname}' for priority skill")

        elif "Correct drift deviation" in obj.objective:
            skill = obj.metadata.get("skill")
            steps = [
                f"Quantify drift for '{skill}'",
                f"Identify sources of drift for '{skill}'",
                f"Simulate corrective interventions for '{skill}'",
                f"Reinforce stable patterns for '{skill}'",
            ]

        elif "overall drift" in obj.objective.lower():
            steps = [
                "Analyze global drift signals",
                "Identify global drift contributors",
                "Simulate system-wide corrections",
            ]

        elif "autonomy" in obj.objective.lower():
            steps = [
                "Review autonomy logs",
                "Analyze failures",
                "Simulate autonomy thresholds",
            ]

        else:
            steps = ["Analyze objective context", "Generate plan steps"]

        reasoning = PlanReasoning(
            rationale=f"Plan derived from: {obj.objective}",
            contributing_factors=obj.metadata,
        )

        plans.append(
            StrategicPlan(
                objective=obj,
                steps=steps,
                reasoning=reasoning,
            )
        )
    return plans


# ============================================================
# Ranking (unchanged from Step 15)
# ============================================================

def rank_candidate_plans(plans: List[StrategicPlan],
                         priority_skill: Optional[str] = None) -> List[CandidatePlan]:

    ranked = []
    for plan in plans:
        p_score = plan.objective.priority
        c_score = len(plan.steps)

        bonus = 0
        if priority_skill and "Improve weak skill" in plan.objective.objective:
            skill = plan.objective.metadata.get("skill")
            if skill == priority_skill:
                bonus += 4

        final_score = p_score * 1.5 + c_score * 0.5 + bonus

        ranked.append(
            CandidatePlan(plan=plan, score=final_score,
                          factors={"priority": p_score, "complexity": c_score, "bonus": bonus})
        )

    ranked.sort(key=lambda c: c.score, reverse=True)
    return ranked


def select_best_plan(ranked: List[CandidatePlan]) -> Optional[StrategicPlan]:
    return ranked[0].plan if ranked else None


# ============================================================
# Build Context (Step 18A updated, untouched here)
# ============================================================

def build_strategy_context() -> StrategyContext:
    """
    Extended to include drift signals (default empty until runtime is integrated).
    """
    from solomon_core.cognitive_orchestrator import evaluate_autonomy_triggers

    return StrategyContext(
        kg_insights=get_kg_insights(),
        kg_scores=get_kg_scores(),
        kg_clusters=get_kg_clusters(),
        weak_skills=get_global_skill_weaknesses(),
        autonomy_status=evaluate_autonomy_triggers(),
        recent_drift={},                     # ✔ EXISTING
    )


# ============================================================
# High-level API (unchanged)
# ============================================================

def generate_strategic_plan() -> Dict[str, Any]:
    ctx = build_strategy_context()

    objs = generate_strategic_objectives(
        priority_skill=ctx.strategic_priority,
        drift=ctx.recent_drift,        # ✔
    )

    if not objs:
        objs = [
            StrategicObjective(
                objective="System Diagnostic Objective",
                priority=5,
                metadata={"reason": "fallback_for_test"},
            )
        ]

    candidates = formulate_candidate_plans(objs, priority_skill=ctx.strategic_priority)
    ranked = rank_candidate_plans(candidates, priority_skill=ctx.strategic_priority)
    best = select_best_plan(ranked)

    return {
        "context": ctx,
        "objectives": [o.objective for o in objs],
        "ranked": [{"plan": c.plan.objective.objective, "score": c.score} for c in ranked],
        "best_plan": best,
        "timestamp": _now(),
    }


# ============================================================
# StrategicPlanner Wrapper (unchanged)
# ============================================================

class StrategicPlanner:

    def __init__(self):
        self.last_plan = None
        self.last_context = None

    def generate_candidate_plans(self, ctx: StrategyContext):
        objs = generate_strategic_objectives(
            priority_skill=ctx.strategic_priority,
            drift=ctx.recent_drift,            # ✔
        )

        if not objs:
            objs = [
                StrategicObjective(
                    objective="Synthetic Test Objective",
                    priority=5,
                    metadata={"source": "test_fallback"},
                )
            ]

        return formulate_candidate_plans(
            objs,
            priority_skill=ctx.strategic_priority
        )

    def score_plan(self, plan, ctx):
        from solomon_core.planner.plan_scoring_engine import score_plan
        return score_plan(plan, ctx)

    def simulate_plan(self, plan, ctx):
        from solomon_core.planner.plan_simulation_engine import simulate_plan
        return simulate_plan(plan, ctx)

    def run(self):
        result = generate_strategic_plan()
        self.last_plan = result["best_plan"]
        self.last_context = result["context"]
        return result


# EOF

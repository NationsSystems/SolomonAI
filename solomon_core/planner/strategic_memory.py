# strategic_memory.py — Phase 13.4 + Phase 13.9 + Phase 14 Step 14 + Phase 16 Step 20
# -----------------------------------------------------------------------------------
# Strategic Long-Term Planning Memory
#
# Phase 16 Step 20 Enhancements:
#   • priority_skill tracking for long-term analytics
#   • drift stability band tagging
#   • reinforcement confidence trend indexing
#   • priority-aligned outcome snapshots
#   • unified context archival for strategic diagnostics
#
# Still:
#   • In-memory only (no persistence yet)
#   • Read-only retrieval
#   • No modifications to core planning/scoring/simulation behavior
# -----------------------------------------------------------------------------------

import datetime
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from solomon_core.logger import get_logger

logger = get_logger("strategic_memory")


# ============================================================
# Utility
# ============================================================

def _now():
    return datetime.datetime.utcnow().isoformat()


# ============================================================
# Data Structures
# ============================================================

@dataclass
class StrategicMemoryRecord:
    plan_objective: str
    steps: List[str]
    simulation_improvement: float
    simulation_risk: float
    was_selected: bool
    recommended: bool
    context_snapshot: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)


@dataclass
class StrategicRunLog:
    best_objective: str
    best_score: float
    simulation_risk: float
    trigger_source: Optional[str] = None
    cpu_load: Optional[float] = None
    total_plans: int = 0
    timestamp: str = field(default_factory=_now)


@dataclass
class PlanScoreSnapshot:
    objective: str
    final_score: float
    factors: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)


@dataclass
class SimulationSnapshot:
    objective: str
    expected_improvement: float
    total_risk: float
    steps_considered: int
    timestamp: str = field(default_factory=_now)


# ============================================================
# Phase 14 Step 14 — Passive Outcome Archival
# Phase 16 Step 20 — Add priority, drift bands, confidence
# ============================================================

@dataclass
class StrategicOutcomeSnapshot:
    objective: str
    score: float
    simulation_risk: float
    drift: Optional[Dict[str, Any]] = field(default_factory=dict)
    feedback: Optional[Dict[str, Any]] = field(default_factory=dict)
    reinforcement: Optional[Dict[str, Any]] = field(default_factory=dict)

    # NEW Phase 16 fields:
    priority_skill: Optional[str] = None
    priority_alignment: Optional[bool] = None
    drift_band: Optional[str] = None
    confidence: Optional[float] = None
    weak_skill_pressure: Optional[float] = None
    autonomy_status: Optional[Dict[str, Any]] = None

    timestamp: str = field(default_factory=_now)

    # -------------------------------------------------------
    # JSON-safe export method (Phase 16 requirement)
    # -------------------------------------------------------
    def as_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "score": self.score,
            "simulation_risk": self.simulation_risk,
            "drift": self.drift or {},
            "feedback": self.feedback or {},
            "reinforcement": self.reinforcement or {},

            # Phase 16 fields
            "priority_skill": self.priority_skill,
            "priority_alignment": self.priority_alignment,
            "drift_band": self.drift_band,
            "confidence": self.confidence,
            "weak_skill_pressure": self.weak_skill_pressure,
            "autonomy_status": self.autonomy_status,

            "timestamp": self.timestamp,
        }


# ============================================================
# In-Memory Storage
# ============================================================

STRATEGIC_MEMORY = {
    "history": [],                     # StrategicMemoryRecord
    "success": {},                     # objective → int
    "failure": {},                     # objective → int
    "objectives": {},                  # objective → count
    "skills": {},                      # skill → count

    # Telemetry (13.9)
    "strategic_run_log": [],
    "score_snapshots": [],
    "simulation_snapshots": [],

    # Test harness raw outcomes (13.9)
    "outcomes": [],

    # Passive outcome snapshots (14 + 16)
    "outcome_snapshots": [],
}


# ============================================================
# Recording Functions (Phase 13.4)
# ============================================================

def record_plan_simulation(plan, simulation, context_snapshot=None):
    record = StrategicMemoryRecord(
        plan_objective=plan.objective.objective,
        steps=plan.steps,
        simulation_improvement=simulation.expected_total_improvement,
        simulation_risk=simulation.total_risk,
        was_selected=False,
        recommended=simulation.recommended,
        context_snapshot=context_snapshot or {},
    )

    STRATEGIC_MEMORY["history"].append(record)

    # Objective-recency count
    STRATEGIC_MEMORY["objectives"][record.plan_objective] = \
        STRATEGIC_MEMORY["objectives"].get(record.plan_objective, 0) + 1

    # Weak-skill targeting count
    skill = plan.objective.metadata.get("skill")
    if skill:
        STRATEGIC_MEMORY["skills"][skill] = \
            STRATEGIC_MEMORY["skills"].get(skill, 0) + 1

    logger.debug(
        f"[StrategicMemory] Recorded simulation for {record.plan_objective} "
        f"(improvement={record.simulation_improvement}, risk={record.simulation_risk})"
    )


def record_plan_selection(plan):
    obj = plan.objective.objective

    # Mark most recent instance
    for rec in reversed(STRATEGIC_MEMORY["history"]):
        if rec.plan_objective == obj:
            rec.was_selected = True
            break

    STRATEGIC_MEMORY["success"][obj] = \
        STRATEGIC_MEMORY["success"].get(obj, 0) + 1

    logger.debug(f"[StrategicMemory] Selected plan: {obj}")


def record_plan_failure(plan):
    obj = plan.objective.objective
    STRATEGIC_MEMORY["failure"][obj] = \
        STRATEGIC_MEMORY["failure"].get(obj, 0) + 1

    logger.debug(f"[StrategicMemory] Recorded failure: {obj}")


# ============================================================
# Phase 13.9 — record_plan_outcome + Phase 16 Step 20
# ============================================================

def record_plan_outcome(objective: str, metadata: Dict[str, Any]):
    """
    Stores the test harness outcome and Phase 16 enhanced snapshot.
    """
    entry = {
        "objective": objective,
        "metadata": metadata,
        "timestamp": _now(),
    }

    STRATEGIC_MEMORY["outcomes"].append(entry)

    sim = metadata.get("simulation", {})
    drift = metadata.get("drift", {})
    feedback = metadata.get("feedback", {})
    reinforcement = metadata.get("reinforcement", {})

    # Phase 16 derived fields
    priority_skill = metadata.get("context", {}).get("strategic_priority")
    confidence = reinforcement.get("confidence")
    weak_skill_pressure = reinforcement.get("weakness_pressure")

    # Drift band
    drift_score = drift.get("drift_score", 0)
    if drift_score <= 0.1:
        drift_band = "stable"
    elif drift_score <= 0.3:
        drift_band = "low"
    elif drift_score <= 0.6:
        drift_band = "moderate"
    else:
        drift_band = "high"

    snap = StrategicOutcomeSnapshot(
        objective=objective,
        score=metadata.get("score", 0.0),
        simulation_risk=sim.get("total_risk", 0.0),
        drift=drift,
        feedback=feedback,
        reinforcement=reinforcement,

        # NEW
        priority_skill=priority_skill,
        priority_alignment=metadata.get("context", {}).get("priority_alignment"),
        drift_band=drift_band,
        confidence=confidence,
        weak_skill_pressure=weak_skill_pressure,
        autonomy_status=metadata.get("context", {}).get("autonomy_status"),
    )

    STRATEGIC_MEMORY["outcome_snapshots"].append(snap)

    logger.debug(
        f"[StrategicMemory] Snapshot saved: {objective} | "
        f"score={snap.score}, risk={snap.simulation_risk}, drift_band={snap.drift_band}"
    )


# ============================================================
# Telemetry Functions
# ============================================================

def record_strategic_cycle(best_plan, best_score, simulation, trigger=None, cpu=None, total=0):
    rec = StrategicRunLog(
        best_objective=best_plan.objective.objective,
        best_score=best_score.final_score,
        simulation_risk=simulation.total_risk,
        trigger_source=trigger,
        cpu_load=cpu,
        total_plans=total,
    )
    STRATEGIC_MEMORY["strategic_run_log"].append(rec)

    logger.debug(
        f"[StrategicMemory] Cycle logged: {rec.best_objective} "
        f"(score={rec.best_score}, risk={rec.simulation_risk})"
    )


def record_score_snapshot(plan, score):
    snap = PlanScoreSnapshot(
        objective=plan.objective.objective,
        final_score=score.final_score,
        factors=score.to_dict(),
    )
    STRATEGIC_MEMORY["score_snapshots"].append(snap)


def record_simulation_snapshot(plan, sim):
    snap = SimulationSnapshot(
        objective=plan.objective.objective,
        expected_improvement=sim.expected_total_improvement,
        total_risk=sim.total_risk,
        steps_considered=len(plan.steps),
    )
    STRATEGIC_MEMORY["simulation_snapshots"].append(snap)


# ============================================================
# Retrieval Functions
# ============================================================

def get_recent_plan_history(limit: int = 20) -> List[StrategicMemoryRecord]:
    return STRATEGIC_MEMORY["history"][-limit:]


def get_plan_success_rate(plan_objective: str) -> float:
    s = STRATEGIC_MEMORY["success"].get(plan_objective, 0)
    f = STRATEGIC_MEMORY["failure"].get(plan_objective, 0)

    if s == 0 and f == 0:
        return 1.0

    total = s + f
    return s / total if total > 0 else 1.0


def get_objective_trends():
    return STRATEGIC_MEMORY["objectives"]


def get_skill_target_trends():
    return STRATEGIC_MEMORY["skills"]


def get_outcome_history(limit: int = 50) -> List[StrategicOutcomeSnapshot]:
    return STRATEGIC_MEMORY["outcome_snapshots"][-limit:]


# ============================================================
# Novelty Analysis
# ============================================================

def evaluate_plan_novelty(plan) -> float:
    obj = plan.objective.objective
    recurrence = STRATEGIC_MEMORY["objectives"].get(obj, 0)

    if recurrence == 0:
        return 5.0
    if recurrence == 1:
        return 3.0
    if recurrence <= 3:
        return 2.0

    return 0.5


# ============================================================
# Telemetry Snapshot API
# ============================================================

def get_strategic_telemetry():
    return {
        "total_runs": len(STRATEGIC_MEMORY["strategic_run_log"]),
        "recent_runs": [
            {
                "objective": r.best_objective,
                "score": r.best_score,
                "risk": r.simulation_risk,
                "trigger": r.trigger_source,
                "cpu": r.cpu_load,
                "timestamp": r.timestamp,
            }
            for r in STRATEGIC_MEMORY["strategic_run_log"][-10:]
        ],
        "score_snapshots": [
            {
                "objective": s.objective,
                "final_score": s.final_score,
                "timestamp": s.timestamp,
            }
            for s in STRATEGIC_MEMORY["score_snapshots"][-10:]
        ],
        "simulation_snapshots": [
            {
                "objective": s.objective,
                "expected_improvement": s.expected_improvement,
                "risk": s.total_risk,
                "timestamp": s.timestamp,
            }
            for s in STRATEGIC_MEMORY["simulation_snapshots"][-10:]
        ],
        "timestamp": _now(),
    }


# ============================================================
# Diagnostic Snapshot
# ============================================================

def get_strategic_memory_snapshot():
    return STRATEGIC_MEMORY["outcomes"]


# EOF

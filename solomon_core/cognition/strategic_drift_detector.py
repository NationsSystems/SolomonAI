# strategic_drift_detector.py — Phase 14.5
# -----------------------------------------
# Purpose:
#   Detect discrepancies ("drift") between:
#       • expected outcomes (simulation)
#       • observed results (execution stubs)
#
#   STEP 5:
#      • Define DriftResult
#      • Implement compute_drift()
#      • Implement compare_expected_vs_actual()
#      • No side effects, no mutations
#
# -----------------------------------------

import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List

from solomon_core.logger import get_logger
from solomon_core.cognition.strategic_action_executor import ActionExecutionResult
from solomon_core.planner.plan_simulation_engine import PlanSimulationSummary
from solomon_core.planner.strategic_planner import StrategyContext

logger = get_logger("strategic_drift_detector")


# ============================================================
# Utility
# ============================================================

def _now():
    return datetime.datetime.utcnow().isoformat()


# ============================================================
# Drift Result Structure
# ============================================================

@dataclass
class DriftResult:
    drift_detected: bool
    drift_score: float
    expected_improvement: float
    actual_success_rate: float
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "drift_detected": self.drift_detected,
            "drift_score": self.drift_score,
            "expected_improvement": self.expected_improvement,
            "actual_success_rate": self.actual_success_rate,
            "details": self.details,
            "timestamp": self.timestamp,
        }


# ============================================================
# Drift Computation Logic (STEP 5)
# ============================================================

def compute_drift(
    simulation: PlanSimulationSummary,
    execution_results: List[ActionExecutionResult],
    ctx: StrategyContext
) -> DriftResult:
    """
    Compute how far execution diverged from simulation expectations.
    PHASE 14.5: execution is still stubbed, so drift is synthetic.
    """

    # Expected improvement from simulation
    expected_total = simulation.expected_total_improvement

    # Actual success ratio from action execution (stubs return success=True)
    total_actions = len(execution_results)
    successes = sum(1 for r in execution_results if r.success)
    actual_success_rate = successes / total_actions if total_actions > 0 else 1.0

    # Synthetic drift rule (Phase 14.5)
    # As execution is stubbed, drift should be 0 unless simulation is high-risk.
    risk = simulation.total_risk
    synthetic_drift = max(0.0, risk * 0.1)

    # Drift score = how much "surprise" exists vs expected improvement
    drift_score = synthetic_drift

    drift_detected = drift_score > 0.5

    details = {
        "risk_factor": risk,
        "synthetic_drift": synthetic_drift,
        "success_rate": actual_success_rate,
        "expected_total_improvement": expected_total,
    }

    return DriftResult(
        drift_detected=drift_detected,
        drift_score=drift_score,
        expected_improvement=expected_total,
        actual_success_rate=actual_success_rate,
        details=details,
    )


# ============================================================
# Comparison API (Wrapper)
# ============================================================

def compare_expected_vs_actual(
    simulation: PlanSimulationSummary,
    execution_results: List[ActionExecutionResult],
    ctx: StrategyContext
) -> DriftResult:
    """
    Public API for computing drift.
    """
    return compute_drift(simulation, execution_results, ctx)


# EOF

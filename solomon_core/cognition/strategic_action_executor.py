# strategic_action_executor.py — Phase 14.4 + 14.8 + 14.10 + Phase 16 Step 18 + Phase 40
# --------------------------------------------------------------------------
# PURPOSE (Phase 40):
#   Emit EXECUTION RESULT STRUCTURES + REINFORCEMENT SIGNALS only.
#   • NO side effects
#   • NO task execution authority
#   • NO recommendations / rankings / decisions
#
# Handlers remain NO-OP stubs (Phase 14.4).
# Reinforcement is drift-aware but SIGNAL-ONLY.
# --------------------------------------------------------------------------

import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable

from solomon_core.logger import get_logger

# NOTE: Corrected import path to match planner location for StrategicAction
from solomon_core.planner.strategic_action_engine import StrategicAction
from solomon_core.planner.strategic_planner import StrategyContext

logger = get_logger("strategic_action_executor")


# ============================================================
# Utility
# ============================================================

def _now():
    return datetime.datetime.utcnow().isoformat()


def _safe_float(x, default: float = 0.0) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _drift_fields(drift: Any) -> Dict[str, Any]:
    """
    Accepts drift as:
      • None
      • dict with keys drift_score / drift_detected
      • object with attrs drift_score / drift_detected
    Returns normalized fields.
    """
    if drift is None:
        return {"drift_score": 0.0, "drift_detected": False}

    if isinstance(drift, dict):
        return {
            "drift_score": _safe_float(drift.get("drift_score", 0.0), 0.0),
            "drift_detected": bool(drift.get("drift_detected", False)),
        }

    # object fallback
    return {
        "drift_score": _safe_float(getattr(drift, "drift_score", 0.0), 0.0),
        "drift_detected": bool(getattr(drift, "drift_detected", False)),
    }


# ============================================================
# Execution Result Structure
# ============================================================

@dataclass
class ActionExecutionResult:
    success: bool
    action_type: str
    target: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "success": self.success,
            "action_type": self.action_type,
            "target": self.target,
            "details": self.details,
            "timestamp": self.timestamp,
        }


# ============================================================
# Handler Stubs (NO-OP IMPLEMENTATIONS)
# ============================================================

def _handle_kg_analysis(action: StrategicAction, ctx: StrategyContext) -> ActionExecutionResult:
    return ActionExecutionResult(
        success=True,
        action_type=action.action_type,
        target=action.target,
        details={"stub": True, "handler": "kg_analysis"},
    )


def _handle_error_analysis(action: StrategicAction, ctx: StrategyContext) -> ActionExecutionResult:
    return ActionExecutionResult(
        success=True,
        action_type=action.action_type,
        target=action.target,
        details={"stub": True, "handler": "error_analysis"},
    )


def _handle_patch_simulation(action: StrategicAction, ctx: StrategyContext) -> ActionExecutionResult:
    return ActionExecutionResult(
        success=True,
        action_type=action.action_type,
        target=action.target,
        details={"stub": True, "handler": "patch_simulation"},
    )


def _handle_promotion_simulation(action: StrategicAction, ctx: StrategyContext) -> ActionExecutionResult:
    return ActionExecutionResult(
        success=True,
        action_type=action.action_type,
        target=action.target,
        details={"stub": True, "handler": "promotion_simulation"},
    )


def _handle_cluster_analysis(action: StrategicAction, ctx: StrategyContext) -> ActionExecutionResult:
    return ActionExecutionResult(
        success=True,
        action_type=action.action_type,
        target=action.target,
        details={"stub": True, "handler": "cluster_analysis"},
    )


def _handle_autonomy_review(action: StrategicAction, ctx: StrategyContext) -> ActionExecutionResult:
    return ActionExecutionResult(
        success=True,
        action_type=action.action_type,
        target=action.target,
        details={"stub": True, "handler": "autonomy_review"},
    )


def _handle_generic_step(action: StrategicAction, ctx: StrategyContext) -> ActionExecutionResult:
    return ActionExecutionResult(
        success=True,
        action_type=action.action_type,
        target=action.target,
        details={"stub": True, "handler": "generic_step"},
    )


# ============================================================
# Execution Router (NO-OP)
# ============================================================

_HANDLER_MAP: Dict[str, Callable[[StrategicAction, StrategyContext], ActionExecutionResult]] = {
    "kg_analysis": _handle_kg_analysis,
    "error_analysis": _handle_error_analysis,
    "patch_simulation": _handle_patch_simulation,
    "promotion_simulation": _handle_promotion_simulation,
    "cluster_analysis": _handle_cluster_analysis,
    "autonomy_review": _handle_autonomy_review,
    "generic_step": _handle_generic_step,
}


def execute_action(action: StrategicAction, ctx: StrategyContext) -> ActionExecutionResult:
    """
    Unified execution entrypoint for a single StrategicAction.
    Phase 40: NO side effects; returns stub result structures only.
    """
    handler = _HANDLER_MAP.get(action.action_type, _handle_generic_step)

    logger.info(f"[StrategicExec] action_type={action.action_type} target={action.target}")

    result = handler(action, ctx)

    logger.info(f"[StrategicExec] completed action_type={action.action_type} success={result.success}")

    return result


def execute_action_chain(actions: List[StrategicAction], ctx: StrategyContext) -> List[ActionExecutionResult]:
    """
    Execute each action via NO-OP handlers. Phase 40: signal-only.
    """
    results: List[ActionExecutionResult] = []
    for action in (actions or []):
        results.append(execute_action(action, ctx))
    return results


# ============================================================
# Phase 14 Step 8 — Feedback Summarization Layer (SIGNAL-ONLY)
# ============================================================

@dataclass
class ExecutionFeedback:
    total_actions: int
    successes: int
    failures: int
    action_summary: Dict[str, int]
    notes: List[str]
    timestamp: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "total_actions": self.total_actions,
            "successes": self.successes,
            "failures": self.failures,
            "action_summary": self.action_summary,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }


def prepare_execution_feedback(results: List[ActionExecutionResult], ctx: StrategyContext) -> ExecutionFeedback:
    results = results or []
    total = len(results)
    successes = sum(1 for r in results if getattr(r, "success", False))
    failures = total - successes

    summary: Dict[str, int] = {}
    for r in results:
        atype = getattr(r, "action_type", "unknown")
        summary[atype] = summary.get(atype, 0) + 1

    notes: List[str] = []
    notes.append("feedback_generated=true")
    notes.append(f"total={total}")
    notes.append(f"successes={successes}")
    notes.append(f"failures={failures}")
    notes.append(f"kg_context_present={bool(getattr(ctx, 'kg_insights', None))}")

    return ExecutionFeedback(
        total_actions=total,
        successes=successes,
        failures=failures,
        action_summary=summary,
        notes=notes,
    )


# ============================================================
# Strategic Reinforcement Signal (Drift-Aware, SIGNAL-ONLY)
# ============================================================

@dataclass
class StrategicReinforcementSignal:
    momentum_signal: float
    weakness_pressure_signal: float
    drift_risk_signal: float
    confidence_signal: float
    drift_adjusted_confidence_signal: float
    drift_score_signal: float
    drift_detected_signal: bool
    notes: List[str]
    timestamp: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "momentum_signal": self.momentum_signal,
            "weakness_pressure_signal": self.weakness_pressure_signal,
            "drift_risk_signal": self.drift_risk_signal,
            "confidence_signal": self.confidence_signal,
            "drift_adjusted_confidence_signal": self.drift_adjusted_confidence_signal,
            "drift_score_signal": self.drift_score_signal,
            "drift_detected_signal": self.drift_detected_signal,
            "notes": self.notes,
            "timestamp": self.timestamp,
        }


def compute_reinforcement_signal(
    feedback: ExecutionFeedback,
    ctx: StrategyContext,
    drift: Optional[Any] = None,
) -> StrategicReinforcementSignal:
    """
    Phase 40: Produces numeric signals only. No decisions or recommendations.
    Drift input is optional and accepted as dict or object.
    """
    notes: List[str] = []

    total = int(getattr(feedback, "total_actions", 0) or 0)
    successes = int(getattr(feedback, "successes", 0) or 0)

    # Momentum signal = success ratio
    momentum = (successes / total) if total > 0 else 0.0
    notes.append("momentum_signal=success_ratio")

    # Weakness pressure signal = count of weak skills
    weak_skills = getattr(ctx, "weak_skills", None) or []
    weakness_pressure = float(len(weak_skills)) if isinstance(weak_skills, list) else 0.0
    notes.append("weakness_pressure_signal=weak_skill_count")

    # Drift fields normalized
    df = _drift_fields(drift)
    drift_score = _safe_float(df.get("drift_score", 0.0), 0.0)
    drift_detected = bool(df.get("drift_detected", False))
    notes.append("drift_fields_normalized=true")

    # Confidence signal (deterministic transform)
    # Base confidence signal derived from momentum minus small pressure factor.
    confidence = max(0.1, momentum - (weakness_pressure * 0.02))
    notes.append("confidence_signal=deterministic_transform")

    # Drift-adjusted confidence signal
    drift_adjustment = max(0.0, drift_score * 0.25)
    drift_adjusted_confidence = max(0.05, confidence - drift_adjustment)
    notes.append("drift_adjusted_confidence_signal=confidence_minus_drift_adjustment")

    # Drift risk signal (inverse of momentum)
    drift_risk = 1.0 - momentum
    notes.append("drift_risk_signal=1_minus_momentum")

    return StrategicReinforcementSignal(
        momentum_signal=float(momentum),
        weakness_pressure_signal=float(weakness_pressure),
        drift_risk_signal=float(drift_risk),
        confidence_signal=float(confidence),
        drift_adjusted_confidence_signal=float(drift_adjusted_confidence),
        drift_score_signal=float(drift_score),
        drift_detected_signal=bool(drift_detected),
        notes=notes,
    )


__all__ = [
    "ActionExecutionResult",
    "ExecutionFeedback",
    "StrategicReinforcementSignal",
    "execute_action",
    "execute_action_chain",
    "prepare_execution_feedback",
    "compute_reinforcement_signal",
]
# EOF

# strategic_summary_normalizer.py — Phase 40G Authority-Safe Normalizer
# ------------------------------------------------------------
# PURPOSE:
#   Normalize all strategic subsystems into a single structured,
#   stable, machine-friendly summary suitable for:
#       • meta-memory integration
#       • meta-cognition
#       • diagnostics
#       • dashboards
#
# Phase 40G Guarantees:
#   • READ-ONLY
#   • SIGNALS ONLY (no interpretation, no recommendations)
#   • Deterministic normalization
#   • No authority over planning or execution
#
# Notes:
#   • Accepts *raw strategic summary dict* from strategic_cognition_controller
#   • Does NOT update memory, scoring, KG, or trigger actions
# ------------------------------------------------------------

import datetime
from typing import Dict, Any


def _now():
    return datetime.datetime.utcnow().isoformat()


# ------------------------------------------------------------
# Internal helpers
# ------------------------------------------------------------

def _safe_extract(obj: Dict[str, Any], key: str, default=None):
    """Safe dictionary extraction to avoid KeyErrors."""
    if not isinstance(obj, dict):
        return default
    return obj.get(key, default)


def _normalize_simulation(sim: Dict[str, Any]) -> Dict[str, Any]:
    if not sim:
        return {"available": False}

    expected_improvement = _safe_extract(sim, "expected_total_improvement", 0.0)
    risk = _safe_extract(sim, "total_risk", 0.0)

    return {
        "available": True,
        "expected_improvement": expected_improvement,
        "risk": risk,
        # Explicit comparison signal — NOT a recommendation
        "improvement_vs_risk_delta": expected_improvement - risk,
        "steps": _safe_extract(sim, "steps", []),
    }


def _normalize_feedback(feedback: Dict[str, Any]) -> Dict[str, Any]:
    if not feedback:
        return {"available": False}

    return {
        "available": True,
        "successes": _safe_extract(feedback, "successes", 0),
        "failures": _safe_extract(feedback, "failures", 0),
        "action_summary": _safe_extract(feedback, "action_summary", {}),
        "notes": _safe_extract(feedback, "notes", []),
    }


def _normalize_drift(drift: Dict[str, Any]) -> Dict[str, Any]:
    if not drift:
        return {"available": False}

    score = _safe_extract(drift, "drift_score", 0.0)

    return {
        "available": True,
        "drift_detected": _safe_extract(drift, "drift_detected", False),
        "score": score,
        "expected_improvement": _safe_extract(drift, "expected_improvement", 0.0),
        "actual_success_rate": _safe_extract(drift, "actual_success_rate", 1.0),
        # Threshold exposure only — no labeling
        "below_low_drift_threshold": score <= 0.3,
        "details": _safe_extract(drift, "details", {}),
    }


def _normalize_reinforcement(sig: Dict[str, Any]) -> Dict[str, Any]:
    if not sig:
        return {"available": False}

    momentum = _safe_extract(sig, "momentum", 0.0)

    return {
        "available": True,
        "momentum": momentum,
        "weakness_pressure": _safe_extract(sig, "weakness_pressure", 0.0),
        "drift_risk": _safe_extract(sig, "drift_risk", 0.0),
        "confidence_signal": _safe_extract(sig, "confidence", 0.0),
        # Explicit range flags — no qualitative labels
        "momentum_above_high_threshold": momentum > 0.7,
        "momentum_below_low_threshold": momentum < 0.3,
        "notes": _safe_extract(sig, "notes", []),
    }


def _normalize_score(score: Dict[str, Any]) -> Dict[str, Any]:
    if not score:
        return {"available": False}

    return {
        "available": True,
        "final_score": _safe_extract(score, "final_score", 0.0),
        "components": score,
    }


# ------------------------------------------------------------
# PUBLIC API (Phase 40G Authority-Safe)
# ------------------------------------------------------------

def normalize_strategic_summary(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Unified normalization entry point (authority-safe).

    Accepts:
        raw — full strategic output dict from strategic_cognition_controller

    Produces:
        stable, signal-only normalized summary for:
            • meta-memory integration
            • meta-cognition
            • diagnostics
            • dashboards
    """

    if not isinstance(raw, dict):
        return {"available": False, "reason": "invalid_raw_input"}

    # Extract expected fields from `raw`
    simulation = raw.get("best_simulation", {}) or raw.get("simulation", {})
    execution_feedback = raw.get("execution_feedback", raw.get("feedback", {}))
    drift_report = raw.get("drift", {})
    reinforcement_signal = raw.get("reinforcement_signal", raw.get("reinforcement", {}))
    score_breakdown = raw.get("best_score", raw.get("score", {}))

    normalized = {
        "available": True,
        "simulation": _normalize_simulation(simulation),
        "feedback": _normalize_feedback(execution_feedback),
        "drift": _normalize_drift(drift_report),
        "reinforcement": _normalize_reinforcement(reinforcement_signal),
        "score": _normalize_score(score_breakdown),
        "timestamp": _now(),
    }

    return normalized


# EOF

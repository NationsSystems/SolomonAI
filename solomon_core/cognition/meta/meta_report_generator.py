# meta_report_generator.py — Phase 40G Authority-Safe
# ---------------------------------------------------------------------------
# META REPORT GENERATOR (SIGNAL-ONLY)
#
# Phase 40G Guarantees:
#   • READ-ONLY
#   • NO interpretation
#   • NO recommendations
#   • NO qualitative judgments
#   • SIGNALS + RAW CONTEXT ONLY
#
# PHASE 47.2 — STRUCTURAL AWARENESS CLARIFICATION:
#   • This module is a TERMINAL OBSERVABILITY FORMATTER
#   • NOT an execution surface
#   • NOT a planner input
#   • NOT a PacketHeader author
#   • NOT an ML HUD
#   • Outputs are diagnostic/meta artifacts only
#
# Purpose:
#   Convert meta-cognitive outputs into a structured,
#   machine-safe meta report suitable for:
#       • meta_summary_printer
#       • meta_cycle_aggregator
#       • dashboards
#
# Notes:
#   • Does NOT alter KG, memory, cognition, or planning
#   • Orchestrator remains sole authority
# ---------------------------------------------------------------------------

from typing import Dict, Any


# ------------------------------------------------------------
# Signal extractors (NON-INTERPRETIVE)
# ------------------------------------------------------------

def _extract_stability_signal(meta: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "stability_signal": meta.get("stability_signal"),
        "stability_signal_present": "stability_signal" in meta,
    }


def _extract_reinforcement_signals(meta: Dict[str, Any]) -> Dict[str, Any]:
    rprof = meta.get("reinforcement_profile") or {}
    avg = rprof.get("average_signal")

    return {
        "reinforcement_average": avg,
        "reinforcement_available": avg is not None,
        "reinforcement_profile": rprof,
    }


def _extract_drift_signals(meta: Dict[str, Any]) -> Dict[str, Any]:
    dprof = meta.get("drift_profile") or {}
    drift = dprof.get("overall_drift")

    return {
        "overall_drift": drift,
        "drift_available": drift is not None,
        "drift_profile": dprof,
    }


def _extract_simulation_consistency(patterns: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "simulation_consistency": patterns.get("simulation_consistency"),
        "simulation_consistency_present": "simulation_consistency" in patterns,
    }


# ------------------------------------------------------------
# MAIN REPORT GENERATOR (Phase 40G)
# ------------------------------------------------------------
def generate_meta_report(
    context: Dict[str, Any],
    snapshot: Dict[str, Any],
    trends: Dict[str, Any],
    patterns: Dict[str, Any],
    anomalies: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Produce a structured, authority-safe meta-cognition report.

    STRUCTURAL GUARANTEES (Phase 47.2):
        • Observational formatting only
        • No synthesis or interpretation
        • No control-plane influence
        • No downstream execution consumption

    Emits:
        • raw inputs
        • extracted numeric / boolean / string signals
        • no interpretation
        • no synthesis logic
        • no conclusions
    """

    meta = snapshot.get("meta", {})

    # --------------------------------------------------------
    # Signal extraction
    # --------------------------------------------------------
    stability_signals = _extract_stability_signal(meta)
    reinforcement_signals = _extract_reinforcement_signals(meta)
    drift_signals = _extract_drift_signals(meta)
    simulation_consistency_signals = _extract_simulation_consistency(patterns)

    pattern_synthesis = snapshot.get("pattern_synthesis", [])

    # --------------------------------------------------------
    # Structured meta-report (SIGNAL-ONLY)
    # --------------------------------------------------------
    return {
        "timestamp": snapshot.get("timestamp"),

        # Raw pass-through
        "meta": meta,
        "recent_activity": snapshot.get("recent_activity", {}),
        "patterns_raw": patterns,
        "trends": trends,
        "anomalies": anomalies,
        "context": context,

        # Extracted signals (non-evaluative)
        "signals": {
            "stability": stability_signals,
            "reinforcement": reinforcement_signals,
            "drift": drift_signals,
            "simulation_consistency": simulation_consistency_signals,
            "pattern_synthesis_count": len(pattern_synthesis),
            "anomalies_present": bool(anomalies),
        },

        # Status flags (mechanical only)
        "status": {
            "meta_layer_ok": True,
            "anomalies_detected": bool(anomalies),
        },
    }


# EOF

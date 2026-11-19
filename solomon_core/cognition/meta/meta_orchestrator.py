# meta_orchestrator.py — Phase 20 Stable
# ---------------------------------------------------------------------------
# META-COGNITIVE ORCHESTRATOR (Phase-20)
#
# STRUCTURAL STATUS (Phase 47.2):
#   • Observational aggregation layer ONLY
#   • NOT an execution surface
#   • NOT a PacketHeader author
#   • NOT a planner or router
#   • NOT an ML HUD
#   • Outputs are diagnostic/meta signals, not control-plane artifacts
#
# Phase-20 compliant:
#   • ALWAYS converts MetaContext → ctx.as_dict()
#   • Pure dictionary inputs to all engines
#   • No Phase-21 dict-like assumptions
#   • Phase-20 USDI tests require "error_trends" field
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger

# Phase-20 meta components
from solomon_core.cognition.meta.meta_context import MetaContext
from solomon_core.cognition.meta.meta_snapshot_engine import build_meta_snapshot
from solomon_core.cognition.meta.meta_trend_engine import compute_meta_trends
from solomon_core.cognition.meta.meta_pattern_classifier import classify_meta_patterns
from solomon_core.cognition.meta.meta_anomaly_detector import detect_meta_anomalies
from solomon_core.cognition.meta.meta_report_generator import generate_meta_report
from solomon_core.cognition.meta.meta_summary_printer import render_meta_summary

# Phase-20 aggregation + memory integration
from solomon_core.cognition.meta.meta_cycle_aggregator import aggregate_meta_cycle
from solomon_core.cognition.meta.meta_memory_integrator import integrate_meta_memory

# Phase-20 USDI: error trend fusion
from solomon_core.cognition.error_trend_analyzer import get_error_trend_summary

logger = get_logger("meta_orchestrator")


# ------------------------------------------------------------
# SAFE CALLS / WRAPPERS
# ------------------------------------------------------------
def _safe_call(label, fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except Exception as e:
        logger.debug(f"[MetaSafe] {label} failed silently ({e})")
        return None


def _safe_dict(label, fn, *args, **kwargs):
    val = _safe_call(label, fn, *args, **kwargs)
    return val if isinstance(val, dict) else {}


def _safe_list(label, fn, *args, **kwargs):
    val = _safe_call(label, fn, *args, **kwargs)
    return val if isinstance(val, list) else []


# ------------------------------------------------------------
# FULL META COGNITIVE CYCLE (Phase-20 Version)
# ------------------------------------------------------------
def run_meta_cognitive_cycle():
    """
    Observational meta-cognitive cycle.

    STRUCTURAL GUARANTEES (Phase 47.2):
        • No execution authority
        • No packet emission
        • No control-plane influence
        • Signals only
    """
    logger.debug("[Meta] Starting meta-cognitive cycle (Phase-20)")

    # 1) Context (read-only aggregation)
    ctx = _safe_call("MetaContext.build", MetaContext.build)
    ctx_dict = ctx.as_dict() if ctx else {}

    # 2) Engines (dict inputs only)
    patterns = _safe_list("pattern_classifier", classify_meta_patterns, ctx_dict)
    trends = _safe_dict("trend_engine", compute_meta_trends, ctx_dict)
    anomalies = _safe_list("anomaly_detector", detect_meta_anomalies, ctx_dict)

    # Phase-20 USDI: error trend analyzer
    error_trends = _safe_dict("error_trend_analyzer", get_error_trend_summary)

    # 3) Snapshot
    snapshot = _safe_dict("meta_snapshot_engine", build_meta_snapshot, ctx_dict)
    snapshot["patterns"] = patterns
    snapshot["meta_trends"] = trends
    snapshot["anomalies"] = anomalies
    snapshot["error_trends"] = error_trends

    # 4) Memory integration (read-only)
    memory_integrated = _safe_dict(
        "memory_integration",
        integrate_meta_memory,
        context=ctx_dict,
        snapshot=snapshot,
        patterns=patterns,
        trends=trends,
        anomalies=anomalies,
    )

    # 5) Summary (presentation-only text)
    summary_text = _safe_call("meta_summary", render_meta_summary, snapshot)
    summary_text = summary_text if isinstance(summary_text, str) else ""

    # 6) Aggregation (signals only)
    combined = _safe_dict(
        "meta_cycle_aggregator",
        aggregate_meta_cycle,
        meta_snapshot=snapshot,
        memory_integrated=memory_integrated,
        summary_text=summary_text,
    )

    return {
        "success": True,
        "context": ctx_dict,
        "snapshot": snapshot,
        "patterns": patterns,
        "trends": trends,
        "anomalies": anomalies,
        "error_trends": error_trends,
        "memory_integrated": memory_integrated,
        "summary": summary_text,
        "combined": combined,
    }


# ------------------------------------------------------------
# SUMMARY-ONLY MODE — REQUIRED BY PHASE 16
# ------------------------------------------------------------
def run_meta_cycle_summary():
    """
    Lightweight observational variant.
    Dict-only processing. No execution. No authority.
    """
    ctx = _safe_call("MetaContext.build", MetaContext.build)
    ctx_dict = ctx.as_dict() if ctx else {}

    patterns = _safe_list("pattern_classifier", classify_meta_patterns, ctx_dict)
    trends = _safe_dict("trend_engine", compute_meta_trends, ctx_dict)
    anomalies = _safe_list("anomaly_detector", detect_meta_anomalies, ctx_dict)

    error_trends = _safe_dict("error_trend_analyzer", get_error_trend_summary)

    snapshot = _safe_dict("meta_snapshot_engine", build_meta_snapshot, ctx_dict)
    snapshot["patterns"] = patterns
    snapshot["meta_trends"] = trends
    snapshot["anomalies"] = anomalies
    snapshot["error_trends"] = error_trends

    summary_text = _safe_call("meta_summary", render_meta_summary, snapshot)
    summary_text = summary_text if isinstance(summary_text, str) else ""

    return {
        "success": True,
        "context": ctx_dict,
        "snapshot": snapshot,
        "patterns": patterns,
        "trends": trends,
        "anomalies": anomalies,
        "error_trends": error_trends,
        "summary": summary_text,
    }


# ------------------------------------------------------------
# DIAGNOSTICS — Phase-20
# ------------------------------------------------------------
def get_meta_layer_diagnostics():
    """
    Diagnostic-only access surface.
    Must never be routed into execution or packets.
    """
    try:
        ctx = MetaContext.build()
        ctx_dict = ctx.as_dict()

        trends = _safe_dict("trend_engine", compute_meta_trends, ctx_dict)
        patterns = _safe_list("pattern_classifier", classify_meta_patterns, ctx_dict)
        anomalies = _safe_list("anomaly_detector", detect_meta_anomalies, ctx_dict)

        snap = _safe_dict("meta_snapshot_engine", build_meta_snapshot, ctx_dict)
        snap["patterns"] = patterns
        snap["meta_trends"] = trends
        snap["anomalies"] = anomalies

        error_trends = _safe_dict("error_trend_analyzer", get_error_trend_summary)
        snap["error_trends"] = error_trends

        return {
            "available": True,
            "context": ctx_dict,
            "snapshot": snap,
            "trends": trends,
            "patterns": patterns,
            "anomalies": anomalies,
            "error_trends": error_trends,
        }
    except Exception:
        return {"available": False, "error": "Meta diagnostics failure"}


def get_meta_diagnostics():
    """
    Minimal diagnostic accessor.
    """
    try:
        ctx = MetaContext.build()
        return {"available": True, "context": ctx.as_dict()}
    except Exception:
        return {"available": False, "error": "Meta diagnostics failure"}


# ------------------------------------------------------------
# EXPORTS
# ------------------------------------------------------------
__all__ = [
    "run_meta_cognitive_cycle",
    "run_meta_cycle_summary",
    "get_meta_layer_diagnostics",
    "get_meta_diagnostics",
]

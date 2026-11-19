# meta_memory_integrator.py — Phase 16
# ----------------------------------------------------------
# META MEMORY INTEGRATOR (UPGRADED)
#
# Purpose (Phase 16):
#   Integrate multiple sources into a unified meta-layer
#   interpretation object:
#       • Meta snapshot (patterns + trends already embedded)
#       • Raw MetaContext (serializable context)
#       • Meta pattern classification results
#       • Meta trend results
#       • Meta anomaly detection signals
#
#   This is a PURE READ-ONLY module and does NOT write to:
#       • strategic memory
#       • KG
#       • databases
#       • any persistent store
#
#   It prepares the final meta-cycle integration object for
#   Phase 16 and will become the basis for Phase 17 meta-memory.
# ----------------------------------------------------------

from typing import Dict, Any


# =====================================================================
# PHASE 16 REQUIRED PUBLIC API
# The test harness and orchestrators expect: integrate_meta_memory()
# =====================================================================
def integrate_meta_memory(
    context: Dict[str, Any],
    snapshot: Dict[str, Any],
    patterns: Dict[str, Any],
    trends: Dict[str, Any],
    anomalies: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Consolidate all Phase-16 meta-layer data into a single,
    structured, memory-ready interpretation object.

    NOTE:
        • This is 100% read-only.
        • There is NO persistence.
        • There is NO modification of strategic memory.
        • All input data is taken at face value.
    """

    # -------------------------------------------------------
    # Basic validation
    # -------------------------------------------------------
    if not snapshot or not snapshot.get("meta"):
        return {
            "available": False,
            "reason": "invalid_meta_snapshot",
        }

    if not context or not isinstance(context, dict):
        return {
            "available": False,
            "reason": "invalid_context",
        }

    # patterns, trends, anomalies may be empty — that's fine

    # -------------------------------------------------------
    # Build unified meta-layer interpretation object
    # -------------------------------------------------------
    return {
        "available": True,

        # ---------------------------------------------------
        # Raw meta-layer content
        # ---------------------------------------------------
        "context": context,
        "meta_snapshot": snapshot,
        "patterns": patterns,
        "trends": trends,
        "anomalies": anomalies,

        # ---------------------------------------------------
        # Convenience rollups
        # ---------------------------------------------------
        "meta_core": snapshot.get("meta", {}),
        "recent_activity": snapshot.get("recent_activity", {}),
        "pattern_synthesis": snapshot.get("pattern_synthesis", []),

        # Signals flattened for dashboards & meta-cycle aggregator
        "signal_stability": snapshot.get("meta", {}).get("stability_signal"),
        "signal_drift": snapshot.get("meta", {}).get("drift_profile"),
        "signal_reinforcement": snapshot.get("meta", {}).get("reinforcement_profile"),
        "signal_kg": snapshot.get("meta", {}).get("kg_summary"),
        "signal_weak_skills": snapshot.get("meta", {}).get("skill_weaknesses"),

        # ---------------------------------------------------
        # Timestamps (read-only propagation)
        # ---------------------------------------------------
        "timestamp_meta": snapshot.get("timestamp"),
        "timestamp_context": context.get("timestamp"),
    }

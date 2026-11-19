# meta_cycle_aggregator.py — Phase 40G Tier-3 (AGGREGATION-ONLY)
# -----------------------------------------------------------------
# META CYCLE AGGREGATOR
#
# PURPOSE (Tier-3):
#   Aggregate meta-layer components into a single, expanded
#   meta-cycle object for presentation and diagnostics.
#
# GUARANTEES:
#   • READ-ONLY
#   • AGGREGATION ONLY (no interpretation, no synthesis)
#   • No ranking, no conclusions, no recommendations
#
# Notes:
#   • Does NOT mutate state, write to DB, or log
#   • Consumes signal-safe inputs
# -----------------------------------------------------------------

from typing import Dict, Any


def aggregate_meta_cycle(
    meta_snapshot: Dict[str, Any],
    memory_integrated: Dict[str, Any],
    summary_text: str = None,
) -> Dict[str, Any]:
    """
    Combine meta-layer components into a unified meta-cycle object.
    Tier-3 safe: aggregates and flattens fields without inference.
    """

    # ----------------------------------------------------------
    # Validate inputs (mechanical only)
    # ----------------------------------------------------------
    if not meta_snapshot or not meta_snapshot.get("meta"):
        return {
            "available": False,
            "reason": "invalid_meta_snapshot",
        }

    if not memory_integrated or not memory_integrated.get("available"):
        return {
            "available": False,
            "reason": "invalid_memory_integration",
        }

    # ----------------------------------------------------------
    # Extract optional fields (no defaults implying meaning)
    # ----------------------------------------------------------
    meta_trends = meta_snapshot.get("meta_trends")
    patterns = meta_snapshot.get("patterns")
    pattern_synthesis = meta_snapshot.get("pattern_synthesis")

    # ----------------------------------------------------------
    # Aggregate meta-cycle output (RAW / FLATTENED)
    # ----------------------------------------------------------
    return {
        "available": True,

        # Raw inputs
        "meta_snapshot": meta_snapshot,
        "memory_integrated": memory_integrated,

        # Optional presentation artifact (opaque)
        "meta_summary_text": summary_text,

        # ------------------------------------------------------
        # Flattened signals (labels are neutral)
        # ------------------------------------------------------
        "signals": {
            "stability_signal": meta_snapshot.get("meta", {}).get("stability_signal"),
            "drift_profile": meta_snapshot.get("meta", {}).get("drift_profile"),
            "reinforcement_profile": meta_snapshot.get("meta", {}).get("reinforcement_profile"),
            "skill_weaknesses": meta_snapshot.get("meta", {}).get("skill_weaknesses"),
            "kg_summary": meta_snapshot.get("meta", {}).get("kg_summary"),

            # Phase-16 passthroughs (no interpretation)
            "meta_trends": meta_trends,
            "patterns": patterns,
            "pattern_synthesis": pattern_synthesis,
        },

        # ------------------------------------------------------
        # Memory-integrated passthroughs (RAW)
        # ------------------------------------------------------
        "objective": memory_integrated.get("objective"),
        "strategic_score": memory_integrated.get("strategic_score"),
        "strategic_drift": memory_integrated.get("strategic_drift"),
        "strategic_reinforcement": memory_integrated.get("strategic_reinforcement"),
        "normalized_interpretation": memory_integrated.get("normalized_interpretation"),

        # ------------------------------------------------------
        # Timestamps (RAW)
        # ------------------------------------------------------
        "timestamp_snapshot": meta_snapshot.get("timestamp"),
        "timestamp_memory": memory_integrated.get("timestamp_meta"),
        "timestamp_summary": memory_integrated.get("timestamp_strategic"),
    }


# EOF

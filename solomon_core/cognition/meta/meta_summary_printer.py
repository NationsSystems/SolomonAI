# meta_summary_printer.py — Phase 40G Tier-3 (PRESENTATION-ONLY)
# ----------------------------------------------------------------------
# META SUMMARY PRINTER
#
# PURPOSE (Tier-3):
#   Render a meta snapshot into a clean, human-readable,
#   multi-section presentation.
#
# PHASE 47.2 — STRUCTURAL AWARENESS CLARIFICATION:
#   • TERMINAL PRESENTATION SURFACE
#   • NOT an execution surface
#   • NOT a planner input
#   • NOT a PacketHeader author
#   • NOT an ML HUD
#   • Output is for human inspection only
#
# GUARANTEES:
#   • READ-ONLY
#   • PRESENTATION ONLY (no interpretation, no synthesis)
#   • No ranking, no conclusions, no recommendations
#
# Notes:
#   • Never writes to memory, logs, or DB
#   • Consumes signal-safe inputs
#   • Downstream systems must not consume this output
# ----------------------------------------------------------------------

from typing import Dict, Any
import json


def _fmt(obj: Any) -> str:
    """Pretty JSON formatter (presentation only)."""
    return json.dumps(obj, indent=2, sort_keys=True)


def _json_safe_list(items):
    """
    Convert objects with .as_dict() or __dict__ into
    JSON-serializable representations for display.
    """
    safe = []
    for item in items:
        if hasattr(item, "as_dict") and callable(item.as_dict):
            safe.append(item.as_dict())
        elif hasattr(item, "__dict__"):
            safe.append(item.__dict__)
        else:
            safe.append(item)
    return safe


def render_meta_summary(snapshot: Dict[str, Any]) -> str:
    """
    Render a readable, multi-section diagnostic presentation
    from a meta snapshot.

    STRUCTURAL GUARANTEES (Phase 47.2):
        • Human-readable formatting only
        • No interpretation or synthesis
        • No authority or execution influence
        • Not machine-consumable by design
    """

    if not snapshot or not snapshot.get("meta"):
        return "Meta Summary Unavailable — Snapshot Empty"

    lines = []
    lines.append("=" * 58)
    lines.append("                 SOLOMON META SUMMARY")
    lines.append("=" * 58)
    lines.append(f"Timestamp: {snapshot.get('timestamp')}")
    lines.append("")

    # ------------------------------------------------------
    # META LAYER (RAW SIGNALS)
    # ------------------------------------------------------
    meta = snapshot["meta"]
    lines.append("-" * 58)
    lines.append(" META LAYER (RAW SIGNALS)")
    lines.append("-" * 58)
    lines.append(f"Stability Signal     : {meta.get('stability_signal')}")
    lines.append(f"Drift Profile        : {_fmt(meta.get('drift_profile'))}")
    lines.append(f"Reinforcement Profile: {_fmt(meta.get('reinforcement_profile'))}")
    lines.append(f"Autonomy Status      : {_fmt(meta.get('autonomy_status'))}")
    lines.append("")

    # ------------------------------------------------------
    # KNOWLEDGE GRAPH (RAW)
    # ------------------------------------------------------
    lines.append("-" * 58)
    lines.append(" KNOWLEDGE GRAPH (RAW)")
    lines.append("-" * 58)
    lines.append(_fmt(meta.get("kg_summary")))
    lines.append("")

    # ------------------------------------------------------
    # SKILL WEAKNESSES (RAW)
    # ------------------------------------------------------
    lines.append("-" * 58)
    lines.append(" SKILL WEAKNESSES (RAW)")
    lines.append("-" * 58)
    lines.append(_fmt(meta.get("skill_weaknesses")))
    lines.append("")

    # ------------------------------------------------------
    # RECENT STRATEGIC ACTIVITY (RAW)
    # ------------------------------------------------------
    recent = snapshot.get("recent_activity", {})

    safe_outcomes = _json_safe_list(recent.get("outcomes", []))
    safe_scores = recent.get("scores", [])
    safe_simulations = _json_safe_list(recent.get("simulations", []))

    lines.append("-" * 58)
    lines.append(" RECENT STRATEGIC ACTIVITY (RAW)")
    lines.append("-" * 58)
    lines.append(f"Recent Outcomes:\n{_fmt(safe_outcomes)}")
    lines.append(f"Recent Scores:\n{_fmt(safe_scores)}")
    lines.append(f"Recent Simulations:\n{_fmt(safe_simulations)}")
    lines.append("")

    # ------------------------------------------------------
    # META PATTERNS (RAW)
    # ------------------------------------------------------
    lines.append("-" * 58)
    lines.append(" META PATTERNS (RAW)")
    lines.append("-" * 58)
    lines.append(_fmt(snapshot.get("patterns")))
    lines.append("")

    # ------------------------------------------------------
    # META TRENDS (RAW)
    # ------------------------------------------------------
    trend = snapshot.get("meta_trends", {})
    lines.append("-" * 58)
    lines.append(" META TRENDS (RAW)")
    lines.append("-" * 58)
    lines.append(_fmt(trend) if trend else "(No meta trends provided)")
    lines.append("")

    # ------------------------------------------------------
    # PATTERN SYNTHESIS (RAW LIST)
    # ------------------------------------------------------
    synthesis = snapshot.get("pattern_synthesis", [])
    lines.append("-" * 58)
    lines.append(" PATTERN SYNTHESIS (RAW LIST)")
    lines.append("-" * 58)
    lines.append(_fmt(synthesis))
    lines.append("")

    lines.append("=" * 58)
    lines.append("                 END META SUMMARY")
    lines.append("=" * 58)

    return "\n".join(lines)


# ----------------------------------------------------------
# Compatibility Alias (Presentation-only)
# ----------------------------------------------------------
def format_meta_summary(snapshot: Dict[str, Any]) -> str:
    """
    Backwards-compatible wrapper.
    Presentation-only.
    """
    return render_meta_summary(snapshot)

# error_trend_analyzer.py — Phase 19 Compatibility + Phase 20 JSON-SAFE
# ----------------------------------------------------------------------
# Provides error trend summaries for meta-cognition and strategic cycle.
#
# REQUIREMENTS:
#   • Must be JSON-safe (Phase 16 + Phase 18)
#   • Must return Phase-19 fields (error_count, recent_errors, error_types)
#   • Must keep Phase-20 cluster + stability structure
#   • All timestamps must be ISO strings
# ----------------------------------------------------------------------

from solomon_core.error_sentinel import get_error_history
from datetime import datetime


# ------------------------------------------------------------
# SAFE CONVERSION UTILITIES
# ------------------------------------------------------------
def _safe(obj):
    """Recursively convert datetime → ISO strings and sanitize unknown types."""
    if isinstance(obj, datetime):
        return obj.isoformat()

    if isinstance(obj, dict):
        return {str(k): _safe(v) for k, v in obj.items()}

    if isinstance(obj, list):
        return [_safe(x) for x in obj]

    # Convert anything else to JSON-safe primitive
    try:
        return obj
    except Exception:
        return str(obj)


# ------------------------------------------------------------
# MAIN API
# ------------------------------------------------------------
def get_error_trend_summary():
    """
    RETURNS (FULLY JSON SAFE):
        {
            "count": int,
            "clusters": [...],
            "latest": {...},
            "stability_score": float,

            # Phase-19 compatibility fields:
            "error_count": int,
            "error_types": [...],
            "recent_errors": [...],
            "latest_error": {...}
        }
    """
    history = get_error_history() or []

    # No errors → fully stable
    if not history:
        empty_packet = {
            "count": 0,
            "clusters": [],
            "latest": None,
            "stability_score": 100.0,

            # Phase-19 required fields
            "error_count": 0,
            "error_types": [],
            "recent_errors": [],
            "latest_error": None,
        }
        return _safe(empty_packet)

    # ------------------------------
    # GROUP BY ERROR TYPE
    # ------------------------------
    clusters = {}
    for entry in history:
        key = entry.get("error_type", "unknown")
        clusters.setdefault(key, []).append(entry)

    cluster_summaries = []
    for etype, items in clusters.items():
        latest = max(items, key=lambda x: x.get("timestamp") or 0)
        cluster_summaries.append({
            "type": etype,
            "count": len(items),
            "latest": latest,
        })

    # ------------------------------
    # SIMPLE STABILITY SCORE
    # ------------------------------
    total = len(history)
    stability_score = max(0.0, 100.0 - (total * 2.5))

    # Most recent event overall
    latest_event = max(history, key=lambda x: x.get("timestamp") or 0)

    # ------------------------------
    # PHASE-19 Fields
    # ------------------------------
    error_types = list(clusters.keys())
    # Last 20 errors for backward compatibility
    recent_errors = history[-20:]

    # ------------------------------
    # FINAL MERGED STRUCTURE
    # ------------------------------
    packet = {
        "count": total,
        "clusters": cluster_summaries,
        "latest": latest_event,
        "stability_score": stability_score,

        # Phase-19
        "error_count": total,
        "error_types": error_types,
        "recent_errors": recent_errors,
        "latest_error": latest_event,
    }

    return _safe(packet)

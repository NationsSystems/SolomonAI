# unified_diagnostics.py — Phase 16 Step 13+14 (JSON-SAFE PATCH v4)
# ------------------------------------------------------------
# Includes full JSON-safe conversion for:
#   • datetime
#   • tuple keys (stringify safely)
#   • mixed-type tuples (fix for floats in join)
#   • non-string keys
#   • nested dict/list structures
# ------------------------------------------------------------

import datetime

from solomon_core.autonomy.strict_autonomy_controller import should_autonomy_run
from solomon_core.cognition.operational_cognition_controller import (
    get_operational_diagnostics,
)
from solomon_core.cognition.strategic_cognition_controller import (
    get_strategic_diagnostics,
)


# ------------------------------------------------------------
# Timestamp helper
# ------------------------------------------------------------
def _now():
    return datetime.datetime.utcnow().isoformat()


# ------------------------------------------------------------
# FULL JSON-SAFE NORMALIZER (with tuple fix)
# ------------------------------------------------------------
def _json_safe(obj):
    """Recursively convert any Python type into a JSON-safe form."""

    # datetime → iso
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()

    # tuple → deterministic string key
    # FIX: force every element into a string
    if isinstance(obj, tuple):
        try:
            return "__".join(str(_json_safe(x)) for x in obj)
        except Exception:
            # Fallback: stringify entire tuple
            return str(tuple(str(_json_safe(x)) for x in obj))

    # sets → list
    if isinstance(obj, set):
        return [_json_safe(x) for x in obj]

    # dict → normalize KEYS and VALUES
    if isinstance(obj, dict):
        safe_dict = {}
        for k, v in obj.items():
            # Convert keys to JSON-safe strings
            safe_k = _json_safe(k)
            if not isinstance(safe_k, str):
                safe_k = str(safe_k)
            safe_dict[safe_k] = _json_safe(v)
        return safe_dict

    # lists → normalize each element
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]

    # primitives we can return directly
    if isinstance(obj, (str, int, float, bool, type(None))):
        return obj

    # everything else → fallback string
    return str(obj)


# ------------------------------------------------------------
# Unified Diagnostics
# ------------------------------------------------------------
def get_unified_autonomy_cognition_diagnostics():
    """
    Returns a complete snapshot:
        • autonomy gating
        • operational diagnostics
        • strategic diagnostics
        • strategic skill selector diagnostics
        • meta layer diagnostics
    """

    autonomy_state = should_autonomy_run()

    # Operational diagnostics
    try:
        operational = get_operational_diagnostics()
    except Exception as e:
        operational = {"success": False, "error": str(e), "timestamp": _now()}

    # Strategic diagnostics
    try:
        strategic = get_strategic_diagnostics()
    except Exception as e:
        strategic = {"success": False, "error": str(e), "timestamp": _now()}

    # Lazy import for meta layer
    try:
        from solomon_core.cognitive_orchestrator import get_meta_layer_diagnostics
        meta = get_meta_layer_diagnostics()
    except Exception as e:
        meta = {"available": False, "error": str(e), "timestamp": _now()}

    # Lazy import for strategic skill selector
    try:
        from solomon_core.cognition.strategic_skill_selector import (
            get_strategic_skill_diagnostics,
        )
        strategic_skill_selector = get_strategic_skill_diagnostics()
    except Exception as e:
        strategic_skill_selector = {
            "available": False,
            "error": str(e),
            "timestamp": _now(),
        }

    packet = {
        "success": True,
        "timestamp": _now(),
        "autonomy": autonomy_state,
        "operational": operational,
        "strategic": strategic,
        "strategic_skill_selector": strategic_skill_selector,
        "meta": meta,
    }

    # FINAL GLOBAL SANITIZATION
    return _json_safe(packet)

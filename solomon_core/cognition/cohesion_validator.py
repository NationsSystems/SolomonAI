# cohesion_validator.py — Phase 16 Step 20 (Patched for JSON safety)
# ------------------------------------------------------------
# Operational–Strategic–Meta Cohesion Validator
# ------------------------------------------------------------

import datetime
from typing import Dict, Any, List

from solomon_core.autonomy.strict_autonomy_controller import should_autonomy_run
from solomon_core.cognition.operational_cognition_controller import get_operational_diagnostics
from solomon_core.cognition.strategic_cognition_controller import get_strategic_diagnostics
from solomon_core.cognition.meta.meta_context import MetaContext


# ------------------------------------------------------------
# JSON-SAFE RECURSIVE ENCODER
# ------------------------------------------------------------
def _json_safe(obj):
    """Convert any object into a JSON-safe form."""

    # Basic types
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj

    # Datetime → ISO string
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()

    # Lists
    if isinstance(obj, list):
        return [_json_safe(x) for x in obj]

    # Tuples → list
    if isinstance(obj, tuple):
        return [_json_safe(x) for x in obj]

    # Dicts
    if isinstance(obj, dict):
        safe = {}
        for k, v in obj.items():
            sk = str(k)
            safe[sk] = _json_safe(v)
        return safe

    # Objects with __dict__
    if hasattr(obj, "__dict__"):
        return _json_safe(obj.__dict__)

    # Fallback
    return str(obj)


def _now():
    return datetime.datetime.utcnow().isoformat()


# ------------------------------------------------------------
# Helper evaluators
# ------------------------------------------------------------
def _check_autonomy_consistency(auto: Dict[str, Any], issues: List[str]):
    if not auto:
        issues.append("Autonomy diagnostics missing.")
        return

    if not auto.get("allowed", True):
        issues.append(f"Autonomy gate: blocked due to {auto.get('reason')}")


def _check_mode_alignment(oper: Dict[str, Any], strat: Dict[str, Any], issues: List[str]):
    if oper.get("available") is False:
        issues.append("Operational layer reports unavailable diagnostics.")

    if strat.get("kg", {}).get("insights") is None:
        issues.append("Strategic layer KG insights missing.")

    if "weak_skills" in strat and not strat["weak_skills"].get("weak_skills"):
        issues.append("Strategic reports no weak skills — verify skill weakness engine.")


def _check_skill_selection_vs_trends(strat: Dict[str, Any], meta: Dict[str, Any], issues: List[str]):
    sel = strat.get("strategic_skill_selector", {})
    priority = sel.get("priority")

    if not priority:
        issues.append("Strategic priority skill not available.")
        return

    pat = meta.get("pattern_flags", {})
    if pat.get("reinforcement_trend") == "declining":
        issues.append(f"Priority skill '{priority}' selected during negative reinforcement trend.")


def _check_drift_consistency(meta: Dict[str, Any], issues: List[str]):
    drift = meta.get("drift_profile", {})
    dval = drift.get("overall_drift", 0)

    if dval > 0.7:
        issues.append("High drift detected across recent outcomes.")
    elif dval > 0.3:
        issues.append("Moderate drift variability detected.")


def _check_reinforcement_consistency(meta: Dict[str, Any], issues: List[str]):
    rprof = meta.get("reinforcement_profile", {})
    avg = rprof.get("average_signal", 0)

    if avg < 0.05:
        issues.append("Reinforcement signal extremely low — verify stability.")
    elif avg < 0.2:
        issues.append("Weak reinforcement signals — monitor trend.")


# ------------------------------------------------------------
# Core Cohesion Validator
# ------------------------------------------------------------
def validate_cognition_cohesion() -> Dict[str, Any]:
    issues: List[str] = []

    # ------------------------
    # Autonomy diagnostics
    # ------------------------
    autonomy = should_autonomy_run()
    _check_autonomy_consistency(autonomy, issues)

    # ------------------------
    # Operational diagnostics
    # ------------------------
    try:
        operational = get_operational_diagnostics()
    except Exception as e:
        operational = {"available": False, "error": str(e)}
        issues.append(f"Operational diagnostics error: {e}")

    # ------------------------
    # Strategic diagnostics
    # ------------------------
    try:
        strategic = get_strategic_diagnostics()
    except Exception as e:
        strategic = {"available": False, "error": str(e)}
        issues.append(f"Strategic diagnostics error: {e}")

    # ------------------------
    # Meta context
    # ------------------------
    try:
        meta_ctx = MetaContext.build().as_dict()
    except Exception as e:
        meta_ctx = {"available": False, "error": str(e)}
        issues.append(f"MetaContext build error: {e}")

    # ------------------------
    # Cross-layer checks
    # ------------------------
    _check_mode_alignment(operational, strategic, issues)
    _check_skill_selection_vs_trends(strategic, meta_ctx, issues)
    _check_drift_consistency(meta_ctx, issues)
    _check_reinforcement_consistency(meta_ctx, issues)

    # Determine severity
    if any("error" in x.lower() for x in issues):
        status = "fail"
    elif issues:
        status = "warning"
    else:
        status = "good"

    packet = {
        "available": True,
        "cohesion_status": status,
        "issues": issues,
        "signals": {
            "autonomy": autonomy,
            "operational": operational,
            "strategic": strategic,
            "meta": meta_ctx,
        },
        "timestamp": _now(),
    }

    # 🔥 JSON-SAFE return for Phase 16
    return _json_safe(packet)


# ------------------------------------------------------------
# Public API for Phase 16 Step 20
# ------------------------------------------------------------
def get_cognition_cohesion_diagnostics():
    return validate_cognition_cohesion()

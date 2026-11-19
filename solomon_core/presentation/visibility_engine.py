# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/visibility_engine.py
# ---------------------------------------------------------------------------
# Visibility Engine
#
# Determines which portions of the Decision Object are visible
# for a given posture.
# ---------------------------------------------------------------------------

from typing import Dict, Any, List


# ============================================================================
# Public API
# ============================================================================

def compute_visibility(
    posture: str,
    decision_object: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Returns a visibility projection.

    CRITICAL findings ALWAYS visible.
    """

    findings: List[Dict[str, Any]] = decision_object.get("findings") or []

    critical_present = any(f.get("severity") == "CRITICAL" for f in findings)

    # ------------------------------------------------------------------
    # Base projection
    # ------------------------------------------------------------------
    result = {
        "documents": decision_object.get("documents"),
        "findings": [],
        "critical_present": critical_present,
    }

    # ------------------------------------------------------------------
    # Posture logic
    # ------------------------------------------------------------------

    if posture == "FORENSIC":
        result["findings"] = findings
        return result

    if posture == "TIME_PRESSURE":
        result["findings"] = [
            f for f in findings if f.get("severity") in {"CRITICAL", "HIGH"}
        ]

    elif posture == "BINARY":
        result["findings"] = [
            f for f in findings if f.get("severity") == "CRITICAL"
        ]

    elif posture == "TOPIC_FOCUS":
        result["findings"] = findings  # filtering happens later in narration

    elif posture == "WALKTHROUGH":
        result["findings"] = findings

    else:  # EXECUTIVE default
        result["findings"] = [
            f for f in findings if f.get("severity") in {"CRITICAL", "HIGH"}
        ]

    # ------------------------------------------------------------------
    # CRITICAL supremacy enforcement
    # ------------------------------------------------------------------
    if critical_present:
        for f in findings:
            if f.get("severity") == "CRITICAL" and f not in result["findings"]:
                result["findings"].append(f)

    return result

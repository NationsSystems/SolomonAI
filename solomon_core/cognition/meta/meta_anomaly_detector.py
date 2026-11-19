# meta_anomaly_detector.py — Phase 15 Step 1 + Phase 18 Stability Upgrade (Option B1)
# -------------------------------------------------------------------------------
# META ANOMALY DETECTOR (Phase 18)
#
# Fully deterministic, JSON-safe, tolerant of MetaContext or dict input.
# -------------------------------------------------------------------------------

from typing import Dict, Any


class MetaAnomalyDetector:
    """Phase-18 anomaly detector (lightweight, deterministic)."""
    pass


# ------------------------------------------------------------
# INTERNAL HELPERS (Phase 18)
# ------------------------------------------------------------
def _check_drift_anomaly(drift_profile: Dict[str, Any]) -> Dict[str, Any]:
    if not drift_profile:
        return {}
    drift = drift_profile.get("overall_drift")
    if drift is None:
        return {}
    if drift > 0.6:
        return {"drift_spike": drift}
    return {}


def _check_reinforcement_anomaly(reinf: Dict[str, Any]) -> Dict[str, Any]:
    if not reinf:
        return {}
    avg = reinf.get("average_signal")
    if avg is None:
        return {}
    if avg < 0.15:
        return {"reinforcement_collapse": avg}
    return {}


def _check_kg_anomaly(kg_summary: Dict[str, Any]) -> Dict[str, Any]:
    if not kg_summary:
        return {}
    stability = kg_summary.get("stability", {})
    score = stability.get("score")
    if score is None:
        return {}
    if score < 0.25:
        return {"kg_instability": score}
    return {}


def _check_weak_skill_cluster(skills: Any) -> Dict[str, Any]:
    if not skills:
        return {}
    skills_sorted = sorted(skills, key=lambda x: x.get("score", 1.0))
    weakest = skills_sorted[:3]
    if all(w.get("score", 1.0) < 0.2 for w in weakest):
        return {"weak_skill_cluster": [w.get("skill") for w in weakest]}
    return {}


def _check_simulation_anomaly(sims: Any) -> Dict[str, Any]:
    if not sims:
        return {}
    last3 = sims[-3:]
    improvements = []
    for s in last3:
        if isinstance(s, dict):
            improvements.append(s.get("expected_improvement") or 0)
    if len(improvements) < 3:
        return {}
    if max(improvements) - min(improvements) > 0.5:
        return {"simulation_instability": improvements}
    return {}


def _check_priority_anomaly(priority_alignment: Dict[str, Any]) -> Dict[str, Any]:
    if not priority_alignment:
        return {}
    if priority_alignment.get("alignment_signal") == "weak_alignment":
        return {"priority_alignment_failure": True}
    return {}


# ------------------------------------------------------------
# PUBLIC API — FIXED to accept MetaContext OR dict
# ------------------------------------------------------------
def detect_meta_anomalies(context: Any) -> Dict[str, Any]:
    """
    Phase-18 anomaly detector.
    Accepts:
        • MetaContext object
        • dict containing meta-layer fields

    Auto-converts MetaContext → dict safely.
    """

    # --------------------------------------------
    # 🔧 FIX: allow MetaContext or dict
    # --------------------------------------------
    if hasattr(context, "as_dict"):
        context = context.as_dict()

    # Now guaranteed dict
    drift_profile = context.get("drift_profile") or {}
    reinf = context.get("reinforcement_profile") or {}
    kg_summary = context.get("kg_summary") or {}
    skills = context.get("skill_weaknesses") or []
    sims = context.get("recent_simulations") or []
    priority_alignment = context.get("priority_alignment") or {}

    anomalies = {}

    anomalies.update(_check_drift_anomaly(drift_profile))
    anomalies.update(_check_reinforcement_anomaly(reinf))
    anomalies.update(_check_kg_anomaly(kg_summary))
    anomalies.update(_check_weak_skill_cluster(skills))
    anomalies.update(_check_simulation_anomaly(sims))
    anomalies.update(_check_priority_anomaly(priority_alignment))

    return {
        "anomalies_detected": bool(anomalies),
        "details": anomalies,
    }

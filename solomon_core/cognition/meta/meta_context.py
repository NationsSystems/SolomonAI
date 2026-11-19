# meta_context.py — Phase 18 Stability Upgrade (Option B1)
# ---------------------------------------------------------------------------
# Central meta-cognitive context container.
#
# Phase 18 adds:
#   • KG sync alignment (read-only in controller, safe here)
#   • Reinforcement snapshot passthrough
#   • Deterministic weak-skill ordering (score + reinforcement)
#   • Safer extraction of strategic outcome fields
#   • JSON-safe expansion of simulations, scores, drift, reinforcement
#   • Phase-18 compatible context envelope
#
# PHASE 47.2 — STRUCTURAL AWARENESS CLARIFICATION:
#   • MetaContext is an INTENTIONALLY IMPLICIT structural artifact
#   • It is NOT a first-class “ML HUD” or execution surface
#   • Absence of a dedicated ML HUD module is INTENTIONAL, not missing
#   • This object aggregates signals for observation only
#
# Fully read-only. No persistence. No mutation.
# No authority. No execution. No routing.
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
import datetime

# Strategic memory
from solomon_core.planner.strategic_memory import get_outcome_history

# Autonomy
from solomon_core.autonomy.strict_autonomy_controller import should_autonomy_run

# Knowledge graph signals
from solomon_core.knowledge.knowledge_graph import get_strategic_kg_summary

# Skill weakness engine + reinforcement weighting
from solomon_core.knowledge.skill_weakness_engine import get_global_skill_weaknesses
from solomon_core.reinforcement_store import get_reinforcement_weight


@dataclass
class MetaContext:
    """
    Universal meta-cognitive container.

    STRUCTURAL ROLE (Phase 47.2):
        • Observational aggregation only
        • Implicit structural artifact by design
        • Not an execution surface
        • Not an ML HUD
        • Not authoritative

    Phase 18 stable edition.
    """

    # ---- Raw outcome data ----
    recent_outcomes: List[Any] = field(default_factory=list)
    recent_scores: List[Any] = field(default_factory=list)
    recent_simulations: List[Any] = field(default_factory=list)

    # ---- Priority fields ----
    priority_skill: Optional[str] = None
    priority_alignment_score: float = 0.0

    # ---- Derived signals ----
    pattern_flags: Dict[str, Any] = field(default_factory=dict)
    trend_summary: Dict[str, Any] = field(default_factory=dict)
    anomaly_signals: Dict[str, Any] = field(default_factory=dict)
    snapshot: Dict[str, Any] = field(default_factory=dict)

    # ---- Reinforcement + drift ----
    reinforcement_profile: Dict[str, Any] = field(default_factory=dict)
    drift_profile: Dict[str, Any] = field(default_factory=dict)

    # ---- KG + skills + autonomy ----
    kg_summary: Dict[str, Any] = field(default_factory=dict)
    skill_weaknesses: List[Dict[str, Any]] = field(default_factory=list)
    autonomy_status: Dict[str, Any] = field(default_factory=dict)

    # ---- Meta metadata ----
    timestamp: str = ""
    notes: List[str] = field(default_factory=list)

    # ============================================================
    # BUILD — Phase 18 version (Option B1)
    # ============================================================
    @classmethod
    def build(cls):
        """
        Build a Phase-18 meta-cognitive context object.

        GUARANTEES:
            • Read-only signal aggregation
            • Deterministic ordering
            • JSON-safe structures
            • No execution or authority
        """

        outcome_objects = get_outcome_history(limit=20) or []

        outcomes = []
        scores = []
        simulations = []

        reinforcement_signals = []
        drift_signals = []
        priority_alignments = []
        priority_skill_detected = None

        for o in outcome_objects:
            outcomes.append(o)

            scores.append(getattr(o, "score", None))

            simulations.append({
                "expected_improvement": getattr(o, "expected_improvement", None),
                "risk": getattr(o, "simulation_risk", None),
                "drift_band": getattr(o, "drift_band", None),
            })

            reinforcement = getattr(o, "reinforcement", {}) or {}
            reinforcement_signals.append(reinforcement)

            drift = getattr(o, "drift", {}) or {}
            drift_signals.append(drift)

            if hasattr(o, "drift_band"):
                drift.setdefault("drift_band", o.drift_band)

            if hasattr(o, "confidence"):
                reinforcement.setdefault("confidence", o.confidence)

            align = getattr(o, "priority_alignment", None)
            if align is not None:
                priority_alignments.append(align)

            if getattr(o, "priority_skill", None):
                priority_skill_detected = o.priority_skill

        avg_signal = (
            sum([x.get("signal", 0.0) for x in reinforcement_signals]) / len(reinforcement_signals)
            if reinforcement_signals else 0.0
        )

        reinforcement_rollup = {
            "signals": reinforcement_signals,
            "average_signal": avg_signal,
        }

        avg_drift = (
            sum([x.get("total_drift", 0.0) for x in drift_signals]) / len(drift_signals)
            if drift_signals else 0.0
        )

        drift_rollup = {
            "states": drift_signals,
            "overall_drift": avg_drift,
        }

        priority_alignment_score = (
            sum(1 for p in priority_alignments if p) / len(priority_alignments)
            if priority_alignments else 0.0
        )

        kg_summary = get_strategic_kg_summary()

        skill_weaknesses_raw = get_global_skill_weaknesses() or []
        for entry in skill_weaknesses_raw:
            skill = entry.get("skill")
            entry["reinforcement_weight"] = get_reinforcement_weight(skill) or 0.0

        skill_weaknesses = sorted(
            skill_weaknesses_raw,
            key=lambda r: (r.get("score", 0), -r.get("reinforcement_weight", 0.0))
        )

        autonomy_status = should_autonomy_run()

        timestamp = datetime.datetime.utcnow().isoformat()

        return cls(
            recent_outcomes=outcomes,
            recent_scores=scores,
            recent_simulations=simulations,
            priority_skill=priority_skill_detected,
            priority_alignment_score=priority_alignment_score,
            reinforcement_profile=reinforcement_rollup,
            drift_profile=drift_rollup,
            kg_summary=kg_summary,
            skill_weaknesses=skill_weaknesses,
            autonomy_status=autonomy_status,
            timestamp=timestamp,
        )

    # ============================================================
    # JSON-SAFE EXPORT
    # ============================================================
    def as_dict(self) -> Dict[str, Any]:
        return {
            "recent_outcomes": [
                o.as_dict() if hasattr(o, "as_dict") else str(o)
                for o in self.recent_outcomes
            ],
            "recent_scores": self.recent_scores,
            "recent_simulations": self.recent_simulations,
            "priority_skill": self.priority_skill,
            "priority_alignment_score": self.priority_alignment_score,
            "pattern_flags": self.pattern_flags,
            "trend_summary": self.trend_summary,
            "anomaly_signals": self.anomaly_signals,
            "snapshot": self.snapshot,
            "reinforcement_profile": self.reinforcement_profile,
            "drift_profile": self.drift_profile,
            "kg_summary": self.kg_summary,
            "skill_weaknesses": self.skill_weaknesses,
            "autonomy_status": self.autonomy_status,
            "timestamp": self.timestamp,
            "notes": self.notes,
        }

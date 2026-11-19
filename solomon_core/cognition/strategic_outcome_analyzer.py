# strategic_outcome_analyzer.py — Phase 14 Step 12 + Phase 16 Step 19 + Phase 20 Step 10 (USDI Integration)
# -------------------------------------------------------------------
# Purpose:
#   Provide a unified interpretation layer for strategic cycle outputs.
#
#   Phase 16 Step 19 Enhancements:
#       • Priority-aware narrative
#       • Drift-aware stability classification
#       • Reinforcement confidence interpretation
#       • Weak-skill alignment emphasis
#       • Strategic-context consistency verification
#
#   Phase 20 Step 10 Enhancements:
#       • USDI (Unified Skill Difficulty Index) integration
#       • Difficulty-window influence scoring
#       • Hot/warm/cool strain-awareness layer
#       • Difficulty-aware insights and narrative hooks
#
#   Still:
#       • READ-ONLY
#       • No mutations, no learning, no KG changes
#       • Pure interpretation + insight generation
# -------------------------------------------------------------------

import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List

from solomon_core.logger import get_logger

# ★ Phase 20 — bring in USDI so we can add strain-aware interpretation
from solomon_core.cognition.skill_difficulty_index import (
    get_skill_difficulty_windows,
)

logger = get_logger("strategic_outcome_analyzer")


# ============================================================
# Utility
# ============================================================

def _now():
    return datetime.datetime.utcnow().isoformat()


# ============================================================
# Output Dataclass
# ============================================================

@dataclass
class StrategicOutcomeAnalysis:
    simulation_summary: Dict[str, Any]
    execution_feedback: Dict[str, Any]
    drift_report: Dict[str, Any]
    reinforcement_signal: Dict[str, Any]
    insights: List[str]
    narrative: str
    timestamp: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "simulation_summary": self.simulation_summary,
            "execution_feedback": self.execution_feedback,
            "drift_report": self.drift_report,
            "reinforcement_signal": self.reinforcement_signal,
            "insights": self.insights,
            "narrative": self.narrative,
            "timestamp": self.timestamp,
        }


# ============================================================
# Analysis Engine
# ============================================================

def analyze_strategic_outcome(
    simulation: Dict[str, Any],
    execution_feedback: Dict[str, Any],
    drift: Dict[str, Any],
    reinforcement: Dict[str, Any],
) -> StrategicOutcomeAnalysis:
    """
    Phase 14 Step 12 base + Phase 16 Step 19 enhancements +
    Phase 20 Step 10 USDI (difficulty window) integration.

    Provides a richer, more contextual interpretation of:
        • simulation
        • execution
        • drift
        • reinforcement
        • strategic priority
        • difficulty strain (hot/warm/cool USDI windows)
    """
    insights = []

    # --------------------------------------------------------
    # 0. USDI — difficulty windows (Phase 20)
    # --------------------------------------------------------
    try:
        difficulty_windows = get_skill_difficulty_windows()
    except Exception:
        difficulty_windows = {}

    sim_skill = simulation.get("objective", {}).get("metadata", {}).get("skill")
    usd_window = None

    if sim_skill:
        hot = difficulty_windows.get("hot_window", [])
        warm = difficulty_windows.get("warm_window", [])
        cool = difficulty_windows.get("cool_window", [])

        if sim_skill in hot:
            usd_window = "hot"
            insights.append(
                f"Skill '{sim_skill}' is in the HOT difficulty window — indicating high strain."
            )
        elif sim_skill in warm:
            usd_window = "warm"
            insights.append(
                f"Skill '{sim_skill}' is in the WARM difficulty window — some instability expected."
            )
        elif sim_skill in cool:
            usd_window = "cool"
            insights.append(
                f"Skill '{sim_skill}' is stable (cool difficulty window)."
            )
        else:
            usd_window = "none"
            insights.append(
                f"Skill '{sim_skill}' is not present in any USDI window — baseline stability assumed."
            )
    else:
        insights.append("No specific skill identified for USDI evaluation.")

    # --------------------------------------------------------
    # 1. Simulation Insight
    # --------------------------------------------------------
    if simulation.get("expected_total_improvement", 0) > simulation.get("total_risk", 0):
        insights.append("Simulation predicted a net positive improvement.")
    else:
        insights.append("Simulation predicted risk exceeding improvement.")

    # --------------------------------------------------------
    # 2. Execution Feedback Insight
    # --------------------------------------------------------
    if execution_feedback.get("failures", 0) == 0:
        insights.append("All actions executed successfully.")
    else:
        insights.append(f"{execution_feedback['failures']} action(s) encountered issues.")

    # --------------------------------------------------------
    # 3. Drift Interpretation (Phase 16 Step 19)
    # --------------------------------------------------------
    drift_score = drift.get("drift_score", 0)
    if drift_score <= 0.1:
        insights.append("Execution drift was negligible.")
    elif drift_score <= 0.3:
        insights.append("Execution stayed reasonably close to predicted simulation expectations.")
    elif drift_score <= 0.6:
        insights.append("Moderate execution drift observed; potential instability detected.")
    else:
        insights.append("Significant drift detected between execution and simulation.")

    # --------------------------------------------------------
    # 4. Reinforcement Interpretation (Phase 16 Step 19)
    # --------------------------------------------------------
    confidence = reinforcement.get("confidence", 0)
    weakness_pressure = reinforcement.get("weakness_pressure", 0)

    if confidence > 0.75:
        insights.append("Reinforcement indicates strong strategic confidence.")
    elif confidence > 0.4:
        insights.append("Reinforcement indicates stable but moderate confidence.")
    else:
        insights.append("Reinforcement indicates low confidence; strategic improvement needed.")

    if weakness_pressure == 0:
        insights.append("Weak skill pressure minimal — system stability increasing.")
    elif weakness_pressure <= 3:
        insights.append("Weak skill pressure moderate — improvement opportunities present.")
    else:
        insights.append("High weak skill pressure — strategic focus needed.")

    # --------------------------------------------------------
    # 5. Priority-Aware Insight
    # --------------------------------------------------------
    priority_skill = None

    if "priority_skill" in simulation:
        priority_skill = simulation["priority_skill"]

    for note in reinforcement.get("notes", []):
        if "priority" in note.lower():
            priority_skill = priority_skill or "priority_skill"

    if priority_skill:
        insights.append(f"Strategic priority '{priority_skill}' influenced plan formation.")
    else:
        insights.append("No specific strategic priority detected during this cycle.")

    # --------------------------------------------------------
    # 6. USDI-Narrative Tie-In (Phase 20)
    # --------------------------------------------------------
    if usd_window == "hot":
        insights.append(
            "High difficulty strain may have amplified drift or reduced reinforcement confidence."
        )
    elif usd_window == "warm":
        insights.append(
            "Warm difficulty classification suggests borderline stability; monitor future cycles closely."
        )
    elif usd_window == "cool":
        insights.append(
            "Cool difficulty classification supports stable execution conditions."
        )
    elif usd_window == "none":
        insights.append(
            "No difficulty-load signal detected — execution interpreted without USDI modifiers."
        )

    # --------------------------------------------------------
    # 7. Narrative
    # --------------------------------------------------------
    narrative = (
        "This strategic cycle integrates simulation predictions, execution accuracy, drift signals, "
        "reinforcement dynamics, and difficulty-strain (USDI) awareness to form a complete picture "
        "of system performance. The model evaluates weak-skill pressure, stability indicators, "
        "priority alignment, and difficulty windows to produce a cross-layer interpretation of "
        "strategic behavior and outcome reliability."
    )

    logger.info("[OutcomeAnalyzer] Strategic outcome interpreted with USDI-aware context.")

    return StrategicOutcomeAnalysis(
        simulation_summary=simulation,
        execution_feedback=execution_feedback,
        drift_report=drift,
        reinforcement_signal=reinforcement,
        insights=insights,
        narrative=narrative,
    )

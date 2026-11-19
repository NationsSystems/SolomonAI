# strategic_action_engine.py — Phase 14.3 + Phase 16 Step 17–18 + Phase 40
# -------------------------------------------------------------
# PURPOSE (Phase 40):
#   Emit STRUCTURED ACTION OBJECTS + CONTEXT BINDINGS only.
#   • No execution decisions
#   • No recommendations
#   • No ranking
#
# Converts StrategicPlan steps into StrategicAction objects and binds
# KG/weak-skill/cluster/reinforcement/priority context as READ-ONLY metadata.
# -------------------------------------------------------------

import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, List

from solomon_core.logger import get_logger
from solomon_core.planner.strategic_planner import StrategicPlan, StrategyContext

logger = get_logger("strategic_action_engine")


# ============================================================
# Utility
# ============================================================

def _now():
    return datetime.datetime.utcnow().isoformat()


# ============================================================
# Action Data Structures
# ============================================================

@dataclass
class StrategicAction:
    action_type: str
    target: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "action_type": self.action_type,
            "target": self.target,
            "metadata": self.metadata,
            "context": self.context,
            "created_at": self.created_at,
        }


@dataclass
class ActionizationResult:
    success: bool
    actions: List[StrategicAction] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=_now)

    def as_dict(self):
        return {
            "success": self.success,
            "actions": [a.as_dict() for a in self.actions],
            "diagnostics": self.diagnostics,
            "timestamp": self.timestamp,
        }


# ============================================================
# Step Classification (STRUCTURAL HEURISTIC ONLY)
# ============================================================

def classify_step(step: str) -> str:
    """
    Structural classifier for step strings.
    Phase 40: heuristic label only; no execution meaning implied.
    """
    s = (step or "").lower()

    if "analyze" in s and "kg" in s:
        return "kg_analysis"
    if "error" in s:
        return "error_analysis"
    if "patch" in s:
        return "patch_simulation"
    if "promotion" in s:
        return "promotion_simulation"
    if "cluster" in s:
        return "cluster_analysis"
    if "autonomy" in s:
        return "autonomy_review"

    return "generic_step"


# ============================================================
# Target Extraction (DETERMINISTIC STRING RULES)
# ============================================================

def _extract_target(step: str) -> str:
    """
    Extract a target token from the step string.
    Deterministic string rules only (no inference).
    """
    step = step or ""
    s = step.lower()

    # Quoted substring for skill/cluster names
    if "'" in step:
        try:
            inner = step.split("'")[1].strip()
            if inner:
                return inner
        except Exception:
            pass

    if "cluster" in s:
        return "knowledge_cluster"
    if "autonomy" in s:
        return "autonomy_system"
    if "skill" in s:
        return "weak_skill"

    return "unknown"


# ============================================================
# Context Binding (READ-ONLY)
# ============================================================

def _bind_context_data(target: str, ctx: StrategyContext) -> Dict[str, Any]:
    """
    Attach KG/weak-skill/cluster/error/reinforcement context as read-only metadata.
    Phase 40: emits signals only; no decisions.
    """
    context_data: Dict[str, Any] = {}

    # Weak skill enrichment
    try:
        for ws in (ctx.weak_skills or []):
            if isinstance(ws, dict) and ws.get("skill") == target:
                context_data["weak_skill"] = ws
                break
    except Exception:
        pass

    # Cluster info (target as cluster name)
    try:
        if isinstance(ctx.kg_clusters, dict) and target in ctx.kg_clusters:
            context_data["cluster"] = ctx.kg_clusters.get(target)
    except Exception:
        pass

    # Error hotspots
    try:
        eh = (ctx.kg_scores or {}).get("error_hotspots", {})
        if isinstance(eh, dict) and target in eh:
            context_data["error_hotspot"] = eh.get(target)
    except Exception:
        pass

    # Reinforcement signals
    try:
        rs = (ctx.kg_scores or {}).get("reinforcement_signals", {})
        if isinstance(rs, dict) and target in rs:
            context_data["reinforcement_signal"] = rs.get(target)
    except Exception:
        pass

    # Autonomy gate snapshot (read-only)
    context_data["autonomy_status"] = ctx.autonomy_status if isinstance(ctx.autonomy_status, dict) else {}

    # Strategic priority binding (signal-only)
    priority = getattr(ctx, "strategic_priority", None)
    if isinstance(priority, str) and priority:
        context_data["priority_skill"] = priority
        # Phase 40: explicit signal rules; substring is treated as a string signal only.
        context_data["priority_alignment_signal"] = bool(
            target == priority or (isinstance(target, str) and priority in target)
        )

    # Drift placeholder (read-only stub)
    context_data["drift_context"] = {
        "placeholder": True,
        "note": "No drift computed here (read_only_stub).",
    }

    return context_data


# ============================================================
# Actionization Logic (SIGNAL-ONLY)
# ============================================================

def actionize_step(step: str, ctx: StrategyContext) -> StrategicAction:
    """
    Convert a plan step into a StrategicAction with read-only context bindings.
    Phase 40: emits structured signals; no decisions.
    """
    step = step or ""
    action_type = classify_step(step)
    target = _extract_target(step)

    context_payload = _bind_context_data(target, ctx)

    priority = getattr(ctx, "strategic_priority", None)
    priority_alignment_signal = bool(
        isinstance(priority, str)
        and priority
        and (target == priority or (isinstance(step, str) and priority in step))
    )

    metadata = {
        "original_step": step,
        "target_extracted": target,
        "action_type_label": action_type,
        "context_bound": bool(context_payload),

        # Phase 16 Step 17 (signal-only)
        "priority_skill": priority if isinstance(priority, str) else None,
        "priority_alignment_signal": priority_alignment_signal,

        # Phase 16 Step 18 (read-only placeholder)
        "drift_metadata": {
            "placeholder": True,
            "note": "Drift computed elsewhere; this file emits placeholders only.",
        },
    }

    return StrategicAction(
        action_type=action_type,
        target=target,
        metadata=metadata,
        context=context_payload,
    )


def actionize_plan(plan: StrategicPlan, ctx: StrategyContext) -> ActionizationResult:
    """
    Convert all plan steps into structured, context-enriched actions.
    Phase 40: actionization only; no execution.
    """
    try:
        steps = plan.steps or []
        actions = [actionize_step(step, ctx) for step in steps]

        return ActionizationResult(
            success=True,
            actions=actions,
            diagnostics={
                "step_count": len(steps),
                "priority_skill": getattr(ctx, "strategic_priority", None),
                "note": "Actionization completed (signal-only).",
            },
        )

    except Exception as exc:
        logger.exception("[StrategicAction] Failed to actionize plan")
        return ActionizationResult(
            success=False,
            actions=[],
            diagnostics={
                "error": repr(exc),
                "note": "Actionization failure (signal-only).",
            },
        )


__all__ = [
    "StrategicAction",
    "ActionizationResult",
    "actionize_step",
    "actionize_plan",
    "classify_step",
]
# EOF

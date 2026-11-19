# internal_tasks.py — Phase 40G Authority-Safe Diagnostics (SIGNAL-ONLY)
# -------------------------------------------------------------------
# PURPOSE:
#   Provide READ-ONLY, SIGNAL-ONLY internal diagnostics.
#
# Phase 40G Guarantees:
#   • NO interpretation
#   • NO recommendations
#   • NO task execution authority
#   • NO action routing
#   • Deterministic, auditable outputs
#
# Notes:
#   • Emits structured signals for observability only
#   • Orchestrator remains sole authority
# -------------------------------------------------------------------

import json
from datetime import datetime
from typing import Dict, Any, List

from solomon_core.memory_store import get_recent_tasks, get_recent_memory
from solomon_core.autonomy.autonomy_state import get_state
from solomon_core.reinforcement_store import get_reinforcement_snapshot
from solomon_core.knowledge.knowledge_graph import get_kg_snapshot

# -------------------------------------------------------------------
# Utility: Limit output size for logs
# -------------------------------------------------------------------
def _truncate(text: str, max_len: int = 2000) -> str:
    if text is None:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len] + "\n... [truncated] ..."

# -------------------------------------------------------------------
# Datetime conversion helper (safe for all reports)
# -------------------------------------------------------------------
def _convert_datetimes(obj):
    if isinstance(obj, dict):
        return {k: _convert_datetimes(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_convert_datetimes(x) for x in obj]
    if isinstance(obj, datetime):
        return obj.isoformat()
    return obj

# -------------------------------------------------------------------
# 1. Recent activity (SIGNALS)
# -------------------------------------------------------------------
def summarize_recent_activity(limit: int = 20) -> Dict[str, Any]:
    recent = get_recent_tasks(limit=limit)
    safe_recent = _convert_datetimes(recent)

    return {
        "available": True,
        "task_count": len(safe_recent),
        "tasks": safe_recent,
        "limit": limit,
    }

# -------------------------------------------------------------------
# 2. Reinforcement trends (SIGNALS)
# -------------------------------------------------------------------
def summarize_reinforcement_trends(limit: int = 10) -> Dict[str, Any]:
    snapshot = get_reinforcement_snapshot()
    safe_snapshot = _convert_datetimes(snapshot)

    # Apply limit locally
    keys = list(safe_snapshot.keys())[:limit] if safe_snapshot else []
    sliced_snapshot = {k: safe_snapshot[k] for k in keys}

    return {
        "available": bool(sliced_snapshot),
        "limit": limit,
        "snapshot": sliced_snapshot,
    }

# -------------------------------------------------------------------
# 3. Planner confidence (SIGNALS ONLY)
# -------------------------------------------------------------------
def summarize_planner_confidence() -> Dict[str, Any]:
    snapshot = get_reinforcement_snapshot()
    safe_snapshot = _convert_datetimes(snapshot)

    return {
        "available": snapshot is not None,
        "reinforcement_snapshot": safe_snapshot,
    }

# -------------------------------------------------------------------
# 4. Memory → KG context (SIGNALS)
# -------------------------------------------------------------------
def summarize_memory_contexts(limit: int = 15) -> Dict[str, Any]:
    mem = get_recent_memory(limit=limit)
    safe = _convert_datetimes(mem)

    return {
        "available": True,
        "limit": limit,
        "memory": safe,
    }

# -------------------------------------------------------------------
# 5. System health (SIGNALS)
# -------------------------------------------------------------------
def system_health_report() -> Dict[str, Any]:
    state = get_state()
    safe_state = _convert_datetimes(state)

    return {
        "available": True,
        "state": safe_state,
    }

# -------------------------------------------------------------------
# 6. Internal pattern metrics (SIGNALS ONLY)
# -------------------------------------------------------------------
def internal_pattern_metrics() -> Dict[str, Any]:
    state = get_state()

    total = state.get("total_cycles", 0)
    successes = state.get("success_count", 0)
    failures = state.get("failure_count", 0)
    errors = state.get("error_count", 0)

    success_rate = (successes / total) if total else None
    failure_rate = (failures / total) if total else None

    return {
        "available": True,
        "total_cycles": total,
        "successes": successes,
        "failures": failures,
        "errors": errors,
        "success_rate": success_rate,
        "failure_rate": failure_rate,
        "last_result_summary_present": bool(state.get("last_result_summary")),
        "last_reasoning_source_present": bool(state.get("last_reasoning_source")),
    }

# -------------------------------------------------------------------
# 6b. Reflect on internal patterns (SIGNALS ONLY)
# -------------------------------------------------------------------
def reflect_on_internal_patterns() -> Dict[str, Any]:
    metrics = internal_pattern_metrics()
    return {
        "available": True,
        "pattern_summary": {
            "total_cycles": metrics.get("total_cycles"),
            "success_rate": metrics.get("success_rate"),
            "failure_rate": metrics.get("failure_rate"),
            "errors": metrics.get("errors"),
        },
    }

# -------------------------------------------------------------------
# 7. Error metrics (SIGNALS)
# -------------------------------------------------------------------
def analyze_recent_errors(limit: int = 20) -> Dict[str, Any]:
    recent = get_recent_tasks(limit=limit)
    errors = [t for t in recent if t.get("error")]

    return {
        "available": True,
        "limit": limit,
        "error_count": len(errors),
        "most_recent_error_present": bool(errors),
        "most_recent_error": _truncate(str(errors[0].get("error"))) if errors else None,
    }

# -------------------------------------------------------------------
# 8. Task intent frequency (SIGNALS)
# -------------------------------------------------------------------
def analyze_task_patterns(limit: int = 15) -> Dict[str, Any]:
    recent = get_recent_tasks(limit=limit)
    intents = [t.get("intent") for t in recent if t.get("intent")]

    freq: Dict[str, int] = {}
    for i in intents:
        freq[i] = freq.get(i, 0) + 1

    return {
        "available": True,
        "limit": limit,
        "total_intents": len(intents),
        "intent_frequency": freq,
    }

# -------------------------------------------------------------------
# 9. HFLO feedback (SIGNALS)
# -------------------------------------------------------------------
def analyze_hflo_feedback(limit: int = 5) -> Dict[str, Any]:
    snapshot = get_reinforcement_snapshot()
    safe_snapshot = _convert_datetimes(snapshot)

    # Apply limit locally
    keys = list(safe_snapshot.keys())[:limit] if safe_snapshot else []
    sliced_snapshot = {k: safe_snapshot[k] for k in keys}

    return {
        "available": True,
        "limit": limit,
        "snapshot": sliced_snapshot,
    }

# -------------------------------------------------------------------
# 10. Aggregated diagnostics (SIGNALS ONLY)
# -------------------------------------------------------------------
def full_diagnostics_snapshot() -> Dict[str, Any]:
    snapshot = {
        "timestamp": datetime.utcnow().isoformat(),
        "recent_activity": summarize_recent_activity(),
        "reinforcement_trends": summarize_reinforcement_trends(),
        "planner_confidence": summarize_planner_confidence(),
        "memory_contexts": summarize_memory_contexts(),
        "system_health": system_health_report(),
        "pattern_metrics": internal_pattern_metrics(),
        "reflect_patterns": reflect_on_internal_patterns(),
        "error_metrics": analyze_recent_errors(),
        "task_patterns": analyze_task_patterns(),
        "hflo_feedback": analyze_hflo_feedback(),
    }
    snapshot["available"] = True
    return snapshot

# -------------------------------------------------------------------
# 11. Registry (SIGNAL PRODUCERS ONLY)
# -------------------------------------------------------------------
SIGNAL_PRODUCERS = {
    "recent_activity": summarize_recent_activity,
    "reinforcement_trends": summarize_reinforcement_trends,
    "planner_confidence": summarize_planner_confidence,
    "memory_contexts": summarize_memory_contexts,
    "system_health": system_health_report,
    "pattern_metrics": internal_pattern_metrics,
    "reflect_patterns": reflect_on_internal_patterns,
    "errors": analyze_recent_errors,
    "task_patterns": analyze_task_patterns,
    "hflo_feedback": analyze_hflo_feedback,
    "full_snapshot": full_diagnostics_snapshot,
}

# -------------------------------------------------------------------
# 12. Signal request entrypoint (NO EXECUTION AUTHORITY)
# -------------------------------------------------------------------
def emit_internal_signals(keys: List[str]) -> Dict[str, Any]:
    results: Dict[str, Any] = {}

    for key in keys:
        producer = SIGNAL_PRODUCERS.get(key)
        if producer:
            results[key] = producer()
        else:
            results[key] = {"available": False, "reason": "unknown_signal_key"}

    return results

# EOF

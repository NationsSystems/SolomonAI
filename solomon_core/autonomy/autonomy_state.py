# autonomy_state.py — Phase 8.2 → Phase 8.4 upgrade
# ---------------------------------------------------------
# Tracks runtime state of Solomon’s autonomous cognitive system.
#
# Phase 8.4 adds:
#   • recent_failures (list)
#   • high_error_modes (list)
#   • goal_history (sequence of past autonomous tasks)
#   • Exposure of these fields to goal_selector via get_context_bundle()
# ---------------------------------------------------------

import threading
from datetime import datetime


# ---------------------------------------------------------
# Internal shared state
# ---------------------------------------------------------
_state_lock = threading.Lock()

_autonomy_state = {
    "last_run": None,
    "total_cycles": 0,
    "success_count": 0,
    "failure_count": 0,

    "last_task": None,
    "last_intent": None,
    "last_reasoning_source": None,
    "last_result_summary": None,
    "last_success": None,

    # reinforcement snapshot from last cycle
    "reinforcement_snapshot": None,

    # errors (internal system issues)
    "error_count": 0,

    # Phase 8.4 additions
    "recent_failures": [],         # list of goal fragments that recently failed
    "high_error_modes": [],        # modes (LLM/internal/etc.) that had repeated errors
    "goal_history": [],            # ordered list of past autonomous goals
}


# ---------------------------------------------------------
# Public getters
# ---------------------------------------------------------
def get_state():
    """Return a safe, read-only copy of all autonomy state."""
    with _state_lock:
        return dict(_autonomy_state)


def get_last_run():
    with _state_lock:
        return _autonomy_state["last_run"]


# ---------------------------------------------------------
# Update functions
# ---------------------------------------------------------
def record_cycle_start(task_text: str, intent: str, reasoning_source: str):
    """Record metadata at the beginning of a cycle."""
    with _state_lock:
        _autonomy_state["last_run"] = datetime.utcnow()
        _autonomy_state["last_task"] = task_text
        _autonomy_state["last_intent"] = intent
        _autonomy_state["last_reasoning_source"] = reasoning_source
        _autonomy_state["total_cycles"] += 1

        # Phase 8.4 — track task history
        _autonomy_state["goal_history"].append(task_text)


def record_cycle_result(
    success: bool,
    summary: str = None,
    reinforcement_snapshot=None,
):
    """Record the outcome of an autonomous cognitive cycle."""
    with _state_lock:
        if success:
            _autonomy_state["success_count"] += 1
        else:
            _autonomy_state["failure_count"] += 1

            # Phase 8.4 — track failures
            last = _autonomy_state.get("last_task")
            if last:
                # Store last 10 failure fragments max
                fails = _autonomy_state["recent_failures"]
                fails.append(last.lower())
                _autonomy_state["recent_failures"] = fails[-10:]

                # Track error-prone reasoning modes
                mode = _autonomy_state.get("last_reasoning_source")
                if mode:
                    modes = _autonomy_state["high_error_modes"]
                    modes.append(mode.lower())
                    _autonomy_state["high_error_modes"] = modes[-10:]

        _autonomy_state["last_success"] = success
        _autonomy_state["last_result_summary"] = summary

        if reinforcement_snapshot is not None:
            _autonomy_state["reinforcement_snapshot"] = reinforcement_snapshot


def record_internal_error():
    """Increment internal system error count (non-fatal)."""
    with _state_lock:
        _autonomy_state["error_count"] += 1


# ---------------------------------------------------------
# Inject state into planner or LLM context
# ---------------------------------------------------------
def get_context_bundle():
    """
    Return a bundle of useful state to feed into generate_plan
    and goal_selector (Phase 8.4).
    """
    with _state_lock:
        return {
            # Legacy structured state
            "autonomy_state": {
                "total_cycles": _autonomy_state["total_cycles"],
                "success_count": _autonomy_state["success_count"],
                "failure_count": _autonomy_state["failure_count"],
                "last_task": _autonomy_state["last_task"],
                "last_intent": _autonomy_state["last_intent"],
                "last_reasoning_source": _autonomy_state["last_reasoning_source"],
                "last_result_summary": _autonomy_state["last_result_summary"],
                "last_success": _autonomy_state["last_success"],
                "reinforcement_snapshot": _autonomy_state["reinforcement_snapshot"],
                "last_run": _autonomy_state["last_run"],
                "error_count": _autonomy_state["error_count"],
            },

            # Phase 8.4 contextual intelligence
            "recent_failures": list(_autonomy_state["recent_failures"]),
            "high_error_modes": list(_autonomy_state["high_error_modes"]),
            "goal_history": list(_autonomy_state["goal_history"]),
            "last_task": _autonomy_state["last_task"],
        }


# ---------------------------------------------------------
# Reset autonomy state
# ---------------------------------------------------------
def reset_state():
    """Reset autonomy runtime values (debug/admin)."""
    with _state_lock:
        # Reset primitives to None
        for key in [
            "last_run",
            "last_task",
            "last_intent",
            "last_reasoning_source",
            "last_result_summary",
            "last_success",
            "reinforcement_snapshot",
        ]:
            _autonomy_state[key] = None

        # Reset counters
        _autonomy_state["total_cycles"] = 0
        _autonomy_state["success_count"] = 0
        _autonomy_state["failure_count"] = 0
        _autonomy_state["error_count"] = 0

        # Reset lists (must NOT be set to None)
        _autonomy_state["goal_history"] = []
        _autonomy_state["recent_failures"] = []
        _autonomy_state["high_error_modes"] = []

# goal_selector.py — Phase 40 Authority-Safe Internal Goal Signals
# ---------------------------------------------------------------------------
# PURPOSE (Phase 40):
#   Emit internal goal OPTIONS only.
#   No selection, no outcome collapse, no human-language authority.
#
#   Orchestrator is the sole decision-maker.
# ---------------------------------------------------------------------------

from solomon_core.autonomy.autonomy_state import get_state


# ---------------------------------------------------------------------------
# Curated fallback goal CODES (STRUCTURAL)
# ---------------------------------------------------------------------------
FALLBACK_GOAL_CODES = [
    {"code": "ANALYZE_TASK_HISTORY"},
    {"code": "REVIEW_MEMORY_PATTERNS"},
    {"code": "EVALUATE_SYSTEM_STABILITY"},
    {"code": "SUMMARIZE_REINFORCEMENT_TRENDS"},
    {"code": "RUN_SELF_DIAGNOSTIC"},
]


# ---------------------------------------------------------------------------
# Reinforcement-driven goal signal
# ---------------------------------------------------------------------------
def _trend_based_goal_signal():
    from solomon_core.reinforcement_store import summarize_reinforcement

    snapshot = summarize_reinforcement(limit=10)
    if not snapshot:
        return None

    best_entry = max(snapshot, key=lambda e: e.get("weight", 0))
    intent = best_entry.get("intent")
    source = best_entry.get("reasoning_source")

    if not intent:
        return None

    return {
        "code": "REFINE_INTENT",
        "metadata": {
            "intent": intent,
            "source": source,
        },
        "origin": "reinforcement",
    }


# ---------------------------------------------------------------------------
# Failure-avoidance signal (NO DECISION)
# ---------------------------------------------------------------------------
def _failure_avoidance_signal(goal_signal):
    if not goal_signal:
        return None

    state = get_state()
    last_success = state.get("last_success")
    last_task = state.get("last_task")

    if not last_success and last_task:
        return {
            **goal_signal,
            "blocked_by_recent_failure": True,
        }

    return goal_signal


# ---------------------------------------------------------------------------
# Fallback goal signals
# ---------------------------------------------------------------------------
def _fallback_goal_signals():
    state = get_state()
    last_task = state.get("last_task")
    last_success = state.get("last_success")

    options = []
    for entry in FALLBACK_GOAL_CODES:
        blocked = False
        if last_task and last_success is False:
            blocked = True
        options.append(
            {
                "code": entry["code"],
                "blocked_by_recent_failure": blocked,
                "origin": "fallback",
            }
        )
    return options


# ---------------------------------------------------------------------------
# Public API — SIGNAL ONLY
# ---------------------------------------------------------------------------
def collect_internal_goal_options(context_bundle: dict):
    """
    Phase 40:
      Emits internal goal options with evidence and block signals.
      No goal selection.
    """

    if context_bundle is None:
        context_bundle = {}

    recent_failures = context_bundle.get("recent_failures", [])
    high_error_modes = context_bundle.get("high_error_modes", [])

    options = []

    adaptive = _trend_based_goal_signal()
    adaptive = _failure_avoidance_signal(adaptive)

    if adaptive:
        blocked = False
        text = str(adaptive.get("metadata", "")).lower()
        if any(frag in text for frag in recent_failures):
            blocked = True
        if any(frag in text for frag in high_error_modes):
            blocked = True

        adaptive["blocked_by_context"] = blocked
        options.append(adaptive)

    options.extend(_fallback_goal_signals())

    return {
        "signal_code": "GOAL_OPTIONS",
        "options": options,
    }


# EOF

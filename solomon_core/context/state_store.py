# ------------------------------------------------------------------
# FILE: solomon_core/context/state_store.py
# DIRECTORY: solomon_core/context/
# ------------------------------------------------------------------

from datetime import datetime

# NOTE:
# This is a deterministic, authoritative state layer.
# It is NOT memory, NOT ECB, NOT context reconstruction.
# It is the single source of truth for Orchestrator state.

# Replace this with real DB connection (MySQL, etc.)
# This version is a minimal deterministic stub.

_STATE_DB = {}


# ============================================================
# READ — Authoritative State (REQUIRED BEFORE ORCHESTRATION)
# ============================================================
def read_state(conversation_id: str) -> dict:
    try:
        state = _STATE_DB.get(conversation_id)

        if not isinstance(state, dict):
            return {
                "current_subject": None,
                "last_resolved_query": None,
                "last_answer": None,
                "state_version": 0,
            }

        return state

    except Exception:
        return {
            "current_subject": None,
            "last_resolved_query": None,
            "last_answer": None,
            "state_version": 0,
        }


# ============================================================
# WRITE — Authoritative State (REQUIRED AFTER RESPONSE)
# ============================================================
def write_state(conversation_id: str, new_state: dict) -> bool:
    try:
        if not isinstance(new_state, dict):
            return False

        # Enforce deterministic structure
        state = {
            "current_subject": new_state.get("current_subject"),
            "last_resolved_query": new_state.get("last_resolved_query"),
            "last_answer": new_state.get("last_answer"),
            "state_version": int(new_state.get("state_version", 0)),
            "updated_at": datetime.utcnow().isoformat(),
        }

        _STATE_DB[conversation_id] = state
        return True

    except Exception:
        return False


# ============================================================
# ACCESSORS — STRICT, READ-ONLY (NO MUTATION, NO LOGIC)
# ============================================================
def get_last_answer(conversation_id: str) -> str | None:
    state = read_state(conversation_id)
    return state.get("last_answer")


def get_current_subject(conversation_id: str) -> str | None:
    state = read_state(conversation_id)
    return state.get("current_subject")


def get_last_resolved_query(conversation_id: str) -> str | None:
    state = read_state(conversation_id)
    return state.get("last_resolved_query")
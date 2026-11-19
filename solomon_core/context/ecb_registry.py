# solomon_core/context/ecb_registry.py
# ---------------------------------------------------------------------------
# Ephemeral Context Buffer (ECB) Registry — Phase 60
# ---------------------------------------------------------------------------
# PURPOSE:
#   • Maintain short-lived conversational context
#   • Explicitly non-authoritative
#   • RAM-resident only (volatility is a feature)
#
# GUARANTEES:
#   • No implicit memory
#   • TTL-bound
#   • Size-bounded
#   • Explicitly auditable
#
# ECB PRINCIPLE:
#   "Solomon remembers exactly what you ask it to — and nothing else."
# ---------------------------------------------------------------------------

import time
import threading
from collections import deque
from typing import Deque, Dict, List, Optional

# ---------------------------------------------------------------------------
# Configuration (Phase 60 defaults — conservative)
# ---------------------------------------------------------------------------
ECB_TTL_SECONDS = 300          # 5 minutes
ECB_MAX_TURNS = 32             # last 16 complete exchanges
ECB_MAX_CONVERSATIONS = 500    # hard cap safety valve

# ---------------------------------------------------------------------------
# Internal Storage (INTENTIONALLY PRIVATE)
# ---------------------------------------------------------------------------
_lock = threading.Lock()


class ECBEntry:
    __slots__ = ("conversation_id", "created_at", "last_access", "turns")

    def __init__(self, conversation_id: str):
        now = time.time()
        self.conversation_id: str = conversation_id
        self.created_at: float = now
        self.last_access: float = now
        self.turns: Deque[dict] = deque(maxlen=ECB_MAX_TURNS)


_ecb_store: Dict[str, ECBEntry] = {}


# ---------------------------------------------------------------------------
# Lifecycle Management (PRIVATE)
# ---------------------------------------------------------------------------
def _prune_expired_locked():
    now = time.time()
    expired = [
        cid for cid, entry in _ecb_store.items()
        if (now - entry.last_access) > ECB_TTL_SECONDS
    ]
    for cid in expired:
        _ecb_store.pop(cid, None)


def _enforce_capacity_locked():
    if len(_ecb_store) <= ECB_MAX_CONVERSATIONS:
        return

    # Remove least-recently-used conversations
    ordered = sorted(
        _ecb_store.values(),
        key=lambda e: e.last_access
    )
    while len(ordered) > ECB_MAX_CONVERSATIONS:
        victim = ordered.pop(0)
        _ecb_store.pop(victim.conversation_id, None)


# ---------------------------------------------------------------------------
# Public Runtime API
# ---------------------------------------------------------------------------
def get_context(conversation_id: str) -> List[dict]:
    """
    Retrieve ECB context for a conversation.
    Returns a COPY — callers cannot mutate internal state.
    """
    with _lock:
        _prune_expired_locked()

        entry = _ecb_store.get(conversation_id)
        if not entry:
            return []

        entry.last_access = time.time()
        return list(entry.turns)


def append_turn(
    conversation_id: str,
    *,
    role: str,
    content: str,
    metadata: Optional[dict] = None
):
    """
    Append a conversational turn.
    This is an explicit act — nothing is automatic.
    """
    with _lock:
        _prune_expired_locked()
        _enforce_capacity_locked()

        entry = _ecb_store.get(conversation_id)
        if not entry:
            entry = ECBEntry(conversation_id)
            _ecb_store[conversation_id] = entry

        entry.last_access = time.time()
        entry.turns.append({
            "role": role,
            "content": content,
            "meta": metadata or {},
            "ts": entry.last_access
        })


def clear_conversation(conversation_id: str):
    """
    Explicit destruction of ECB context.
    """
    with _lock:
        _ecb_store.pop(conversation_id, None)


# ---------------------------------------------------------------------------
# Diagnostic / Operator Visibility (SAFE, NON-AUTHORITATIVE)
# ---------------------------------------------------------------------------
def ecb_health_probe() -> dict:
    """
    Diagnostic-safe ECB presence & liveliness probe.

    RULES:
      • NO content exposure
      • NO turn inspection
      • NO private symbol access
      • Read-only
      • Advisory only

    Used by:
      • context_ecb_probe
      • pre-phase health checks
      • tooling recognition
    """
    with _lock:
        _prune_expired_locked()
        return {
            "present": True,
            "active_conversations": len(_ecb_store),
            "ttl_seconds": ECB_TTL_SECONDS,
            "max_turns": ECB_MAX_TURNS,
            "max_conversations": ECB_MAX_CONVERSATIONS,
        }


def snapshot_registry() -> dict:
    """
    Operator / audit visibility.
    NO content inspection — counts and timing only.
    """
    with _lock:
        _prune_expired_locked()
        return {
            "active_conversations": len(_ecb_store),
            "ttl_seconds": ECB_TTL_SECONDS,
            "max_turns": ECB_MAX_TURNS,
            "max_conversations": ECB_MAX_CONVERSATIONS,
            "conversations": {
                cid: {
                    "turn_count": len(entry.turns),
                    "age_seconds": time.time() - entry.created_at,
                    "idle_seconds": time.time() - entry.last_access,
                }
                for cid, entry in _ecb_store.items()
            },
        }
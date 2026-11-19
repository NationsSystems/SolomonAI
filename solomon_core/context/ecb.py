# solomon_core/context/ecb.py
# ---------------------------------------------------------------------------
# Ephemeral Context Buffer (ECB)
# Phase 60 — Volatile State Memory
# ---------------------------------------------------------------------------
# DESIGN GOALS:
#   • RAM-only (no persistence)
#   • TTL-bounded
#   • Explicit opt-in per conversation
#   • Deterministic eviction
#   • Zero hidden accumulation
#
# CORE PRINCIPLE:
#   "Solomon remembers exactly what you ask it to — and nothing else."
# ---------------------------------------------------------------------------

import time
import threading
from typing import Dict, List, Optional


class ECBEntry:
    """
    Single ECB record.
    """
    __slots__ = ("content", "timestamp")

    def __init__(self, content: str):
        self.content = content
        self.timestamp = time.time()


class EphemeralContextBuffer:
    """
    In-memory, TTL-bound conversation context buffer.
    """

    def __init__(self, ttl_seconds: int = 300, max_entries: int = 20):
        self.ttl_seconds = ttl_seconds
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._store: Dict[str, List[ECBEntry]] = {}

    # ------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------

    def add(self, conversation_id: str, content: str) -> None:
        """
        Add context to a conversation buffer.
        """
        with self._lock:
            self._evict_expired_locked(conversation_id)

            entries = self._store.setdefault(conversation_id, [])
            entries.append(ECBEntry(content))

            # Hard cap (FIFO)
            if len(entries) > self.max_entries:
                self._store[conversation_id] = entries[-self.max_entries :]

    def get_context(self, conversation_id: str) -> List[str]:
        """
        Retrieve valid context for a conversation.
        """
        with self._lock:
            self._evict_expired_locked(conversation_id)
            return [e.content for e in self._store.get(conversation_id, [])]

    def clear(self, conversation_id: str) -> None:
        """
        Explicitly clear ECB for a conversation.
        """
        with self._lock:
            self._store.pop(conversation_id, None)

    def stats(self) -> Dict[str, int]:
        """
        Diagnostics-only visibility.
        """
        with self._lock:
            return {
                "active_conversations": len(self._store),
                "total_entries": sum(len(v) for v in self._store.values()),
            }

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    def _evict_expired_locked(self, conversation_id: Optional[str] = None) -> None:
        """
        Evict expired entries deterministically.
        """
        now = time.time()

        def _filter(entries: List[ECBEntry]) -> List[ECBEntry]:
            return [
                e for e in entries
                if (now - e.timestamp) <= self.ttl_seconds
            ]

        if conversation_id:
            if conversation_id in self._store:
                filtered = _filter(self._store[conversation_id])
                if filtered:
                    self._store[conversation_id] = filtered
                else:
                    self._store.pop(conversation_id, None)
        else:
            # Global sweep (rare / diagnostic)
            for cid in list(self._store.keys()):
                filtered = _filter(self._store[cid])
                if filtered:
                    self._store[cid] = filtered
                else:
                    self._store.pop(cid, None)


# ------------------------------------------------------------
# Singleton (authoritative ECB instance)
# ------------------------------------------------------------
ECB = EphemeralContextBuffer()

# solomon_core/diagnostics/ecb_diagnostics.py
# ---------------------------------------------------------------------------
# Phase 60 — ECB Diagnostics (OPERATOR-ONLY)
# ---------------------------------------------------------------------------
# PURPOSE:
#   Provide safe, non-invasive visibility into the Ephemeral Context Buffer.
#
# GUARANTEES:
#   • RAM-only inspection
#   • No mutation unless explicitly requested
#   • No payload/content leakage
#   • No persistence
#
# SCOPE:
#   • Active conversation count
#   • Per-conversation turn depth
#   • TTL remaining
#   • Eviction verification
#
# ACCESS:
#   Operator / diagnostic tooling only
# ---------------------------------------------------------------------------

import time
from typing import Dict, Any

from solomon_core.solomon_core import _ECB_STORE, ECB_TTL_SECONDS
from solomon_core.logger import get_logger

logger = get_logger("ecb_diagnostics")


def snapshot_ecb_state() -> Dict[str, Any]:
    """
    Returns a snapshot of ECB metadata.
    NO message content is exposed.
    """
    now = time.time()

    conversations = []
    expired = []

    for cid, entry in list(_ECB_STORE.items()):
        age = now - entry.get("last_seen", now)
        remaining = max(0, ECB_TTL_SECONDS - age)

        meta = {
            "conversation_id": cid,
            "turn_count": len(entry.get("turns", [])) // 2,
            "seconds_since_last_seen": int(age),
            "ttl_remaining_seconds": int(remaining),
        }

        if age > ECB_TTL_SECONDS:
            expired.append(meta)
        else:
            conversations.append(meta)

    return {
        "ecb_active": True,
        "total_conversations": len(conversations),
        "expired_conversations": len(expired),
        "conversations": conversations,
    }


def evict_expired_conversations() -> int:
    """
    Force-evict expired ECB entries.
    Safe to call repeatedly.
    """
    now = time.time()
    evicted = 0

    for cid, entry in list(_ECB_STORE.items()):
        if now - entry.get("last_seen", now) > ECB_TTL_SECONDS:
            _ECB_STORE.pop(cid, None)
            evicted += 1

    if evicted:
        logger.info(
            "ECB eviction sweep completed",
            extra={"evicted": evicted},
        )

    return evicted

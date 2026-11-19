# solomon_core/context_processors.py
# ---------------------------------------------------------------
# Global context processors (read-only, non-authoritative)
#
# Injects:
#   • hflo_pending_count — number of pending HFLO upgrade items
#   • network_context   — Phase 68 network context (optional)
# ---------------------------------------------------------------

from flask import session
from solomon_core.db import SessionLocal
from solomon_core.models import HfloPendingUpgrade


def inject_hflo_pending_count():
    db = SessionLocal()
    try:
        count = (
            db.query(HfloPendingUpgrade)
            .filter(HfloPendingUpgrade.reviewed == False)
            .count()
        )
        return {"hflo_pending_count": count}
    except Exception:
        return {"hflo_pending_count": 0}
    finally:
        db.close()


def inject_network_context():
    """
    Phase 68: Expose non-authoritative network context as read-only.
    Context may be absent; no assumptions are made.
    """
    ctx = session.get("network_context")
    return {"network_context": ctx} if ctx else {}

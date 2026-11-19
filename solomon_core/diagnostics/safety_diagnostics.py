# solomon_core/diagnostics/safety_diagnostics.py
# ------------------------------------------------------------------
# Phase 46 — Tier-3 Safety Diagnostics (SIGNAL-ONLY)
# Phase 47.4 — Planner & Drift Signal Cleanup (Safety Alignment)
#
# PURPOSE (Tier-3):
#   Expose raw safety- and error-related diagnostics for
#   observability and presentation layers.
#
# PHASE 47.4 CHANGES:
#   • Align structural probes with packet-router reality
#   • Remove misleading “missing structure” implications
#   • Clarify that safety signals are observational only
#
# GUARANTEES:
#   • READ-ONLY
#   • SIGNAL-ONLY (no interpretation, no conclusions)
#   • No recommendations or framing
#   • No exceptions propagated upward
# ------------------------------------------------------------------

import importlib.util

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal

logger = get_logger("diagnostics.safety")


# -----------------------------------------------------------
# Structural awareness helpers (READ-ONLY)
# -----------------------------------------------------------

def _module_exists(module_path: str) -> bool:
    """Check whether a module exists without importing it."""
    try:
        spec = importlib.util.find_spec(module_path)
        return spec is not None
    except Exception:
        return False


def _check_packet_router_present():
    """
    Detect orchestrator / packet router presence (STRUCTURAL).

    NOTE (Phase 47.4):
        Confirms packet-router architecture is present.
        Absence would indicate installation corruption.
    """
    return _module_exists("solomon_core.solomon_core")


def _check_packet_header_defined():
    """
    Detect PacketHeader schema definition (STRUCTURAL).

    NOTE (Phase 47.4):
        Indicates schema availability, not runtime emission.
    """
    return _module_exists("solomon_core.packets.packet_header")


def _check_docintel_available():
    """
    Detect DocIntel semantic skill domain presence (STRUCTURAL).

    NOTE:
        Presence indicates capability availability, not usage.
    """
    return _module_exists("solomon_core.skills.semantic")


# -----------------------------------------------------------
# Tier-3 safety diagnostics entrypoint (SIGNAL-ONLY)
# -----------------------------------------------------------

def run():
    try:
        session = SessionLocal()

        # Query recent error sentinel data (RAW)
        try:
            rows = session.execute(
                """
                SELECT error_message, occurrences, created_at
                FROM error_sentinel
                ORDER BY occurrences DESC
                LIMIT 10
                """
            ).fetchall()
        except Exception:
            # Table may not exist yet or schema may differ — fail gracefully
            rows = []

        session.close()

        # Convert SQLAlchemy row objects → dicts (RAW)
        error_list = []
        for r in rows:
            try:
                error_list.append({
                    "error_message": r[0],
                    "occurrences": r[1],
                    "created_at": str(r[2]),
                })
            except Exception:
                continue

        signals = {
            # ---------------------------------
            # Raw error signals
            # ---------------------------------
            "errors": error_list,
            "error_count": len(error_list),

            # ---------------------------------
            # Auto-repair placeholders (RAW)
            # ---------------------------------
            "auto_repair_last_run": None,
            "auto_repair_success": None,

            # ---------------------------------
            # Structural awareness (POST-PACKET)
            # ---------------------------------
            "packet_router_present": _check_packet_router_present(),
            "packet_header_defined": _check_packet_header_defined(),
            "docintel_available": _check_docintel_available(),

            # ---------------------------------
            # Diagnostic posture (EXPLICIT)
            # ---------------------------------
            "enforcement_enabled": False,   # diagnostics are observational only
            "auto_repair_enabled": False,   # no execution authority here
        }

        return {
            "ok": True,
            "signals": signals,
        }

    except Exception as e:
        logger.exception("Safety diagnostics failure")
        return {
            "ok": False,
            "signals": {},
            "error": str(e),
        }

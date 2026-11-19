# solomon_core/investigator/human_review_port.py
# ---------------------------------------------------------------------------
# Human Review Port (Minimal Authority Socket)
#
# Purpose:
#   Provide a runtime-callable boundary where a human can:
#       • observe ONE conflict
#       • enter a resolution
#       • persist precedent
#
# This module is intentionally tiny.
#
# It does NOT:
#   • rank
#   • recommend
#   • filter
#   • batch
#   • interpret
#   • alter reconciliation
#
# Think: kernel syscall for human authority.
# ---------------------------------------------------------------------------

from datetime import datetime
from typing import Any, Iterable

from solomon_core.logger import get_logger
from .precedent_recorder import record_precedent

logger = get_logger("human_review_port")


# ---------------------------------------------------------------------------

def _normalize_conflicts(container: Any) -> Iterable:
    """
    Accepts list OR ConflictSet.
    Returns iterable.
    """
    if hasattr(container, "conflicts"):
        return container.conflicts
    return container


# ---------------------------------------------------------------------------

def review_single_conflict(artifact: dict):
    """
    Present exactly one conflict to a human.

    If none exist → exit cleanly.
    """

    conflicts = _normalize_conflicts(artifact.get("conflicts", []))

    if not conflicts:
        print("\nNo conflicts detected. Nothing for reviewer.\n")
        return

    conflict = list(conflicts)[0]

    fingerprint = getattr(conflict, "fingerprint", None)
    if isinstance(conflict, dict):
        fingerprint = conflict.get("fingerprint")

    print("\n================ HUMAN REVIEW REQUIRED =================")
    print(f"Fingerprint: {fingerprint}")

    if isinstance(conflict, dict):
        print("Signal Type:", conflict.get("signal_type"))
        print("Values:", conflict.get("values"))
        print("Documents:", conflict.get("documents"))
    else:
        print("Signal Type:", getattr(conflict, "signal_type", None))
        print("Values:", getattr(conflict, "values", None))
        print("Documents:", getattr(conflict, "documents", None))

    print("========================================================\n")

    choice = input("Enter resolution label (free text): ").strip()

    if not choice:
        print("No input received. Skipping record.\n")
        return

    case_id = f"cli_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    authority_actor = "cli_user"

    logger.info(
        "[REVIEW_PORT] recording fingerprint=%s case=%s",
        fingerprint,
        case_id,
    )

    record_precedent(
        fingerprint=fingerprint,
        resolution=choice,
        case_id=case_id,
        authority_actor=authority_actor,
    )

    print("Done.\n")

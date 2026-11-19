# solomon_core/docintel/reconciliation/conflict_prioritizer.py
# ---------------------------------------------------------------------------
# Conflict Prioritizer
#
# Purpose:
#   Provide deterministic ordering of reconciliation buckets so
#   professional reviewers see the most critical multiplicity first.
#
# Authority:
#   • DOES NOT modify facts
#   • DOES NOT resolve conflicts
#   • DOES NOT infer correctness
#
# This is a presentation / workflow accelerator only.
# ---------------------------------------------------------------------------

from typing import Dict, Any, List

from solomon_core.logger import get_logger

logger = get_logger("conflict_prioritizer")


# ---------------------------------------------------------------------------

PRIORITY_ORDER = [
    # money & schedule first
    "base_bid_amount",
    "bid_date",
    "schedule_or_duration_terms",

    # contractual risk
    "exclusions",
    "inclusions",
    "special_conditions_or_risks",

    # informational
    "issuing_party",
]


# ---------------------------------------------------------------------------

def _priority_index(signal_type: str) -> int:
    if signal_type in PRIORITY_ORDER:
        return PRIORITY_ORDER.index(signal_type)
    return len(PRIORITY_ORDER)


# ---------------------------------------------------------------------------

def prioritize(reconciliation_artifact: Dict[str, Any]) -> Dict[str, Any]:
    buckets = reconciliation_artifact.get("buckets") or []

    ordered = sorted(
        buckets,
        key=lambda b: (
            _priority_index(b.get("signal_type")),
            not b.get("conflict", False),
            not b.get("multiplicity", False),
            b.get("signal_type") or "",
        ),
    )

    logger.info(
        "[PRIORITIZER] buckets=%s",
        len(ordered),
    )

    return {
        "bucket_count": len(ordered),
        "buckets": ordered,
    }

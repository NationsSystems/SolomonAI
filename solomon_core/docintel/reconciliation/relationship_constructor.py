# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/relationship_constructor.py
#
# PURPOSE:
# Deterministically construct structural relationships among Tier-1 signals.
#
# AUTHORITY:
# Non-decisional. Non-mutating.
#
# PHASE-75 GUARANTEES:
# • No inference
# • No priority
# • No override
# • Fully rebuildable
# ---------------------------------------------------------------------------

from typing import List, Dict, Iterable

from .relationship_models import (
    Relationship,
    RelationshipSet,
    RELATIONSHIP_CO_REFERENCE,
)
from .deterministic_ids import build_relationship_id


# ---------------------------------------------------------------------------
# Expected Tier-1 signal contract (minimum required fields)
# ---------------------------------------------------------------------------
REQUIRED_KEYS = [
    "signal_id",
    "signal_type",
    "value",
]


# ---------------------------------------------------------------------------
# Relationship Constructor
# ---------------------------------------------------------------------------

def build_relationships(signals: Iterable[Dict]) -> RelationshipSet:
    """
    Create mechanical co-reference relationships.

    Current Phase-75 implementation:
        Signals sharing the same signal_type are grouped.
    """

    # validate minimum shape
    for s in signals:
        for k in REQUIRED_KEYS:
            if k not in s:
                raise ValueError(f"Tier-1 signal missing required key: {k}")

    groups: Dict[str, List[str]] = {}

    for s in signals:
        groups.setdefault(s["signal_type"], []).append(s["signal_id"])

    relationships: List[Relationship] = []

    for signal_type, member_ids in groups.items():
        if len(member_ids) < 2:
            continue  # no relationship needed

        basis = "shared_signal_type"

        relationship_id = build_relationship_id(
            RELATIONSHIP_CO_REFERENCE,
            member_ids,
            basis,
        )

        relationships.append(
            Relationship(
                relationship_id=relationship_id,
                relationship_type=RELATIONSHIP_CO_REFERENCE,
                members=sorted(member_ids),
                basis=basis,
                metadata={"signal_type": signal_type},
            )
        )

    return RelationshipSet(relationships=relationships)

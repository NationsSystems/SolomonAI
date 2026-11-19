# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/conflict_detector.py
#
# PURPOSE:
# Detect observable disagreements within relationships.
#
# AUTHORITY:
# Non-decisional.
# Never selects a winner.
#
# PHASE-75 GUARANTEES:
# • Derived strictly from Tier-1
# • Fully traceable
# • Rebuildable
# ---------------------------------------------------------------------------

from typing import Dict, Iterable, List

from .relationship_models import RelationshipSet
from .conflict_models import (
    Conflict,
    ConflictSet,
    CONFLICT_VALUE_DISAGREEMENT,
)
from .deterministic_ids import build_conflict_id


# ---------------------------------------------------------------------------
# Conflict Detector
# ---------------------------------------------------------------------------

def detect_conflicts(
    relationships: RelationshipSet,
    signals_by_id: Dict[str, Dict],
) -> ConflictSet:
    """
    Detect value disagreement among members of a relationship.
    """

    conflicts: List[Conflict] = []

    for r in relationships.relationships:
        values = {}

        for sid in r.members:
            signal = signals_by_id.get(sid)
            if not signal:
                continue
            values.setdefault(str(signal.get("value")), []).append(sid)

        if len(values.keys()) <= 1:
            continue  # agreement

        basis = "value_mismatch"

        conflict_id = build_conflict_id(
            r.relationship_id,
            r.members,
            basis,
        )

        conflicts.append(
            Conflict(
                conflict_id=conflict_id,
                relationship_id=r.relationship_id,
                members=sorted(r.members),
                basis=basis,
                metadata={"distinct_values": len(values)},
            )
        )

    return ConflictSet(conflicts=conflicts)

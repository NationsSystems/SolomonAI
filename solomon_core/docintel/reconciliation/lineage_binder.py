# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/lineage_binder.py
#
# PURPOSE:
# Guarantee that every relationship and conflict remains traceable
# back to Tier-1 signals.
#
# AUTHORITY:
# Verification only.
# Rejects objects that cannot prove lineage.
#
# PHASE-75 GUARANTEES:
# • No orphan structures
# • Auditor reconstructability
# ---------------------------------------------------------------------------

from typing import Dict

from .relationship_models import RelationshipSet
from .conflict_models import ConflictSet


# ---------------------------------------------------------------------------
# Lineage Verification
# ---------------------------------------------------------------------------

def verify_relationship_lineage(
    relationships: RelationshipSet,
    signals_by_id: Dict[str, Dict],
) -> None:
    """
    Raises if any relationship references unknown Tier-1 signal.
    """
    for r in relationships.relationships:
        for sid in r.members:
            if sid not in signals_by_id:
                raise ValueError(
                    f"Relationship {r.relationship_id} references unknown signal {sid}"
                )


def verify_conflict_lineage(
    conflicts: ConflictSet,
    signals_by_id: Dict[str, Dict],
) -> None:
    """
    Raises if any conflict references unknown Tier-1 signal.
    """
    for c in conflicts.conflicts:
        for sid in c.members:
            if sid not in signals_by_id:
                raise ValueError(
                    f"Conflict {c.conflict_id} references unknown signal {sid}"
                )

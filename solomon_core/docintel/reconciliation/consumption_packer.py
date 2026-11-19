# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/consumption_packer.py
#
# PURPOSE:
# Convert reconciliation artifacts into serialization-safe,
# presentation-neutral formats.
#
# AUTHORITY:
# None. Packaging only.
#
# PHASE-75 GUARANTEES:
# • No suppression
# • No prioritization
# • No mutation
# ---------------------------------------------------------------------------

from typing import Dict, Any


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pack_relationship(r) -> Dict[str, Any]:
    return {
        "relationship_id": r.relationship_id,
        "relationship_type": r.relationship_type,
        "members": list(r.members),
        "basis": r.basis,
        "metadata": dict(r.metadata),
    }


def pack_conflict(c) -> Dict[str, Any]:
    return {
        "conflict_id": c.conflict_id,
        "relationship_id": c.relationship_id,
        "members": list(c.members),
        "basis": c.basis,
        "metadata": dict(c.metadata),
    }


# ---------------------------------------------------------------------------
# Public
# ---------------------------------------------------------------------------

def pack_output(result: Dict) -> Dict:
    return {
        "relationships": [
            pack_relationship(r) for r in result["relationships"].relationships
        ],
        "conflicts": [
            pack_conflict(c) for c in result["conflicts"].conflicts
        ],
    }

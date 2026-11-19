# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/conflict_models.py
#
# PURPOSE:
# Deterministic containers describing observable tension between
# related Tier-1 signals.
#
# AUTHORITY:
# Non-decisional. Non-mutating.
# Conflicts expose differences but never resolve them.
#
# PHASE-75 GUARANTEES:
# • Built only from relationships
# • Fully traceable
# • No precedence
# • No correction
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Conflict Types
# ---------------------------------------------------------------------------

CONFLICT_VALUE_DISAGREEMENT = "value_disagreement"
CONFLICT_PRESENCE_MISMATCH = "presence_mismatch"
CONFLICT_STRUCTURAL_INCONSISTENCY = "structural_inconsistency"


# ---------------------------------------------------------------------------
# Core Conflict Object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Conflict:
    """
    Represents an unresolved structural issue among related Tier-1 signals.

    This object never:
        • declares which signal is correct
        • removes alternatives
        • assigns priority
    """

    conflict_id: str
    relationship_id: str

    # Tier-1 members participating in the conflict
    members: List[str]

    # mechanical basis for detection
    basis: str

    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper container
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ConflictSet:
    conflicts: List[Conflict]

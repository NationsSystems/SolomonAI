# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/relationship_models.py
#
# PURPOSE:
# Deterministic containers describing lawful structural relationships
# between Tier-1 signals.
#
# AUTHORITY:
# Non-decisional. Non-mutating.
# These models never imply correctness, priority, or override.
#
# PHASE-75 GUARANTEES:
# • Rebuildable from Tier-1
# • Fully traceable
# • No inference
# • No winner selection
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import List, Dict, Any


# ---------------------------------------------------------------------------
# Relationship Types (expandable only via charter revision)
# ---------------------------------------------------------------------------

RELATIONSHIP_CO_REFERENCE = "co_reference"
RELATIONSHIP_VALUE_VARIATION = "value_variation"
RELATIONSHIP_STRUCTURAL_ASSOCIATION = "structural_association"
RELATIONSHIP_POTENTIAL_DEPENDENCY = "potential_dependency"


# ---------------------------------------------------------------------------
# Core Relationship Object
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Relationship:
    """
    Represents a deterministic structural link between Tier-1 signals.

    This object never:
        • selects a winner
        • modifies a value
        • implies authority
    """

    relationship_id: str
    relationship_type: str

    # Tier-1 signal ids participating in the relationship
    members: List[str]

    # mechanical reason relationship exists
    basis: str

    # reproducibility metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helper container for grouping
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RelationshipSet:
    relationships: List[Relationship]

# solomon_core/docintel/reconciliation/reconciliation_engine.py
# ---------------------------------------------------------------------------
# Deterministic Reconciliation Engine — Left/Right Removed
#
# Purpose:
#   • Organize Tier-1 BEI facts across documents
#   • Detect multiplicity and surface disagreements
#   • Provide a stable structure for Tier-3 certification
#
# Non-Authority:
#   • Does NOT choose winners
#   • Does NOT modify Tier-1 values
#   • Does NOT infer equivalence
#
# Output:
#   JSON-serializable reconciliation artifact
# ---------------------------------------------------------------------------

from typing import Dict, List, Any

from solomon_core.logger import get_logger
from .bei_fact import BEIFact, BEIFactSet

logger = get_logger("reconciliation_engine")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ReconciliationBucket:
    """
    Holds all facts of the same signal_type.
    Deterministic — no left/right, no user input required.
    """

    def __init__(self, signal_type: str):
        self.signal_type = signal_type
        self.facts: List[BEIFact] = []

    def add(self, fact: BEIFact):
        self.facts.append(fact)

    # -----------------------------------------------------------
    # Structural views (NO interpretation)
    # -----------------------------------------------------------

    def is_conflict(self) -> bool:
        # Conflict purely based on differing fact values
        values = {str(f.value) for f in self.facts}
        return len(values) > 1

    def is_multiplicity(self) -> bool:
        # Multiplicity purely based on number of facts
        return len(self.facts) > 1

    def serialize(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "multiplicity": self.is_multiplicity(),
            "conflict": self.is_conflict(),
            "facts": [f.to_dict() for f in self.facts],
        }


# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------

class ReconciliationEngine:
    """
    Deterministic grouping + exposure.
    No left/right decisions anywhere.
    """

    def __init__(self):
        self.buckets: Dict[str, ReconciliationBucket] = {}

    # -----------------------------------------------------------

    def ingest(self, fact_set: BEIFactSet):
        for fact in fact_set.all():
            bucket = self.buckets.setdefault(
                fact.fact_type,
                ReconciliationBucket(fact.fact_type),
            )
            bucket.add(fact)

    # -----------------------------------------------------------

    def serialize(self) -> Dict[str, Any]:
        ordered = sorted(self.buckets.values(), key=lambda b: b.signal_type)

        return {
            "bucket_count": len(ordered),
            "buckets": [b.serialize() for b in ordered],
        }


# ---------------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------------

def reconcile(fact_sets: List[BEIFactSet]) -> Dict[str, Any]:
    engine = ReconciliationEngine()

    for fs in fact_sets:
        engine.ingest(fs)

    result = engine.serialize()

    logger.info(
        "[RECONCILIATION] buckets=%s",
        result["bucket_count"],
    )

    return result

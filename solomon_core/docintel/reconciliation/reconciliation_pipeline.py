# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/reconciliation_pipeline.py
#
# PURPOSE:
# Execute deterministic structural construction.
#
# ORDER:
# Tier-1 →
#   relationships →
#   compatibility →
#   conflicts →
#   lineage verification
#
# AUTHORITY:
# No decisions.
# Pure construction.
#
# GUARANTEES:
# • Rebuildable
# • Deterministic
# • Traceable
# ---------------------------------------------------------------------------

from typing import Iterable, Dict

from .relationship_constructor import build_relationships
from .conflict_detector import detect_conflicts
from .lineage_binder import (
    verify_relationship_lineage,
    verify_conflict_lineage,
)


# ---------------------------------------------------------------------------
# Compatibility Classifier
# ---------------------------------------------------------------------------

def _classify_compatibility(left: Dict, right: Dict) -> str:
    """
    Determine if two signals are compatible.

    v1 law:
    - Same fact_type AND same value → compatible
    - Same fact_type AND different value → incompatible
    - Otherwise → unknown

    No mutation.
    No inference.
    Pure comparison.
    """

    if left.get("fact_type") != right.get("fact_type"):
        return "unknown"

    if left.get("value") == right.get("value"):
        return "compatible"

    return "incompatible"


def _attach_compatibility(relationships, signals_by_id):
    """
    Enrich relationships with compatibility metadata.
    """
    enriched = []

    for rel in relationships:
        left = signals_by_id.get(rel.get("left_signal_id"))
        right = signals_by_id.get(rel.get("right_signal_id"))

        if left and right:
            rel = dict(rel)
            rel["compatibility"] = _classify_compatibility(left, right)

        enriched.append(rel)

    return enriched


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_reconciliation(signals: Iterable[Dict]) -> Dict:
    """
    Entry point for structural build.
    """

    signals = list(signals)

    signals_by_id = {s["signal_id"]: s for s in signals}

    relationships = build_relationships(signals)

    # 🔹 Sub-Phase-2 Entry: semantic relationship tagging
    relationships = _attach_compatibility(relationships, signals_by_id)

    conflicts = detect_conflicts(relationships, signals_by_id)

    verify_relationship_lineage(relationships, signals_by_id)
    verify_conflict_lineage(conflicts, signals_by_id)

    return {
        "relationships": relationships,
        "conflicts": conflicts,
    }

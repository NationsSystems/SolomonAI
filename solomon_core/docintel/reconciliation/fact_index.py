# solomon_core/docintel/reconciliation/fact_index.py
# ---------------------------------------------------------------------------
# Fact Index — Deterministic Access Layer
#
# Purpose:
#   Provide stable, queryable views over collections of BEIFacts
#   without altering, interpreting, or adjudicating them.
#
# Authority:
#   • READ ONLY
#   • NO mutation
#   • NO inference
#   • NO conflict resolution
#
# Phase Position:
#   Tier-2 structural organization layer.
# ---------------------------------------------------------------------------

from typing import Dict, List, Iterable, Set
from collections import defaultdict

from .bei_fact import BEIFact, BEIFactSet


# ============================================================================
# Fact Index
# ============================================================================

class FactIndex:
    """
    Deterministic multi-view index of BEIFacts.

    Guarantees:
      • reproducible ordering
      • stable access patterns
      • zero interpretation
    """

    # ------------------------------------------------------------------
    def __init__(self, fact_sets: Iterable[BEIFactSet]):
        self._all_facts: List[BEIFact] = []
        self._by_signal: Dict[str, List[BEIFact]] = defaultdict(list)
        self._by_document: Dict[str, List[BEIFact]] = defaultdict(list)

        for fs in fact_sets:
            for fact in fs.all():
                self._all_facts.append(fact)

                self._by_signal[fact.fact_type].append(fact)

                doc_id = fact.source_document_id or "unknown"
                self._by_document[doc_id].append(fact)

        # stable ordering for determinism
        self._all_facts = list(self._all_facts)
        for k in list(self._by_signal.keys()):
            self._by_signal[k] = list(self._by_signal[k])
        for k in list(self._by_document.keys()):
            self._by_document[k] = list(self._by_document[k])

    # ------------------------------------------------------------------
    # Global Views
    # ------------------------------------------------------------------

    def all(self) -> List[BEIFact]:
        return list(self._all_facts)

    def signals(self) -> List[str]:
        return sorted(self._by_signal.keys())

    def documents(self) -> List[str]:
        return sorted(self._by_document.keys())

    # ------------------------------------------------------------------
    # Signal Views
    # ------------------------------------------------------------------

    def by_signal(self, signal_type: str) -> List[BEIFact]:
        return list(self._by_signal.get(signal_type, []))

    # ------------------------------------------------------------------
    # Document Views
    # ------------------------------------------------------------------

    def by_document(self, document_id: str) -> List[BEIFact]:
        return list(self._by_document.get(document_id, []))

    # ------------------------------------------------------------------
    # Structural Helpers
    # ------------------------------------------------------------------

    def signal_present(self, signal_type: str) -> bool:
        return signal_type in self._by_signal

    def document_has_signal(self, document_id: str, signal_type: str) -> bool:
        return any(
            f.fact_type == signal_type
            for f in self._by_document.get(document_id, [])
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, object]:
        return {
            "total_facts": len(self._all_facts),
            "signals": self.signals(),
            "documents": self.documents(),
        }

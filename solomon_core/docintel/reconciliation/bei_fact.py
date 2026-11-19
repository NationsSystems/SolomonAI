# solomon_core/docintel/reconciliation/bei_fact.py
# ---------------------------------------------------------------------------
# BEI Fact Model — Canonical Reconciliation Currency
# ---------------------------------------------------------------------------
#
# Purpose:
#   Provide a deterministic, uniform representation for facts emitted by
#   Tier-1 extraction so higher tiers can perform lawful comparison,
#   propagation, and certification without modifying the original evidence.
#
# Authority:
#   • Representation layer only
#   • No inference
#   • No mutation of Tier-1 values
#   • Purely structural normalization
#
# Phase Position:
#   Post-extraction, pre-reconciliation logic.
#
# Design Law:
#   If a value did not originate from Tier-1, it cannot appear here.
# ---------------------------------------------------------------------------

from dataclasses import dataclass, asdict
from typing import Any, Dict, Iterable, List, Optional
import hashlib
import json
import re


# ============================================================================
# Deterministic Identity
# ============================================================================

def _stable_hash(payload: Dict[str, Any]) -> str:
    """
    Produce deterministic fingerprint for a fact.
    Same inputs → same ID forever.
    """
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


# ============================================================================
# Atomic Fact
# ============================================================================

@dataclass(frozen=True)
class BEIFact:
    """
    The smallest portable unit of bid intelligence.

    Immutable.
    JSON serializable.
    Traceable to a source artifact.
    """

    fact_id: str
    fact_type: str
    value: Any
    source_document_id: Optional[str]
    source_display_name: Optional[str]
    extraction_method: str = "explicit"
    provenance: Optional[Dict[str, Any]] = None  # ⭐ NEW

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ============================================================================
# Fact Collection
# ============================================================================

class BEIFactSet:
    """
    Deterministic container of BEIFacts.
    Prevents duplicate identity insertion.
    """

    def __init__(self, facts: Optional[Iterable[BEIFact]] = None):
        self._facts: List[BEIFact] = []
        self._seen_ids = set()

        if facts:
            self.extend(facts)

    def add(self, fact: BEIFact) -> None:
        if fact.fact_id in self._seen_ids:
            return
        self._seen_ids.add(fact.fact_id)
        self._facts.append(fact)

    def extend(self, facts: Iterable[BEIFact]) -> None:
        for f in facts:
            self.add(f)

    def all(self) -> List[BEIFact]:
        return list(self._facts)

    def by_type(self, fact_type: str) -> List[BEIFact]:
        return [f for f in self._facts if f.fact_type == fact_type]

    def to_dict(self) -> List[Dict[str, Any]]:
        return [f.to_dict() for f in self._facts]


# ============================================================================
# Admission Filter (Conservative v1)
# ============================================================================

_FURNITURE_PATTERNS = [
    r"^section\s+\d",
    r"^article\s+\d",
    r"^page\s+\d",
    r"^end of",
]


def _admit_value(value: Any) -> bool:
    """
    Ultra-conservative hygiene gate.

    Rejects only material with near-zero probability of being
    legitimate professional evidence.
    """

    if value is None:
        return False

    text = str(value).strip()

    # Empty
    if not text:
        return False

    # No alphanumeric content
    if not any(c.isalnum() for c in text):
        return False

    # Broken currency
    if "$" in text and sum(c.isdigit() for c in text) == 0:
        return False

    # Strong furniture patterns
    lowered = text.lower()
    for pat in _FURNITURE_PATTERNS:
        if re.match(pat, lowered):
            return False

    return True


# ============================================================================
# Deterministic Conversion Helpers
# ============================================================================

def _build_fact(
    *,
    fact_type: str,
    value: Any,
    document_id: Optional[str],
    display_name: Optional[str],
    provenance: Optional[Dict[str, Any]] = None,
) -> BEIFact:
    identity_payload = {
        "fact_type": fact_type,
        "value": value,
        "source_document_id": document_id,
    }

    return BEIFact(
        fact_id=_stable_hash(identity_payload),
        fact_type=fact_type,
        value=value,
        source_document_id=document_id,
        source_display_name=display_name,
        provenance=provenance,
    )


def facts_from_tier1_evidence(
    *,
    evidence: Dict[str, Any],
    document_id: Optional[str],
    display_name: Optional[str],
) -> BEIFactSet:
    """
    Mechanical transformation from Tier-1 evidence dictionary
    into a BEIFactSet.

    NEW CANONICAL RULE:
      If Tier-1 declared the vocabulary (value_type / section_type),
      we MUST use it.

    No interpretation.
    No renaming.
    """

    fact_set = BEIFactSet()

    if not isinstance(evidence, dict):
        return fact_set

    for field, value in evidence.items():
        if value is None:
            continue

        # ------------------------------------------------------------------
        # LIST → attempt structured signal mapping
        # ------------------------------------------------------------------
        if isinstance(value, list):
            for item in value:
                if item is None:
                    continue

                # Admission check
                if not _admit_value(item):
                    continue

                if isinstance(item, dict):

                    # VALUE signals
                    if "value_type" in item:
                        fact_set.add(
                            _build_fact(
                                fact_type=item["value_type"],
                                value=item.get("raw_value"),
                                document_id=document_id,
                                display_name=display_name,
                                provenance=item,
                            )
                        )
                        continue

                    # SECTION signals
                    if "section_type" in item:
                        fact_set.add(
                            _build_fact(
                                fact_type=item["section_type"],
                                value=item,
                                document_id=document_id,
                                display_name=display_name,
                                provenance=item,
                            )
                        )
                        continue

                # Fallback → preserve raw under original field
                fact_set.add(
                    _build_fact(
                        fact_type=field,
                        value=item,
                        document_id=document_id,
                        display_name=display_name,
                        provenance=None,
                    )
                )

            continue

        # ------------------------------------------------------------------
        # SCALAR / DICT → single fact
        # ------------------------------------------------------------------

        if not _admit_value(value):
            continue

        fact_set.add(
            _build_fact(
                fact_type=field,
                value=value,
                document_id=document_id,
                display_name=display_name,
                provenance=None,
            )
        )

    return fact_set

# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/fact_models.py
#
# PURPOSE:
# Canonical atomic currency used for reconciliation.
#
# These objects:
#   • do NOT infer
#   • do NOT merge
#   • do NOT evaluate
#
# They are structural containers only.
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from typing import List


# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BEIFact:
    """
    Immutable Tier-1 fact.

    Represents exactly one observed signal.
    """

    signal_type: str
    value: str
    source_doc: str
    section_header: str
    ordinal_position: int
    raw_text: str


# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BEIFactSet:
    """
    All facts belonging to a document.
    """

    document_id: str
    facts: List[BEIFact]

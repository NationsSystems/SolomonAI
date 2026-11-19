# solomon_core/docintel/reconciliation/conflict_reporter.py
# ---------------------------------------------------------------------------
# Conflict & Multiplicity Reporter
#
# Purpose:
#   Present reconciliation structure in a professional review format.
#
# Authority:
#   • READ ONLY
#   • DOES NOT select winners
#   • DOES NOT alter facts
#
# Phase Position:
#   Tier-3 professional visibility layer.
# ---------------------------------------------------------------------------

from typing import Dict, Any, List

from .fact_index import FactIndex
from .bei_fact import BEIFactSet


# ============================================================================
# Reporter
# ============================================================================

def build_conflict_report(fact_sets: List[BEIFactSet]) -> Dict[str, Any]:
    index = FactIndex(fact_sets)

    signals = index.signals()
    report = []

    for signal in signals:
        facts = index.by_signal(signal)

        values = sorted({str(f.value) for f in facts})
        documents = sorted({f.source_document_id for f in facts if f.source_document_id})

        report.append(
            {
                "signal_type": signal,
                "document_count": len(documents),
                "value_count": len(values),
                "multiplicity": len(facts) > 1,
                "conflict": len(values) > 1,
                "values": values,
                "documents": documents,
            }
        )

    return {
        "signal_count": len(report),
        "signals": report,
    }

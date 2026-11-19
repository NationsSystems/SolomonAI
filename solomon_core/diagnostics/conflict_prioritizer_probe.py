# solomon_core/diagnostics/conflict_prioritizer_probe.py
# ---------------------------------------------------------------------------
# Conflict Prioritizer CLI Probe
#
# Purpose:
#   Deterministically show how reconciliation buckets are ordered
#   for professional review.
#
# Authority:
#   None. Read-only pipeline visibility.
# ---------------------------------------------------------------------------

import json
from pathlib import Path

from solomon_core.logger import get_logger
from solomon_core.docintel.reconciliation.bei_fact import (
    BEIFact,
    BEIFactSet,
)
from solomon_core.docintel.reconciliation.reconciliation_engine import (
    reconcile,
)
from solomon_core.docintel.reconciliation.conflict_prioritizer import (
    prioritize,
)

logger = get_logger("conflict_prioritizer_probe")


DEFAULT_INPUT = Path("tests/tier1_output.json")


# ---------------------------------------------------------------------------

def _load_fact_sets(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Tier-1 input not found: {path}")

    data = json.loads(path.read_text())

    fact_sets = []

    for doc in data.get("documents", []):
        fact_set = BEIFactSet()

        for item in doc.get("facts", []):
            fact_set.add(
                BEIFact(
                    fact_type=item.get("signal_type"),
                    value=item.get("value"),
                    source_document_id=item.get("source_doc"),
                    source_display_name=doc.get("document_id"),
                )
            )

        fact_sets.append(fact_set)

    return fact_sets


# ---------------------------------------------------------------------------

def run(path: Path = DEFAULT_INPUT):
    logger.info("[PROBE] loading Tier-1 data from %s", path)

    fact_sets = _load_fact_sets(path)

    logger.info("[PROBE] reconciling")
    artifact = reconcile(fact_sets)

    logger.info("[PROBE] prioritizing")
    prioritized = prioritize(artifact)

    print("\n================ PRIORITIZED REVIEW ORDER ================")
    print(json.dumps(prioritized, indent=2))
    print("=========================================================\n")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()

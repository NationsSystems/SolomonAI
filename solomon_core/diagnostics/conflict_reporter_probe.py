# solomon_core/diagnostics/conflict_reporter_probe.py
# ---------------------------------------------------------------------------
# Conflict Reporter CLI Probe
#
# Purpose:
#   Tier-3 visibility of:
#       • multiplicity
#       • conflicts
#       • per-signal distribution
#
# This is NOT authority.
# This is NOT decision making.
# ---------------------------------------------------------------------------

import json
from pathlib import Path

from solomon_core.logger import get_logger
from solomon_core.docintel.reconciliation.bei_fact import (
    BEIFact,
    BEIFactSet,
)
from solomon_core.docintel.reconciliation.conflict_reporter import (
    build_conflict_report,
)

logger = get_logger("conflict_reporter_probe")


DEFAULT_INPUT = Path("tests/tier1_output.json")


# ---------------------------------------------------------------------------

def _load_fact_sets(path: Path):
    if not path.exists():
        raise FileNotFoundError(f"Tier-1 input not found: {path}")

    data = json.loads(path.read_text())

    fact_sets = []

    for doc in data.get("documents", []):
        fs = BEIFactSet()

        for item in doc.get("facts", []):
            fs.add(
                BEIFact(
                    fact_type=item.get("fact_type"),
                    value=item.get("value"),
                    source_document_id=item.get("source_document_id"),
                    source_display_name=item.get("source_display_name"),
                )
            )

        fact_sets.append(fs)

    return fact_sets


# ---------------------------------------------------------------------------

def run(path: Path = DEFAULT_INPUT):
    logger.info("[PROBE] loading Tier-1 facts from %s", path)

    fact_sets = _load_fact_sets(path)

    logger.info("[PROBE] building conflict report")
    report = build_conflict_report(fact_sets)

    print("\n================ CONFLICT REPORT ================")
    print(json.dumps(report, indent=2))
    print("=================================================\n")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()

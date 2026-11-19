# ---------------------------------------------------------------------------
# FILE: solomon_core/diagnostics/human_review_smoke.py
#
# PURPOSE:
# Deterministic smoke test for the human authority boundary.
#
# Guarantees:
#   If a conflict exists and we record a resolution,
#   that resolution MUST be readable from the database.
#
# Non-authority:
#   This simulates plumbing, not human judgment.
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from datetime import datetime

from solomon_core.logger import get_logger
from solomon_core.docintel.reconciliation.bei_fact import (
    BEIFact,
    BEIFactSet,
)
from solomon_core.docintel.reconciliation.reconciliation_engine import (
    reconcile,
)
from solomon_core.investigator.precedent_recorder import record_precedent
from solomon_core.investigator.precedent_lookup import lookup_precedents

logger = get_logger("human_review_smoke")


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

def _extract_first_conflict(artifact):
    buckets = artifact.get("buckets", [])

    for b in buckets:
        if not b.get("conflict"):
            continue

        values = sorted({str(f.get("value")) for f in b.get("facts", [])})
        fingerprint = f"{b.get('signal_type')}|{len(values)}"

        return fingerprint

    return None


# ---------------------------------------------------------------------------

def run(path: Path = DEFAULT_INPUT):
    logger.info("[SMOKE] loading Tier-1 data from %s", path)

    fact_sets = _load_fact_sets(path)

    logger.info("[SMOKE] running reconciliation")
    artifact = reconcile(fact_sets)

    fingerprint = _extract_first_conflict(artifact)

    if not fingerprint:
        print("\nSMOKE TEST SKIPPED — no conflict present.\n")
        return

    case_id = f"smoke_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    resolution = "SMOKE_TEST"
    authority_actor = "smoke_runner"

    print(f"\nRecording smoke precedent for: {fingerprint}")

    record_precedent(
        fingerprint=fingerprint,
        resolution=resolution,
        case_id=case_id,
        authority_actor=authority_actor,
    )

    print("Verifying persistence...")

    rows = lookup_precedents(fingerprint)

    for r in rows:
        if r.get("case_id") == case_id:
            print("\n✅ SMOKE TEST PASSED\n")
            return

    print("\n❌ SMOKE TEST FAILED — record not found\n")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()

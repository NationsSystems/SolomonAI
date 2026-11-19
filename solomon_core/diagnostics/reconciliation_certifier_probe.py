# solomon_core/diagnostics/reconciliation_certifier_probe.py
# ---------------------------------------------------------------------------
# Reconciliation + Certification CLI Probe
#
# Purpose:
#   Deterministically exercise:
#       Tier-1 facts → reconciliation → certification
#
# Extended:
#   Minimal Reviewer Harness v1
#       → present ONE conflict
#       → capture human decision
#       → write precedent
#
# This is NOT business logic.
# This is observability infrastructure.
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
from solomon_core.docintel.reconciliation.reconciliation_certifier import (
    certify,
)

from solomon_core.investigator.precedent_recorder import record_precedent

logger = get_logger("reconciliation_certifier_probe")


# ---------------------------------------------------------------------------

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
            # ✅ UPDATED — match canonical BEIFact shape
            fact_set.add(
                BEIFact(
                    fact_id=item.get("fact_id"),
                    fact_type=item.get("fact_type"),
                    value=item.get("value"),
                    source_document_id=item.get("source_document_id"),
                    source_display_name=item.get("source_display_name"),
                )
            )

        fact_sets.append(fact_set)

    return fact_sets


# ---------------------------------------------------------------------------
# bucket-driven conflict extraction
# ---------------------------------------------------------------------------

def _extract_conflicts(artifact):
    buckets = artifact.get("buckets", [])
    conflicts = []

    for b in buckets:
        if not b.get("conflict"):
            continue

        values = sorted({str(f.get("value")) for f in b.get("facts", [])})
        documents = sorted({f.get("source_document_id") for f in b.get("facts", [])})

        fingerprint = f"{b.get('signal_type')}|{len(values)}"

        conflicts.append(
            {
                "fingerprint": fingerprint,
                "signal_type": b.get("signal_type"),
                "values": values,
                "documents": documents,
            }
        )

    return conflicts


def _present_single_conflict(artifact):
    conflicts = _extract_conflicts(artifact)

    if not conflicts:
        print("\nNo conflicts detected. Nothing for reviewer.\n")
        return

    conflict = conflicts[0]
    fingerprint = conflict.get("fingerprint")

    print("\n================ HUMAN REVIEW REQUIRED =================")
    print(f"Fingerprint: {fingerprint}")
    print("Signal Type:", conflict.get("signal_type"))
    print("Values:", conflict.get("values"))
    print("Documents:", conflict.get("documents"))
    print("========================================================\n")

    choice = input("Enter resolution label (free text): ").strip()

    if not choice:
        print("No input received. Skipping record.\n")
        return

    case_id = f"cli_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
    authority_actor = "cli_user"

    print("\nRecording precedent...")
    record_precedent(
        fingerprint=fingerprint,
        resolution=choice,
        case_id=case_id,
        authority_actor=authority_actor,
    )
    print("Done.\n")


# ---------------------------------------------------------------------------

def run(path: Path = DEFAULT_INPUT):
    logger.info("[PROBE] loading Tier-1 data from %s", path)

    fact_sets = _load_fact_sets(path)

    logger.info("[PROBE] reconciling %s documents", len(fact_sets))
    artifact = reconcile(fact_sets)

    logger.info("[PROBE] running certifier")
    result = certify(artifact)

    print("\n================ RECONCILIATION CERTIFICATION ================")
    print(json.dumps(result, indent=2))
    print("==============================================================\n")

    # ---- Human Authority Attachment ----
    _present_single_conflict(artifact)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()

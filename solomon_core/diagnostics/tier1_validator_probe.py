# solomon_core/diagnostics/tier1_validator_probe.py
# ---------------------------------------------------------------------------
# Tier-1 Validator Probe
# ---------------------------------------------------------------------------
#
# Purpose:
#   Bulk validate Tier-1 extraction packets before reconciliation.
#
# This is NOT business logic.
# This is admissibility infrastructure.
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from typing import List, Dict, Any

from solomon_core.logger import get_logger
from solomon_core.docintel.validation.tier1_output_validator import validate

logger = get_logger("tier1_validator_probe")


# ---------------------------------------------------------------------------

DEFAULT_INPUT = Path("tests/tier1_output.json")


# ---------------------------------------------------------------------------

def _load_packets(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"Tier-1 input not found: {path}")

    data = json.loads(path.read_text())

    packets = []
    for doc in data.get("documents", []):
        packets.append(doc.get("packet"))

    return packets


# ---------------------------------------------------------------------------

def run(path: Path = DEFAULT_INPUT):
    logger.info("[PROBE] loading Tier-1 packets from %s", path)

    packets = _load_packets(path)

    total = len(packets)
    failed = 0
    results = []

    for i, packet in enumerate(packets, start=1):
        result = validate(packet)

        if not result["passed"]:
            failed += 1
            results.append(
                {
                    "index": i,
                    "failures": result["failures"],
                }
            )

    passed = failed == 0

    print("\n================ TIER-1 ADMISSIBILITY ================")
    print(f"documents: {total}")
    print(f"failed: {failed}")
    print(f"passed: {passed}")

    if results:
        print("\nFailure details:")
        print(json.dumps(results, indent=2))

    print("======================================================\n")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()

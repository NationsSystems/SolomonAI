# solomon_core/diagnostics/tier1_fact_validator_probe.py
# ---------------------------------------------------------------------------
# Tier-1 Fact Validator Probe
# ---------------------------------------------------------------------------

import json
from pathlib import Path

from solomon_core.logger import get_logger
from solomon_core.diagnostics.tier1_fact_validator import validate

logger = get_logger("tier1_fact_validator_probe")


DEFAULT_INPUT = Path("tests/tier1_output.json")


# ---------------------------------------------------------------------------

def run(path: Path = DEFAULT_INPUT):
    logger.info("[PROBE] loading Tier-1 facts from %s", path)

    if not path.exists():
        raise FileNotFoundError(f"Input not found: {path}")

    dataset = json.loads(path.read_text())

    result = validate(dataset)

    print("\n================ FACT ADMISSIBILITY ================")
    print(json.dumps(result, indent=2))
    print("====================================================\n")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()

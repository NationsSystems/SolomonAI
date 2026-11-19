# ---------------------------------------------------------------------------
# Precedent Lookup Probe#
# solomon_core/diagnostics/precedent_lookup_probe.py
# ---------------------------------------------------------------------------

from solomon_core.investigator.precedent_lookup import lookup_precedents
import json


def run():
    results = lookup_precedents("TEST::fingerprint")

    print("\n================ PRECEDENT LOOKUP ================")
    print(json.dumps(results, indent=2, default=str))
    print("=================================================\n")


if __name__ == "__main__":
    run()

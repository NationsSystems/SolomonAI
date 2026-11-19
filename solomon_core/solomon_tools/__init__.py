# -------------------------------------------------------------------
# FILE: __init__.py
# DIRECTORY: solomon_core/solomon_tools/
# -------------------------------------------------------------------
# Package initialization for Solomon tool and maintenance utilities.
# -------------------------------------------------------------------

import os
import sys

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
        "..",
    )
)

if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from . import fileops

__all__ = [
    "fileops",
]


def main():
    """Run Solomon's self-repair cycle from the command line."""

    from solomon_core.solomon_tools import self_repair

    results = self_repair.run_self_repair()

    print("\n=== Solomon Self-Repair Report ===")
    print(f"Status: {results.get('status', 'unknown')}")
    print(f"Timestamp: {results.get('timestamp')}")
    print("\nDatabase:", results.get("database"))
    print("\nMemory:", results.get("memory"))
    print("\nLogs:", results.get("logs"))
    print("\nReport saved to data/logs/self_repair_report.json")


if __name__ == "__main__":
    main()
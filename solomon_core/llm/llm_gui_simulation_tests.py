# solomon_core/llm/llm_gui_simulation_tests.py
# ---------------------------------------------------------------------------
# Phase 43 — GUI Simulation Tests (LLM Execution Validation)
# ---------------------------------------------------------------------------
# PURPOSE:
#   Provide deterministic, repeatable simulations that demonstrate:
#   • Deterministic-first behavior
#   • Governed LLM fallback usage
#   • Graceful handling of unpredictable queries
#
# NOTES:
#   • This file does NOT alter system behavior
#   • This file does NOT introduce authority
#   • This file mirrors GUI execution paths
# ---------------------------------------------------------------------------

import sys
import os

# ---------------------------------------------------------------------------
# Ensure project root is on PYTHONPATH (safe, local-only)
# ---------------------------------------------------------------------------
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from solomon_core.solomon_core import execute_task
from solomon_core.logger import get_logger

logger = get_logger("llm_gui_simulation_tests")


# ===========================================================================
# Test Cases (Canonical Phase-43 Acceptance Set)
# ===========================================================================

TEST_CASES = [
    {
        "name": "Deterministic factual query",
        "input": "What city is the Texas state capitol in?",
        "expected_path": "factual_handler",
    },
    {
        "name": "General explanatory query (LLM fallback)",
        "input": "Explain what a lien waiver is.",
        "expected_path": "llm_fallback",
    },
    {
        "name": "Random philosophical query (LLM fallback)",
        "input": "Why do people say time is money?",
        "expected_path": "llm_fallback",
    },
    {
        "name": "Adversarial but benign query",
        "input": "What should I invest in right now?",
        "expected_path": "llm_fallback",
    },
]


# ===========================================================================
# Runner
# ===========================================================================

def run_gui_simulation_tests():
    logger.info("=== Phase 43 GUI Simulation Tests START ===")

    for idx, test in enumerate(TEST_CASES, start=1):
        logger.info(f"[TEST {idx}] {test['name']}")
        logger.info(f"User Input: {test['input']}")

        response = execute_task(test["input"])

        user_output = response.get("user_output")
        orch_state = response.get("orchestrator_state")

        logger.info(
            "[RESULT]",
            extra={
                "orchestrator_state": orch_state,
                "response_mode": response.get("response_mode"),
                "user_output_preview": str(user_output)[:120],
            },
        )

        print("\n-------------------------------")
        print(f"TEST: {test['name']}")
        print(f"INPUT: {test['input']}")
        print(f"STATE: {orch_state}")
        print(f"OUTPUT:\n{user_output}")
        print("-------------------------------\n")

    logger.info("=== Phase 43 GUI Simulation Tests END ===")


# ===========================================================================
# CLI Entry
# ===========================================================================

if __name__ == "__main__":
    run_gui_simulation_tests()

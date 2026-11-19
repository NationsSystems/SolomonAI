# auto_adjust.py — Phase 7 Step 7.7
# --------------------------------------------------------------------
# Solomon Autonomous Adjustment Loop
#
# Purpose:
#   Dynamically adjusts internal reasoning weights based on recent
#   task performance metrics. Uses evaluator + DB statistics to
#   bias toward the most successful reasoning paths (deterministic,
#   semantic, or llm) and saves to data/memory/weights.json.
#
#   This forms the foundation of Solomon's self-improvement cycle.
# --------------------------------------------------------------------

import os
import json
import math
from datetime import datetime
from solomon_core.solomon_tools import evaluator
from solomon_core.memory_store import log_memory_entry
from solomon_core.logger import get_logger

logger = get_logger("auto_adjust")

# --------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MEMORY_DIR = os.path.join(BASE_DIR, "data", "memory")
os.makedirs(MEMORY_DIR, exist_ok=True)

WEIGHTS_FILE = os.path.join(MEMORY_DIR, "weights.json")

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def _load_weights():
    """Load existing weights from file or set defaults."""
    default = {"deterministic": 0.6, "semantic": 0.3, "llm": 0.1}
    if not os.path.exists(WEIGHTS_FILE):
        return default
    try:
        with open(WEIGHTS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {**default, **data}
    except Exception as e:
        logger.error(f"Error loading weights: {e}")
    return default


def _save_weights(weights: dict):
    """Safely save normalized weights to disk."""
    try:
        with open(WEIGHTS_FILE, "w", encoding="utf-8") as f:
            json.dump(weights, f, indent=2)
        logger.info(f"Updated reasoning weights saved → {WEIGHTS_FILE}")
    except Exception as e:
        logger.error(f"Error saving weights: {e}")


def _normalize(weights: dict):
    """Ensure weights sum to 1.0."""
    total = sum(weights.values())
    if total == 0:
        return weights
    return {k: round(v / total, 3) for k, v in weights.items()}


def _adjust_value(old_value, delta):
    """Apply delta adjustment with clamping."""
    new_val = old_value + delta
    return max(0.05, min(0.9, new_val))


# --------------------------------------------------------------------
# Core Adjustment Logic
# --------------------------------------------------------------------
def run_adjustment_cycle():
    """
    Perform one autonomous recalibration pass.
    - Reads evaluator performance data
    - Adjusts mode weights accordingly
    - Persists new configuration
    """
    try:
        stats = evaluator.summarize_performance()
        weights = _load_weights()

        if not stats or stats.get("total", 0) == 0:
            logger.info("No performance data available for adjustment.")
            return {"ok": False, "reason": "insufficient data"}

        success_rates = {
            "deterministic": stats.get("deterministic", 0) / max(stats["total"], 1),
            "semantic": stats.get("semantic", 0) / max(stats["total"], 1),
            "llm": stats.get("llm", 0) / max(stats["total"], 1),
        }

        # Expected baseline = current weights
        new_weights = {}
        for mode, old_w in weights.items():
            rate = success_rates.get(mode, 0)
            delta = 0.2 * (rate - old_w)  # adaptive gain factor
            new_weights[mode] = _adjust_value(old_w, delta)

        new_weights = _normalize(new_weights)
        _save_weights(new_weights)

        summary = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "old_weights": weights,
            "new_weights": new_weights,
            "success_rates": success_rates,
            "total_tasks": stats["total"],
        }

        log_memory_entry("auto_adjust", json.dumps(summary))
        logger.info(f"Auto-adjustment complete: {summary}")

        return {"ok": True, "updated": new_weights}

    except Exception as e:
        logger.exception(f"Adjustment cycle failed: {e}")
        return {"ok": False, "error": str(e)}


# --------------------------------------------------------------------
# CLI Entry Point
# --------------------------------------------------------------------
if __name__ == "__main__":
    print("Running Solomon Autonomous Adjustment Loop...")
    result = run_adjustment_cycle()
    print(json.dumps(result, indent=2))

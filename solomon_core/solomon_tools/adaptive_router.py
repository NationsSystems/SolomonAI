# adaptive_router.py — Phase 7 · Step 7.6b
# -------------------------------------------------------------------
# Solomon Adaptive Routing Brainstem
# Learns routing bias dynamically from reinforcement patterns
# and exports bias + weight data for the metrics dashboard.

import os
import sys
import json
import statistics
from datetime import datetime

# --- Fix import path for standalone execution ---
CURRENT_DIR = os.path.dirname(__file__)
PARENT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, ".."))
ROOT_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    # Normal import when executed as part of the Solomon package
    from ..logger import get_logger
except ImportError:
    # Fallback for direct script execution
    from solomon_core.logger import get_logger

logger = get_logger("adaptive_router")

# ------------------------------------------------------------
# Data store location
# ------------------------------------------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "data"))
ADAPTIVE_FILE = os.path.join(BASE_DIR, "adaptive_bias.json")
WEIGHT_HISTORY_FILE = os.path.join(BASE_DIR, "adaptive_weights_history.json")
os.makedirs(BASE_DIR, exist_ok=True)

# Bias structure: {mode: {"bias": float, "updated": timestamp}}
_bias_cache = {
    "deterministic": {"bias": 0.0, "updated": None},
    "semantic": {"bias": 0.0, "updated": None},
    "llm": {"bias": 0.0, "updated": None},
}

# ------------------------------------------------------------
# Helper: load / save bias cache
# ------------------------------------------------------------
def _save_bias():
    try:
        with open(ADAPTIVE_FILE, "w", encoding="utf-8") as f:
            json.dump(_bias_cache, f, indent=2)
        logger.info(f"[AdaptiveRouter] Saved bias data → {ADAPTIVE_FILE}")
    except Exception as e:
        logger.error(f"[AdaptiveRouter] Failed to save bias: {e}")

def _load_bias():
    global _bias_cache
    if os.path.exists(ADAPTIVE_FILE):
        try:
            with open(ADAPTIVE_FILE, "r", encoding="utf-8") as f:
                _bias_cache.update(json.load(f))
            logger.debug("[AdaptiveRouter] Loaded previous bias state")
        except Exception as e:
            logger.warning(f"[AdaptiveRouter] Could not load bias file: {e}")

# ------------------------------------------------------------
# Weight history helpers
# ------------------------------------------------------------
def _load_weight_history():
    """Load historical reasoning weight evolution."""
    if not os.path.exists(WEIGHT_HISTORY_FILE):
        return []
    try:
        with open(WEIGHT_HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def _save_weight_history(history):
    try:
        with open(WEIGHT_HISTORY_FILE, "w", encoding="utf-8") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logger.error(f"[AdaptiveRouter] Failed to save weight history: {e}")

def _append_weight_history(new_weights):
    """Append a timestamped weight snapshot."""
    history = _load_weight_history()
    history.append({
        "timestamp": datetime.utcnow().isoformat(),
        "new_weights": new_weights
    })
    _save_weight_history(history)

# ------------------------------------------------------------
# Core function: update adaptive bias from reinforcement data
# ------------------------------------------------------------
def update_bias_from_reinforcement():
    """Analyze reinforcement history and update adaptive bias."""
    global _bias_cache
    try:
        # 🔁 Deferred import to avoid circular dependency
        try:
            from ..reinforcement_store import get_all_reinforcement
        except ImportError:
            from solomon_core.reinforcement_store import get_all_reinforcement

        records = get_all_reinforcement()
        mode_scores = {"deterministic": [], "semantic": [], "llm": []}

        for rec in records:
            mode = rec.get("reasoning_source")
            weight = rec.get("success_weight", 0)
            if mode in mode_scores:
                mode_scores[mode].append(weight)

        for mode in mode_scores:
            avg_weight = statistics.mean(mode_scores[mode]) if mode_scores[mode] else 0.0
            # Normalize to a -0.5 → +0.5 range
            bias_val = max(-0.5, min(0.5, avg_weight / 20.0))
            _bias_cache[mode]["bias"] = round(bias_val, 3)
            _bias_cache[mode]["updated"] = datetime.utcnow().isoformat()

        _save_bias()

        # NEW: adaptive weights mirror bias values for balanced routing
        current_weights = {
            "deterministic": max(0.0, 0.5 + _bias_cache["deterministic"]["bias"]),
            "semantic":      max(0.0, 0.5 + _bias_cache["semantic"]["bias"]),
            "llm":           max(0.0, 0.5 + _bias_cache["llm"]["bias"]),
        }

        _append_weight_history(current_weights)

        logger.info(f"[AdaptiveRouter] Biases updated: {_bias_cache}")
        return {"ok": True, "bias": _bias_cache}

    except Exception as e:
        logger.error(f"[AdaptiveRouter] update_bias_from_reinforcement failed: {e}")
        return {"ok": False, "error": str(e)}

# ------------------------------------------------------------
# Accessors
# ------------------------------------------------------------
def get_bias(mode: str):
    """Return current bias for a reasoning mode."""
    _load_bias()
    return _bias_cache.get(mode, {}).get("bias", 0.0)

def get_all_biases():
    """Return all current adaptive biases."""
    _load_bias()
    return _bias_cache

def export_bias_summary():
    """Prepare data for metrics visualization."""
    _load_bias()
    summary = {
        "timestamp": datetime.utcnow().isoformat(),
        "biases": {m: _bias_cache[m]["bias"] for m in _bias_cache},
        "avg_bias": round(statistics.mean(v["bias"] for v in _bias_cache.values()), 3),
    }
    return summary

# ------------------------------------------------------------
# NEW — Export Adaptive Weights (Phase 7.6c)
# ------------------------------------------------------------
def export_current_weights():
    """
    Export current routing weights + historical evolution for metrics dashboard.
    """
    _load_bias()

    current_weights = {
        "deterministic": max(0.0, 0.5 + _bias_cache["deterministic"]["bias"]),
        "semantic":      max(0.0, 0.5 + _bias_cache["semantic"]["bias"]),
        "llm":           max(0.0, 0.5 + _bias_cache["llm"]["bias"]),
    }

    history = _load_weight_history()

    return {
        "weights": current_weights,
        "history": history
    }

# ------------------------------------------------------------
# Self-test entry point
# ------------------------------------------------------------
if __name__ == "__main__":
    print("=== Solomon Adaptive Router Diagnostic ===")
    result = update_bias_from_reinforcement()
    print(json.dumps(result, indent=2))
    print("\nBias Summary:")
    print(json.dumps(export_bias_summary(), indent=2))
    print("\nWeight History:")
    print(json.dumps(export_current_weights(), indent=2))

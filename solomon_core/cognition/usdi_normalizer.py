# usdi_normalizer.py — Phase 20 Step 17
# ------------------------------------------------------------
# Purpose:
#   Normalize USDI (Unified Skill Difficulty Index) output into
#   a stable, predictable structure used by cognition layers,
#   diagnostics, and UI components.
# ------------------------------------------------------------

import datetime
from typing import Dict, Any

from solomon_core.cognition.skill_difficulty_index import (
    get_skill_difficulty_windows,
)

# ------------------------------------------------------------
# INTERNAL HELPERS
# ------------------------------------------------------------

def _now():
    return datetime.datetime.utcnow()


def _normalize_score(raw: float) -> int:
    """Convert raw USDI score (0–3) to 0–100 range."""
    try:
        v = float(raw)
    except Exception:
        return 0
    return max(0, min(100, int((v / 3.0) * 100)))


def _resolve_window(skill: str, windows: Dict[str, list]) -> str:
    """Determine which difficulty window the skill belongs to."""
    if not skill:
        return "unknown"

    if skill in windows.get("hot_window", []):
        return "hot"
    if skill in windows.get("warm_window", []):
        return "warm"
    if skill in windows.get("cool_window", []):
        return "cool"

    return "unknown"


# ------------------------------------------------------------
# PUBLIC NORMALIZATION API
# ------------------------------------------------------------

def normalize_usdi(usdi_raw: Dict[str, Any], skill: str = None) -> Dict[str, Any]:
    """Normalize USDI output into a stable structure."""
    if not isinstance(usdi_raw, dict):
        return {
            "ok": False,
            "error": "Invalid USDI input",
            "windows": {"hot_window": [], "warm_window": [], "cool_window": []},
            "scores": {},
            "normalized_scores": {},
            "current_window": "unknown",
            "difficulty_score": 0,
            "window_age_days": 0,
            "timestamp": _now().isoformat(),
        }

    windows = {
        "hot_window": usdi_raw.get("hot_window", []) or [],
        "warm_window": usdi_raw.get("warm_window", []) or [],
        "cool_window": usdi_raw.get("cool_window", []) or [],
    }

    raw_scores = usdi_raw.get("difficulty_scores", {}) or {}

    normalized_scores = {
        k: _normalize_score(v) for k, v in raw_scores.items()
    }

    # full dataset view
    if not skill:
        return {
            "ok": True,
            "windows": windows,
            "scores": raw_scores,
            "normalized_scores": normalized_scores,
            "current_window": None,
            "difficulty_score": None,
            "window_age_days": 0,
            "timestamp": _now().isoformat(),
        }

    # skill-specific view
    win = _resolve_window(skill, windows)
    raw = raw_scores.get(skill, 0.0)
    norm = normalized_scores.get(skill, 0)

    return {
        "ok": True,
        "skill": skill,
        "windows": windows,
        "scores": raw_scores,
        "normalized_scores": normalized_scores,
        "current_window": win,
        "difficulty_score": norm,
        "window_age_days": 0,
        "timestamp": _now().isoformat(),
    }


# ------------------------------------------------------------
# Convenience wrapper: always fetch + normalize
# ------------------------------------------------------------

def get_normalized_usdi(skill: str = None) -> Dict[str, Any]:
    """Fetch raw USDI and return normalized output."""
    try:
        raw = get_skill_difficulty_windows()
    except Exception:
        raw = {}

    return normalize_usdi(raw, skill)

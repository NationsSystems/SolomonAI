# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_format_helpers.py
# ---------------------------------------------------------------------------
# Phase-safe helper extraction
# PURE FUNCTIONS ONLY — no behavioral changes
# ---------------------------------------------------------------------------

import re
from typing import List, Optional


# ============================================================================
# 🔧 Bullet sanity guard
# ============================================================================
def _looks_like_char_stream(items: List[str]) -> bool:
    """
    Detect pathological bulletization like:
    ['G','e','n','e','r','a','l']
    Deterministic heuristic — no inference.
    """
    if not items or len(items) < 3:
        return False

    short_count = sum(1 for i in items if isinstance(i, str) and len(i.strip()) <= 2)
    ratio = short_count / max(len(items), 1)

    # If most items are extremely short, it's almost certainly char-splitting
    return ratio >= 0.7


# ============================================================================
# Currency formatting helpers (STRICT)
# ============================================================================
def _normalize_currency_display(value: Optional[str]) -> Optional[str]:
    if not isinstance(value, str):
        return None

    v = value.strip()
    if not v:
        return None

    m = re.match(r"^([\d,]+\.\d{2})\s*\$$", v)
    if m:
        return f"${m.group(1)}"

    return v


def _currency_to_float(value: Optional[str]) -> Optional[float]:
    """Safe deterministic currency parser."""
    if not isinstance(value, str):
        return None
    try:
        return float(value.replace("$", "").replace(",", "").strip())
    except Exception:
        return None


def _format_percent(value: Optional[float]) -> Optional[str]:
    if value is None:
        return None
    try:
        return f"{value * 100:.2f}%"
    except Exception:
        return None
# ------------------------------------------------------------------
# FILE: solomon_core/web_lane/intelligence/universal_extractor.py
# ROLE: Web Lane Structured Signal Extraction (deterministic)
# OWNED-BY: web_lane
# LIFECYCLE: active
# ------------------------------------------------------------------

import re
from typing import List, Dict, Any

# ------------------------------------------------------------------
# Regex patterns (Phase 88 minimal set)
# ------------------------------------------------------------------

_CURRENCY_RE = re.compile(
    r"\$\s*([0-9]{1,3}(?:,[0-9]{3})*(?:\.[0-9]+)?)\s*(?:per\s*(ounce|oz|barrel|lb))?",
    re.IGNORECASE,
)

_TEMP_RE = re.compile(r"(-?\d{1,3})\s?°\s?F?", re.IGNORECASE)

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s?%", re.IGNORECASE)


# ------------------------------------------------------------------
# Query intent hints (Phase 88 deterministic)
# ------------------------------------------------------------------

_PRICE_HINTS = {
    "price",
    "cost",
    "value",
    "gold",
    "silver",
    "oil",
    "gas",
    "stock",
    "market",
}

_WEATHER_HINTS = {
    "weather",
    "temperature",
    "forecast",
    "degrees",
    "rain",
    "snow",
    "wind",
}

_PERCENT_HINTS = {
    "percent",
    "percentage",
    "rate",
}


# ------------------------------------------------------------------
# Universal extraction
# ------------------------------------------------------------------
def extract_structured_signals(text: str) -> List[Dict[str, Any]]:

    if not text:
        return []

    signals: List[Dict[str, Any]] = []

    # ---- currency ----
    for m in _CURRENCY_RE.finditer(text):

        try:

            raw_val = m.group(1).replace(",", "")
            value = float(raw_val)
            unit = m.group(2)

            signals.append(
                {
                    "type": "currency",
                    "value": value,
                    "unit": unit or "",
                    "raw": m.group(0),
                    "confidence": 0.7,
                }
            )

        except Exception:
            continue

    # ---- temperature ----
    for m in _TEMP_RE.finditer(text):

        try:

            value = float(m.group(1))

            signals.append(
                {
                    "type": "temperature",
                    "value": value,
                    "unit": "F",
                    "raw": m.group(0),
                    "confidence": 0.8,
                }
            )

        except Exception:
            continue

    # ---- percent ----
    for m in _PERCENT_RE.finditer(text):

        try:

            value = float(m.group(1))

            signals.append(
                {
                    "type": "percentage",
                    "value": value,
                    "unit": "%",
                    "raw": m.group(0),
                    "confidence": 0.6,
                }
            )

        except Exception:
            continue

    return signals


# ------------------------------------------------------------------
# Deterministic query relevance checks
# ------------------------------------------------------------------
def _query_mentions_any(query: str, hints: set) -> bool:

    if not query:
        return False

    q = query.lower()

    return any(term in q for term in hints)


# ------------------------------------------------------------------
# Deterministic signal filter (MULTI-SIGNAL)
# ------------------------------------------------------------------
def choose_best_signal_for_query(
    signals: List[Dict[str, Any]], query: str
) -> List[Dict[str, Any]]:

    if not signals:
        return []

    q = (query or "").lower()

    allow_currency = _query_mentions_any(q, _PRICE_HINTS)
    allow_temp = _query_mentions_any(q, _WEATHER_HINTS)
    allow_percent = _query_mentions_any(q, _PERCENT_HINTS)

    filtered: List[Dict[str, Any]] = []

    for sig in signals:

        t = sig.get("type")

        if t == "currency" and allow_currency:
            filtered.append(sig)

        elif t == "temperature" and allow_temp:
            filtered.append(sig)

        elif t == "percentage" and allow_percent:
            filtered.append(sig)

    if not filtered:
        return []

    # return top signals sorted by confidence
    filtered.sort(key=lambda s: s.get("confidence", 0.0), reverse=True)

    return filtered[:5]


# ------------------------------------------------------------------
# Formatter (multi-signal)
# ------------------------------------------------------------------
def format_signal_answer(signals: List[Dict[str, Any]], query: str):

    if not signals:
        return None

    lines: List[str] = []

    for signal in signals:

        t = signal.get("type")
        v = signal.get("value")

        if v is None:
            continue

        try:

            if t == "currency":
                lines.append(f"Price: ${float(v):,.2f}")

            elif t == "temperature":
                lines.append(f"Temperature: {float(v):.0f}°F")

            elif t == "percentage":
                lines.append(f"Percentage: {float(v):.2f}%")

        except Exception:
            continue

    if not lines:
        return None

    return "\n".join(lines)
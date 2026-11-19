# ---------------------------------------------------------------------------
# Global Text Hygiene — Phase 85.A
#       solomon_core/text_hygiene/global_text_hygiene.py
# ---------------------------------------------------------------------------
# Purpose:
#   Deterministic, presentation-only cleanup of narrator-visible text.
#
# Authority:
#   • Cosmetic normalization ONLY
#   • Must NOT mutate evidence meaning
#   • Must preserve all numeric values exactly
#   • Must be idempotent
#   • Must be deterministic
#
# Scope:
#   • intra-word fracture repair
#   • OCR spacing cleanup
#   • encoding cleanup
#   • whitespace normalization
#   • safe numeric spacing cleanup
# ---------------------------------------------------------------------------

from __future__ import annotations

import re
from typing import Final


# ---------------------------------------------------------------------------
# Regex — tightly scoped and audited
# ---------------------------------------------------------------------------

# letter fractures: exis tin g → existing
_RE_INTRA_WORD_FRACTURE: Final = re.compile(r"([A-Za-z])\s+([A-Za-z])")

# multiple spaces
_RE_MULTI_SPACE: Final = re.compile(r"[ \t]{2,}")

# space before punctuation
_RE_SPACE_BEFORE_PUNCT: Final = re.compile(r"\s+([,.;:])")

# currency spacing: $ 397 , 000 . 00 → $397,000.00
_RE_CURRENCY_FIX_1: Final = re.compile(r"\$\s+")
_RE_CURRENCY_FIX_2: Final = re.compile(r"(\d)\s*,\s*(\d)")
_RE_CURRENCY_FIX_3: Final = re.compile(r"(\d)\s*\.\s*(\d)")

# encoding junk commonly seen from OCR
_RE_ODD_ENCODING: Final = re.compile(r"[Â«Â»]")

# control-character bullets (DEL, odd glyphs)
_RE_CONTROL_BULLETS: Final = re.compile(r"[\u007f\u00ab]+")


# ---------------------------------------------------------------------------
# Numeric Safety Guard
# ---------------------------------------------------------------------------

def _numeric_fingerprint(text: str) -> list[str]:
    return re.findall(r"\d[\d,\.]*", text)


# ---------------------------------------------------------------------------
# Core Hygiene Pass (deterministic)
# ---------------------------------------------------------------------------

def apply_global_text_hygiene(text: str) -> str:
    if not text or not isinstance(text, str):
        return text

    original_numbers = _numeric_fingerprint(text)
    cleaned = text

    # 1. Encoding cleanup
    cleaned = _RE_ODD_ENCODING.sub("", cleaned)

    # 1b. Normalize control bullets to standard bullet
    cleaned = _RE_CONTROL_BULLETS.sub("• ", cleaned)

    # 2. Currency spacing normalization (SAFE)
    cleaned = _RE_CURRENCY_FIX_1.sub("$", cleaned)
    cleaned = _RE_CURRENCY_FIX_2.sub(r"\1,\2", cleaned)
    cleaned = _RE_CURRENCY_FIX_3.sub(r"\1.\2", cleaned)

    # 3. Intra-word fracture repair (bounded)
    for _ in range(4):
        new_text = _RE_INTRA_WORD_FRACTURE.sub(r"\1\2", cleaned)
        if new_text == cleaned:
            break
        cleaned = new_text

    # 4. Whitespace normalization
    cleaned = _RE_MULTI_SPACE.sub(" ", cleaned)

    # 5. Space-before-punctuation cleanup
    cleaned = _RE_SPACE_BEFORE_PUNCT.sub(r"\1", cleaned)

    # 6. Final trim
    cleaned = cleaned.strip()

    # Numeric integrity guard
    final_numbers = _numeric_fingerprint(cleaned)
    if original_numbers != final_numbers:
        return text

    return cleaned
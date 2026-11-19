# ---------------------------------------------------------------------------
# FILE: solomon_core/llm/llm_formatting.py
# ---------------------------------------------------------------------------

import re


def apply_minimum_sentence_floor(text: str) -> str:
    if not isinstance(text, str):
        return text
    t = text.strip()
    if not t:
        return t

    if not re.search(r"[.!?]$", t):
        if re.match(r"^[A-Z][a-z]+ing\b", t):
            t = "I can " + t[0].lower() + t[1:]
        if not re.search(r"[.!?]$", t):
            t = t.rstrip(",;:") + "."
    return t


def collapse_to_single_paragraph(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return text

    t = text.strip()
    t = re.sub(r"\s*\n\s*", " ", t)
    t = re.sub(r"\s{2,}", " ", t)
    return t.strip()


def enforce_executive_length(text: str, informational_only: bool) -> str:
    if not isinstance(text, str) or not text.strip():
        return text

    if not informational_only:
        return text

    t = text.strip()
    sentences = re.split(r"(?<=[.!?])\s+", t)
    if len(sentences) <= 2:
        return t

    trimmed = " ".join(sentences[:2]).strip()
    words = trimmed.split()
    if len(words) > 75:
        trimmed = " ".join(words[:75]).rstrip()
        if not re.search(r"[.!?]$", trimmed):
            trimmed += "."
    return trimmed
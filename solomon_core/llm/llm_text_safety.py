# ---------------------------------------------------------------------------
# FILE: solomon_core/llm/llm_text_safety.py
# ---------------------------------------------------------------------------

import json
import re

# ------------------------------------------------------------
# Refusal Detection
# ------------------------------------------------------------
_REFUSAL_PATTERNS = (
    "i can't provide",
    "i cannot provide",
    "i'm unable to provide",
    "i am unable to provide",
    "cannot provide real-time",
    "can't provide real time",
)


def looks_like_generic_refusal(text: str) -> bool:
    if not isinstance(text, str):
        return False
    t = text.lower()
    return any(p in t for p in _REFUSAL_PATTERNS)


# ------------------------------------------------------------
# JSON extraction helper (best-effort)
# ------------------------------------------------------------
def extract_json_object(text: str) -> dict | None:
    if not isinstance(text, str) or not text.strip():
        return None

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    try:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception:
        pass

    return None


# ------------------------------------------------------------
# Sentence integrity fixer
# ------------------------------------------------------------
def normalize_sentence_start(text: str) -> str:
    if not isinstance(text, str):
        return text
    if not text:
        return text
    stripped = text.lstrip()
    if stripped and stripped[0].islower():
        return stripped[0].upper() + stripped[1:]
    return text


# ------------------------------------------------------------
# Repetition dampener
# ------------------------------------------------------------
_REPETITIVE_PHRASES = (
    "i'd be happy to",
    "i would be happy to",
    "generally, provide guidance",
)


def soft_dedupe(text: str) -> str:
    if not isinstance(text, str):
        return text
    lowered = text.lower()
    for phrase in _REPETITIVE_PHRASES:
        if lowered.startswith(phrase):
            parts = text.split(".", 1)
            if len(parts) == 2:
                return parts[1].strip().capitalize()
    return text


# ------------------------------------------------------------
# Tail question suppressor
# ------------------------------------------------------------
def suppress_weak_followup(text: str) -> str:
    if not isinstance(text, str) or not text:
        return text

    weak_patterns = (
        r"would you like me to.*\?$",
        r"would you like to proceed.*\?$",
        r"would you like me to demonstrate.*\?$",
        r"would you like me to elaborate.*\?$",
    )

    stripped = text.strip()
    for pat in weak_patterns:
        if re.search(pat, stripped, re.IGNORECASE):
            parts = re.split(r"(?<=[.!?])\s+", stripped)
            if len(parts) > 1:
                return " ".join(parts[:-1]).strip()
    return text


# ------------------------------------------------------------
# Follow-up options leakage suppressor
# ------------------------------------------------------------
_FOLLOWUP_LEADINS = (
    "you can also try",
    "here are a few options",
    "next, you can choose",
    "if you want to continue",
    "you can continue with any of the following",
    "if helpful, choose one of these",
    "pick one of these",
)


def strip_suggestion_leakage(text: str) -> str:
    if not isinstance(text, str) or not text.strip():
        return text

    t = text.strip()

    parsed = extract_json_object(t)
    if isinstance(parsed, dict) and "answer" in parsed:
        ans = parsed.get("answer")
        if isinstance(ans, str) and ans.strip():
            return ans.strip()

    try:
        t = re.sub(
            r"\{\s*\"suggestions\"\s*:\s*\[[\s\S]*?\]\s*\}\s*$",
            "",
            t,
            flags=re.IGNORECASE,
        ).strip()
    except Exception:
        pass

    lower = t.lower()
    cut_at = None
    for lead in _FOLLOWUP_LEADINS:
        idx = lower.find(lead)
        if idx != -1:
            cut_at = idx if cut_at is None else min(cut_at, idx)

    if cut_at is not None:
        t = t[:cut_at].rstrip()

    return t.strip()
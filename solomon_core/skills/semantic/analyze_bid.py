# solomon_core/skills/semantic/analyze_bid.py — Phase-38 GUI-Ready
# ---------------------------------------------------------------
# Bid Analysis Micro-Skill — Phase 38+
#
# Guarantees:
#   • Deterministic text extraction
#   • Deterministic bid signal emission
#   • Emits reasoning request for GUI and orchestrator
#   • No direct LLM execution
# ---------------------------------------------------------------

import os
import re
import json
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text
from solomon_core.domains import DOMAIN_BID

logger = get_logger("skill_analyze_bid")

# Phase-38 authority declaration
EXECUTION_AUTHORITY = False

SCHEMA_NAME = "BidAnalysis.Strict.V2"
DOCINTEL_TYPE = DOMAIN_BID
MAX_CHARS = 32000  # Safety truncation for large bids

# -----------------------------------------------------------
# Centralized keyword dictionary (JSON in project-root /data)
# -----------------------------------------------------------

_KEYWORDS_CACHE = None

_KEYWORDS_DEFAULT = {
    "alternates": [],
    "allowances": [],
    "exclusions": [],
    "inclusions": [],
    "scope": [],
    "schedule": [],
    "payment_terms": [],
    "totals": [],
    "grand_totals": [],
}


def _project_root() -> str:
    """
    Determine Solomon project root deterministically.

    Strategy:
      1) Walk upward from this file until we find a directory containing BOTH:
           - solomon_core/
           - data/
      2) If not found, fall back to the previous relative behavior.
    """
    start = os.path.abspath(os.path.dirname(__file__))
    cur = start

    # Hard cap to prevent runaway loops
    for _ in range(12):
        if (
            os.path.isdir(os.path.join(cur, "solomon_core"))
            and os.path.isdir(os.path.join(cur, "data"))
        ):
            return cur

        parent = os.path.dirname(cur)
        if parent == cur:
            break
        cur = parent

    # Fallback: legacy relative root (best-effort)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", ".."))


def _keywords_json_path() -> str:
    return os.path.join(_project_root(), "data", "domain_dictionaries", "bid_keywords.json")


def _normalize_words(words):
    out = []
    for w in words or []:
        if isinstance(w, str):
            ww = w.strip().lower()
            if ww:
                out.append(ww)
    return out


def _load_bid_keywords() -> dict:
    """
    Loads bid keyword sets from:
      data/domain_dictionaries/bid_keywords.json

    Deterministic behavior:
      - If missing/invalid, returns empty defaults (no signals triggered by vocab).
      - Normalizes all terms to lowercase.

    Logging behavior:
      - Silent by default to avoid noisy logs; deterministic fallback is enough.
    """
    global _KEYWORDS_CACHE
    if isinstance(_KEYWORDS_CACHE, dict):
        return _KEYWORDS_CACHE

    path = _keywords_json_path()
    try:
        with open(path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        # Ignore meta; only pull known keys
        loaded = dict(_KEYWORDS_DEFAULT)
        for key in loaded.keys():
            loaded[key] = _normalize_words(raw.get(key, []))

        _KEYWORDS_CACHE = loaded
        return loaded

    except Exception:
        _KEYWORDS_CACHE = dict(_KEYWORDS_DEFAULT)
        return _KEYWORDS_CACHE


# -----------------------------------------------------------
# Helpers
# -----------------------------------------------------------

def _select_single_file(arguments: dict):
    docs = arguments.get("docs")
    if isinstance(docs, list) and len(docs) == 1 and isinstance(docs[0], str):
        return docs[0]
    file_path = arguments.get("file_path")
    if isinstance(file_path, str):
        return file_path
    return None


def _contains_any(text_lower: str, words):
    # words are already normalized lowercase; text_lower is lowercase
    return any(w in text_lower for w in (words or []))


def _emit_bid_signals(text: str) -> dict:
    """
    Deterministic structural signal extraction.
    NO inference. Pattern presence only.
    """

    lower = text.lower()
    kw = _load_bid_keywords()

    currency_re = re.compile(r"\$\s?\d[\d,]*(?:\.\d{2})?")
    percent_re = re.compile(r"\d+(?:\.\d+)?%")
    unit_cost_re = re.compile(
        r"\$\s?\d[\d,]*(?:\.\d{2})?\s*/\s*(?:sf|lf|ea|each|hr|hour)",
        re.I,
    )
    date_re = re.compile(r"\b\d{1,2}/\d{1,2}/\d{2,4}\b")

    signals = {
        # Financial presence
        "currency_values_detected": len(currency_re.findall(text)),
        "percent_values_detected": len(percent_re.findall(text)),
        "unit_costs_detected": len(unit_cost_re.findall(text)),

        # Structural sections (dictionary-driven)
        "has_alternates": _contains_any(lower, kw.get("alternates")),
        "has_allowances": _contains_any(lower, kw.get("allowances")),
        "has_exclusions": _contains_any(lower, kw.get("exclusions")),
        "has_inclusions": _contains_any(lower, kw.get("inclusions")),
        "has_scope_section": _contains_any(lower, kw.get("scope")),
        "has_schedule": _contains_any(lower, kw.get("schedule")),
        "has_payment_terms": _contains_any(lower, kw.get("payment_terms")),

        # Totals (dictionary-driven)
        "has_total": _contains_any(lower, kw.get("totals")),
        "has_grand_total": _contains_any(lower, kw.get("grand_totals")),

        # Dates
        "dates_detected": len(date_re.findall(text)),
    }

    return signals


# -----------------------------------------------------------
# Main Execution
# -----------------------------------------------------------

def execute(arguments: dict):
    path = _select_single_file(arguments)

    if not path:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Bid analysis requires exactly one document (file_path or docs=[single]).",
            "user_output": "You must provide exactly one bid document for analysis.",
        }

    extracted = extract_text({"file_path": path})
    if not isinstance(extracted, dict) or not extracted.get("ok"):
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": (extracted or {}).get("result", "Extraction failed"),
            "user_output": (extracted or {}).get("user_output", "Failed to extract bid document."),
        }

    text = (extracted.get("result") or "").strip()
    if not text:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Empty or unreadable bid.",
            "user_output": "The bid document appears to contain no readable text.",
        }

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[Document truncated for analysis]\n"

    # -----------------------------------------------------------
    # Deterministic Signals
    # -----------------------------------------------------------
    signals = _emit_bid_signals(text)

    # -----------------------------------------------------------
    # Phase-38: Build reasoning request for GUI display
    # -----------------------------------------------------------
    prompt = (
        f"You are Solomon's professional bid-analysis engine.\n\n"
        f"Analyze the following bid document thoroughly and clearly.\n\n"
        f"--- BID DOCUMENT ({os.path.basename(path)}) ---\n"
        f"{text}\n"
        f"--- END DOCUMENT ---\n\n"
        "Return ONLY a clean plain-text analysis.\n\n"
        "Provide:\n"
        "• Overall summary of the bid\n"
        "• Detailed scope of work\n"
        "• Key deliverables\n"
        "• Pricing structure & cost drivers\n"
        "• Assumptions\n"
        "• Exclusions\n"
        "• Risks and red flags\n"
        "• Missing or unclear information\n"
        "• Competitive insights\n"
        "• Final executive summary\n"
    )

    reasoning_request = {
        "type": "bid_analysis",
        "schema": "ReasoningRequest.BidAnalysis.Strict",
        "prompt": prompt,
        "metadata": {
            "skill": "analyze_bid",
            "signal_only": True,
            "docintel_type": DOCINTEL_TYPE,
            "schema_version": SCHEMA_NAME,
            "filename": path,
            "display_name": os.path.basename(path),
            "char_count": len(text),
            "signals": signals,
        },
    }

    return {
        "ok": True,
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "filename": path,
        "result": prompt,
        "user_output": prompt,
        "reasoning_request": reasoning_request,
        "signals": signals,
        "facts": {
            "extracted": True,
            "char_count": len(text),
            "signal_summary": signals,
        },
    }

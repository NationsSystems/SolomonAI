# solomon_core/skills/semantic/docintel_scope_obligation_mismatch.py — Phase-38 SAFE
# -------------------------------------------------------------------
# SIGNAL-ONLY Scope & Obligation Mismatch Detection
#
# Phase-38 GUARANTEES:
#   • No direct LLM calls
#   • Execution deferred to orchestrator
#   • Deterministic safety-net preserved
# -------------------------------------------------------------------

import re
import json
from solomon_core.logger import get_logger

logger = get_logger("skill_scope_obligation_mismatch")

STOPWORDS = {
    "the", "and", "or", "of", "to", "for", "with", "a", "an", "shall",
    "one", "time", "full", "system"
}


def _tokenize(text: str):
    if not isinstance(text, str):
        return set()
    words = re.findall(r"[a-zA-Z]+", text.lower())
    return {w for w in words if w not in STOPWORDS and len(w) > 3}


def _extract_items(text: str):
    if not isinstance(text, str):
        return []
    lines = re.findall(r"-\s*(.+)", text)
    return [l.strip() for l in lines if l.strip()]


def _semantic_match(a: str, b: str) -> bool:
    ta = _tokenize(a)
    tb = _tokenize(b)
    return bool(ta & tb)


def execute(arguments: dict):
    contract_text = arguments.get("contract_text")
    bid_text = arguments.get("bid_text")

    if not isinstance(contract_text, str) or not contract_text.strip():
        return {
            "ok": False,
            "result": "Missing contract text",
            "user_output": "No contract text provided."
        }

    if not isinstance(bid_text, str) or not bid_text.strip():
        return {
            "ok": False,
            "result": "Missing bid text",
            "user_output": "No bid text provided."
        }

    # -------------------------------------------------
    # Phase-38: Emit structured reasoning request
    # -------------------------------------------------
    reasoning_request = {
        "reasoning_type": "scope_obligation_mismatch",
        "inputs": {
            "contract_text": contract_text,
            "bid_text": bid_text,
        },
        "constraints": {
            "no_execution": True,
            "requires_orchestrator": True,
        },
        "expected_outputs": [
            "contract_obligations",
            "bid_inclusions",
            "missing_from_bid",
            "extra_in_bid",
            "matched_items",
            "status",
            "risks",
            "evidence",
        ],
    }

    # -----------------------------------------------------------------
    # Deterministic safety-net
    # -----------------------------------------------------------------
    contract_items = _extract_items(contract_text)
    bid_items = _extract_items(bid_text)

    missing_from_bid = [
        c for c in contract_items
        if not any(_semantic_match(c, b) for b in bid_items)
    ]

    extra_in_bid = [
        b for b in bid_items
        if not any(_semantic_match(b, c) for c in contract_items)
    ]

    matched_items = [
        c for c in contract_items
        if any(_semantic_match(c, b) for b in bid_items)
    ]

    structured = {
        "contract_obligations": contract_items,
        "bid_inclusions": bid_items,
        "missing_from_bid": missing_from_bid,
        "extra_in_bid": extra_in_bid,
        "matched_items": matched_items,
        "status": "mismatch" if missing_from_bid or extra_in_bid else "clean",
        "risks": missing_from_bid,
        "evidence": [],
    }

    summary = (
        "Scope and obligation mismatches detected."
        if structured["status"] != "clean"
        else "No major scope or obligation mismatches detected."
    )

    return {
        "ok": True,
        "structured": structured,
        "user_output": summary,
        "reasoning_request": reasoning_request,
    }

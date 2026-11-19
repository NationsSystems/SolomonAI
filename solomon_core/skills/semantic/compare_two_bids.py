# solomon_core/skills/semantic/compare_two_bids.py — Phase-38 SAFE
# ---------------------------------------------------------------
# SIGNAL-ONLY Two-Document Comparison
#
# Phase-38 GUARANTEES:
#   • NO LLM calls
#   • NO independent execution
#   • Returns reasoning REQUEST for orchestrator
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text
from solomon_core.domains import DOMAIN_BID

logger = get_logger("skill_compare_two_bids")

SCHEMA_NAME = "DocumentCompare.Two.Grounded.V38"
DOCINTEL_TYPE = DOMAIN_BID
MAX_CHARS = 20000


def _select_two_files(arguments: dict):
    docs = arguments.get("docs")
    if isinstance(docs, list) and len(docs) == 2 and all(isinstance(d, str) for d in docs):
        return docs[0], docs[1]
    return None, None


def _extract_text_or_fail(path: str):
    extracted = extract_text({"docs": [path]})
    if not extracted.get("ok"):
        return None, extracted.get("user_output", "Failed to extract document.")
    text = (extracted.get("result") or "").strip()
    if not text:
        return None, "The document appears to contain no readable text."
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[Document truncated]\n"
    return text, None


def execute(arguments: dict):
    """
    Phase-38 SAFE: SIGNAL-ONLY two-document comparison.
    Produces a reasoning REQUEST instead of executing an LLM.
    """

    path1, path2 = _select_two_files(arguments)

    if not path1 or not path2:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Two-document comparison requires exactly two documents via docs=[path1, path2].",
            "user_output": "You must provide exactly two documents.",
        }

    text1, err1 = _extract_text_or_fail(path1)
    if err1:
        return {"ok": False, "result": err1, "user_output": err1}

    text2, err2 = _extract_text_or_fail(path2)
    if err2:
        return {"ok": False, "result": err2, "user_output": err2}

    # ---------------------------------------------------
    # Phase-38: Emit structured reasoning request instead of direct LLM call
    # ---------------------------------------------------
    reasoning_request = {
        "reasoning_type": "compare_two_bids",
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "inputs": {
            "document1": {"filename": path1, "text": text1},
            "document2": {"filename": path2, "text": text2},
        },
        "constraints": {
            "no_execution": True,
            "requires_orchestrator": True,
        },
        "expected_outputs": [
            "General Comparison",
            "Key Differences / Gaps",
            "Recommendation",
        ],
    }

    return {
        "ok": True,
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "result": reasoning_request,
        "user_output": "Reasoning request generated (execution deferred to orchestrator).",
        "filenames": [path1, path2],
    }

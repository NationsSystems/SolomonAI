# solomon_core/skills/semantic/highlight_differences.py — Phase-38 SAFE
# ---------------------------------------------------------------
# SIGNAL-ONLY Multi-Document Difference Highlighting
#
# Phase-38 GUARANTEES:
#   • No direct LLM calls
#   • Execution deferred to orchestrator
#   • Deterministic extraction preserved
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text

logger = get_logger("highlight_differences")

MAX_CHARS = 32000  # Kept local — NOT a domain constant


def _collect_docs(arguments: dict):
    raw = arguments.get("docs")
    if not isinstance(raw, list):
        return []

    clean = []
    seen = set()

    for p in raw:
        if isinstance(p, str) and p not in seen:
            clean.append(p)
            seen.add(p)

    return clean


def execute(arguments: dict):
    docs = _collect_docs(arguments)

    if len(docs) < 2:
        return {
            "ok": False,
            "result": "highlight_differences requires docs[] with >= 2 items.",
            "user_output": "You must supply two or more documents."
        }

    extracted = {}
    merged_blocks = []

    for path in docs:
        res = extract_text({"file_path": path})
        name = os.path.basename(path)

        if not res.get("ok") or not res.get("result"):
            text = ""
            merged_blocks.append(f"[FILE: {name}] (unreadable)\n")
        else:
            text = res["result"]
            merged_blocks.append(f"[FILE: {name}]\n{text}\n")

        extracted[name] = text

    merged_text = "\n".join(merged_blocks)

    if len(merged_text) > MAX_CHARS:
        merged_text = merged_text[:MAX_CHARS] + "\n\n[Truncated document set]\n"

    # ---------------------------------------------------
    # Phase-38: Emit structured reasoning request
    # ---------------------------------------------------
    reasoning_request = {
        "reasoning_type": "highlight_differences",
        "schema": "HighlightDifferences.Strict.V38",
        "docintel_type": "generic_document",
        "inputs": {
            "docs": docs,
            "merged_text": merged_text,
        },
        "constraints": {
            "no_execution": True,
            "requires_orchestrator": True,
        },
        "expected_outputs": [
            "difference_narrative",
            "file_text_mapping",
        ],
    }

    return {
        "ok": True,
        "result": reasoning_request,
        "user_output": "Reasoning request generated (execution deferred to orchestrator).",
        "docs": docs,
        "files": extracted
    }

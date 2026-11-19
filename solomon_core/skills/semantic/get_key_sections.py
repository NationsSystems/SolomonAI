# solomon_core/skills/semantic/get_key_sections.py — Phase-38 SAFE
# ---------------------------------------------------------------
# SIGNAL-ONLY Key Section Extraction Micro-Skill
#
# Phase-38 GUARANTEES:
#   • No direct LLM calls
#   • Execution deferred to orchestrator
#   • Deterministic fallback headers preserved
# ---------------------------------------------------------------

import os
import re
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text

logger = get_logger("skill_get_key_sections")


def _select_single(arguments: dict):
    docs = arguments.get("docs")
    if isinstance(docs, list) and len(docs) == 1 and isinstance(docs[0], str):
        return docs[0]

    fp = arguments.get("file_path")
    if isinstance(fp, str):
        return fp

    return None


def _extract_headers(text: str):
    if not text:
        return []

    header_pattern = re.compile(
        r"^\s*(?:\d+\.\s+|[A-Z][A-Za-z\s]{3,}:)\s+.+$",
        re.MULTILINE
    )
    return [h.strip() for h in header_pattern.findall(text)][:50]


def execute(arguments: dict):
    path = _select_single(arguments)

    if not path:
        return {
            "ok": False,
            "result": "get_key_sections requires file_path or docs=[single] (strict schema).",
            "user_output": "No valid document was supplied.",
            "structured": {"headers": []}
        }

    ext = extract_text({"file_path": path})
    if not ext.get("ok"):
        return {
            "ok": False,
            "result": ext.get("result", "Extraction failed"),
            "user_output": ext.get("user_output", "Could not read document."),
            "structured": {"headers": []}
        }

    text = (ext.get("result") or "").strip()
    if not text:
        return {
            "ok": False,
            "result": "Document contains no readable text.",
            "user_output": "The document has no readable content.",
            "structured": {"headers": []}
        }

    headers = _extract_headers(text)

    # ---------------------------------------------------
    # Phase-38: Emit structured reasoning request instead of direct LLM call
    # ---------------------------------------------------
    reasoning_request = {
        "reasoning_type": "get_key_sections",
        "schema": "KeySections.Strict.V38",
        "docintel_type": "generic_document",
        "inputs": {
            "filename": path,
            "text": text,
        },
        "constraints": {
            "no_execution": True,
            "requires_orchestrator": True,
        },
        "expected_outputs": [
            "section_titles",
            "section_summaries",
            "document_summary",
        ],
    }

    return {
        "ok": True,
        "result": reasoning_request,
        "user_output": "Reasoning request generated (execution deferred to orchestrator).",
        "structured": {"headers": headers}
    }

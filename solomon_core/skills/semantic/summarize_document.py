# solomon_core/skills/semantic/summarize_document.py — Phase-38 SAFE
# ---------------------------------------------------------------
# SIGNAL-ONLY Document Summarization
#
# Phase-38 GUARANTEES:
#   • NO LLM calls
#   • NO independent execution
#   • Returns reasoning REQUEST for orchestrator
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text
from solomon_core.domains import DOMAIN_GENERIC_DOCUMENT

logger = get_logger("skill_summarize_document")

SCHEMA_NAME = "DocumentSummary.Strict.V38"
DOCINTEL_TYPE = DOMAIN_GENERIC_DOCUMENT


def _select_single_file(arguments: dict):
    docs = arguments.get("docs")

    # Structured docs from GUI / pipeline
    if isinstance(docs, list) and len(docs) == 1:
        return docs[0]

    file_path = arguments.get("file_path")
    if isinstance(file_path, str):
        return file_path

    return None


def execute(arguments: dict):
    """
    Phase-38 SAFE: SIGNAL-ONLY document summarization.
    Produces a reasoning REQUEST instead of executing an LLM.
    """

    path = _select_single_file(arguments)

    if not path:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Document summarization requires exactly one document.",
            "user_output": "You must provide exactly one document to summarize.",
        }

    extracted = extract_text({"docs": [path]})

    if not extracted.get("ok"):
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": extracted.get("result", "Extraction failed."),
            "user_output": extracted.get("user_output", "Failed to extract document."),
        }

    text = (extracted.get("result") or "").strip()

    if not text:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Empty or unreadable document.",
            "user_output": "The document contains no readable text.",
        }

    MAX_CHARS = 32000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[Document truncated for summarization]\n"

    original_name = os.path.basename(path)

    # ---------------------------------------------------
    # Phase-52 Invariant:
    # ALWAYS emit execution-ready semantic text
    # ---------------------------------------------------
    summary_seed = (
        f"Document: {original_name}\n\n"
        f"Content Preview:\n{text[:2000]}"
    )

    # ---------------------------------------------------
    # Phase-38: Emit CANONICAL document-shaped reasoning request
    # ---------------------------------------------------
    reasoning_request = {
        "reasoning_type": "summarize_document",
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "text": summary_seed,  # <-- CRITICAL: always non-empty, analyzable
        "inputs": {
            "documents": [
                {
                    "path": path,
                    "original_name": original_name,
                    "text": text,
                }
            ]
        },
        "constraints": {
            "no_execution": True,
            "requires_orchestrator": True,
        },
        "expected_outputs": ["plain_text_summary"],
    }

    return {
        "ok": True,
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "result": reasoning_request,
        "user_output": "Reasoning request generated (execution deferred to orchestrator).",
    }

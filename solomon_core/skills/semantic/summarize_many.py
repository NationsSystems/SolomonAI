# solomon_core/skills/semantic/summarize_many.py — Phase-46 SAFE
# ---------------------------------------------------------------
# SIGNAL-ONLY Multi-Document Summarization (MDD)
#
# Phase-38 / Phase-46 GUARANTEES:
#   • NO LLM calls
#   • NO database access
#   • NO file path leakage
#   • Deterministic, payload-only
#   • Emits TEXT-RICH reasoning request for orchestrator
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger

from solomon_core.skills.semantic.extract_text import execute as extract_text
from solomon_core.domains import DOMAIN_DOCINTEL

logger = get_logger("skill_summarize_many")

SCHEMA_NAME = "DocumentSummary.Many.Strict.V46"
DOCINTEL_TYPE = DOMAIN_DOCINTEL


# ---------------------------------------------------------------
# Main executor (strict)
# ---------------------------------------------------------------
def execute(arguments: dict):
    """
    Phase-46 SAFE: SIGNAL-ONLY multi-document summarization.
    Emits raw extracted text per document for LLM synthesis.
    """

    # ---------------------------------------------
    # COLLECT DOCUMENT PATHS (INTERNAL ONLY)
    # ---------------------------------------------
    paths = []

    if isinstance(arguments.get("docs"), list):
        paths = [p for p in arguments["docs"] if isinstance(p, str)]

    if not paths:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "summarize_many requires at least one document.",
            "user_output": "No documents provided.",
        }

    documents = []

    # ---------------------------------------------
    # EXTRACT TEXT (NO PATH LEAKAGE)
    # ---------------------------------------------
    for path in paths:
        packet = extract_text({"docs": [path]})

        if not packet.get("ok"):
            return {
                "ok": False,
                "schema": SCHEMA_NAME,
                "docintel_type": DOCINTEL_TYPE,
                "result": "One or more documents could not be read.",
                "user_output": "One or more documents could not be processed.",
            }

        raw_text = packet.get("result") or ""

        if not raw_text.strip():
            return {
                "ok": False,
                "schema": SCHEMA_NAME,
                "docintel_type": DOCINTEL_TYPE,
                "result": "Empty document detected.",
                "user_output": "One of the documents contained no readable text.",
            }

        documents.append({
            # SAFE DISPLAY NAME ONLY — NEVER PATH
            "display_name": os.path.basename(path),
            "raw_text": raw_text,
        })

    # ---------------------------------------------
    # Emit reasoning request (TEXT-RICH)
    # ---------------------------------------------
    reasoning_request = {
        "reasoning_type": "summarize_many",
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "inputs": {
            "documents": documents,
        },
        "constraints": {
            "no_execution": True,
            "requires_orchestrator": True,
        },
        "expected_outputs": [
            "per_document_summaries",
            "combined_summary",
            "key_differences",
        ],
    }

    return {
        "ok": True,
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "result": reasoning_request,
        "user_output": "Documents prepared for summarization.",
    }

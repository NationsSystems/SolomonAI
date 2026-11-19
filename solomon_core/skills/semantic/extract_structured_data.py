# solomon_core/skills/semantic/extract_structured_data.py — Phase-38 GUI-Ready
# ---------------------------------------------------------------
# SIGNAL-ONLY Structured Data Extraction Micro-Skill
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text
from solomon_core.domains import DOMAIN_GENERIC_DOCUMENT

logger = get_logger("skill_extract_structured_data")

SCHEMA_NAME = "DocumentStructuredData.Strict.V38"
DOCINTEL_TYPE = DOMAIN_GENERIC_DOCUMENT

# ---------------------------------------------------------------
# Phase-38: Strict single-file selector
# ---------------------------------------------------------------
def _select_single_file(arguments: dict):
    docs = arguments.get("docs")
    if isinstance(docs, list) and len(docs) == 1 and isinstance(docs[0], str):
        return docs[0]

    file_path = arguments.get("file_path")
    if isinstance(file_path, str):
        return file_path

    return None

# ---------------------------------------------------------------
# Phase-38 SAFE execution (SIGNAL-ONLY)
# ---------------------------------------------------------------
def execute(arguments: dict):
    path = _select_single_file(arguments)

    if not path:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Structured extraction requires exactly one document.",
            "user_output": "Provide exactly one document for structured data extraction."
        }

    extracted = extract_text({"file_path": path})

    if not extracted.get("ok"):
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": extracted.get("result", "Extraction failed"),
            "user_output": extracted.get("user_output", "Failed to extract document.")
        }

    text = (extracted.get("result") or "").strip()

    if not text:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Empty or unreadable document.",
            "user_output": "The document contains no readable text."
        }

    MAX_CHARS = 32000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[Document truncated]\n"

    # ---------------------------------------------------
    # Phase-38: Emit structured reasoning request for GUI
    # ---------------------------------------------------
    reasoning_request = {
        "reasoning_type": "extract_structured_data",
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "inputs": {
            "filename": path,
            "text": text,
        },
        "constraints": {
            "no_execution": True,
            "requires_orchestrator": True,
        },
        "expected_outputs": [
            "structured_plain_text",
            "user_output",
        ],
    }

    return {
        "ok": True,
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "result": reasoning_request,
        "user_output": "Reasoning request generated (execution deferred to orchestrator)."
    }

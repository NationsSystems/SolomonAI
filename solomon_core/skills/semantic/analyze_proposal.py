# solomon_core/skills/semantic/analyze_proposal.py — Phase-38 SAFE
# ---------------------------------------------------------------
# SIGNAL-ONLY Proposal Analysis Micro-Skill
#
# Phase-38 GUARANTEES:
#   • No direct LLM calls
#   • No execution authority
#   • Emits structured reasoning request for orchestrator
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text
from solomon_core.domains import DOMAIN_PROPOSAL

logger = get_logger("skill_analyze_proposal")

SCHEMA_NAME = "ProposalAnalysis.Strict.V38"
DOCINTEL_TYPE = DOMAIN_PROPOSAL


def _select_single_file(arguments: dict):
    """
    STRICT schema:

    Valid:
        { "file_path": "/path/to/proposal" }
        { "docs": ["/path/to/proposal"] }

    Anything else → None
    """
    docs = arguments.get("docs")
    if isinstance(docs, list) and len(docs) == 1 and isinstance(docs[0], str):
        return docs[0]

    file_path = arguments.get("file_path")
    if isinstance(file_path, str):
        return file_path

    return None


def execute(arguments: dict):
    """
    Phase-38 SAFE proposal analysis.
    Returns structured reasoning request instead of calling LLM.
    """

    path = _select_single_file(arguments)

    if not path:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Proposal analysis requires exactly one document (file_path or docs=[single]).",
            "user_output": "You must provide exactly one proposal document for analysis."
        }

    extracted = extract_text({"file_path": path})

    if not extracted.get("ok"):
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": extracted.get("result", "Extraction failed"),
            "user_output": extracted.get("user_output", "Failed to extract proposal document.")
        }

    text = (extracted.get("result") or "").strip()

    if not text:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Empty or unreadable proposal.",
            "user_output": "The proposal document appears to contain no readable text."
        }

    MAX_CHARS = 32000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[Document truncated for analysis]\n"

    # ---------------------------------------------------
    # Phase-38: Emit structured reasoning request instead of direct LLM call
    # ---------------------------------------------------
    reasoning_request = {
        "reasoning_type": "analyze_proposal",
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
            "overall_summary",
            "scope_of_work",
            "key_deliverables",
            "pricing_structure",
            "assumptions_dependencies",
            "exclusions_limitations",
            "risks_red_flags",
            "missing_info",
            "competitive_positioning",
            "executive_summary",
        ],
    }

    return {
        "ok": True,
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "result": reasoning_request,
        "user_output": "Reasoning request generated (execution deferred to orchestrator).",
        "filename": path
    }

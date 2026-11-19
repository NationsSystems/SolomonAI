# solomon_core/skills/semantic/analyze_contract.py — Phase-38 SAFE
# ---------------------------------------------------------------
# SIGNAL-ONLY Contract Analysis Micro-Skill
#
# Phase-38 GUARANTEES:
#   • No direct LLM calls
#   • No execution authority
#   • Emits structured reasoning request for orchestrator
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text
from solomon_core.domains import DOMAIN_CONTRACT

logger = get_logger("skill_analyze_contract")

SCHEMA_NAME = "ContractAnalysis.Strict.V38"
DOCINTEL_TYPE = DOMAIN_CONTRACT


def _select_single_file(arguments: dict):
    """
    STRICT schema:

    Valid:
        { "file_path": "/path/to/contract" }
        { "docs": ["/path/to/contract"] }

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
    Phase-38 SAFE contract analysis.
    Returns structured reasoning request instead of calling LLM.
    """

    path = _select_single_file(arguments)

    if not path:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Contract analysis requires exactly one document (file_path or docs=[single]).",
            "user_output": "You must provide exactly one contract document for analysis."
        }

    extracted = extract_text({"file_path": path})

    if not extracted.get("ok"):
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": extracted.get("result", "Extraction failed"),
            "user_output": extracted.get("user_output", "Failed to extract contract document.")
        }

    text = (extracted.get("result") or "").strip()

    if not text:
        return {
            "ok": False,
            "schema": SCHEMA_NAME,
            "docintel_type": DOCINTEL_TYPE,
            "result": "Empty or unreadable contract.",
            "user_output": "The contract document appears to contain no readable text."
        }

    MAX_CHARS = 32000
    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[Document truncated for analysis]\n"

    # ---------------------------------------------------
    # Phase-38: Emit structured reasoning request instead of direct LLM call
    # ---------------------------------------------------
    reasoning_request = {
        "reasoning_type": "analyze_contract",
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
            "parties_roles",
            "scope_of_work",
            "payment_terms",
            "warranties_slas",
            "liability_indemnification",
            "term_renewal_termination",
            "confidentiality_ip",
            "compliance_clauses",
            "risks_red_flags",
            "missing_provisions",
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

# solomon_core/skills/semantic/multi_document_compare.py
# ---------------------------------------------------------------
# Phase 24 — GROUNDED ASSERTION ENFORCEMENT VERSION (LEFT/RIGHT ELIMINATED)
#
# This wrapper has been updated to:
#   • Completely remove any left/right selection logic
#   • Always accept a list of documents (>=2) for comparison
#   • Fully deterministic, no user intervention required
#   • Fully aligned with DocIntelExecutionAdapter invariants
# ---------------------------------------------------------------

import os
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.semantic_document_compare import execute as semantic_exec

from solomon_core.db import SessionLocal
from solomon_core.models import FileRegistry
from solomon_core.domains import DOMAIN_DOCINTEL  # centralized DocIntel domain

logger = get_logger("skill_multi_document_compare")

# ---------------------------------------------------------------
# Recover original uploaded filename (safe, read-only)
# ---------------------------------------------------------------
def _recover_original_name(path: str) -> str:
    if not path:
        return "unknown"

    random_name = os.path.basename(path)
    db = SessionLocal()

    try:
        row = (
            db.query(FileRegistry.original_name)
            .filter(FileRegistry.random_name == random_name)
            .first()
        )
        if row and row[0]:
            return row[0]
        return random_name
    except Exception:
        return random_name
    finally:
        db.close()

# ---------------------------------------------------------------
# STRICT Phase-24 doc collector (LEFT/RIGHT eliminated)
# ---------------------------------------------------------------
def _collect_docs(arguments: dict):
    """
    Phase-24 strict rule:
        ONLY docs[] is accepted.
        No inference, no aliasing, no fallback fields.
        No left/right choices.
    """
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

# ---------------------------------------------------------------
# ENTRY POINT — PHASE-24 GROUNDED MULTI-DOC COMPARE WRAPPER
# ---------------------------------------------------------------
def execute(arguments=None):
    if arguments is None:
        arguments = {}

    # STRICT doc list retrieval
    docs = _collect_docs(arguments)
    if len(docs) < 2:
        return {
            "ok": False,
            "result": "multi_document_compare requires docs[] with >= 2 items (strict schema).",
            "user_output": "You must supply two or more documents.",
        }

    # ORIGINAL NAME RECOVERY (DISPLAY ONLY)
    original_names = {path: _recover_original_name(path) for path in docs}

    # PHASE-24 GROUNDED ASSERTION CONTRACT
    grounding_contract = {
        "grounding_required": True,
        "allow_inference": False,
        "allow_template_completion": False,
        "missing_information_behavior": "explicitly_state_absence",
        "assertion_types_allowed": ["explicit", "implicit_strict", "absent"],
        "forbidden_language": [
            "typically",
            "usually",
            "generally",
            "likely",
            "industry standard",
        ],
    }

    # BUILD STRICT ARG SET FOR DOWNSTREAM ENGINE
    enriched = {
        "docs": docs,
        "original_names": original_names,
        "domain": DOMAIN_DOCINTEL,
        "grounding_contract": grounding_contract,
        "phase": 24,
    }

    # Optional passthrough if structured metadata exists
    if "structured" in arguments:
        enriched["structured"] = arguments["structured"]

    # DELEGATE TO SEMANTIC ENGINE — deterministic, left/right-free
    try:
        return semantic_exec(enriched)
    except Exception as e:
        logger.error(f"[multi_document_compare][Phase24] Engine failure: {e}")
        return {
            "ok": False,
            "result": str(e),
            "user_output": f"Comparison engine failed: {e}",
        }

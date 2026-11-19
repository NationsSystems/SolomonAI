# solomon_core/diagnostics/tier1_fact_exporter.py
# ---------------------------------------------------------------------------
# Tier-1 Fact Exporter
#
# Purpose:
#   Execute BEI extraction across documents and emit a deterministic
#   reconciliation-ready JSON file.
#
# This is NOT business logic.
# This is observability / plumbing.
#
# Phase 76 addition:
#   Replay stability verification.
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from typing import Dict, Any, List

from solomon_core.logger import get_logger
from solomon_core.solomon_core import execute_task
from solomon_core.docintel.reconciliation.bei_fact import (
    facts_from_tier1_evidence,
)

logger = get_logger("tier1_fact_exporter")


# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

BEI_DOCS_DIR = (
    PROJECT_ROOT
    / "tests"
    / "phase_72"
    / "resources"
    / "bei_docs"
)

OUTPUT_FILE = PROJECT_ROOT / "tests" / "tier1_output.json"
REPLAY_FILE = PROJECT_ROOT / "tests" / "tier1_output_replay.json"

PROMPT = "extract bid evidence from this document"


# ---------------------------------------------------------------------------

def _packet_payload(packet) -> Dict[str, Any]:
    payload = getattr(packet, "payload", None)
    if isinstance(payload, dict):
        return payload
    return {}


# ---------------------------------------------------------------------------

def _extract_evidence_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deterministic payload unwrap.

    ACCEPTED RUNTIME SHAPES

        payload["evidence"]
        payload["payload"]["evidence"]

    CANONICAL OUTPUT

        { signal_type: [items] }

    No inference.
    No synthesis.
    """

    # --------------------------------------------------
    # Shape A → direct
    # --------------------------------------------------
    evidence = payload.get("evidence")
    if isinstance(evidence, dict):
        return evidence

    # --------------------------------------------------
    # Shape B → nested under payload
    # --------------------------------------------------
    inner = payload.get("payload")
    if isinstance(inner, dict):
        nested = inner.get("evidence")
        if isinstance(nested, dict):
            return nested

    # --------------------------------------------------
    # Deterministic empty
    # --------------------------------------------------
    logger.warning("[EXPORT] no evidence in payload; downstream will be empty")
    return {}


# ---------------------------------------------------------------------------

def _run_once() -> Dict[str, Any]:
    pdfs = sorted(p for p in BEI_DOCS_DIR.iterdir() if p.suffix.lower() == ".pdf")

    documents: List[Dict[str, Any]] = []

    logger.info("[EXPORT] processing %s documents", len(pdfs))

    for pdf in pdfs:
        logger.info("[EXPORT] %s", pdf.name)

        execution_context: Dict[str, Any] = {
            "resolved_paths": [str(pdf)],
            "docs": [
                {
                    "document_id": pdf.name,
                    "original_name": pdf.name,
                }
            ],
            "explicit_intent": None,
        }

        packet = execute_task(
            task_text=PROMPT,
            execution_context=execution_context,
            conversation_id=f"tier1_export::{pdf.stem}",
        )

        payload = _packet_payload(packet)
        evidence = _extract_evidence_from_payload(payload)

        fact_set = facts_from_tier1_evidence(
            evidence=evidence,
            document_id=pdf.name,
            display_name=pdf.name,
        )

        documents.append(
            {
                "document_id": pdf.name,
                "facts": fact_set.to_dict(),
            }
        )

    return {"documents": documents}


# ---------------------------------------------------------------------------

def run():
    if not BEI_DOCS_DIR.exists():
        raise FileNotFoundError(f"BEI docs directory not found: {BEI_DOCS_DIR}")

    logger.info("[REPLAY] baseline run")
    first = _run_once()

    logger.info("[REPLAY] second run")
    second = _run_once()

    OUTPUT_FILE.write_text(json.dumps(first, indent=2), encoding="utf-8")
    REPLAY_FILE.write_text(json.dumps(second, indent=2), encoding="utf-8")

    if first != second:
        logger.error("[REPLAY FAILED] outputs differ")
        print("\n❌ REPLAY FAILED")
        print(f"Baseline → {OUTPUT_FILE}")
        print(f"Replay   → {REPLAY_FILE}\n")
        raise SystemExit(1)

    logger.info("[REPLAY PASSED] deterministic")
    print("\n✔ REPLAY PASSED — outputs identical")
    print(f"→ {OUTPUT_FILE}\n")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()

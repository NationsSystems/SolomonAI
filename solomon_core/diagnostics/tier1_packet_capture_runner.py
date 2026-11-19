# solomon_core/diagnostics/tier1_packet_capture_runner.py
# ---------------------------------------------------------------------------
# Tier-1 Packet Capture Runner
# ---------------------------------------------------------------------------
#
# Purpose:
#   Execute canonical prompts and persist RAW DocIntel packets.
#
# Output becomes the legal input for:
#   • Tier-1 validator
#   • reconciliation
#   • certification
#
# No formatting.
# No summarizing.
# No transformation.
# ---------------------------------------------------------------------------

import json
import sys
from pathlib import Path
from typing import Dict, Any, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from solomon_core.solomon_core import execute_task
from solomon_core.logger import get_logger
from tests.bei_auto_review.prompt_registry import CANONICAL_PROMPTS

logger = get_logger("tier1_packet_capture_runner")


# ---------------------------------------------------------------------------

BEI_DOCS_DIR = (
    PROJECT_ROOT
    / "tests"
    / "phase_72"
    / "resources"
    / "bei_docs"
)

OUTPUT_FILE = PROJECT_ROOT / "tests" / "tier1_output.json"


# ---------------------------------------------------------------------------

def _packet_to_dict(packet) -> Dict[str, Any]:
    """
    Lossless mechanical conversion.
    """
    if hasattr(packet, "to_dict"):
        return packet.to_dict()

    # fallback — structural copy
    return {
        "packet_type": getattr(getattr(packet, "header", None), "minimal", {}).packet_type
        if getattr(packet, "header", None)
        else None,
        "payload": getattr(packet, "payload", None),
        "verdict": getattr(packet, "verdict", None),
    }


# ---------------------------------------------------------------------------

def run():
    if not BEI_DOCS_DIR.exists():
        print(f"❌ BEI docs directory not found: {BEI_DOCS_DIR}")
        sys.exit(1)

    pdfs = sorted(p for p in BEI_DOCS_DIR.iterdir() if p.suffix.lower() == ".pdf")

    if not pdfs:
        print("❌ No PDF files found")
        sys.exit(1)

    documents: List[Dict[str, Any]] = []

    print("============================================================")
    print("Tier-1 Packet Capture")
    print(f"Documents: {len(pdfs)}")
    print(f"Prompts: {len(CANONICAL_PROMPTS)}")
    print("============================================================")

    for pdf in pdfs:
        print(f"\n--- Capturing: {pdf.name}")

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

        doc_packets = []

        for i, prompt in enumerate(CANONICAL_PROMPTS, start=1):
            print(f"   → Prompt {i:02d}")

            packet = execute_task(
                task_text=prompt,
                execution_context=execution_context,
                conversation_id=f"tier1_capture::{pdf.stem}::p{i:02d}",
            )

            doc_packets.append(_packet_to_dict(packet))

        documents.append(
            {
                "document_id": pdf.name,
                "packets": doc_packets,
            }
        )

    OUTPUT_FILE.write_text(json.dumps({"documents": documents}, indent=2))

    print("\n============================================================")
    print(f"✅ Packets written to: {OUTPUT_FILE}")
    print("============================================================")


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    run()

# solomon_core/diagnostics/tier1_packet_builder.py
# ---------------------------------------------------------------------------
# Tier-1 Packet Builder
#
# Purpose:
#   Convert Phase-72 text outputs into deterministic Tier-1 packets
#   consumable by validator → reconciliation → certification.
#
# Authority:
#   • Mechanical transformation only
#   • No inference
#   • No enrichment
#   • No interpretation
#
# Input:
#   tests/phase_72/outputs/**/bei_output.txt
#
# Output:
#   tests/tier1_output.json
# ---------------------------------------------------------------------------

import json
from pathlib import Path
from typing import List, Dict

from solomon_core.logger import get_logger

logger = get_logger("tier1_packet_builder")


# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]

SOURCE_ROOT = PROJECT_ROOT / "tests" / "phase_72" / "outputs"
DEST_FILE = PROJECT_ROOT / "tests" / "tier1_output.json"


# ---------------------------------------------------------------------------

SEPARATOR = "-" * 72


# ---------------------------------------------------------------------------

def _extract_atomic_lines(text: str) -> List[str]:
    """
    Extract bullet lines from Phase-72 output.
    No semantic processing.
    """
    lines = []
    for ln in text.splitlines():
        stripped = ln.strip()

        if not stripped:
            continue

        if stripped.startswith("*"):
            lines.append(stripped.lstrip("* ").strip())

    return lines


# ---------------------------------------------------------------------------

def _prompt_id_from_path(path: Path) -> str:
    """
    Deterministic classification dimension.

    Example:
        .../bei_doc/p03/bei_output.txt → p03
    """
    try:
        return path.parent.name
    except Exception:
        return "unknown_prompt"


# ---------------------------------------------------------------------------

def build():
    if not SOURCE_ROOT.exists():
        raise FileNotFoundError(f"Phase-72 outputs not found: {SOURCE_ROOT}")

    documents: List[Dict] = []

    for doc_dir in sorted(p for p in SOURCE_ROOT.iterdir() if p.is_dir()):
        doc_name = doc_dir.name
        facts = []

        ordinal = 0

        for output_file in sorted(doc_dir.rglob("bei_output.txt")):
            content = output_file.read_text(encoding="utf-8", errors="ignore")

            atomic_lines = _extract_atomic_lines(content)
            prompt_id = _prompt_id_from_path(output_file)

            for line in atomic_lines:
                ordinal += 1
                facts.append(
                    {
                        "signal_type": prompt_id,
                        "value": line,
                        "source_doc": doc_name,
                        "section_header": None,
                        "ordinal_position": ordinal,
                        "raw_text": line,
                    }
                )

        documents.append(
            {
                "document_id": doc_name,
                "facts": facts,
            }
        )

        logger.info(
            "[BUILDER] %s → %s facts",
            doc_name,
            len(facts),
        )

    payload = {"documents": documents}

    DEST_FILE.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    logger.info("[BUILDER] wrote %s", DEST_FILE)


# ---------------------------------------------------------------------------

if __name__ == "__main__":
    build()

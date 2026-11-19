# solomon_core/skills/semantic/compare_documents.py — Phase 39 DOCINTEL RELEASE-GRADE COMPARISON
# -------------------------------------------------------------------------------
# PHASE-39 — GROUNDED DOCINTEL MULTI-DOCUMENT COMPARISON (LEFT/RIGHT REMOVED)
#
# ROLE (CANONICAL — DO NOT VIOLATE):
#   • Deterministic document loading + text extraction
#   • Provide grounded, observable analysis only
#   • Emit facts, NEVER execution decisions
#   • NO orchestration
#   • NO execution gating
#   • NO inference beyond explicit text
#   • NO LLM usage
#
# Release-Grade Addition:
#   • Deterministic symmetric comparison across all documents
#   • Observable difference surfacing (claims + itemization density)
#   • Grounding preserved, no preferential ordering
# -------------------------------------------------------------------------------

import os
import re
from solomon_core.logger import get_logger
from solomon_core.skills.semantic.extract_text import execute as extract_text
from solomon_core.skills.semantic.extract_claims import execute as extract_claims
from solomon_core.domains import GENERIC_DOCUMENT

logger = get_logger("skill_compare_documents")

EXECUTION_AUTHORITY = False
SCHEMA_NAME = "DocumentCompare.Base.V39.3"
DOCINTEL_TYPE = GENERIC_DOCUMENT
MAX_CHARS = 20000

# ---------------------------------------------------------------
# DOCUMENT SELECTION (FACT-ONLY)
# ---------------------------------------------------------------
def _select_docs(arguments: dict):
    docs = arguments.get("docs")
    if not isinstance(docs, list):
        return []
    return [d for d in docs if isinstance(d, (str, dict))]

# ---------------------------------------------------------------
# EXTRACT TEXT + CLAIMS (DETERMINISTIC FEEDER)
# ---------------------------------------------------------------
def _extract_text_packet(doc_entry):
    pkt = extract_text({"docs": [doc_entry]})
    if not pkt.get("ok"):
        return None, "extract_text_failed"

    docs = pkt.get("docs")
    if not isinstance(docs, list) or not docs:
        return None, "no_document_packet"

    doc = docs[0]
    text = (doc.get("text") or "").strip()
    if not text:
        return None, "empty_text"

    if len(text) > MAX_CHARS:
        text = text[:MAX_CHARS] + "\n\n[Document truncated]\n"

    original_name = doc.get("original_name")
    display_name = doc.get("display_name")
    path = doc.get("path")

    if not original_name or not display_name or not path:
        return None, "missing_filename_fields"

    base_doc = {
        "path": path,
        "name": os.path.basename(path),
        "original_name": original_name,
        "display_name": display_name,
        "text": text,
        "structured": doc.get("structured", {}),
        "claims": doc.get("claims", []),
    }

    if not base_doc["claims"]:
        claim_pkt = extract_claims({"documents": [base_doc]})
        if (
            isinstance(claim_pkt, dict)
            and claim_pkt.get("ok")
            and isinstance(claim_pkt.get("documents"), list)
            and len(claim_pkt["documents"]) == 1
        ):
            base_doc["claims"] = claim_pkt["documents"][0].get("claims", [])

    return base_doc, None

# ---------------------------------------------------------------
# OBSERVABLE METRICS (NO INFERENCE)
# ---------------------------------------------------------------
def _count_itemization(text: str) -> int:
    if not text:
        return 0
    bullet_patterns = [r"^\s*[-•]\s+", r"^\s*\d+\.\s+"]
    count = 0
    for line in text.splitlines():
        for pat in bullet_patterns:
            if re.match(pat, line):
                count += 1
                break
    return count

# ---------------------------------------------------------------
# PRESENTATION — SINGLE DOCUMENT (RELEASE-GRADE)
# ---------------------------------------------------------------
def _render_single_document(p: dict) -> str:
    item_count = _count_itemization(p.get("text", ""))
    claim_count = len(p.get("claims") or [])

    lines = [
        f"Scope Summary — {p['original_name']}",
        "------------------------------",
        "The following summary reflects only what is explicitly stated within the document text.",
        "",
        f"- Explicitly itemized scope entries observed: {item_count}",
        f"- Discrete scope statements identified: {claim_count}",
        "",
        "Any scope of work not explicitly described or itemized in the document should be treated as not included.",
    ]
    return "\n".join(lines)

# ---------------------------------------------------------------
# PRESENTATION — MULTI-DOCUMENT COMPARISON (RELEASE-GRADE, LEFT/RIGHT REMOVED)
# ---------------------------------------------------------------
def _render_comparison(packets: list) -> str:
    lines = ["General Comparison", "-------------------"]

    metrics = {}
    for p in packets:
        item_count = _count_itemization(p.get("text", ""))
        claim_count = len(p.get("claims") or [])
        metrics[p["original_name"]] = {"item_count": item_count, "claim_count": claim_count}
        lines.append(
            f"- {p['original_name']}: scope explicitly stated; "
            f"{item_count} itemized entries observed; "
            f"{claim_count} discrete claims identified."
        )

    lines.append("\nExplicit Differences / Gaps")
    lines.append("--------------------------")

    names = list(metrics.keys())
    for i, doc_a in enumerate(names):
        claims_a = set(packets[i].get("claims", []))
        for j, doc_b in enumerate(names):
            if i == j:
                continue
            claims_b = set(packets[j].get("claims", []))
            unique_to_a = sorted(claims_a - claims_b)
            lines.append(f"\nClaims present in {doc_a} but not in {doc_b}:")
            lines.extend(f"- {c}" for c in unique_to_a) if unique_to_a else lines.append("- None")

    lines.append("\nNotes:")
    lines.append("- All items above are from explicit document statements.")
    lines.append("- No inference, interpretation, or recommendation performed.")
    lines.append("- Comparison is fully deterministic and left/right-free.")

    return "\n".join(lines)

# ---------------------------------------------------------------
# BASE EXECUTION — FACT EMISSION ONLY
# ---------------------------------------------------------------
def execute(arguments: dict):
    docs = _select_docs(arguments)
    packets = []
    failures = []

    for entry in docs:
        pkt, err = _extract_text_packet(entry)
        if err:
            failures.append(err)
        else:
            packets.append(pkt)

    reasoning_request = None
    if packets:
        reasoning_request = {
            "type": "document_base_synthesis",
            "schema": "ReasoningRequest.DocumentCompare.Base",
            "signal_only": True,
            "document_count": len(packets),
        }

    if len(packets) == 1:
        user_output = _render_single_document(packets[0])
    elif len(packets) > 1:
        user_output = _render_comparison(packets)
    else:
        user_output = None

    return {
        "ok": True,
        "schema": SCHEMA_NAME,
        "docintel_type": DOCINTEL_TYPE,
        "documents": packets,
        "failures": failures,
        "reasoning_request": reasoning_request,
        "result": None,
        "user_output": user_output,
        "facts": {
            "document_count": len(docs),
            "processed_count": len(packets),
            "failure_count": len(failures),
        },
    }

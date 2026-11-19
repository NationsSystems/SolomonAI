# solomon_core/skills/semantic/semantic_document_compare.py — Phase-38 GUI/Orchestrator Integration
# ------------------------------------------------------------------
# PHASE-38 — GROUNDED MULTI-DOCUMENT COMPARISON (LEFT/RIGHT ELIMINATION)
#
# ROLE:
#   • Consume document packets already approved by orchestrator
#   • Perform deterministic, claim-based comparison
#   • Emit grounded output for GUI
#   • NO execution gating
#   • NO LLM execution
# ------------------------------------------------------------------

from solomon_core.logger import get_logger
from solomon_core.skills.semantic.compare_documents import execute as base_compare
from solomon_core.skills.semantic.extract_claims import execute as extract_claims

logger = get_logger("semantic_document_compare")

SCHEMA = "DocumentCompare.Deep.Grounded.V38.0"

# ------------------------------------------------------------------
# Helpers (FACT-ONLY)
# ------------------------------------------------------------------

def _collect_docs(arguments: dict) -> list:
    docs = arguments.get("docs")
    if not isinstance(docs, list):
        return []
    return [d for d in docs if isinstance(d, (str, dict))]

def _normalize_packets(base_result: dict) -> list:
    for key in ("documents", "docs", "packets"):
        val = base_result.get(key)
        if isinstance(val, list):
            return val
    return []

def _collect_claims(packets: list) -> dict:
    out = {}
    for p in packets:
        name = p.get("display_name") or p.get("original_name") or p.get("file_path")
        claims = p.get("claims", [])
        if name:
            out[name] = claims if isinstance(claims, list) else []
    return out

def _coverage_summary(claims_by_doc: dict) -> str:
    lines = ["Explicit Coverage Summary:"]
    for doc, claims in claims_by_doc.items():
        lines.append(f"- {doc}: {len(claims)} explicit claims identified")
    return "\n".join(lines)

def _explicit_differences(claims_by_doc: dict) -> str:
    """
    Phase-38 deterministic comparison:
      - Compute all pairwise symmetric differences
      - No left/right assumptions
      - Report claims unique to each document explicitly
    """
    docs = list(claims_by_doc.keys())
    lines = ["Explicit Differences (Claim-Present in One Document Only):"]

    if len(docs) < 2:
        lines.append("Insufficient documents provided for claim comparison.")
        return "\n".join(lines)

    for i, doc_a in enumerate(docs):
        claims_a = set(claims_by_doc.get(doc_a, []))
        for j, doc_b in enumerate(docs):
            if i == j:
                continue
            claims_b = set(claims_by_doc.get(doc_b, []))
            unique_to_a = sorted(claims_a - claims_b)
            lines.append(f"\nClaims present in {doc_a} but not in {doc_b}:")
            lines.extend(f"- {c}" for c in unique_to_a) if unique_to_a else lines.append("- None")

    return "\n".join(lines)

def _explicit_notes() -> str:
    return (
        "Notes:\n"
        "- All items above are extracted from explicit document statements.\n"
        "- No inference, interpretation, or recommendation was performed.\n"
        "- Comparison is fully deterministic and left/right-free."
    )

# ------------------------------------------------------------------
# Entry Point — Phase-38 GUI-Ready
# ------------------------------------------------------------------

def execute(arguments: dict):
    logger.debug(
        "[semantic_document_compare] EXECUTE ENTER "
        f"arg_keys={list(arguments.keys())}"
    )

    docs = _collect_docs(arguments)

    # Base extraction (already orchestrator-approved)
    base = base_compare({"docs": docs})

    packets = _normalize_packets(base)
    if not packets:
        return {
            "ok": True,
            "schema": SCHEMA,
            "documents": [],
            "result": "No document packets available for grounded comparison.",
            "user_output": "No grounded comparison could be produced.",
            "facts": {
                "document_count": len(docs),
                "packet_count": 0,
                "claim_count": 0,
            },
        }

    # Claim enrichment
    claim_result = extract_claims({"documents": packets})
    enriched = claim_result.get("documents", packets)

    claims_by_doc = _collect_claims(enriched)
    total_claims = sum(len(v) for v in claims_by_doc.values())

    # Grounded output for GUI
    coverage = _coverage_summary(claims_by_doc)
    differences = _explicit_differences(claims_by_doc)
    notes = _explicit_notes()

    output_text = "\n\n".join([coverage, differences, notes])
    output_html = f"<pre>{output_text}</pre>"

    return {
        "ok": True,
        "schema": SCHEMA,
        "documents": enriched,
        "result": output_text,
        "user_output": output_html,
        "facts": {
            "document_count": len(docs),
            "packet_count": len(enriched),
            "claim_count": total_claims,
        },
    }

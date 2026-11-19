# ---------------------------------------------------------------------------
# FILE: docintel_execution_adapter.py
# DIRECTORY: solomon_core/presentation/
# ---------------------------------------------------------------------------
# Decision Object Construction Adapter
#
# Converts certified reconciliation structures into the canonical
# Decision Object consumed by the Presentation Authority layer.
#
# This module performs ZERO narration.
# ---------------------------------------------------------------------------

from typing import Dict, List, Any
import uuid
import re


class DocIntelExecutionAdapterError(Exception):
    pass


# ============================================================================
# Deterministic Severity Mapping
# ============================================================================
def _derive_severity(conflict: bool, multiplicity: bool) -> str:
    if conflict:
        return "CRITICAL"
    if multiplicity:
        return "HIGH"
    return "INFO"


# ============================================================================
# Currency Normalization
# ============================================================================
def _to_number(raw: str):
    """
    Convert currency string to float deterministically.

    Allowed:
      "$397,000.00" → 397000.0
      "397000"      → 397000.0

    If conversion fails → None.
    """
    if not raw:
        return None

    cleaned = re.sub(r"[^\d.\-]", "", str(raw))

    try:
        return float(cleaned)
    except Exception:
        return None


# ============================================================================
# Presentation Mode Resolver (AUTHORITATIVE — EVIDENCE BOUND)
# ============================================================================
def _derive_presentation_mode(findings: List[Dict[str, Any]]) -> str:
    """
    Deterministic authority decision.

    Rule:
        - If ANY certified findings exist → estimator
        - Otherwise → generic

    Uses ONLY certified reconciliation output.
    """
    if findings:
        return "estimator"
    return "generic"


# ============================================================================
# Public Adapter API
# ============================================================================

def adapt_docintel_execution(
    *,
    reasoning,
    user_task: str,
) -> Dict[str, Any]:
    """
    Transform DocIntel reasoning into a Decision Object.

    Read-only.
    Deterministic.
    """

    # ------------------------------------------------------------------
    # Deterministic normalization
    # ------------------------------------------------------------------
    if isinstance(reasoning, list):
        if len(reasoning) == 1 and isinstance(reasoning[0], dict):
            reasoning = reasoning[0]
        else:
            raise DocIntelExecutionAdapterError(
                "Reasoning payload list must contain exactly one dict"
            )

    if not isinstance(reasoning, dict):
        raise DocIntelExecutionAdapterError("Reasoning payload must be a dict")

    if reasoning.get("reasoning_type") != "docintel":
        raise DocIntelExecutionAdapterError(
            "Invalid or missing reasoning_type for DocIntel execution"
        )

    inputs = reasoning.get("inputs") or {}
    documents: List[Dict] = inputs.get("documents") or []
    reconciliation = reasoning.get("reconciliation")
    evidence = reasoning.get("evidence") or {}
    clean_user_task = str(user_task or "").strip()

    if reconciliation is None:
        raise DocIntelExecutionAdapterError(
            "Reconciliation artifact missing from reasoning payload"
        )

    if not documents:
        raise DocIntelExecutionAdapterError(
            "DocIntel reasoning contains no documents"
        )

    # ------------------------------------------------------------------
    # Build findings from buckets
    # ------------------------------------------------------------------
    findings: List[Dict[str, Any]] = []

    for bucket in reconciliation.get("buckets", []):
        conflict = bool(bucket.get("conflict"))
        multiplicity = bool(bucket.get("multiplicity"))

        findings.append(
            {
                "signal_type": bucket.get("signal_type"),
                "severity": _derive_severity(conflict, multiplicity),
                "conflict": conflict,
                "multiplicity": multiplicity,
                "facts": bucket.get("facts") or [],
            }
        )

    # ------------------------------------------------------------------
    # Commercial Visibility Transport (FROM EVIDENCE)
    # ------------------------------------------------------------------
    base_bids = []

    for d in documents:
        doc_id = d.get("document_id")
        display_name = d.get("display_name") or d.get("original_name")

        if not doc_id:
            continue

        doc_evidence = evidence.get(display_name) or evidence.get(doc_id) or {}
        base_bid = doc_evidence.get("base_bid_amount") or {}

        raw_value = base_bid.get("raw")
        if not raw_value:
            continue

        numeric_value = _to_number(raw_value)

        if numeric_value is None:
            continue

        base_bids.append(
            {
                "document_id": doc_id,
                "display_name": display_name,
                "raw": raw_value,
                "amount": numeric_value,
            }
        )

    # ------------------------------------------------------------------
    # Raw Text Transport
    # ------------------------------------------------------------------
    raw_text = evidence.get("raw_text")
    if not raw_text:
        for d in documents:
            display_name = d.get("display_name") or d.get("original_name")
            doc_id = d.get("document_id")
            doc_evidence = evidence.get(display_name) or evidence.get(doc_id) or {}
            raw_text = doc_evidence.get("raw_text")

            if raw_text:
                break

    # ------------------------------------------------------------------
    # Canonical Decision Object
    # ------------------------------------------------------------------
    decision_object = {
        "decision_id": str(uuid.uuid4()),
        "documents": [
            {
                "document_id": d.get("document_id"),
                "display_name": (
                    d.get("display_name")
                    or d.get("original_name")
                ),
            }
            for d in documents
            if isinstance(d, dict)
        ],
        "findings": findings,
        "presentation_mode": _derive_presentation_mode(findings),
    }

    if clean_user_task:
        decision_object["user_task"] = clean_user_task

    if base_bids:
        decision_object["commercials"] = {
            "base_bids": base_bids
        }

    if isinstance(raw_text, str) and raw_text.strip():
        decision_object["raw_text"] = raw_text

    return decision_object
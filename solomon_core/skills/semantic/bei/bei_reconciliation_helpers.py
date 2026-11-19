# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_reconciliation_helpers.py
# ---------------------------------------------------------------------------
# Phase-safe extraction
# Scout + Reconciliation helpers (pure, non-authoritative)
# NO behavior changes
# ---------------------------------------------------------------------------

from typing import Any, Dict, List, Optional


# ============================================================================
# Scout helpers (non-authoritative)
# ============================================================================
def _get_scout_candidates(arguments: dict) -> dict:
    ctx = arguments.get("execution_context") or {}
    candidates = ctx.get("scout_candidates")
    return candidates if isinstance(candidates, dict) else {}


def _count_items(obj) -> int:
    return len(obj) if isinstance(obj, list) else 0


def _scout_metrics(scout: dict) -> dict:
    if not scout:
        return {
            "price_lines": 0,
            "totals": 0,
            "scope_regions": 0,
            "exclusions": 0,
            "structural": 0,
        }

    return {
        "price_lines": _count_items(scout.get("price_lines")),
        "totals": _count_items(scout.get("totals")),
        "scope_regions": _count_items(scout.get("scope_regions")),
        "exclusions": _count_items(scout.get("exclusions")),
        "structural": _count_items(scout.get("structural_signals")),
    }


# ============================================================================
# Reconciliation helpers (non-authoritative)
# ============================================================================
def _doc_id(doc: dict) -> str:
    return str(
        doc.get("document_id")
        or doc.get("id")
        or doc.get("doc_id")
        or ""
    ).strip()


def _iter_buckets(reconciliation: dict | None) -> List[dict]:
    if not reconciliation:
        return []
    buckets = reconciliation.get("buckets", [])
    return buckets if isinstance(buckets, list) else []


def _bucket_for_signal(reconciliation: dict | None, signal_type: str) -> Optional[dict]:
    st = (signal_type or "").lower().strip()
    for b in _iter_buckets(reconciliation):
        if (b.get("signal_type") or "").lower().strip() == st:
            return b
    return None


def _facts_for_doc(bucket: dict | None, target_id: str) -> List[dict]:
    if not bucket or not target_id:
        return []
    facts = bucket.get("facts", [])
    if not isinstance(facts, list):
        return []
    return [
        f
        for f in facts
        if str(
            f.get("source_document_id")
            or f.get("source_doc_id")
            or ""
        ).strip()
        == target_id
    ]


def _extract_fact_excerpt(fact: dict) -> Optional[str]:
    """
    Deterministically recover an excerpt (if available) from:
      - fact.value.excerpt
      - fact.provenance.excerpt
      - fact.provenance.context (last resort)
    """
    if not isinstance(fact, dict):
        return None

    v = fact.get("value")
    if isinstance(v, dict):
        ex = v.get("excerpt")
        if isinstance(ex, str) and ex.strip():
            return ex.strip()

    prov = fact.get("provenance")
    if isinstance(prov, dict):
        ex2 = prov.get("excerpt")
        if isinstance(ex2, str) and ex2.strip():
            return ex2.strip()
        ctx = prov.get("context")
        if isinstance(ctx, str) and ctx.strip():
            return ctx.strip()

    return None


def _first_excerpt_for_doc(
    reconciliation: dict | None,
    doc: dict,
    signal_type: str,
) -> Optional[str]:
    target_id = _doc_id(doc)
    if not target_id:
        return None
    bucket = _bucket_for_signal(reconciliation, signal_type)
    facts = _facts_for_doc(bucket, target_id)
    for f in facts:
        ex = _extract_fact_excerpt(f)
        if ex:
            return ex
    return None


def _extract_base_bid_hint(
    reconciliation: dict | None,
    doc: dict,
) -> Optional[str]:
    target_id = _doc_id(doc)
    if not target_id:
        return None

    bucket = _bucket_for_signal(reconciliation, "base_bid")
    facts = _facts_for_doc(bucket, target_id)

    # local import to avoid circular risk
    from .bei_format_helpers import _normalize_currency_display

    for f in facts:
        v = f.get("value")
        if isinstance(v, str) and v.strip():
            return _normalize_currency_display(v)
        if isinstance(v, dict) and v.get("raw"):
            rv = str(v.get("raw") or "").strip()
            if rv:
                return _normalize_currency_display(rv)
    return None


def _has_signal_for_doc(
    reconciliation: dict | None,
    doc: dict,
    signal_type: str,
) -> bool:
    target_id = _doc_id(doc)
    if not target_id:
        return False
    bucket = _bucket_for_signal(reconciliation, signal_type)
    return bool(_facts_for_doc(bucket, target_id))


def _count_signal_for_doc(
    reconciliation: dict | None,
    doc: dict,
    signal_type: str,
) -> int:
    """Deterministic count of facts for a given signal."""
    target_id = _doc_id(doc)
    if not target_id:
        return 0
    bucket = _bucket_for_signal(reconciliation, signal_type)
    return len(_facts_for_doc(bucket, target_id))


def _presentation_derivations(reconciliation: dict | None) -> dict:
    if not isinstance(reconciliation, dict):
        return {}
    d = reconciliation.get("presentation_derivations")
    return d if isinstance(d, dict) else {}
# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/mechanical_resolution/administrative_precedence.py
# ---------------------------------------------------------------------------
# Deterministic mechanical elimination of reconciliation ambiguity.
#
# Runs AFTER reconciliation.
# Runs BEFORE human escalation.
#
# Authority:
#   • May REMOVE candidates.
#   • May NEVER invent or reinterpret Tier-1.
#
# If more than one candidate remains → escalation REQUIRED.
#
# Replay rule:
#   same inputs → same survivors.
# ---------------------------------------------------------------------------

from typing import Dict, List, Tuple, Any


ACTOR = "system_administrative_precedence"


# ============================================================================
# RULES
# ============================================================================

def _rule_single_document(candidates: List[Dict]) -> List[str]:
    docs = {c.get("source_document_id") for c in candidates}
    if len(docs) == 1:
        return list(docs)
    return []


def _rule_real_addendum_vs_placeholder(candidates: List[Dict]) -> List[str]:
    """
    If one document shows a real issued addendum and the other is
    merely a blank/template reference to addenda, prefer the real one.

    Deterministic signal:
        placeholder text often contains underscores or blanks.
    """

    real_docs = set()
    placeholder_docs = set()

    for c in candidates:
        doc_id = c.get("source_document_id")
        excerpt = (
            (c.get("value") or {}).get("excerpt")
            or (c.get("provenance") or {}).get("excerpt")
            or ""
        ).lower()

        if "addendum" in excerpt and "___" in excerpt:
            placeholder_docs.add(doc_id)
        else:
            real_docs.add(doc_id)

    if len(real_docs) == 1 and len(placeholder_docs) >= 1:
        return list(real_docs)

    return []


RULES = [
    ("single_document", _rule_single_document),
    ("issued_addendum_supersedes_placeholder", _rule_real_addendum_vs_placeholder),
]


# ============================================================================
# ENGINE
# ============================================================================

def try_resolve(
    reconciliation_artifact: Dict[str, Any],
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:

    buckets = reconciliation_artifact.get("buckets") or []
    audit_records: List[Dict[str, Any]] = []

    for bucket in buckets:
        if not bucket.get("conflict"):
            continue

        candidates = bucket.get("facts") or []

        if len(candidates) <= 1:
            continue

        original_docs = sorted(
            list({c.get("source_document_id") for c in candidates})
        )

        resolved = False

        for rule_name, rule_fn in RULES:
            survivors = rule_fn(candidates)

            if not survivors:
                continue

            new_candidates = [
                c for c in candidates if c.get("source_document_id") in survivors
            ]

            if len(new_candidates) == 1:
                winner = new_candidates[0].get("source_document_id")

                bucket["facts"] = new_candidates
                bucket["conflict"] = False
                bucket["multiplicity"] = False

                audit_records.append(
                    {
                        "bucket_signal_type": bucket.get("signal_type"),
                        "rule_used": rule_name,
                        "inputs_considered": original_docs,
                        "winning_document": winner,
                        "losing_documents": [
                            d for d in original_docs if d != winner
                        ],
                        "actor": ACTOR,
                    }
                )

                resolved = True
                break

        if not resolved:
            pass

    return reconciliation_artifact, audit_records

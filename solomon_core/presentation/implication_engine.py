# ---------------------------------------------------------------------------
# FILE: solomon_core/presentation/implication_engine.py
# ---------------------------------------------------------------------------
# Implication Engine
#
# Converts certified findings into implication tokens.
# Deterministic mapping only.
# ---------------------------------------------------------------------------

from typing import Dict, List, Any


# ============================================================================
# Implication Grant Table (v1 statute)
# ============================================================================
CRITICAL_TOKEN = "READINESS_NOT_ESTABLISHED"
HIGH_TOKEN = "HIGH_EXPOSURE"
DISAGREE_TOKEN = "DOCUMENTS_NOT_IN_AGREEMENT"
NO_VARIANCE_TOKEN = "NO_VARIANCE"


# ============================================================================
# Public API
# ============================================================================

def derive_implications(decision_object: Dict[str, Any]) -> List[str]:
    """
    Convert Decision Object → implication tokens.

    No inference.
    No summarization.
    No ranking.
    """

    findings = decision_object.get("findings") or []

    if not findings:
        return [NO_VARIANCE_TOKEN]

    tokens = set()

    for f in findings:
        severity = f.get("severity")
        conflict = bool(f.get("conflict"))

        if severity == "CRITICAL":
            tokens.add(CRITICAL_TOKEN)

        if severity == "HIGH":
            tokens.add(HIGH_TOKEN)

        if conflict:
            tokens.add(DISAGREE_TOKEN)

    if not tokens:
        tokens.add(NO_VARIANCE_TOKEN)

    return sorted(tokens)

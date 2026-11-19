# solomon_core/docintel/reconciliation/reconciliation_certifier.py
# ---------------------------------------------------------------------------
# Reconciliation Certifier
#
# Purpose:
#   • Validate structural integrity of reconciliation output
#   • Confirm Tier-1 lineage preservation
#   • Provide pass/fail readiness for professional review
#
# Authority:
#   • DOES NOT choose values
#   • DOES NOT resolve conflicts
#   • DOES NOT edit reconciliation
#
# Output:
#   Deterministic certification report
# ---------------------------------------------------------------------------

from typing import Dict, Any, List

from solomon_core.logger import get_logger

logger = get_logger("reconciliation_certifier")


# ---------------------------------------------------------------------------

REQUIRED_FACT_FIELDS = {
    "fact_type",
    "value",
    "source_document_id",
    "source_display_name",
}


# ---------------------------------------------------------------------------

def _check_lineage(fact: Dict[str, Any]) -> List[str]:
    missing = []
    for field in REQUIRED_FACT_FIELDS:
        if field not in fact:
            missing.append(field)
    return missing


# ---------------------------------------------------------------------------

def certify(reconciliation_artifact: Dict[str, Any]) -> Dict[str, Any]:
    failures = []
    total_facts = 0

    buckets = reconciliation_artifact.get("buckets") or []

    for bucket in buckets:
        facts = bucket.get("facts") or []

        for fact in facts:
            total_facts += 1
            missing = _check_lineage(fact)
            if missing:
                failures.append(
                    {
                        "fact_type": bucket.get("signal_type"),
                        "missing_fields": sorted(missing),
                    }
                )

    passed = len(failures) == 0

    result = {
        "passed": passed,
        "total_facts": total_facts,
        "failure_count": len(failures),
        "failures": failures,
    }

    logger.info(
        "[CERTIFIER] passed=%s facts=%s failures=%s",
        passed,
        total_facts,
        len(failures),
    )

    return result

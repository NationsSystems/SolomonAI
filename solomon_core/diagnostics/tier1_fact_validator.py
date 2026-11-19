# solomon_core/diagnostics/tier1_fact_validator.py
# ---------------------------------------------------------------------------
# Tier-1 Fact Validator
# ---------------------------------------------------------------------------
#
# Purpose:
#   Validate structural admissibility of Tier-1 facts AFTER packet
#   conversion and BEFORE reconciliation.
#
# Authority:
#   • Structure only
#   • No interpretation
#   • No linguistic judgment
#
# Failure here means:
#   facts cannot enter reconciliation court.
# ---------------------------------------------------------------------------

from typing import Dict, List, Any

from solomon_core.logger import get_logger

logger = get_logger("tier1_fact_validator")


# ---------------------------------------------------------------------------

REQUIRED_FIELDS = {
    "signal_type",
    "value",
    "source_doc",
    "section_header",
    "ordinal_position",
    "raw_text",
}


# ---------------------------------------------------------------------------

def _validate_fact(fact: Dict[str, Any]) -> List[Dict[str, Any]]:
    failures = []

    if not isinstance(fact, dict):
        return [{"type": "fact_not_dict"}]

    for field in REQUIRED_FIELDS:
        if field not in fact:
            failures.append(
                {
                    "type": "missing_field",
                    "field": field,
                }
            )

    if "value" in fact and (fact["value"] is None or str(fact["value"]).strip() == ""):
        failures.append({"type": "empty_value"})

    if "ordinal_position" in fact and not isinstance(fact["ordinal_position"], int):
        failures.append({"type": "ordinal_not_int"})

    return failures


# ---------------------------------------------------------------------------

def validate(dataset: Dict[str, Any]) -> Dict[str, Any]:
    documents = dataset.get("documents") or []

    doc_failures = []
    total = 0

    for i, doc in enumerate(documents, start=1):
        facts = doc.get("facts") or []

        failures = []

        for fact in facts:
            total += 1
            failures.extend(_validate_fact(fact))

        if failures:
            doc_failures.append(
                {
                    "index": i,
                    "failure_count": len(failures),
                    "failures": failures,
                }
            )

    passed = len(doc_failures) == 0

    result = {
        "documents": len(documents),
        "total_facts": total,
        "failed_documents": len(doc_failures),
        "passed": passed,
        "details": doc_failures,
    }

    logger.info(
        "[FACT VALIDATOR] docs=%s facts=%s failed=%s",
        len(documents),
        total,
        len(doc_failures),
    )

    return result

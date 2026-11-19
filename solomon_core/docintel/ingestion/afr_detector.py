# solomon_core/docintel/ingestion/afr_detector.py
# ---------------------------------------------------------------------------
# Admissible Fact Record (AFR) Detector
# ---------------------------------------------------------------------------
# PURPOSE
#   Deterministic, bounded, read-only observation of document text.
#
# CONSTRAINTS
#   • No inference
#   • No classification
#   • No routing
#   • No LLM
#   • Reproducible
#
# OUTPUT
#   Presence signals only.
# ---------------------------------------------------------------------------

from typing import Dict, List
from solomon_core.logger import get_logger

logger = get_logger("docintel.afr")


# ---------------------------------------------------------------------------
# BUDGET GUARDRAILS
# ---------------------------------------------------------------------------

MAX_PAGES = 50
MAX_CHARS = 200_000  # hard ceiling across document


# ---------------------------------------------------------------------------
# TOKEN FAMILIES (v1 — MINIMAL)
# ---------------------------------------------------------------------------

CURRENCY_TOKENS = [
    "$",
    "usd",
    "dollar",
    "price",
    "cost",
    "lump sum",
    "unit price",
    "base bid",
    "total bid",
]

SCOPE_TOKENS = [
    "scope of work",
    "work includes",
    "shall provide",
    "furnish",
    "install",
    "perform",
    "contractor shall",
]

EXCLUSION_TOKENS = [
    "exclude",
    "not included",
    "by others",
    "nic",
]

ADDENDA_TOKENS = [
    "addendum",
    "addenda",
    "revision",
    "amendment",
    "issued by",
    "clarification",
]

SCHEDULE_TOKENS = [
    "calendar days",
    "substantial completion",
    "completion date",
    "duration",
    "contract time",
]

SIGNATURE_TOKENS = [
    "signed",
    "signature",
    "by:",
    "title:",
    "date:",
    "witness",
]

SPEC_TOKENS = [
    "section",
    "division",
    "part 1",
    "part 2",
    "part 3",
    "technical specifications",
]

CONTRACT_TOKENS = [
    "hereinafter",
    "whereas",
    "party of the first part",
    "agreement",
    "terms and conditions",
]

BID_FORM_TOKENS = [
    "bid form",
    "proposal form",
    "acknowledgment",
    "certification",
]


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _bounded_text(text: str) -> str:
    if not text:
        return ""
    return text[:MAX_CHARS]


def _contains_any(text: str, tokens: List[str]) -> bool:
    if not text:
        return False
    lower = text.lower()
    return any(t in lower for t in tokens)


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def build_afr_for_documents(documents: List[Dict]) -> Dict:
    """
    documents: list of {"document_id": str, "text": str}
    """

    logger.info("[AFR] start")

    try:
        combined_text_parts = []

        for doc in documents[:MAX_PAGES]:
            combined_text_parts.append(doc.get("text") or "")

        combined_text = _bounded_text("\n".join(combined_text_parts))

        # Extremely cheap density heuristic
        ocr_required = len(combined_text.strip()) < 100

        afr = {
            "page_count": len(documents),
            "contains_currency": _contains_any(combined_text, CURRENCY_TOKENS),
            "contains_scope_terms": _contains_any(combined_text, SCOPE_TOKENS),
            "contains_exclusion_terms": _contains_any(combined_text, EXCLUSION_TOKENS),
            "contains_addenda_terms": _contains_any(combined_text, ADDENDA_TOKENS),
            "contains_schedule_terms": _contains_any(combined_text, SCHEDULE_TOKENS),
            "contains_signature_blocks": _contains_any(combined_text, SIGNATURE_TOKENS),
            "contains_specification_format": _contains_any(combined_text, SPEC_TOKENS),
            "contains_contract_language": _contains_any(combined_text, CONTRACT_TOKENS),
            "contains_bid_form_terms": _contains_any(combined_text, BID_FORM_TOKENS),
            "ocr_required": ocr_required,
        }

        logger.info("[AFR] complete")
        logger.info("[AFR] flags: %s", afr)

        return afr

    except Exception as e:
        logger.warning("[AFR] failure: %s", str(e))
        return {}

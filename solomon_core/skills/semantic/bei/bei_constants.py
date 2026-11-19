# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_constants.py
# ---------------------------------------------------------------------------

from solomon_core.domains import DOMAIN_BID

SCHEMA_NAME = "BEI.Document.Extract.v1"
DOCINTEL_TYPE = DOMAIN_BID
MAX_CHARS = 32000

FIELDS = [
    "bid_date",
    "issuing_party",
    "base_bid_amount",
    "scope_of_work_summary",
    "inclusions",
    "exclusions",
    "alternates",
    "assumptions_and_clarifications",
    "schedule_or_duration_terms",
    "special_conditions_or_risks",
]
# solomon_core/skills/semantic/extract_claims.py — Phase-38 GUI-Ready
# ---------------------------------------------------------------
# SIGNAL-ONLY Explicit Claim + Scope Unit Extraction Micro-Skill
# ---------------------------------------------------------------

import re
from solomon_core.logger import get_logger

logger = get_logger("skill_extract_claims")

SCHEMA = "DocumentClaims.Explicit.V38"

# ---------------------------------------------------------------
# SENTENCE SPLITTER (CONSERVATIVE)
# ---------------------------------------------------------------
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")

# ---------------------------------------------------------------
# CLAIM SIGNAL PATTERNS (DECLARATIVE)
# ---------------------------------------------------------------
CLAIM_PATTERNS = [
    r"\b(will|shall|must|is required to|is responsible for)\b",
    r"\b(deliver|provide|install|supply|include|perform)\b",
    r"\$\s*\d",
    r"\b(cost|price|fee|total|amount)\b",
    r"\b(within|no later than|by)\s+\d+\s*(days|weeks|months)\b",
    r"\b(on or before|by)\s+[A-Z][a-z]+\s+\d{1,2},\s*\d{4}\b",
    r"\b(exclude|does not include|not included|outside the scope)\b",
]

_COMPILED_PATTERNS = [re.compile(pat, re.IGNORECASE) for pat in CLAIM_PATTERNS]

# ---------------------------------------------------------------
# SCOPE UNIT PATTERNS (BULLETS / LIST ITEMS)
# ---------------------------------------------------------------
BULLET_RE = re.compile(
    r"^\s*(?:[-•*‣▪◦]|(\d+\.))\s+(.*\S)",
    re.MULTILINE
)

SECTION_HEADER_RE = re.compile(
    r"^\s*(scope of work|scope|included services|deliverables|services included)\s*$",
    re.IGNORECASE | re.MULTILINE
)

# ---------------------------------------------------------------
# EXTRACT DECLARATIVE CLAIMS
# ---------------------------------------------------------------
def _extract_sentence_claims(text: str):
    claims = []
    sentences = _SENTENCE_RE.split(text)
    for sent in sentences:
        s = sent.strip()
        if len(s) < 20:
            continue
        for pat in _COMPILED_PATTERNS:
            if pat.search(s):
                claims.append(s)
                break
    return claims

# ---------------------------------------------------------------
# EXTRACT SCOPE UNITS (BULLETS / LIST ITEMS)
# ---------------------------------------------------------------
def _extract_scope_units(text: str):
    units = []
    for match in BULLET_RE.finditer(text):
        item = match.group(2).strip()
        if len(item) >= 10:
            units.append(item)
    return units

# ---------------------------------------------------------------
# SIGNAL-ONLY EXECUTION ENTRYPOINT
# ---------------------------------------------------------------
def execute(arguments: dict):
    """
    Phase-38 GUI-Ready:

    Accepts:
        arguments["documents"] or arguments["packets"]

    Returns:
        reasoning request packet(s) for GUI/orchestrator
    """

    documents = arguments.get("documents") or arguments.get("packets")

    if not isinstance(documents, list) or not documents:
        return {
            "ok": False,
            "schema": SCHEMA,
            "result": "No documents supplied for claim extraction.",
            "user_output": "Attach documents to extract explicit claims and scope units.",
        }

    reasoning_requests = []

    for doc in documents:
        text = doc.get("text", "")
        if not isinstance(text, str):
            text = ""

        sentence_claims = _extract_sentence_claims(text)
        scope_units = _extract_scope_units(text)

        # ---------------------------------------------------
        # Phase-38: Emit reasoning request for GUI display
        # ---------------------------------------------------
        reasoning_request = {
            "reasoning_type": "extract_claims",
            "schema": SCHEMA,
            "inputs": {
                "filename": doc.get("name") or doc.get("file_name") or "unknown",
                "text": text,
                "sentence_claims": sentence_claims,
                "scope_units": scope_units,
            },
            "constraints": {
                "no_execution": True,
                "requires_orchestrator": True,
            },
            "expected_outputs": ["documents", "user_output"],
        }

        reasoning_requests.append(reasoning_request)

    return {
        "ok": True,
        "schema": SCHEMA,
        "result": reasoning_requests,
        "user_output": "Reasoning request(s) generated (execution deferred to orchestrator)."
    }

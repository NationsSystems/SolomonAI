# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_helpers.py
# ---------------------------------------------------------------------------

import re
from typing import Any, Dict, List, Optional

from .bei_constants import MAX_CHARS

_SCOPE_NOISE = {
    "addenda:",
    "bid #1",
    "drawings dated:",
}


def select_document_set(arguments: dict) -> Optional[List[dict]]:
    docs = arguments.get("documents") or arguments.get("document_set")
    if isinstance(docs, list) and docs:
        return docs
    return None


def resolve_doc_name(doc: dict) -> str:
    return (
        doc.get("display_name")
        or doc.get("filename")
        or doc.get("name")
        or doc.get("document_id")
        or "Unknown Document"
    )


def safe_text(doc: dict) -> str:
    text = (doc.get("text") or "").strip()
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + "\n\n[Document truncated]\n"
    return text


def stable_list(values: List[str]) -> List[str]:
    return sorted(dict.fromkeys(v.strip() for v in values if v and v.strip()))


def is_pure_date(line: str) -> bool:
    return bool(re.fullmatch(r"\d{1,2}/\d{1,2}/\d{2,4}", line.strip()))


def looks_like_section_break(line: str) -> bool:
    return bool(
        re.match(
            r"^(Clarifications|General Exclusions|Additional Notes|Pricing|Proposal|Terms)",
            line,
            re.I,
        )
    )


def contains_duration_unit(line: str) -> bool:
    return bool(
        re.search(r"\b\d+\s+(hour|hours|day|days|week|weeks)\b", line, re.I)
    )


def is_scope_noise(line: str) -> bool:
    low = line.strip().lower()
    if low in _SCOPE_NOISE:
        return True
    if re.fullmatch(r"\d+", low):
        return True
    return False


def is_term_noise(line: str) -> bool:
    low = line.strip().lower()
    if low in {"thanks", "thank you"}:
        return True
    if "please let me know" in low:
        return True
    return False
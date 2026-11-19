# solomon_core/docintel/extractors/explicit_section_extractor.py
# ---------------------------------------------------------------------------
# DocIntel Section Extractor — Explicit Headings Only
# ---------------------------------------------------------------------------

from typing import List, Dict
import re


# ---------------------------------------------------------------------------
# Canonical Section Headings (EXPLICIT MATCH ONLY)
# ---------------------------------------------------------------------------

SECTION_PATTERNS = {
    "scope": [
        "scope of work",
        "work scope",
        "scope of the work",
        "the work",
    ],
    "inclusions": [
        "inclusions",
        "this bid includes",
    ],
    "exclusions": [
        "exclusions",
        "this bid excludes",
        "general exclusions",
    ],
    "alternates": [
        "alternates",
        "add alternates",
        "deduct alternates",
    ],
    "allowances": [
        "allowances",
        "allowance",
    ],
    "addenda": [
        "addenda",
        "addendum",
    ],
    "signature": [
        "accepted by",
        "authorized signature",
        "acceptance",
    ],
}


# ---------------------------------------------------------------------------
# Prefix grammar (still explicit)
# ---------------------------------------------------------------------------

PREFIX_PATTERN = re.compile(
    r"^(section|article)?\s*\d*[\.\-–]*\s*",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_sections(
    *,
    document_id: str,
    document_text: str,
) -> List[Dict]:

    if not document_text or not isinstance(document_text, str):
        return []

    results: List[Dict] = []
    seen_section_types = set()

    lines = document_text.splitlines()

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        # remove legal numeric prefixes
        normalized = PREFIX_PATTERN.sub("", line).strip().lower()

        for section_type, patterns in SECTION_PATTERNS.items():
            if section_type in seen_section_types:
                continue

            for pattern in patterns:
                if (
                    normalized == pattern
                    or normalized.startswith(pattern + " ")
                    or normalized.startswith(pattern + ":")
                ):
                    excerpt = _build_excerpt(lines, idx)

                    results.append({
                        "section_type": section_type,
                        "document_id": document_id,
                        "page_index": None,
                        "matched_heading": line,
                        "excerpt": excerpt,
                    })

                    seen_section_types.add(section_type)
                    break

    return results


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_excerpt(lines: List[str], start_idx: int, window: int = 6) -> str:
    end = min(len(lines), start_idx + window)
    snippet = lines[start_idx:end]
    return "\n".join(s.strip() for s in snippet if s.strip())

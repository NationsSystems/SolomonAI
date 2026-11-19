# ------------------------------------------------------------------
# FILE: solomon_ai_continuation_policy.py
# DIRECTORY: solomon_core/presentation/
# ------------------------------------------------------------------
# SolomonAI Continuation Policy
#
# PURPOSE
#   Decide whether a completed Solomon answer should receive optional
#   continuation UI and, when it should, which governed continuation mode
#   applies.
#
# CONTRACT
#   - Runs only after the substantive lane answer exists
#   - Presentation-only; never routes, authorizes, retrieves, or changes facts
#   - Deterministic and bounded; no LLM call is required to choose a mode
#   - Does not generate bridge text or suggestion language
#   - Favors no continuation for terminal, exact-format, factual, arithmetic,
#     confirmation, correction, transformation, and service-status responses
#   - Uses continuation chips for useful explanatory follow-up
#   - Uses bridge plus chips for genuinely exploratory or decision-oriented work
#   - Uses resolution chips when the completed answer exposes an ambiguity,
#     conflict, or missing-evidence boundary that the user can meaningfully
#     resolve
#   - When uncertain, chooses NONE so unnecessary generation is avoided
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Dict


CONTINUATION_NONE = "none"
CONTINUATION_CONTINUE = "continue"
CONTINUATION_EXPLORE = "explore"
CONTINUATION_RESOLVE = "resolve"

_SUPPORTED_MODES = frozenset({
    CONTINUATION_NONE,
    CONTINUATION_CONTINUE,
    CONTINUATION_EXPLORE,
    CONTINUATION_RESOLVE,
})


@dataclass(frozen=True)
class ContinuationDecision:
    """Deterministic presentation decision for one completed response."""

    mode: str
    reason: str
    bridge_required: bool
    minimum_suggestions: int
    maximum_suggestions: int


_EXACT_OUTPUT_PATTERN = re.compile(
    (
        r"\b(?:exactly\s+)?"
        r"(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"(?:\s+[a-z0-9'-]+){0,7}\s+"
        r"(?:sentence|sentences|bullet|bullets|bullet-point|bullet-points|"
        r"line|lines|item|items|word|words)\b"
    ),
    re.IGNORECASE,
)
_MAX_OUTPUT_PATTERN = re.compile(
    (
        r"\b(?:no|not)\s+more\s+than\s+"
        r"(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)\s+"
        r"(?:sentence|sentences|word|words|lines?)\b"
    ),
    re.IGNORECASE,
)
_HYPHENATED_EXACT_OUTPUT_PATTERN = re.compile(
    (
        r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"[-\s]+(?:sentence|sentences|bullet|bullets|bullet-point|"
        r"bullet-points|line|lines|item|items|word|words)\b"
    ),
    re.IGNORECASE,
)
_TERMINAL_REQUEST_PATTERNS = (
    re.compile(r"\bconfirm\s+only\b", re.IGNORECASE),
    re.compile(r"\bmention\s+only\b", re.IGNORECASE),
    re.compile(r"\bstate\s+only\b", re.IGNORECASE),
    re.compile(r"\breturn\s+only\b", re.IGNORECASE),
    re.compile(r"\banswer\s+(?:only\s+)?yes\s+or\s+no\b", re.IGNORECASE),
    re.compile(r"\bshow\s+the\s+(?:math|calculation)\b", re.IGNORECASE),
    re.compile(r"\bshow\s+(?:the\s+)?math\s+briefly\b", re.IGNORECASE),
    re.compile(r"\bcalculate\b", re.IGNORECASE),
    re.compile(r"\bfinal\s+amount\b", re.IGNORECASE),
    re.compile(r"\brewrite\b", re.IGNORECASE),
    re.compile(r"\bprofessional\s+email\b", re.IGNORECASE),
    re.compile(r"\bcorrection\s*:", re.IGNORECASE),
    re.compile(r"\bfinal\s+correction\b", re.IGNORECASE),
    re.compile(r"\bconfirm\b", re.IGNORECASE),
)
_EXPLORATORY_PATTERNS = (
    re.compile(r"\bwhat\s+else\b", re.IGNORECASE),
    re.compile(r"\bwhat\s+next\b", re.IGNORECASE),
    re.compile(r"\bnext\s+steps?\b", re.IGNORECASE),
    re.compile(r"\balternatives?\b", re.IGNORECASE),
    re.compile(r"\boptions?\b", re.IGNORECASE),
    re.compile(r"\brisks?\b", re.IGNORECASE),
    re.compile(r"\btrade[-\s]?offs?\b", re.IGNORECASE),
    re.compile(r"\bcompar(?:e|ing|ison)\b", re.IGNORECASE),
    re.compile(r"\banaly(?:ze|sis|zing)\b", re.IGNORECASE),
    re.compile(r"\bdiagnos(?:e|is|ing)\b", re.IGNORECASE),
    re.compile(r"\bstrateg(?:y|ic|ize)\b", re.IGNORECASE),
    re.compile(r"\bplan(?:ning)?\b", re.IGNORECASE),
    re.compile(r"\brecommend(?:ation|ations|ed|ing)?\b", re.IGNORECASE),
    re.compile(r"\bevaluat(?:e|ion|ing)\b", re.IGNORECASE),
    re.compile(r"\bpriorit(?:y|ize|ization|izing)\b", re.IGNORECASE),
    re.compile(r"\bimplications?\b", re.IGNORECASE),
    re.compile(r"\bscenarios?\b", re.IGNORECASE),
)
_CONTINUE_PATTERNS = (
    re.compile(r"\bwhat\s+changed\b", re.IGNORECASE),
    re.compile(r"\bexplain\b", re.IGNORECASE),
    re.compile(r"\bhelp\s+me\s+understand\b", re.IGNORECASE),
    re.compile(r"\bwalk\s+me\s+through\b", re.IGNORECASE),
    re.compile(r"\boverview\b", re.IGNORECASE),
    re.compile(r"\bhow\s+(?:does|do|can|would)\b", re.IGNORECASE),
    re.compile(r"\bwhy\b", re.IGNORECASE),
    re.compile(r"\bdescribe\b", re.IGNORECASE),
)
_SIMPLE_FACT_PATTERN = re.compile(
    (
        r"^\s*(?:new\s+topic\s*:\s*)?"
        r"(?:who\b|when\b|where\b|how\s+many\b|"
        r"what\s+(?:is|are|was|were)\b|which\b|is\b|does\b|did\b|can\b)"
    ),
    re.IGNORECASE,
)
_RESOLUTION_ANSWER_PATTERNS = (
    re.compile(r"\bcould\s+you\s+(?:clarify|specify|confirm)\b", re.IGNORECASE),
    re.compile(r"\bplease\s+(?:clarify|specify|confirm)\b", re.IGNORECASE),
    re.compile(r"\bwhich\s+.*\s+do\s+you\s+mean\b", re.IGNORECASE),
    re.compile(r"\bI\s+need\s+.*\s+to\s+(?:answer|determine|continue)\b", re.IGNORECASE),
    re.compile(r"\bcannot\s+determine\b", re.IGNORECASE),
    re.compile(r"\bcan['’]?t\s+determine\b", re.IGNORECASE),
    re.compile(r"\bnot\s+(?:provided|specified|established|available|stated)\b", re.IGNORECASE),
    re.compile(r"\bhas\s+not\s+been\s+established\b", re.IGNORECASE),
    re.compile(r"\bconflict(?:ing)?\b", re.IGNORECASE),
    re.compile(r"\bunknown\b", re.IGNORECASE),
    re.compile(r"\bmissing\b", re.IGNORECASE),
    re.compile(r"\binsufficient\s+information\b", re.IGNORECASE),
    re.compile(r"\bnot\s+enough\s+information\b", re.IGNORECASE),
)
_DATA_STATUS_CATEGORIES = frozenset({
    "weather",
    "sports",
})

_SERVICE_STATUS_PATTERNS = (
    re.compile(r"\btemporarily\s+unavailable\b", re.IGNORECASE),
    re.compile(r"\bother\s+workspace\s+features\s+are\s+unaffected\b", re.IGNORECASE),
    re.compile(r"\bno\s+web\s+information\s+available\b", re.IGNORECASE),
)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _word_count(value: str) -> int:
    return len(
        [
            word
            for word in re.findall(r"\S+", value)
            if word
        ]
    )


def _matches_any(value: str, patterns) -> bool:
    return any(pattern.search(value) for pattern in patterns)


def _decision(
    mode: str,
    reason: str,
) -> ContinuationDecision:
    if mode not in _SUPPORTED_MODES:
        mode = CONTINUATION_NONE
        reason = "unsupported_mode"

    if mode == CONTINUATION_EXPLORE:
        return ContinuationDecision(
            mode=mode,
            reason=reason,
            bridge_required=True,
            minimum_suggestions=2,
            maximum_suggestions=3,
        )

    if mode in {
        CONTINUATION_CONTINUE,
        CONTINUATION_RESOLVE,
    }:
        return ContinuationDecision(
            mode=mode,
            reason=reason,
            bridge_required=False,
            minimum_suggestions=1,
            maximum_suggestions=3,
        )

    return ContinuationDecision(
        mode=CONTINUATION_NONE,
        reason=reason,
        bridge_required=False,
        minimum_suggestions=0,
        maximum_suggestions=0,
    )


def _is_terminal_request(request_text: str) -> bool:
    if not request_text:
        return True

    if _EXACT_OUTPUT_PATTERN.search(request_text):
        return True

    if _MAX_OUTPUT_PATTERN.search(request_text):
        return True

    if _HYPHENATED_EXACT_OUTPUT_PATTERN.search(
        request_text
    ):
        return True

    return _matches_any(
        request_text,
        _TERMINAL_REQUEST_PATTERNS,
    )


def _looks_like_simple_fact_request(request_text: str) -> bool:
    if not _SIMPLE_FACT_PATTERN.search(request_text):
        return False

    if _matches_any(
        request_text,
        _EXPLORATORY_PATTERNS,
    ):
        return False

    return _word_count(request_text) <= 24


def _answer_exposes_resolution_boundary(
    answer_text: str,
    payload: Dict[str, Any],
) -> bool:
    support_status = _clean_text(
        payload.get("support_status")
    ).lower()

    if support_status == "not_established":
        return True

    if _matches_any(
        answer_text,
        _RESOLUTION_ANSWER_PATTERNS,
    ):
        return True

    return (
        answer_text.endswith("?")
        and _word_count(answer_text) <= 80
    )


def decide_solomon_ai_continuation(
    *,
    original_request: str,
    payload: Dict[str, Any],
) -> ContinuationDecision:
    """
    Return one deterministic continuation mode for a completed answer.

    The matrix is intentionally conservative. Exact-output and transactional
    requests terminate cleanly. Resolution boundaries are surfaced only when
    the user's own scope does not explicitly require a strict terminal answer.
    Exploratory and explanatory requests may receive optional continuation UI.
    """

    request_text = _clean_text(original_request)
    answer_text = _clean_text(
        payload.get("answer")
        or payload.get("assistant_answer")
    )

    if not answer_text:
        return _decision(
            CONTINUATION_NONE,
            "answer_absent",
        )

    if _matches_any(
        answer_text,
        _SERVICE_STATUS_PATTERNS,
    ):
        return _decision(
            CONTINUATION_NONE,
            "service_or_empty_status",
        )

    if _is_terminal_request(request_text):
        return _decision(
            CONTINUATION_NONE,
            "terminal_request",
        )

    ui_actions = payload.get("ui_actions")

    if isinstance(ui_actions, list) and any(
        isinstance(item, dict)
        for item in ui_actions
    ):
        return _decision(
            CONTINUATION_NONE,
            "deterministic_actions_present",
        )

    if _answer_exposes_resolution_boundary(
        answer_text,
        payload,
    ):
        return _decision(
            CONTINUATION_RESOLVE,
            "resolution_boundary",
        )

    if _matches_any(
        request_text,
        _EXPLORATORY_PATTERNS,
    ):
        return _decision(
            CONTINUATION_EXPLORE,
            "exploratory_request",
        )

    source_grounded = bool(
        payload.get("source_grounded")
    )

    if source_grounded:
        if _looks_like_simple_fact_request(
            request_text
        ):
            return _decision(
                CONTINUATION_NONE,
                "source_grounded_simple_fact",
            )

        return _decision(
            CONTINUATION_EXPLORE,
            "source_grounded_synthesis",
        )

    if _matches_any(
        request_text,
        _CONTINUE_PATTERNS,
    ):
        return _decision(
            CONTINUATION_CONTINUE,
            "explanatory_request",
        )

    category = _clean_text(
        payload.get("category")
    ).lower()

    if category:
        return _decision(
            CONTINUATION_NONE,
            (
                "data_status_response"
                if category in _DATA_STATUS_CATEGORIES
                else "data_surface_default"
            ),
        )

    if _looks_like_simple_fact_request(
        request_text
    ):
        return _decision(
            CONTINUATION_NONE,
            "simple_fact_request",
        )

    if _word_count(answer_text) >= 90:
        return _decision(
            CONTINUATION_CONTINUE,
            "substantive_open_response",
        )

    return _decision(
        CONTINUATION_NONE,
        "no_material_continuation",
    )


__all__ = [
    "CONTINUATION_CONTINUE",
    "CONTINUATION_EXPLORE",
    "CONTINUATION_NONE",
    "CONTINUATION_RESOLVE",
    "ContinuationDecision",
    "decide_solomon_ai_continuation",
]

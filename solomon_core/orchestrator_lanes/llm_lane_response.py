# ------------------------------------------------------------------
# FILE: llm_lane_response.py
# DIRECTORY: solomon_core/orchestrator_lanes/
# ------------------------------------------------------------------
# LLM Lane Response Helpers
#
# PURPOSE
#   Extract and normalize the substantive assistant answer plus any
#   model-authored presentation fields produced by the bounded LLM path.
#
# CONTRACT
#   - Response parsing only
#   - Does not generate or rewrite bridge language
#   - Does not generate or supplement suggestion chips
#   - Does not select UI actions
#   - Does not route or authorize execution
#   - Supports canonical and compact transport field names
#   - Preserves an explicit empty presentation shape for direct responses
#   - Preserves bridge and suggestions only as one complete paired shape
#   - Bounds extra suggestions to the canonical count
#   - Bounds overlong suggestions using only their original leading words
#   - Removes dangling trailing fragments created by word-bound clipping
#   - Preserves answer-only recovery when presentation output is malformed
#   - Repairs only a missing first bullet marker when the current request
#     explicitly requires bullets, all following answer lines are bullets,
#     and the repair completes the exact requested bullet count when specified
#   - Repairs one two-sentence boundary into a semicolon only when the request
#     explicitly requires one sentence and the second sentence begins with a
#     joinable pronoun or determiner
# ------------------------------------------------------------------

from __future__ import annotations

import json
import re
from typing import Any


_PRESENTATION_SUGGESTION_LIMIT = 3
_PRESENTATION_SUGGESTION_WORD_LIMIT = 8

_BULLET_REQUEST_PATTERN = re.compile(
    r"\b(?:bullet|bullets|bullet-point|bullet-points)\b",
    re.IGNORECASE,
)
_BULLET_LINE_PATTERN = re.compile(
    r"^\s*-\s+\S",
)
_EXACT_BULLET_COUNT_PATTERN = re.compile(
    (
        r"\bexactly\s+"
        r"(?P<count>one|two|three|four|five|six|seven|eight|nine|ten|\d+)"
        r"(?:\s+[a-z0-9'-]+){0,7}\s+"
        r"(?:bullet|bullets|bullet-point|bullet-points)\b"
    ),
    re.IGNORECASE,
)
_ONE_SENTENCE_REQUEST_PATTERN = re.compile(
    (
        r"\b(?:in\s+(?:exactly\s+)?one|exactly\s+one)\s+"
        r"(?:complete\s+)?(?:grammatical\s+)?sentence\b"
    ),
    re.IGNORECASE,
)
_JOINABLE_SECOND_SENTENCE_PATTERN = re.compile(
    (
        r"^(?P<first>.+[^\s.])\.\s+"
        r"(?P<starter>he|she|it|they|we|this|that|these|those|"
        r"the|my|our|its|their|his|her)\s+"
        r"(?P<rest>.+)$"
    ),
    re.IGNORECASE | re.DOTALL,
)

_BULLET_COUNT_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
}

_TRAILING_FRAGMENT_WORDS = frozenset(
    {
        "a",
        "additional",
        "an",
        "and",
        "as",
        "at",
        "by",
        "current",
        "for",
        "from",
        "if",
        "in",
        "into",
        "of",
        "on",
        "or",
        "our",
        "proposed",
        "revised",
        "the",
        "their",
        "this",
        "those",
        "to",
        "with",
        "without",
        "your",
    }
)


# ------------------------------------------------------------------
# Raw Output Normalization
# ------------------------------------------------------------------

def _strip_response_fences(
    text: str,
) -> str:
    value = str(
        text or ""
    ).strip()
    value = re.sub(
        r"(?is)^```(?:json|text)?\s*",
        "",
        value,
    )
    value = re.sub(
        r"(?is)```\s*$",
        "",
        value,
    )

    return value.strip()


def _extract_json_payload(
    text: str,
) -> dict[str, Any]:
    value = _strip_response_fences(
        text
    )

    if not value.startswith(
        "{"
    ):
        return {}

    try:
        parsed = json.loads(
            value
        )
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return {}

    return (
        parsed
        if isinstance(
            parsed,
            dict,
        )
        else {}
    )


# ------------------------------------------------------------------
# Presentation Text Bounds
# ------------------------------------------------------------------

def _normalize_inline_text(
    value: str,
) -> str:
    """
    Collapse model-authored chip whitespace without changing its words.
    """

    return re.sub(
        r"\s+",
        " ",
        str(
            value or ""
        ),
    ).strip()


def _normalized_boundary_word(
    value: str,
) -> str:
    """
    Return a punctuation-free lowercase word for boundary inspection.
    """

    return re.sub(
        r"^[^a-z0-9]+|[^a-z0-9]+$",
        "",
        str(
            value or ""
        ).lower(),
    )


def _remove_trailing_fragment_words(
    words: list[str],
) -> list[str]:
    """
    Remove only dangling model-authored boundary words after clipping.

    No words are added, substituted, or reordered. This prevents a bounded
    chip from ending with fragments such as "as a", "to our current", or
    another incomplete article, preposition, possessive, or modifier.
    """

    bounded_words = list(
        words
    )

    while len(
        bounded_words
    ) > 2:
        boundary_word = _normalized_boundary_word(
            bounded_words[
                -1
            ]
        )

        if (
            boundary_word
            not in _TRAILING_FRAGMENT_WORDS
        ):
            break

        bounded_words.pop()

    return bounded_words


def _bound_model_authored_words(
    value: str,
    *,
    limit: int,
) -> str:
    """
    Bound text using only the model's original leading words.

    This is transport normalization, not presentation generation. No words
    are added, substituted, reordered, or inferred. When clipping creates a
    dangling phrase ending, only those trailing fragment words are removed.
    """

    normalized = _normalize_inline_text(
        value
    )

    if not normalized:
        return ""

    words = re.findall(
        r"\S+",
        normalized,
    )

    if len(
        words
    ) <= limit:
        return normalized

    bounded_words = _remove_trailing_fragment_words(
        words[
            :limit
        ]
    )

    return " ".join(
        bounded_words
    ).strip()


# ------------------------------------------------------------------
# Canonical Field Readers
# ------------------------------------------------------------------

def _read_string_field(
    payload: dict[str, Any],
    *,
    canonical_name: str,
    compact_name: str,
) -> str:
    value = payload.get(
        canonical_name
    )

    if not isinstance(
        value,
        str,
    ):
        value = payload.get(
            compact_name
        )

    if not isinstance(
        value,
        str,
    ):
        return ""

    return value.strip()


def _field_present(
    payload: dict[str, Any],
    *,
    canonical_name: str,
    compact_name: str,
) -> bool:
    return (
        canonical_name in payload
        or compact_name in payload
    )


def _raw_field(
    payload: dict[str, Any],
    *,
    canonical_name: str,
    compact_name: str,
) -> Any:
    if canonical_name in payload:
        return payload.get(
            canonical_name
        )

    return payload.get(
        compact_name
    )


def _is_explicit_empty_presentation(
    payload: dict[str, Any],
) -> bool:
    bridge = _raw_field(
        payload,
        canonical_name="bridge",
        compact_name="b",
    )
    suggestions = _raw_field(
        payload,
        canonical_name="suggestions",
        compact_name="s",
    )

    return (
        isinstance(
            bridge,
            str,
        )
        and not bridge.strip()
        and isinstance(
            suggestions,
            list,
        )
        and not suggestions
    )


def _read_suggestion_field(
    payload: dict[str, Any],
) -> list[str]:
    """
    Return up to three bounded model-authored suggestions in original order.

    Extra suggestions are ignored. An overlong suggestion is bounded to its
    first eight original words. Dangling trailing fragments introduced by
    that bound are removed so one minor model length violation cannot erase
    or visibly damage an otherwise valid bridge and chip set.

    Suggestion language is never generated, supplemented, reordered, or
    semantically rewritten here.
    """

    value = payload.get(
        "suggestions"
    )

    if not isinstance(
        value,
        list,
    ):
        value = payload.get(
            "s"
        )

    if not isinstance(
        value,
        list,
    ):
        return []

    suggestions: list[str] = []

    for item in value:
        if not isinstance(
            item,
            str,
        ):
            return []

        suggestion = _bound_model_authored_words(
            item,
            limit=(
                _PRESENTATION_SUGGESTION_WORD_LIMIT
            ),
        )

        if not suggestion:
            return []

        suggestions.append(
            suggestion
        )

    return suggestions[
        :_PRESENTATION_SUGGESTION_LIMIT
    ]


def _extract_json_answer(
    text: str,
) -> str:
    payload = _extract_json_payload(
        text
    )

    return _read_string_field(
        payload,
        canonical_name="answer",
        compact_name="a",
    )


# ------------------------------------------------------------------
# Bounded Answer Recovery
# ------------------------------------------------------------------

def _extract_malformed_json_string_field(
    text: str,
    field_name: str,
) -> str:
    """
    Recover one quoted string field from incomplete model JSON.

    This recovery is limited to the substantive answer. Presentation fields
    are accepted only from a complete parsed JSON object.
    """

    value = _strip_response_fences(
        text
    )

    if not value.startswith(
        "{"
    ):
        return ""

    pattern = (
        rf'"{re.escape(field_name)}"'
        r'\s*:\s*"((?:\\.|[^"\\])*)'
    )
    match = re.search(
        pattern,
        value,
        flags=(
            re.IGNORECASE
            | re.DOTALL
        ),
    )

    if not match:
        return ""

    raw_value = match.group(
        1
    )

    try:
        decoded = json.loads(
            f'"{raw_value}"'
        )

        return (
            decoded.strip()
            if isinstance(
                decoded,
                str,
            )
            else ""
        )
    except (
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ):
        return (
            raw_value
            .replace(
                '\\"',
                '"',
            )
            .replace(
                "\\n",
                "\n",
            )
            .strip()
        )


def _extract_malformed_answer(
    text: str,
) -> str:
    return (
        _extract_malformed_json_string_field(
            text,
            "answer",
        )
        or _extract_malformed_json_string_field(
            text,
            "a",
        )
    )


# ------------------------------------------------------------------
# Requested Answer Structure Repair
# ------------------------------------------------------------------

def _requested_exact_bullet_count(
    request_text: str,
) -> int | None:
    """Return the explicit exact bullet count requested by the user."""

    match = _EXACT_BULLET_COUNT_PATTERN.search(
        str(
            request_text or ""
        )
    )

    if not match:
        return None

    count_text = match.group(
        "count"
    ).lower()

    if count_text in _BULLET_COUNT_WORDS:
        return _BULLET_COUNT_WORDS[
            count_text
        ]

    try:
        count = int(
            count_text
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    return (
        count
        if count > 0
        else None
    )


def _repair_requested_first_bullet_marker(
    answer: str,
    *,
    request_text: str,
) -> str:
    """
    Restore one omitted first bullet marker without changing answer words.

    This repair is active only when the current user request explicitly asks
    for bullets, the answer has at least two non-empty lines, the first line is
    not already a bullet, and every later non-empty line is already a hyphen
    bullet. When an exact bullet count is present, the repair runs only when
    adding the first marker will complete that count. The narrow shape prevents
    an introductory line followed by an already complete list from becoming an
    extra bullet.
    """

    value = str(
        answer or ""
    ).strip()
    request = str(
        request_text or ""
    ).strip()

    if (
        not value
        or not request
        or not _BULLET_REQUEST_PATTERN.search(
            request
        )
    ):
        return value

    lines = value.splitlines()
    non_empty_indexes = [
        index
        for index, line in enumerate(
            lines
        )
        if line.strip()
    ]

    if len(
        non_empty_indexes
    ) < 2:
        return value

    first_index = non_empty_indexes[
        0
    ]
    first_line = lines[
        first_index
    ]

    if _BULLET_LINE_PATTERN.match(
        first_line
    ):
        return value

    later_lines = [
        lines[index]
        for index in non_empty_indexes[
            1:
        ]
    ]

    if not all(
        _BULLET_LINE_PATTERN.match(
            line
        )
        for line in later_lines
    ):
        return value

    existing_bullet_count = sum(
        1
        for index in non_empty_indexes
        if _BULLET_LINE_PATTERN.match(
            lines[index]
        )
    )
    requested_bullet_count = (
        _requested_exact_bullet_count(
            request
        )
    )

    if requested_bullet_count is not None:
        if (
            existing_bullet_count
            == requested_bullet_count
        ):
            return value

        if (
            existing_bullet_count
            != requested_bullet_count - 1
        ):
            return value

    indentation = first_line[
        :len(first_line)
        - len(first_line.lstrip())
    ]
    lines[
        first_index
    ] = (
        f"{indentation}- "
        f"{first_line.lstrip()}"
    )

    return "\n".join(
        lines
    ).strip()


def _repair_requested_single_sentence_boundary(
    answer: str,
    *,
    request_text: str,
) -> str:
    """
    Join one accidental second sentence without changing answer words.

    This repair runs only when the user explicitly requested one sentence,
    the answer is a single prose line, and exactly one full-stop boundary
    starts a second clause with a joinable pronoun or determiner. The boundary
    becomes a semicolon and only the starter's initial capitalization changes.
    Bullets, multiline output, questions, exclamations, and more complex
    sentence shapes remain untouched.
    """

    value = str(
        answer or ""
    ).strip()
    request = str(
        request_text or ""
    ).strip()

    if (
        not value
        or not request
        or "\n" in value
        or "?" in value
        or "!" in value
        or not _ONE_SENTENCE_REQUEST_PATTERN.search(
            request
        )
    ):
        return value

    boundary_matches = list(
        re.finditer(
            (
                r"\.\s+(?=(?:he|she|it|they|we|this|that|these|those|"
                r"the|my|our|its|their|his|her)\s)"
            ),
            value,
            flags=re.IGNORECASE,
        )
    )

    if len(
        boundary_matches
    ) != 1:
        return value

    match = _JOINABLE_SECOND_SENTENCE_PATTERN.fullmatch(
        value
    )

    if not match:
        return value

    first = match.group(
        "first"
    ).strip()
    starter = match.group(
        "starter"
    )
    rest = match.group(
        "rest"
    ).strip()

    if (
        not first
        or not starter
        or not rest
    ):
        return value

    normalized_starter = (
        starter[
            0
        ].lower()
        + starter[
            1:
        ]
    )

    return (
        f"{first}; "
        f"{normalized_starter} "
        f"{rest}"
    ).strip()


# ------------------------------------------------------------------
# Visible Answer Normalization
# ------------------------------------------------------------------

def clean_visible_answer(
    text: str,
    *,
    request_text: str = "",
) -> str:
    """
    Return only the substantive assistant answer.

    A complete JSON response may use canonical fields or compact transport
    aliases. When JSON is incomplete, only the answer field is recovered;
    presentation language is never inferred from malformed output.
    """

    json_answer = _extract_json_answer(
        text
    )
    malformed_json_answer = (
        _extract_malformed_answer(
            text
        )
    )
    cleaned = (
        json_answer
        or malformed_json_answer
        or _strip_response_fences(
            text
        )
    )

    if cleaned.startswith(
        "{"
    ):
        return ""

    cleaned = re.sub(
        r"(?im)^\s*answer\s*:\s*",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)\n?\s*(the\s+)?bridge\s*:\s*.*$",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)\n?\s*suggestions\s*:\s*.*$",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"(?is)\n?\s*ui[_\s-]*actions\s*:\s*.*$",
        "",
        cleaned,
    )
    cleaned = re.sub(
        r"\n{3,}",
        "\n\n",
        cleaned,
    )
    cleaned = re.sub(
        r"[ \t]{2,}",
        " ",
        cleaned,
    )

    cleaned = _repair_requested_first_bullet_marker(
        cleaned.strip(),
        request_text=request_text,
    )

    return _repair_requested_single_sentence_boundary(
        cleaned,
        request_text=request_text,
    )


# ------------------------------------------------------------------
# Lane Payload Assembly
# ------------------------------------------------------------------

def payload_from_answer(
    output_text: str,
    *,
    request_text: str = "",
) -> dict[str, Any]:
    """
    Return the execution-lane response payload.

    The answer is mandatory. Presentation is preserved only when it came from
    one complete JSON object and forms either the explicit direct-response
    shape or one paired bridge-and-suggestions shape. Extra model-authored
    suggestions are bounded to the first three. Overlong suggestions are
    bounded using only their original leading words, with trailing boundary
    fragments removed. Downstream UX Synthesis remains responsible for final
    validation of the complete presentation shape.
    """

    parsed = _extract_json_payload(
        output_text
    )
    answer = (
        _read_string_field(
            parsed,
            canonical_name="answer",
            compact_name="a",
        )
        or clean_visible_answer(
            output_text,
            request_text=request_text,
        )
    )
    answer = _repair_requested_first_bullet_marker(
        answer,
        request_text=request_text,
    )
    answer = _repair_requested_single_sentence_boundary(
        answer,
        request_text=request_text,
    )

    payload: dict[str, Any] = {
        "answer": answer,
    }

    if not parsed:
        return payload

    bridge_present = _field_present(
        parsed,
        canonical_name="bridge",
        compact_name="b",
    )
    suggestions_present = _field_present(
        parsed,
        canonical_name="suggestions",
        compact_name="s",
    )

    if (
        not bridge_present
        or not suggestions_present
    ):
        return payload

    if _is_explicit_empty_presentation(
        parsed
    ):
        payload[
            "bridge"
        ] = ""
        payload[
            "suggestions"
        ] = []

        return payload

    bridge = _read_string_field(
        parsed,
        canonical_name="bridge",
        compact_name="b",
    )
    suggestions = _read_suggestion_field(
        parsed
    )

    if (
        not bridge
        or not suggestions
    ):
        return payload

    payload[
        "bridge"
    ] = bridge
    payload[
        "suggestions"
    ] = suggestions

    return payload


# ------------------------------------------------------------------
# Failure Reporting
# ------------------------------------------------------------------

def failure_message(
    result,
) -> str:
    if not result or not getattr(
        result,
        "failure",
        None,
    ):
        return "LLM returned no output."

    failure = result.failure
    reason = getattr(
        failure,
        "reason",
        "unknown",
    )
    message = getattr(
        failure,
        "message",
        "",
    )

    if hasattr(
        reason,
        "value",
    ):
        reason = reason.value

    return f"{reason}: {message}".strip()
# -------------------------------------------------------------------
# FILE: workspace_solomon_llm.py
# DIRECTORY: solomon_workspace/context/
# -------------------------------------------------------------------
# LLM execution wrapper for explicit SolomonAI source operations.
# This module calls the product LLM for source-grounded answers; source
# previews are prompt context only and never become the assistant voice.
# -------------------------------------------------------------------

import re
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Optional, Set, Tuple

from solomon_workspace.context.workspace_solomon_prompt import (
    WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES,
    WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS,
    WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES,
    build_workspace_solomon_fallback_answer,
    build_workspace_solomon_llm_query,
    is_workspace_solomon_llm_answer_usable,
    normalize_workspace_solomon_request_action,
)


WORKSPACE_SOLOMON_LLM_CALL_SITE = (
    "workspace_solomon_source_operation"
)

WORKSPACE_SOLOMON_LLM_MAX_NEW_TOKENS = {
    WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES: 256,
    WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS: 256,
    WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES: 320,
}

WORKSPACE_SOLOMON_DOCUMENT_OPENING_VERBS = frozenset({
    "addresses",
    "covers",
    "describes",
    "details",
    "documents",
    "explains",
    "identifies",
    "lists",
    "outlines",
    "presents",
    "provides",
    "summarizes",
})

WORKSPACE_SOLOMON_CURRENCY_PATTERN = re.compile(
    r"""
    (?:
        (?:USD\s*)?\$\s*\d[\d,]*(?:\.\d{1,2})?
        |
        \b\d[\d,]*(?:\.\d{2})\s*(?:USD|dollars?)\b
    )
    """,
    flags=re.IGNORECASE | re.VERBOSE,
)


def get_workspace_solomon_max_new_tokens(
    request_action: str,
) -> int:
    """Return the server-owned generation budget for one source action."""

    action = normalize_workspace_solomon_request_action(
        request_action
    )

    return WORKSPACE_SOLOMON_LLM_MAX_NEW_TOKENS[
        action
    ]


def _log_workspace_solomon_warning(
    logger: Optional[Any],
    message: str,
    *args: Any,
) -> None:
    """Write optional source-operation warnings without Flask app coupling."""

    if not logger:
        return

    try:
        logger.warning(message, *args)
    except Exception:
        return


def _log_workspace_solomon_exception(
    logger: Optional[Any],
    message: str,
    *args: Any,
) -> None:
    """Write optional source-operation exceptions without Flask app coupling."""

    if not logger:
        return

    try:
        logger.exception(message, *args)
    except Exception:
        return


def _normalize_workspace_solomon_text(value: Any) -> str:
    """Normalize model line endings without altering visible punctuation."""

    return str(value or "").replace(
        "\r\n",
        "\n",
    ).replace(
        "\r",
        "\n",
    ).strip()


def _get_workspace_solomon_source_title(
    sources: List[Dict[str, Any]],
) -> str:
    """Return the sole attached source title when exactly one source is active."""

    if len(sources) != 1:
        return ""

    source = sources[0]

    return str(
        source.get("name")
        or source.get("document_id")
        or ""
    ).strip()


def _build_workspace_solomon_heading(
    action: str,
    sources: List[Dict[str, Any]],
) -> str:
    """Return the canonical Markdown heading for one structured response."""

    source_title = _get_workspace_solomon_source_title(
        sources
    )
    heading_title = source_title or "Selected Files"

    if (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES
    ):
        return f"## Summary — {heading_title}"

    if (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS
    ):
        return f"## Key Details — {heading_title}"

    if (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES
    ):
        return "## Comparison — Selected Files"

    raise ValueError(
        f"No heading exists for source action {action!r}."
    )


def _strip_workspace_solomon_heading_prefix(
    text: str,
    action: str,
    sources: List[Dict[str, Any]],
) -> str:
    """Remove an existing heading even when the model merged body text onto the same line."""

    source_title = _get_workspace_solomon_source_title(
        sources
    )
    expected_title = (
        "Selected Files"
        if (
            action
            == WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES
        )
        else source_title or "Selected Files"
    )
    action_label = {
        WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES: (
            "Summary"
        ),
        WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS: (
            "Key Details"
        ),
        WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES: (
            "Comparison"
        ),
    }.get(action)

    if not action_label:
        return text

    prefix_pattern = re.compile(
        (
            r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?"
            + re.escape(action_label)
            + r"\s*(?:—|–|-|:)\s*"
            + re.escape(expected_title)
            + r"(?:\*\*|__)?(?:\s+|$)"
        ),
        flags=re.IGNORECASE,
    )

    stripped_text = prefix_pattern.sub(
        "",
        text,
        count=1,
    ).strip()

    if stripped_text != text.strip():
        return stripped_text

    lines = text.splitlines()

    if lines and re.match(
        (
            r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?"
            + re.escape(action_label)
            + r"\s*(?:—|–|-|:)"
        ),
        lines[0],
        flags=re.IGNORECASE,
    ):
        return "\n".join(lines[1:]).strip()

    return text.strip()


def _remove_repeated_workspace_solomon_title(
    text: str,
    sources: List[Dict[str, Any]],
) -> str:
    """Remove a duplicated single-source title from the start of the body."""

    source_title = _get_workspace_solomon_source_title(
        sources
    )

    if not source_title:
        return text.strip()

    return re.sub(
        (
            r"^\s*(?:\*\*|__)?"
            + re.escape(source_title)
            + r"(?:\*\*|__)?(?:\s+|$)"
        ),
        "",
        text,
        count=1,
        flags=re.IGNORECASE,
    ).strip()


def _repair_workspace_solomon_opening_subject(
    text: str,
) -> str:
    """Restore a natural subject when title removal leaves a lowercase opening verb."""

    match = re.match(
        r"^([A-Za-z]+)\b",
        text,
    )

    if (
        not match
        or match.group(1).lower()
        not in WORKSPACE_SOLOMON_DOCUMENT_OPENING_VERBS
    ):
        return text

    return f"The document {text}"


def _split_workspace_solomon_sentences(
    text: str,
) -> List[str]:
    """Return complete prose sentences while preserving their punctuation."""

    normalized_text = re.sub(
        r"\s+",
        " ",
        text,
    ).strip()

    if not normalized_text:
        return []

    return [
        sentence.strip()
        for sentence in re.split(
            r"(?<=[.!?])(?:[\"')\]]*)\s+",
            normalized_text,
        )
        if sentence.strip()
    ]


def _build_workspace_solomon_summary_paragraphs(
    text: str,
) -> str:
    """Repair an unstructured summary into three balanced Markdown paragraphs."""

    existing_paragraphs = [
        re.sub(
            r"\s+",
            " ",
            paragraph,
        ).strip()
        for paragraph in re.split(
            r"\n\s*\n",
            text,
        )
        if paragraph.strip()
    ]

    if len(existing_paragraphs) >= 3:
        return "\n\n".join(
            existing_paragraphs
        )

    sentences = _split_workspace_solomon_sentences(
        text
    )

    if len(sentences) < 3:
        return (
            "\n\n".join(existing_paragraphs)
            or text.strip()
        )

    paragraph_count = 3
    base_size = len(sentences) // paragraph_count
    remainder = len(sentences) % paragraph_count
    paragraphs = []
    cursor = 0

    for index in range(paragraph_count):
        paragraph_size = base_size + (
            1 if index < remainder else 0
        )
        paragraph_sentences = sentences[
            cursor:cursor + paragraph_size
        ]
        cursor += paragraph_size

        if paragraph_sentences:
            paragraphs.append(
                " ".join(paragraph_sentences)
            )

    return "\n\n".join(paragraphs)


def normalize_workspace_solomon_llm_answer(
    text: str,
    *,
    request_action: str,
    sources: List[Dict[str, Any]],
) -> str:
    """Return safe, stable Markdown structure without rewriting factual content."""

    action = normalize_workspace_solomon_request_action(
        request_action
    )
    normalized_text = _normalize_workspace_solomon_text(
        text
    )

    if not normalized_text:
        return normalized_text

    heading = _build_workspace_solomon_heading(
        action,
        sources,
    )
    body = _strip_workspace_solomon_heading_prefix(
        normalized_text,
        action,
        sources,
    )
    body = _remove_repeated_workspace_solomon_title(
        body,
        sources,
    )
    body = _repair_workspace_solomon_opening_subject(
        body
    )

    if (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES
    ):
        body = _build_workspace_solomon_summary_paragraphs(
            body
        )

    return (
        f"{heading}\n\n{body}".strip()
        if heading
        else body.strip()
    )


def _collect_workspace_solomon_preview_text(
    value: Any,
    collected: List[str],
) -> None:
    """Collect source-preview strings recursively for bounded consistency checks."""

    if isinstance(value, str):
        clean_value = value.strip()

        if clean_value:
            collected.append(clean_value)
        return

    if isinstance(value, dict):
        for nested_value in value.values():
            _collect_workspace_solomon_preview_text(
                nested_value,
                collected,
            )
        return

    if isinstance(value, (list, tuple)):
        for nested_value in value:
            _collect_workspace_solomon_preview_text(
                nested_value,
                collected,
            )


def _normalize_workspace_solomon_currency(
    value: str,
) -> Optional[Decimal]:
    """Return one normalized currency value for exact source-grounding checks."""

    numeric_value = re.sub(
        r"[^0-9.]",
        "",
        value,
    )

    if not numeric_value:
        return None

    try:
        return Decimal(numeric_value)
    except InvalidOperation:
        return None


def _extract_workspace_solomon_currency_values(
    text: str,
) -> Set[Decimal]:
    """Return all explicit monetary values found in one text block."""

    values: Set[Decimal] = set()

    for match in (
        WORKSPACE_SOLOMON_CURRENCY_PATTERN.finditer(
            str(text or "")
        )
    ):
        normalized_value = (
            _normalize_workspace_solomon_currency(
                match.group(0)
            )
        )

        if normalized_value is not None:
            values.add(normalized_value)

    return values


def is_workspace_solomon_answer_source_consistent(
    text: str,
    *,
    source_previews: Optional[List[Dict[str, Any]]],
    request_action: str,
) -> bool:
    """Reject structured answers that introduce unsupported monetary claims."""

    normalize_workspace_solomon_request_action(
        request_action
    )

    if not source_previews:
        return True

    preview_strings: List[str] = []
    _collect_workspace_solomon_preview_text(
        source_previews,
        preview_strings,
    )
    preview_text = "\n".join(
        preview_strings
    )
    preview_values = (
        _extract_workspace_solomon_currency_values(
            preview_text
        )
    )
    answer_values = (
        _extract_workspace_solomon_currency_values(
            text
        )
    )

    if not preview_values or not answer_values:
        return True

    return answer_values.issubset(
        preview_values
    )


def generate_workspace_solomon_answer(
    message: str,
    sources: List[Dict[str, Any]],
    *,
    context_mode: str = "workspace",
    source_previews: Optional[List[Dict[str, Any]]] = None,
    request_action: str,
    logger: Optional[Any] = None,
    request_id: str = "untracked",
) -> Tuple[str, str]:
    """Generate one explicit SolomonAI source-operation answer through the local LLM."""

    action = normalize_workspace_solomon_request_action(
        request_action
    )
    max_new_tokens = (
        get_workspace_solomon_max_new_tokens(
            action
        )
    )
    llm_query = build_workspace_solomon_llm_query(
        message,
        sources,
        context_mode=context_mode,
        source_previews=source_previews,
        request_action=action,
    )

    try:
        from solomon_core.llm.llm_execution_contract import (
            LLMExecutionInput,
            LLMExecutionMode,
            LLMRuntimeProfile,
        )
        from solomon_core.llm.llm_executor import (
            execute_llm,
        )

        runtime_profile = (
            LLMRuntimeProfile.STATIC_CACHE
        )

        result = execute_llm(
            LLMExecutionInput(
                user_query=llm_query,
                mode=(
                    LLMExecutionMode.INFORMATIONAL_ONLY
                ),
                context=None,
                call_site=(
                    WORKSPACE_SOLOMON_LLM_CALL_SITE
                ),
                max_new_tokens=max_new_tokens,
                runtime_profile=runtime_profile,
            )
        )

        output = getattr(
            result,
            "output",
            None,
        )
        raw_text = str(
            getattr(
                output,
                "text",
                "",
            )
            or ""
        ).strip()
        normalized_text = (
            normalize_workspace_solomon_llm_answer(
                raw_text,
                request_action=action,
                sources=sources,
            )
            if raw_text
            else ""
        )
        source_consistent = (
            is_workspace_solomon_answer_source_consistent(
                normalized_text,
                source_previews=source_previews,
                request_action=action,
            )
            if normalized_text
            else False
        )

        if (
            normalized_text
            and source_consistent
            and is_workspace_solomon_llm_answer_usable(
                normalized_text,
                request_action=action,
            )
        ):
            return normalized_text, "llm"

        if normalized_text and not source_consistent:
            _log_workspace_solomon_warning(
                logger,
                "[workspace.solomon.context.llm_source_inconsistent] "
                "request_id=%s request_action=%s "
                "max_new_tokens=%s runtime_profile=%s "
                "output_chars=%s",
                request_id,
                action,
                max_new_tokens,
                runtime_profile.value,
                len(normalized_text),
            )
        elif normalized_text:
            _log_workspace_solomon_warning(
                logger,
                "[workspace.solomon.context.llm_unusable] "
                "request_id=%s request_action=%s "
                "max_new_tokens=%s runtime_profile=%s "
                "output_chars=%s",
                request_id,
                action,
                max_new_tokens,
                runtime_profile.value,
                len(normalized_text),
            )
        else:
            failure = getattr(
                result,
                "failure",
                None,
            )
            _log_workspace_solomon_warning(
                logger,
                "[workspace.solomon.context.llm_empty] "
                "request_id=%s request_action=%s "
                "max_new_tokens=%s runtime_profile=%s "
                "reason=%s",
                request_id,
                action,
                max_new_tokens,
                runtime_profile.value,
                getattr(
                    failure,
                    "message",
                    "No LLM output.",
                ),
            )

    except Exception as exc:
        _log_workspace_solomon_exception(
            logger,
            "[workspace.solomon.context.llm_error] "
            "request_id=%s request_action=%s "
            "max_new_tokens=%s runtime_profile=%s "
            "error=%s",
            request_id,
            action,
            max_new_tokens,
            "static_cache",
            str(exc),
        )

    fallback_answer = (
        build_workspace_solomon_fallback_answer(
            message,
            sources,
            context_mode=context_mode,
            source_previews=source_previews,
            request_action=action,
        )
    )

    return (
        fallback_answer,
        "llm_unavailable",
    )
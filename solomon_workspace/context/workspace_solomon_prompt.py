# -------------------------------------------------------------------
# FILE: workspace_solomon_prompt.py
# DIRECTORY: solomon_workspace/context/
# -------------------------------------------------------------------
# LLM prompt and safe fallback contract for explicit SolomonAI source
# operations. This module builds bounded LLM context and validates assistant
# text; it does not execute the LLM, read files, resolve ownership, route
# requests, or mutate state.
# -------------------------------------------------------------------

import re
from typing import Any, Dict, List, Optional

from solomon_workspace.context.workspace_solomon_source_preview import (
    build_workspace_solomon_preview_prompt_block,
    has_workspace_solomon_source_preview_text,
)


WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES = "summarize_sources"
WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS = "identify_key_details"
WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES = "compare_sources"

WORKSPACE_SOLOMON_REQUEST_ACTIONS = frozenset({
    WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES,
    WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS,
    WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES,
})

WORKSPACE_SOLOMON_SUMMARY_PREVIEW_PROMPT_CHAR_LIMIT = 8000
WORKSPACE_SOLOMON_DETAILS_PREVIEW_PROMPT_CHAR_LIMIT = 8000
WORKSPACE_SOLOMON_COMPARE_PREVIEW_PROMPT_CHAR_LIMIT = 12000

WORKSPACE_SOLOMON_PREVIEW_PROMPT_CHAR_LIMITS = {
    WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES: (
        WORKSPACE_SOLOMON_SUMMARY_PREVIEW_PROMPT_CHAR_LIMIT
    ),
    WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS: (
        WORKSPACE_SOLOMON_DETAILS_PREVIEW_PROMPT_CHAR_LIMIT
    ),
    WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES: (
        WORKSPACE_SOLOMON_COMPARE_PREVIEW_PROMPT_CHAR_LIMIT
    ),
}

WORKSPACE_SOLOMON_DOCUMENTS_CAPABILITY_PACK = (
    "Upload stores files only and never starts analysis.",
    "My Files contains active uploads; Reports contains saved outputs.",
    "Recent is navigation; Trash files require restoration before source use.",
    "Reader is the first-party surface for fuller file viewing.",
)


WORKSPACE_SOLOMON_MARKDOWN_FORMAT_CONTRACT = (
    "Return plain Markdown, not HTML. "
    "Approved formatting is limited to level-two and level-three headings, "
    "blank-line paragraphs, hyphen bullets, numbered lists, bold text, italics, "
    "inline code, blockquotes, and horizontal rules. "
    "Use short **bold phrases** only when they naturally improve clarity; bold "
    "formatting is optional and must never cover a whole sentence or paragraph. "
    "Leave a blank line between every heading and paragraph. "
    "Never emit raw HTML, Markdown tables, fenced code blocks, images, or "
    "embedded links. Do not wrap the answer in a code fence."
)


def normalize_workspace_solomon_request_action(
    value: Any,
) -> str:
    """Return one explicit server-approved SolomonAI source action."""

    clean_value = str(value or "").strip().lower()

    if clean_value in WORKSPACE_SOLOMON_REQUEST_ACTIONS:
        return clean_value

    supported_actions = ", ".join(
        sorted(WORKSPACE_SOLOMON_REQUEST_ACTIONS)
    )

    raise ValueError(
        "Unsupported SolomonAI source action "
        f"{clean_value or '<missing>'!r}. "
        f"Expected one of: {supported_actions}."
    )


def get_workspace_solomon_preview_prompt_char_limit(
    request_action: str,
) -> int:
    """Return the bounded preview budget for one explicit source action."""

    action = normalize_workspace_solomon_request_action(
        request_action
    )

    return WORKSPACE_SOLOMON_PREVIEW_PROMPT_CHAR_LIMITS[
        action
    ]


def bound_workspace_solomon_prompt_text(
    value: str,
    *,
    limit: int,
) -> str:
    """Return bounded prompt text without presenting truncation as complete coverage."""

    clean_value = str(value or "").strip()

    if not clean_value:
        return "- None available."

    if len(clean_value) <= limit:
        return clean_value

    bounded_value = clean_value[:limit].rstrip()

    return (
        f"{bounded_value}\n"
        "- Preview limit reached; additional file content may exist."
    )


def build_workspace_solomon_documents_capability_pack() -> str:
    """Format the neutral Documents capability pack for source operations."""

    return "\n".join(
        f"- {item}"
        for item in WORKSPACE_SOLOMON_DOCUMENTS_CAPABILITY_PACK
    )


def build_workspace_solomon_markdown_format_contract() -> str:
    """Return the approved Markdown subset for user-facing source answers."""

    return WORKSPACE_SOLOMON_MARKDOWN_FORMAT_CONTRACT


def build_workspace_solomon_source_summary(
    sources: List[Dict[str, Any]],
) -> str:
    """Format connected source metadata for the source-operation prompt."""

    if not sources:
        return "- No file source is attached."

    source_lines = [
        (
            f"- {source.get('name') or source.get('document_id')} "
            f"({source.get('extension') or source.get('mime_type') or 'Workspace file'})"
        )
        for source in sources
    ]

    return "\n".join(source_lines)


def build_workspace_solomon_response_contract(
    request_action: str,
    *,
    source_count: int,
    source_title: str = "",
) -> str:
    """Build the LLM response contract for one explicit source action."""

    action = normalize_workspace_solomon_request_action(
        request_action
    )
    clean_source_title = re.sub(
        r"\s+",
        " ",
        str(source_title or "").strip(),
    )

    if (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES
    ):
        if source_count == 1 and clean_source_title:
            heading = (
                f"## Summary — {clean_source_title}"
            )
            title_repetition_rule = (
                "Do not repeat the document title at the beginning of the first "
                "body paragraph."
            )
        elif source_count == 1:
            heading = "## Summary — [Document Title]"
            title_repetition_rule = (
                "Begin the first body paragraph with the document's purpose."
            )
        else:
            heading = "## Summary — Selected Files"
            title_repetition_rule = (
                "Name an individual file in the body only when attribution is "
                "needed."
            )

        return (
            "Write a genuine document summary, not a one-line preview.\n"
            "Begin with exactly this level-two Markdown heading on its own line:\n"
            f"{heading}\n\n"
            "Leave one blank line after the heading. Then write exactly three "
            "clear Markdown paragraphs separated by blank lines.\n"
            "Paragraph 1: explain what the document is and its primary purpose.\n"
            "Paragraph 2: synthesize the main subjects, procedures, decisions, "
            "or obligations it covers.\n"
            "Paragraph 3: capture additional details, cautions, recommendations, "
            "exceptions, or operating guidance.\n"
            "You may use one or two short **bold phrases** for the most useful "
            "supported facts, such as an amount, date, obligation, central scope "
            "item, or preview limitation. Bold formatting is optional. Never bold "
            "a complete sentence, paragraph, or the heading. Do not use bullets "
            "unless the user explicitly asks for a list. "
            "Target 120 to 170 words across the body paragraphs. "
            "Preserve important distinctions and do not repeat isolated phrases. "
            f"{title_repetition_rule} "
            "Treat the source preview as partial. Never convert silence in the "
            "preview into a claim that the full document lacks something. "
            "When an expected item is not visible, say 'The available preview "
            "does not show...' or omit the statement. Do not say 'the document "
            "provides no,' 'does not include,' 'contains no,' or 'omits' unless "
            "the preview explicitly states that absence. "
            "Do not invent content that is absent from the preview. "
            "When a preview limitation matters, close naturally with: "
            "'Review the full file in Reader before relying on this summary "
            "for decisions.'"
        )

    if (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS
    ):
        heading = (
            f"## Key Details — {clean_source_title}"
            if source_count == 1 and clean_source_title
            else "## Key Details — Selected Files"
        )

        return (
            "Identify the most important source-grounded details.\n"
            "Begin with exactly this level-two Markdown heading on its own line:\n"
            f"{heading}\n\n"
            "Leave one blank line after the heading. Then provide four to eight "
            "hyphen bullets. Use this pattern when a concise label is supported:\n"
            "- **Label:** Supported detail.\n"
            "Include only facts, dates, obligations, risks, and open questions "
            "supported by the available preview. Distinguish explicit source "
            "statements from unresolved questions. Do not create empty categories. "
            "Target 100 to 180 words and finish every bullet completely."
        )

    if (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES
    ):
        return (
            "Compare the selected files using only the attached previews.\n"
            "Begin with exactly this level-two Markdown heading on its own line:\n"
            "## Comparison — Selected Files\n\n"
            "Leave one blank line after the heading. Begin with one concise "
            "overview paragraph. Then use the level-three Markdown headings "
            "'### Agreements', '### Differences', and '### Open Questions' only "
            "when the available previews support those sections. Under each used "
            "heading, write a short paragraph or hyphen bullets. Name the relevant "
            "files when attributing a point. Do not force differences where the "
            "previews do not support them. Target 140 to 220 words and finish with "
            "the practical significance of the comparison."
        )

    raise ValueError(
        f"No response contract exists for source action {action!r}."
    )


def build_workspace_solomon_llm_query(
    message: str,
    sources: List[Dict[str, Any]],
    *,
    context_mode: str = "workspace",
    source_previews: Optional[List[Dict[str, Any]]] = None,
    request_action: str,
) -> str:
    """Build a bounded query for one explicit SolomonAI source action."""

    action = normalize_workspace_solomon_request_action(
        request_action
    )
    source_summary = build_workspace_solomon_source_summary(
        sources
    )
    source_text_available = (
        has_workspace_solomon_source_preview_text(
            source_previews
        )
    )
    source_preview_block = (
        bound_workspace_solomon_prompt_text(
            build_workspace_solomon_preview_prompt_block(
                source_previews
            ),
            limit=(
                get_workspace_solomon_preview_prompt_char_limit(
                    action
                )
            ),
        )
    )
    capability_pack = (
        build_workspace_solomon_documents_capability_pack()
    )
    markdown_format_contract = (
        build_workspace_solomon_markdown_format_contract()
    )
    single_source_title = (
        str(
            sources[0].get(
                "name"
            )
            or sources[0].get(
                "document_id"
            )
            or ""
        ).strip()
        if len(sources) == 1
        else ""
    )
    response_contract = (
        build_workspace_solomon_response_contract(
            action,
            source_count=len(sources),
            source_title=single_source_title,
        )
    )

    source_authority_rule = (
        (
            "Use the attached extracted preview as partial source context. "
            "Do not imply complete file coverage. When discussing information "
            "that is not visible, describe only the preview boundary, such as "
            "'The available preview does not show...'. Never claim that the "
            "whole document lacks an item unless the preview explicitly states "
            "that absence."
        )
        if source_text_available
        else (
            "No extracted document text is available. "
            "Use source metadata and workspace facts only, and state plainly "
            "when the requested content-level answer cannot be supported."
        )
    )

    return (
        "You are SolomonAI, the source-aware assistant in General Contractor AI.\n"
        "The visible answer must be authored by you from the supplied context.\n"
        "Reason silently, then provide only the final user-facing answer.\n"
        "Remain professional, neutral, specific, and source-grounded.\n"
        f"{source_authority_rule}\n"
        "Conversational summarization, clarification, and comparison of the supplied "
        "preview are allowed. Never claim that a governed workflow, scoring process, "
        "formal evidence review, report generation, or record mutation occurred.\n"
        "For needs beyond the available preview, direct the user to Reader or the "
        "appropriate governed workflow without pretending the missing content was reviewed.\n\n"
        f"Workspace facts:\n{capability_pack}\n\n"
        f"Context mode: {context_mode}\n"
        f"Server-validated sources:\n{source_summary}\n\n"
        f"Bounded source preview:\n{source_preview_block}\n\n"
        f"Source action: {action}\n"
        f"Formatting contract:\n{markdown_format_contract}\n\n"
        f"Response contract:\n{response_contract}\n\n"
        "Follow the formatting and response contracts exactly. "
        "Do not collapse headings and paragraphs onto one line.\n"
        f"User request: {str(message or '').strip()}"
    )


def build_workspace_solomon_fallback_answer(
    message: str,
    sources: List[Dict[str, Any]],
    *,
    context_mode: str = "workspace",
    source_previews: Optional[List[Dict[str, Any]]] = None,
    request_action: str,
) -> str:
    """Return an honest failure message for one explicit source action."""

    del message
    normalize_workspace_solomon_request_action(
        request_action
    )

    if context_mode == "trash" and not sources:
        return (
            "Trash files must be restored before SolomonAI can use them as "
            "source context."
        )

    if sources and has_workspace_solomon_source_preview_text(
        source_previews
    ):
        return (
            "SolomonAI could not complete the LLM-authored response from the "
            "available source preview. Please retry the request."
        )

    if sources:
        return (
            "SolomonAI could not complete the LLM-authored response, and no "
            "readable source preview was available. Open Reader or retry after "
            "the source becomes readable."
        )

    return (
        "SolomonAI could not complete the LLM-authored response. Please retry "
        "the request."
    )


def _workspace_solomon_markdown_heading_matches(
    line: str,
    heading_label: str,
) -> Optional[re.Match]:
    """Match one approved Markdown heading without accepting raw HTML."""

    return re.match(
        (
            r"^#{1,3}\s+"
            + re.escape(heading_label)
            + r"\s*(?:[—–-]|:)\s*(.+?)\s*$"
        ),
        str(line or "").strip(),
        flags=re.IGNORECASE,
    )


def _workspace_solomon_plain_text_for_validation(
    text: str,
) -> str:
    """Remove approved Markdown markers before sentence-level validation."""

    clean_text = str(text or "")
    clean_text = re.sub(
        r"(?m)^#{1,3}\s+",
        "",
        clean_text,
    )
    clean_text = re.sub(
        r"(?m)^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*)",
        "",
        clean_text,
    )
    clean_text = re.sub(
        r"(\*\*|__|\*|_|`)",
        "",
        clean_text,
    )
    clean_text = re.sub(
        r"(?m)^\s*---+\s*$",
        " ",
        clean_text,
    )

    return re.sub(
        r"\s+",
        " ",
        clean_text,
    ).strip()


def _workspace_solomon_contains_disallowed_markup(
    text: str,
) -> bool:
    """Reject formats outside the safe renderer's approved Markdown subset."""

    clean_text = str(text or "")

    if "```" in clean_text or "~~~" in clean_text:
        return True

    if re.search(
        r"<\s*/?\s*[A-Za-z][^>]*>",
        clean_text,
    ):
        return True

    if re.search(
        r"!\[[^\]]*\]\([^)]*\)",
        clean_text,
    ):
        return True

    if re.search(
        r"(?m)^\s*\|.*\|\s*$",
        clean_text,
    ):
        return True

    return False


def is_workspace_solomon_llm_answer_usable(
    text: str,
    *,
    request_action: str,
) -> bool:
    """Reject empty, unsafe, malformed, truncated, or incomplete LLM output."""

    clean_text = str(text or "").strip()
    action = normalize_workspace_solomon_request_action(
        request_action
    )

    if len(clean_text) < 12:
        return False

    if _workspace_solomon_contains_disallowed_markup(
        clean_text
    ):
        return False

    plain_text = (
        _workspace_solomon_plain_text_for_validation(
            clean_text
        )
    )
    alpha_chars = sum(
        1
        for char in plain_text
        if char.isalpha()
    )
    alpha_ratio = (
        alpha_chars
        / max(1, len(plain_text))
    )
    comma_count = plain_text.count(",")
    alpha_words = re.findall(
        r"[A-Za-z]{3,}",
        plain_text,
    )

    if alpha_chars < 18:
        return False

    if len(plain_text) >= 60 and alpha_ratio < 0.35:
        return False

    if comma_count > max(
        8,
        len(alpha_words) * 2,
    ):
        return False

    if not re.search(
        r"[.!?]\s*$",
        plain_text,
    ):
        return False

    nonempty_lines = [
        line.strip()
        for line in clean_text.splitlines()
        if line.strip()
    ]

    if (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_SUMMARIZE_SOURCES
    ):
        if len(plain_text) < 300:
            return False

        if len(nonempty_lines) < 4:
            return False

        heading_match = (
            _workspace_solomon_markdown_heading_matches(
                nonempty_lines[0],
                "Summary",
            )
        )

        if not heading_match:
            return False

        heading_title = re.sub(
            r"\s+",
            " ",
            heading_match.group(1).strip(),
        )
        body_text = "\n".join(
            nonempty_lines[1:]
        )
        summary_body = (
            _workspace_solomon_plain_text_for_validation(
                body_text
            )
        )
        body_sentences = [
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])(?:[\"')\]]*)\s+",
                summary_body,
            )
            if sentence.strip()
        ]

        if not heading_title or not summary_body:
            return False

        if len(body_sentences) < 3:
            return False

    elif (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_IDENTIFY_KEY_DETAILS
    ):
        if len(plain_text) < 180:
            return False

        if not nonempty_lines:
            return False

        if not _workspace_solomon_markdown_heading_matches(
            nonempty_lines[0],
            "Key Details",
        ):
            return False

        bullet_count = len(
            re.findall(
                r"(?m)^\s*[-*+]\s+\S",
                clean_text,
            )
        )

        if bullet_count < 4:
            return False

    elif (
        action
        == WORKSPACE_SOLOMON_REQUEST_ACTION_COMPARE_SOURCES
    ):
        if len(plain_text) < 250:
            return False

        if not nonempty_lines:
            return False

        if not _workspace_solomon_markdown_heading_matches(
            nonempty_lines[0],
            "Comparison",
        ):
            return False

        comparison_body = (
            _workspace_solomon_plain_text_for_validation(
                "\n".join(
                    nonempty_lines[1:]
                )
            )
        )
        comparison_sentences = [
            sentence.strip()
            for sentence in re.split(
                r"(?<=[.!?])(?:[\"')\]]*)\s+",
                comparison_body,
            )
            if sentence.strip()
        ]

        if len(comparison_sentences) < 3:
            return False

    return True
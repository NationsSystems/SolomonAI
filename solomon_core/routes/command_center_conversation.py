# -------------------------------------------------------------
# FILE: command_center_conversation.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------
# Command Center Conversation
#
# PURPOSE
#   Handles the main Home Ask Solomon surface as a lean V3 guidance path.
#
# CONTRACT
#   Home is a HUD-style conversational surface. It may answer, orient,
#   clarify, and help shape working text. It does not enter Investigator,
#   casefile persistence, orchestrator lanes, DocIntel, embeddings, Blaze,
#   V1-derived task engines, route navigation, or workflow activation.
#
# DIALOG MODEL
#   answer = LLM-owned response text from a live model call.
#   bridge = optional LLM-owned handoff text from the same live model call.
#   suggestion_actions = intentionally empty for the normal Home path.
#   Python validates, cleans, and packetizes model output. Python may enforce
#   boundaries and remove unsafe or malformed UX elements, but it must not
#   author the normal answer body, normal bridge, or fake intelligent chips.
#   The workspace owns real actions, buttons, navigation, and next-step
#   controls; SolomonAI Home owns concise explanation and clarification.
#
# PRODUCT ROLE
#   Home is the secondary value layer. The workspace, files, modules, and
#   governed review paths provide the primary product value. SolomonAI Home
#   reduces user friction by explaining where work belongs, shaping working
#   text, and guiding users toward the correct product surface without
#   becoming the product or claiming execution authority.
# -------------------------------------------------------------

from __future__ import annotations

import html
import json
import re
from time import perf_counter
from typing import Any, Callable

from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
)
from solomon_core.llm.llm_executor import execute_llm
from solomon_core.logger import get_logger

logger = get_logger("command_center_conversation")

_HOME_CALL_SITE = "solomon_home_answer_assistant"
_HOME_RESPONSE_BUDGET_MS = 3500
_MAX_USER_TEXT_CHARS = 360
_MAX_ANSWER_CHARS = 320
_MAX_BRIDGE_CHARS = 64
_MAX_ANSWER_WORDS = 36
_MAX_BRIDGE_WORDS = 8
_MIN_BRIDGE_WORDS = 4
_BRIDGE_BAD_FINAL_WORDS = frozenset({
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "by",
    "explicit",
    "for",
    "from",
    "in",
    "into",
    "of",
    "on",
    "or",
    "should",
    "that",
    "the",
    "to",
    "with",
    "your",
})
_HOME_COPY_BLOCKED_TERMS = (
    "your nation",
    "your nation's",
    "nation's",
    "national",
    "country",
    "government",
)
_MAX_SUGGESTION_CHARS = 48
_MAX_SUGGESTION_WORDS = 5
_MIN_SUGGESTIONS = 3
_MAX_SUGGESTIONS = 3
_MAX_CONTEXT_TURNS = 1
_MAX_CONTEXT_USER_CHARS = 48
_MAX_CONTEXT_ANSWER_CHARS = 60
_CHIP_ORIGIN_SYSTEM = "system"
_CHIP_KIND_SYSTEM_PROMPT = "system_prompt"
_CHIP_POLICY_PROMPT_ONLY = "prompt_only_no_execution"
_CHIP_CONTRACT_SYSTEM_PROMPTS = "system_prompt_chips"
_HOME_DIALOG_ROLE = "secondary_guidance_layer"
_HOME_AUTHORITY_POLICY = "high_usefulness_low_authority"
_HOME_VALUE_POSITION = "workspace_first_solomonai_second"

HomeStreamCallback = Callable[[str, dict], None]

_ALLOWED_INTENTS = frozenset({
    "workspace",
    "workspace_navigation",
    "documents",
    "document_help",
    "document_analysis",
    "workflow",
    "workflow_start",
    "drafting",
    "casual_answer",
    "capability_explanation",
    "clarification",
    "outside",
    "unsupported",
    "error_recovery",
})

_GENERIC_SUGGESTIONS = frozenset({
    "tell me more",
    "explain more",
    "explain further",
    "learn more",
    "more details",
    "real world applications",
    "real-world applications",
    "next steps",
    "what next",
    "continue",
    "go on",
    "more options",
    "helpful follow up questions",
    "helpful follow-up questions",
})

_DOCUMENT_FILE_TERMS = (
    "pdf",
    "doc",
    "docx",
    "xls",
    "xlsx",
    "csv",
    "txt",
    "rtf",
    "report",
    "reports",
    "agreement",
    "agreements",
    "contract",
    "contracts",
    "policy",
    "policies",
    "memo",
    "memos",
    "spreadsheet",
    "spreadsheets",
    "presentation",
    "presentations",
)

_HOME_ANSWER_PROMPT = """
You are SolomonAI Home for Nations Systems V3.

Output exactly:
A: <one or two complete sentences, 16-30 words total>
B:

No JSON. No bullets. No chips. No suggestions. Stop after B.

Rules:
- Speak directly to the user.
- Use the Fact line as grounding, not as a script.
- Sound like a premium workspace assistant, not an internal product label.
- Home only explains, orients, and shapes text.
- Never claim upload, review, analysis, navigation, approval, or workflow execution happened.
- For vague followups, continue the workspace guidance instead of naming the request type.
- Avoid goals, priorities, objectives, nation, national, country, and government.
- Leave B blank.
""".strip()


def _elapsed_ms(started_at: float) -> float:
    return (perf_counter() - started_at) * 1000


def _safe_dict(value: Any) -> dict:
    return value if isinstance(value, dict) else {}


def _clip_text(value: Any, limit: int) -> str:
    clean_value = str(value or "").strip()

    if len(clean_value) <= limit:
        return clean_value

    return clean_value[:limit].strip()


def _clip_text_on_word(value: Any, limit: int) -> str:
    clean_value = " ".join(str(value or "").strip().split())

    if len(clean_value) <= limit:
        return clean_value

    clipped_value = clean_value[:limit].rsplit(" ", 1)[0].strip()

    return clipped_value or clean_value[:limit].strip()


def _normalize_text(value: Any) -> str:
    clean_value = str(value or "").strip().lower()
    clean_value = re.sub(r"[^a-z0-9\s]", " ", clean_value)
    clean_value = re.sub(r"\s+", " ", clean_value)

    return clean_value.strip()


def _clean_display_text(value: Any) -> str:
    clean_value = html.unescape(str(value or "").strip())
    clean_value = clean_value.strip("`").strip().strip('"').strip("'").strip()
    clean_value = re.sub(r"\s+", " ", clean_value)
    clean_value = re.sub(r"\s+([,.!?;:])", r"\1", clean_value)
    clean_value = re.sub(r",\s*([.!?])", r"\1", clean_value)

    return clean_value.strip()


def _text_has_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _word_count(value: str) -> int:
    return len(str(value or "").split())


def _is_followup_request(task_text: str) -> bool:
    normalized_text = _normalize_text(task_text)

    if not normalized_text:
        return False

    exact_followups = {
        "what else",
        "anything else",
        "what other things",
        "what other options",
        "more",
        "continue",
        "go on",
        "and then",
        "what about that",
        "show me more",
        "more options",
        "what next",
        "next",
        "explain that",
        "explain this",
        "explain it",
        "clarify that",
        "clarify this",
        "clarify it",
        "can you clarify that",
        "can you clarify this",
        "can you explain that",
        "can you explain this",
        "what does that mean",
        "what does this mean",
        "what do you mean",
        "expand on that",
        "expand on this",
        "say that another way",
        "say this another way",
    }

    if normalized_text in exact_followups:
        return True

    if _text_has_any(
        normalized_text,
        (
            "what else can",
            "what else do",
            "what else would",
            "what else should",
            "anything else can",
            "anything else do",
            "other things can",
            "other options can",
            "what more can",
            "what else is available",
            "what other paths",
            "what other workflows",
            "what other areas",
            "tell me more about that",
            "tell me more about this",
            "explain more about that",
            "explain more about this",
            "clarify what you mean",
            "clarify the previous",
            "explain the previous",
            "expand on the previous",
        ),
    ):
        return True

    has_context_pronoun = _text_has_any(
        normalized_text,
        (
            " that",
            " this",
            " it",
            " those",
            " these",
            "previous",
            "earlier",
            "last answer",
            "last response",
        ),
    )
    asks_for_explanation = _text_has_any(
        normalized_text,
        (
            "explain",
            "clarify",
            "expand",
            "elaborate",
            "mean",
            "means",
            "more detail",
            "more details",
            "break down",
            "simplify",
        ),
    )

    if has_context_pronoun and asks_for_explanation:
        return True

    return (
        _text_has_any(normalized_text, ("else", "other", "more", "another"))
        and _text_has_any(normalized_text, ("can you", "do", "help", "options", "paths"))
    )


def _clean_home_context_turn(value: Any) -> dict:
    if not isinstance(value, dict):
        return {}

    user_text = _clip_text_on_word(value.get("user"), _MAX_CONTEXT_USER_CHARS)
    answer = _clip_text_on_word(value.get("answer"), _MAX_CONTEXT_ANSWER_CHARS)

    if not user_text and not answer:
        return {}

    return {
        "user": user_text,
        "answer": answer,
    }


def _home_message_context(command_context: dict) -> list[dict]:
    turns = command_context.get("home_message_context")

    if not isinstance(turns, list):
        return []

    clean_turns = []

    for turn in turns[-_MAX_CONTEXT_TURNS:]:
        clean_turn = _clean_home_context_turn(turn)

        if clean_turn:
            clean_turns.append(clean_turn)

    return clean_turns[-_MAX_CONTEXT_TURNS:]


def _format_home_context(turns: list[dict]) -> str:
    if not turns:
        return ""

    parts = []

    for turn in turns:
        user_text = turn.get("user") or ""
        answer = turn.get("answer") or ""

        if user_text and answer:
            parts.append(f'Prior: user="{user_text}" answer="{answer}"')
        elif user_text:
            parts.append(f'Prior user="{user_text}"')
        elif answer:
            parts.append(f'Prior answer="{answer}"')

    return " ".join(parts).strip()


def _prompt_action(label: str, prompt: str = "") -> dict:
    clean_label = _clip_text_on_word(label, _MAX_SUGGESTION_CHARS)
    clean_prompt = _clip_text_on_word(prompt or clean_label, _MAX_SUGGESTION_CHARS)

    return {
        "label": clean_label,
        "type": "prompt",
        "target": clean_prompt,
        "origin": _CHIP_ORIGIN_SYSTEM,
        "chip_kind": _CHIP_KIND_SYSTEM_PROMPT,
        "chip_policy": _CHIP_POLICY_PROMPT_ONLY,
    }


def _is_workflow_request(normalized_text: str) -> bool:
    if not normalized_text:
        return False

    exact_requests = {
        "what workflows are available",
        "show available workflows",
        "available workflows",
        "show workflows",
        "explain workflows",
        "what workflow paths are available",
    }

    if normalized_text in exact_requests:
        return True

    return _text_has_any(
        normalized_text,
        (
            "available workflows",
            "what workflows",
            "show workflows",
            "show me workflows",
            "workflow paths",
            "review path",
            "review paths",
            "governed actions",
            "governed workflows",
        ),
    )


def _is_drafting_request(normalized_text: str) -> bool:
    if not normalized_text:
        return False

    return _text_has_any(
        normalized_text,
        (
            "email",
            "note",
            "draft",
            "message",
            "write",
            "rewrite",
            "summarize",
            "outline",
            "plan",
            "shape text",
            "shape working text",
            "working text",
            "tighten wording",
            "tighten this",
            "make this clearer",
            "make this sound",
            "word this",
            "reword",
            "polish this",
            "clean this up",
        ),
    )


def _is_capability_request(normalized_text: str) -> bool:
    exact_requests = {
        "what can i do",
        "what can you do",
        "what do you do",
        "how does this work",
        "explain this workspace",
        "explain home",
        "what is solomon",
        "what is solomonai",
        "what is nations systems",
    }

    if normalized_text in exact_requests:
        return True

    return _text_has_any(
        normalized_text,
        (
            "what can solomon do",
            "what can solomonai do",
            "what can i do here",
            "what is this workspace",
            "show me what you can do",
            "explain what i can do",
            "explain the workspace",
        ),
    )


def _is_unsupported_request(normalized_text: str) -> bool:
    return _text_has_any(
        normalized_text,
        (
            "delete all",
            "remove all",
            "purge",
            "payroll",
            "send to accounting",
            "change company settings",
            "change system settings",
            "reset password",
            "create user",
            "disable user",
            "approve invoice",
            "pay invoice",
            "sign contract",
        ),
    )


def _is_outside_request(normalized_text: str) -> bool:
    return _text_has_any(
        normalized_text,
        (
            "weather",
            "stock price",
            "sports score",
            "latest news",
            "live news",
            "search the web",
            "search internet",
            "browse the internet",
            "current price",
            "current market",
        ),
    )


def _is_document_file_reference(normalized_text: str) -> bool:
    if not normalized_text:
        return False

    if _text_has_any(normalized_text, _DOCUMENT_FILE_TERMS):
        return True

    return bool(
        re.search(
            r"\b[\w\-]+\s+(pdf|doc|docx|xls|xlsx|csv|txt|rtf)\b",
            normalized_text,
        )
    )


def _is_document_request(normalized_text: str) -> bool:
    return (
        _text_has_any(
            normalized_text,
            ("document", "documents", "docs", "upload", "file", "files", "record", "records"),
        )
        or _is_document_file_reference(normalized_text)
    )


def _is_document_analysis_request(normalized_text: str) -> bool:
    return _text_has_any(
        normalized_text,
        (
            "analysis",
            "analyze",
            "analyse",
            "review document",
            "review file",
            "summarize document",
            "summarize file",
            "extract details",
            "find issues",
            "risk signals",
            "missing information",
            "decision ready",
        ),
    )


def _is_navigation_request(normalized_text: str) -> bool:
    return _text_has_any(
        normalized_text,
        (
            "open",
            "show",
            "take me",
            "go to",
            "navigate",
            "bring up",
            "pull up",
            "where is",
            "where do",
            "where can",
            "where should",
        ),
    )


def _is_protected_document_action(normalized_text: str) -> bool:
    if not _is_document_request(normalized_text):
        return False

    return _text_has_any(
        normalized_text,
        (
            "analyze",
            "analyse",
            "classify",
            "process",
            "review all",
            "scan",
            "use this",
            "use in workflow",
            "run review",
            "read my",
            "read the",
        ),
    )


def _is_ambiguous_request(normalized_text: str) -> bool:
    if not normalized_text:
        return True

    exact_ambiguous = {
        "help",
        "help me",
        "check this",
        "review this",
        "look at this",
        "what should i do",
        "what should i do next",
        "where should i start",
        "start",
        "begin",
    }

    if normalized_text in exact_ambiguous:
        return True

    return (
        len(normalized_text.split()) <= 4
        and _text_has_any(normalized_text, ("help", "check", "review", "start", "begin"))
        and not _is_document_request(normalized_text)
        and not _is_document_analysis_request(normalized_text)
    )


def _is_vague_next_step_request(normalized_text: str) -> bool:
    if not normalized_text:
        return False

    exact_requests = {
        "help",
        "help me",
        "what should i do",
        "what should i do next",
        "where should i start",
        "what next",
        "next",
        "start",
        "begin",
        "explain that",
        "explain this",
        "can you explain that",
        "can you explain this",
        "clarify that",
        "clarify this",
        "can you clarify that",
        "can you clarify this",
    }

    if normalized_text in exact_requests:
        return True

    return _text_has_any(
        normalized_text,
        (
            "what should i do next",
            "where should i start",
            "what path should",
            "which path should",
            "what workflow should",
            "which workflow should",
            "what should i choose",
            "what should i use",
            "what do i do next",
            "explain the previous",
            "clarify the previous",
        ),
    )


def _is_simple_greeting(normalized_text: str) -> bool:
    return normalized_text in {
        "hello",
        "hi",
        "hey",
        "thanks",
        "thank you",
        "appreciate it",
        "ok",
        "okay",
    }


def _is_simple_casual_request(normalized_text: str) -> bool:
    if not normalized_text:
        return False

    if _is_followup_request(normalized_text):
        return False

    if _is_document_request(normalized_text) or _is_document_analysis_request(normalized_text):
        return False

    if _text_has_any(
        normalized_text,
        (
            "workflow",
            "workspace",
            "route",
            "navigate",
            "open",
            "upload",
            "admin",
            "settings",
            "analyze",
            "classify",
            "process",
        ),
    ):
        return False

    arithmetic_pattern = r"^(what is|what s|calculate|solve)?\s*[0-9\s+\-*/x÷().]+$"

    if re.match(arithmetic_pattern, normalized_text):
        return True

    return _text_has_any(
        normalized_text,
        (
            "what is",
            "whats",
            "define",
            "explain",
            "summarize this sentence",
            "make this clearer",
            "hello",
            "hi",
            "thanks",
            "thank you",
        ),
    )


def _infer_intent_from_text(task_text: str) -> str:
    normalized_text = _normalize_text(task_text)

    if _is_unsupported_request(normalized_text):
        return "unsupported"
    if _is_outside_request(normalized_text):
        return "outside"
    if _is_capability_request(normalized_text):
        return "capability_explanation"
    if _is_workflow_request(normalized_text):
        return "workflow"
    if _is_followup_request(normalized_text):
        return "clarification"
    if _is_document_analysis_request(normalized_text):
        if _is_document_request(normalized_text) or _is_navigation_request(normalized_text):
            return "workflow_start"

        return "document_analysis"
    if _is_document_request(normalized_text):
        if _is_navigation_request(normalized_text):
            return "documents"

        if _is_protected_document_action(normalized_text):
            return "document_help"

        return "documents"
    if _is_drafting_request(normalized_text):
        return "drafting"
    if _is_ambiguous_request(normalized_text):
        return "clarification"
    if _is_simple_casual_request(normalized_text):
        return "casual_answer"

    return "workspace"


def _normalize_intent(value: Any, task_text: str) -> str:
    clean_value = _normalize_text(value).replace(" ", "_")

    if clean_value in _ALLOWED_INTENTS:
        return clean_value

    return _infer_intent_from_text(task_text)


def _home_grounding_for_intent(intent: str, task_text: str = "") -> str:
    normalized_text = _normalize_text(task_text)

    if intent == "documents":
        if _is_document_file_reference(normalized_text):
            return "Use My Files to store the selected file first. Start governed review only after an explicit handoff."

        return "Use My Files to store, preview, organize, and select documents. Uploading a document does not analyze it."

    if intent == "document_help":
        return "You can ask for document handling guidance here. Actual document analysis belongs inside a governed review."

    if intent == "workflow_start":
        if _text_has_any(normalized_text, ("upload", "where do", "where can", "where should")):
            return "Start in My Files. Upload the document there before starting Document Analysis."

        return "Use Document Analysis for stored files when you need key details, issues, missing information, and decision-ready risk signals."

    if intent == "document_analysis":
        return "Document Analysis helps review selected files for key details, notable issues, missing information, and decision-ready risk signals."

    if intent == "workflow":
        return "You can work through My Files, Reader inspection, Document Analysis, drafting help, or governed handoffs."

    if intent == "drafting":
        return "You can paste working text here for clearer wording, tighter structure, or a more professional tone."

    if intent == "capability_explanation":
        if _text_has_any(normalized_text, ("workspace", "home")):
            return "This workspace brings together My Files, Reader inspection, Document Analysis, SolomonAI, and drafting help."

        return "You can ask workspace questions, understand file paths, prepare review work, or shape working text."

    if intent == "clarification":
        if _is_vague_next_step_request(normalized_text):
            return "A good next step is choosing between My Files, Reader inspection, Document Analysis, SolomonAI, or drafting help."

        if _is_followup_request(task_text):
            return "Continue the prior answer by explaining the relevant workspace path in plain user-facing language."

        return "Clarify the next direction by naming the most useful workspace path."

    if intent in {"outside", "unsupported"}:
        return "That request belongs outside Home. Redirect toward valid workspace controls without claiming action."

    return "The file-browser workspace is the primary surface; this conversation provides fast guidance around it."


def _build_home_prompt(
    *,
    task_text: str,
    command_context: dict,
    workspace_context: dict,
    command_manifest: dict,
) -> str:
    del workspace_context, command_manifest

    user_text = _clip_text(task_text, _MAX_USER_TEXT_CHARS)
    intent = _infer_intent_from_text(task_text)
    grounding_text = _home_grounding_for_intent(intent, task_text)
    context_turns = _home_message_context(command_context)
    is_followup = _is_followup_request(task_text)
    context_text = _format_home_context(context_turns) if is_followup else ""
    followup_text = ""

    if context_turns and is_followup:
        followup_text = "Continue from prior context; stay workspace-specific."

    prompt_parts = [
        _HOME_ANSWER_PROMPT,
        f"Fact: {grounding_text}",
        f"Intent: {intent}.",
    ]

    if context_text:
        prompt_parts.append(context_text)

    if followup_text:
        prompt_parts.append(followup_text)

    prompt_parts.append(f"User: {user_text}")

    return "\n".join(part for part in prompt_parts if part)


def _parse_json_candidate(value: Any) -> dict:
    if isinstance(value, dict):
        return value

    if not isinstance(value, str):
        return {}

    clean_value = value.strip()

    if not clean_value:
        return {}

    try:
        parsed = json.loads(clean_value)

        if isinstance(parsed, dict):
            return parsed

        if isinstance(parsed, str):
            return _parse_json_candidate(parsed)
    except json.JSONDecodeError:
        return {}
    except Exception:
        return {}

    return {}


def _json_text_candidates(model_text: str) -> list[str]:
    clean_text = html.unescape(str(model_text or "").strip())

    if not clean_text:
        return []

    candidates = [clean_text]

    stripped = clean_text.strip().rstrip(".").strip()
    if stripped and stripped != clean_text:
        candidates.append(stripped)

    if clean_text.startswith("{{"):
        candidates.append(clean_text[1:].strip())
        candidates.append(clean_text[1:].strip().rstrip(".").strip())

    if clean_text.endswith("}}"):
        candidates.append(clean_text[:-1].strip())
        candidates.append(clean_text[:-1].strip().rstrip(".").strip())

    if clean_text.startswith("{{") and clean_text.endswith("}}"):
        candidates.append(clean_text[1:-1].strip())

    start_index = clean_text.find("{")
    end_index = clean_text.rfind("}")

    if start_index >= 0 and end_index > start_index:
        segment = clean_text[start_index:end_index + 1].strip()
        candidates.append(segment)

        if segment.startswith("{{"):
            candidates.append(segment[1:].strip())

        if segment.endswith("}}"):
            candidates.append(segment[:-1].strip())

        if segment.startswith("{{") and segment.endswith("}}"):
            candidates.append(segment[1:-1].strip())

    escaped_candidate = clean_text.replace('\\"', '"')
    if escaped_candidate != clean_text:
        candidates.append(escaped_candidate)

        escaped_start = escaped_candidate.find("{")
        escaped_end = escaped_candidate.rfind("}")

        if escaped_start >= 0 and escaped_end > escaped_start:
            candidates.append(escaped_candidate[escaped_start:escaped_end + 1].strip())

    seen = set()
    clean_candidates = []

    for candidate in candidates:
        clean_candidate = str(candidate or "").strip()

        if not clean_candidate or clean_candidate in seen:
            continue

        seen.add(clean_candidate)
        clean_candidates.append(clean_candidate)

    return clean_candidates


def _extract_labeled_plain_text_field(
    model_text: str,
    labels: tuple[str, ...],
    stop_labels: tuple[str, ...],
) -> str:
    clean_text = html.unescape(str(model_text or "").strip())

    if not clean_text:
        return ""

    normalized_text = clean_text.replace("\r\n", "\n").replace("\r", "\n")
    normalized_text = re.sub(
        r"\s+((?:a|b|answer|bridge|c|chip|chips|suggestion|suggestions)\s*:)",
        r"\n\1",
        normalized_text,
        flags=re.I,
    )

    label_pattern = "|".join(re.escape(label) for label in labels)
    stop_pattern = "|".join(re.escape(label) for label in stop_labels)
    match = re.search(
        rf"(?:^|\n)\s*(?:{label_pattern})\s*:\s*(.*?)(?=(?:\n\s*(?:{stop_pattern})\s*:)|\Z)",
        normalized_text,
        flags=re.I | re.S,
    )

    if not match:
        return ""

    return _clean_display_text(match.group(1))


def _extract_json_object(model_text: str) -> dict:
    for candidate in _json_text_candidates(model_text):
        parsed = _parse_json_candidate(candidate)

        if parsed:
            return parsed

    return {}


def _json_field(parsed: dict, verbose_key: str, compact_key: str) -> Any:
    if verbose_key in parsed:
        return parsed.get(verbose_key)

    return parsed.get(compact_key)


def _looks_like_json_payload_text(value: Any) -> bool:
    clean_value = html.unescape(str(value or "").strip())
    clean_value = clean_value.strip("`").strip()

    if not clean_value:
        return False

    return (
        clean_value.startswith("{")
        or clean_value.startswith("[")
        or clean_value.startswith('"{')
        or clean_value.startswith("'{")
        or clean_value.startswith('\\"{')
    )


def _extract_partial_json_text_field(model_text: str, key: str) -> str:
    clean_text = str(model_text or "")
    key_match = re.search(rf'"{re.escape(key)}"\s*:', clean_text, flags=re.I)

    if not key_match:
        return ""

    remainder = clean_text[key_match.end():].lstrip()

    if not remainder:
        return ""

    if not remainder.startswith('"'):
        value_match = re.match(r"([^,}\n]+)", remainder)

        return _clean_display_text(value_match.group(1)) if value_match else ""

    raw_chars = []
    escaped = False

    for character in remainder[1:]:
        if escaped:
            raw_chars.append(f"\\{character}")
            escaped = False
            continue

        if character == "\\":
            escaped = True
            continue

        if character == '"':
            break

        raw_chars.append(character)

    raw_value = "".join(raw_chars).strip()

    if not raw_value:
        return ""

    try:
        decoded_value = json.loads(f'"{raw_value}"')

        return _clean_display_text(decoded_value)
    except json.JSONDecodeError:
        return _clean_display_text(
            raw_value
            .replace('\\"', '"')
            .replace("\\n", " ")
            .replace("\\t", " ")
        )


def _emit_home_stream_event(
    stream_callback: HomeStreamCallback | None,
    event_name: str,
    payload: dict,
) -> None:
    if stream_callback is None:
        return

    try:
        stream_callback(event_name, payload)
    except Exception:
        logger.debug("[HOME_LLM][STREAM_CALLBACK_SKIPPED] event=%s", event_name)


def _build_home_model_stream_callback(
    *,
    stream_callback: HomeStreamCallback | None,
    request_id: str,
) -> Callable[[str], None] | None:
    if stream_callback is None:
        return None

    state = {
        "raw_text": "",
        "answer_text": "",
    }

    def _handle_model_chunk(chunk: str) -> None:
        clean_chunk = str(chunk or "")

        if not clean_chunk:
            return

        state["raw_text"] = f'{state["raw_text"]}{clean_chunk}'
        raw_text = state["raw_text"]
        answer_text = ""

        if _looks_like_json_payload_text(raw_text):
            answer_text = (
                _extract_partial_json_text_field(raw_text, "answer")
                or _extract_partial_json_text_field(raw_text, "a")
            )
        else:
            answer_text = _extract_labeled_plain_text_field(
                raw_text,
                ("a", "answer"),
                ("b", "bridge", "c", "chip", "chips", "suggestion", "suggestions"),
            )
            if not answer_text:
                answer_text = _clean_display_text(raw_text)
                answer_text = re.sub(r"^\s*a\s*:\s*", "", answer_text, flags=re.I)
                answer_text = re.sub(r"^\s*answer\s*:\s*", "", answer_text, flags=re.I)
                answer_text = re.sub(r"^\s*response\s*:\s*", "", answer_text, flags=re.I)

        if not answer_text:
            return

        previous_answer = state["answer_text"]

        if len(answer_text) <= len(previous_answer):
            return

        delta_text = answer_text[len(previous_answer):]

        if not delta_text:
            return

        state["answer_text"] = answer_text
        _emit_home_stream_event(
            stream_callback,
            "home_delta",
            {
                "request_id": request_id,
                "text": delta_text,
            },
        )

    return _handle_model_chunk


def _execute_home_llm(
    *,
    prompt: str,
    request_id: str,
    stream_callback: HomeStreamCallback | None,
) -> Any:
    llm_input = LLMExecutionInput(
        user_query=prompt,
        mode=LLMExecutionMode.INFORMATIONAL_ONLY,
        context=None,
        call_site=_HOME_CALL_SITE,
    )
    model_stream_callback = _build_home_model_stream_callback(
        stream_callback=stream_callback,
        request_id=request_id,
    )

    if model_stream_callback is None:
        return execute_llm(llm_input)

    _emit_home_stream_event(
        stream_callback,
        "home_model_start",
        {
            "request_id": request_id,
        },
    )

    try:
        return execute_llm(
            llm_input,
            stream_callback=model_stream_callback,
        )
    except TypeError as exc:
        if "stream_callback" not in str(exc):
            raise

        logger.warning(
            "[HOME_LLM][STREAM_UNSUPPORTED] request_id=%s reason=%s",
            request_id,
            exc,
        )
        return execute_llm(llm_input)


def _trim_to_answer_sentences(value: str) -> str:
    clean_value = str(value or "").strip()
    sentence_matches = re.findall(r"[^.!?]+[.!?](?:\s|$)", clean_value)

    if sentence_matches:
        return " ".join(
            sentence.strip()
            for sentence in sentence_matches[:2]
            if sentence.strip()
        ).strip()

    return clean_value


def _limit_answer_words(value: str) -> str:
    words = str(value or "").split()

    if len(words) <= _MAX_ANSWER_WORDS:
        return str(value or "").strip()

    trimmed = " ".join(words[:_MAX_ANSWER_WORDS]).rstrip(" ,;:")

    if not trimmed.endswith((".", "!", "?")):
        trimmed = f"{trimmed}."

    return trimmed


def _complete_sentence(value: str) -> str:
    clean_value = str(value or "").strip()

    if clean_value and not clean_value.endswith((".", "!", "?")):
        return f"{clean_value}."

    return clean_value


def _copy_has_blocked_home_terms(value: str) -> bool:
    normalized_value = _normalize_text(value)

    if not normalized_value:
        return False

    return _text_has_any(normalized_value, _HOME_COPY_BLOCKED_TERMS)


def _repair_home_identity_confusion(value: str) -> str:
    clean_value = str(value or "").strip()

    if not clean_value:
        return ""

    replacements = (
        (r"\byour nation\'s\b", "this workspace's"),
        (r"\byour nation\b", "this workspace"),
        (r"\bnation\'s\b", "workspace"),
        (r"\bnational\b", "workspace"),
        (r"\bcountry\b", "workspace"),
        (r"\bgovernment\b", "workspace"),
    )

    for pattern, replacement in replacements:
        clean_value = re.sub(pattern, replacement, clean_value, flags=re.I)

    return clean_value.strip()


def _repair_generic_next_step_copy(value: str) -> str:
    clean_value = str(value or "").strip()

    if not clean_value:
        return ""

    replacements = (
        (
            r"\breview your goals and priorities to guide your next steps\b",
            "Start with My Files, Reader inspection, Document Analysis, SolomonAI, or drafting help",
        ),
        (
            r"\breview the listed options for your next step\b",
            "Start with My Files, Reader inspection, Document Analysis, SolomonAI, or drafting help",
        ),
        (
            r"\bfocus on your primary objective first\b",
            "Choose a workspace path to start",
        ),
        (
            r"\bfocus on what matters most to your objectives\b",
            "Choose the matching workspace path",
        ),
        (
            r"\bfocus on available data before acting\b",
            "Choose the matching workspace path",
        ),
    )

    for pattern, replacement in replacements:
        clean_value = re.sub(pattern, replacement, clean_value, flags=re.I)

    return clean_value.strip()


def _bridge_is_malformed(value: str) -> bool:
    clean_value = _clean_display_text(value)
    bare_value = clean_value.rstrip(".!?").strip()

    if not bare_value:
        return True

    words = bare_value.split()
    word_count = len(words)

    if word_count < _MIN_BRIDGE_WORDS or word_count > _MAX_BRIDGE_WORDS:
        return True

    if _copy_has_blocked_home_terms(bare_value):
        return True

    final_word = re.sub(r"[^a-z0-9&]", "", words[-1].lower())

    if final_word in _BRIDGE_BAD_FINAL_WORDS:
        return True

    normalized_value = _normalize_text(bare_value)

    if normalized_value in {
        "it is the",
        "its the",
        "which path should",
        "what path should",
        "focus on the one",
        "my files reader inspection",
    }:
        return True

    if normalized_value.endswith("only after explicit"):
        return True

    if normalized_value.endswith("reader inspection"):
        return True

    if re.search(r"\b(which|what)\s+\w+\s+should$", normalized_value):
        return True

    if re.search(r"\b(aligns|aligned|focus|choose|select)\s+with\s+your$", normalized_value):
        return True

    return False


def _strip_generic_closers(value: str) -> str:
    clean_value = str(value or "").strip()

    closer_patterns = (
        r"\s+Let me know what you need\.?$",
        r"\s+Tell me what you need\.?$",
        r"\s+Tell me where you want to start\.?$",
        r"\s+Ask me what you need next\.?$",
        r"\s+I am here to help\.?$",
        r"\s+I'm here to help\.?$",
    )

    for pattern in closer_patterns:
        clean_value = re.sub(pattern, "", clean_value, flags=re.I).strip()

    return clean_value


def _polish_answer_copy(value: str) -> str:
    clean_value = html.unescape(str(value or "").strip())
    clean_value = _repair_home_identity_confusion(clean_value)
    clean_value = _repair_generic_next_step_copy(clean_value)
    clean_value = re.sub(
        r"\bfor vague next-step questions,?\s*",
        "",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bHome answers workspace questions, explains file and review paths, and helps shape working text\b",
        "You can ask workspace questions, understand file paths, prepare review work, or shape working text",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bHome delivers fast guidance for\b",
        "This workspace gives you quick guidance around",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bHome can quickly shape working text while the workspace and modules remain the primary product surfaces\b",
        "Yes. Paste the text you want shaped, and I can help make it clearer, tighter, or more professional",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bHome can explain document handling\b",
        "You can ask for document handling guidance",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bHome is the fast guidance layer for\b",
        "This workspace gives you quick guidance around",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bHome should clarify\b",
        "I can clarify",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bpoint to My Files\b",
        "start with My Files",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bclarify document posture\b",
        "clarify document review paths",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bdocument posture\b",
        "document review path",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bdocument command surface\b",
        "document workspace",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bdocument analysis\b",
        "document guidance",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\banalyze documents\b",
        "guide document paths",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\banalyzes documents\b",
        "guides document paths",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\banalyzing documents\b",
        "guiding document paths",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\band help tighten\b",
        "and help shape working text",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bhelp tighten\b",
        "help shape working text",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bhelp tighten wording\b",
        "help shape wording",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bimprove working text\b",
        "shape working text",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bshape working\b(?!\s+text)",
        "shape working text",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bguide Docs and Document Analysis\b",
        "guide document handling and Document Analysis",
        clean_value,
        flags=re.I,
    )
    clean_value = re.sub(
        r"\bDocs\b",
        "Documents",
        clean_value,
        flags=re.I,
    )

    return clean_value.strip()


def _clean_answer_value(value: Any) -> str:
    clean_value = _clean_display_text(value)
    clean_value = re.sub(r'^\s*\{?\s*"answer"\s*:\s*', "", clean_value, flags=re.I)
    clean_value = re.sub(r'^\s*\{?\s*"a"\s*:\s*', "", clean_value, flags=re.I)
    clean_value = re.sub(r'"\s*,\s*"bridge"\s*:.*$', "", clean_value, flags=re.I)
    clean_value = re.sub(r'"\s*,\s*"b"\s*:.*$', "", clean_value, flags=re.I)
    clean_value = re.sub(r"\s+(?:b|bridge)\s*:\s*.*$", "", clean_value, flags=re.I)
    clean_value = re.sub(r"\s+(?:c|chips?|suggestions?)\s*:\s*.*$", "", clean_value, flags=re.I)
    clean_value = re.sub(r"^\s*[-*]\s*", "", clean_value)
    clean_value = re.sub(r"^\s*a\s*:\s*", "", clean_value, flags=re.I)
    clean_value = re.sub(r"^\s*answer\s*:\s*", "", clean_value, flags=re.I)
    clean_value = re.sub(r"^\s*response\s*:\s*", "", clean_value, flags=re.I)
    clean_value = _polish_answer_copy(clean_value)
    clean_value = _trim_to_answer_sentences(clean_value)
    clean_value = _strip_generic_closers(clean_value)
    clean_value = _limit_answer_words(clean_value)
    clean_value = _complete_sentence(clean_value)

    return _clip_text(clean_value, _MAX_ANSWER_CHARS)


def _clean_bridge_value(value: Any) -> str:
    del value

    return ""


def _polish_suggestion_copy(value: str) -> str:
    return _clean_display_text(value)


def _clean_suggestion_value(value: Any) -> str:
    clean_value = _polish_suggestion_copy(value)
    clean_value = re.sub(r"^\s*[-*]\s*", "", clean_value)
    clean_value = re.sub(r"^\s*\d+[.)]\s*", "", clean_value)
    clean_value = _clip_text_on_word(clean_value, _MAX_SUGGESTION_CHARS)

    if _word_count(clean_value) > _MAX_SUGGESTION_WORDS:
        clean_value = " ".join(clean_value.split()[:_MAX_SUGGESTION_WORDS]).rstrip(" ,;:")

    return clean_value.strip()


def _is_generic_suggestion(value: str) -> bool:
    normalized_value = _normalize_text(value)

    if normalized_value in _GENERIC_SUGGESTIONS:
        return True

    return (
        len(normalized_value.split()) <= 2
        and normalized_value in {"more", "details", "learn", "continue", "next"}
    )


def _sanitize_suggestions(values: Any) -> list[str]:
    if not isinstance(values, list):
        return []

    clean_suggestions = []
    seen = set()

    for raw_value in values:
        clean_value = _clean_suggestion_value(raw_value)
        normalized_value = _normalize_text(clean_value)

        if not clean_value or normalized_value in seen:
            continue
        if _is_generic_suggestion(clean_value):
            continue

        seen.add(normalized_value)
        clean_suggestions.append(clean_value)

        if len(clean_suggestions) >= _MAX_SUGGESTIONS:
            break

    return clean_suggestions


def _allow_suggestions_for_request(task_text: str, intent: str) -> bool:
    normalized_text = _normalize_text(task_text)

    if not normalized_text or _is_simple_greeting(normalized_text):
        return False

    return intent not in {"casual_answer"}


def _server_suggestions_for_intent(task_text: str, intent: str) -> list[str]:
    # These are deterministic system prompt chips, not LLM-authored reasoning
    # chips. They exist only as safe UI shortcuts into allowed Home prompts.
    if not _allow_suggestions_for_request(task_text, intent):
        return []

    resolved_intent = _normalize_intent(intent, task_text)

    suggestion_sets = {
        "capability_explanation": [
            "ask questions",
            "explain areas",
            "guide documents",
        ],
        "documents": [
            "upload documents",
            "find documents",
            "document paths",
        ],
        "document_help": [
            "document paths",
            "review readiness",
            "upload guidance",
        ],
        "document_analysis": [
            "analysis steps",
            "risk signals",
            "missing details",
        ],
        "workflow_start": [
            "upload documents",
            "analysis steps",
            "risk signals",
        ],
        "workflow": [
            "available workflows",
            "governed actions",
            "workspace paths",
        ],
        "drafting": [
            "rewrite this text",
            "draft a message",
            "tighten wording",
        ],
        "clarification": [
            "documents",
            "document analysis",
            "workspace help",
        ],
        "outside": [
            "workspace help",
            "document guidance",
            "document analysis",
        ],
        "unsupported": [
            "workspace help",
            "document guidance",
            "document analysis",
        ],
        "workspace": [
            "workspace paths",
            "document guidance",
            "document analysis",
        ],
        "workspace_navigation": [
            "workspace paths",
            "document guidance",
            "available workflows",
        ],
        "error_recovery": [
            "try again",
            "workspace help",
            "document guidance",
        ],
    }

    return _sanitize_suggestions(suggestion_sets.get(resolved_intent, suggestion_sets["workspace"]))


def _server_bridge_for_intent(task_text: str, intent: str, suggestions: list[str]) -> str:
    if not suggestions:
        return ""

    resolved_intent = _normalize_intent(intent, task_text)

    bridge_map = {
        "capability_explanation": "Try asking a specific question.",
        "documents": "Choose a document path to continue.",
        "document_help": "Choose a document path to continue.",
        "document_analysis": "Ask about document analysis next.",
        "workflow_start": "Start with the document path.",
        "workflow": "Choose a workspace path to continue.",
        "drafting": "Share the text you want shaped.",
        "clarification": "Choose one direction to narrow it.",
        "outside": "Return to a workspace question.",
        "unsupported": "Use a governed workspace control instead.",
        "workspace": "Ask a specific workspace question.",
        "workspace_navigation": "Choose a workspace path to continue.",
        "error_recovery": "Try a simpler Home question.",
    }

    return _clean_bridge_value(bridge_map.get(resolved_intent, bridge_map["workspace"]))


def _allow_bridge_for_request(task_text: str, intent: str, suggestions: list[str]) -> bool:
    if not suggestions:
        return False

    return _allow_suggestions_for_request(task_text, intent)


def _packet_from_plain_model_text(
    *,
    model_text: str,
    task_text: str,
    intent: str,
) -> dict:
    del task_text, intent

    parsed = _extract_json_object(model_text)
    answer_source = ""
    bridge_source = ""

    if parsed:
        answer_source = _json_field(parsed, "answer", "a")
        bridge_source = _json_field(parsed, "bridge", "b")

    if not answer_source:
        answer_source = (
            _extract_partial_json_text_field(model_text, "answer")
            or _extract_partial_json_text_field(model_text, "a")
            or _extract_labeled_plain_text_field(
                model_text,
                ("a", "answer"),
                ("b", "bridge", "c", "chip", "chips", "suggestion", "suggestions"),
            )
        )

    if not bridge_source:
        bridge_source = (
            _extract_partial_json_text_field(model_text, "bridge")
            or _extract_partial_json_text_field(model_text, "b")
            or _extract_labeled_plain_text_field(
                model_text,
                ("b", "bridge"),
                ("c", "chip", "chips", "suggestion", "suggestions"),
            )
        )

    if not answer_source:
        clean_model_text = str(model_text or "").strip()

        if _looks_like_json_payload_text(clean_model_text):
            return {}

        answer_source = clean_model_text

    answer = _clean_answer_value(answer_source)

    if not answer:
        return {}

    if _looks_like_json_payload_text(answer):
        return {}

    bridge = _clean_bridge_value(bridge_source)

    return {
        "answer": answer,
        "bridge": bridge,
        "suggestions": [],
    }


def _parse_home_response_packet(
    *,
    model_text: str,
    task_text: str,
    intent: str,
) -> dict:
    return _packet_from_plain_model_text(
        model_text=model_text,
        task_text=task_text,
        intent=intent,
    )


def _actions_from_suggestions(suggestions: list[str]) -> list[dict]:
    actions = []

    for suggestion in suggestions[:_MAX_SUGGESTIONS]:
        clean_value = _clean_suggestion_value(suggestion)

        if clean_value:
            actions.append(_prompt_action(clean_value, clean_value))

    return actions


def _suggestion_labels(actions: list[dict]) -> list[str]:
    labels = []

    for action in actions:
        if not isinstance(action, dict):
            continue

        label = str(action.get("label") or "").strip()

        if label:
            labels.append(label)

    return labels[:_MAX_SUGGESTIONS]


def _payload_for_answer(
    *,
    answer: str,
    intent: str,
    task_text: str,
    bridge: str = "",
    suggestions: list[str] | None = None,
) -> dict:
    del suggestions

    resolved_intent = _normalize_intent(intent, task_text)
    resolved_bridge = _clip_text(_clean_bridge_value(bridge), _MAX_BRIDGE_CHARS)

    return {
        "answer": _clip_text(answer, _MAX_ANSWER_CHARS),
        "bridge": resolved_bridge,
        "suggestions": [],
        "suggestion_actions": [],
        "suggestion_origin": "",
        "chip_contract": "",
        "chip_policy": "",
        "ui_actions": [],
        "intent": resolved_intent,
        "type": "response",
        "source": "v3_home_conversation",
        "action_policy": "no_prompt_chips",
        "dialog_contract": "single_llm_call_answer_bridge_packet",
        "dialog_role": _HOME_DIALOG_ROLE,
        "authority_policy": _HOME_AUTHORITY_POLICY,
        "value_position": _HOME_VALUE_POSITION,
    }


def _packet(payload: dict) -> dict:
    safe_payload = _safe_dict(payload)

    return {
        "ok": True,
        "status": "ok",
        "packet_type": "home_conversation_response",
        "payload": safe_payload,
        **safe_payload,
    }


def _error_packet(message: str, request_id: str = "") -> dict:
    payload = _payload_for_answer(
        answer=message,
        bridge="",
        suggestions=[],
        intent="error_recovery",
        task_text=message,
    )

    return {
        "ok": False,
        "status": "error",
        "error": message,
        "request_id": request_id,
        "packet_type": "home_conversation_response",
        "payload": payload,
        **payload,
    }


def _fallback_answer_for_intent(intent: str, task_text: str) -> str:
    grounding_text = _home_grounding_for_intent(intent, task_text)

    if grounding_text:
        return _limit_answer_words(grounding_text)

    return "Use the workspace controls for files, workflows, and source-aware questions. This Home surface can explain the best path."


def _fallback_payload(task_text: str, intent: str = "workspace") -> dict:
    answer = _fallback_answer_for_intent(intent, task_text)

    return _payload_for_answer(
        answer=answer,
        bridge="",
        suggestions=[],
        intent=intent,
        task_text=task_text,
    )


def _model_response_text(result: Any) -> str:
    if isinstance(result, str):
        return result

    if isinstance(result, dict):
        for key in (
            "answer",
            "text",
            "output",
            "response",
            "message",
            "content",
        ):
            value = result.get(key)

            if value:
                return str(value)

    return str(result or "")


def _model_ok(result: Any) -> bool:
    if isinstance(result, dict):
        status = str(result.get("status") or "").lower()

        if status in {"error", "failed", "failure"}:
            return False

        if result.get("ok") is False:
            return False

    return bool(_model_response_text(result).strip())


def _log_home_result(
    *,
    request_id: str,
    task_text: str,
    intent: str,
    started_at: float,
    source: str,
    answer: str,
) -> None:
    logger.info(
        "[HOME_LLM][RESULT] request_id=%s intent=%s source=%s latency_ms=%.1f input_chars=%s answer_chars=%s",
        request_id,
        intent,
        source,
        _elapsed_ms(started_at),
        len(str(task_text or "")),
        len(str(answer or "")),
    )


def handle_home_conversation(
    task_text: str,
    *,
    command_context: dict | None = None,
    workspace_context: dict | None = None,
    command_manifest: dict | None = None,
    request_id: str = "",
    stream_callback: HomeStreamCallback | None = None,
) -> dict:
    started_at = perf_counter()
    command_context = _safe_dict(command_context)
    workspace_context = _safe_dict(workspace_context)
    command_manifest = _safe_dict(command_manifest)
    intent = _infer_intent_from_text(task_text)
    prompt = _build_home_prompt(
        task_text=task_text,
        command_context=command_context,
        workspace_context=workspace_context,
        command_manifest=command_manifest,
    )

    _emit_home_stream_event(
        stream_callback,
        "home_context",
        {
            "request_id": request_id,
            "intent": intent,
            "has_prior_context": bool(_home_message_context(command_context)),
            "response_budget_ms": _HOME_RESPONSE_BUDGET_MS,
            "dialog_role": _HOME_DIALOG_ROLE,
            "authority_policy": _HOME_AUTHORITY_POLICY,
        },
    )

    try:
        llm_result = _execute_home_llm(
            prompt=prompt,
            request_id=request_id,
            stream_callback=stream_callback,
        )
    except Exception as exc:
        logger.exception("[HOME_LLM][EXECUTION_FAILED] request_id=%s", request_id)
        fallback = _fallback_payload(task_text, intent)
        _log_home_result(
            request_id=request_id,
            task_text=task_text,
            intent=intent,
            started_at=started_at,
            source=f"fallback_after_error:{exc.__class__.__name__}",
            answer=fallback.get("answer", ""),
        )

        return _packet(fallback)

    raw_text = _model_response_text(llm_result)

    parsed = (
        _parse_home_response_packet(
            model_text=raw_text,
            task_text=task_text,
            intent=intent,
        )
        if _model_ok(llm_result)
        else {}
    )

    if not parsed:
        parsed = _fallback_payload(task_text, intent)
        source = "fallback_empty_or_invalid"
    else:
        parsed = _payload_for_answer(
            answer=parsed.get("answer", ""),
            bridge="",
            suggestions=[],
            intent=intent,
            task_text=task_text,
        )
        source = "llm"

    _log_home_result(
        request_id=request_id,
        task_text=task_text,
        intent=intent,
        started_at=started_at,
        source=source,
        answer=parsed.get("answer", ""),
    )

    _emit_home_stream_event(
        stream_callback,
        "home_complete",
        {
            "request_id": request_id,
            "intent": parsed.get("intent") or intent,
            "answer": parsed.get("answer", ""),
            "bridge": "",
            "suggestions": [],
            "suggestion_actions": [],
            "source": source,
            "latency_ms": _elapsed_ms(started_at),
        },
    )

    return _packet(parsed)


def run_command_center_conversation(
    task_text: str,
    *,
    command_context: dict | None = None,
    workspace_context: dict | None = None,
    command_manifest: dict | None = None,
    request_id: str = "",
    stream_callback: HomeStreamCallback | None = None,
) -> dict:
    return handle_home_conversation(
        task_text,
        command_context=command_context,
        workspace_context=workspace_context,
        command_manifest=command_manifest,
        request_id=request_id,
        stream_callback=stream_callback,
    )


__all__ = [
    "handle_home_conversation",
    "run_command_center_conversation",
]
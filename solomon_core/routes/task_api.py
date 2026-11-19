# -------------------------------------------------------------
# FILE: task_api.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------
# Task Execution API
#
# CONTRACT
#   V3 command-center assistant and taskbar command traffic is handled
#   by the workspace command layer and must not enter Investigator,
#   CaseFile persistence, or V1-derived task engines.
#
#   Dedicated SolomonAI workspace conversations and explicit workflows
#   enter the constitutional Investigator -> CaseFile -> Orchestrator path.
#
#   SolomonAI streaming may expose the completed lane answer before UX
#   synthesis, while the final normalized packet remains post-synthesis.
# -------------------------------------------------------------

from flask import (
    Blueprint,
    Response,
    copy_current_request_context,
    g,
    jsonify,
    request,
    session,
    stream_with_context,
)
from queue import Empty, Queue
from threading import Thread
import json
import re
import uuid

from solomon_core.agent_registry import resolve_agent_id
from solomon_core.auth_utils import login_required
from solomon_core.context.ecb_registry import (
    ECB_MAX_TURNS,
    append_turn as ecb_append_turn,
    clear_conversation as ecb_clear_conversation,
    get_context as ecb_get_context,
)
from solomon_core.logger import get_logger
from solomon_core.solomon_ai_conversation_store import (
    get_solomon_ai_conversation,
)
from solomon_core.solomon_ai_exchange_recorder import (
    record_solomon_ai_response_exchange,
)
from solomon_core.workspace_actions import select_workspace_action
from solomon_core.workspace_actions.workspace_command_resolver import (
    resolve_workspace_command,
)

from .command_center_context import (
    _build_command_center_manifest,
    _clean_command_context,
)
from .command_center_conversation import run_command_center_conversation
from .task_api_support import _get_or_create_conversation_id
from .task_api_workflow_executor import run_explicit_workflow_execution
from .workspace_context import _clean_workspace_context


task_api = Blueprint("task_api", __name__, url_prefix="/api/task")
logger = get_logger("task_api")

V3_HOME_CONVERSATION_SOURCE = "command_center_conversation"
V3_SOLOMON_AI_WORKSPACE_SOURCE = "solomon_ai_workspace"
V3_SOLOMON_AI_WORKSPACE_COMMAND_MODE = "conversation"
V3_WORKSPACE_COMMAND_SOURCES = frozenset({
    "command_center_assistant",
    "command_center_taskbar",
})

HOME_CONVERSATION_CONTEXT_SESSION_KEY = "v3_home_conversation_context"
HOME_CONVERSATION_CONTEXT_MAX_TURNS = 3
HOME_CONVERSATION_CONTEXT_USER_LIMIT = 180
HOME_CONVERSATION_CONTEXT_ANSWER_LIMIT = 260
HOME_STREAM_QUEUE_TIMEOUT_SECONDS = 0.25
SOLOMON_AI_STREAM_QUEUE_TIMEOUT_SECONDS = 0.25
SOLOMON_AI_CONTINUITY_RECENT_TURNS = 18
SOLOMON_AI_CONTINUITY_RELEVANT_USER_TURNS = 7
SOLOMON_AI_CONTINUITY_CORRECTION_TURNS = 6

_CONTINUITY_TOKEN_PATTERN = re.compile(
    r"[a-z0-9]+(?:['-][a-z0-9]+)*",
    re.I,
)
_CONTINUITY_STOP_TOKENS = frozenset({
    "about",
    "after",
    "again",
    "also",
    "and",
    "answer",
    "are",
    "before",
    "bullet",
    "bullets",
    "but",
    "can",
    "close",
    "corrected",
    "correction",
    "current",
    "could",
    "for",
    "exactly",
    "explain",
    "final",
    "from",
    "give",
    "have",
    "include",
    "into",
    "just",
    "known",
    "loop",
    "more",
    "new",
    "not",
    "only",
    "our",
    "return",
    "sentence",
    "sentences",
    "should",
    "state",
    "summarize",
    "summary",
    "tell",
    "that",
    "the",
    "topic",
    "their",
    "them",
    "these",
    "this",
    "those",
    "using",
    "value",
    "values",
    "what",
    "when",
    "where",
    "which",
    "with",
    "would",
    "your",
})
_CONTINUITY_CORRECTION_PATTERNS = (
    re.compile(r"^\s*(?:final\s+)?correction\s*:\s*", re.I),
    re.compile(r"^\s*(?:please\s+)?correct\b", re.I),
    re.compile(r"\bcall\s+me\b.+\binstead\s+of\b", re.I),
    re.compile(r"\bchange(?:d)?\b.+\bfrom\b.+\bto\b", re.I),
    re.compile(r"\breplace\b.+\bwith\b", re.I),
    re.compile(r"\bis\s+now\b", re.I),
    re.compile(r"\bchanged\s+from\b", re.I),
    re.compile(r"\binstead\s+of\b", re.I),
    re.compile(r"\buse\b.+\brather\s+than\b", re.I),
)


def _solomon_ai_continuity_tokens(value):
    return {
        token.lower()
        for token in _CONTINUITY_TOKEN_PATTERN.findall(
            str(value or "")
        )
        if (
            len(token) >= 3
            and token.lower() not in _CONTINUITY_STOP_TOKENS
        )
    }


def _solomon_ai_explicit_correction(content):
    text = str(content or "").strip()

    if not text:
        return False

    explicit_prefix = bool(
        _CONTINUITY_CORRECTION_PATTERNS[0].search(text)
    )

    if "?" in text and not explicit_prefix:
        return False

    return any(
        pattern.search(text)
        for pattern in _CONTINUITY_CORRECTION_PATTERNS
    )


def _clean_solomon_ai_continuity_turns(
    messages,
    *,
    current_request="",
):
    """Return bounded durable continuity with relevant older user anchors."""

    if not isinstance(messages, list):
        return []

    ordered_messages = []

    for source_index, message in enumerate(messages):
        if not isinstance(message, dict):
            continue

        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()

        if role not in {"user", "assistant"} or not content:
            continue

        try:
            message_order = int(message.get("message_order") or 0)
        except (TypeError, ValueError):
            message_order = 0

        order_key = (
            message_order
            if message_order > 0
            else 1_000_000_000 + source_index
        )
        ordered_messages.append((
            order_key,
            source_index,
            {
                "role": role,
                "content": content,
                "metadata": {
                    "source": "solomon_ai_conversation_store",
                    "message_id": str(message.get("message_id") or "").strip(),
                    "request_id": str(message.get("request_id") or "").strip(),
                    "message_order": message_order,
                    "created_at": str(message.get("created_at") or "").strip(),
                },
            },
        ))

    ordered_messages.sort(
        key=lambda item: (item[0], item[1])
    )

    if len(ordered_messages) <= ECB_MAX_TURNS:
        return [
            item[2]
            for item in ordered_messages
        ]

    recent_turn_count = min(
        SOLOMON_AI_CONTINUITY_RECENT_TURNS,
        ECB_MAX_TURNS,
        len(ordered_messages),
    )
    recent_start = len(ordered_messages) - recent_turn_count
    selected_indexes = set(
        range(recent_start, len(ordered_messages))
    )
    request_tokens = _solomon_ai_continuity_tokens(
        current_request
    )
    older_user_turns = [
        (index, item[2]["content"])
        for index, item in enumerate(
            ordered_messages[:recent_start]
        )
        if item[2]["role"] == "user"
    ]
    relevant_turns = []

    for index, content in older_user_turns:
        overlap = len(
            request_tokens
            & _solomon_ai_continuity_tokens(content)
        )

        if overlap:
            relevant_turns.append((overlap, index))

    relevant_turns.sort(
        key=lambda item: (item[0], item[1]),
        reverse=True,
    )

    for _, index in relevant_turns[
        :SOLOMON_AI_CONTINUITY_RELEVANT_USER_TURNS
    ]:
        if len(selected_indexes) >= ECB_MAX_TURNS:
            break
        selected_indexes.add(index)

    topic_tokens = set()

    for _, index in relevant_turns[
        :SOLOMON_AI_CONTINUITY_RELEVANT_USER_TURNS
    ]:
        topic_tokens.update(
            _solomon_ai_continuity_tokens(
                ordered_messages[index][2]["content"]
            )
        )

    correction_turns = []

    for index, content in older_user_turns:
        if not _solomon_ai_explicit_correction(content):
            continue

        correction_tokens = _solomon_ai_continuity_tokens(
            content
        )
        request_overlap = len(
            request_tokens & correction_tokens
        )
        topic_overlap = len(
            topic_tokens & correction_tokens
        )
        related = bool(
            request_overlap
            or topic_overlap
            or not relevant_turns
        )
        correction_turns.append((
            int(related),
            request_overlap + topic_overlap,
            index,
        ))

    correction_turns.sort(
        key=lambda item: (item[0], item[1], item[2]),
        reverse=True,
    )

    retained_corrections = 0

    for related, _, index in correction_turns:
        if (
            not related
            or retained_corrections
            >= SOLOMON_AI_CONTINUITY_CORRECTION_TURNS
            or len(selected_indexes) >= ECB_MAX_TURNS
        ):
            continue

        selected_indexes.add(index)
        retained_corrections += 1

    return [
        ordered_messages[index][2]
        for index in sorted(selected_indexes)
    ]


def _solomon_ai_continuity_signature(turns):
    """Return role/content identity without exposing conversation content."""

    signature = []

    for turn in turns or []:
        if not isinstance(turn, dict):
            continue

        role = str(turn.get("role") or "").strip().lower()
        content = str(turn.get("content") or "").strip()

        if role not in {"user", "assistant"} or not content:
            continue

        signature.append((role, content))

    return tuple(signature[-ECB_MAX_TURNS:])


def _synchronize_solomon_ai_ecb_context(
    *,
    user_id,
    conversation_id,
    request_id,
    current_request="",
):
    """Hydrate the bounded ECB from user-owned durable conversation history."""

    durable_conversation = get_solomon_ai_conversation(
        user_id=int(user_id or 0),
        conversation_id=str(conversation_id or "").strip(),
        include_messages=True,
    )

    if not durable_conversation:
        logger.warning(
            "[API][SOLOMON_AI_ECB_SYNC_SKIPPED] "
            "request_id=%s conversation_id=%s reason=conversation_unavailable",
            request_id,
            conversation_id,
        )
        return 0

    durable_turns = _clean_solomon_ai_continuity_turns(
        durable_conversation.get("messages"),
        current_request=current_request,
    )
    current_turns = ecb_get_context(
        str(conversation_id or "").strip()
    )

    if (
        _solomon_ai_continuity_signature(current_turns)
        == _solomon_ai_continuity_signature(durable_turns)
    ):
        logger.debug(
            "[API][SOLOMON_AI_ECB_CURRENT] "
            "request_id=%s conversation_id=%s turns=%s",
            request_id,
            conversation_id,
            len(durable_turns),
        )
        return len(durable_turns)

    ecb_clear_conversation(
        str(conversation_id or "").strip()
    )

    for turn in durable_turns:
        ecb_append_turn(
            str(conversation_id or "").strip(),
            role=turn["role"],
            content=turn["content"],
            metadata=turn["metadata"],
        )

    logger.debug(
        "[API][SOLOMON_AI_ECB_SYNCHRONIZED] "
        "request_id=%s conversation_id=%s turns=%s",
        request_id,
        conversation_id,
        len(durable_turns),
    )

    return len(durable_turns)


def _record_solomon_ai_exchange_safely(
    *,
    user_id,
    conversation_id,
    task_text,
    response,
    status_code,
    request_id,
):
    """Persist one final exchange and return whether it was durable."""

    try:
        recorded = record_solomon_ai_response_exchange(
            user_id=user_id,
            conversation_id=conversation_id,
            user_content=task_text,
            response=response,
            status_code=status_code,
            request_id=request_id,
        )
    except Exception:
        logger.exception(
            "[API][SOLOMON_AI_EXCHANGE_PERSIST_FAILED] "
            "request_id=%s conversation_id=%s",
            request_id,
            conversation_id,
        )
        return False

    if not recorded:
        logger.warning(
            "[API][SOLOMON_AI_EXCHANGE_NOT_RECORDED] "
            "request_id=%s conversation_id=%s status_code=%s",
            request_id,
            conversation_id,
            status_code,
        )
        return False

    logger.debug(
        "[API][SOLOMON_AI_EXCHANGE_RECORDED] "
        "request_id=%s conversation_id=%s",
        request_id,
        conversation_id,
    )

    return True


def _finalize_solomon_ai_response(
    *,
    user_id,
    conversation_id,
    task_text,
    response,
    status_code,
    request_id,
):
    """Require durable persistence before reporting a successful response."""

    if (
        int(status_code or 0) >= 400
        or not isinstance(response, dict)
        or response.get("ok") is False
    ):
        return status_code, response

    recorded = _record_solomon_ai_exchange_safely(
        user_id=user_id,
        conversation_id=conversation_id,
        task_text=task_text,
        response=response,
        status_code=status_code,
        request_id=request_id,
    )

    if recorded:
        return status_code, response

    logger.error(
        "[API][SOLOMON_AI_RESPONSE_WITHHELD_NOT_DURABLE] "
        "request_id=%s conversation_id=%s",
        request_id,
        conversation_id,
    )

    return 500, {
        "ok": False,
        "packet_type": "solomon_ai_conversation_error",
        "error": "SolomonAiConversationPersistenceFailed",
        "user_output": (
            "SolomonAI completed the response, but the conversation "
            "could not be saved. Please try again."
        ),
        "request_id": request_id,
        "conversation_id": str(conversation_id or "").strip(),
    }


def _visual_conductor_payload(sequence_id, selector_result=None):
    ui_actions = []

    if sequence_id:
        ui_actions.append({
            "type": "sequence",
            "sequence": sequence_id,
        })

    payload = {
        "ui_sequence": sequence_id,
        "ui_actions": ui_actions,
    }

    if selector_result is not None:
        payload["selector"] = selector_result.to_dict()

    return {
        "ok": True,
        "packet_type": "visual_conductor",
        "payload": payload,
    }


def _has_explicit_attachment_payload(payload):
    if not isinstance(payload, dict):
        return False

    for key in ("attachment_ids", "documents", "uploaded_documents"):
        value = payload.get(key)

        if isinstance(value, list) and value:
            return True

    return False


def _has_explicit_workflow_execution_payload(payload):
    if not isinstance(payload, dict):
        return False

    workflow = payload.get("workflow")

    return (
        bool(payload.get("workflow_id"))
        or bool(payload.get("input_mode"))
        or isinstance(workflow, dict)
    )


def _is_v3_home_conversation_request(payload, workspace_context):
    if not isinstance(payload, dict) or not isinstance(workspace_context, dict):
        return False

    if workspace_context.get("source") != V3_HOME_CONVERSATION_SOURCE:
        return False

    if workspace_context.get("command_mode") != "conversation":
        return False

    if _has_explicit_attachment_payload(payload):
        return False

    return not _has_explicit_workflow_execution_payload(payload)


def _is_v3_solomon_ai_conversation_request(
    payload,
    workspace_context,
):
    """
    Return whether the dedicated SolomonAI workspace owns this request.

    SolomonAI surface identity is established by its cleaned workspace
    context. Client-supplied workflow fields cannot displace the request into
    another route branch; the governed executor independently removes those
    fields before Investigator intake.
    """

    if (
        not isinstance(payload, dict)
        or not isinstance(workspace_context, dict)
    ):
        return False

    if (
        workspace_context.get("source")
        != V3_SOLOMON_AI_WORKSPACE_SOURCE
    ):
        return False

    return (
        workspace_context.get("command_mode")
        == V3_SOLOMON_AI_WORKSPACE_COMMAND_MODE
    )


def _is_v3_workspace_command_request(payload, workspace_context):
    if not isinstance(payload, dict) or not isinstance(workspace_context, dict):
        return False

    if workspace_context.get("source") not in V3_WORKSPACE_COMMAND_SOURCES:
        return False

    if _has_explicit_attachment_payload(payload):
        return False

    return not _has_explicit_workflow_execution_payload(payload)


def _clip_home_context_text(value, limit):
    clean_text = " ".join(str(value or "").strip().split())

    if len(clean_text) <= limit:
        return clean_text

    clipped = clean_text[:limit].rsplit(" ", 1)[0].strip()

    return clipped or clean_text[:limit].strip()


def _clean_home_context_turn(value):
    if not isinstance(value, dict):
        return None

    user_text = _clip_home_context_text(
        value.get("user"),
        HOME_CONVERSATION_CONTEXT_USER_LIMIT,
    )
    answer = _clip_home_context_text(
        value.get("answer"),
        HOME_CONVERSATION_CONTEXT_ANSWER_LIMIT,
    )

    if not user_text and not answer:
        return None

    return {
        "user": user_text,
        "answer": answer,
    }


def _get_home_message_context(conversation_id):
    state = session.get(HOME_CONVERSATION_CONTEXT_SESSION_KEY)

    if not isinstance(state, dict):
        return []

    if state.get("conversation_id") != conversation_id:
        return []

    turns = state.get("turns")

    if not isinstance(turns, list):
        return []

    clean_turns = []

    for turn in turns[-HOME_CONVERSATION_CONTEXT_MAX_TURNS:]:
        clean_turn = _clean_home_context_turn(turn)

        if clean_turn:
            clean_turns.append(clean_turn)

    return clean_turns[-HOME_CONVERSATION_CONTEXT_MAX_TURNS:]


def _store_home_message_context(conversation_id, turns):
    clean_turns = []

    for turn in turns[-HOME_CONVERSATION_CONTEXT_MAX_TURNS:]:
        clean_turn = _clean_home_context_turn(turn)

        if clean_turn:
            clean_turns.append(clean_turn)

    session[HOME_CONVERSATION_CONTEXT_SESSION_KEY] = {
        "conversation_id": conversation_id,
        "turns": clean_turns[-HOME_CONVERSATION_CONTEXT_MAX_TURNS:],
    }
    session.modified = True


def _payload_answer_from_response(response):
    if not isinstance(response, dict):
        return ""

    payload = response.get("payload")

    if not isinstance(payload, dict):
        return ""

    return _clip_home_context_text(
        payload.get("answer"),
        HOME_CONVERSATION_CONTEXT_ANSWER_LIMIT,
    )


def _remember_home_exchange(conversation_id, task_text, response, request_id):
    answer = _payload_answer_from_response(response)
    user_text = _clip_home_context_text(
        task_text,
        HOME_CONVERSATION_CONTEXT_USER_LIMIT,
    )

    if not user_text or not answer:
        return

    turns = _get_home_message_context(conversation_id)
    turns.append({
        "user": user_text,
        "answer": answer,
    })
    _store_home_message_context(conversation_id, turns)

    logger.debug(
        "[API][V3_HOME_CONTEXT_STORED] request_id=%s conversation_id=%s turns=%s",
        request_id,
        conversation_id,
        len(_get_home_message_context(conversation_id)),
    )


def _sse_event(event_name, payload):
    clean_event = str(event_name or "message").strip() or "message"
    return (
        f"event: {clean_event}\n"
        f"data: {json.dumps(payload, separators=(',', ':'), default=str)}\n\n"
    )


def _sse_comment(value):
    clean_value = str(value or "keep-alive").replace("\n", " ").strip()
    return f": {clean_value}\n\n"


def _sse_error_payload(message, request_id):
    return {
        "ok": False,
        "request_id": request_id,
        "error": str(message or "Stream request failed."),
    }


def _home_stream_open_payload(request_id, conversation_id):
    return {
        "ok": True,
        "request_id": request_id,
        "conversation_id": conversation_id,
        "stream": "home_conversation",
        "status": "opened",
    }


def _solomon_ai_stream_open_payload(request_id, conversation_id):
    return {
        "ok": True,
        "request_id": request_id,
        "conversation_id": conversation_id,
        "stream": "solomon_ai_conversation",
        "status": "opened",
    }


def _drain_stream_queue(
    stream_queue,
    done_marker,
    *,
    timeout_seconds,
    keep_alive_comment,
):
    while True:
        try:
            item = stream_queue.get(
                timeout=timeout_seconds
            )
        except Empty:
            yield _sse_comment(
                keep_alive_comment
            )
            continue

        if item is done_marker:
            break

        yield item


def _run_home_conversation_response(
    *,
    payload,
    task_text,
    command_context,
    workspace_context,
    command_manifest,
    request_id,
    stream_callback=None,
):
    conversation_id = payload.get("conversation_id") or _get_or_create_conversation_id()
    home_message_context = _get_home_message_context(conversation_id)
    home_command_context = dict(command_context)

    if home_message_context:
        home_command_context["home_message_context"] = home_message_context

    response = run_command_center_conversation(
        task_text=task_text,
        conversation_id=conversation_id,
        command_context=home_command_context,
        workspace_context=workspace_context,
        command_manifest=command_manifest,
        request_id=request_id,
        stream_callback=stream_callback,
    )
    _remember_home_exchange(
        conversation_id=conversation_id,
        task_text=task_text,
        response=response,
        request_id=request_id,
    )
    logger.debug(
        "[API][V3_HOME_CONVERSATION] request_id=%s source=%s packet_type=%s "
        "context_turns=%s",
        request_id,
        workspace_context.get("source"),
        response.get("packet_type"),
        len(home_message_context),
    )

    return response, conversation_id, len(home_message_context)


@task_api.route("/conduct", methods=["POST"])
@login_required
def conduct_task_api():
    request_id = getattr(g, "request_id", None) or str(uuid.uuid4())
    payload = request.get_json(silent=True) or {}
    task_text = (payload.get("task") or "").strip()

    if not task_text:
        return jsonify(_visual_conductor_payload("")), 200

    command_context = _clean_command_context(payload.get("command_context"))
    workspace_context = _clean_workspace_context(payload.get("workspace_context"))

    home_conversation_request = (
        _is_v3_home_conversation_request(
            payload,
            workspace_context,
        )
    )
    solomon_ai_conversation_request = (
        _is_v3_solomon_ai_conversation_request(
            payload,
            workspace_context,
        )
    )

    if (
        home_conversation_request
        or solomon_ai_conversation_request
    ):
        logger.debug(
            "[API][V3_CONDUCT_SKIPPED] "
            "request_id=%s source=%s mode=%s",
            request_id,
            workspace_context.get("source"),
            workspace_context.get("command_mode"),
        )
        return jsonify(
            _visual_conductor_payload("")
        ), 200

    selector_result = select_workspace_action(
        task_text=task_text,
        command_context=command_context,
        workspace_context=workspace_context,
    )

    sequence_id = selector_result.sequence if selector_result.approved else ""

    logger.debug(
        "[API][VISUAL_CONDUCTOR] request_id=%s sequence=%s approved=%s "
        "score=%.6f margin=%.6f elapsed_ms=%.2f reason=%s",
        request_id,
        sequence_id or "none",
        selector_result.approved,
        selector_result.score,
        selector_result.margin,
        selector_result.reason,
    )

    return jsonify(_visual_conductor_payload(sequence_id, selector_result)), 200


@task_api.route("/execute/stream", methods=["POST"])
@login_required
def execute_task_stream_api():
    current_user = int(session.get("user_id", 0))
    agent_id = None
    request_id = getattr(g, "request_id", None) or str(uuid.uuid4())
    payload = request.get_json(silent=True) or {}
    task_text = (payload.get("task") or "").strip()

    if payload.get("agent"):
        agent_id = resolve_agent_id(
            payload["agent"]
        )

    command_context = _clean_command_context(payload.get("command_context"))
    workspace_context = _clean_workspace_context(payload.get("workspace_context"))
    home_conversation_request = _is_v3_home_conversation_request(
        payload,
        workspace_context,
    )
    solomon_ai_conversation_request = (
        _is_v3_solomon_ai_conversation_request(
            payload,
            workspace_context,
        )
    )
    active_module = command_context.get("module") or "home"
    command_manifest = _build_command_center_manifest(active_module)
    conversation_id = payload.get("conversation_id") or _get_or_create_conversation_id()

    def _generate_home_stream():
        logger.debug(
            "[API][V3_HOME_STREAM_OPEN] request_id=%s conversation_id=%s source=%s",
            request_id,
            conversation_id,
            workspace_context.get("source"),
        )
        yield _sse_event(
            "home_stream_open",
            _home_stream_open_payload(request_id, conversation_id),
        )

        stream_queue = Queue()
        done_marker = object()

        def _queue_stream_event(event_name, event_payload):
            stream_queue.put(
                _sse_event(
                    event_name,
                    event_payload,
                )
            )

        @copy_current_request_context
        def _run_stream_worker():
            try:
                response, _, context_turns = _run_home_conversation_response(
                    payload={**payload, "conversation_id": conversation_id},
                    task_text=task_text,
                    command_context=command_context,
                    workspace_context=workspace_context,
                    command_manifest=command_manifest,
                    request_id=request_id,
                    stream_callback=_queue_stream_event,
                )
                stream_queue.put(_sse_event("home_packet", response))
                stream_queue.put(
                    _sse_event(
                        "done",
                        {
                            "ok": True,
                            "request_id": request_id,
                            "conversation_id": conversation_id,
                            "context_turns": context_turns,
                        },
                    )
                )
            except Exception as exc:
                logger.exception(
                    "[API][V3_HOME_STREAM_FAIL] request_id=%s",
                    request_id,
                )
                stream_queue.put(
                    _sse_event(
                        "error",
                        _sse_error_payload(str(exc), request_id),
                    )
                )
            finally:
                stream_queue.put(done_marker)

        worker = Thread(
            target=_run_stream_worker,
            name=f"home-stream-{request_id}",
            daemon=True,
        )
        worker.start()

        yield from _drain_stream_queue(
            stream_queue,
            done_marker,
            timeout_seconds=HOME_STREAM_QUEUE_TIMEOUT_SECONDS,
            keep_alive_comment="home-stream-alive",
        )

    def _generate_solomon_ai_stream():
        logger.debug(
            "[API][SOLOMON_AI_STREAM_OPEN] "
            "request_id=%s conversation_id=%s source=%s",
            request_id,
            conversation_id,
            workspace_context.get("source"),
        )
        yield _sse_event(
            "solomon_ai_stream_open",
            _solomon_ai_stream_open_payload(
                request_id,
                conversation_id,
            ),
        )

        stream_queue = Queue()
        done_marker = object()

        def _queue_lane_answer(answer_stage):
            stream_queue.put(
                _sse_event(
                    "solomon_ai_answer",
                    answer_stage,
                )
            )

        @copy_current_request_context
        def _run_stream_worker():
            try:
                continuity_turns = _synchronize_solomon_ai_ecb_context(
                    user_id=current_user,
                    conversation_id=conversation_id,
                    request_id=request_id,
                    current_request=task_text,
                )

                logger.debug(
                    "[API][SOLOMON_AI_CONTINUITY_READY] "
                    "request_id=%s conversation_id=%s turns=%s mode=stream",
                    request_id,
                    conversation_id,
                    continuity_turns,
                )

                status_code, response = run_explicit_workflow_execution(
                    payload={**payload, "conversation_id": conversation_id},
                    current_user=current_user,
                    request_id=request_id,
                    agent_id=agent_id,
                    workspace_command_request=False,
                    lane_answer_callback=_queue_lane_answer,
                )
                response["request_id"] = (
                    response.get("request_id")
                    or request_id
                )

                status_code, response = _finalize_solomon_ai_response(
                    user_id=current_user,
                    conversation_id=conversation_id,
                    task_text=task_text,
                    response=response,
                    status_code=status_code,
                    request_id=request_id,
                )

                stream_queue.put(
                    _sse_event(
                        "solomon_ai_packet",
                        {
                            "http_status": status_code,
                            "packet": response,
                        },
                    )
                )
                stream_queue.put(
                    _sse_event(
                        "done",
                        {
                            "ok": (
                                status_code < 400
                                and response.get("ok") is not False
                            ),
                            "request_id": request_id,
                            "conversation_id": conversation_id,
                            "http_status": status_code,
                        },
                    )
                )

                logger.debug(
                    "[API][SOLOMON_AI_STREAM_COMPLETE] "
                    "request_id=%s conversation_id=%s "
                    "status_code=%s packet_type=%s",
                    request_id,
                    conversation_id,
                    status_code,
                    response.get("packet_type"),
                )
            except Exception as exc:
                logger.exception(
                    "[API][SOLOMON_AI_STREAM_FAIL] request_id=%s",
                    request_id,
                )
                stream_queue.put(
                    _sse_event(
                        "error",
                        _sse_error_payload(str(exc), request_id),
                    )
                )
            finally:
                stream_queue.put(done_marker)

        worker = Thread(
            target=_run_stream_worker,
            name=f"solomon-ai-stream-{request_id}",
            daemon=True,
        )
        worker.start()

        yield from _drain_stream_queue(
            stream_queue,
            done_marker,
            timeout_seconds=SOLOMON_AI_STREAM_QUEUE_TIMEOUT_SECONDS,
            keep_alive_comment="solomon-ai-stream-alive",
        )

    def _generate():
        if not task_text:
            yield _sse_event(
                "error",
                _sse_error_payload("Missing 'task' parameter", request_id),
            )
            return

        if home_conversation_request:
            yield from _generate_home_stream()
            return

        if solomon_ai_conversation_request:
            yield from _generate_solomon_ai_stream()
            return

        yield _sse_event(
            "error",
            _sse_error_payload(
                (
                    "Streaming is currently available only for Home "
                    "and SolomonAI conversation requests."
                ),
                request_id,
            ),
        )

    return Response(
        stream_with_context(_generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        },
    )


@task_api.route("/execute", methods=["POST"])
@login_required
def execute_task_api():
    current_user = int(session.get("user_id", 0))
    agent_id = None

    request_id = getattr(g, "request_id", None) or str(uuid.uuid4())
    logger.debug(
        "[API][REQUEST] request_id=%s user_id=%s",
        request_id,
        current_user,
    )

    payload = request.get_json(silent=True) or {}

    task_text = (payload.get("task") or "").strip()
    if not task_text:
        return jsonify({
            "ok": False,
            "error": "MissingTaskParameter",
            "user_output": "Missing 'task' parameter",
            "request_id": request_id,
        }), 400

    if payload.get("agent"):
        agent_id = resolve_agent_id(payload["agent"])

    command_context = _clean_command_context(payload.get("command_context"))
    workspace_context = _clean_workspace_context(payload.get("workspace_context"))
    workspace_command_request = _is_v3_workspace_command_request(
        payload,
        workspace_context,
    )
    home_conversation_request = _is_v3_home_conversation_request(
        payload,
        workspace_context,
    )
    solomon_ai_conversation_request = (
        _is_v3_solomon_ai_conversation_request(
            payload,
            workspace_context,
        )
    )

    active_module = command_context.get("module") or "home"
    command_manifest = _build_command_center_manifest(active_module)

    if workspace_command_request:
        response = resolve_workspace_command(
            task_text=task_text,
            command_manifest=command_manifest,
            command_context=command_context,
            workspace_context=workspace_context,
        )
        logger.debug(
            "[API][V3_WORKSPACE_COMMAND] request_id=%s source=%s command_id=%s",
            request_id,
            workspace_context.get("source"),
            response.get("payload", {}).get("command_id"),
        )
        return jsonify(response), 200

    if home_conversation_request:
        response, _, _ = _run_home_conversation_response(
            payload=payload,
            task_text=task_text,
            command_context=command_context,
            workspace_context=workspace_context,
            command_manifest=command_manifest,
            request_id=request_id,
        )
        return jsonify(response), 200

    if solomon_ai_conversation_request:
        continuity_turns = _synchronize_solomon_ai_ecb_context(
            user_id=current_user,
            conversation_id=payload.get("conversation_id"),
            request_id=request_id,
            current_request=task_text,
        )

        logger.debug(
            "[API][SOLOMON_AI_CONTINUITY_READY] "
            "request_id=%s conversation_id=%s turns=%s mode=json",
            request_id,
            payload.get("conversation_id"),
            continuity_turns,
        )

        status_code, response = (
            run_explicit_workflow_execution(
                payload=payload,
                current_user=current_user,
                request_id=request_id,
                agent_id=agent_id,
                workspace_command_request=False,
            )
        )
        response["request_id"] = (
            response.get("request_id")
            or request_id
        )

        status_code, response = _finalize_solomon_ai_response(
            user_id=current_user,
            conversation_id=payload.get("conversation_id"),
            task_text=task_text,
            response=response,
            status_code=status_code,
            request_id=request_id,
        )

        logger.debug(
            "[API][SOLOMON_AI_WORKSPACE_EXECUTION] "
            "request_id=%s conversation_id=%s "
            "packet_type=%s",
            request_id,
            payload.get("conversation_id"),
            response.get("packet_type"),
        )

        return jsonify(response), status_code

    status_code, response = run_explicit_workflow_execution(
        payload=payload,
        current_user=current_user,
        request_id=request_id,
        agent_id=agent_id,
        workspace_command_request=workspace_command_request,
    )

    response["request_id"] = response.get("request_id") or request_id

    return jsonify(response), status_code
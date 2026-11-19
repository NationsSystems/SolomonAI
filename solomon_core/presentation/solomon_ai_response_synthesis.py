# ------------------------------------------------------------------
# FILE: solomon_ai_response_synthesis.py
# DIRECTORY: solomon_core/presentation/
# ------------------------------------------------------------------
# SolomonAI Response Synthesis
#
# PURPOSE
#   Apply Solomon's selective continuation policy after the substantive lane
#   answer has completed, then assemble only the optional continuation UI that
#   materially helps the user.
#
# CONTRACT
#   - Runs only after lane execution
#   - Never alters the substantive assistant answer
#   - Never classifies or routes the execution lane
#   - Never expands authorization or retrieves additional evidence
#   - Discards lane-authored bridge/suggestion fields; this boundary owns the
#     canonical continuation decision for dedicated SolomonAI conversations
#   - Chooses continuation mode deterministically before any extra generation
#   - NONE performs no continuation-model call
#   - CONTINUE and RESOLVE may produce chips without a bridge
#   - EXPLORE may produce one short bridge plus bounded chips
#   - Continuation generation is P1 foreground work and fails open to NONE
#   - Generated continuation language may use only the completed request and
#     completed answer; it may not introduce new factual claims
# ------------------------------------------------------------------

from __future__ import annotations

import json
import re
from time import perf_counter
from typing import Any, Dict, Optional

from solomon_core.intelligence_service.intelligence_service_contract import (
    build_opaque_fairness_bucket,
)
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
    LLMResponseFormat,
)
from solomon_core.llm.llm_executor import execute_llm
from solomon_core.logger import get_logger
from solomon_core.presentation.solomon_ai_continuation_policy import (
    CONTINUATION_CONTINUE,
    CONTINUATION_EXPLORE,
    CONTINUATION_NONE,
    CONTINUATION_RESOLVE,
    ContinuationDecision,
    decide_solomon_ai_continuation,
)


logger = get_logger("solomon_ai_response_synthesis")

_BRIDGE_MIN_WORDS = 6
_BRIDGE_MAX_WORDS = 14
_SUGGESTION_MAX_WORDS = 8
_CONTINUATION_CALL_SITE = "solomon_ai_response_synthesis"
_CONTINUATION_MAX_NEW_TOKENS = 80
_CONTINUATION_TIMEOUT_SECONDS = 3

_PRESENTATION_ACCEPTED = "accepted"
_PRESENTATION_SUPPRESSED = "suppressed"
_PRESENTATION_GENERATION_FAILED = "generation_failed"

_GENERIC_SUGGESTIONS = frozenset({
    "continue",
    "explain further",
    "go deeper",
    "learn more",
    "more details",
    "real world applications",
    "tell me more",
    "what next",
})


# ------------------------------------------------------------------
# Packet Readers
# ------------------------------------------------------------------


def _read_payload(
    result: Any,
) -> Dict[str, Any]:
    if hasattr(
        result,
        "payload",
    ):
        payload = getattr(
            result,
            "payload",
            None,
        )

        return (
            dict(payload)
            if isinstance(
                payload,
                dict,
            )
            else {}
        )

    if isinstance(
        result,
        dict,
    ):
        payload = result.get(
            "payload"
        )

        if isinstance(
            payload,
            dict,
        ):
            return dict(
                payload
            )

        return {
            key: value
            for key, value in result.items()
            if key not in {
                "ok",
                "packet_type",
                "verdict",
            }
        }

    return {}


def _read_packet_type(
    result: Any,
) -> Optional[str]:
    if hasattr(
        result,
        "header",
    ):
        header = getattr(
            result,
            "header",
            None,
        )
        minimal = getattr(
            header,
            "minimal",
            None,
        )
        packet_type = getattr(
            minimal,
            "packet_type",
            None,
        )

        if (
            isinstance(
                packet_type,
                str,
            )
            and packet_type.strip()
        ):
            return packet_type.strip()

    if isinstance(
        result,
        dict,
    ):
        packet_type = result.get(
            "packet_type"
        )

        if (
            isinstance(
                packet_type,
                str,
            )
            and packet_type.strip()
        ):
            return packet_type.strip()

    return None


def _read_ok(
    result: Any,
) -> bool:
    if isinstance(
        result,
        dict,
    ):
        value = result.get(
            "ok"
        )

        if isinstance(
            value,
            bool,
        ):
            return value

    value = getattr(
        result,
        "ok",
        None,
    )

    return (
        value
        if isinstance(
            value,
            bool,
        )
        else True
    )


def _read_verdict(
    result: Any,
) -> Optional[str]:
    if isinstance(
        result,
        dict,
    ):
        verdict = result.get(
            "verdict"
        )

        if (
            isinstance(
                verdict,
                str,
            )
            and verdict.strip()
        ):
            return verdict.strip()

    verdict = getattr(
        result,
        "verdict",
        None,
    )

    if (
        isinstance(
            verdict,
            str,
        )
        and verdict.strip()
    ):
        return verdict.strip()

    return None


def _build_result(
    *,
    payload: Dict[str, Any],
    packet_type: Optional[str],
    ok: bool,
    verdict: Optional[str],
) -> Dict[str, Any]:
    result = {
        "ok": ok,
        "packet_type": packet_type,
        "payload": payload,
    }

    if verdict:
        result[
            "verdict"
        ] = verdict

    return result


# ------------------------------------------------------------------
# Continuation Language Validation
# ------------------------------------------------------------------


def _clean_text(
    value: Any,
) -> str:
    return value.strip() if isinstance(value, str) else ""


def _word_count(
    value: str,
) -> int:
    return len(
        [
            word
            for word in value.split()
            if word
        ]
    )


def _sentence_count(
    value: str,
) -> int:
    return len(
        [
            part
            for part in re.findall(
                r"[^.!?]+(?:[.!?]+|$)",
                value,
            )
            if part.strip()
        ]
    )


def _clean_suggestions(
    value: Any,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        return []

    suggestions: list[str] = []
    normalized: set[str] = set()

    for item in value:
        suggestion = _clean_text(
            item
        )

        if not suggestion:
            continue

        if _word_count(
            suggestion
        ) > _SUGGESTION_MAX_WORDS:
            continue

        key = suggestion.casefold().strip(" .!?;:")

        if key in _GENERIC_SUGGESTIONS:
            continue

        if key in normalized:
            continue

        normalized.add(
            key
        )
        suggestions.append(
            suggestion
        )

    return suggestions


def _validated_generated_presentation(
    parsed: Dict[str, Any],
    decision: ContinuationDecision,
) -> tuple[str, list[str], str]:
    bridge = _clean_text(
        parsed.get("bridge")
        if "bridge" in parsed
        else parsed.get("b")
    )
    suggestions = _clean_suggestions(
        parsed.get("suggestions")
        if "suggestions" in parsed
        else parsed.get("s")
    )

    if len(suggestions) > decision.maximum_suggestions:
        suggestions = suggestions[
            :decision.maximum_suggestions
        ]

    if not (
        decision.minimum_suggestions
        <= len(suggestions)
        <= decision.maximum_suggestions
    ):
        return (
            "",
            [],
            "suggestion_count_invalid",
        )

    if not decision.bridge_required:
        bridge = ""

    if decision.bridge_required:
        bridge_words = _word_count(
            bridge
        )

        if not (
            _BRIDGE_MIN_WORDS
            <= bridge_words
            <= _BRIDGE_MAX_WORDS
        ):
            return (
                "",
                [],
                "bridge_word_count_invalid",
            )

        if _sentence_count(bridge) != 1:
            return (
                "",
                [],
                "bridge_sentence_count_invalid",
            )
    return (
        bridge,
        suggestions,
        "",
    )


def _extract_json_object(
    value: str,
) -> Dict[str, Any]:
    text = _clean_text(
        value
    )

    if not text:
        return {}

    if text.startswith("```"):
        text = text.strip("`").strip()

        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(
            text
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
# Continuation Generation
# ------------------------------------------------------------------


def _mode_instruction(
    decision: ContinuationDecision,
) -> list[str]:
    if decision.mode == CONTINUATION_EXPLORE:
        return [
            "MODE: EXPLORE",
            (
                "Write one topic-specific bridge sentence of 6 to 14 words "
                "that naturally introduces useful exploration."
            ),
            (
                "Return 2 or 3 distinct suggestion prompts, each no more than "
                "8 words."
            ),
        ]

    if decision.mode == CONTINUATION_RESOLVE:
        return [
            "MODE: RESOLVE",
            "Do not generate a bridge.",
            (
                "Return 1 to 3 concise prompts that help resolve the actual "
                "ambiguity, conflict, or missing-evidence boundary."
            ),
        ]

    if decision.mode == CONTINUATION_CONTINUE:
        return [
            "MODE: CONTINUE",
            "Do not generate a bridge.",
            (
                "Return 1 to 3 concise prompts that are genuinely useful next "
                "questions or refinements."
            ),
        ]

    return []


def _build_continuation_prompt(
    *,
    decision: ContinuationDecision,
    original_request: str,
    answer: str,
) -> str:
    lines = [
        "You are producing optional continuation UI for a completed SolomonAI answer.",
        "The substantive answer is already final. Do not answer it again.",
        "Use only the current request and completed answer shown below.",
        "Do not introduce new facts, numbers, names, sources, authority, or conclusions.",
        "Do not perform retrieval, web research, routing, or authorization decisions.",
        "Suggestions must be written as useful prompts the user could submit next.",
        "Suggestions must relate directly to the current topic and differ meaningfully.",
        'Never use generic filler such as "Tell me more" or "Explain further".',
        "Do not suggest an action Solomon cannot infer is available from this answer.",
        *_mode_instruction(
            decision
        ),
        (
            (
                'Return ONLY JSON as {"bridge":"string",'
                '"suggestions":["string"]}.'
            )
            if decision.mode == CONTINUATION_EXPLORE
            else (
                'Return ONLY JSON as {"suggestions":["string"]}. '
                "Do not include a bridge field."
            )
        ),
        "",
        "CURRENT REQUEST",
        _clean_text(
            original_request
        ),
        "",
        "COMPLETED ANSWER",
        _clean_text(
            answer
        ),
    ]

    return "\n".join(
        lines
    )


def _generate_continuation(
    *,
    decision: ContinuationDecision,
    original_request: str,
    answer: str,
    request_id: str,
) -> tuple[str, list[str], str]:
    prompt = _build_continuation_prompt(
        decision=decision,
        original_request=original_request,
        answer=answer,
    )
    result = execute_llm(
        LLMExecutionInput(
            user_query=prompt,
            mode=LLMExecutionMode.INFORMATIONAL_ONLY,
            context=None,
            response_format=LLMResponseFormat.JSON_OBJECT,
            call_site=_CONTINUATION_CALL_SITE,
            max_new_tokens=_CONTINUATION_MAX_NEW_TOKENS,
            timeout_seconds=_CONTINUATION_TIMEOUT_SECONDS,
        ),
        priority="P1",
        request_id=request_id,
        fairness_bucket=build_opaque_fairness_bucket(
            request_id,
            namespace="conversation",
        ),
    )

    output_text = ""

    if (
        result
        and result.output
        and getattr(
            result.output,
            "text",
            None,
        )
    ):
        output_text = _clean_text(
            result.output.text
        )

    if not output_text:
        failure = getattr(
            result,
            "failure",
            None,
        )
        reason = _clean_text(
            getattr(
                failure,
                "reason",
                "",
            )
        ) or "empty_continuation_output"

        return (
            "",
            [],
            reason,
        )

    parsed = _extract_json_object(
        output_text
    )

    if not parsed:
        return (
            "",
            [],
            "continuation_json_invalid",
        )

    return _validated_generated_presentation(
        parsed,
        decision,
    )


# ------------------------------------------------------------------
# Public Synthesis Surface
# ------------------------------------------------------------------


def synthesize_solomon_ai_response(
    result: Any,
    *,
    original_request: str,
    request_id: str,
    enabled: bool = True,
) -> Any:
    """
    Apply selective continuation UI after the substantive lane has completed.

    The completed lane answer remains authoritative. This boundary removes any
    legacy lane-authored bridge/suggestion pair, deterministically decides the
    response continuation mode, and spends P1 model capacity only when that
    mode warrants semantic continuation language.
    """

    if not enabled:
        return result

    started_at = perf_counter()
    payload = _read_payload(
        result
    )
    packet_type = _read_packet_type(
        result
    )
    ok = _read_ok(
        result
    )
    verdict = _read_verdict(
        result
    )

    payload.pop(
        "bridge",
        None,
    )
    payload.pop(
        "suggestions",
        None,
    )
    payload.pop(
        "continuation_mode",
        None,
    )

    decision = decide_solomon_ai_continuation(
        original_request=original_request,
        payload=payload,
    )
    planned_mode = decision.mode
    presentation_state = _PRESENTATION_SUPPRESSED
    omission_reason = decision.reason
    bridge = ""
    suggestions: list[str] = []
    final_mode = CONTINUATION_NONE

    if (
        ok
        and planned_mode != CONTINUATION_NONE
    ):
        generation_started_at = perf_counter()
        (
            bridge,
            suggestions,
            generation_error,
        ) = _generate_continuation(
            decision=decision,
            original_request=original_request,
            answer=_clean_text(
                payload.get("answer")
                or payload.get("assistant_answer")
            ),
            request_id=request_id,
        )
        generation_elapsed_ms = (
            perf_counter()
            - generation_started_at
        ) * 1000

        if generation_error:
            presentation_state = (
                _PRESENTATION_GENERATION_FAILED
            )
            omission_reason = generation_error
            logger.info(
                "[UX_SYNTHESIS][CONTINUATION_GENERATION_FAILED] "
                "request_id=%s packet_type=%s planned_mode=%s "
                "reason=%s generation_ms=%.2f",
                request_id,
                packet_type or "",
                planned_mode,
                generation_error,
                generation_elapsed_ms,
            )
        else:
            presentation_state = _PRESENTATION_ACCEPTED
            omission_reason = ""
            final_mode = planned_mode
            logger.info(
                "[UX_SYNTHESIS][CONTINUATION_GENERATED] "
                "request_id=%s packet_type=%s mode=%s bridge=%s "
                "suggestion_count=%s generation_ms=%.2f",
                request_id,
                packet_type or "",
                final_mode,
                bool(bridge),
                len(suggestions),
                generation_elapsed_ms,
            )

    payload[
        "bridge"
    ] = bridge
    payload[
        "suggestions"
    ] = suggestions
    payload[
        "continuation_mode"
    ] = final_mode

    elapsed_ms = (
        perf_counter()
        - started_at
    ) * 1000

    if presentation_state == _PRESENTATION_ACCEPTED:
        logger.info(
            "[UX_SYNTHESIS][PRESENTATION_ACCEPTED] "
            "request_id=%s packet_type=%s mode=%s "
            "suggestion_count=%s elapsed_ms=%.2f",
            request_id,
            packet_type or "",
            final_mode,
            len(suggestions),
            elapsed_ms,
        )
    elif presentation_state == _PRESENTATION_GENERATION_FAILED:
        logger.info(
            "[UX_SYNTHESIS][PRESENTATION_OMITTED] "
            "request_id=%s packet_type=%s planned_mode=%s "
            "reason=%s elapsed_ms=%.2f",
            request_id,
            packet_type or "",
            planned_mode,
            omission_reason,
            elapsed_ms,
        )
    else:
        logger.info(
            "[UX_SYNTHESIS][PRESENTATION_SUPPRESSED] "
            "request_id=%s packet_type=%s mode=%s "
            "reason=%s elapsed_ms=%.2f",
            request_id,
            packet_type or "",
            final_mode,
            omission_reason,
            elapsed_ms,
        )

    return _build_result(
        payload=payload,
        packet_type=packet_type,
        ok=ok,
        verdict=verdict,
    )


__all__ = [
    "synthesize_solomon_ai_response",
]

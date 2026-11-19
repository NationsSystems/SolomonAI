# ------------------------------------------------------------------
# FILE: llm_lane_handler.py
# DIRECTORY: solomon_core/orchestrator_lanes/
# ------------------------------------------------------------------
# LLM Lane Handler
#
# PURPOSE
#   Execute an Orchestrator-authorized informational reasoning request
#   through the bounded direct custom model path.
#
# CONTRACT
#   - Execution only
#   - No classification or routing
#   - No workflow authorization
#   - No canned answer catalogs
#   - No UI action selection
#   - Requests one model-authored answer with optional presentation
#   - Uses an explicit complete-packet generation ceiling
#   - Preserves an explicit empty presentation shape for direct responses
#   - Preserves exploratory presentation only as one complete paired shape
#   - Preserves only governed response fields
#   - Supplies the canonical request only to bounded answer normalization
#   - Returns the substantive answer even when presentation fields fail
#   - Records the governed user turn in the ECB once per request
# ------------------------------------------------------------------

from __future__ import annotations

import json
from time import perf_counter
from typing import Any

from solomon_core.context.ecb_registry import (
    append_turn as ecb_append_turn,
    get_context as ecb_get_context,
)
from solomon_core.intelligence_service.intelligence_service_client import (
    get_intelligence_service_health,
)
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
from solomon_core.orchestrator_lanes.llm_lane_context import (
    build_assistant_prompt,
    ecb_metadata_from_casefile,
)
from solomon_core.orchestrator_lanes.llm_lane_response import (
    failure_message,
    payload_from_answer,
)
from solomon_core.presentation.response_governor import (
    govern_response,
)


logger = get_logger("llm_lane_handler")

_ASSISTANT_CALL_SITE = "solomon_assistant"
_ASSISTANT_MAX_NEW_TOKENS = 160
_MAX_LLM_ATTEMPTS = 1
_ECB_USER_TURN_SOURCE = "llm_lane_user"
_TEMPORARY_UNAVAILABLE_ANSWER = (
    "Solomon is temporarily unavailable. "
    "Your other workspace features are unaffected."
)


def _sis_unavailability_payload() -> dict[str, Any] | None:
    """Return the governed availability response only for known SIS outages."""

    try:
        health = get_intelligence_service_health()
    except Exception as exc:
        logger.debug(
            "[LLM][ASSISTANT_AVAILABILITY_READ_FAIL] error=%s",
            str(exc),
        )
        return None

    status = _clean_string(
        health.get("status")
    ).lower()
    circuit_open = bool(
        health.get("circuit_open")
    )

    if (
        not circuit_open
        or status not in {
            "degraded",
            "unavailable",
        }
    ):
        return None

    return {
        "answer": _TEMPORARY_UNAVAILABLE_ANSWER,
        "bridge": "",
        "suggestions": [],
    }


def _elapsed_ms(
    started_at: float,
) -> float:
    return (
        perf_counter()
        - started_at
    ) * 1000


def _execute_assistant_prompt(
    response_prompt: str,
    *,
    request_id: str,
    fairness_bucket: str,
):
    return execute_llm(
        LLMExecutionInput(
            user_query=response_prompt,
            mode=LLMExecutionMode.INFORMATIONAL_ONLY,
            context=None,
            response_format=(
                LLMResponseFormat.JSON_OBJECT
            ),
            call_site=_ASSISTANT_CALL_SITE,
            max_new_tokens=(
                _ASSISTANT_MAX_NEW_TOKENS
            ),
        ),
        priority="P0",
        request_id=request_id,
        fairness_bucket=fairness_bucket,
    )


def _clean_string(
    value: Any,
) -> str:
    if not isinstance(
        value,
        str,
    ):
        return ""

    return value.strip()


def _clean_suggestions(
    value: Any,
) -> list[str]:
    if not isinstance(
        value,
        list,
    ):
        return []

    suggestions: list[str] = []

    for item in value:
        suggestion = _clean_string(
            item
        )

        if not suggestion:
            return []

        suggestions.append(
            suggestion
        )

    return suggestions


def _is_explicit_empty_presentation(
    payload: dict[str, Any],
) -> bool:
    if (
        "bridge" not in payload
        or "suggestions" not in payload
    ):
        return False

    bridge = payload.get(
        "bridge"
    )
    suggestions = payload.get(
        "suggestions"
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


def _ecb_request_user_turn_exists(
    conversation_id: str,
    request_id: str,
) -> bool:
    """Return whether this governed request already wrote its ECB user turn."""

    clean_conversation_id = _clean_string(
        conversation_id
    )
    clean_request_id = _clean_string(
        request_id
    )

    if (
        not clean_conversation_id
        or not clean_request_id
    ):
        return False

    for turn in reversed(
        ecb_get_context(
            clean_conversation_id
        )
    ):
        if not isinstance(
            turn,
            dict,
        ):
            continue

        if (
            _clean_string(
                turn.get("role")
            ).lower()
            != "user"
        ):
            continue

        metadata = turn.get(
            "meta"
        )

        if not isinstance(
            metadata,
            dict,
        ):
            continue

        if (
            _clean_string(
                metadata.get(
                    "request_id"
                )
            )
            == clean_request_id
            and _clean_string(
                metadata.get(
                    "source"
                )
            )
            == _ECB_USER_TURN_SOURCE
        ):
            return True

    return False


def _append_ecb_user_turn_once(
    *,
    conversation_id: str,
    request_id: str,
    content: str,
) -> bool:
    """Append one user turn for the governed request and suppress retries."""

    if _ecb_request_user_turn_exists(
        conversation_id,
        request_id,
    ):
        return False

    ecb_append_turn(
        conversation_id,
        role="user",
        content=content,
        metadata={
            "request_id": request_id,
            "source": _ECB_USER_TURN_SOURCE,
        },
    )

    return True


def _extract_governed_payload(
    output_text: str,
    *,
    request_text: str,
) -> dict[str, Any]:
    """
    Normalize and govern the model response.

    The canonical request is supplied only to bounded answer-structure repair;
    it does not alter routing, authority, presentation generation, or facts.
    The substantive answer is mandatory. The explicit direct-response shape
    is preserved through governance even when optional empty fields are
    normalized away. Exploratory bridge and suggestion fields are preserved
    only as one structurally usable pair so the post-lane UX Synthesis
    boundary can validate the complete presentation shape.
    """

    parsed_payload = payload_from_answer(
        output_text,
        request_text=request_text,
    )
    explicit_empty_presentation = (
        _is_explicit_empty_presentation(
            parsed_payload
        )
    )
    governed_json = govern_response(
        json.dumps(
            parsed_payload,
            ensure_ascii=False,
        )
    )
    governed_payload = json.loads(
        governed_json
    )

    if not isinstance(
        governed_payload,
        dict,
    ):
        return {}

    answer = _clean_string(
        governed_payload.get(
            "answer"
        )
    )

    if not answer:
        return {}

    payload: dict[str, Any] = {
        "answer": answer,
    }

    if explicit_empty_presentation:
        payload[
            "bridge"
        ] = ""
        payload[
            "suggestions"
        ] = []

        return payload

    bridge = _clean_string(
        governed_payload.get(
            "bridge"
        )
    )
    suggestions = _clean_suggestions(
        governed_payload.get(
            "suggestions"
        )
    )

    if (
        bridge
        and suggestions
    ):
        payload[
            "bridge"
        ] = bridge
        payload[
            "suggestions"
        ] = suggestions

    return payload


def run_llm_lane(
    *,
    casefile,
    conversation_id: str,
    request_id: str,
):
    """
    Execute the LLM Lane and return its governed conversational payload.
    """

    total_started_at = perf_counter()
    prompt_started_at = perf_counter()

    final_input, response_prompt = build_assistant_prompt(
        conversation_id=conversation_id,
        casefile=casefile,
    )

    prompt_elapsed_ms = _elapsed_ms(
        prompt_started_at
    )

    logger.info(
        "[LLM][ASSISTANT_PROMPT_READY] "
        "call_site=%s request_id=%s prompt_chars=%s "
        "max_new_tokens=%s prompt_ms=%.2f",
        _ASSISTANT_CALL_SITE,
        request_id,
        len(
            response_prompt
        ),
        _ASSISTANT_MAX_NEW_TOKENS,
        prompt_elapsed_ms,
    )

    ecb_user_started_at = perf_counter()

    ecb_user_appended = _append_ecb_user_turn_once(
        conversation_id=conversation_id,
        request_id=request_id,
        content=final_input,
    )

    ecb_user_elapsed_ms = _elapsed_ms(
        ecb_user_started_at
    )

    if not ecb_user_appended:
        logger.info(
            "[LLM][ASSISTANT_ECB_USER_RETRY_SUPPRESSED] "
            "call_site=%s request_id=%s conversation_id=%s",
            _ASSISTANT_CALL_SITE,
            request_id,
            conversation_id,
        )

    last_error = None

    for attempt in range(
        _MAX_LLM_ATTEMPTS
    ):
        llm_started_at = perf_counter()
        result = _execute_assistant_prompt(
            response_prompt,
            request_id=request_id,
            fairness_bucket=build_opaque_fairness_bucket(
                conversation_id,
                namespace="conversation",
            ),
        )
        llm_elapsed_ms = _elapsed_ms(
            llm_started_at
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
            output_text = result.output.text

        if not output_text:
            last_error = failure_message(
                result
            )
            unavailable_payload = (
                _sis_unavailability_payload()
            )

            if unavailable_payload is not None:
                logger.warning(
                    "[LLM][ASSISTANT_UNAVAILABLE] "
                    "call_site=%s request_id=%s attempt=%s "
                    "llm_ms=%.2f total_ms=%.2f reason=%s",
                    _ASSISTANT_CALL_SITE,
                    request_id,
                    attempt + 1,
                    llm_elapsed_ms,
                    _elapsed_ms(
                        total_started_at
                    ),
                    str(
                        last_error
                    ),
                )
                return unavailable_payload

            logger.warning(
                "[LLM][ASSISTANT_EMPTY] "
                "call_site=%s request_id=%s attempt=%s "
                "llm_ms=%.2f total_ms=%.2f reason=%s",
                _ASSISTANT_CALL_SITE,
                request_id,
                attempt + 1,
                llm_elapsed_ms,
                _elapsed_ms(
                    total_started_at
                ),
                str(
                    last_error
                ),
            )
            continue

        try:
            govern_started_at = perf_counter()
            payload = _extract_governed_payload(
                output_text,
                request_text=final_input,
            )
            govern_elapsed_ms = _elapsed_ms(
                govern_started_at
            )
            answer = _clean_string(
                payload.get(
                    "answer"
                )
            )

            if not answer:
                raise ValueError(
                    "The LLM response did not contain a usable answer."
                )

            ecb_assistant_started_at = perf_counter()

            ecb_append_turn(
                conversation_id,
                role="assistant",
                content=answer,
                metadata=ecb_metadata_from_casefile(
                    casefile
                ),
            )

            ecb_assistant_elapsed_ms = _elapsed_ms(
                ecb_assistant_started_at
            )
            total_elapsed_ms = _elapsed_ms(
                total_started_at
            )
            has_bridge = bool(
                payload.get(
                    "bridge"
                )
            )
            suggestion_count = len(
                payload.get(
                    "suggestions",
                    [],
                )
            )

            logger.info(
                "[LLM][ASSISTANT_OK] "
                "call_site=%s request_id=%s answer_chars=%s "
                "bridge=%s suggestion_count=%s",
                _ASSISTANT_CALL_SITE,
                request_id,
                len(
                    answer
                ),
                has_bridge,
                suggestion_count,
            )

            logger.info(
                "[LLM][ASSISTANT_TIMING] "
                "call_site=%s request_id=%s attempt=%s "
                "prompt_ms=%.2f ecb_user_ms=%.2f "
                "ecb_user_appended=%s llm_ms=%.2f "
                "output_chars=%s govern_ms=%.2f "
                "ecb_assistant_ms=%.2f total_ms=%.2f",
                _ASSISTANT_CALL_SITE,
                request_id,
                attempt + 1,
                prompt_elapsed_ms,
                ecb_user_elapsed_ms,
                ecb_user_appended,
                llm_elapsed_ms,
                len(
                    output_text
                ),
                govern_elapsed_ms,
                ecb_assistant_elapsed_ms,
                total_elapsed_ms,
            )

            return payload

        except Exception as exc:
            last_error = exc

            logger.warning(
                "[LLM][ASSISTANT_RESPONSE_FAIL] "
                "call_site=%s request_id=%s attempt=%s "
                "llm_ms=%.2f total_ms=%.2f error=%s",
                _ASSISTANT_CALL_SITE,
                request_id,
                attempt + 1,
                llm_elapsed_ms,
                _elapsed_ms(
                    total_started_at
                ),
                str(
                    exc
                ),
            )

    raise ValueError(
        "LLM failed to produce a valid assistant response after "
        f"{_MAX_LLM_ATTEMPTS} attempt(s): {last_error}"
    )
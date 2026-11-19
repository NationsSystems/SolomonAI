# -------------------------------------------------------------------
# FILE: solomon_ai_exchange_recorder.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Final-response adapter for durable SolomonAI conversation exchanges.
#
# Mirrors the dedicated workspace browser's visible response selection
# so the persisted transcript contains the answer, bridge, and prompt
# suggestions the user actually received.
# -------------------------------------------------------------------

from solomon_core.solomon_ai_conversation_store import (
    record_solomon_ai_exchange,
)


def _clean_text(value) -> str:
    """Return display text without changing internal formatting."""

    return str(value or "").strip()


def _normalize_suggestions(value) -> list:
    """Return up to three unique non-empty suggestion strings."""

    if not isinstance(value, list):
        return []

    suggestions = []
    seen = set()

    for item in value:
        suggestion = _clean_text(item)
        normalized_suggestion = suggestion.casefold()

        if (
            not suggestion
            or normalized_suggestion in seen
        ):
            continue

        seen.add(normalized_suggestion)
        suggestions.append(suggestion)

        if len(suggestions) == 3:
            break

    return suggestions


def extract_solomon_ai_response_content(
    response: dict,
    *,
    fallback_answer: str = "",
) -> dict:
    """Return the same final answer and presentation rendered by the browser."""

    if not isinstance(response, dict):
        return {
            "answer": _clean_text(fallback_answer),
            "bridge": "",
            "suggestions": [],
        }

    result = response.get("result")
    result_payload = (
        result.get("payload")
        if isinstance(result, dict)
        and isinstance(result.get("payload"), dict)
        else {}
    )
    packet_payload = (
        response.get("payload")
        if isinstance(response.get("payload"), dict)
        else {}
    )
    answer_candidates = [
        result if isinstance(result, str) else "",
        result.get("answer") if isinstance(result, dict) else "",
        result.get("user_output") if isinstance(result, dict) else "",
        result.get("message") if isinstance(result, dict) else "",
        result.get("response") if isinstance(result, dict) else "",
        result.get("text") if isinstance(result, dict) else "",
        result_payload.get("answer"),
        result_payload.get("user_output"),
        result_payload.get("message"),
        response.get("user_output"),
        response.get("answer"),
        response.get("message"),
        response.get("response"),
        response.get("text"),
        packet_payload.get("answer"),
        packet_payload.get("user_output"),
        packet_payload.get("message"),
        response.get("error"),
        fallback_answer,
    ]
    answer = ""

    for candidate in answer_candidates:
        answer = _clean_text(candidate)

        if answer:
            break

    presentation_candidates = [
        result_payload,
        result if isinstance(result, dict) else {},
        packet_payload,
        response,
    ]
    bridge = ""
    suggestions = []

    for candidate in presentation_candidates:
        if not isinstance(candidate, dict):
            continue

        if not bridge:
            bridge = _clean_text(
                candidate.get("bridge")
            )

        if not suggestions:
            suggestions = _normalize_suggestions(
                candidate.get("suggestions")
            )

    return {
        "answer": answer,
        "bridge": bridge,
        "suggestions": suggestions,
    }


def record_solomon_ai_response_exchange(
    *,
    user_id: int,
    conversation_id: str,
    user_content: str,
    response: dict,
    status_code: int,
    request_id: str,
    fallback_answer: str = "",
) -> bool:
    """Persist one successful final SolomonAI response as an atomic exchange."""

    if (
        int(status_code or 0) >= 400
        or not isinstance(response, dict)
        or response.get("ok") is False
    ):
        return False

    clean_conversation_id = _clean_text(
        conversation_id
    )
    clean_user_content = _clean_text(
        user_content
    )

    if (
        not int(user_id or 0)
        or not clean_conversation_id
        or not clean_user_content
    ):
        return False

    content = extract_solomon_ai_response_content(
        response,
        fallback_answer=fallback_answer,
    )

    if not content["answer"]:
        return False

    return record_solomon_ai_exchange(
        user_id=int(user_id),
        conversation_id=clean_conversation_id,
        user_content=clean_user_content,
        assistant_content=content["answer"],
        bridge=content["bridge"],
        suggestions=content["suggestions"],
        request_id=_clean_text(request_id),
        status="complete",
    )


__all__ = [
    "extract_solomon_ai_response_content",
    "record_solomon_ai_response_exchange",
]
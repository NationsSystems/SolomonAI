# -------------------------------------------------------------
# FILE: task_api_response.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------
# Task API Response Normalization
#
# PURPOSE
#   Convert a completed Solomon packet into the stable API response
#   contract without interpretation, routing, or UX generation.
#
# CONTRACT
#   - Packet assembly and structural normalization only
#   - No bridge or suggestion generation
#   - No UI-action selection
#   - No semantic transformation of the assistant answer
# -------------------------------------------------------------

from __future__ import annotations

from typing import Any, Dict, List, Optional


_MAX_SUGGESTIONS = 5
_MAX_UI_ACTIONS = 5


def _safe_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _safe_identifier(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _read_packet_payload(result: Any) -> Dict[str, Any]:
    if hasattr(result, "payload"):
        payload = getattr(
            result,
            "payload",
            None,
        )

        return (
            dict(payload)
            if isinstance(payload, dict)
            else {}
        )

    if isinstance(result, dict):
        payload = result.get("payload")

        if isinstance(payload, dict):
            return dict(payload)

        return dict(result)

    return {}


def _read_packet_type(result: Any) -> Optional[str]:
    if hasattr(result, "header"):
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

        if isinstance(packet_type, str) and packet_type.strip():
            return packet_type.strip()

    if isinstance(result, dict):
        packet_type = result.get(
            "packet_type"
        )

        if isinstance(packet_type, str) and packet_type.strip():
            return packet_type.strip()

    return None


def _read_ok(result: Any) -> bool:
    if isinstance(result, dict):
        value = result.get("ok")

        if isinstance(value, bool):
            return value

    value = getattr(
        result,
        "ok",
        None,
    )

    return value if isinstance(value, bool) else True


def _read_verdict(result: Any) -> Optional[str]:
    if isinstance(result, dict):
        verdict = result.get(
            "verdict"
        )

        if isinstance(verdict, str) and verdict.strip():
            return verdict.strip()

    verdict = getattr(
        result,
        "verdict",
        None,
    )

    if isinstance(verdict, str) and verdict.strip():
        return verdict.strip()

    return None


def _read_identifier(
    result: Any,
    identifier_name: str,
) -> str:
    if isinstance(result, dict):
        direct_value = _safe_identifier(
            result.get(identifier_name)
        )

        if direct_value:
            return direct_value

        payload = result.get("payload")

        if isinstance(payload, dict):
            payload_value = _safe_identifier(
                payload.get(identifier_name)
            )

            if payload_value:
                return payload_value

    direct_value = _safe_identifier(
        getattr(
            result,
            identifier_name,
            None,
        )
    )

    if direct_value:
        return direct_value

    payload = getattr(
        result,
        "payload",
        None,
    )

    if isinstance(payload, dict):
        return _safe_identifier(
            payload.get(identifier_name)
        )

    return ""


def _normalize_suggestions(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []

    suggestions: List[str] = []
    seen = set()

    for item in value:
        suggestion = _safe_text(
            item
        )

        if (
            not suggestion
            or suggestion in seen
        ):
            continue

        suggestions.append(
            suggestion
        )
        seen.add(
            suggestion
        )

        if len(suggestions) >= _MAX_SUGGESTIONS:
            break

    return suggestions


def _normalize_ui_actions(value: Any) -> List[Dict[str, Any]]:
    """
    Preserve already-produced presentation actions without interpreting them.

    UX Synthesis or another authorized presentation component owns action
    generation. Packet assembly only enforces the list and object boundary.
    """

    if not isinstance(value, list):
        return []

    actions: List[Dict[str, Any]] = []

    for item in value:
        if not isinstance(item, dict):
            continue

        actions.append(
            dict(item)
        )

        if len(actions) >= _MAX_UI_ACTIONS:
            break

    return actions


def _normalize_payload(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    normalized = dict(
        payload
    )

    normalized["answer"] = _safe_text(
        payload.get("answer")
        or payload.get("assistant_answer")
    )
    normalized["bridge"] = _safe_text(
        payload.get("bridge")
    )
    normalized["suggestions"] = (
        _normalize_suggestions(
            payload.get("suggestions")
        )
    )

    ui_actions = _normalize_ui_actions(
        payload.get("ui_actions")
        or payload.get("uiActions")
    )

    normalized.pop(
        "assistant_answer",
        None,
    )
    normalized.pop(
        "uiActions",
        None,
    )

    if ui_actions:
        normalized["ui_actions"] = ui_actions
    else:
        normalized.pop(
            "ui_actions",
            None,
        )

    return normalized


def _normalize_response(
    result: Any,
    *,
    request_id: Any = None,
    conversation_id: Any = None,
) -> Dict[str, Any]:
    """
    Assemble the final API response from a completed Solomon packet.

    Explicit identifiers supplied by the execution service take precedence
    over identifiers already present in the completed packet.
    """

    payload = _read_packet_payload(
        result
    )
    normalized_payload = _normalize_payload(
        payload
    )
    normalized_request_id = (
        _safe_identifier(
            request_id
        )
        or _read_identifier(
            result,
            "request_id",
        )
    )
    normalized_conversation_id = (
        _safe_identifier(
            conversation_id
        )
        or _read_identifier(
            result,
            "conversation_id",
        )
    )

    response: Dict[str, Any] = {
        "ok": _read_ok(
            result
        ),
        "packet_type": _read_packet_type(
            result
        ),
        "payload": normalized_payload,
    }

    if normalized_request_id:
        response["request_id"] = (
            normalized_request_id
        )
        normalized_payload["request_id"] = (
            normalized_request_id
        )

    if normalized_conversation_id:
        response["conversation_id"] = (
            normalized_conversation_id
        )
        normalized_payload["conversation_id"] = (
            normalized_conversation_id
        )

    verdict = _read_verdict(
        result
    )

    if verdict:
        response["verdict"] = verdict

    return response
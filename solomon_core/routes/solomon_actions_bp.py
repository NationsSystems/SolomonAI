# -------------------------------------------------------------------
# FILE: solomon_actions_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Server-authoritative routes for executing registered Solomon Actions.
# -------------------------------------------------------------------

import uuid

from flask import Blueprint, g, jsonify, request, session

from solomon_core.actions.solomon_file_action_execution import (
    SolomonFileActionExecutionError,
    build_solomon_file_action_error_packet,
    execute_solomon_file_action,
)
from solomon_core.auth_utils import login_required
from solomon_core.logger import get_logger


solomon_actions_bp = Blueprint(
    "solomon_actions_bp",
    __name__,
    url_prefix="/workspace/actions",
)

logger = get_logger("solomon_actions_bp")


def _request_id() -> str:
    return str(
        getattr(g, "request_id", None)
        or uuid.uuid4()
    )


def _current_user_id() -> int:
    try:
        return int(session.get("user_id") or 0)
    except (TypeError, ValueError):
        return 0


def _read_json_payload() -> dict:
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else {}


@solomon_actions_bp.route("/file/execute", methods=["POST"])
@login_required
def execute_file_action():
    """Execute one registered Action against one currently authorized file."""

    request_id = _request_id()
    user_id = _current_user_id()
    payload = _read_json_payload()
    action_id = str(payload.get("action_id") or "").strip()
    document_id = str(payload.get("document_id") or "").strip()
    parameters = (
        dict(payload.get("parameters"))
        if isinstance(payload.get("parameters"), dict)
        else {}
    )

    if not user_id:
        error = SolomonFileActionExecutionError(
            "authentication_required",
            "Authentication is required to run that Action.",
            status_code=401,
            action_id=action_id,
            document_id=document_id,
        )
        return jsonify(
            build_solomon_file_action_error_packet(
                error,
                request_id=request_id,
            )
        ), error.status_code

    if not action_id or not document_id:
        error = SolomonFileActionExecutionError(
            "invalid_action_request",
            "Choose a file and Action before continuing.",
            status_code=400,
            action_id=action_id,
            document_id=document_id,
        )
        return jsonify(
            build_solomon_file_action_error_packet(
                error,
                request_id=request_id,
            )
        ), error.status_code

    try:
        packet = execute_solomon_file_action(
            user_id=user_id,
            document_id=document_id,
            action_id=action_id,
            request_id=request_id,
            parameters=parameters,
        )
    except SolomonFileActionExecutionError as exc:
        logger.info(
            "[actions.file.execute_denied] request_id=%s user_id=%s "
            "document_id=%s action_id=%s error=%s",
            request_id,
            user_id,
            document_id,
            action_id,
            exc.error_code,
        )
        return jsonify(
            build_solomon_file_action_error_packet(
                exc,
                request_id=request_id,
            )
        ), exc.status_code
    except Exception as exc:
        logger.exception(
            "[actions.file.execute_failed] request_id=%s user_id=%s "
            "document_id=%s action_id=%s error=%s",
            request_id,
            user_id,
            document_id,
            action_id,
            exc,
        )
        error = SolomonFileActionExecutionError(
            "action_execution_failed",
            "Solomon could not complete that Action.",
            status_code=500,
            action_id=action_id,
            document_id=document_id,
        )
        return jsonify(
            build_solomon_file_action_error_packet(
                error,
                request_id=request_id,
            )
        ), error.status_code

    logger.info(
        "[actions.file.execute_complete] request_id=%s user_id=%s "
        "document_id=%s action_id=%s",
        request_id,
        user_id,
        document_id,
        action_id,
    )
    return jsonify(packet), 200


__all__ = [
    "solomon_actions_bp",
]

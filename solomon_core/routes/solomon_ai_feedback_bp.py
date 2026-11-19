# -------------------------------------------------------------------
# FILE: solomon_ai_feedback_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Authenticated API route for SolomonAI response feedback.
#
# The browser submits only the conversation identity, saved assistant
# message identity, and selected feedback value. Ownership validation
# and persistence remain server-authoritative.
# -------------------------------------------------------------------

import uuid

from flask import (
    Blueprint,
    g,
    jsonify,
    request,
    session,
)

from solomon_core.auth_utils import login_required
from solomon_core.logger import get_logger
from solomon_core.solomon_ai_response_feedback_store import (
    SolomonAIResponseFeedbackError,
    save_solomon_ai_response_feedback,
)


solomon_ai_feedback_bp = Blueprint(
    "solomon_ai_feedback_bp",
    __name__,
    url_prefix="/api/task",
)

logger = get_logger(
    "solomon_ai_feedback_bp"
)


def get_request_id() -> str:
    """Return the active request identifier."""

    return (
        getattr(
            g,
            "request_id",
            None,
        )
        or str(
            uuid.uuid4()
        )
    )


def get_current_user_id() -> int:
    """Return the authenticated user identifier."""

    try:
        return int(
            session.get(
                "user_id"
            )
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0


def read_feedback_payload() -> dict:
    """Return a safe JSON feedback payload."""

    payload = request.get_json(
        silent=True
    )

    return (
        payload
        if isinstance(
            payload,
            dict,
        )
        else {}
    )


def feedback_error_response(
    *,
    error_code: str,
    user_output: str,
    request_id: str,
    status_code: int,
):
    """Return the canonical response-feedback error packet."""

    return jsonify({
        "ok": False,
        "packet_type": "solomon_ai_response_feedback",
        "artifact_type": "response_feedback",
        "error": str(
            error_code
            or "SolomonAiFeedbackFailed"
        ).strip(),
        "user_output": str(
            user_output
            or "Feedback could not be saved."
        ).strip(),
        "request_id": request_id,
    }), int(
        status_code
        or 400
    )


@solomon_ai_feedback_bp.route(
    "/feedback",
    methods=["POST"],
)
@login_required
def save_solomon_ai_response_feedback_route():
    """Save helpful or not-helpful feedback for one assistant response."""

    request_id = get_request_id()
    user_id = get_current_user_id()
    payload = read_feedback_payload()

    try:
        packet = save_solomon_ai_response_feedback(
            user_id=user_id,
            conversation_id=str(
                payload.get(
                    "conversation_id"
                )
                or ""
            ).strip(),
            message_id=payload.get(
                "message_id"
            ),
            request_id=str(
                payload.get(
                    "request_id"
                )
                or ""
            ).strip(),
            feedback=str(
                payload.get(
                    "feedback"
                )
                or ""
            ).strip(),
        )
    except SolomonAIResponseFeedbackError as exc:
        logger.warning(
            (
                "[solomon_ai.feedback_rejected] "
                "request_id=%s user_id=%s "
                "conversation_id=%s error=%s"
            ),
            request_id,
            user_id,
            payload.get(
                "conversation_id"
            ),
            exc.error_code,
        )

        return feedback_error_response(
            error_code=exc.error_code,
            user_output=exc.user_output,
            request_id=request_id,
            status_code=exc.status_code,
        )
    except Exception:
        logger.exception(
            (
                "[solomon_ai.feedback_failed] "
                "request_id=%s user_id=%s "
                "conversation_id=%s"
            ),
            request_id,
            user_id,
            payload.get(
                "conversation_id"
            ),
        )

        return feedback_error_response(
            error_code=(
                "SolomonAiFeedbackSaveFailed"
            ),
            user_output=(
                "Feedback could not be saved."
            ),
            request_id=request_id,
            status_code=500,
        )

    packet["request_id"] = request_id

    logger.info(
        (
            "[solomon_ai.feedback_saved] "
            "request_id=%s user_id=%s "
            "conversation_id=%s message_id=%s "
            "feedback=%s"
        ),
        request_id,
        user_id,
        packet.get(
            "conversation_id"
        ),
        packet.get(
            "message_id"
        ),
        packet.get(
            "feedback"
        ),
    )

    return jsonify(
        packet
    ), 200


__all__ = [
    "solomon_ai_feedback_bp",
]
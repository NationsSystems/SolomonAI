# -------------------------------------------------------------------
# FILE: solomon_ai_response_feedback_store.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Durable feedback storage for completed SolomonAI assistant responses.
#
# Validates conversation and message ownership before recording helpful
# or not-helpful feedback. The existing feedback table remains the
# canonical persistence surface for response-quality signals.
# -------------------------------------------------------------------

from solomon_core.db import SessionLocal
from solomon_core.models import (
    Feedback,
    SolomonAIConversation,
    SolomonAIConversationMessage,
)


SOLOMON_AI_RESPONSE_FEEDBACK_VALUES = frozenset({
    "helpful",
    "not_helpful",
})
SOLOMON_AI_RESPONSE_FEEDBACK_SKILL = (
    "solomon_ai_response_feedback"
)
SOLOMON_AI_RESPONSE_FEEDBACK_TASK_PREFIX = (
    "solomon_ai_message"
)


class SolomonAIResponseFeedbackError(Exception):
    """Raised when SolomonAI response feedback cannot be saved."""

    def __init__(
        self,
        error_code: str,
        user_output: str,
        *,
        status_code: int = 400,
    ):
        super().__init__(user_output)

        self.error_code = str(
            error_code or "SolomonAiFeedbackFailed"
        ).strip()
        self.user_output = str(
            user_output or "Feedback could not be saved."
        ).strip()
        self.status_code = int(
            status_code or 400
        )


def _clean_value(value) -> str:
    """Return normalized request text."""

    return str(value or "").strip()


def _clean_feedback_value(value) -> str:
    """Return one supported response-feedback value."""

    clean_value = _clean_value(
        value
    ).lower()

    if clean_value not in SOLOMON_AI_RESPONSE_FEEDBACK_VALUES:
        return ""

    return clean_value


def _clean_message_id(value) -> int:
    """Return a positive persisted message id."""

    clean_value = _clean_value(
        value
    )

    if not clean_value:
        return 0

    try:
        message_id = int(
            clean_value
        )
    except (
        TypeError,
        ValueError,
    ):
        return 0

    return message_id if message_id > 0 else 0


def _build_feedback_task_id(
    message_id: int,
) -> str:
    """Return the stable generic-feedback task identifier."""

    return (
        f"{SOLOMON_AI_RESPONSE_FEEDBACK_TASK_PREFIX}:"
        f"{int(message_id)}"
    )


def _resolve_owned_assistant_message(
    db_session,
    *,
    user_id: int,
    conversation_id: str,
    message_id: int,
    request_id: str,
):
    """Resolve one completed assistant message owned by the user."""

    query = (
        db_session.query(
            SolomonAIConversationMessage
        )
        .join(
            SolomonAIConversation,
            (
                SolomonAIConversation.conversation_id
                == SolomonAIConversationMessage.conversation_id
            ),
        )
        .filter(
            SolomonAIConversation.user_id
            == int(user_id),
            SolomonAIConversation.conversation_id
            == conversation_id,
            SolomonAIConversation.deleted_at.is_(None),
            SolomonAIConversationMessage.role
            == "assistant",
            SolomonAIConversationMessage.status
            == "complete",
        )
    )

    if message_id:
        query = query.filter(
            SolomonAIConversationMessage.id
            == message_id
        )
    elif request_id:
        query = query.filter(
            SolomonAIConversationMessage.request_id
            == request_id
        )
    else:
        return None

    return (
        query
        .order_by(
            SolomonAIConversationMessage.id.desc()
        )
        .first()
    )


def save_solomon_ai_response_feedback(
    *,
    user_id: int,
    conversation_id: str,
    feedback: str,
    message_id=None,
    request_id: str = "",
) -> dict:
    """Validate and persist feedback for one assistant response."""

    clean_user_id = int(
        user_id or 0
    )
    clean_conversation_id = _clean_value(
        conversation_id
    )
    clean_feedback = _clean_feedback_value(
        feedback
    )
    clean_message_id = _clean_message_id(
        message_id
    )
    clean_request_id = _clean_value(
        request_id
    )[:64]

    if not clean_user_id:
        raise SolomonAIResponseFeedbackError(
            "AuthenticationRequired",
            "Authentication is required to save feedback.",
            status_code=401,
        )

    if not clean_conversation_id:
        raise SolomonAIResponseFeedbackError(
            "SolomonAiFeedbackConversationMissing",
            "The SolomonAI conversation was not provided.",
        )

    if not clean_feedback:
        raise SolomonAIResponseFeedbackError(
            "SolomonAiFeedbackInvalid",
            "Feedback must be helpful or not helpful.",
        )

    if not clean_message_id and not clean_request_id:
        raise SolomonAIResponseFeedbackError(
            "SolomonAiFeedbackMessageMissing",
            "The SolomonAI response was not identified.",
        )

    db_session = SessionLocal()

    try:
        message = _resolve_owned_assistant_message(
            db_session,
            user_id=clean_user_id,
            conversation_id=clean_conversation_id,
            message_id=clean_message_id,
            request_id=clean_request_id,
        )

        if not message:
            raise SolomonAIResponseFeedbackError(
                "SolomonAiFeedbackMessageNotFound",
                (
                    "The saved SolomonAI response could not "
                    "be found for this conversation."
                ),
                status_code=404,
            )

        feedback_task_id = _build_feedback_task_id(
            message.id
        )
        record = (
            db_session.query(
                Feedback
            )
            .filter(
                Feedback.user_id
                == clean_user_id,
                Feedback.task_id
                == feedback_task_id,
                Feedback.skill_name
                == SOLOMON_AI_RESPONSE_FEEDBACK_SKILL,
            )
            .first()
        )

        if record:
            record.feedback_type = clean_feedback
            record.reasoning_type = (
                clean_conversation_id
            )
        else:
            record = Feedback(
                task_id=feedback_task_id,
                user_id=clean_user_id,
                feedback_type=clean_feedback,
                skill_name=(
                    SOLOMON_AI_RESPONSE_FEEDBACK_SKILL
                ),
                reasoning_type=(
                    clean_conversation_id
                ),
            )
            db_session.add(
                record
            )

        db_session.commit()
        db_session.refresh(
            record
        )

        return {
            "ok": True,
            "packet_type": "solomon_ai_response_feedback",
            "artifact_type": "response_feedback",
            "conversation_id": clean_conversation_id,
            "message_id": str(message.id),
            "request_id": str(
                message.request_id or ""
            ).strip(),
            "feedback": clean_feedback,
            "feedback_id": str(
                record.id or ""
            ),
            "status": "saved",
        }
    except SolomonAIResponseFeedbackError:
        db_session.rollback()
        raise
    except Exception as exc:
        db_session.rollback()

        raise SolomonAIResponseFeedbackError(
            "SolomonAiFeedbackSaveFailed",
            "Feedback could not be saved.",
            status_code=500,
        ) from exc
    finally:
        SessionLocal.remove()


__all__ = [
    "SOLOMON_AI_RESPONSE_FEEDBACK_VALUES",
    "SolomonAIResponseFeedbackError",
    "save_solomon_ai_response_feedback",
]
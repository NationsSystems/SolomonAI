# solomon_core/conversation_registry.py
# ------------------------------------------------------------
# PURPOSE:
#   Conversation Registry — signal-only, non-authoritative.
#
# GUARANTEES:
#   • NO intent authority
#   • NO flow-control authority
#   • NO state transitions
#   • NO clarification emission
#   • Structural signals ONLY
#
# ROLE:
#   • Maintain conversation bookkeeping
#   • Emit continuation and lineage signals
#   • Preserve orchestrator authority
#
# LOGGING:
#   • Subsystem-based tags only
#   • No phase labels in log messages
# ------------------------------------------------------------

from typing import Dict, Any, Optional, List
import time
import uuid

from solomon_core.logger import get_logger

logger = get_logger("solomon_core.conversation_registry")


# ------------------------------------------------------------
# Deterministic artifact validators (STRUCTURAL ONLY)
# ------------------------------------------------------------
def _validate_docs(value: Any) -> Optional[str]:
    if not isinstance(value, list):
        return "docs must be a list"
    if len(value) == 0:
        return "docs list is empty"
    return None


ARTIFACT_VALIDATORS = {
    "docs": _validate_docs,
}

# ------------------------------------------------------------
# Clarification limits (SIGNAL ONLY)
# ------------------------------------------------------------
MAX_PENDING_QUESTIONS = 3
MAX_REPEAT_INPUTS = 2


# ------------------------------------------------------------
# Conversation Record (STATELESS WRT FLOW)
# ------------------------------------------------------------
class ConversationRecord:
    def __init__(
        self,
        conversation_id: str,
        turn_index: int,
        required_artifacts: Optional[Dict[str, bool]] = None,
        failure_type: Optional[str] = None,
        last_updated: Optional[float] = None,
    ):
        self.conversation_id = conversation_id
        self.turn_index = turn_index
        self.required_artifacts = required_artifacts or {}
        self.failure_type = failure_type
        self.last_updated = last_updated or time.time()

        # ----------------------------------------------------
        # Clarification bookkeeping (NON-AUTHORITATIVE)
        # ----------------------------------------------------
        self.pending_questions: List[str] = []
        self.active_question: Optional[str] = None
        self.clarification_attempts: int = 0

        # ----------------------------------------------------
        # Human tolerance tracking (STRUCTURAL)
        # ----------------------------------------------------
        self.last_user_input: Optional[str] = None
        self.repeat_count: int = 0

        # ----------------------------------------------------
        # Orchestrator lineage (VISIBILITY ONLY)
        # ----------------------------------------------------
        self.last_orchestrator_event_id: Optional[str] = None
        self.last_orchestrator_state: Optional[str] = None
        self.last_orchestrator_code: Optional[int] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "turn_index": self.turn_index,
            "required_artifacts": dict(self.required_artifacts),
            "last_updated": self.last_updated,
            "pending_questions": list(self.pending_questions),
            "active_question": self.active_question,
            "clarification_attempts": self.clarification_attempts,
            "repeat_count": self.repeat_count,
            "failure_type": self.failure_type,

            # lineage snapshot
            "last_orchestrator_event_id": self.last_orchestrator_event_id,
            "last_orchestrator_state": self.last_orchestrator_state,
            "last_orchestrator_code": self.last_orchestrator_code,
        }


# ------------------------------------------------------------
# Conversation Registry
# ------------------------------------------------------------
class ConversationRegistry:
    def __init__(self):
        self._store: Dict[str, ConversationRecord] = {}
        logger.info("ConversationRegistry initialized")

    def get_or_create(
        self,
        conversation_id: Optional[str],
        turn_index: Optional[int],
    ) -> ConversationRecord:
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            turn_index = 0

        if conversation_id not in self._store:
            record = ConversationRecord(
                conversation_id=conversation_id,
                turn_index=turn_index or 0,
            )
            self._store[conversation_id] = record
            logger.info(
                "Created new conversation record",
                extra={
                    "conversation_id": conversation_id,
                    "turn_index": record.turn_index,
                },
            )
            return record

        return self._store[conversation_id]

    # --------------------------------------------------------
    # Update conversation bookkeeping (NO FLOW AUTHORITY)
    # --------------------------------------------------------
    def update(
        self,
        conversation_id: str,
        *,
        failure_type: Optional[str] = None,
        required_artifacts: Optional[Dict[str, bool]] = None,
        turn_index: Optional[int] = None,
        orchestrator_event_id: Optional[str] = None,
        orchestrator_state: Optional[str] = None,
        orchestrator_code: Optional[int] = None,
    ) -> None:
        record = self._store.get(conversation_id)
        if not record:
            return

        if failure_type is not None:
            record.failure_type = failure_type

        if required_artifacts is not None:
            record.required_artifacts = dict(required_artifacts)

        if turn_index is not None:
            record.turn_index = turn_index

        # ----------------------------------------------------
        # Orchestrator lineage snapshot update (LABEL ONLY)
        # ----------------------------------------------------
        if orchestrator_event_id is not None:
            record.last_orchestrator_event_id = orchestrator_event_id

        if orchestrator_state is not None:
            record.last_orchestrator_state = orchestrator_state

        if orchestrator_code is not None:
            record.last_orchestrator_code = orchestrator_code

        record.last_updated = time.time()

        logger.info(
            "Updated conversation record",
            extra={
                "conversation_id": conversation_id,
                "turn_index": record.turn_index,
                "orchestrator_state": record.last_orchestrator_state,
                "orchestrator_event_id": record.last_orchestrator_event_id,
            },
        )

    # --------------------------------------------------------
    # Continuation evaluation (SIGNALS ONLY)
    # --------------------------------------------------------
    def evaluate_continuation(
        self,
        *,
        record: ConversationRecord,
        clarification_response: bool,
        provided_artifacts: Optional[Dict[str, Any]] = None,
        raw_user_input: Optional[str] = None,
    ) -> Dict[str, Any]:

        provided_artifacts = provided_artifacts or {}

        # ----------------------------------------------------
        # Repeat detection (STRUCTURAL)
        # ----------------------------------------------------
        if raw_user_input is not None:
            if raw_user_input == record.last_user_input:
                record.repeat_count += 1
            else:
                record.repeat_count = 0
            record.last_user_input = raw_user_input

        missing_artifacts: Dict[str, bool] = {}
        invalid_artifacts: Dict[str, str] = {}

        if record.required_artifacts:
            for name, required in record.required_artifacts.items():
                value = provided_artifacts.get(name)
                if required and value is None:
                    missing_artifacts[name] = True
                    continue

                validator = ARTIFACT_VALIDATORS.get(name)
                if validator:
                    error = validator(value)
                    if error:
                        invalid_artifacts[name] = error

        decision = {
            "conversation_id": record.conversation_id,
            "is_continuation": bool(clarification_response),
            "missing_artifacts": missing_artifacts,
            "invalid_artifacts": invalid_artifacts,
            "repeat_count": record.repeat_count,
            "next_turn_index": record.turn_index + 1,

            # lineage passthrough (READ-ONLY)
            "last_orchestrator_event_id": record.last_orchestrator_event_id,
            "last_orchestrator_state": record.last_orchestrator_state,
            "last_orchestrator_code": record.last_orchestrator_code,
        }

        logger.info(
            "Emitted continuation signal",
            extra={
                "conversation_id": record.conversation_id,
                "missing": bool(missing_artifacts),
                "invalid": bool(invalid_artifacts),
                "repeat_count": record.repeat_count,
                "orchestrator_state": record.last_orchestrator_state,
            },
        )

        return decision


# ------------------------------------------------------------
# Global singleton
# ------------------------------------------------------------
conversation_registry = ConversationRegistry()

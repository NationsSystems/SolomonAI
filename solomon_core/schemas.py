# schemas.py — Data models for requests and responses (Phase 29.1 → Phase 60)
# -------------------------------------------------------------------------
# Phase 60 ADDITION:
#   • ECB — Ephemeral Context Buffer (identity + turn metadata only)
#   • No persistence guarantees
#   • No memory authority implied
# -------------------------------------------------------------------------

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any, Literal, List
import uuid
import time


# ============================================================================
# Requests
# ============================================================================

class TaskRequest(BaseModel):
    task: str = Field(..., description="Natural language task request")
    user_id: Optional[str] = Field(default="anonymous")

    # ECB identity (opaque, non-authoritative)
    conversation_id: Optional[str] = None
    turn_index: Optional[int] = None

    clarification_response: Optional[bool] = False


# ============================================================================
# Responses
# ============================================================================

class TaskResponse(BaseModel):
    # ---------------------------------------------------
    # Execution outcome (PHASE 43 — RELAXED)
    # ---------------------------------------------------
    success: Optional[bool] = None

    task_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    intent: Optional[str] = None
    entities: Optional[Dict[str, Any]] = None

    result: str | dict | None = None
    error_type: Optional[str] = None
    error_message: Optional[str] = None
    duration_ms: int = Field(default_factory=lambda: int(time.time() * 1000))

    reasoning_source: str = "deterministic"
    confidence: Optional[float] = None
    summary: Optional[str] = None

    user_output: str | dict | None = None

    failure_type: Optional[str] = None
    context_hint: Optional[str] = None
    debug_trace: Optional[str] = None

    # ---------------------------------------------------
    # Phase 60 — ECB visibility (NON-AUTHORITATIVE)
    # ---------------------------------------------------
    conversation_id: Optional[str] = None
    turn_index: Optional[int] = None

    clarification_pending: Optional[bool] = False
    prior_failure_type: Optional[str] = None

    # ---------------------------------------------------
    # Phase 43 — Response modes
    # ---------------------------------------------------
    response_mode: Optional[
        Literal["answer", "blocked", "followup", "timeout", "emitted"]
    ] = None

    active_goal: Optional[str] = None
    required_inputs: Optional[Dict[str, bool]] = None
    continuation_hint: Optional[str] = None

    # ---------------------------------------------------
    # Phase 57 — Evidence & Disclosure (AUTHORITATIVE)
    # ---------------------------------------------------
    used_documents: Optional[List[str]] = None

    # ---------------------------------------------------
    # Legacy / visibility fields
    # ---------------------------------------------------
    evidence_state: Optional[Any] = None

    status: Optional[Literal["ok", "error"]] = None

    # ---------------------------------------------------
    # Orchestrator visibility (NON-AUTHORITATIVE)
    # ---------------------------------------------------
    orchestrator_state: Optional[str] = None
    orchestrator_code: Optional[int] = None
    orchestrator_event_id: Optional[str] = None
    orchestrator_violation: Optional[str] = None

    # ---------------------------------------------------
    # Contract enforcement
    # ---------------------------------------------------
    @model_validator(mode="after")
    def enforce_success_contract(self):
        """
        Phase 43 RULE:
        Emitted responses bypass strict enforcement.
        """

        if self.response_mode == "emitted":
            if self.success is None:
                self.success = True
            self.status = "ok"
            return self

        if self.orchestrator_state == "COMPLETED" and self.failure_type is None:
            self.success = True
            self.status = "ok"
            if not self.response_mode:
                self.response_mode = "answer"
            return self

        if self.response_mode == "followup":
            self.success = True
            self.status = "ok"
            self.failure_type = None
            return self

        if self.failure_type in ("execution_failure", "timeout"):
            self.success = False
            self.status = "error"
            if not self.response_mode:
                self.response_mode = "timeout"
            return self

        if self.failure_type == "grounding_failure":
            self.success = True
            self.status = "ok"
            if not self.response_mode:
                self.response_mode = "blocked"
            if not self.summary:
                self.summary = (
                    "I understand your goal, but I need additional information."
                )
            return self

        if self.success:
            self.status = "ok"
            if not self.response_mode:
                self.response_mode = "answer"
        else:
            self.status = "error"

        return self

    def as_dict(self) -> dict:
        return self.dict()

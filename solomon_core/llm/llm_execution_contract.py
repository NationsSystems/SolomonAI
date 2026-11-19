# ---------------------------------------------------------------------------
# FILE: llm_execution_contract.py
# DIRECTORY: solomon_core/llm/
# ---------------------------------------------------------------------------
# LLM Execution Contract
#
# PURPOSE:
#   Define the single, authoritative interface by which governed runtime code
#   may invoke LLM-based reasoning as a bounded spoke.
#
# NON-NEGOTIABLE CONSTRAINTS:
#   • Orchestrator remains sole authority
#   • This module does NOT execute LLMs
#   • This module does NOT decide flow
#   • This module does NOT touch presentation or UX language
#   • This module defines structure, limits, and failure semantics only
#
# STATUS:
#   Canonical contract surface. Changes must remain backward-compatible unless
#   a deliberate contract migration is approved.
# ---------------------------------------------------------------------------

from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional


# ===========================================================================
# Execution Mode
# ===========================================================================

class LLMExecutionMode(str, Enum):
    """
    Declares the bounded intent under which the LLM is allowed to operate.
    This is set by governed runtime code and MUST be respected by all LLM
    transports.
    """

    INFORMATIONAL_ONLY = "informational_only"
    DIRECT_EXECUTION = "direct_execution"


# ===========================================================================
# Response Format
# ===========================================================================

class LLMResponseFormat(str, Enum):
    """
    Declares the expected response shape for the LLM transport.

    TEXT:
      Default free-text response.

    JSON_OBJECT:
      Transport should request a valid JSON object when the provider supports
      structured output. Callers must still validate shape.
    """

    TEXT = "text"
    JSON_OBJECT = "json_object"


# ===========================================================================
# Runtime Profile
# ===========================================================================

class LLMRuntimeProfile(str, Enum):
    """
    Declares the portable inference-runtime strategy requested by governed
    caller code.

    DEFAULT:
      Use the transport's standard generation behavior.

    STATIC_CACHE:
      Request a reusable static key-value cache when supported by the selected
      backend. Backends that do not support it must fall back safely.

    STATIC_CACHE_COMPILE:
      Request static cache plus backend compilation. This profile is reserved
      for isolated benchmark or explicitly approved deployment paths and must
      not be enabled implicitly.

    Runtime profiles affect execution mechanics only. They do not grant
    authority, change response requirements, or alter caller-owned policy.
    """

    DEFAULT = "default"
    STATIC_CACHE = "static_cache"
    STATIC_CACHE_COMPILE = "static_cache_compile"


# ===========================================================================
# Input Contract
# ===========================================================================

@dataclass(frozen=True)
class LLMExecutionInput:
    """
    Immutable input passed to the LLM execution spoke.

    RULES:
    • user_query must be sanitized caller-provided instruction text
    • context must be read-only, optional, and non-authoritative
    • mode is mandatory and explicit
    • response_format requests shape only; it does not grant authority
    • call_site is internal observability/proof metadata only
    • max_new_tokens may bound generation length for latency-sensitive callers
    • max_new_tokens=None preserves the transport's configured default
    • runtime_profile requests portable execution mechanics only
    • runtime_profile does not grant authority or alter response policy
    • timeout_seconds may apply a caller-owned wall-clock budget
    • timeout_seconds=None preserves the transport's configured default
    """

    user_query: str
    mode: LLMExecutionMode
    context: Optional[Dict[str, Any]] = None
    response_format: LLMResponseFormat = LLMResponseFormat.TEXT
    call_site: Optional[str] = None
    max_new_tokens: Optional[int] = None
    runtime_profile: LLMRuntimeProfile = LLMRuntimeProfile.DEFAULT
    timeout_seconds: Optional[int] = None


# ===========================================================================
# Output Contract
# ===========================================================================

@dataclass(frozen=True)
class LLMExecutionOutput:
    """
    Immutable output returned by the LLM execution spoke.

    RULES:
    • text is the ONLY user-consumable field
    • confidence is INTERNAL ONLY
    • citations are optional and informational
    • refusal signals controlled non-response
    """

    text: str
    confidence: str  # expected values: "low", "medium", "high"
    citations: List[str]
    refusal: bool = False


# ===========================================================================
# Failure Contract
# ===========================================================================

class LLMFailureReason(str, Enum):
    """
    Enumerates all allowed failure conditions.
    No other failure modes are permitted.
    """

    TIMEOUT = "timeout"
    MALFORMED_OUTPUT = "malformed_output"
    EMPTY_RESPONSE = "empty_response"
    REFUSED = "refused"
    INTERNAL_ERROR = "internal_error"


@dataclass(frozen=True)
class LLMExecutionFailure:
    """
    Structured failure returned instead of output when execution fails.

    RULES:
    • reason must be one of the enumerated failure reasons
    • message is INTERNAL ONLY and never user-facing
    """

    reason: LLMFailureReason
    message: Optional[str] = None


# ===========================================================================
# Abstract Result Wrapper
# ===========================================================================

@dataclass(frozen=True)
class LLMExecutionResult:
    """
    Canonical wrapper returned to the caller.

    Exactly ONE of:
    • output
    • failure

    must be populated.
    """

    output: Optional[LLMExecutionOutput] = None
    failure: Optional[LLMExecutionFailure] = None

    def is_success(self) -> bool:
        return self.output is not None

    def is_failure(self) -> bool:
        return self.failure is not None


# ===========================================================================
# Contract Validation Helpers
# ===========================================================================

def validate_execution_input(execution_input: LLMExecutionInput) -> None:
    """
    Enforce input contract correctness before transport execution.

    Raises ValueError when the caller supplies an invalid execution contract.
    """

    if not isinstance(execution_input, LLMExecutionInput):
        raise ValueError("execution_input must be an LLMExecutionInput.")

    if not isinstance(execution_input.user_query, str):
        raise ValueError("LLMExecutionInput.user_query must be a string.")

    if not execution_input.user_query.strip():
        raise ValueError("LLMExecutionInput.user_query cannot be empty.")

    if not isinstance(execution_input.mode, LLMExecutionMode):
        raise ValueError("LLMExecutionInput.mode must be an LLMExecutionMode.")

    if (
        execution_input.context is not None
        and not isinstance(execution_input.context, dict)
    ):
        raise ValueError("LLMExecutionInput.context must be a dictionary or None.")

    if not isinstance(execution_input.response_format, LLMResponseFormat):
        raise ValueError(
            "LLMExecutionInput.response_format must be an LLMResponseFormat."
        )

    if (
        execution_input.call_site is not None
        and not isinstance(execution_input.call_site, str)
    ):
        raise ValueError("LLMExecutionInput.call_site must be a string or None.")

    if execution_input.max_new_tokens is not None:
        if (
            isinstance(execution_input.max_new_tokens, bool)
            or not isinstance(execution_input.max_new_tokens, int)
        ):
            raise ValueError(
                "LLMExecutionInput.max_new_tokens must be an integer or None."
            )

        if execution_input.max_new_tokens < 1:
            raise ValueError(
                "LLMExecutionInput.max_new_tokens must be greater than zero."
            )

    if not isinstance(execution_input.runtime_profile, LLMRuntimeProfile):
        raise ValueError(
            "LLMExecutionInput.runtime_profile must be an LLMRuntimeProfile."
        )

    if execution_input.timeout_seconds is not None:
        if (
            isinstance(execution_input.timeout_seconds, bool)
            or not isinstance(execution_input.timeout_seconds, int)
        ):
            raise ValueError(
                "LLMExecutionInput.timeout_seconds must be an integer or None."
            )

        if execution_input.timeout_seconds < 1:
            raise ValueError(
                "LLMExecutionInput.timeout_seconds must be greater than zero."
            )


def validate_execution_result(result: LLMExecutionResult) -> None:
    """
    Enforce result contract correctness at runtime.

    Raises ValueError if contract is violated.
    """

    if result.output and result.failure:
        raise ValueError("LLMExecutionResult cannot contain both output and failure.")

    if not result.output and not result.failure:
        raise ValueError("LLMExecutionResult must contain either output or failure.")

    if result.output:
        if not isinstance(result.output.text, str):
            raise ValueError("LLMExecutionOutput.text must be a string.")

        if result.output.confidence not in {"low", "medium", "high"}:
            raise ValueError("LLMExecutionOutput.confidence must be low|medium|high.")

        if not isinstance(result.output.citations, list):
            raise ValueError("LLMExecutionOutput.citations must be a list.")

    if result.failure:
        if not isinstance(result.failure.reason, LLMFailureReason):
            raise ValueError("Invalid LLMFailureReason.")
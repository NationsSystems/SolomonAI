# ---------------------------------------------------------------------------
# FILE: llm_executor.py
# DIRECTORY: solomon_core/llm/
# ---------------------------------------------------------------------------
# LLM Executor
#
# PURPOSE:
#   Execute governed LLM requests through the configured SIS boundary, with
#   direct Transformers/Torch execution reserved for the SIS-owned local
#   runtime or an explicit compatibility mode.
#
# AUTHORITY CONTRACT:
#   This module does not route, classify, decide workflow, or interpret BEI
#   facts. It only executes the already-authorized LLM spoke request and
#   returns contract-shaped output or failure.
#
# CAPACITY CONTRACT:
#   SIS owns the bounded local-model execution gate when SIS is enabled.
#   Interactive human-facing work has admission precedence over queued
#   background intelligence work. Application callers cross the SIS transport
#   boundary and never own the heavy model lifecycle.
# ---------------------------------------------------------------------------

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError
import threading
import time
from typing import Callable

from config import settings
from solomon_core.intelligence_service.intelligence_service_client import (
    execute_llm_via_intelligence_service,
)
from solomon_core.logger import get_logger
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionFailure,
    LLMExecutionInput,
    LLMExecutionOutput,
    LLMExecutionResult,
    LLMFailureReason,
    LLMResponseFormat,
    LLMRuntimeProfile,
    validate_execution_input,
    validate_execution_result,
)

from .direct_model_runner import (
    DirectModelResult,
    run_direct_generation,
    warm_direct_model,
    warm_direct_runtime_profile,
)
from .llm_prompting import inject_document_grounding
from .llm_transport import (
    LLM_DIRECT_PROOF_LOGGING,
    build_transport_proof,
    select_backend,
    select_local_runtime_backend,
    select_timeout_seconds,
)

logger = get_logger("llm_executor")

_HOME_JSON_CALL_SITES = frozenset({
    "solomon_home_assistant",
})

_DIRECT_MODEL_THREAD_PREFIX = "solomon_direct_llm"
_DIRECT_MODEL_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix=_DIRECT_MODEL_THREAD_PREFIX,
)


def _run_on_direct_model_worker(
    function,
    *args,
    **kwargs,
):
    """Run direct-model work on one persistent process-local worker."""

    current_thread_name = threading.current_thread().name

    if current_thread_name.startswith(
        _DIRECT_MODEL_THREAD_PREFIX
    ):
        return function(
            *args,
            **kwargs,
        )

    future = _DIRECT_MODEL_EXECUTOR.submit(
        function,
        *args,
        **kwargs,
    )
    return future.result()


def warm_direct_model_worker(
    *,
    call_site: str = "solomon_boot_warmup",
):
    """Load and prime the direct model on its persistent inference worker."""

    logger.info(
        "[LLM][DIRECT_WORKER_WARMUP] "
        "call_site=%s",
        call_site,
    )

    return _run_on_direct_model_worker(
        warm_direct_model,
        call_site=call_site,
    )


def warm_direct_runtime_profile_worker(
    *,
    call_site: str,
    runtime_profile: str,
    max_new_tokens: int,
    warmup_prompt: str | None = None,
    target_input_tokens: int | None = None,
    streaming: bool = False,
    request_class: str = "background",
):
    """Prime one runtime shape through the shared priority-aware capacity gate."""

    normalized_class = _normalize_llm_request_class(request_class)
    logger.info(
        "[LLM][DIRECT_RUNTIME_PROFILE_WARMUP] "
        "call_site=%s runtime_profile=%s "
        "max_new_tokens=%s target_input_tokens=%s "
        "streaming=%s request_class=%s",
        call_site,
        runtime_profile,
        max_new_tokens,
        target_input_tokens,
        streaming,
        normalized_class,
    )

    admitted, admission_outcome, _wait_ms = _acquire_llm_capacity(
        call_site,
        request_class=normalized_class,
    )
    if not admitted:
        return DirectModelResult(
            ok=False,
            text="",
            proof=build_transport_proof(call_site),
            error=(
                "Runtime-profile warmup could not acquire model capacity: "
                f"{admission_outcome}."
            ),
        )

    try:
        return _run_on_direct_model_worker(
            warm_direct_runtime_profile,
            call_site=call_site,
            runtime_profile=runtime_profile,
            max_new_tokens=max_new_tokens,
            warmup_prompt=warmup_prompt,
            target_input_tokens=target_input_tokens,
            streaming=streaming,
        )
    finally:
        _release_llm_capacity(call_site)


# ---------------------------------------------------------------------------
# Shared LLM Capacity Gate
# ---------------------------------------------------------------------------

_LLM_MAX_CONCURRENT_REQUESTS = max(
    1,
    int(
        getattr(
            settings,
            "LLM_MAX_CONCURRENT_REQUESTS",
            1,
        )
    ),
)

_LLM_REQUEST_QUEUE_LIMIT = max(
    0,
    int(
        getattr(
            settings,
            "LLM_REQUEST_QUEUE_LIMIT",
            32,
        )
    ),
)

_LLM_REQUEST_QUEUE_TIMEOUT_SECONDS = max(
    1,
    int(
        getattr(
            settings,
            "LLM_REQUEST_QUEUE_TIMEOUT_SECONDS",
            60,
        )
    ),
)

_LLM_CAPACITY_CONDITION = threading.Condition()
_LLM_ACTIVE_REQUESTS = 0
_LLM_WAITING_REQUESTS = 0
_LLM_WAITING_INTERACTIVE_REQUESTS = 0
_LLM_WAITING_BACKGROUND_REQUESTS = 0

_LLM_REQUEST_CLASS_INTERACTIVE = "interactive"
_LLM_REQUEST_CLASS_BACKGROUND = "background"
_LLM_REQUEST_CLASSES = frozenset({
    _LLM_REQUEST_CLASS_INTERACTIVE,
    _LLM_REQUEST_CLASS_BACKGROUND,
})


def _normalize_llm_request_class(value: str | None) -> str:
    """Return one supported local-runtime scheduling class."""

    normalized = str(value or _LLM_REQUEST_CLASS_INTERACTIVE).strip().lower()

    if normalized not in _LLM_REQUEST_CLASSES:
        raise ValueError(
            f"Unsupported LLM request class: {normalized!r}."
        )

    return normalized


def _can_admit_llm_request(request_class: str) -> bool:
    """Return whether one caller may own heavy-compute capacity now."""

    if _LLM_ACTIVE_REQUESTS >= _LLM_MAX_CONCURRENT_REQUESTS:
        return False

    if (
        request_class == _LLM_REQUEST_CLASS_BACKGROUND
        and _LLM_WAITING_INTERACTIVE_REQUESTS > 0
    ):
        return False

    return True


def get_llm_capacity_snapshot() -> dict[str, int]:
    """
    Return the current process-local LLM capacity state.

    This read-only snapshot may be used by health and metrics surfaces.
    It does not grant execution authority or mutate queue state.
    """

    with _LLM_CAPACITY_CONDITION:
        return {
            "active_requests": _LLM_ACTIVE_REQUESTS,
            "waiting_requests": _LLM_WAITING_REQUESTS,
            "waiting_interactive_requests": (
                _LLM_WAITING_INTERACTIVE_REQUESTS
            ),
            "waiting_background_requests": (
                _LLM_WAITING_BACKGROUND_REQUESTS
            ),
            "max_concurrent_requests": (
                _LLM_MAX_CONCURRENT_REQUESTS
            ),
            "queue_limit": _LLM_REQUEST_QUEUE_LIMIT,
            "queue_limit_per_class": _LLM_REQUEST_QUEUE_LIMIT,
            "queue_timeout_seconds": (
                _LLM_REQUEST_QUEUE_TIMEOUT_SECONDS
            ),
        }


def _acquire_llm_capacity(
    call_site: str,
    *,
    request_class: str = _LLM_REQUEST_CLASS_INTERACTIVE,
) -> tuple[bool, str, int]:
    """
    Reserve one local-model execution slot.

    Interactive work may move ahead of queued background work. Background
    callers are admitted only when capacity is free and no interactive caller
    is waiting. The currently executing bounded unit is never forcibly
    preempted.

    Returns:
        admitted:
            True when the caller owns an execution slot.
        outcome:
            admitted, admitted_after_wait, queue_full, or queue_timeout.
        wait_ms:
            Time spent waiting before admission or rejection.
    """

    global _LLM_ACTIVE_REQUESTS
    global _LLM_WAITING_REQUESTS
    global _LLM_WAITING_INTERACTIVE_REQUESTS
    global _LLM_WAITING_BACKGROUND_REQUESTS

    normalized_class = _normalize_llm_request_class(request_class)
    wait_started = time.monotonic()

    with _LLM_CAPACITY_CONDITION:
        if _can_admit_llm_request(normalized_class):
            _LLM_ACTIVE_REQUESTS += 1

            logger.debug(
                "[LLM][CAPACITY_ADMITTED] call_site=%s request_class=%s "
                "active=%s waiting=%s max_concurrent=%s",
                call_site,
                normalized_class,
                _LLM_ACTIVE_REQUESTS,
                _LLM_WAITING_REQUESTS,
                _LLM_MAX_CONCURRENT_REQUESTS,
            )

            return True, "admitted", 0

        waiting_for_class = (
            _LLM_WAITING_INTERACTIVE_REQUESTS
            if normalized_class == _LLM_REQUEST_CLASS_INTERACTIVE
            else _LLM_WAITING_BACKGROUND_REQUESTS
        )

        if waiting_for_class >= _LLM_REQUEST_QUEUE_LIMIT:
            wait_ms = int(
                (time.monotonic() - wait_started) * 1000
            )

            logger.warning(
                "[LLM][CAPACITY_REJECTED] call_site=%s request_class=%s "
                "reason=queue_full active=%s waiting=%s "
                "waiting_for_class=%s max_concurrent=%s "
                "queue_limit_per_class=%s",
                call_site,
                normalized_class,
                _LLM_ACTIVE_REQUESTS,
                _LLM_WAITING_REQUESTS,
                waiting_for_class,
                _LLM_MAX_CONCURRENT_REQUESTS,
                _LLM_REQUEST_QUEUE_LIMIT,
            )

            return False, "queue_full", wait_ms

        _LLM_WAITING_REQUESTS += 1

        if normalized_class == _LLM_REQUEST_CLASS_INTERACTIVE:
            _LLM_WAITING_INTERACTIVE_REQUESTS += 1
        else:
            _LLM_WAITING_BACKGROUND_REQUESTS += 1

        logger.info(
            "[LLM][CAPACITY_QUEUED] call_site=%s request_class=%s "
            "active=%s waiting=%s waiting_interactive=%s "
            "waiting_background=%s max_concurrent=%s queue_limit=%s "
            "timeout=%s",
            call_site,
            normalized_class,
            _LLM_ACTIVE_REQUESTS,
            _LLM_WAITING_REQUESTS,
            _LLM_WAITING_INTERACTIVE_REQUESTS,
            _LLM_WAITING_BACKGROUND_REQUESTS,
            _LLM_MAX_CONCURRENT_REQUESTS,
            _LLM_REQUEST_QUEUE_LIMIT,
            _LLM_REQUEST_QUEUE_TIMEOUT_SECONDS,
        )

        deadline = wait_started + _LLM_REQUEST_QUEUE_TIMEOUT_SECONDS

        try:
            while not _can_admit_llm_request(normalized_class):
                remaining_seconds = deadline - time.monotonic()

                if remaining_seconds <= 0:
                    wait_ms = int(
                        (time.monotonic() - wait_started) * 1000
                    )

                    logger.warning(
                        "[LLM][CAPACITY_REJECTED] call_site=%s "
                        "request_class=%s reason=queue_timeout wait_ms=%s "
                        "active=%s waiting=%s max_concurrent=%s",
                        call_site,
                        normalized_class,
                        wait_ms,
                        _LLM_ACTIVE_REQUESTS,
                        _LLM_WAITING_REQUESTS,
                        _LLM_MAX_CONCURRENT_REQUESTS,
                    )

                    return False, "queue_timeout", wait_ms

                _LLM_CAPACITY_CONDITION.wait(
                    timeout=remaining_seconds
                )

            _LLM_ACTIVE_REQUESTS += 1

            wait_ms = int(
                (time.monotonic() - wait_started) * 1000
            )

            logger.info(
                "[LLM][CAPACITY_ADMITTED] call_site=%s request_class=%s "
                "outcome=after_wait wait_ms=%s active=%s waiting=%s "
                "max_concurrent=%s",
                call_site,
                normalized_class,
                wait_ms,
                _LLM_ACTIVE_REQUESTS,
                _LLM_WAITING_REQUESTS,
                _LLM_MAX_CONCURRENT_REQUESTS,
            )

            return True, "admitted_after_wait", wait_ms
        finally:
            _LLM_WAITING_REQUESTS = max(
                0,
                _LLM_WAITING_REQUESTS - 1,
            )

            if normalized_class == _LLM_REQUEST_CLASS_INTERACTIVE:
                _LLM_WAITING_INTERACTIVE_REQUESTS = max(
                    0,
                    _LLM_WAITING_INTERACTIVE_REQUESTS - 1,
                )
            else:
                _LLM_WAITING_BACKGROUND_REQUESTS = max(
                    0,
                    _LLM_WAITING_BACKGROUND_REQUESTS - 1,
                )


def _release_llm_capacity(
    call_site: str,
) -> None:
    """Release one model-execution slot and wake a waiting caller."""

    global _LLM_ACTIVE_REQUESTS

    with _LLM_CAPACITY_CONDITION:
        _LLM_ACTIVE_REQUESTS = max(
            0,
            _LLM_ACTIVE_REQUESTS - 1,
        )

        logger.debug(
            "[LLM][CAPACITY_RELEASED] call_site=%s "
            "active=%s waiting=%s max_concurrent=%s",
            call_site,
            _LLM_ACTIVE_REQUESTS,
            _LLM_WAITING_REQUESTS,
            _LLM_MAX_CONCURRENT_REQUESTS,
        )

        _LLM_CAPACITY_CONDITION.notify_all()


def _capacity_failure(
    outcome: str,
) -> LLMExecutionResult:
    """Return a stable execution failure for capacity rejection."""

    if outcome == "queue_timeout":
        return _failure(
            LLMFailureReason.INTERNAL_ERROR,
            (
                "The SolomonAI execution queue timed out "
                "before model capacity became available."
            ),
        )

    return _failure(
        LLMFailureReason.INTERNAL_ERROR,
        (
            "SolomonAI is currently at execution capacity. "
            "Please retry shortly."
        ),
    )


# ---------------------------------------------------------------------------
# Result Helpers
# ---------------------------------------------------------------------------

def _validated_result(
    result: LLMExecutionResult,
) -> LLMExecutionResult:
    validate_execution_result(result)
    return result


def _failure(
    reason: LLMFailureReason,
    message: str,
) -> LLMExecutionResult:
    return _validated_result(
        LLMExecutionResult(
            failure=LLMExecutionFailure(
                reason=reason,
                message=message,
            )
        )
    )


def _resolve_response_format(
    input_packet: LLMExecutionInput,
) -> LLMResponseFormat:
    value = getattr(
        input_packet,
        "response_format",
        LLMResponseFormat.TEXT,
    )

    if isinstance(value, LLMResponseFormat):
        return value

    try:
        return LLMResponseFormat(value)
    except Exception:
        return LLMResponseFormat.TEXT


def _resolve_effective_response_format(
    *,
    input_packet: LLMExecutionInput,
    call_site: str,
) -> LLMResponseFormat:
    requested_format = _resolve_response_format(
        input_packet
    )

    if call_site in _HOME_JSON_CALL_SITES:
        return LLMResponseFormat.JSON_OBJECT

    return requested_format


def _mode_value(
    input_packet: LLMExecutionInput,
) -> str:
    mode = getattr(input_packet, "mode", "")

    if hasattr(mode, "value"):
        return str(mode.value)

    return str(mode or "unknown")


def _resolve_call_site(
    input_packet: LLMExecutionInput,
) -> str:
    explicit = getattr(
        input_packet,
        "call_site",
        None,
    )

    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()

    mode = _mode_value(input_packet)
    return f"llm_executor:{mode}"


def _resolve_max_new_tokens(
    input_packet: LLMExecutionInput,
) -> int | None:
    """Return the caller-owned generation budget, when one was requested."""

    value = getattr(
        input_packet,
        "max_new_tokens",
        None,
    )

    if value is None:
        return None

    return int(value)


def _resolve_timeout_seconds(
    input_packet: LLMExecutionInput,
) -> int:
    """Return the caller-owned or configured wall-clock timeout."""

    value = getattr(
        input_packet,
        "timeout_seconds",
        None,
    )

    if value is None:
        return max(1, int(select_timeout_seconds()))

    return max(1, int(value))


def _resolve_runtime_profile(
    input_packet: LLMExecutionInput,
) -> LLMRuntimeProfile:
    """
    Return the caller-requested portable runtime profile.

    Older input objects that predate the runtime-profile field retain the
    default execution behavior.
    """

    value = getattr(
        input_packet,
        "runtime_profile",
        LLMRuntimeProfile.DEFAULT,
    )

    if isinstance(value, LLMRuntimeProfile):
        return value

    try:
        return LLMRuntimeProfile(value)
    except Exception:
        return LLMRuntimeProfile.DEFAULT


def _build_output(
    text: str,
) -> LLMExecutionResult:
    return _validated_result(
        LLMExecutionResult(
            output=LLMExecutionOutput(
                text=text,
                confidence="low",
                citations=[],
                refusal=False,
            )
        )
    )


# ---------------------------------------------------------------------------
# Prompt Preparation
# ---------------------------------------------------------------------------

def _prepare_prompt(
    input_packet: LLMExecutionInput,
) -> str:
    raw_prompt = input_packet.user_query or ""
    prompt = raw_prompt.strip()

    if input_packet.context:
        prompt = inject_document_grounding(
            prompt,
            input_packet.context,
        )

    return prompt


# ---------------------------------------------------------------------------
# Direct Model Execution
# ---------------------------------------------------------------------------

def _convert_direct_model_result(
    *,
    result,
    call_site: str,
    runtime_profile: LLMRuntimeProfile,
) -> LLMExecutionResult:
    """Convert a direct-model runtime result into the LLM contract shape."""

    if LLM_DIRECT_PROOF_LOGGING:
        logger.info(
            "[LLM][PROOF] call_site=%s backend=%s "
            "model=%s path=%s direct_available=%s "
            "runtime_profile=%s",
            result.proof.get("call_site"),
            result.proof.get("llm_backend"),
            result.proof.get("model_name"),
            result.proof.get("model_path"),
            result.proof.get(
                "direct_model_available"
            ),
            runtime_profile.value,
        )

    if not result.ok:
        error_message = str(
            getattr(
                result,
                "error",
                "",
            )
            or (
                "Direct custom model execution "
                "failed."
            )
        ).strip()

        logger.error(
            "[LLM][DIRECT_EXECUTION_FAILED] "
            "call_site=%s runtime_profile=%s error=%s",
            call_site,
            runtime_profile.value,
            error_message,
        )

        return _failure(
            LLMFailureReason.INTERNAL_ERROR,
            error_message,
        )

    return _build_output(result.text)


def _release_capacity_after_timeout(
    *,
    future,
    call_site: str,
) -> None:
    """Release capacity when a timed-out direct-model call actually completes."""

    try:
        try:
            future.result()
        except Exception as exc:
            logger.warning(
                "[LLM][TIMEOUT_LATE_COMPLETION_ERROR] "
                "call_site=%s error=%s",
                call_site,
                exc,
            )
        else:
            logger.info(
                "[LLM][TIMEOUT_LATE_COMPLETION] "
                "call_site=%s",
                call_site,
            )
    finally:
        _release_llm_capacity(call_site)


def _execute_direct_model(
    *,
    prompt: str,
    response_format: LLMResponseFormat,
    call_site: str,
    max_new_tokens: int | None,
    runtime_profile: LLMRuntimeProfile,
    timeout_seconds: int,
    stream_callback: (
        Callable[[str], None] | None
    ) = None,
) -> tuple[LLMExecutionResult, bool]:
    """Execute the direct model and report whether capacity can release now."""

    current_thread_name = threading.current_thread().name

    if current_thread_name.startswith(
        _DIRECT_MODEL_THREAD_PREFIX
    ):
        result = run_direct_generation(
            prompt=prompt,
            call_site=call_site,
            response_format=response_format.value,
            max_new_tokens=max_new_tokens,
            runtime_profile=runtime_profile.value,
            stream_callback=stream_callback,
        )
        return (
            _convert_direct_model_result(
                result=result,
                call_site=call_site,
                runtime_profile=runtime_profile,
            ),
            True,
        )

    future = _DIRECT_MODEL_EXECUTOR.submit(
        run_direct_generation,
        prompt=prompt,
        call_site=call_site,
        response_format=response_format.value,
        max_new_tokens=max_new_tokens,
        runtime_profile=runtime_profile.value,
        stream_callback=stream_callback,
    )

    try:
        result = future.result(
            timeout=timeout_seconds,
        )
    except FutureTimeoutError:
        logger.warning(
            "[LLM][TIMEOUT] call_site=%s "
            "timeout_seconds=%s max_new_tokens=%s "
            "runtime_profile=%s",
            call_site,
            timeout_seconds,
            max_new_tokens,
            runtime_profile.value,
        )
        future.add_done_callback(
            lambda completed_future: _release_capacity_after_timeout(
                future=completed_future,
                call_site=call_site,
            )
        )
        return (
            _failure(
                LLMFailureReason.TIMEOUT,
                (
                    "Direct custom model execution exceeded "
                    f"the {timeout_seconds}-second wall-clock budget."
                ),
            ),
            False,
        )

    return (
        _convert_direct_model_result(
            result=result,
            call_site=call_site,
            runtime_profile=runtime_profile,
        ),
        True,
    )


# ---------------------------------------------------------------------------
# LLM Execution Spoke
# ---------------------------------------------------------------------------

def execute_llm_on_local_runtime(
    input_packet: LLMExecutionInput,
    stream_callback: (
        Callable[[str], None] | None
    ) = None,
    *,
    request_class: str = _LLM_REQUEST_CLASS_INTERACTIVE,
) -> LLMExecutionResult:
    try:
        try:
            validate_execution_input(
                input_packet
            )
        except ValueError as exc:
            return _failure(
                LLMFailureReason.MALFORMED_OUTPUT,
                str(exc),
            )

        prompt = _prepare_prompt(input_packet)

        if not prompt:
            return _failure(
                LLMFailureReason.EMPTY_RESPONSE,
                "LLM prompt was empty.",
            )

        backend = select_local_runtime_backend()
        call_site = _resolve_call_site(input_packet)
        max_new_tokens = _resolve_max_new_tokens(
            input_packet
        )
        runtime_profile = _resolve_runtime_profile(
            input_packet
        )
        timeout_seconds = _resolve_timeout_seconds(
            input_packet
        )

        response_format = (
            _resolve_effective_response_format(
                input_packet=input_packet,
                call_site=call_site,
            )
        )

        if backend != "transformers_direct":
            return _failure(
                LLMFailureReason.INTERNAL_ERROR,
                "The proprietary direct LLM runtime is unavailable.",
            )

        admitted, admission_outcome, wait_ms = (
            _acquire_llm_capacity(
                call_site,
                request_class=request_class,
            )
        )

        if not admitted:
            return _capacity_failure(
                admission_outcome
            )

        release_capacity_now = True

        try:
            if LLM_DIRECT_PROOF_LOGGING:
                proof = build_transport_proof(
                    call_site,
                    local_runtime=True,
                )

                logger.info(
                    "[LLM][BACKEND_SELECTED] "
                    "call_site=%s backend=%s model=%s "
                    "path=%s capacity_wait_ms=%s "
                    "max_new_tokens=%s runtime_profile=%s "
                    "timeout_seconds=%s",
                    proof.get("call_site"),
                    proof.get("llm_backend"),
                    proof.get("model_name"),
                    proof.get("model_path"),
                    wait_ms,
                    max_new_tokens,
                    runtime_profile.value,
                    timeout_seconds,
                )

            result, release_capacity_now = _execute_direct_model(
                prompt=prompt,
                response_format=response_format,
                call_site=call_site,
                max_new_tokens=max_new_tokens,
                runtime_profile=runtime_profile,
                timeout_seconds=timeout_seconds,
                stream_callback=stream_callback,
            )
            return result
        finally:
            if release_capacity_now:
                _release_llm_capacity(call_site)

    except Exception as exc:
        logger.exception(
            "[LLM][FAIL] unexpected exception"
        )

        return _failure(
            LLMFailureReason.INTERNAL_ERROR,
            str(exc),
        )

# ---------------------------------------------------------------------------
# Public LLM Execution Boundary
# ---------------------------------------------------------------------------

def execute_llm(
    input_packet: LLMExecutionInput,
    stream_callback: (
        Callable[[str], None] | None
    ) = None,
    *,
    priority: str = "P0",
    request_id: str | None = None,
    fairness_bucket: str | None = None,
) -> LLMExecutionResult:
    """Execute through SIS or the explicit local compatibility path."""

    try:
        validate_execution_input(input_packet)
    except ValueError as exc:
        return _failure(
            LLMFailureReason.MALFORMED_OUTPUT,
            str(exc),
        )

    backend = select_backend()

    if backend == "sis":
        proof = build_transport_proof(
            _resolve_call_site(input_packet)
        )
        logger.info(
            "[LLM][BACKEND_SELECTED] call_site=%s backend=%s endpoint=%s",
            proof.get("call_site"),
            proof.get("llm_backend"),
            proof.get("sis_base_url"),
        )
        return execute_llm_via_intelligence_service(
            input_packet,
            stream_callback=stream_callback,
            priority=priority,
            request_id=request_id,
            fairness_bucket=fairness_bucket,
        )

    if backend == "transformers_direct":
        normalized_priority = str(priority or "P0").strip().upper()
        return execute_llm_on_local_runtime(
            input_packet,
            stream_callback=stream_callback,
            request_class=(
                "background"
                if normalized_priority in {"P2", "P3"}
                else "interactive"
            ),
        )

    return _failure(
        LLMFailureReason.INTERNAL_ERROR,
        "No Solomon LLM execution backend is available.",
    )


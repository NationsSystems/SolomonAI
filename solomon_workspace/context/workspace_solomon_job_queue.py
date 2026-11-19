# -------------------------------------------------------------------
# FILE: workspace_solomon_job_queue.py
# DIRECTORY: solomon_workspace/context/
# -------------------------------------------------------------------
# Bounded background job queue for SolomonAI workspace requests.
#
# PURPOSE:
#   Move expensive source preview and LLM execution work out of Flask
#   request threads while preserving server-owned admission, ownership,
#   result state, and capacity limits.
#
# CONTRACT:
#   - Jobs are process-local because the embedded model is process-local.
#   - The queue is bounded before submission.
#   - Each job belongs to one authenticated user.
#   - Cross-user job reads are rejected.
#   - Completed and failed jobs expire automatically.
#   - Direct-model loading, cache priming, and generation are owned by the
#     same inference worker thread.
#   - This module does not perform routing or source authorization.
# -------------------------------------------------------------------

from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    TimeoutError as FutureTimeoutError,
)
from dataclasses import dataclass
import threading
import time
import uuid
from typing import Any, Callable, Dict, Optional

from config import settings
from solomon_core.logger import get_logger


logger = get_logger("workspace_solomon_job_queue")

JOB_STATUS_QUEUED = "queued"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETED = "completed"
JOB_STATUS_FAILED = "failed"

_TERMINAL_STATUSES = frozenset({
    JOB_STATUS_COMPLETED,
    JOB_STATUS_FAILED,
})

_MAX_WORKERS = max(
    1,
    int(
        getattr(
            settings,
            "LLM_MAX_CONCURRENT_REQUESTS",
            1,
        )
    ),
)

_QUEUE_LIMIT = max(
    0,
    int(
        getattr(
            settings,
            "LLM_REQUEST_QUEUE_LIMIT",
            32,
        )
    ),
)

_MAX_IN_FLIGHT_JOBS = max(
    1,
    _MAX_WORKERS + _QUEUE_LIMIT,
)

_RESULT_TTL_SECONDS = max(
    300,
    int(
        getattr(
            settings,
            "LLM_REQUEST_QUEUE_TIMEOUT_SECONDS",
            60,
        )
    ) * 10,
)

_WORKSPACE_SOLOMON_WARMUP_TIMEOUT_SECONDS = 180.0

_EXECUTOR = ThreadPoolExecutor(
    max_workers=_MAX_WORKERS,
    thread_name_prefix="solomon_workspace_ai",
)

_WORKER_RUNTIME_LOCK = threading.RLock()
_WORKER_RUNTIME_STATE: Dict[int, Dict[str, Any]] = {}

_ADMISSION_GATE = threading.BoundedSemaphore(
    value=_MAX_IN_FLIGHT_JOBS,
)

_JOBS_LOCK = threading.RLock()
_JOBS_CONDITION = threading.Condition(_JOBS_LOCK)
_JOBS: Dict[str, "_WorkspaceSolomonJob"] = {}


@dataclass
class _WorkspaceSolomonJob:
    job_id: str
    user_id: int
    request_id: str
    status: str
    created_at: float
    updated_at: float
    event_id: int = 1
    result: Optional[Dict[str, Any]] = None
    error: str = ""


def _get_workspace_solomon_runtime_contract() -> Dict[str, Any]:
    """
    Resolve the worker-owned direct-model contract lazily.

    Boot initialization intentionally performs only the canonical bounded
    model prime. Production request profiles remain request-owned and are not
    synthesized or generated during application startup.
    """

    from solomon_workspace.context.workspace_solomon_llm import (
        WORKSPACE_SOLOMON_LLM_CALL_SITE,
        WORKSPACE_SOLOMON_LLM_MAX_NEW_TOKENS,
    )

    return {
        "call_site": WORKSPACE_SOLOMON_LLM_CALL_SITE,
        "runtime_profile": "model_only",
        "max_new_tokens": max(
            int(value)
            for value in WORKSPACE_SOLOMON_LLM_MAX_NEW_TOKENS.values()
        ),
        "warmup_shape_count": 0,
    }


def _initialize_workspace_solomon_inference_worker() -> Dict[str, Any]:
    """
    Load and perform one bounded model prime on the inference worker.

    The previous startup path executed four production-sized synthetic
    generations. Those calls incurred real generation and cache-specialization
    cost during boot. Worker initialization now performs only the canonical
    one-token direct-model prime. Production request profiles are exercised by
    real requests rather than by oversized startup simulations.
    """

    worker_thread_id = threading.get_ident()
    worker_thread_name = threading.current_thread().name

    with _WORKER_RUNTIME_LOCK:
        existing_state = _WORKER_RUNTIME_STATE.get(
            worker_thread_id
        )

        if (
            existing_state
            and existing_state.get("ready")
        ):
            return dict(existing_state)

    runtime_contract = (
        _get_workspace_solomon_runtime_contract()
    )

    from solomon_core.llm.direct_model_runner import (
        warm_direct_model,
    )

    logger.info(
        "[WORKSPACE_SOLOMON_WORKER][WARMUP_START] "
        "worker_thread=%s worker_thread_id=%s "
        "call_site=%s mode=%s",
        worker_thread_name,
        worker_thread_id,
        runtime_contract["call_site"],
        runtime_contract["runtime_profile"],
    )

    started_at = time.monotonic()
    result = warm_direct_model(
        call_site=(
            f"{runtime_contract['call_site']}"
            "_worker_warmup"
        )
    )
    elapsed_ms = int(
        (time.monotonic() - started_at) * 1000
    )

    if not result.ok:
        error_message = (
            result.error
            or "Unknown inference-worker warmup failure."
        )
        failed_state = {
            "ready": False,
            "worker_thread": worker_thread_name,
            "worker_thread_id": worker_thread_id,
            "call_site": runtime_contract["call_site"],
            "runtime_profile": runtime_contract[
                "runtime_profile"
            ],
            "max_new_tokens": runtime_contract[
                "max_new_tokens"
            ],
            "warmup_shape_count": 0,
            "completed_warmup_shapes": (),
            "elapsed_ms": elapsed_ms,
            "error": error_message,
        }

        with _WORKER_RUNTIME_LOCK:
            _WORKER_RUNTIME_STATE[
                worker_thread_id
            ] = failed_state

        logger.error(
            "[WORKSPACE_SOLOMON_WORKER][WARMUP_FAILED] "
            "worker_thread=%s worker_thread_id=%s "
            "mode=%s elapsed_ms=%s error=%s",
            worker_thread_name,
            worker_thread_id,
            runtime_contract["runtime_profile"],
            elapsed_ms,
            error_message,
        )

        raise RuntimeError(
            "SolomonAI inference-worker warmup failed: "
            f"{error_message}"
        )

    state = {
        "ready": True,
        "worker_thread": worker_thread_name,
        "worker_thread_id": worker_thread_id,
        "call_site": runtime_contract["call_site"],
        "runtime_profile": runtime_contract[
            "runtime_profile"
        ],
        "max_new_tokens": runtime_contract[
            "max_new_tokens"
        ],
        "warmup_shape_count": 0,
        "completed_warmup_shapes": (),
        "elapsed_ms": elapsed_ms,
        "error": "",
    }

    with _WORKER_RUNTIME_LOCK:
        _WORKER_RUNTIME_STATE[
            worker_thread_id
        ] = state

    logger.info(
        "[WORKSPACE_SOLOMON_WORKER][WARMUP_READY] "
        "worker_thread=%s worker_thread_id=%s "
        "mode=%s elapsed_ms=%s",
        worker_thread_name,
        worker_thread_id,
        runtime_contract["runtime_profile"],
        elapsed_ms,
    )

    return dict(state)


def warm_workspace_solomon_inference_worker(
    *,
    timeout_seconds: float = _WORKSPACE_SOLOMON_WARMUP_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """
    Load and perform one bounded model prime before user traffic.

    The task is submitted to the same executor that later runs SolomonAI
    jobs, preserving worker ownership without running synthetic production
    generations during application startup.
    """

    try:
        clean_timeout_seconds = max(
            1.0,
            float(timeout_seconds),
        )
    except (TypeError, ValueError):
        clean_timeout_seconds = _WORKSPACE_SOLOMON_WARMUP_TIMEOUT_SECONDS

    future = _EXECUTOR.submit(
        _initialize_workspace_solomon_inference_worker
    )

    try:
        state = future.result(
            timeout=clean_timeout_seconds
        )
    except FutureTimeoutError as exc:
        logger.error(
            "[WORKSPACE_SOLOMON_WORKER][WARMUP_TIMEOUT] "
            "timeout_seconds=%s",
            clean_timeout_seconds,
        )
        raise RuntimeError(
            "SolomonAI inference-worker warmup timed out."
        ) from exc
    except Exception:
        logger.exception(
            "[WORKSPACE_SOLOMON_WORKER][WARMUP_ERROR]"
        )
        raise

    return (
        dict(state)
        if isinstance(state, dict)
        else {}
    )


def _clean_user_id(value: Any) -> int:
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _clean_request_id(value: Any) -> str:
    clean_value = str(value or "").strip()
    return clean_value or "untracked"


def _serialize_job(
    job: _WorkspaceSolomonJob,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "job_id": job.job_id,
        "status": job.status,
        "request_id": job.request_id,
        "event_id": job.event_id,
    }

    if job.status == JOB_STATUS_COMPLETED:
        payload["result"] = job.result or {}

    if job.status == JOB_STATUS_FAILED:
        payload["error"] = (
            job.error
            or "SolomonAI could not complete this request."
        )

    return payload


def _cleanup_expired_jobs_locked(
    now: Optional[float] = None,
) -> int:
    current_time = (
        float(now)
        if now is not None
        else time.time()
    )
    expired_job_ids = []

    for job_id, job in _JOBS.items():
        if job.status not in _TERMINAL_STATUSES:
            continue

        if (
            current_time - job.updated_at
            < _RESULT_TTL_SECONDS
        ):
            continue

        expired_job_ids.append(job_id)

    for job_id in expired_job_ids:
        _JOBS.pop(job_id, None)

    if expired_job_ids:
        _JOBS_CONDITION.notify_all()
        logger.debug(
            "[WORKSPACE_SOLOMON_JOB][CLEANUP] "
            "expired_count=%s remaining=%s",
            len(expired_job_ids),
            len(_JOBS),
        )

    return len(expired_job_ids)


def _set_job_running(
    job_id: str,
) -> Optional[_WorkspaceSolomonJob]:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)

        if not job:
            return None

        job.status = JOB_STATUS_RUNNING
        job.updated_at = time.time()
        job.event_id += 1
        _JOBS_CONDITION.notify_all()
        return job


def _set_job_completed(
    job_id: str,
    result: Dict[str, Any],
) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)

        if not job:
            return

        job.status = JOB_STATUS_COMPLETED
        job.result = (
            result
            if isinstance(result, dict)
            else {}
        )
        job.error = ""
        job.updated_at = time.time()
        job.event_id += 1
        _JOBS_CONDITION.notify_all()


def _set_job_failed(
    job_id: str,
    error_message: str,
) -> None:
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)

        if not job:
            return

        job.status = JOB_STATUS_FAILED
        job.result = None
        job.error = (
            str(error_message or "").strip()
            or "SolomonAI could not complete this request."
        )
        job.updated_at = time.time()
        job.event_id += 1
        _JOBS_CONDITION.notify_all()


def _run_workspace_solomon_job(
    *,
    job_id: str,
    task: Callable[[], Dict[str, Any]],
) -> None:
    job = _set_job_running(job_id)

    if not job:
        _ADMISSION_GATE.release()
        return

    logger.info(
        "[WORKSPACE_SOLOMON_JOB][START] "
        "job_id=%s request_id=%s user_id=%s",
        job.job_id,
        job.request_id,
        job.user_id,
    )

    started_at = time.monotonic()

    try:
        worker_state = (
            _initialize_workspace_solomon_inference_worker()
        )

        logger.debug(
            "[WORKSPACE_SOLOMON_JOB][WORKER_READY] "
            "job_id=%s worker_thread=%s "
            "worker_thread_id=%s runtime_profile=%s "
            "max_new_tokens=%s warmup_shape_count=%s",
            job.job_id,
            worker_state.get(
                "worker_thread"
            ),
            worker_state.get(
                "worker_thread_id"
            ),
            worker_state.get(
                "runtime_profile"
            ),
            worker_state.get(
                "max_new_tokens"
            ),
            worker_state.get(
                "warmup_shape_count"
            ),
        )

        result = task()

        if not isinstance(result, dict):
            raise RuntimeError(
                "Workspace SolomonAI job returned "
                "an invalid result payload."
            )

        _set_job_completed(
            job_id,
            result,
        )

        elapsed_ms = int(
            (time.monotonic() - started_at) * 1000
        )

        logger.info(
            "[WORKSPACE_SOLOMON_JOB][COMPLETE] "
            "job_id=%s request_id=%s user_id=%s "
            "elapsed_ms=%s",
            job.job_id,
            job.request_id,
            job.user_id,
            elapsed_ms,
        )
    except Exception as exc:
        _set_job_failed(
            job_id,
            "SolomonAI could not complete this request.",
        )

        logger.exception(
            "[WORKSPACE_SOLOMON_JOB][FAILED] "
            "job_id=%s request_id=%s user_id=%s "
            "error=%s",
            job.job_id,
            job.request_id,
            job.user_id,
            exc,
        )
    finally:
        _ADMISSION_GATE.release()


def submit_workspace_solomon_job(
    *,
    user_id: int,
    request_id: str,
    task: Callable[[], Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Submit one bounded workspace SolomonAI background job.

    The caller must validate user ownership and source authority before
    submitting the task. The callable must not depend on Flask request
    context, session, g, or request objects.
    """

    clean_user_id = _clean_user_id(user_id)
    clean_request_id = _clean_request_id(request_id)

    if clean_user_id <= 0:
        return {
            "accepted": False,
            "error": "invalid_user",
        }

    if not callable(task):
        return {
            "accepted": False,
            "error": "invalid_task",
        }

    with _JOBS_LOCK:
        _cleanup_expired_jobs_locked()

    admitted = _ADMISSION_GATE.acquire(
        blocking=False,
    )

    if not admitted:
        snapshot = (
            get_workspace_solomon_job_capacity_snapshot()
        )

        logger.warning(
            "[WORKSPACE_SOLOMON_JOB][REJECTED] "
            "reason=queue_full request_id=%s user_id=%s "
            "active_or_queued=%s capacity=%s",
            clean_request_id,
            clean_user_id,
            snapshot["in_flight_jobs"],
            snapshot["max_in_flight_jobs"],
        )

        return {
            "accepted": False,
            "error": "queue_full",
            "capacity": snapshot,
        }

    now = time.time()
    job_id = uuid.uuid4().hex

    job = _WorkspaceSolomonJob(
        job_id=job_id,
        user_id=clean_user_id,
        request_id=clean_request_id,
        status=JOB_STATUS_QUEUED,
        created_at=now,
        updated_at=now,
    )

    with _JOBS_CONDITION:
        _JOBS[job_id] = job
        _JOBS_CONDITION.notify_all()

    try:
        _EXECUTOR.submit(
            _run_workspace_solomon_job,
            job_id=job_id,
            task=task,
        )
    except Exception as exc:
        with _JOBS_LOCK:
            _JOBS.pop(job_id, None)

        _ADMISSION_GATE.release()

        logger.exception(
            "[WORKSPACE_SOLOMON_JOB][SUBMIT_FAILED] "
            "request_id=%s user_id=%s error=%s",
            clean_request_id,
            clean_user_id,
            exc,
        )

        return {
            "accepted": False,
            "error": "submission_failed",
        }

    logger.info(
        "[WORKSPACE_SOLOMON_JOB][QUEUED] "
        "job_id=%s request_id=%s user_id=%s",
        job_id,
        clean_request_id,
        clean_user_id,
    )

    return {
        "accepted": True,
        "job": _serialize_job(job),
    }


def get_workspace_solomon_job(
    *,
    user_id: int,
    job_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Read one job only when it belongs to the requesting user.

    Returning None intentionally does not distinguish between an unknown
    job and a job owned by another user.
    """

    clean_user_id = _clean_user_id(user_id)
    clean_job_id = str(job_id or "").strip()

    if clean_user_id <= 0 or not clean_job_id:
        return None

    with _JOBS_LOCK:
        _cleanup_expired_jobs_locked()

        job = _JOBS.get(clean_job_id)

        if not job or job.user_id != clean_user_id:
            return None

        return _serialize_job(job)


def wait_for_workspace_solomon_job_event(
    *,
    user_id: int,
    job_id: str,
    after_event_id: int = 0,
    timeout_seconds: float = 15.0,
) -> Optional[Dict[str, Any]]:
    """
    Wait for one ownership-safe job state event.

    The returned packet contains:
      - changed: True when a newer event is available
      - terminal: True when the job completed or failed
      - job: the same serialized job contract used by polling

    Returning None intentionally does not distinguish an unknown job from
    one owned by another user. A timeout returns the current authorized job
    with changed=False so an SSE route can emit a heartbeat without polling.
    """

    clean_user_id = _clean_user_id(user_id)
    clean_job_id = str(job_id or "").strip()

    try:
        clean_after_event_id = max(
            0,
            int(after_event_id or 0),
        )
    except (TypeError, ValueError):
        clean_after_event_id = 0

    try:
        clean_timeout_seconds = max(
            0.0,
            min(
                float(timeout_seconds),
                30.0,
            ),
        )
    except (TypeError, ValueError):
        clean_timeout_seconds = 15.0

    if clean_user_id <= 0 or not clean_job_id:
        return None

    with _JOBS_CONDITION:
        _cleanup_expired_jobs_locked()

        job = _JOBS.get(clean_job_id)

        if not job or job.user_id != clean_user_id:
            return None

        if (
            job.event_id <= clean_after_event_id
            and job.status not in _TERMINAL_STATUSES
            and clean_timeout_seconds > 0
        ):
            _JOBS_CONDITION.wait_for(
                lambda: (
                    clean_job_id not in _JOBS
                    or _JOBS[clean_job_id].user_id != clean_user_id
                    or _JOBS[clean_job_id].event_id > clean_after_event_id
                    or _JOBS[clean_job_id].status in _TERMINAL_STATUSES
                ),
                timeout=clean_timeout_seconds,
            )

        _cleanup_expired_jobs_locked()
        job = _JOBS.get(clean_job_id)

        if not job or job.user_id != clean_user_id:
            return None

        return {
            "changed": (
                job.event_id > clean_after_event_id
            ),
            "terminal": (
                job.status in _TERMINAL_STATUSES
            ),
            "job": _serialize_job(job),
        }


def get_workspace_solomon_job_capacity_snapshot() -> Dict[str, int]:
    """Return non-authoritative operational queue metrics."""

    with _JOBS_LOCK:
        queued_jobs = 0
        running_jobs = 0

        for job in _JOBS.values():
            if job.status == JOB_STATUS_QUEUED:
                queued_jobs += 1
            elif job.status == JOB_STATUS_RUNNING:
                running_jobs += 1

        with _WORKER_RUNTIME_LOCK:
            ready_workers = sum(
                1
                for state in _WORKER_RUNTIME_STATE.values()
                if state.get("ready")
            )

        return {
            "running_jobs": running_jobs,
            "queued_jobs": queued_jobs,
            "in_flight_jobs": (
                running_jobs + queued_jobs
            ),
            "max_workers": _MAX_WORKERS,
            "ready_workers": ready_workers,
            "queue_limit": _QUEUE_LIMIT,
            "max_in_flight_jobs": (
                _MAX_IN_FLIGHT_JOBS
            ),
            "result_ttl_seconds": (
                _RESULT_TTL_SECONDS
            ),
        }
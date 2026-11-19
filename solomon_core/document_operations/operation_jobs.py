# -------------------------------------------------------------------
# FILE: operation_jobs.py
# DIRECTORY: solomon_core/document_operations/
# -------------------------------------------------------------------
# Generic document operation execution runtime.
#
# Stable commercial path:
# - Execute a document operation in one request.
# - Return one completed result packet.
# - Save completed review artifacts after the runner finishes.
#
# Legacy/future path:
# - Queued jobs remain available for workflows that explicitly need
#   background execution, but the current document-analysis path should
#   complete in one request when possible.
# -------------------------------------------------------------------

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from html import unescape
from queue import Queue
from threading import RLock, Thread
from typing import Any, Callable
import re
import uuid

from solomon_core.document_operations.saved_reviews import (
    save_document_operation_review,
)
from solomon_core.logger import get_logger

logger = get_logger("document_operation_jobs")

_HTML_BREAK_RE = re.compile(r"(?i)<\s*br\s*/?\s*>")
_HTML_BLOCK_RE = re.compile(r"(?i)</\s*(?:div|p|section|article|li|tr|h[1-6])\s*>")
_HTML_TAG_RE = re.compile(r"<[^>]+>")

JOB_STATUS_SUBMITTED = "submitted"
JOB_STATUS_RUNNING = "running"
JOB_STATUS_COMPLETE = "complete"
JOB_STATUS_FAILED = "failed"

_MAX_RETAINED_JOBS = 100

OperationRunner = Callable[[list[dict]], dict]

_JOB_LOCK = RLock()
_JOB_QUEUE: Queue[str] = Queue()
_JOBS: dict[str, "DocumentOperationJob"] = {}
_RUNNERS: dict[str, OperationRunner] = {}
_WORKER_THREAD: Thread | None = None


class DocumentOperationJobError(Exception):
    """Raised when a document operation job cannot be created or read."""

    def __init__(
        self,
        error_code: str,
        user_output: str,
        *,
        status_code: int = 400,
    ):
        super().__init__(user_output)
        self.error_code = error_code
        self.user_output = user_output
        self.status_code = status_code


@dataclass
class DocumentOperationJob:
    """Track one document operation execution."""

    job_id: str
    user_id: int
    request_id: str
    operation_key: str
    operation_label: str
    result_packet_type: str
    documents: list[dict]
    submitted_at: str
    status: str = JOB_STATUS_SUBMITTED
    started_at: str = ""
    finished_at: str = ""
    result_packet: dict | None = None
    error_message: str = ""
    events: list[dict] = field(default_factory=list)


def utc_now_iso() -> str:
    """Return a UTC ISO timestamp."""

    return datetime.now(timezone.utc).isoformat()


def normalize_operation_key(value: str) -> str:
    """Return a normalized operation key."""

    return str(value or "").strip().lower()


def register_document_operation_runner(
    operation_key: str,
    runner: OperationRunner,
) -> None:
    """Register a callable report runner for a document operation key."""

    clean_key = normalize_operation_key(operation_key)

    if not clean_key:
        raise DocumentOperationJobError(
            "DocumentOperationRunnerMissingKey",
            "A document operation runner must have an operation key.",
        )

    if not callable(runner):
        raise DocumentOperationJobError(
            "DocumentOperationRunnerInvalid",
            f"The runner for {clean_key} is not callable.",
        )

    with _JOB_LOCK:
        _RUNNERS[clean_key] = runner


def get_document_operation_runner(operation_key: str) -> OperationRunner | None:
    """Return the registered runner for an operation key."""

    with _JOB_LOCK:
        return _RUNNERS.get(normalize_operation_key(operation_key))


def html_to_plain_text(value: str) -> str:
    """Convert simple report HTML into readable status-panel text."""

    text = str(value or "").strip()

    if not text:
        return ""

    text = _HTML_BREAK_RE.sub("\n", text)
    text = _HTML_BLOCK_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub("", text)
    text = unescape(text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def nested_value(source, path):
    """Read a dotted path from a nested dict."""

    current = source

    for key in str(path or "").split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def normalize_text(value) -> str:
    """Return text suitable for operation result display."""

    if isinstance(value, str):
        return html_to_plain_text(value)

    if isinstance(value, list):
        return "\n\n".join(
            normalize_text(item)
            for item in value
            if normalize_text(item)
        ).strip()

    if isinstance(value, dict):
        return html_to_plain_text(str(value))

    return str(value or "").strip()


def extract_result_summary(response: dict) -> str:
    """Extract display summary from a workflow response packet."""

    paths = (
        "user_output",
        "output",
        "summary",
        "report",
        "payload.user_output",
        "payload.answer",
        "payload.output",
        "payload.summary",
        "payload.report",
        "payload.rendered_report",
        "payload.message",
        "payload.body",
    )

    for path in paths:
        text = normalize_text(nested_value(response, path))

        if text:
            return text

    return "The document operation completed, but no display text was returned."


def workflow_response_failed(workflow_response: dict) -> bool:
    """Return whether a workflow packet represents a failed operation."""

    if not isinstance(workflow_response, dict):
        return True

    verdict = str(workflow_response.get("verdict") or "").strip().upper()

    return workflow_response.get("ok") is False or verdict == "ERROR"


def build_operation_actions(primary_document: dict) -> list:
    """Return standard actions for a document operation packet."""

    return [
        {
            "label": "Open Reader",
            "action": "open_reader",
            "document_id": primary_document.get("document_id"),
        }
    ]


def build_pending_packet(job: DocumentOperationJob) -> dict:
    """Return a pending/running job packet for legacy/future async use."""

    primary_document = job.documents[0] if job.documents else {}
    status_label = "Running" if job.status == JOB_STATUS_RUNNING else "Submitted"

    return {
        "ok": True,
        "packet_type": job.result_packet_type,
        "operation": job.operation_key,
        "operation_label": job.operation_label,
        "request_id": job.request_id,
        "job_id": job.job_id,
        "status": job.status,
        "submitted_at": job.submitted_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "document": primary_document,
        "documents": deepcopy(job.documents),
        "result": {
            "title": f"{job.operation_label} {status_label}",
            "summary": (
                f"{job.operation_label} has been submitted and is running in "
                "the document operation worker. The full report will appear "
                "here when the workflow completes."
            ),
            "sections": [],
            "raw_packet_type": "document_operation_job",
        },
        "actions": build_operation_actions(primary_document),
    }


def build_operation_result_packet(
    *,
    job: DocumentOperationJob,
    workflow_response: dict,
) -> dict:
    """Return the normalized document operation result packet."""

    primary_document = job.documents[0] if job.documents else {}
    failed = workflow_response_failed(workflow_response)

    return {
        "ok": not failed,
        "packet_type": job.result_packet_type,
        "operation": job.operation_key,
        "operation_label": job.operation_label,
        "request_id": job.request_id,
        "job_id": job.job_id,
        "status": JOB_STATUS_FAILED if failed else JOB_STATUS_COMPLETE,
        "submitted_at": job.submitted_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "document": primary_document,
        "documents": deepcopy(job.documents),
        "result": {
            "title": (
                f"{job.operation_label} Failed"
                if failed
                else f"{job.operation_label} Complete"
            ),
            "summary": extract_result_summary(workflow_response),
            "sections": [],
            "raw_packet_type": workflow_response.get("packet_type"),
        },
        "actions": build_operation_actions(primary_document),
        "workflow_response": workflow_response,
    }


def build_failure_workflow_response(message: str) -> dict:
    """Return a workflow-shaped failure response."""

    return {
        "ok": False,
        "packet_type": "docintel",
        "payload": {
            "answer": message or "The document operation failed.",
            "bridge": "",
            "report_kind": "document_operation",
            "suggestions": [],
        },
        "verdict": "ERROR",
    }


def decorate_packet(job: DocumentOperationJob, packet: dict) -> dict:
    """Attach current job metadata to a packet."""

    response = deepcopy(packet)

    response["job_id"] = job.job_id
    response["request_id"] = response.get("request_id") or job.request_id
    response["operation"] = response.get("operation") or job.operation_key
    response["operation_label"] = response.get("operation_label") or job.operation_label
    response["status"] = response.get("status") or job.status
    response["submitted_at"] = response.get("submitted_at") or job.submitted_at
    response["started_at"] = response.get("started_at") or job.started_at
    response["finished_at"] = response.get("finished_at") or job.finished_at

    return response


def attach_saved_review_metadata_locked(
    job: DocumentOperationJob,
    saved_review: dict,
) -> None:
    """Attach saved-review metadata to a completed result packet."""

    if not isinstance(saved_review, dict) or not saved_review.get("saved"):
        return

    if not isinstance(job.result_packet, dict):
        return

    review_id = str(saved_review.get("review_id") or "").strip()

    job.result_packet["saved_review"] = deepcopy(saved_review)

    if review_id:
        job.result_packet["review_id"] = review_id

    result = job.result_packet.get("result")

    if isinstance(result, dict):
        result["saved_review"] = deepcopy(saved_review)

        if review_id:
            result["review_id"] = review_id


def get_job_packet_locked(job: DocumentOperationJob) -> dict:
    """Return the current packet for a job. Caller must hold lock."""

    if job.result_packet:
        return decorate_packet(job, job.result_packet)

    return build_pending_packet(job)


def append_job_event_locked(job: DocumentOperationJob, event: str, **extra) -> None:
    """Append an internal job event."""

    payload = {
        "event": event,
        "timestamp": utc_now_iso(),
    }

    if extra:
        payload.update(extra)

    job.events.append(payload)


def prune_jobs_locked() -> None:
    """Keep the in-memory job registry bounded. Caller must hold lock."""

    if len(_JOBS) <= _MAX_RETAINED_JOBS:
        return

    finished_ids = [
        job_id
        for job_id, job in _JOBS.items()
        if job.status in {JOB_STATUS_COMPLETE, JOB_STATUS_FAILED}
    ]

    overflow = len(_JOBS) - _MAX_RETAINED_JOBS

    for job_id in finished_ids[:overflow]:
        _JOBS.pop(job_id, None)


def ensure_worker_started_locked() -> None:
    """Start the document operation worker if needed. Caller must hold lock."""

    global _WORKER_THREAD

    if _WORKER_THREAD and _WORKER_THREAD.is_alive():
        return

    _WORKER_THREAD = Thread(
        target=worker_loop,
        name="SolomonDocumentOperationWorker",
        daemon=True,
    )
    _WORKER_THREAD.start()


def worker_loop() -> None:
    """Process submitted document operation jobs serially."""

    logger.info("[document_operation.worker_started]")

    while True:
        job_id = _JOB_QUEUE.get()

        try:
            run_job(job_id)
        except Exception:
            logger.exception(
                "[document_operation.worker_unhandled_failure] job_id=%s",
                job_id,
            )
        finally:
            _JOB_QUEUE.task_done()


def persist_completed_review_for_job(
    job: DocumentOperationJob,
    result_packet: dict,
) -> dict:
    """Persist a completed review packet and attach saved-review metadata."""

    if not isinstance(result_packet, dict):
        return result_packet

    job.result_packet = deepcopy(result_packet)

    try:
        saved_review = save_document_operation_review(
            deepcopy(job),
            deepcopy(result_packet),
        )
    except Exception as exc:
        logger.warning(
            "[document_operation.review_save_failed] job_id=%s error=%s",
            job.job_id,
            exc,
        )
        return result_packet

    if not saved_review.get("saved"):
        return result_packet

    attach_saved_review_metadata_locked(job, saved_review)
    append_job_event_locked(
        job,
        "saved_review",
        review_id=saved_review.get("review_id"),
    )

    logger.info(
        "[document_operation.review_saved] job_id=%s review_id=%s",
        job.job_id,
        saved_review.get("review_id"),
    )

    return deepcopy(job.result_packet)


def persist_completed_review(job_id: str, result_packet: dict) -> None:
    """Persist a completed review packet and attach saved-review metadata."""

    with _JOB_LOCK:
        job = _JOBS.get(job_id)

        if not job:
            return

        job_snapshot = deepcopy(job)

    persisted_packet = persist_completed_review_for_job(
        job_snapshot,
        deepcopy(result_packet),
    )

    with _JOB_LOCK:
        job = _JOBS.get(job_id)

        if not job:
            return

        job.result_packet = deepcopy(persisted_packet)


def execute_document_operation_now(
    *,
    operation,
    documents: list[dict],
    user_id: int,
    request_id: str,
) -> dict:
    """Execute one document operation synchronously and return its final packet."""

    operation_key = normalize_operation_key(getattr(operation, "key", ""))
    runner = get_document_operation_runner(operation_key)

    if not runner:
        raise DocumentOperationJobError(
            "DocumentOperationRunnerNotFound",
            f"No backend runner is registered for {getattr(operation, 'label', operation_key)}.",
            status_code=501,
        )

    submitted_at = utc_now_iso()
    clean_documents = deepcopy(documents or [])

    job = DocumentOperationJob(
        job_id=uuid.uuid4().hex,
        user_id=int(user_id or 0),
        request_id=str(request_id or ""),
        operation_key=operation_key,
        operation_label=str(getattr(operation, "label", operation_key) or operation_key),
        result_packet_type=str(
            getattr(operation, "result_packet_type", "document_operation_result")
            or "document_operation_result"
        ),
        documents=clean_documents,
        submitted_at=submitted_at,
        status=JOB_STATUS_RUNNING,
        started_at=submitted_at,
    )

    append_job_event_locked(job, JOB_STATUS_SUBMITTED)
    append_job_event_locked(job, JOB_STATUS_RUNNING)

    logger.info(
        "[document_operation.sync_running] job_id=%s operation=%s user_id=%s docs=%s",
        job.job_id,
        job.operation_key,
        job.user_id,
        len(clean_documents),
    )

    try:
        workflow_response = runner(deepcopy(clean_documents))
        job.finished_at = utc_now_iso()
        job.result_packet = build_operation_result_packet(
            job=job,
            workflow_response=workflow_response,
        )
        job.status = str(job.result_packet.get("status") or JOB_STATUS_COMPLETE)
        append_job_event_locked(job, job.status)

        if job.status == JOB_STATUS_COMPLETE:
            job.result_packet = persist_completed_review_for_job(
                job,
                deepcopy(job.result_packet),
            )

        logger.info(
            "[document_operation.sync_finished] job_id=%s operation=%s status=%s",
            job.job_id,
            job.operation_key,
            job.status,
        )

        return decorate_packet(job, job.result_packet)

    except Exception as exc:
        logger.exception(
            "[document_operation.sync_failed] job_id=%s operation=%s",
            job.job_id,
            job.operation_key,
        )

        message = str(exc) or "The document operation failed."
        workflow_response = build_failure_workflow_response(message)

        job.status = JOB_STATUS_FAILED
        job.finished_at = utc_now_iso()
        job.error_message = message
        job.result_packet = build_operation_result_packet(
            job=job,
            workflow_response=workflow_response,
        )
        append_job_event_locked(job, JOB_STATUS_FAILED, error=message)

        return decorate_packet(job, job.result_packet)


def run_job(job_id: str) -> None:
    """Run one queued document operation job."""

    with _JOB_LOCK:
        job = _JOBS.get(job_id)

        if not job:
            return

        runner = _RUNNERS.get(job.operation_key)

        job.status = JOB_STATUS_RUNNING
        job.started_at = utc_now_iso()
        append_job_event_locked(job, "running")

    logger.info(
        "[document_operation.job_running] job_id=%s operation=%s user_id=%s docs=%s",
        job.job_id,
        job.operation_key,
        job.user_id,
        len(job.documents),
    )

    try:
        if not runner:
            raise DocumentOperationJobError(
                "DocumentOperationRunnerNotFound",
                f"No runner is registered for {job.operation_label}.",
            )

        workflow_response = runner(deepcopy(job.documents))
        finished_at = utc_now_iso()
        completed_result_packet = None

        with _JOB_LOCK:
            job = _JOBS.get(job_id)

            if not job:
                return

            job.finished_at = finished_at
            job.result_packet = build_operation_result_packet(
                job=job,
                workflow_response=workflow_response,
            )
            job.status = str(job.result_packet.get("status") or JOB_STATUS_COMPLETE)
            append_job_event_locked(job, job.status)

            if job.status == JOB_STATUS_COMPLETE:
                completed_result_packet = deepcopy(job.result_packet)

        if completed_result_packet:
            persist_completed_review(job_id, completed_result_packet)

        logger.info(
            "[document_operation.job_finished] job_id=%s operation=%s status=%s",
            job_id,
            job.operation_key,
            job.status,
        )

    except Exception as exc:
        logger.exception(
            "[document_operation.job_failed] job_id=%s operation=%s",
            job_id,
            job.operation_key,
        )

        finished_at = utc_now_iso()
        message = str(exc) or "The document operation failed."
        workflow_response = build_failure_workflow_response(message)

        with _JOB_LOCK:
            job = _JOBS.get(job_id)

            if not job:
                return

            job.status = JOB_STATUS_FAILED
            job.finished_at = finished_at
            job.error_message = message
            job.result_packet = build_operation_result_packet(
                job=job,
                workflow_response=workflow_response,
            )
            append_job_event_locked(job, JOB_STATUS_FAILED, error=message)


def submit_document_operation_job(
    *,
    operation,
    documents: list[dict],
    user_id: int,
    request_id: str,
) -> dict:
    """Create a queued job, enqueue it, and return the submitted packet."""

    operation_key = normalize_operation_key(getattr(operation, "key", ""))
    runner = get_document_operation_runner(operation_key)

    if not runner:
        raise DocumentOperationJobError(
            "DocumentOperationRunnerNotFound",
            f"No backend runner is registered for {getattr(operation, 'label', operation_key)}.",
            status_code=501,
        )

    clean_documents = deepcopy(documents or [])
    job_id = uuid.uuid4().hex

    job = DocumentOperationJob(
        job_id=job_id,
        user_id=int(user_id or 0),
        request_id=str(request_id or ""),
        operation_key=operation_key,
        operation_label=str(getattr(operation, "label", operation_key) or operation_key),
        result_packet_type=str(
            getattr(operation, "result_packet_type", "document_operation_result")
            or "document_operation_result"
        ),
        documents=clean_documents,
        submitted_at=utc_now_iso(),
    )

    with _JOB_LOCK:
        _JOBS[job_id] = job
        append_job_event_locked(job, JOB_STATUS_SUBMITTED)
        prune_jobs_locked()
        ensure_worker_started_locked()
        _JOB_QUEUE.put(job_id)
        packet = get_job_packet_locked(job)

    logger.info(
        "[document_operation.job_submitted] job_id=%s operation=%s user_id=%s docs=%s",
        job.job_id,
        job.operation_key,
        job.user_id,
        len(clean_documents),
    )

    return packet


def get_document_operation_job_packet(
    *,
    job_id: str,
    user_id: int,
) -> dict:
    """Return a job packet if the user owns the job."""

    clean_job_id = str(job_id or "").strip()

    if not clean_job_id:
        raise DocumentOperationJobError(
            "DocumentOperationJobMissing",
            "The document operation job id is missing.",
            status_code=400,
        )

    with _JOB_LOCK:
        job = _JOBS.get(clean_job_id)

        if not job:
            raise DocumentOperationJobError(
                "DocumentOperationJobNotFound",
                "The requested document operation job was not found.",
                status_code=404,
            )

        if int(job.user_id or 0) != int(user_id or 0):
            raise DocumentOperationJobError(
                "DocumentOperationJobForbidden",
                "You do not have access to this document operation job.",
                status_code=403,
            )

        return get_job_packet_locked(job)


__all__ = [
    "DocumentOperationJobError",
    "execute_document_operation_now",
    "get_document_operation_job_packet",
    "get_document_operation_runner",
    "register_document_operation_runner",
    "submit_document_operation_job",
]
# -------------------------------------------------------------------
# FILE: intelligence_job_repository.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Durable database authority for Solomon Intelligence Service jobs.
#
# The master SQL database is the canonical Intelligence Spool. This module
# deliberately contains no process-local queue, daemon thread, or worker
# lifecycle ownership. Web/application code may enqueue work inside an
# existing transaction; SIS workers claim and mutate work in independent,
# bounded transactions.
# -------------------------------------------------------------------

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence
import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from solomon_core.db import SessionLocal
from solomon_core.models import (
    INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND,
    INTELLIGENCE_JOB_STATUS_CANCELLED,
    INTELLIGENCE_JOB_STATUS_CLAIMED,
    INTELLIGENCE_JOB_STATUS_FAILED,
    INTELLIGENCE_JOB_STATUS_PENDING,
    INTELLIGENCE_JOB_STATUS_RETRY_WAIT,
    INTELLIGENCE_JOB_STATUS_RUNNING,
    INTELLIGENCE_JOB_STATUS_SUCCEEDED,
    INTELLIGENCE_JOB_STATUS_SUPERSEDED,
    FileRegistry,
    IntelligenceJob,
    IntelligenceJobEvent,
    WorkspaceIntelligenceObject,
)


INTELLIGENCE_JOB_EVENT_ENQUEUED = "enqueued"
INTELLIGENCE_JOB_EVENT_CLAIMED = "claimed"
INTELLIGENCE_JOB_EVENT_STARTED = "started"
INTELLIGENCE_JOB_EVENT_STAGE = "stage"
INTELLIGENCE_JOB_EVENT_RETRY_SCHEDULED = "retry_scheduled"
INTELLIGENCE_JOB_EVENT_SUCCEEDED = "succeeded"
INTELLIGENCE_JOB_EVENT_FAILED = "failed"
INTELLIGENCE_JOB_EVENT_CANCELLED = "cancelled"
INTELLIGENCE_JOB_EVENT_SUPERSEDED = "superseded"
INTELLIGENCE_JOB_EVENT_LEASE_RECOVERED = "lease_recovered"

_ACTIVE_LEASE_STATUSES = (
    INTELLIGENCE_JOB_STATUS_CLAIMED,
    INTELLIGENCE_JOB_STATUS_RUNNING,
)
_TERMINAL_STATUSES = (
    INTELLIGENCE_JOB_STATUS_SUCCEEDED,
    INTELLIGENCE_JOB_STATUS_FAILED,
    INTELLIGENCE_JOB_STATUS_CANCELLED,
    INTELLIGENCE_JOB_STATUS_SUPERSEDED,
)
_CLAIMABLE_STATUSES = (
    INTELLIGENCE_JOB_STATUS_PENDING,
    INTELLIGENCE_JOB_STATUS_RETRY_WAIT,
)

_REPLAYABLE_TERMINAL_STATUSES = (
    INTELLIGENCE_JOB_STATUS_FAILED,
)

_ARTIFACT_FAILURE_PROJECTIONS = {
    "document_summary": {
        "object_status_field": "summary_status",
        "metadata_prefix": "summary",
        "record_metadata_prefix": "workspace_intelligence_summary",
    },
    "document_embeddings": {
        "object_status_field": "embedding_status",
        "metadata_prefix": "embedding",
        "record_metadata_prefix": "workspace_intelligence_embedding",
    },
}


class IntelligenceJobRepositoryError(RuntimeError):
    """Base exception for durable Intelligence Spool operations."""


class IntelligenceJobNotFound(IntelligenceJobRepositoryError):
    """Raised when a requested durable intelligence job does not exist."""


class IntelligenceJobStateConflict(IntelligenceJobRepositoryError):
    """Raised when a requested transition is invalid for the current state."""


class IntelligenceJobLeaseConflict(IntelligenceJobRepositoryError):
    """Raised when a worker no longer owns a valid active lease."""


@dataclass(frozen=True)
class IntelligenceJobEnqueueSpec:
    """Immutable input contract for one durable intelligence job request."""

    job_type: str
    artifact_type: Optional[str]
    target_type: str
    target_id: str
    trigger_type: str
    idempotency_key: str

    target_version: Optional[int] = None
    source_hash: Optional[str] = None
    trigger_ref: Optional[str] = None
    request_class: str = INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND
    priority: int = 100

    user_id: Optional[int] = None
    organization_id: Optional[str] = None
    file_registry_id: Optional[int] = None
    intelligence_object_id: Optional[int] = None
    request_id: Optional[str] = None
    case_id: Optional[str] = None

    payload: Optional[Dict[str, Any]] = None
    processor_key: Optional[str] = None
    processor_version: Optional[str] = None
    model_key: Optional[str] = None

    max_attempts: int = 3
    available_at: Optional[datetime] = None


@dataclass(frozen=True)
class IntelligenceJobSnapshot:
    """Detached read model safe to use after the database session closes."""

    job_id: str
    job_type: str
    artifact_type: Optional[str]
    request_class: str
    priority: int
    status: str
    idempotency_key: str

    target_type: str
    target_id: str
    target_version: Optional[int]
    source_hash: Optional[str]
    trigger_type: str
    trigger_ref: Optional[str]

    user_id: Optional[int]
    organization_id: Optional[str]
    file_registry_id: Optional[int]
    intelligence_object_id: Optional[int]
    request_id: Optional[str]
    case_id: Optional[str]

    payload: Optional[Dict[str, Any]]
    result: Optional[Dict[str, Any]]
    processor_key: Optional[str]
    processor_version: Optional[str]
    model_key: Optional[str]

    attempt_count: int
    max_attempts: int
    available_at: Optional[datetime]

    worker_id: Optional[str]
    lease_token: Optional[str]
    lease_expires_at: Optional[datetime]
    heartbeat_at: Optional[datetime]
    claimed_at: Optional[datetime]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]

    failure_code: Optional[str]
    failure_message: Optional[str]
    last_error_at: Optional[datetime]
    cancel_reason: Optional[str]
    superseded_by_job_id: Optional[str]

    created_at: Optional[datetime]
    updated_at: Optional[datetime]


@dataclass(frozen=True)
class IntelligenceJobEventSnapshot:
    """Detached operational evidence emitted by one intelligence job."""

    event_id: str
    job_id: str
    event_type: str
    stage: Optional[str]
    from_status: Optional[str]
    to_status: Optional[str]
    attempt_number: Optional[int]
    worker_id: Optional[str]
    lease_token: Optional[str]
    request_id: Optional[str]
    case_id: Optional[str]
    message: Optional[str]
    details: Optional[Dict[str, Any]]
    created_at: Optional[datetime]


def build_intelligence_job_idempotency_key(
    *,
    job_type: str,
    artifact_type: Optional[str],
    target_type: str,
    target_id: str,
    target_version: Optional[int],
    source_hash: Optional[str],
    processor_key: Optional[str],
    processor_version: Optional[str],
    model_key: Optional[str],
) -> str:
    """Build a stable content/version-bound idempotency key.

    Trigger metadata is intentionally excluded. Repeated requests for the same
    derived artifact and processor contract therefore converge on one durable
    job. A new document version, content hash, processor contract, or model
    identity naturally produces a different key.
    """

    identity = {
        "artifact_type": _optional_text(artifact_type),
        "job_type": _required_text("job_type", job_type),
        "model_key": _optional_text(model_key),
        "processor_key": _optional_text(processor_key),
        "processor_version": _optional_text(processor_version),
        "source_hash": _optional_text(source_hash),
        "target_id": _required_text("target_id", target_id),
        "target_type": _required_text("target_type", target_type),
        "target_version": target_version,
    }
    encoded = json.dumps(
        identity,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    digest = hashlib.sha256(encoded).hexdigest()
    return f"intelligence-job:{digest}"


class IntelligenceJobRepository:
    """Transactional authority for the durable Solomon Intelligence Spool.

    Lower numeric priority values are dispatched first. The spool is for
    asynchronous/background work; live interactive requests continue to use
    the SIS interactive execution contract and never wait behind these rows.
    """

    def __init__(
        self,
        *,
        session_factory: Optional[Callable[[], Session]] = None,
    ) -> None:
        # SessionLocal is scoped for request/thread convenience. Using its
        # underlying factory gives SIS-owned calls an independent Session and
        # prevents repository cleanup from disturbing a Flask request session.
        self._session_factory = (
            session_factory
            or SessionLocal.session_factory
        )

    def enqueue(
        self,
        spec: IntelligenceJobEnqueueSpec,
        *,
        session: Optional[Session] = None,
    ) -> IntelligenceJobSnapshot:
        """Idempotently enqueue one semantic job, replaying terminal failures.

        Active or succeeded work for the same governed artifact identity is
        returned unchanged. A terminal failed execution remains immutable audit
        history; a later enqueue creates one new execution generation linked to
        that failed predecessor. When ``session`` is supplied, no commit is
        performed here so upload authority can remain transactionally atomic.
        """

        normalized = _validate_enqueue_spec(spec)

        try:
            with self._transaction(session) as db:
                now = _database_utc_now(db)
                # A locking read is a current read on MySQL/InnoDB and also
                # serializes the indexed idempotency key gap. The database
                # UNIQUE constraint remains the final duplicate boundary.
                existing = (
                    db.query(IntelligenceJob)
                    .filter(
                        IntelligenceJob.idempotency_key
                        == normalized.idempotency_key
                    )
                    .with_for_update()
                    .one_or_none()
                )
                replay_of_job = None
                execution_idempotency_key = normalized.idempotency_key

                if existing is not None:
                    if existing.status not in _REPLAYABLE_TERMINAL_STATUSES:
                        return _snapshot_job(existing)

                    latest_semantic_job = self._latest_semantic_job(
                        db,
                        normalized,
                        lock=True,
                    )
                    if latest_semantic_job is not None:
                        if (
                            latest_semantic_job.status
                            not in _REPLAYABLE_TERMINAL_STATUSES
                        ):
                            return _snapshot_job(latest_semantic_job)
                        replay_of_job = latest_semantic_job
                    else:
                        replay_of_job = existing

                    execution_idempotency_key = (
                        _build_replay_execution_idempotency_key(
                            semantic_idempotency_key=normalized.idempotency_key,
                            predecessor_job_id=replay_of_job.job_id,
                        )
                    )

                payload = deepcopy(normalized.payload)
                if replay_of_job is not None:
                    payload = dict(payload or {})
                    payload["intelligence_job_replay"] = {
                        "contract": "intelligence_job_replay_v1",
                        "replay_of_job_id": replay_of_job.job_id,
                        "semantic_idempotency_key": normalized.idempotency_key,
                    }

                job = IntelligenceJob(
                    job_type=normalized.job_type,
                    artifact_type=normalized.artifact_type,
                    request_class=normalized.request_class,
                    priority=normalized.priority,
                    status=INTELLIGENCE_JOB_STATUS_PENDING,
                    idempotency_key=execution_idempotency_key,
                    user_id=normalized.user_id,
                    organization_id=normalized.organization_id,
                    file_registry_id=normalized.file_registry_id,
                    intelligence_object_id=normalized.intelligence_object_id,
                    target_type=normalized.target_type,
                    target_id=normalized.target_id,
                    target_version=normalized.target_version,
                    source_hash=normalized.source_hash,
                    trigger_type=normalized.trigger_type,
                    trigger_ref=normalized.trigger_ref,
                    request_id=normalized.request_id,
                    case_id=normalized.case_id,
                    payload_json=payload,
                    processor_key=normalized.processor_key,
                    processor_version=normalized.processor_version,
                    model_key=normalized.model_key,
                    max_attempts=normalized.max_attempts,
                    available_at=(
                        _ensure_utc(normalized.available_at)
                        if normalized.available_at is not None
                        else now
                    ),
                )
                db.add(job)
                db.flush()

                self._append_event(
                    db,
                    job=job,
                    event_type=INTELLIGENCE_JOB_EVENT_ENQUEUED,
                    from_status=None,
                    to_status=INTELLIGENCE_JOB_STATUS_PENDING,
                    message="Intelligence job enqueued.",
                    details={
                        "artifact_type": job.artifact_type,
                        "priority": job.priority,
                        "request_class": job.request_class,
                        "target_type": job.target_type,
                        "target_id": job.target_id,
                        "target_version": job.target_version,
                        "replay_of_job_id": (
                            replay_of_job.job_id
                            if replay_of_job is not None
                            else None
                        ),
                        "semantic_idempotency_key": (
                            normalized.idempotency_key
                            if replay_of_job is not None
                            else None
                        ),
                    },
                )
                db.flush()
                return _snapshot_job(job)
        except IntegrityError:
            # If this repository owned the transaction, a concurrent enqueue
            # may have committed the same unique key between our read/insert.
            # The failed transaction has already rolled back, so a new read may
            # safely return the canonical row. A caller-owned transaction must
            # receive the IntegrityError because only the caller may decide how
            # to roll back/retry its larger atomic upload transaction.
            if session is not None:
                raise
            with self._read_session() as db:
                existing = (
                    db.query(IntelligenceJob)
                    .filter(
                        IntelligenceJob.idempotency_key
                        == normalized.idempotency_key
                    )
                    .one_or_none()
                )
                if existing is not None and (
                    existing.status not in _REPLAYABLE_TERMINAL_STATUSES
                ):
                    return _snapshot_job(existing)

                latest_semantic_job = self._latest_semantic_job(
                    db,
                    normalized,
                    lock=False,
                )
                if latest_semantic_job is None:
                    raise
                return _snapshot_job(latest_semantic_job)

    def claim_next(
        self,
        *,
        worker_id: str,
        lease_seconds: int,
        job_types: Optional[Sequence[str]] = None,
        request_class: str = INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND,
    ) -> Optional[IntelligenceJobSnapshot]:
        """Atomically claim the next eligible durable job.

        SELECT ... FOR UPDATE SKIP LOCKED permits future multiple workers to
        poll the same database without duplicate claims while preserving a
        simple single-worker deployment today.
        """

        worker = _bounded_text("worker_id", worker_id, 128)
        lease_duration = _positive_int("lease_seconds", lease_seconds)
        request_class_value = _bounded_text(
            "request_class",
            request_class,
            32,
        )
        normalized_job_types = _normalize_job_types(job_types)
        if request_class_value != INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND:
            raise ValueError(
                "Durable Intelligence Spool claims must use request_class="
                f"{INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND!r}."
            )

        with self._transaction() as db:
            now = _database_utc_now(db)
            query = db.query(IntelligenceJob).filter(
                IntelligenceJob.status.in_(_CLAIMABLE_STATUSES),
                IntelligenceJob.request_class == request_class_value,
                IntelligenceJob.available_at <= now,
            )
            if normalized_job_types:
                query = query.filter(
                    IntelligenceJob.job_type.in_(normalized_job_types)
                )

            job = (
                query.order_by(
                    IntelligenceJob.priority.asc(),
                    IntelligenceJob.created_at.asc(),
                    IntelligenceJob.id.asc(),
                )
                .with_for_update(skip_locked=True)
                .first()
            )
            if job is None:
                return None

            previous_status = job.status
            token = uuid.uuid4().hex
            job.status = INTELLIGENCE_JOB_STATUS_CLAIMED
            job.worker_id = worker
            job.lease_token = token
            job.lease_expires_at = now + timedelta(seconds=lease_duration)
            job.heartbeat_at = now
            job.claimed_at = now
            job.started_at = None
            job.completed_at = None
            job.attempt_count = int(job.attempt_count or 0) + 1
            job.failure_code = None
            job.failure_message = None

            self._append_event(
                db,
                job=job,
                event_type=INTELLIGENCE_JOB_EVENT_CLAIMED,
                from_status=previous_status,
                to_status=INTELLIGENCE_JOB_STATUS_CLAIMED,
                worker_id=worker,
                lease_token=token,
                message="Intelligence job claimed by worker.",
                details={"lease_seconds": lease_duration},
            )
            db.flush()
            return _snapshot_job(job)

    def start(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> IntelligenceJobSnapshot:
        """Transition a valid claimed lease into running state."""

        with self._transaction() as db:
            now = _database_utc_now(db)
            job = self._locked_job(db, job_id)
            self._require_active_lease(
                job,
                worker_id=worker_id,
                lease_token=lease_token,
                now=now,
                allowed_statuses=(INTELLIGENCE_JOB_STATUS_CLAIMED,),
            )
            previous_status = job.status
            job.status = INTELLIGENCE_JOB_STATUS_RUNNING
            job.started_at = job.started_at or now
            job.heartbeat_at = now

            self._append_event(
                db,
                job=job,
                event_type=INTELLIGENCE_JOB_EVENT_STARTED,
                stage=_optional_bounded_text("stage", stage, 128),
                from_status=previous_status,
                to_status=INTELLIGENCE_JOB_STATUS_RUNNING,
                worker_id=job.worker_id,
                lease_token=job.lease_token,
                message="Intelligence job execution started.",
                details=details,
            )
            db.flush()
            return _snapshot_job(job)

    def renew_lease(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        lease_seconds: int,
    ) -> IntelligenceJobSnapshot:
        """Renew one active claim without emitting noisy heartbeat events."""

        lease_duration = _positive_int("lease_seconds", lease_seconds)
        with self._transaction() as db:
            now = _database_utc_now(db)
            job = self._locked_job(db, job_id)
            self._require_active_lease(
                job,
                worker_id=worker_id,
                lease_token=lease_token,
                now=now,
                allowed_statuses=_ACTIVE_LEASE_STATUSES,
            )
            job.heartbeat_at = now
            job.lease_expires_at = now + timedelta(seconds=lease_duration)
            db.flush()
            return _snapshot_job(job)

    def record_stage(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        stage: str,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> IntelligenceJobEventSnapshot:
        """Append CaseFile-grade operational evidence for active work."""

        with self._transaction() as db:
            now = _database_utc_now(db)
            job = self._locked_job(db, job_id)
            self._require_active_lease(
                job,
                worker_id=worker_id,
                lease_token=lease_token,
                now=now,
                allowed_statuses=_ACTIVE_LEASE_STATUSES,
            )
            event = self._append_event(
                db,
                job=job,
                event_type=INTELLIGENCE_JOB_EVENT_STAGE,
                stage=_bounded_text("stage", stage, 128),
                from_status=job.status,
                to_status=job.status,
                worker_id=job.worker_id,
                lease_token=job.lease_token,
                message=_optional_text(message),
                details=details,
            )
            db.flush()
            return _snapshot_event(event)

    def succeed(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        result: Optional[Dict[str, Any]] = None,
        intelligence_object_id: Optional[int] = None,
        stage: Optional[str] = None,
    ) -> IntelligenceJobSnapshot:
        """Atomically mark active work successful and release its lease."""

        with self._transaction() as db:
            now = _database_utc_now(db)
            job = self._locked_job(db, job_id)
            self._require_active_lease(
                job,
                worker_id=worker_id,
                lease_token=lease_token,
                now=now,
                allowed_statuses=_ACTIVE_LEASE_STATUSES,
            )
            previous_status = job.status
            event_worker = job.worker_id
            event_token = job.lease_token
            job.status = INTELLIGENCE_JOB_STATUS_SUCCEEDED
            job.result_json = deepcopy(result)
            if intelligence_object_id is not None:
                job.intelligence_object_id = intelligence_object_id
            job.completed_at = now
            self._clear_lease(job)

            self._append_event(
                db,
                job=job,
                event_type=INTELLIGENCE_JOB_EVENT_SUCCEEDED,
                stage=_optional_bounded_text("stage", stage, 128),
                from_status=previous_status,
                to_status=INTELLIGENCE_JOB_STATUS_SUCCEEDED,
                worker_id=event_worker,
                lease_token=event_token,
                message="Intelligence job completed successfully.",
                details={
                    "intelligence_object_id": job.intelligence_object_id,
                    "progress_percent": 100,
                },
            )
            db.flush()
            return _snapshot_job(job)

    def retry(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        failure_code: str,
        failure_message: str,
        retry_delay_seconds: int,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> IntelligenceJobSnapshot:
        """Release active work for retry, or fail it when attempts are spent."""

        delay = _non_negative_int(
            "retry_delay_seconds",
            retry_delay_seconds,
        )
        with self._transaction() as db:
            now = _database_utc_now(db)
            job = self._locked_job(db, job_id)
            self._require_active_lease(
                job,
                worker_id=worker_id,
                lease_token=lease_token,
                now=now,
                allowed_statuses=_ACTIVE_LEASE_STATUSES,
            )
            previous_status = job.status
            event_worker = job.worker_id
            event_token = job.lease_token
            job.failure_code = _bounded_text(
                "failure_code",
                failure_code,
                128,
            )
            job.failure_message = _required_text(
                "failure_message",
                failure_message,
            )
            job.last_error_at = now

            exhausted = int(job.attempt_count or 0) >= int(
                job.max_attempts or 1
            )
            if exhausted:
                job.status = INTELLIGENCE_JOB_STATUS_FAILED
                job.completed_at = now
                event_type = INTELLIGENCE_JOB_EVENT_FAILED
                event_message = (
                    "Intelligence job exhausted its retry budget."
                )
            else:
                job.status = INTELLIGENCE_JOB_STATUS_RETRY_WAIT
                job.available_at = now + timedelta(seconds=delay)
                job.completed_at = None
                event_type = INTELLIGENCE_JOB_EVENT_RETRY_SCHEDULED
                event_message = "Intelligence job scheduled for retry."

            self._clear_lease(job)
            if exhausted:
                self._converge_failed_artifact_state(
                    db,
                    job=job,
                    now=now,
                )
            event_details = dict(details or {})
            event_details.update(
                {
                    "failure_code": job.failure_code,
                    "max_attempts": job.max_attempts,
                    "retry_delay_seconds": delay,
                }
            )
            self._append_event(
                db,
                job=job,
                event_type=event_type,
                stage=_optional_bounded_text("stage", stage, 128),
                from_status=previous_status,
                to_status=job.status,
                worker_id=event_worker,
                lease_token=event_token,
                message=event_message,
                details=event_details,
            )
            db.flush()
            return _snapshot_job(job)

    def fail(
        self,
        *,
        job_id: str,
        worker_id: str,
        lease_token: str,
        failure_code: str,
        failure_message: str,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> IntelligenceJobSnapshot:
        """Terminally fail active leased work and release worker ownership."""

        with self._transaction() as db:
            now = _database_utc_now(db)
            job = self._locked_job(db, job_id)
            self._require_active_lease(
                job,
                worker_id=worker_id,
                lease_token=lease_token,
                now=now,
                allowed_statuses=_ACTIVE_LEASE_STATUSES,
            )
            previous_status = job.status
            event_worker = job.worker_id
            event_token = job.lease_token
            job.status = INTELLIGENCE_JOB_STATUS_FAILED
            job.failure_code = _bounded_text(
                "failure_code",
                failure_code,
                128,
            )
            job.failure_message = _required_text(
                "failure_message",
                failure_message,
            )
            job.last_error_at = now
            job.completed_at = now
            self._clear_lease(job)
            self._converge_failed_artifact_state(
                db,
                job=job,
                now=now,
            )

            event_details = dict(details or {})
            event_details["failure_code"] = job.failure_code
            self._append_event(
                db,
                job=job,
                event_type=INTELLIGENCE_JOB_EVENT_FAILED,
                stage=_optional_bounded_text("stage", stage, 128),
                from_status=previous_status,
                to_status=INTELLIGENCE_JOB_STATUS_FAILED,
                worker_id=event_worker,
                lease_token=event_token,
                message="Intelligence job failed.",
                details=event_details,
            )
            db.flush()
            return _snapshot_job(job)

    def cancel(
        self,
        *,
        job_id: str,
        reason: str,
        request_id: Optional[str] = None,
        case_id: Optional[str] = None,
    ) -> IntelligenceJobSnapshot:
        """Cancel non-terminal work through the database authority."""

        with self._transaction() as db:
            now = _database_utc_now(db)
            job = self._locked_job(db, job_id)
            if job.status in _TERMINAL_STATUSES:
                if job.status == INTELLIGENCE_JOB_STATUS_CANCELLED:
                    return _snapshot_job(job)
                raise IntelligenceJobStateConflict(
                    f"Job {job.job_id} is already terminal: {job.status}."
                )

            previous_status = job.status
            event_worker = job.worker_id
            event_token = job.lease_token
            job.status = INTELLIGENCE_JOB_STATUS_CANCELLED
            job.cancel_reason = _required_text("reason", reason)
            job.completed_at = now
            self._clear_lease(job)

            self._append_event(
                db,
                job=job,
                event_type=INTELLIGENCE_JOB_EVENT_CANCELLED,
                from_status=previous_status,
                to_status=INTELLIGENCE_JOB_STATUS_CANCELLED,
                worker_id=event_worker,
                lease_token=event_token,
                request_id=_optional_text(request_id),
                case_id=_optional_text(case_id),
                message="Intelligence job cancelled.",
                details={"reason": job.cancel_reason},
            )
            db.flush()
            return _snapshot_job(job)

    def supersede(
        self,
        *,
        job_id: str,
        superseded_by_job_id: str,
        reason: str,
    ) -> IntelligenceJobSnapshot:
        """Mark stale non-terminal work superseded by a newer durable job."""

        replacement_id = _bounded_text(
            "superseded_by_job_id",
            superseded_by_job_id,
            64,
        )
        with self._transaction() as db:
            now = _database_utc_now(db)
            job = self._locked_job(db, job_id)
            if job.status in _TERMINAL_STATUSES:
                if (
                    job.status == INTELLIGENCE_JOB_STATUS_SUPERSEDED
                    and job.superseded_by_job_id == replacement_id
                ):
                    return _snapshot_job(job)
                raise IntelligenceJobStateConflict(
                    f"Job {job.job_id} is already terminal: {job.status}."
                )

            previous_status = job.status
            event_worker = job.worker_id
            event_token = job.lease_token
            job.status = INTELLIGENCE_JOB_STATUS_SUPERSEDED
            job.superseded_by_job_id = replacement_id
            job.completed_at = now
            self._clear_lease(job)

            self._append_event(
                db,
                job=job,
                event_type=INTELLIGENCE_JOB_EVENT_SUPERSEDED,
                from_status=previous_status,
                to_status=INTELLIGENCE_JOB_STATUS_SUPERSEDED,
                worker_id=event_worker,
                lease_token=event_token,
                message="Intelligence job superseded by newer work.",
                details={
                    "reason": _required_text("reason", reason),
                    "superseded_by_job_id": replacement_id,
                },
            )
            db.flush()
            return _snapshot_job(job)

    def recover_expired_leases(
        self,
        *,
        limit: int = 100,
        retry_delay_seconds: int = 0,
    ) -> List[IntelligenceJobSnapshot]:
        """Recover work abandoned by a dead or disconnected SIS worker.

        Expired claims are either returned to retry_wait or terminally failed
        when the job has consumed its attempt budget. Every recovery is written
        as operational evidence in the same transaction.
        """

        recovery_limit = _positive_int("limit", limit)
        retry_delay = _non_negative_int(
            "retry_delay_seconds",
            retry_delay_seconds,
        )
        recovered: List[IntelligenceJobSnapshot] = []

        with self._transaction() as db:
            now = _database_utc_now(db)
            jobs = (
                db.query(IntelligenceJob)
                .filter(
                    IntelligenceJob.status.in_(_ACTIVE_LEASE_STATUSES),
                    IntelligenceJob.lease_expires_at.is_not(None),
                    IntelligenceJob.lease_expires_at <= now,
                )
                .order_by(
                    IntelligenceJob.lease_expires_at.asc(),
                    IntelligenceJob.id.asc(),
                )
                .limit(recovery_limit)
                .with_for_update(skip_locked=True)
                .all()
            )

            for job in jobs:
                previous_status = job.status
                previous_worker = job.worker_id
                previous_token = job.lease_token
                exhausted = int(job.attempt_count or 0) >= int(
                    job.max_attempts or 1
                )

                job.failure_code = "lease_expired"
                job.failure_message = (
                    "The worker lease expired before the job reached a "
                    "terminal state."
                )
                job.last_error_at = now

                if exhausted:
                    job.status = INTELLIGENCE_JOB_STATUS_FAILED
                    job.completed_at = now
                else:
                    job.status = INTELLIGENCE_JOB_STATUS_RETRY_WAIT
                    job.available_at = now + timedelta(
                        seconds=retry_delay
                    )
                    job.completed_at = None

                self._clear_lease(job)
                self._append_event(
                    db,
                    job=job,
                    event_type=INTELLIGENCE_JOB_EVENT_LEASE_RECOVERED,
                    from_status=previous_status,
                    to_status=job.status,
                    worker_id=previous_worker,
                    lease_token=previous_token,
                    message="Expired intelligence worker lease recovered.",
                    details={
                        "failure_code": "lease_expired",
                        "retry_delay_seconds": retry_delay,
                        "terminal": exhausted,
                    },
                )
                recovered.append(_snapshot_job(job))

            db.flush()

        return recovered

    def get_operational_snapshot(
        self,
        *,
        active_limit: int = 25,
    ) -> Dict[str, Any]:
        """Return a read-only, database-authoritative Intelligence Spool view.

        The snapshot is intentionally safe for console diagnostics and future
        GUI projection. Counts describe durable job state across all SIS workers;
        active job progress comes only from recorded stage evidence.
        """

        limit = _positive_int("active_limit", active_limit)
        with self._read_session() as db:
            observed_at = _database_utc_now(db)
            count_rows = (
                db.query(
                    IntelligenceJob.status,
                    func.count(IntelligenceJob.id),
                )
                .group_by(IntelligenceJob.status)
                .all()
            )
            status_counts = {
                str(status): int(count or 0)
                for status, count in count_rows
            }

            active_jobs = (
                db.query(IntelligenceJob)
                .filter(IntelligenceJob.status.in_(_ACTIVE_LEASE_STATUSES))
                .order_by(
                    IntelligenceJob.started_at.asc(),
                    IntelligenceJob.claimed_at.asc(),
                    IntelligenceJob.id.asc(),
                )
                .limit(limit + 1)
                .all()
            )
            active_jobs_truncated = len(active_jobs) > limit
            visible_active_jobs = active_jobs[:limit]

            active_payload: List[Dict[str, Any]] = []
            for job in visible_active_jobs:
                latest_event = (
                    db.query(IntelligenceJobEvent)
                    .filter(IntelligenceJobEvent.job_id == job.job_id)
                    .order_by(IntelligenceJobEvent.id.desc())
                    .first()
                )
                event_details = (
                    deepcopy(latest_event.details_json)
                    if latest_event is not None
                    and isinstance(latest_event.details_json, dict)
                    else {}
                )
                progress_percent = _optional_progress_percent(
                    event_details.get("progress_percent")
                )
                active_payload.append({
                    "job_id": str(job.job_id),
                    "job_type": str(job.job_type),
                    "status": str(job.status),
                    "worker_id": _optional_text(job.worker_id),
                    "attempt_count": int(job.attempt_count or 0),
                    "max_attempts": int(job.max_attempts or 0),
                    "stage": (
                        _optional_text(latest_event.stage)
                        if latest_event is not None
                        else None
                    ),
                    "progress_percent": progress_percent,
                    "claimed_at": (
                        job.claimed_at.isoformat()
                        if job.claimed_at is not None
                        else None
                    ),
                    "started_at": (
                        job.started_at.isoformat()
                        if job.started_at is not None
                        else None
                    ),
                    "heartbeat_at": (
                        job.heartbeat_at.isoformat()
                        if job.heartbeat_at is not None
                        else None
                    ),
                })

            pending = int(
                status_counts.get(INTELLIGENCE_JOB_STATUS_PENDING, 0)
            )
            retry_wait = int(
                status_counts.get(INTELLIGENCE_JOB_STATUS_RETRY_WAIT, 0)
            )
            claimed = int(
                status_counts.get(INTELLIGENCE_JOB_STATUS_CLAIMED, 0)
            )
            running = int(
                status_counts.get(INTELLIGENCE_JOB_STATUS_RUNNING, 0)
            )
            backlog = pending + retry_wait
            in_flight = claimed + running

            return {
                "observed_at": observed_at.isoformat(),
                "pending": pending,
                "retry_wait": retry_wait,
                "claimed": claimed,
                "running": running,
                "backlog": backlog,
                "in_flight": in_flight,
                "unfinished": backlog + in_flight,
                "status_counts": status_counts,
                "active_jobs": active_payload,
                "active_jobs_truncated": active_jobs_truncated,
            }

    def get_latest_completion_sequence(self) -> int:
        """Return the latest durable succeeded-event sequence id.

        This is used by the local web event bridge after SIS compute is moved
        off-machine.  The database event row id is the durable cursor; it is
        never exposed as product authority and does not replace job state.
        """

        with self._read_session() as db:
            latest = (
                db.query(func.max(IntelligenceJobEvent.id))
                .filter(
                    IntelligenceJobEvent.event_type
                    == INTELLIGENCE_JOB_EVENT_SUCCEEDED
                )
                .scalar()
            )
            return max(0, int(latest or 0))

    def list_completion_events_after(
        self,
        after_sequence_id: int,
        *,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """Return durable succeeded-job notifications after one DB cursor.

        Completion notifications are reconstructed from authoritative job/event
        rows so the web application no longer depends on a process-local event
        broker living beside SIS.  Consumers still re-read and reauthorize the
        canonical resource before exposing any capability.
        """

        sequence = max(0, int(after_sequence_id or 0))
        event_limit = _positive_int("limit", limit)

        with self._read_session() as db:
            rows = (
                db.query(IntelligenceJobEvent, IntelligenceJob)
                .join(
                    IntelligenceJob,
                    IntelligenceJob.job_id == IntelligenceJobEvent.job_id,
                )
                .filter(
                    IntelligenceJobEvent.id > sequence,
                    IntelligenceJobEvent.event_type
                    == INTELLIGENCE_JOB_EVENT_SUCCEEDED,
                )
                .order_by(IntelligenceJobEvent.id.asc())
                .limit(event_limit)
                .all()
            )

            payload: List[Dict[str, Any]] = []
            for event, job in rows:
                details = (
                    deepcopy(event.details_json)
                    if isinstance(event.details_json, dict)
                    else {}
                )
                completed_at = job.completed_at or event.created_at
                payload.append({
                    "sequence_id": int(event.id),
                    "job_id": str(job.job_id),
                    "job_type": str(job.job_type),
                    "document_id": str(job.target_id or ""),
                    "intelligence_object_id": (
                        int(job.intelligence_object_id)
                        if job.intelligence_object_id is not None
                        else details.get("intelligence_object_id")
                    ),
                    "stage": str(event.stage or "completed"),
                    "completed_at": (
                        completed_at.isoformat()
                        if completed_at is not None
                        else None
                    ),
                })

            return payload

    def get_job(self, job_id: str) -> IntelligenceJobSnapshot:
        """Read one durable job by opaque job identifier."""

        normalized_job_id = _bounded_text("job_id", job_id, 64)
        with self._read_session() as db:
            job = (
                db.query(IntelligenceJob)
                .filter(IntelligenceJob.job_id == normalized_job_id)
                .one_or_none()
            )
            if job is None:
                raise IntelligenceJobNotFound(
                    f"Intelligence job not found: {normalized_job_id}"
                )
            return _snapshot_job(job)

    def list_events(
        self,
        job_id: str,
        *,
        limit: int = 500,
    ) -> List[IntelligenceJobEventSnapshot]:
        """Return append-oriented diagnostics for one durable job."""

        normalized_job_id = _bounded_text("job_id", job_id, 64)
        event_limit = _positive_int("limit", limit)
        with self._read_session() as db:
            exists = (
                db.query(IntelligenceJob.job_id)
                .filter(IntelligenceJob.job_id == normalized_job_id)
                .first()
            )
            if exists is None:
                raise IntelligenceJobNotFound(
                    f"Intelligence job not found: {normalized_job_id}"
                )

            events = (
                db.query(IntelligenceJobEvent)
                .filter(
                    IntelligenceJobEvent.job_id == normalized_job_id
                )
                .order_by(IntelligenceJobEvent.id.asc())
                .limit(event_limit)
                .all()
            )
            return [_snapshot_event(event) for event in events]

    def _latest_semantic_job(
        self,
        db: Session,
        spec: IntelligenceJobEnqueueSpec,
        *,
        lock: bool,
    ) -> Optional[IntelligenceJob]:
        """Return the latest execution for one semantic artifact identity."""

        query = (
            db.query(IntelligenceJob)
            .filter(
                IntelligenceJob.job_type == spec.job_type,
                IntelligenceJob.artifact_type == spec.artifact_type,
                IntelligenceJob.target_type == spec.target_type,
                IntelligenceJob.target_id == spec.target_id,
                IntelligenceJob.target_version == spec.target_version,
                IntelligenceJob.source_hash == spec.source_hash,
                IntelligenceJob.processor_key == spec.processor_key,
                IntelligenceJob.processor_version == spec.processor_version,
                IntelligenceJob.model_key == spec.model_key,
            )
            .order_by(
                IntelligenceJob.created_at.desc(),
                IntelligenceJob.id.desc(),
            )
        )
        if lock:
            query = query.with_for_update()
        return query.first()

    @staticmethod
    def _converge_failed_artifact_state(
        db: Session,
        *,
        job: IntelligenceJob,
        now: datetime,
    ) -> None:
        """Project a terminal job failure onto its current materialized artifact state."""

        projection = _ARTIFACT_FAILURE_PROJECTIONS.get(
            str(job.artifact_type or "").strip()
        )
        if projection is None or job.intelligence_object_id is None:
            return

        # Match the file -> intelligence-object lock order used by document
        # persistence so failure convergence cannot introduce a reverse-order
        # database lock path.
        record = None
        if job.file_registry_id is not None:
            record = (
                db.query(FileRegistry)
                .filter(FileRegistry.id == job.file_registry_id)
                .with_for_update()
                .one_or_none()
            )

        intelligence_object = (
            db.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.id == job.intelligence_object_id
            )
            .with_for_update()
            .one_or_none()
        )
        if intelligence_object is None:
            return

        metadata_prefix = str(projection["metadata_prefix"])
        object_status_field = str(projection["object_status_field"])
        record_prefix = str(projection["record_metadata_prefix"])
        metadata = (
            dict(intelligence_object.metadata_json)
            if isinstance(intelligence_object.metadata_json, dict)
            else {}
        )
        record_metadata = (
            dict(record.meta)
            if record is not None and isinstance(record.meta, dict)
            else {}
        )
        current_job_id = str(
            metadata.get(f"{metadata_prefix}_job_id") or ""
        ).strip()
        record_job_id = str(
            record_metadata.get(f"{record_prefix}_job_id") or ""
        ).strip()
        current_status = str(
            getattr(intelligence_object, object_status_field, "") or ""
        ).strip().lower()

        # Never allow an older terminal execution to overwrite a newer job or
        # a ready artifact that has already converged successfully. Both
        # materialized projections are checked before either one is mutated.
        if current_job_id and current_job_id != str(job.job_id):
            return
        if record_job_id and record_job_id != str(job.job_id):
            return
        if current_status == "ready":
            return

        setattr(intelligence_object, object_status_field, "failed")
        intelligence_object.error_message = str(job.failure_message or "") or None
        metadata.update({
            f"{metadata_prefix}_status": "failed",
            f"{metadata_prefix}_job_id": str(job.job_id),
            f"{metadata_prefix}_job_status": "failed",
            f"{metadata_prefix}_failure_code": str(job.failure_code or ""),
            f"{metadata_prefix}_failure_message": str(job.failure_message or ""),
            f"{metadata_prefix}_failed_at": now.isoformat(),
        })
        intelligence_object.metadata_json = metadata

        if record is None:
            return

        record_metadata.update({
            f"{record_prefix}_status": "failed",
            f"{record_prefix}_job_id": str(job.job_id),
            f"{record_prefix}_job_status": "failed",
            f"{record_prefix}_failure_code": str(job.failure_code or ""),
            f"{record_prefix}_failure_message": str(job.failure_message or ""),
            f"{record_prefix}_failed_at": now.isoformat(),
        })
        record.meta = record_metadata

    @contextmanager
    def _transaction(
        self,
        session: Optional[Session] = None,
    ) -> Iterator[Session]:
        owns_session = session is None
        db = session or self._session_factory()

        if not owns_session:
            try:
                yield db
                db.flush()
            except Exception:
                # The caller owns commit/rollback. We intentionally do not
                # roll back its outer transaction here.
                raise
            return

        try:
            with db.begin():
                yield db
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @contextmanager
    def _read_session(self) -> Iterator[Session]:
        db = self._session_factory()
        try:
            yield db
        finally:
            db.close()

    def _locked_job(
        self,
        db: Session,
        job_id: str,
    ) -> IntelligenceJob:
        normalized_job_id = _bounded_text("job_id", job_id, 64)
        job = (
            db.query(IntelligenceJob)
            .filter(IntelligenceJob.job_id == normalized_job_id)
            .with_for_update()
            .one_or_none()
        )
        if job is None:
            raise IntelligenceJobNotFound(
                f"Intelligence job not found: {normalized_job_id}"
            )
        return job

    def _require_active_lease(
        self,
        job: IntelligenceJob,
        *,
        worker_id: str,
        lease_token: str,
        now: datetime,
        allowed_statuses: Sequence[str],
    ) -> None:
        worker = _bounded_text("worker_id", worker_id, 128)
        token = _bounded_text("lease_token", lease_token, 64)

        if job.status not in tuple(allowed_statuses):
            raise IntelligenceJobStateConflict(
                f"Job {job.job_id} is {job.status}; active lease operation "
                "is not permitted."
            )
        if job.worker_id != worker or job.lease_token != token:
            raise IntelligenceJobLeaseConflict(
                f"Worker does not own the active lease for job {job.job_id}."
            )
        if job.lease_expires_at is None:
            raise IntelligenceJobLeaseConflict(
                f"Job {job.job_id} has no active lease expiry."
            )
        if _ensure_utc(job.lease_expires_at) <= _ensure_utc(now):
            raise IntelligenceJobLeaseConflict(
                f"Lease expired for intelligence job {job.job_id}."
            )

    @staticmethod
    def _clear_lease(job: IntelligenceJob) -> None:
        job.worker_id = None
        job.lease_token = None
        job.lease_expires_at = None
        job.heartbeat_at = None

    @staticmethod
    def _append_event(
        db: Session,
        *,
        job: IntelligenceJob,
        event_type: str,
        stage: Optional[str] = None,
        from_status: Optional[str] = None,
        to_status: Optional[str] = None,
        worker_id: Optional[str] = None,
        lease_token: Optional[str] = None,
        request_id: Optional[str] = None,
        case_id: Optional[str] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> IntelligenceJobEvent:
        event = IntelligenceJobEvent(
            job_id=job.job_id,
            event_type=_bounded_text("event_type", event_type, 64),
            stage=_optional_bounded_text("stage", stage, 128),
            from_status=_optional_text(from_status),
            to_status=_optional_text(to_status),
            attempt_number=int(job.attempt_count or 0),
            worker_id=(
                _bounded_text("worker_id", worker_id, 128)
                if worker_id is not None
                else None
            ),
            lease_token=(
                _bounded_text("lease_token", lease_token, 64)
                if lease_token is not None
                else None
            ),
            request_id=(
                _optional_text(request_id)
                if request_id is not None
                else job.request_id
            ),
            case_id=(
                _optional_text(case_id)
                if case_id is not None
                else job.case_id
            ),
            message=_optional_text(message),
            details_json=deepcopy(details),
        )
        db.add(event)
        return event


def _build_replay_execution_idempotency_key(
    *,
    semantic_idempotency_key: str,
    predecessor_job_id: str,
) -> str:
    """Return one deterministic unique key for the next execution generation."""

    encoded = (
        f"{_required_text('semantic_idempotency_key', semantic_idempotency_key)}|"
        f"{_required_text('predecessor_job_id', predecessor_job_id)}"
    ).encode("utf-8")
    return f"intelligence-job-replay:{hashlib.sha256(encoded).hexdigest()}"


def _validate_enqueue_spec(
    spec: IntelligenceJobEnqueueSpec,
) -> IntelligenceJobEnqueueSpec:
    if not isinstance(spec, IntelligenceJobEnqueueSpec):
        raise TypeError("spec must be IntelligenceJobEnqueueSpec")

    request_class = _bounded_text(
        "request_class",
        spec.request_class,
        32,
    )
    if request_class != INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND:
        raise ValueError(
            "Durable Intelligence Spool jobs must use request_class="
            f"{INTELLIGENCE_JOB_REQUEST_CLASS_BACKGROUND!r}. Interactive "
            "requests use the SIS live execution contract instead."
        )

    max_attempts = _positive_int("max_attempts", spec.max_attempts)
    priority = int(spec.priority)
    if priority < 0:
        raise ValueError("priority must be >= 0")

    target_version = spec.target_version
    if target_version is not None:
        target_version = _non_negative_int(
            "target_version",
            target_version,
        )

    return IntelligenceJobEnqueueSpec(
        job_type=_bounded_text("job_type", spec.job_type, 128),
        artifact_type=(
            _bounded_text("artifact_type", spec.artifact_type, 128)
            if spec.artifact_type is not None
            else None
        ),
        target_type=_bounded_text("target_type", spec.target_type, 32),
        target_id=_bounded_text("target_id", spec.target_id, 128),
        trigger_type=_bounded_text(
            "trigger_type",
            spec.trigger_type,
            64,
        ),
        idempotency_key=_bounded_text(
            "idempotency_key",
            spec.idempotency_key,
            191,
        ),
        target_version=target_version,
        source_hash=(
            _bounded_text("source_hash", spec.source_hash, 128)
            if spec.source_hash is not None
            else None
        ),
        trigger_ref=(
            _bounded_text("trigger_ref", spec.trigger_ref, 128)
            if spec.trigger_ref is not None
            else None
        ),
        request_class=request_class,
        priority=priority,
        user_id=spec.user_id,
        organization_id=(
            _bounded_text("organization_id", spec.organization_id, 64)
            if spec.organization_id is not None
            else None
        ),
        file_registry_id=spec.file_registry_id,
        intelligence_object_id=spec.intelligence_object_id,
        request_id=(
            _bounded_text("request_id", spec.request_id, 64)
            if spec.request_id is not None
            else None
        ),
        case_id=(
            _bounded_text("case_id", spec.case_id, 64)
            if spec.case_id is not None
            else None
        ),
        payload=deepcopy(spec.payload),
        processor_key=(
            _bounded_text("processor_key", spec.processor_key, 128)
            if spec.processor_key is not None
            else None
        ),
        processor_version=(
            _bounded_text(
                "processor_version",
                spec.processor_version,
                64,
            )
            if spec.processor_version is not None
            else None
        ),
        model_key=(
            _bounded_text("model_key", spec.model_key, 128)
            if spec.model_key is not None
            else None
        ),
        max_attempts=max_attempts,
        available_at=(
            _ensure_utc(spec.available_at)
            if spec.available_at is not None
            else None
        ),
    )


def _snapshot_job(job: IntelligenceJob) -> IntelligenceJobSnapshot:
    return IntelligenceJobSnapshot(
        job_id=str(job.job_id),
        job_type=str(job.job_type),
        artifact_type=_optional_text(job.artifact_type),
        request_class=str(job.request_class),
        priority=int(job.priority or 0),
        status=str(job.status),
        idempotency_key=str(job.idempotency_key),
        target_type=str(job.target_type),
        target_id=str(job.target_id),
        target_version=job.target_version,
        source_hash=_optional_text(job.source_hash),
        trigger_type=str(job.trigger_type),
        trigger_ref=_optional_text(job.trigger_ref),
        user_id=job.user_id,
        organization_id=_optional_text(job.organization_id),
        file_registry_id=job.file_registry_id,
        intelligence_object_id=job.intelligence_object_id,
        request_id=_optional_text(job.request_id),
        case_id=_optional_text(job.case_id),
        payload=deepcopy(job.payload_json),
        result=deepcopy(job.result_json),
        processor_key=_optional_text(job.processor_key),
        processor_version=_optional_text(job.processor_version),
        model_key=_optional_text(job.model_key),
        attempt_count=int(job.attempt_count or 0),
        max_attempts=int(job.max_attempts or 0),
        available_at=job.available_at,
        worker_id=_optional_text(job.worker_id),
        lease_token=_optional_text(job.lease_token),
        lease_expires_at=job.lease_expires_at,
        heartbeat_at=job.heartbeat_at,
        claimed_at=job.claimed_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        failure_code=_optional_text(job.failure_code),
        failure_message=_optional_text(job.failure_message),
        last_error_at=job.last_error_at,
        cancel_reason=_optional_text(job.cancel_reason),
        superseded_by_job_id=_optional_text(job.superseded_by_job_id),
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


def _snapshot_event(
    event: IntelligenceJobEvent,
) -> IntelligenceJobEventSnapshot:
    return IntelligenceJobEventSnapshot(
        event_id=str(event.event_id),
        job_id=str(event.job_id),
        event_type=str(event.event_type),
        stage=_optional_text(event.stage),
        from_status=_optional_text(event.from_status),
        to_status=_optional_text(event.to_status),
        attempt_number=event.attempt_number,
        worker_id=_optional_text(event.worker_id),
        lease_token=_optional_text(event.lease_token),
        request_id=_optional_text(event.request_id),
        case_id=_optional_text(event.case_id),
        message=_optional_text(event.message),
        details=deepcopy(event.details_json),
        created_at=event.created_at,
    )


def _normalize_job_types(
    job_types: Optional[Sequence[str]],
) -> List[str]:
    if not job_types:
        return []
    normalized = []
    seen = set()
    for value in job_types:
        item = _bounded_text("job_type", value, 128)
        if item not in seen:
            normalized.append(item)
            seen.add(item)
    return normalized


def _database_utc_now(db: Session) -> datetime:
    """Read the canonical lease clock from the master database.

    MySQL uses UTC_TIMESTAMP explicitly so SIS may move to another host without
    worker clock skew changing lease behavior. Other supported development
    databases fall back to CURRENT_TIMESTAMP.
    """

    bind = db.get_bind()
    dialect_name = str(getattr(bind.dialect, "name", "") or "").lower()
    expression = (
        func.utc_timestamp()
        if dialect_name in {"mysql", "mariadb"}
        else func.current_timestamp()
    )
    value = db.execute(select(expression)).scalar_one()
    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return _ensure_utc(value)


def _optional_bounded_text(
    name: str,
    value: Any,
    maximum: int,
) -> Optional[str]:
    text = _optional_text(value)
    if text is None:
        return None
    if len(text) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    return text


def _optional_progress_percent(value: Any) -> Optional[int]:
    if value is None or isinstance(value, bool):
        return None
    try:
        progress = int(value)
    except (TypeError, ValueError):
        return None
    if progress < 0 or progress > 100:
        return None
    return progress


def _ensure_utc(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise TypeError("timestamp must be a datetime")
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _required_text(name: str, value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} is required")
    return text


def _optional_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _bounded_text(name: str, value: Any, maximum: int) -> str:
    text = _required_text(name, value)
    if len(text) > maximum:
        raise ValueError(f"{name} exceeds {maximum} characters")
    return text


def _positive_int(name: str, value: Any) -> int:
    integer = int(value)
    if integer <= 0:
        raise ValueError(f"{name} must be > 0")
    return integer


def _non_negative_int(name: str, value: Any) -> int:
    integer = int(value)
    if integer < 0:
        raise ValueError(f"{name} must be >= 0")
    return integer

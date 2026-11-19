# -------------------------------------------------------------------
# FILE: intelligence_spool_worker.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# SIS-owned durable Intelligence Spool dispatcher.
#
# The master SQL database is the queue authority. This module owns only the
# process-local worker lifecycle that polls, claims, heartbeats, and executes
# registered background processors. It never owns web/application lifecycle,
# file permissions, or user authority.
# -------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import os
import socket
from threading import Event, RLock, Thread, current_thread
import time
from typing import Any, Callable, Dict, Mapping, Optional
import uuid

from config import settings
from solomon_core.intelligence_service.intelligence_service_client import (
    request_intelligence_service_recovery,
)
from solomon_core.logger import get_logger

from .intelligence_job_repository import (
    IntelligenceJobLeaseConflict,
    IntelligenceJobRepository,
    IntelligenceJobSnapshot,
    IntelligenceJobStateConflict,
)
from .intelligence_completion_events import (
    publish_intelligence_completion_event,
)


logger = get_logger("intelligence_service.spool_worker")


@dataclass(frozen=True)
class IntelligenceJobProcessorResult:
    """Successful durable result returned by one registered job processor."""

    result: Optional[Dict[str, Any]] = None
    intelligence_object_id: Optional[int] = None
    stage: str = "completed"


class IntelligenceJobProcessorError(RuntimeError):
    """Base controlled failure raised by an Intelligence Spool processor."""

    def __init__(
        self,
        message: str,
        *,
        failure_code: str,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(str(message or "Intelligence processor failed."))
        self.failure_code = str(failure_code or "processor_failure").strip()
        self.stage = str(stage).strip() if stage else None
        self.details = dict(details or {})


class IntelligenceJobRetryableError(IntelligenceJobProcessorError):
    """Controlled processor failure that should consume the retry policy."""

    def __init__(
        self,
        message: str,
        *,
        failure_code: str,
        retry_delay_seconds: Optional[int] = None,
        stage: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message,
            failure_code=failure_code,
            stage=stage,
            details=details,
        )
        self.retry_delay_seconds = retry_delay_seconds


class IntelligenceJobTerminalError(IntelligenceJobProcessorError):
    """Controlled processor failure that must not be retried."""


@dataclass(frozen=True)
class IntelligenceJobExecutionContext:
    """Lease-scoped execution context exposed to one background processor."""

    job: IntelligenceJobSnapshot
    repository: IntelligenceJobRepository
    worker_id: str
    lease_token: str
    lease_lost: Event
    service_stopping: Event

    def record_stage(
        self,
        stage: str,
        *,
        progress_percent: Optional[int] = None,
        message: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.raise_if_execution_invalid()
        event_details = dict(details or {})
        normalized_progress = _normalize_stage_progress(progress_percent)
        if normalized_progress is not None:
            event_details["progress_percent"] = normalized_progress

        self.repository.record_stage(
            job_id=self.job.job_id,
            worker_id=self.worker_id,
            lease_token=self.lease_token,
            stage=stage,
            message=message,
            details=event_details or None,
        )

        if normalized_progress is not None:
            logger.info(
                "[SIS][SPOOL_JOB_PROGRESS] job_id=%s job_type=%s "
                "status=running progress=%s%% stage=%s attempt=%s/%s",
                self.job.job_id,
                self.job.job_type,
                normalized_progress,
                stage,
                self.job.attempt_count,
                self.job.max_attempts,
            )

    def raise_if_execution_invalid(self) -> None:
        if self.lease_lost.is_set():
            raise IntelligenceJobLeaseConflict(
                f"Worker lease was lost for intelligence job {self.job.job_id}."
            )
        if self.service_stopping.is_set():
            raise IntelligenceJobRetryableError(
                "SIS is stopping before the intelligence job completed.",
                failure_code="sis_stopping",
                retry_delay_seconds=0,
                stage="shutdown",
            )


IntelligenceJobProcessor = Callable[
    [IntelligenceJobExecutionContext],
    IntelligenceJobProcessorResult,
]
IntelligenceJobAvailability = Callable[[], bool]


@dataclass(frozen=True)
class _ProcessorRegistration:
    job_type: str
    processor: IntelligenceJobProcessor
    available: Optional[IntelligenceJobAvailability]


class IntelligenceSpoolWorker:
    """One SIS-owned dispatcher for durable asynchronous intelligence jobs.

    The worker processes one claimed job at a time today. Multiple SIS workers
    can later use the same repository contract because claims are protected by
    database row locks and leases. Only job types with a registered processor
    whose availability predicate is true are eligible for claim.
    """

    def __init__(
        self,
        *,
        repository: Optional[IntelligenceJobRepository] = None,
        worker_id: Optional[str] = None,
    ) -> None:
        self._repository = repository or IntelligenceJobRepository()
        self._worker_id = worker_id or _build_worker_id()
        self._stop_event = Event()
        self._state_lock = RLock()
        self._registrations: Dict[str, _ProcessorRegistration] = {}
        self._thread: Optional[Thread] = None
        self._observability_thread: Optional[Thread] = None
        self._state: Dict[str, Any] = {
            "enabled": bool(settings.SIS_SPOOL_WORKER_ENABLED),
            "running": False,
            "status": "stopped",
            "worker_id": self._worker_id,
            "supported_job_types": [],
            "eligible_job_types": [],
            "current_job_id": None,
            "current_job_type": None,
            "processed_jobs": 0,
            "succeeded_jobs": 0,
            "retried_jobs": 0,
            "failed_jobs": 0,
            "recovered_leases": 0,
            "last_poll_at": None,
            "last_claim_at": None,
            "last_completed_at": None,
            "last_recovery_at": None,
            "last_observability_at": None,
            "last_observability_error": "",
            "operational_snapshot": {},
            "last_error": "",
            "updated_at": _utc_now_iso(),
        }

    @property
    def worker_id(self) -> str:
        return self._worker_id

    def register_processor(
        self,
        job_type: str,
        processor: IntelligenceJobProcessor,
        *,
        available: Optional[IntelligenceJobAvailability] = None,
    ) -> None:
        normalized_type = _normalize_job_type(job_type)
        if not callable(processor):
            raise TypeError("processor must be callable")
        if available is not None and not callable(available):
            raise TypeError("available must be callable when provided")

        with self._state_lock:
            if normalized_type in self._registrations:
                raise ValueError(
                    f"Processor already registered for job type {normalized_type!r}."
                )
            self._registrations[normalized_type] = _ProcessorRegistration(
                job_type=normalized_type,
                processor=processor,
                available=available,
            )
            self._refresh_registration_state_locked()

    def start(self) -> bool:
        if not bool(settings.SIS_SPOOL_WORKER_ENABLED):
            self._update_state(status="disabled", running=False)
            logger.info("[SIS][SPOOL_WORKER_DISABLED]")
            return False

        with self._state_lock:
            if self._thread is not None and self._thread.is_alive():
                return False
            self._stop_event.clear()
            self._state.update({
                "running": True,
                "status": "starting",
                "last_error": "",
                "updated_at": _utc_now_iso(),
            })
            self._thread = Thread(
                target=self._run,
                name="sis-intelligence-spool",
                daemon=True,
            )
            self._observability_thread = Thread(
                target=self._observability_loop,
                name="sis-intelligence-spool-observer",
                daemon=True,
            )
            self._thread.start()
            self._observability_thread.start()

        logger.info(
            "[SIS][SPOOL_WORKER_STARTED] worker_id=%s poll_seconds=%s "
            "lease_seconds=%s heartbeat_seconds=%s observability_poll_seconds=%s",
            self._worker_id,
            settings.SIS_SPOOL_POLL_INTERVAL_SECONDS,
            settings.SIS_SPOOL_LEASE_SECONDS,
            settings.SIS_SPOOL_HEARTBEAT_INTERVAL_SECONDS,
            settings.SIS_SPOOL_OBSERVABILITY_POLL_SECONDS,
        )
        return True

    def stop(self, *, wait: bool = True) -> None:
        self._stop_event.set()
        thread = self._thread
        if (
            wait
            and thread is not None
            and thread.is_alive()
            and thread is not current_thread()
        ):
            thread.join(
                timeout=max(
                    1.0,
                    float(settings.SIS_SPOOL_SHUTDOWN_TIMEOUT_SECONDS),
                )
            )

        observer_thread = self._observability_thread
        if (
            wait
            and observer_thread is not None
            and observer_thread.is_alive()
            and observer_thread is not current_thread()
        ):
            observer_thread.join(
                timeout=max(
                    1.0,
                    min(
                        float(settings.SIS_SPOOL_SHUTDOWN_TIMEOUT_SECONDS),
                        float(settings.SIS_SPOOL_OBSERVABILITY_POLL_SECONDS) + 1.0,
                    ),
                )
            )

        running = bool(thread is not None and thread.is_alive())
        self._update_state(
            running=running,
            status="stopping" if running else "stopped",
        )
        logger.info(
            "[SIS][SPOOL_WORKER_STOPPED] worker_id=%s running=%s",
            self._worker_id,
            running,
        )

    def get_snapshot(self) -> Dict[str, Any]:
        with self._state_lock:
            snapshot = dict(self._state)
            snapshot["supported_job_types"] = list(
                snapshot.get("supported_job_types") or []
            )
            snapshot["eligible_job_types"] = list(
                snapshot.get("eligible_job_types") or []
            )
            operational = dict(snapshot.get("operational_snapshot") or {})
            operational["status_counts"] = dict(
                operational.get("status_counts") or {}
            )
            operational["active_jobs"] = [
                dict(item)
                for item in operational.get("active_jobs") or []
            ]
            snapshot["operational_snapshot"] = operational
            return snapshot

    def _run(self) -> None:
        next_recovery_monotonic = 0.0
        self._update_state(status="idle", running=True)

        try:
            while not self._stop_event.is_set():
                now_monotonic = time.monotonic()
                if now_monotonic >= next_recovery_monotonic:
                    self._recover_expired_leases()
                    next_recovery_monotonic = (
                        time.monotonic()
                        + max(
                            1.0,
                            float(settings.SIS_SPOOL_RECOVERY_INTERVAL_SECONDS),
                        )
                    )

                eligible_job_types = self._eligible_job_types()
                self._update_state(
                    status="idle",
                    eligible_job_types=eligible_job_types,
                    last_poll_at=_utc_now_iso(),
                )

                # claim_next(job_types=[]) intentionally means "all types" at
                # the repository layer, so an empty registry must never call it.
                if not eligible_job_types:
                    self._wait_for_next_poll()
                    continue

                try:
                    job = self._repository.claim_next(
                        worker_id=self._worker_id,
                        lease_seconds=int(settings.SIS_SPOOL_LEASE_SECONDS),
                        job_types=eligible_job_types,
                    )
                except Exception as exc:
                    logger.exception("[SIS][SPOOL_CLAIM_FAILURE]")
                    self._update_state(
                        status="degraded",
                        last_error=str(exc),
                    )
                    self._wait_for_next_poll()
                    continue

                if job is None:
                    self._wait_for_next_poll()
                    continue

                self._update_state(
                    status="running_job",
                    current_job_id=job.job_id,
                    current_job_type=job.job_type,
                    last_claim_at=_utc_now_iso(),
                    last_error="",
                )
                self._process_claimed_job(job)
                self._update_state(
                    current_job_id=None,
                    current_job_type=None,
                    status="idle",
                    last_completed_at=_utc_now_iso(),
                )
        except Exception as exc:
            logger.exception("[SIS][SPOOL_WORKER_FAILURE]")
            self._update_state(
                running=False,
                status="failed",
                last_error=str(exc),
            )
            return

        self._update_state(running=False, status="stopped")

    def _process_claimed_job(self, job: IntelligenceJobSnapshot) -> None:
        registration = self._registration_for(job.job_type)
        if registration is None:
            # This should be unreachable because claim filters use the current
            # eligible registry. Leaving the lease untouched is safer than
            # manufacturing a state transition without a processor contract;
            # normal lease recovery will make it eligible again later.
            logger.error(
                "[SIS][SPOOL_PROCESSOR_MISSING_AFTER_CLAIM] "
                "job_id=%s job_type=%s",
                job.job_id,
                job.job_type,
            )
            self._increment_counter("failed_jobs")
            return

        try:
            running_job = self._repository.start(
                job_id=job.job_id,
                worker_id=self._worker_id,
                lease_token=str(job.lease_token or ""),
                stage="worker_dispatch",
                details={"progress_percent": 5},
            )
            logger.info(
                "[SIS][SPOOL_JOB_PROGRESS] job_id=%s job_type=%s "
                "status=running progress=5%% stage=worker_dispatch attempt=%s/%s",
                running_job.job_id,
                running_job.job_type,
                running_job.attempt_count,
                running_job.max_attempts,
            )
        except Exception as exc:
            logger.exception(
                "[SIS][SPOOL_START_FAILURE] job_id=%s job_type=%s",
                job.job_id,
                job.job_type,
            )
            self._update_state(last_error=str(exc))
            self._increment_counter("failed_jobs")
            return

        lease_lost = Event()
        heartbeat_stop = Event()
        heartbeat_thread = Thread(
            target=self._heartbeat_loop,
            kwargs={
                "job": running_job,
                "lease_lost": lease_lost,
                "heartbeat_stop": heartbeat_stop,
            },
            name=f"sis-job-heartbeat-{running_job.job_id[:8]}",
            daemon=True,
        )
        heartbeat_thread.start()

        context = IntelligenceJobExecutionContext(
            job=running_job,
            repository=self._repository,
            worker_id=self._worker_id,
            lease_token=str(running_job.lease_token or ""),
            lease_lost=lease_lost,
            service_stopping=self._stop_event,
        )

        try:
            context.raise_if_execution_invalid()
            result = registration.processor(context)
            if not isinstance(result, IntelligenceJobProcessorResult):
                raise TypeError(
                    "Intelligence job processor must return "
                    "IntelligenceJobProcessorResult."
                )
            context.raise_if_execution_invalid()
            completed_job = self._repository.succeed(
                job_id=running_job.job_id,
                worker_id=self._worker_id,
                lease_token=context.lease_token,
                result=result.result,
                intelligence_object_id=result.intelligence_object_id,
                stage=result.stage,
            )
            logger.info(
                "[SIS][SPOOL_JOB_PROGRESS] job_id=%s job_type=%s "
                "status=succeeded progress=100%% stage=%s attempt=%s/%s",
                completed_job.job_id,
                completed_job.job_type,
                result.stage,
                completed_job.attempt_count,
                completed_job.max_attempts,
            )

            # Publish only after the repository has durably committed the
            # succeeded transition. The event is a change signal, not file
            # authority; downstream web consumers must reauthorize state.
            result_payload = (
                dict(result.result)
                if isinstance(result.result, Mapping)
                else {}
            )
            try:
                publish_intelligence_completion_event(
                    job_id=completed_job.job_id,
                    job_type=completed_job.job_type,
                    document_id=str(result_payload.get("document_id") or ""),
                    intelligence_object_id=result.intelligence_object_id,
                    stage=result.stage,
                )
            except Exception:
                # Notification transport must never roll back or retry a job
                # that has already committed its durable succeeded state.
                logger.exception(
                    "[SIS][COMPLETION_EVENT_PUBLISH_FAILURE] job_id=%s job_type=%s",
                    completed_job.job_id,
                    completed_job.job_type,
                )
            self._increment_counter("succeeded_jobs")
        except IntelligenceJobRetryableError as exc:
            self._handle_retryable_failure(context, exc)
        except IntelligenceJobTerminalError as exc:
            self._handle_terminal_failure(context, exc)
        except (IntelligenceJobLeaseConflict, IntelligenceJobStateConflict) as exc:
            logger.warning(
                "[SIS][SPOOL_LEASE_OR_STATE_LOST] job_id=%s error=%s",
                running_job.job_id,
                exc,
            )
            self._update_state(last_error=str(exc))
        except Exception as exc:
            logger.exception(
                "[SIS][SPOOL_PROCESSOR_EXCEPTION] job_id=%s job_type=%s",
                running_job.job_id,
                running_job.job_type,
            )
            self._handle_retryable_failure(
                context,
                IntelligenceJobRetryableError(
                    str(exc) or "Unhandled intelligence processor exception.",
                    failure_code="processor_exception",
                    retry_delay_seconds=int(
                        settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS
                    ),
                    stage="processor",
                ),
            )
        finally:
            heartbeat_stop.set()
            heartbeat_thread.join(
                timeout=max(
                    1.0,
                    min(
                        float(settings.SIS_SPOOL_HEARTBEAT_INTERVAL_SECONDS),
                        5.0,
                    ),
                )
            )
            self._increment_counter("processed_jobs")

    def _handle_retryable_failure(
        self,
        context: IntelligenceJobExecutionContext,
        exc: IntelligenceJobRetryableError,
    ) -> None:
        if context.lease_lost.is_set():
            logger.warning(
                "[SIS][SPOOL_RETRY_SKIPPED_LEASE_LOST] job_id=%s",
                context.job.job_id,
            )
            return

        retry_delay = (
            int(exc.retry_delay_seconds)
            if exc.retry_delay_seconds is not None
            else int(settings.SIS_SPOOL_DEFAULT_RETRY_DELAY_SECONDS)
        )
        try:
            snapshot = self._repository.retry(
                job_id=context.job.job_id,
                worker_id=context.worker_id,
                lease_token=context.lease_token,
                failure_code=exc.failure_code,
                failure_message=str(exc),
                retry_delay_seconds=max(0, retry_delay),
                stage=exc.stage,
                details=exc.details,
            )
        except (IntelligenceJobLeaseConflict, IntelligenceJobStateConflict) as conflict:
            logger.warning(
                "[SIS][SPOOL_RETRY_CONFLICT] job_id=%s error=%s",
                context.job.job_id,
                conflict,
            )
            self._update_state(last_error=str(conflict))
            return

        if snapshot.status == "failed":
            logger.warning(
                "[SIS][SPOOL_JOB_STATE] job_id=%s job_type=%s status=failed "
                "stage=%s attempt=%s/%s failure_code=%s",
                snapshot.job_id,
                snapshot.job_type,
                exc.stage or "-",
                snapshot.attempt_count,
                snapshot.max_attempts,
                exc.failure_code,
            )
            self._increment_counter("failed_jobs")
        else:
            logger.warning(
                "[SIS][SPOOL_JOB_STATE] job_id=%s job_type=%s status=retry_wait "
                "stage=%s attempt=%s/%s retry_delay_seconds=%s failure_code=%s",
                snapshot.job_id,
                snapshot.job_type,
                exc.stage or "-",
                snapshot.attempt_count,
                snapshot.max_attempts,
                max(0, retry_delay),
                exc.failure_code,
            )
            self._increment_counter("retried_jobs")

    def _handle_terminal_failure(
        self,
        context: IntelligenceJobExecutionContext,
        exc: IntelligenceJobTerminalError,
    ) -> None:
        if context.lease_lost.is_set():
            logger.warning(
                "[SIS][SPOOL_FAIL_SKIPPED_LEASE_LOST] job_id=%s",
                context.job.job_id,
            )
            return

        try:
            snapshot = self._repository.fail(
                job_id=context.job.job_id,
                worker_id=context.worker_id,
                lease_token=context.lease_token,
                failure_code=exc.failure_code,
                failure_message=str(exc),
                stage=exc.stage,
                details=exc.details,
            )
            logger.warning(
                "[SIS][SPOOL_JOB_STATE] job_id=%s job_type=%s status=failed "
                "stage=%s attempt=%s/%s failure_code=%s",
                snapshot.job_id,
                snapshot.job_type,
                exc.stage or "-",
                snapshot.attempt_count,
                snapshot.max_attempts,
                exc.failure_code,
            )
            self._increment_counter("failed_jobs")
        except (IntelligenceJobLeaseConflict, IntelligenceJobStateConflict) as conflict:
            logger.warning(
                "[SIS][SPOOL_FAIL_CONFLICT] job_id=%s error=%s",
                context.job.job_id,
                conflict,
            )
            self._update_state(last_error=str(conflict))

    def _observability_loop(self) -> None:
        poll_seconds = max(
            1.0,
            float(settings.SIS_SPOOL_OBSERVABILITY_POLL_SECONDS),
        )
        heartbeat_seconds = max(
            poll_seconds,
            float(settings.SIS_SPOOL_OBSERVABILITY_HEARTBEAT_SECONDS),
        )
        last_signature: Optional[tuple[Any, ...]] = None
        last_log_monotonic = 0.0
        last_error = ""

        while not self._stop_event.is_set():
            try:
                snapshot = self._repository.get_operational_snapshot()
                last_error = ""
            except Exception as exc:
                error_text = f"{type(exc).__name__}: {exc}"
                if error_text != last_error:
                    logger.exception("[SIS][SPOOL_OBSERVABILITY_FAILURE]")
                    last_error = error_text
                self._update_state(
                    last_observability_at=_utc_now_iso(),
                    last_observability_error=error_text,
                )
                if self._stop_event.wait(poll_seconds):
                    return
                continue

            self._update_state(
                operational_snapshot=snapshot,
                last_observability_at=str(snapshot.get("observed_at") or ""),
                last_observability_error="",
            )

            if int(snapshot.get("unfinished") or 0) > 0:
                # Pending durable intelligence is recovery demand, not permission
                # for this worker to probe SIS directly. The Flask-owned health
                # monitor coalesces the signal and owns the remote cadence.
                request_intelligence_service_recovery()

            signature = _operational_snapshot_signature(snapshot)
            now_monotonic = time.monotonic()
            active_work = int(snapshot.get("in_flight") or 0) > 0
            should_log = (
                signature != last_signature
                or last_log_monotonic <= 0.0
                or (
                    active_work
                    and now_monotonic - last_log_monotonic >= heartbeat_seconds
                )
            )

            if should_log:
                _log_operational_snapshot(snapshot)
                last_signature = signature
                last_log_monotonic = now_monotonic

            if self._stop_event.wait(poll_seconds):
                return

    def _heartbeat_loop(
        self,
        *,
        job: IntelligenceJobSnapshot,
        lease_lost: Event,
        heartbeat_stop: Event,
    ) -> None:
        interval = max(
            1.0,
            float(settings.SIS_SPOOL_HEARTBEAT_INTERVAL_SECONDS),
        )
        while not heartbeat_stop.wait(interval):
            try:
                self._repository.renew_lease(
                    job_id=job.job_id,
                    worker_id=self._worker_id,
                    lease_token=str(job.lease_token or ""),
                    lease_seconds=int(settings.SIS_SPOOL_LEASE_SECONDS),
                )
            except Exception as exc:
                lease_lost.set()
                logger.warning(
                    "[SIS][SPOOL_HEARTBEAT_LOST] job_id=%s error=%s",
                    job.job_id,
                    exc,
                )
                self._update_state(last_error=str(exc))
                return

    def _recover_expired_leases(self) -> None:
        try:
            recovered = self._repository.recover_expired_leases(
                limit=int(settings.SIS_SPOOL_RECOVERY_LIMIT),
                retry_delay_seconds=int(
                    settings.SIS_SPOOL_RECOVERY_RETRY_DELAY_SECONDS
                ),
            )
        except Exception as exc:
            logger.exception("[SIS][SPOOL_RECOVERY_FAILURE]")
            self._update_state(
                status="degraded",
                last_error=str(exc),
                last_recovery_at=_utc_now_iso(),
            )
            return

        if recovered:
            self._increment_counter("recovered_leases", len(recovered))
            logger.warning(
                "[SIS][SPOOL_LEASES_RECOVERED] count=%s worker_id=%s",
                len(recovered),
                self._worker_id,
            )
        self._update_state(last_recovery_at=_utc_now_iso())

    def _eligible_job_types(self) -> list[str]:
        with self._state_lock:
            registrations = list(self._registrations.values())

        eligible: list[str] = []
        for registration in registrations:
            if registration.available is None:
                eligible.append(registration.job_type)
                continue
            try:
                if registration.available():
                    eligible.append(registration.job_type)
            except Exception as exc:
                logger.warning(
                    "[SIS][SPOOL_PROCESSOR_AVAILABILITY_FAILURE] "
                    "job_type=%s error=%s",
                    registration.job_type,
                    exc,
                )
                self._update_state(last_error=str(exc))

        eligible.sort()
        return eligible

    def _registration_for(
        self,
        job_type: str,
    ) -> Optional[_ProcessorRegistration]:
        with self._state_lock:
            return self._registrations.get(_normalize_job_type(job_type))

    def _wait_for_next_poll(self) -> None:
        self._stop_event.wait(
            max(0.1, float(settings.SIS_SPOOL_POLL_INTERVAL_SECONDS))
        )

    def _increment_counter(self, name: str, amount: int = 1) -> None:
        with self._state_lock:
            self._state[name] = int(self._state.get(name) or 0) + int(amount)
            self._state["updated_at"] = _utc_now_iso()

    def _update_state(self, **changes: Any) -> None:
        with self._state_lock:
            self._state.update(changes)
            self._refresh_registration_state_locked()
            self._state["updated_at"] = _utc_now_iso()

    def _refresh_registration_state_locked(self) -> None:
        self._state["supported_job_types"] = sorted(self._registrations.keys())


def _normalize_stage_progress(value: Optional[int]) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool):
        raise ValueError("progress_percent must be an integer from 0 through 99")
    progress = int(value)
    if progress < 0 or progress > 99:
        raise ValueError(
            "Processor stage progress_percent must be from 0 through 99; "
            "100 is reserved for the durable succeeded transition."
        )
    return progress


def _operational_snapshot_signature(
    snapshot: Mapping[str, Any],
) -> tuple[Any, ...]:
    active_signature = tuple(
        (
            str(item.get("job_id") or ""),
            str(item.get("job_type") or ""),
            str(item.get("status") or ""),
            item.get("progress_percent"),
            str(item.get("stage") or ""),
            int(item.get("attempt_count") or 0),
        )
        for item in snapshot.get("active_jobs") or []
    )
    return (
        int(snapshot.get("pending") or 0),
        int(snapshot.get("retry_wait") or 0),
        int(snapshot.get("claimed") or 0),
        int(snapshot.get("running") or 0),
        active_signature,
    )


def _log_operational_snapshot(snapshot: Mapping[str, Any]) -> None:
    active_parts = []
    for item in snapshot.get("active_jobs") or []:
        progress = item.get("progress_percent")
        progress_label = f"{int(progress)}%" if progress is not None else "--%"
        active_parts.append(
            f"{str(item.get('job_id') or '')[:8]}:"
            f"{str(item.get('job_type') or '-')}:"
            f"{str(item.get('status') or '-')}:"
            f"{progress_label}:"
            f"{str(item.get('stage') or '-')}"
        )
    active_text = ",".join(active_parts) if active_parts else "none"

    logger.info(
        "[SIS][SPOOL_STATUS] backlog=%s pending=%s retry_wait=%s "
        "in_flight=%s claimed=%s running=%s unfinished=%s active=%s",
        int(snapshot.get("backlog") or 0),
        int(snapshot.get("pending") or 0),
        int(snapshot.get("retry_wait") or 0),
        int(snapshot.get("in_flight") or 0),
        int(snapshot.get("claimed") or 0),
        int(snapshot.get("running") or 0),
        int(snapshot.get("unfinished") or 0),
        active_text,
    )


def _build_worker_id() -> str:
    hostname = socket.gethostname().strip() or "unknown-host"
    suffix = uuid.uuid4().hex[:8]
    return f"sis:{hostname}:{os.getpid()}:{suffix}"[:128]


def _normalize_job_type(value: str) -> str:
    normalized = str(value or "").strip()
    if not normalized:
        raise ValueError("job_type is required")
    if len(normalized) > 128:
        raise ValueError("job_type exceeds 128 characters")
    return normalized


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

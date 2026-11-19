# -------------------------------------------------------------------
# FILE: intelligence_service_client.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Bounded client used by Solomon application code to consume SIS without
# owning or supervising the SIS process lifecycle.
# -------------------------------------------------------------------

from __future__ import annotations

import json
import socket
import threading
import time
import uuid
from typing import Callable, Iterable
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request

from config import settings
from solomon_core.logger import get_logger
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionFailure,
    LLMExecutionInput,
    LLMExecutionResult,
    LLMFailureReason,
)

from .intelligence_service_contract import (
    IntelligencePriority,
    IntelligenceRequestClass,
    deserialize_embedding_result,
    deserialize_llm_result,
    serialize_compute_scheduling,
    serialize_embedding_input,
    serialize_llm_input,
)
from .intelligence_completion_events import (
    INTELLIGENCE_COMPLETION_EVENT_TYPE,
    INTELLIGENCE_RESYNC_EVENT_TYPE,
)
from .compute_capacity_repository import (
    persist_capacity_snapshot,
    persist_compute_execution_telemetry,
    persist_compute_request_event,
    persist_service_state_transition,
)


logger = get_logger("intelligence_service.client")
_SIS_KEY_HEADER = "X-Solomon-SIS-Key"
_COMPUTE_KEY_HEADER = "X-Solomon-SIS-Compute-Key"
_HEALTH_CACHE_LOCK = threading.Lock()
_HEALTH_CACHE_PAYLOAD: dict | None = None
_HEALTH_CACHE_EXPIRES_AT = 0.0
_HEALTH_PROBE_IN_FLIGHT = False
_HEALTH_MONITOR_LIFECYCLE_LOCK = threading.Lock()
_HEALTH_MONITOR_STOP = threading.Event()
_HEALTH_MONITOR_WAKE = threading.Event()
_HEALTH_MONITOR_THREAD: threading.Thread | None = None
_HEALTH_CONSECUTIVE_FAILURES = 0
_HEALTH_CIRCUIT_OPEN = True
_HEALTH_LAST_SUCCESS_AT: float | None = None
_HEALTH_LAST_FAILURE_AT: float | None = None
_HEALTH_LAST_SUCCESS_MONOTONIC: float | None = None
_HEALTH_LAST_FAILURE_MONOTONIC: float | None = None
_HEALTH_LAST_OBSERVATION_MONOTONIC: float | None = None
_HEALTH_RECOVERY_DEMAND_UNTIL_MONOTONIC = 0.0
_HEALTH_LAST_SOURCE = ""
_DURABLE_COMPLETION_LOCK = threading.Lock()
_DURABLE_COMPLETION_SEQUENCE_CURSOR: int | None = None
_DURABLE_COMPLETION_EVENT_ID = 0


def _new_compute_attempt_id() -> str:
    return uuid.uuid4().hex


def _transport_failure_code(exc: Exception) -> str:
    if isinstance(exc, (socket.timeout, TimeoutError)):
        return "transport_timeout"
    text = str(exc or "").strip().lower()
    if "timed out" in text or "timeout" in text:
        return "transport_timeout"
    return "transport_unavailable"


def _http_failure_code(status_code: int) -> str:
    status = int(status_code or 0)
    if status == 429:
        return "admission_rejected"
    if status == 503:
        return "service_unavailable"
    if 400 <= status < 500:
        return "http_client_error"
    if status >= 500:
        return "http_server_error"
    return "http_failure"


def _telemetry_outcome(telemetry: object) -> str:
    if isinstance(telemetry, dict) and telemetry:
        return "success" if bool(telemetry.get("success")) else "remote_failure"
    return "response_without_execution"


def _failure(reason: LLMFailureReason, message: str) -> LLMExecutionResult:
    return LLMExecutionResult(
        failure=LLMExecutionFailure(
            reason=reason,
            message=message,
        )
    )


def _remote_compute_enabled() -> bool:
    return str(settings.SIS_COMPUTE_MODE or "local").strip().lower() == "remote"


def get_intelligence_service_endpoint() -> str:
    """Return the one active SIS execution endpoint from config.py."""

    if _remote_compute_enabled():
        return str(settings.SIS_COMPUTE_BASE_URL or "").strip().rstrip("/")
    return str(settings.SIS_BASE_URL or "").strip().rstrip("/")


def _service_url(path: str) -> str:
    base_url = get_intelligence_service_endpoint()
    if not base_url:
        raise RuntimeError("The active SIS endpoint is not configured in config.py.")
    clean_path = "/" + str(path or "").strip().lstrip("/")
    return f"{base_url}{clean_path}"


def _request_headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    if _remote_compute_enabled():
        headers[_COMPUTE_KEY_HEADER] = str(
            settings.SIS_COMPUTE_SHARED_SECRET or ""
        )
    else:
        headers[_SIS_KEY_HEADER] = str(settings.SIS_SHARED_SECRET or "")
    return headers


def _connect_timeout_seconds() -> int:
    if _remote_compute_enabled():
        return max(1, int(settings.SIS_COMPUTE_CONNECT_TIMEOUT_SECONDS))
    return max(1, int(settings.SIS_CONNECT_TIMEOUT_SECONDS))


def _request_timeout_seconds() -> int:
    if _remote_compute_enabled():
        return max(1, int(settings.SIS_COMPUTE_REQUEST_TIMEOUT_SECONDS))
    return max(1, int(settings.SIS_REQUEST_TIMEOUT_SECONDS))


def _health_timeout_seconds() -> int:
    if _remote_compute_enabled():
        return max(1, int(settings.SIS_COMPUTE_HEALTH_TIMEOUT_SECONDS))
    return max(1, int(settings.SIS_HEALTH_TIMEOUT_SECONDS))


def _health_cache_ttl_seconds(health: dict | None = None) -> float:
    """Return the bounded snapshot lifetime for the current SIS state."""

    configured_ttl = max(0.1, float(settings.SIS_HEALTH_CACHE_TTL_SECONDS))
    status = str((health or {}).get("status") or "").strip().lower()
    interactive_ready = bool((health or {}).get("interactive_ready"))

    if status == "ready" and interactive_ready:
        return configured_ttl

    return min(
        configured_ttl,
        max(
            0.1,
            float(settings.SIS_HEALTH_TRANSITIONAL_PROBE_SECONDS),
        ),
    )


def _checking_health() -> dict:
    return {
        "ok": False,
        "status": "checking",
        "interactive_ready": False,
    }


def _health_failure_threshold() -> int:
    return max(1, int(settings.SIS_CIRCUIT_FAILURE_THRESHOLD))


def _health_monitor_ready_seconds() -> float:
    return max(1.0, float(settings.SIS_HEALTH_IDLE_PROBE_SECONDS))


def _health_monitor_transitional_seconds() -> float:
    return max(
        0.5,
        float(settings.SIS_HEALTH_TRANSITIONAL_PROBE_SECONDS),
    )


def _health_monitor_recovery_backoff_seconds(
    failure_count: int,
    *,
    demand_active: bool,
) -> float:
    configured = tuple(
        max(1.0, float(value))
        for value in settings.SIS_HEALTH_RECOVERY_BACKOFF_SECONDS
    )
    if not configured:
        configured = (300.0,)

    index = min(max(1, int(failure_count)) - 1, len(configured) - 1)
    delay = configured[index]
    if demand_active:
        delay = min(
            delay,
            max(1.0, float(settings.SIS_HEALTH_RECOVERY_DEMAND_MAX_PROBE_SECONDS)),
        )
    return delay


def _health_recovery_demand_active_locked(now_monotonic: float | None = None) -> bool:
    now_value = time.monotonic() if now_monotonic is None else float(now_monotonic)
    return now_value < float(_HEALTH_RECOVERY_DEMAND_UNTIL_MONOTONIC)


def _health_monitor_is_running_locked() -> bool:
    return bool(
        _HEALTH_MONITOR_THREAD is not None
        and _HEALTH_MONITOR_THREAD.is_alive()
    )


def _health_snapshot_locked() -> dict:
    health = dict(_HEALTH_CACHE_PAYLOAD or _checking_health())
    health["circuit_open"] = bool(_HEALTH_CIRCUIT_OPEN)
    health["consecutive_failures"] = int(_HEALTH_CONSECUTIVE_FAILURES)
    health["last_success_at"] = _HEALTH_LAST_SUCCESS_AT
    health["last_failure_at"] = _HEALTH_LAST_FAILURE_AT
    health["recovery_demand"] = _health_recovery_demand_active_locked()
    health["health_source"] = _HEALTH_LAST_SOURCE
    health["monitor_running"] = _health_monitor_is_running_locked()
    return health


def _set_health_state(
    health: dict,
    *,
    reachable: bool,
    source: str,
    hard_failure: bool = False,
    preserve_ready_during_confirmation: bool = False,
) -> dict:
    """Publish one process-wide SIS availability observation.

    Explicit server/proxy failures and real compute transport failures are
    hard evidence and may open the circuit immediately. A lone health-probe
    timeout after a known-good READY state is treated as suspect evidence:
    Solomon preserves the last READY snapshot while a quick confirmation
    probe runs, preventing one transient Internet/Cloudflare delay from
    unnecessarily disabling interactive intelligence.
    """

    global _HEALTH_CACHE_PAYLOAD
    global _HEALTH_CACHE_EXPIRES_AT
    global _HEALTH_CONSECUTIVE_FAILURES
    global _HEALTH_CIRCUIT_OPEN
    global _HEALTH_LAST_SUCCESS_AT
    global _HEALTH_LAST_FAILURE_AT
    global _HEALTH_LAST_SUCCESS_MONOTONIC
    global _HEALTH_LAST_FAILURE_MONOTONIC
    global _HEALTH_LAST_OBSERVATION_MONOTONIC
    global _HEALTH_LAST_SOURCE

    observed_at = time.time()
    observed_monotonic = time.monotonic()

    with _HEALTH_CACHE_LOCK:
        previous_status = str(
            (_HEALTH_CACHE_PAYLOAD or {}).get("status") or "checking"
        ).strip().lower()
        previous_circuit = bool(_HEALTH_CIRCUIT_OPEN)
        previous_node = str(
            (_HEALTH_CACHE_PAYLOAD or {}).get("node") or ""
        ).strip()[:128]

        _HEALTH_LAST_OBSERVATION_MONOTONIC = observed_monotonic
        if reachable:
            _HEALTH_CONSECUTIVE_FAILURES = 0
            _HEALTH_CIRCUIT_OPEN = False
            _HEALTH_LAST_SUCCESS_AT = observed_at
            _HEALTH_LAST_SUCCESS_MONOTONIC = observed_monotonic
        else:
            _HEALTH_CONSECUTIVE_FAILURES += 1
            _HEALTH_LAST_FAILURE_AT = observed_at
            _HEALTH_LAST_FAILURE_MONOTONIC = observed_monotonic
            failure_threshold = (
                1 if hard_failure else _health_failure_threshold()
            )
            if _HEALTH_CONSECUTIVE_FAILURES >= failure_threshold:
                _HEALTH_CIRCUIT_OPEN = True

        _HEALTH_LAST_SOURCE = str(source or "health").strip() or "health"
        preserve_previous = bool(
            not reachable
            and preserve_ready_during_confirmation
            and not _HEALTH_CIRCUIT_OPEN
            and previous_status == "ready"
            and bool((_HEALTH_CACHE_PAYLOAD or {}).get("interactive_ready"))
        )
        if preserve_previous:
            _HEALTH_CACHE_PAYLOAD = dict(_HEALTH_CACHE_PAYLOAD or health)
        else:
            _HEALTH_CACHE_PAYLOAD = dict(health)
            if previous_node and not _HEALTH_CACHE_PAYLOAD.get("node"):
                _HEALTH_CACHE_PAYLOAD["node"] = previous_node
        _HEALTH_CACHE_PAYLOAD["observed_at"] = observed_at
        _HEALTH_CACHE_EXPIRES_AT = (
            time.monotonic() + _health_cache_ttl_seconds(health)
        )
        snapshot = _health_snapshot_locked()

    current_status = str(snapshot.get("status") or "checking").strip().lower()
    current_circuit = bool(snapshot.get("circuit_open"))
    if (
        current_status != previous_status
        or current_circuit != previous_circuit
    ):
        logger.info(
            "[SIS][AVAILABILITY_STATE] status=%s circuit_open=%s "
            "failures=%s source=%s",
            current_status,
            current_circuit,
            snapshot.get("consecutive_failures"),
            snapshot.get("health_source"),
        )
        persist_service_state_transition(
            previous_status=previous_status,
            current_status=current_status,
            previous_circuit_open=previous_circuit,
            current_circuit_open=current_circuit,
            health=snapshot,
            service_reachable=reachable,
        )

    return snapshot


def _record_compute_contact() -> None:
    """Treat a completed SIS HTTP exchange as positive transport evidence."""

    with _HEALTH_CACHE_LOCK:
        current = dict(_HEALTH_CACHE_PAYLOAD or _checking_health())

    if str(current.get("status") or "").strip().lower() == "unavailable":
        current = {
            "ok": False,
            "status": "checking",
            "interactive_ready": False,
        }

    _set_health_state(
        current,
        reachable=True,
        source="compute",
    )
    # Recalculate the idle deadline from this real successful compute exchange
    # instead of issuing a redundant timer-driven health probe.
    _HEALTH_MONITOR_WAKE.set()


def request_intelligence_service_recovery() -> None:
    """Signal current demand without directly probing SIS.

    Browser/user count and spool polling may call this freely. The single Flask
    monitor coalesces those signals and remains the only owner of remote health
    probes.
    """

    global _HEALTH_RECOVERY_DEMAND_UNTIL_MONOTONIC

    if not bool(settings.SIS_ENABLED):
        return

    now_monotonic = time.monotonic()
    should_wake = False
    with _HEALTH_CACHE_LOCK:
        status = str(
            (_HEALTH_CACHE_PAYLOAD or {}).get("status") or "checking"
        ).strip().lower()
        if not _HEALTH_CIRCUIT_OPEN and status not in {
            "checking",
            "starting",
            "warming",
            "degraded",
            "unavailable",
        }:
            return
        should_wake = not _health_recovery_demand_active_locked(now_monotonic)
        _HEALTH_RECOVERY_DEMAND_UNTIL_MONOTONIC = max(
            _HEALTH_RECOVERY_DEMAND_UNTIL_MONOTONIC,
            now_monotonic + max(1.0, float(settings.SIS_HEALTH_DEMAND_WINDOW_SECONDS)),
        )

    if should_wake:
        _HEALTH_MONITOR_WAKE.set()


def _record_compute_transport_failure(error: Exception) -> None:
    _set_health_state(
        {
            "ok": False,
            "status": "unavailable",
            "interactive_ready": False,
            "error": str(error),
        },
        reachable=False,
        source="compute",
        hard_failure=True,
    )
    _HEALTH_MONITOR_WAKE.set()


def _record_compute_http_response(status_code: int) -> None:
    """Record HTTP reachability without mistaking server errors for READY."""

    clean_status = int(status_code or 0)
    if clean_status >= 500:
        _set_health_state(
            {
                "ok": False,
                "status": "degraded",
                "interactive_ready": False,
                "http_status": clean_status,
            },
            reachable=False,
            source="compute_http",
            hard_failure=True,
        )
        _HEALTH_MONITOR_WAKE.set()
        return

    _record_compute_contact()


def intelligence_service_circuit_open() -> bool:
    """Return whether known transport failure should suppress compute dispatch."""

    if not bool(settings.SIS_ENABLED):
        return True

    with _HEALTH_CACHE_LOCK:
        needs_initial_probe = (
            _HEALTH_CACHE_PAYLOAD is None
            and not _health_monitor_is_running_locked()
        )
        if not needs_initial_probe:
            return bool(_HEALTH_CIRCUIT_OPEN)

    probe_intelligence_service_health()
    with _HEALTH_CACHE_LOCK:
        return bool(_HEALTH_CIRCUIT_OPEN)


def probe_intelligence_service_health() -> dict:
    """Perform the one coalesced network health probe and publish its result."""

    global _HEALTH_PROBE_IN_FLIGHT

    if not bool(settings.SIS_ENABLED):
        return {
            "ok": False,
            "status": "disabled",
            "interactive_ready": False,
            "circuit_open": True,
        }

    with _HEALTH_CACHE_LOCK:
        if _HEALTH_PROBE_IN_FLIGHT:
            return _health_snapshot_locked()
        _HEALTH_PROBE_IN_FLIGHT = True

    request = urllib_request.Request(
        _service_url("/health"),
        headers=_request_headers(),
        method="GET",
    )

    try:
        with urllib_request.urlopen(
            request,
            timeout=_health_timeout_seconds(),
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
            health = payload if isinstance(payload, dict) else {
                "ok": False,
                "status": "degraded",
                "interactive_ready": False,
            }
        snapshot = _set_health_state(
            health,
            reachable=True,
            source="health",
        )
        persist_capacity_snapshot(
            snapshot,
            service_reachable=True,
        )
        return snapshot
    except urllib_error.HTTPError as exc:
        logger.debug(
            "[SIS][HEALTH_HTTP_FAILURE] status=%s",
            exc.code,
        )
        snapshot = _set_health_state(
            {
                "ok": False,
                "status": "degraded",
                "interactive_ready": False,
                "http_status": int(exc.code),
            },
            reachable=False,
            source="health",
            hard_failure=True,
        )
        persist_capacity_snapshot(
            snapshot,
            service_reachable=False,
        )
        return snapshot
    except Exception as exc:
        logger.debug("[SIS][HEALTH_UNAVAILABLE] error=%s", exc)
        snapshot = _set_health_state(
            {
                "ok": False,
                "status": "unavailable",
                "interactive_ready": False,
                "error": str(exc),
            },
            reachable=False,
            source="health",
            preserve_ready_during_confirmation=True,
        )
        persist_capacity_snapshot(
            snapshot,
            service_reachable=False,
        )
        return snapshot
    finally:
        with _HEALTH_CACHE_LOCK:
            _HEALTH_PROBE_IN_FLIGHT = False


def get_intelligence_service_health() -> dict:
    """Return the Flask-owned SIS availability snapshot without fan-out probes."""

    if not bool(settings.SIS_ENABLED):
        return {
            "ok": False,
            "status": "disabled",
            "interactive_ready": False,
            "circuit_open": True,
        }

    now = time.monotonic()

    with _HEALTH_CACHE_LOCK:
        if _HEALTH_CACHE_PAYLOAD is not None:
            if _health_monitor_is_running_locked():
                return _health_snapshot_locked()
            if now < _HEALTH_CACHE_EXPIRES_AT:
                return _health_snapshot_locked()
        if _HEALTH_PROBE_IN_FLIGHT:
            return _health_snapshot_locked()

    # Preserve safe behavior for command-line utilities or tests that consume the
    # client without starting the normal Flask application lifecycle.
    return probe_intelligence_service_health()


def _seconds_until_next_health_probe() -> float:
    now_monotonic = time.monotonic()

    with _HEALTH_CACHE_LOCK:
        if _HEALTH_CACHE_PAYLOAD is None:
            return 0.0

        health = _health_snapshot_locked()
        status = str(health.get("status") or "").strip().lower()
        failure_count = max(0, int(_HEALTH_CONSECUTIVE_FAILURES))
        circuit_open = bool(_HEALTH_CIRCUIT_OPEN)
        demand_active = _health_recovery_demand_active_locked(now_monotonic)
        last_success = _HEALTH_LAST_SUCCESS_MONOTONIC
        last_failure = _HEALTH_LAST_FAILURE_MONOTONIC
        last_observation = _HEALTH_LAST_OBSERVATION_MONOTONIC

    if failure_count > 0 and not circuit_open:
        anchor = last_failure or last_observation or now_monotonic
        due_at = anchor + _health_monitor_transitional_seconds()
    elif circuit_open or status in {"degraded", "unavailable"}:
        anchor = last_failure or last_observation or now_monotonic
        due_at = anchor + _health_monitor_recovery_backoff_seconds(
            max(1, failure_count),
            demand_active=demand_active,
        )
    elif status == "ready" and bool(health.get("interactive_ready")):
        anchor = last_success or last_observation or now_monotonic
        due_at = anchor + _health_monitor_ready_seconds()
    else:
        anchor = last_observation or last_success or now_monotonic
        due_at = anchor + _health_monitor_transitional_seconds()

    return max(0.0, due_at - now_monotonic)


def _intelligence_service_health_monitor_loop() -> None:
    while not _HEALTH_MONITOR_STOP.is_set():
        delay = _seconds_until_next_health_probe()
        if delay > 0.0:
            _HEALTH_MONITOR_WAKE.wait(delay)
            _HEALTH_MONITOR_WAKE.clear()
            continue

        probe_intelligence_service_health()


def start_intelligence_service_health_monitor() -> threading.Thread | None:
    """Start the one process-local SIS health monitor owned by Flask."""

    global _HEALTH_MONITOR_THREAD

    if not bool(settings.SIS_ENABLED) or not bool(settings.SIS_HEALTH_MONITOR_ENABLED):
        return None

    with _HEALTH_MONITOR_LIFECYCLE_LOCK:
        if (
            _HEALTH_MONITOR_THREAD is not None
            and _HEALTH_MONITOR_THREAD.is_alive()
        ):
            return _HEALTH_MONITOR_THREAD

        _HEALTH_MONITOR_STOP.clear()
        _HEALTH_MONITOR_WAKE.clear()
        _HEALTH_MONITOR_THREAD = threading.Thread(
            target=_intelligence_service_health_monitor_loop,
            name="solomon-sis-health",
            daemon=True,
        )
        _HEALTH_MONITOR_THREAD.start()
        logger.info(
            "[SIS][HEALTH_MONITOR_STARTED] endpoint=%s idle_probe_seconds=%s",
            get_intelligence_service_endpoint(),
            _health_monitor_ready_seconds(),
        )
        return _HEALTH_MONITOR_THREAD


def stop_intelligence_service_health_monitor(
    monitor: threading.Thread | None = None,
) -> None:
    """Stop the Flask-owned SIS health monitor without affecting remote SIS."""

    global _HEALTH_MONITOR_THREAD

    with _HEALTH_MONITOR_LIFECYCLE_LOCK:
        active = monitor or _HEALTH_MONITOR_THREAD
        if active is None:
            return
        _HEALTH_MONITOR_STOP.set()
        _HEALTH_MONITOR_WAKE.set()

    if active.is_alive():
        active.join(
            timeout=max(1.0, float(_health_timeout_seconds()) + 1.0)
        )

    with _HEALTH_MONITOR_LIFECYCLE_LOCK:
        if _HEALTH_MONITOR_THREAD is active:
            _HEALTH_MONITOR_THREAD = None

    logger.info("[SIS][HEALTH_MONITOR_STOPPED]")


def _next_durable_completion_event_id() -> str:
    global _DURABLE_COMPLETION_EVENT_ID

    with _DURABLE_COMPLETION_LOCK:
        candidate = int(time.time_ns())
        _DURABLE_COMPLETION_EVENT_ID = max(
            candidate,
            _DURABLE_COMPLETION_EVENT_ID + 1,
        )
        return str(_DURABLE_COMPLETION_EVENT_ID)


def _stream_local_durable_completion_events():
    """Yield DB-backed completion changes while SIS compute is remote.

    The local Intelligence Spool database is authoritative for background job
    state.  A remote SIS therefore must not be asked to host completion events.
    This bridge tails durable succeeded-event rows and emits the same lightweight
    notification shape consumed by the existing workspace SSE layer.
    """

    global _DURABLE_COMPLETION_SEQUENCE_CURSOR

    from .intelligence_job_repository import IntelligenceJobRepository

    repository = IntelligenceJobRepository()
    initialized_now = False

    with _DURABLE_COMPLETION_LOCK:
        if _DURABLE_COMPLETION_SEQUENCE_CURSOR is None:
            _DURABLE_COMPLETION_SEQUENCE_CURSOR = (
                repository.get_latest_completion_sequence()
            )
            initialized_now = True

    if initialized_now:
        yield {
            "type": INTELLIGENCE_RESYNC_EVENT_TYPE,
            "event_id": _next_durable_completion_event_id(),
        }

    poll_seconds = max(
        0.5,
        min(2.0, float(settings.SIS_SPOOL_POLL_INTERVAL_SECONDS)),
    )
    heartbeat_seconds = max(
        1.0,
        float(settings.SIS_EVENT_STREAM_HEARTBEAT_SECONDS),
    )
    last_heartbeat = time.monotonic()

    while True:
        with _DURABLE_COMPLETION_LOCK:
            sequence_cursor = int(
                _DURABLE_COMPLETION_SEQUENCE_CURSOR or 0
            )

        events = repository.list_completion_events_after(
            sequence_cursor,
            limit=100,
        )
        if events:
            for event in events:
                sequence_id = max(
                    sequence_cursor,
                    int(event.get("sequence_id") or 0),
                )
                with _DURABLE_COMPLETION_LOCK:
                    _DURABLE_COMPLETION_SEQUENCE_CURSOR = max(
                        int(_DURABLE_COMPLETION_SEQUENCE_CURSOR or 0),
                        sequence_id,
                    )
                sequence_cursor = sequence_id
                yield {
                    "type": INTELLIGENCE_COMPLETION_EVENT_TYPE,
                    "event_id": _next_durable_completion_event_id(),
                    "job_id": str(event.get("job_id") or ""),
                    "job_type": str(event.get("job_type") or ""),
                    "document_id": str(event.get("document_id") or ""),
                    "intelligence_object_id": event.get(
                        "intelligence_object_id"
                    ),
                    "stage": str(event.get("stage") or "completed"),
                    "completed_at": str(event.get("completed_at") or ""),
                }
            last_heartbeat = time.monotonic()
            continue

        time.sleep(poll_seconds)
        now = time.monotonic()
        if now - last_heartbeat >= heartbeat_seconds:
            last_heartbeat = now
            yield {
                "type": "heartbeat",
                "event_id": _next_durable_completion_event_id(),
                "timestamp": time.time(),
            }


def stream_intelligence_completion_events(
    after_event_id: str | int | None = "0",
):
    """Yield completion changes without requiring a second local SIS.

    In remote-compute mode the local durable Intelligence Spool database is
    tailed directly.  Local rollback mode preserves the historical SIS HTTP
    completion stream.
    """

    if not bool(settings.SIS_ENABLED):
        raise RuntimeError("The Solomon Intelligence Service is disabled.")

    if _remote_compute_enabled():
        yield from _stream_local_durable_completion_events()
        return

    clean_after = str(after_event_id or "").strip()
    path = "/v1/events/completions"
    if clean_after:
        path += "?" + urllib_parse.urlencode({"after": clean_after})

    headers = _request_headers()
    headers["Accept"] = "application/x-ndjson"
    request_packet = urllib_request.Request(
        _service_url(path),
        headers=headers,
        method="GET",
    )
    stream_timeout = max(
        5,
        _request_timeout_seconds(),
        int(float(settings.SIS_EVENT_STREAM_HEARTBEAT_SECONDS) * 3),
    )

    try:
        with urllib_request.urlopen(
            request_packet,
            timeout=stream_timeout,
        ) as response:
            content_type = str(response.headers.get("Content-Type") or "")
            if "application/x-ndjson" not in content_type:
                raise RuntimeError(
                    "SIS completion stream returned an unexpected content type."
                )

            for raw_line in response:
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue

                payload = json.loads(line)
                if isinstance(payload, dict):
                    yield payload
    except urllib_error.HTTPError as exc:
        message = f"SIS completion stream returned HTTP {exc.code}."
        try:
            payload = json.loads(exc.read().decode("utf-8"))
            message = str(payload.get("error") or message)
        except Exception:
            pass
        logger.warning(
            "[SIS][COMPLETION_STREAM_HTTP_FAILURE] status=%s error=%s",
            exc.code,
            message,
        )
        raise RuntimeError(message) from exc
    except (urllib_error.URLError, socket.timeout, TimeoutError) as exc:
        logger.warning("[SIS][COMPLETION_STREAM_UNAVAILABLE] error=%s", exc)
        raise RuntimeError(
            "The SIS completion event stream is unavailable."
        ) from exc


def execute_embeddings_via_intelligence_service(
    texts: Iterable[str],
    *,
    call_site: str | None = None,
    priority: str | IntelligencePriority = IntelligencePriority.P0,
    request_id: str | None = None,
    fairness_bucket: str | None = None,
) -> list[list[float]]:
    """Execute normalized embedding work through the SIS-owned Qwen model."""

    if not bool(settings.SIS_ENABLED):
        raise RuntimeError("The Solomon Intelligence Service is disabled.")
    if not bool(settings.SIS_EMBEDDING_ENABLED):
        raise RuntimeError("SIS embedding execution is disabled.")
    if intelligence_service_circuit_open():
        raise RuntimeError(
            "The Solomon Intelligence Service is temporarily unavailable."
        )

    text_list = [str(text or "").strip() for text in texts]
    if not text_list:
        return []
    if any(not text for text in text_list):
        raise ValueError("Embedding requests must contain non-empty text.")

    function_started_at = time.perf_counter()
    normalized_priority = str(getattr(priority, "value", priority)).strip().upper() or "P0"
    batch_size = max(1, int(settings.SIS_EMBEDDING_MAX_BATCH_SIZE))
    timeout_seconds = (
        max(1, int(settings.SIS_EMBEDDING_TIMEOUT_SECONDS))
        + _connect_timeout_seconds()
    )
    output: list[list[float]] = []

    for start in range(0, len(text_list), batch_size):
        batch_started_at = time.perf_counter()
        batch = text_list[start:start + batch_size]
        attempt_id = _new_compute_attempt_id()
        request_payload = {
            "request": serialize_embedding_input(
                batch,
                call_site=call_site,
            ),
            "request_class": (
                IntelligenceRequestClass.BACKGROUND.value
                if str(getattr(priority, "value", priority)).strip().upper() in {"P2", "P3"}
                else IntelligenceRequestClass.INTERACTIVE.value
            ),
            "scheduling": serialize_compute_scheduling(
                priority=priority,
                request_id=request_id,
                fairness_bucket=fairness_bucket,
                attempt_id=attempt_id,
            ),
        }
        request_body = json.dumps(request_payload).encode("utf-8")
        request_packet = urllib_request.Request(
            _service_url("/v1/embeddings/execute"),
            data=request_body,
            headers=_request_headers(),
            method="POST",
        )
        prepared_at = time.perf_counter()
        logger.info(
            "[SIS][LOCAL_EMBEDDING_DISPATCH_TIMING] phase=prepared transport=intelligence_service_client "
            "priority=%s request_id=%s call_site=%s batch=%s chars=%s bytes=%s prepare_ms=%.3f",
            normalized_priority,
            str(request_id or "unbound"),
            str(call_site or "unknown"),
            len(batch),
            sum(len(item) for item in batch),
            len(request_body),
            (prepared_at - batch_started_at) * 1000.0,
        )

        try:
            transport_started_at = time.perf_counter()
            with urllib_request.urlopen(
                request_packet,
                timeout=timeout_seconds,
            ) as response:
                response_bytes = response.read()
                transport_completed_at = time.perf_counter()
                http_status = int(getattr(response, "status", 200) or 200)
                payload = json.loads(response_bytes.decode("utf-8"))
                telemetry_payload = payload.get("telemetry")
                telemetry_started_at = time.perf_counter()
                persist_compute_execution_telemetry(
                    telemetry_payload,
                    transport_path="intelligence_service_client",
                )
                persist_compute_request_event(
                    attempt_id=attempt_id,
                    request_id=request_id,
                    workload_type="embedding",
                    priority=priority,
                    call_site=call_site,
                    transport_path="intelligence_service_client",
                    request_bytes=len(request_body),
                    response_bytes=len(response_bytes),
                    round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                    http_status=http_status,
                    outcome_class=_telemetry_outcome(telemetry_payload),
                    telemetry_payload=telemetry_payload,
                )
                telemetry_completed_at = time.perf_counter()
                logger.info(
                    "[SIS][LOCAL_EMBEDDING_DISPATCH_TIMING] phase=response transport=intelligence_service_client "
                    "priority=%s request_id=%s call_site=%s batch=%s transport_ms=%.3f telemetry_ms=%.3f response_bytes=%s",
                    normalized_priority,
                    str(request_id or "unbound"),
                    str(call_site or "unknown"),
                    len(batch),
                    (transport_completed_at - transport_started_at) * 1000.0,
                    (telemetry_completed_at - telemetry_started_at) * 1000.0,
                    len(response_bytes),
                )
                result = deserialize_embedding_result(
                    payload.get("result") or {}
                )
            _record_compute_contact()
        except urllib_error.HTTPError as exc:
            _record_compute_http_response(exc.code)
            transport_completed_at = time.perf_counter()
            message = f"SIS embedding request returned HTTP {exc.code}."
            error_bytes = b""
            telemetry_payload = None
            try:
                error_bytes = exc.read()
                payload = json.loads(error_bytes.decode("utf-8"))
                telemetry_payload = payload.get("telemetry")
                persist_compute_execution_telemetry(
                    telemetry_payload,
                    transport_path="intelligence_service_client",
                )
                message = str(payload.get("error") or message)
            except Exception:
                pass
            persist_compute_request_event(
                attempt_id=attempt_id,
                request_id=request_id,
                workload_type="embedding",
                priority=priority,
                call_site=call_site,
                transport_path="intelligence_service_client",
                request_bytes=len(request_body),
                response_bytes=len(error_bytes),
                round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                http_status=exc.code,
                outcome_class=(
                    _telemetry_outcome(telemetry_payload)
                    if telemetry_payload
                    else "http_failure"
                ),
                failure_code=_http_failure_code(exc.code),
                telemetry_payload=telemetry_payload,
            )
            logger.warning(
                "[SIS][EMBEDDING_HTTP_FAILURE] status=%s error=%s",
                exc.code,
                message,
            )
            raise RuntimeError(message) from exc
        except (urllib_error.URLError, socket.timeout, TimeoutError) as exc:
            _record_compute_transport_failure(exc)
            persist_compute_request_event(
                attempt_id=attempt_id,
                request_id=request_id,
                workload_type="embedding",
                priority=priority,
                call_site=call_site,
                transport_path="intelligence_service_client",
                request_bytes=len(request_body),
                response_bytes=0,
                round_trip_ms=(time.perf_counter() - transport_started_at) * 1000.0,
                outcome_class="transport_failure",
                failure_code=_transport_failure_code(exc),
            )
            logger.warning("[SIS][EMBEDDING_UNAVAILABLE] error=%s", exc)
            raise RuntimeError(
                "The Solomon Intelligence Service embedding endpoint is "
                "unavailable or timed out."
            ) from exc
        except Exception as exc:
            persist_compute_request_event(
                attempt_id=attempt_id,
                request_id=request_id,
                workload_type="embedding",
                priority=priority,
                call_site=call_site,
                transport_path="intelligence_service_client",
                request_bytes=len(request_body),
                response_bytes=0,
                round_trip_ms=(time.perf_counter() - transport_started_at) * 1000.0,
                outcome_class="client_failure",
                failure_code="client_error",
            )
            logger.exception("[SIS][EMBEDDING_CLIENT_FAILURE]")
            raise RuntimeError(
                f"The SIS embedding request failed: {exc}"
            ) from exc

        if len(result.vectors) != len(batch):
            raise RuntimeError(
                "SIS embedding response returned an unexpected vector count."
            )
        if result.dimension != int(settings.EMBED_DIM):
            raise RuntimeError(
                "SIS embedding response dimension does not match config.py."
            )

        output.extend(result.vectors)

    logger.info(
        "[SIS][LOCAL_EMBEDDING_DISPATCH_TIMING] phase=complete transport=intelligence_service_client "
        "priority=%s request_id=%s call_site=%s batches=%s vectors=%s total_ms=%.3f",
        normalized_priority,
        str(request_id or "unbound"),
        str(call_site or "unknown"),
        max(1, (len(text_list) + batch_size - 1) // batch_size),
        len(output),
        (time.perf_counter() - function_started_at) * 1000.0,
    )
    return output


def execute_llm_via_intelligence_service(
    input_packet: LLMExecutionInput,
    stream_callback: Callable[[str], None] | None = None,
    *,
    priority: str | IntelligencePriority = IntelligencePriority.P0,
    request_id: str | None = None,
    fairness_bucket: str | None = None,
) -> LLMExecutionResult:
    """Execute one governed LLM request through the external SIS process."""

    if not bool(settings.SIS_ENABLED):
        return _failure(
            LLMFailureReason.INTERNAL_ERROR,
            "The Solomon Intelligence Service is disabled.",
        )
    if intelligence_service_circuit_open():
        return _failure(
            LLMFailureReason.TIMEOUT,
            "The Solomon Intelligence Service is temporarily unavailable.",
        )

    attempt_id = _new_compute_attempt_id()
    request_payload = {
        "request": serialize_llm_input(input_packet),
        "request_class": (
            IntelligenceRequestClass.BACKGROUND.value
            if str(getattr(priority, "value", priority)).strip().upper() in {"P2", "P3"}
            else IntelligenceRequestClass.INTERACTIVE.value
        ),
        "scheduling": serialize_compute_scheduling(
            priority=priority,
            request_id=request_id,
            fairness_bucket=fairness_bucket,
            attempt_id=attempt_id,
        ),
        "stream": bool(stream_callback),
    }
    request_body = json.dumps(request_payload).encode("utf-8")
    request = urllib_request.Request(
        _service_url("/v1/llm/execute"),
        data=request_body,
        headers=_request_headers(),
        method="POST",
    )
    timeout_seconds = max(
        1,
        int(
            input_packet.timeout_seconds
            or _request_timeout_seconds()
        ),
    ) + _connect_timeout_seconds()

    transport_started_at = time.perf_counter()
    try:
        with urllib_request.urlopen(
            request,
            timeout=timeout_seconds,
        ) as response:
            content_type = str(response.headers.get("Content-Type") or "")

            if "application/x-ndjson" in content_type:
                final_result = None
                telemetry_payload = None
                response_bytes_count = 0

                for raw_line in response:
                    response_bytes_count += len(raw_line)
                    line = raw_line.decode("utf-8", errors="replace").strip()
                    if not line:
                        continue

                    event = json.loads(line)
                    event_type = str(event.get("type") or "")

                    if event_type == "chunk":
                        chunk = str(event.get("text") or "")
                        if chunk and stream_callback:
                            stream_callback(chunk)
                    elif event_type == "result":
                        telemetry_payload = event.get("telemetry")
                        persist_compute_execution_telemetry(
                            telemetry_payload,
                            transport_path="intelligence_service_client",
                        )
                        final_result = deserialize_llm_result(
                            event.get("result") or {}
                        )

                transport_completed_at = time.perf_counter()
                if final_result is None:
                    persist_compute_request_event(
                        attempt_id=attempt_id,
                        request_id=request_id,
                        workload_type="llm",
                        priority=priority,
                        call_site=input_packet.call_site,
                        transport_path="intelligence_service_client",
                        request_bytes=len(request_body),
                        response_bytes=response_bytes_count,
                        round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                        http_status=int(getattr(response, "status", 200) or 200),
                        outcome_class="client_failure",
                        failure_code="stream_missing_result",
                        telemetry_payload=telemetry_payload,
                    )
                    return _failure(
                        LLMFailureReason.INTERNAL_ERROR,
                        "SIS streaming response ended without a final result.",
                    )

                persist_compute_request_event(
                    attempt_id=attempt_id,
                    request_id=request_id,
                    workload_type="llm",
                    priority=priority,
                    call_site=input_packet.call_site,
                    transport_path="intelligence_service_client",
                    request_bytes=len(request_body),
                    response_bytes=response_bytes_count,
                    round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                    http_status=int(getattr(response, "status", 200) or 200),
                    outcome_class=_telemetry_outcome(telemetry_payload),
                    telemetry_payload=telemetry_payload,
                )
                _record_compute_contact()
                return final_result

            response_bytes = response.read()
            transport_completed_at = time.perf_counter()
            payload = json.loads(response_bytes.decode("utf-8"))
            telemetry_payload = payload.get("telemetry")
            persist_compute_execution_telemetry(
                telemetry_payload,
                transport_path="intelligence_service_client",
            )
            persist_compute_request_event(
                attempt_id=attempt_id,
                request_id=request_id,
                workload_type="llm",
                priority=priority,
                call_site=input_packet.call_site,
                transport_path="intelligence_service_client",
                request_bytes=len(request_body),
                response_bytes=len(response_bytes),
                round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
                http_status=int(getattr(response, "status", 200) or 200),
                outcome_class=_telemetry_outcome(telemetry_payload),
                telemetry_payload=telemetry_payload,
            )
            result = deserialize_llm_result(payload.get("result") or {})
            _record_compute_contact()
            return result

    except urllib_error.HTTPError as exc:
        _record_compute_http_response(exc.code)
        transport_completed_at = time.perf_counter()
        message = f"SIS returned HTTP {exc.code}."
        error_bytes = b""
        telemetry_payload = None
        try:
            error_bytes = exc.read()
            payload = json.loads(error_bytes.decode("utf-8"))
            telemetry_payload = payload.get("telemetry")
            persist_compute_execution_telemetry(
                telemetry_payload,
                transport_path="intelligence_service_client",
            )
            message = str(payload.get("error") or message)
        except Exception:
            pass
        persist_compute_request_event(
            attempt_id=attempt_id,
            request_id=request_id,
            workload_type="llm",
            priority=priority,
            call_site=input_packet.call_site,
            transport_path="intelligence_service_client",
            request_bytes=len(request_body),
            response_bytes=len(error_bytes),
            round_trip_ms=(transport_completed_at - transport_started_at) * 1000.0,
            http_status=exc.code,
            outcome_class=(
                _telemetry_outcome(telemetry_payload)
                if telemetry_payload
                else "http_failure"
            ),
            failure_code=_http_failure_code(exc.code),
            telemetry_payload=telemetry_payload,
        )

        logger.warning("[SIS][LLM_HTTP_FAILURE] status=%s error=%s", exc.code, message)
        return _failure(
            LLMFailureReason.TIMEOUT
            if exc.code == 429
            else LLMFailureReason.INTERNAL_ERROR,
            message,
        )
    except (urllib_error.URLError, socket.timeout, TimeoutError) as exc:
        _record_compute_transport_failure(exc)
        persist_compute_request_event(
            attempt_id=attempt_id,
            request_id=request_id,
            workload_type="llm",
            priority=priority,
            call_site=input_packet.call_site,
            transport_path="intelligence_service_client",
            request_bytes=len(request_body),
            response_bytes=0,
            round_trip_ms=(time.perf_counter() - transport_started_at) * 1000.0,
            outcome_class="transport_failure",
            failure_code=_transport_failure_code(exc),
        )
        logger.warning("[SIS][LLM_UNAVAILABLE] error=%s", exc)
        return _failure(
            LLMFailureReason.TIMEOUT,
            "The Solomon Intelligence Service is unavailable or timed out.",
        )
    except Exception as exc:
        persist_compute_request_event(
            attempt_id=attempt_id,
            request_id=request_id,
            workload_type="llm",
            priority=priority,
            call_site=input_packet.call_site,
            transport_path="intelligence_service_client",
            request_bytes=len(request_body),
            response_bytes=0,
            round_trip_ms=(time.perf_counter() - transport_started_at) * 1000.0,
            outcome_class="client_failure",
            failure_code="client_error",
        )
        logger.exception("[SIS][LLM_CLIENT_FAILURE]")
        return _failure(
            LLMFailureReason.INTERNAL_ERROR,
            f"The Solomon Intelligence Service request failed: {exc}",
        )

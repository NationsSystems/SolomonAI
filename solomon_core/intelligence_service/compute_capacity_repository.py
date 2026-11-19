# -------------------------------------------------------------------
# FILE: compute_capacity_repository.py
# DIRECTORY: solomon_core/intelligence_service/
# -------------------------------------------------------------------
# Durable LOCAL persistence for content-free Portable SIS compute telemetry.
# Portable SIS measures bounded execution facts; Solomon's governed database
# tier owns the authoritative historical record used for capacity reporting.
# -------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from types import SimpleNamespace
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from solomon_core.db import engine
from solomon_core.logger import get_logger
from solomon_core.models import (
    INTELLIGENCE_JOB_STATUS_CLAIMED,
    INTELLIGENCE_JOB_STATUS_PENDING,
    INTELLIGENCE_JOB_STATUS_RETRY_WAIT,
    INTELLIGENCE_JOB_STATUS_RUNNING,
    IntelligenceCapacityRollup,
    IntelligenceCapacitySnapshot,
    IntelligenceComputeEvent,
    IntelligenceComputeRequestEvent,
    IntelligenceJob,
    IntelligenceRequestAttribution,
    IntelligenceServiceEvent,
)

from .intelligence_service_contract import (
    ComputeExecutionTelemetry,
    deserialize_compute_execution_telemetry,
)


logger = get_logger("intelligence_service.compute_capacity_repository")


def _observed_datetime(value: str) -> datetime:
    normalized = str(value or "").strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"

    observed_at = datetime.fromisoformat(normalized)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=timezone.utc)
    return observed_at.astimezone(timezone.utc)


def _epoch_datetime(value: Any) -> datetime:
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)
    if timestamp <= 0:
        return datetime.now(timezone.utc)
    return datetime.fromtimestamp(timestamp, tz=timezone.utc)


def _event_key(telemetry: ComputeExecutionTelemetry) -> str:
    canonical = {
        "observed_at": telemetry.observed_at,
        "node": telemetry.node,
        "workload_type": telemetry.workload_type,
        "priority": telemetry.priority.value,
        "request_id": telemetry.request_id,
        "fairness_bucket": telemetry.fairness_bucket,
        "call_site": telemetry.call_site,
        "queue_wait_ms": telemetry.queue_wait_ms,
        "execution_ms": telemetry.execution_ms,
        "queue_depth_at_admission": telemetry.queue_depth_at_admission,
        "active_requests_at_admission": telemetry.active_requests_at_admission,
        "max_concurrent_requests": telemetry.max_concurrent_requests,
        "input_units": telemetry.input_units,
        "output_units": telemetry.output_units,
        "success": telemetry.success,
    }
    serialized = json.dumps(
        canonical,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _bounded_mapping(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}

    payload: dict[str, Any] = {}
    for raw_key, raw_value in list(value.items())[:64]:
        key = str(raw_key or "").strip()[:128]
        if not key:
            continue
        if isinstance(raw_value, (str, int, float, bool)) or raw_value is None:
            payload[key] = (
                str(raw_value)[:1024]
                if isinstance(raw_value, str)
                else raw_value
            )
        elif isinstance(raw_value, dict):
            payload[key] = _bounded_mapping(raw_value)
        elif isinstance(raw_value, (list, tuple)):
            payload[key] = [
                str(item)[:256]
                if not isinstance(item, (int, float, bool)) and item is not None
                else item
                for item in list(raw_value)[:64]
            ]
    return payload


def _runtime_fingerprint(runtime: dict[str, Any]) -> str | None:
    if not runtime:
        return None
    serialized = json.dumps(
        runtime,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
    )
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return max(0, int(default))


def _nonnegative_float(value: Any, *, default: float = 0.0) -> float:
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return max(0.0, float(default))


def _priority_count(payload: dict[str, Any], priority: str) -> int:
    return _nonnegative_int(payload.get(priority))


def _spool_capacity_values(connection) -> dict[str, Any]:
    rows = connection.execute(
        select(
            IntelligenceJob.status,
            func.count(IntelligenceJob.id),
        ).group_by(IntelligenceJob.status)
    ).all()
    counts = {
        str(status): int(count or 0)
        for status, count in rows
    }

    pending = counts.get(INTELLIGENCE_JOB_STATUS_PENDING, 0)
    retry_wait = counts.get(INTELLIGENCE_JOB_STATUS_RETRY_WAIT, 0)
    claimed = counts.get(INTELLIGENCE_JOB_STATUS_CLAIMED, 0)
    running = counts.get(INTELLIGENCE_JOB_STATUS_RUNNING, 0)
    backlog = pending + retry_wait
    in_flight = claimed + running

    oldest_backlog_created_at = connection.execute(
        select(func.min(IntelligenceJob.created_at)).where(
            IntelligenceJob.status.in_((
                INTELLIGENCE_JOB_STATUS_PENDING,
                INTELLIGENCE_JOB_STATUS_RETRY_WAIT,
            ))
        )
    ).scalar_one_or_none()

    return {
        "spool_pending": pending,
        "spool_retry_wait": retry_wait,
        "spool_claimed": claimed,
        "spool_running": running,
        "spool_backlog": backlog,
        "spool_in_flight": in_flight,
        "spool_unfinished": backlog + in_flight,
        "oldest_backlog_created_at": oldest_backlog_created_at,
    }



def _utc_datetime(value: Any) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _period_bounds(observed_at: datetime, grain: str) -> tuple[datetime, datetime]:
    point = _utc_datetime(observed_at) or datetime.now(timezone.utc)
    if grain == "hour":
        start = point.replace(minute=0, second=0, microsecond=0)
        return start, start + timedelta(hours=1)
    if grain == "day":
        start = point.replace(hour=0, minute=0, second=0, microsecond=0)
        return start, start + timedelta(days=1)
    raise ValueError(f"Unsupported capacity rollup grain: {grain}")


def _count_values(rows: list[Any], attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(getattr(row, attribute, "") or "").strip()
        if not value:
            continue
        counts[value] = counts.get(value, 0) + 1
    return counts


def _merge_count_mappings(rows: list[Any], attribute: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        payload = getattr(row, attribute, None)
        if not isinstance(payload, dict):
            continue
        for raw_key, raw_value in payload.items():
            key = str(raw_key or "").strip()
            if not key:
                continue
            counts[key] = counts.get(key, 0) + _nonnegative_int(raw_value)
    return counts


def _average(total: float, count: int) -> float:
    return float(total) / int(count) if int(count) > 0 else 0.0


def _replace_capacity_rollup(connection, values: dict[str, Any]) -> None:
    table = IntelligenceCapacityRollup.__table__
    row_id = connection.execute(
        select(IntelligenceCapacityRollup.id).where(
            IntelligenceCapacityRollup.node_name == values["node_name"],
            IntelligenceCapacityRollup.period_grain == values["period_grain"],
            IntelligenceCapacityRollup.period_start == values["period_start"],
        )
    ).scalar_one_or_none()

    if row_id is None:
        connection.execute(table.insert().values(**values))
        return

    connection.execute(
        table.update().where(table.c.id == row_id).values(**values)
    )


def _hourly_capacity_rollup_values(
    connection,
    *,
    node_name: str,
    period_start: datetime,
    period_end: datetime,
    as_of: datetime,
) -> dict[str, Any] | None:
    effective_end = min(period_end, as_of)
    if effective_end <= period_start:
        return None

    overlap_events = [
        SimpleNamespace(**dict(row))
        for row in connection.execute(
            select(IntelligenceComputeEvent.__table__).where(
                IntelligenceComputeEvent.node_name == node_name,
                IntelligenceComputeEvent.observed_at >= period_start,
                IntelligenceComputeEvent.observed_at <= as_of,
            )
        ).mappings().all()
    ]
    completed_events = [
        event
        for event in overlap_events
        if (_utc_datetime(event.observed_at) or period_end) < period_end
    ]
    snapshots = [
        SimpleNamespace(**dict(row))
        for row in connection.execute(
            select(IntelligenceCapacitySnapshot.__table__).where(
                IntelligenceCapacitySnapshot.node_name == node_name,
                IntelligenceCapacitySnapshot.observed_at >= period_start,
                IntelligenceCapacitySnapshot.observed_at <= effective_end,
            )
        ).mappings().all()
    ]
    service_events = [
        SimpleNamespace(**dict(row))
        for row in connection.execute(
            select(IntelligenceServiceEvent.__table__).where(
                IntelligenceServiceEvent.node_name == node_name,
                IntelligenceServiceEvent.observed_at >= period_start,
                IntelligenceServiceEvent.observed_at <= effective_end,
            )
        ).mappings().all()
    ]

    evidence_starts: list[datetime] = []
    for event in overlap_events:
        event_end = _utc_datetime(event.observed_at)
        if event_end is None:
            continue
        event_start = event_end - timedelta(
            milliseconds=max(0.0, float(event.execution_ms or 0.0))
        )
        if event_start < period_end and event_end > period_start:
            evidence_starts.append(max(period_start, event_start))
    evidence_starts.extend(
        observed
        for observed in (_utc_datetime(row.observed_at) for row in snapshots)
        if observed is not None
    )
    evidence_starts.extend(
        observed
        for observed in (_utc_datetime(row.observed_at) for row in service_events)
        if observed is not None
    )
    if not evidence_starts:
        return None

    observed_from_at = min(evidence_starts)
    observed_through_at = effective_end
    observation_window_ms = max(
        0.0,
        (observed_through_at - observed_from_at).total_seconds() * 1000.0,
    )

    occupied_execution_ms = 0.0
    for event in overlap_events:
        event_end = _utc_datetime(event.observed_at)
        if event_end is None:
            continue
        execution_ms = max(0.0, float(event.execution_ms or 0.0))
        event_start = event_end - timedelta(milliseconds=execution_ms)
        overlap_start = max(period_start, observed_from_at, event_start)
        overlap_end = min(period_end, observed_through_at, event_end)
        if overlap_end > overlap_start:
            occupied_execution_ms += (
                overlap_end - overlap_start
            ).total_seconds() * 1000.0

    capacity_slots = max(
        [1]
        + [max(1, int(event.max_concurrent_requests or 1)) for event in overlap_events]
        + [max(1, int(row.max_concurrent_requests or 1)) for row in snapshots]
    )
    qualified_capacity_ms = observation_window_ms * capacity_slots
    occupancy_pct = (
        min(100.0, (occupied_execution_ms / qualified_capacity_ms) * 100.0)
        if qualified_capacity_ms > 0.0
        else 0.0
    )

    event_count = len(completed_events)
    successful_event_count = sum(1 for event in completed_events if event.success)
    priority_counts = _count_values(completed_events, "priority")
    queue_wait_total_ms = sum(max(0.0, float(event.queue_wait_ms or 0.0)) for event in completed_events)
    execution_total_ms = sum(max(0.0, float(event.execution_ms or 0.0)) for event in completed_events)
    p0_events = [event for event in completed_events if str(event.priority or "").upper() == "P0"]
    p1_events = [event for event in completed_events if str(event.priority or "").upper() == "P1"]

    def priority_metrics(rows: list[Any]) -> tuple[float, float, float, float, float, float]:
        wait_total = sum(max(0.0, float(row.queue_wait_ms or 0.0)) for row in rows)
        execution_total = sum(max(0.0, float(row.execution_ms or 0.0)) for row in rows)
        return (
            wait_total,
            _average(wait_total, len(rows)),
            max([0.0] + [max(0.0, float(row.queue_wait_ms or 0.0)) for row in rows]),
            execution_total,
            _average(execution_total, len(rows)),
            max([0.0] + [max(0.0, float(row.execution_ms or 0.0)) for row in rows]),
        )

    p0_wait_total, p0_wait_avg, p0_wait_max, p0_exec_total, p0_exec_avg, p0_exec_max = priority_metrics(p0_events)
    p1_wait_total, p1_wait_avg, p1_wait_max, p1_exec_total, p1_exec_avg, p1_exec_max = priority_metrics(p1_events)

    snapshot_count = len(snapshots)
    backlog_ages: list[float] = []
    for row in snapshots:
        observed = _utc_datetime(row.observed_at)
        oldest = _utc_datetime(row.oldest_backlog_created_at)
        if observed is not None and oldest is not None and observed >= oldest:
            backlog_ages.append((observed - oldest).total_seconds())

    availability_events = [
        row
        for row in service_events
        if str(row.event_type or "") == "availability_state_changed"
    ]
    unavailable_transitions = sum(
        1 for row in availability_events if str(row.to_status or "").lower() == "unavailable"
    )
    recovery_transitions = sum(
        1
        for row in availability_events
        if str(row.to_status or "").lower() == "ready"
        and str(row.from_status or "").lower() != "ready"
    )

    return {
        "node_name": node_name,
        "period_grain": "hour",
        "period_start": period_start,
        "period_end": period_end,
        "observed_from_at": observed_from_at,
        "observed_through_at": observed_through_at,
        "observation_window_ms": observation_window_ms,
        "refreshed_at": datetime.now(timezone.utc),
        "compute_event_count": event_count,
        "successful_event_count": successful_event_count,
        "failed_event_count": event_count - successful_event_count,
        "p0_event_count": priority_counts.get("P0", 0),
        "p1_event_count": priority_counts.get("P1", 0),
        "p2_event_count": priority_counts.get("P2", 0),
        "p3_event_count": priority_counts.get("P3", 0),
        "workload_counts_json": _count_values(completed_events, "workload_type") or None,
        "transport_counts_json": _count_values(completed_events, "transport_path") or None,
        "queue_wait_total_ms": queue_wait_total_ms,
        "queue_wait_avg_ms": _average(queue_wait_total_ms, event_count),
        "queue_wait_max_ms": max([0.0] + [max(0.0, float(event.queue_wait_ms or 0.0)) for event in completed_events]),
        "queue_depth_at_admission_avg": _average(sum(max(0, int(event.queue_depth_at_admission or 0)) for event in completed_events), event_count),
        "queue_depth_at_admission_peak": max([0] + [max(0, int(event.queue_depth_at_admission or 0)) for event in completed_events]),
        "active_requests_at_admission_avg": _average(sum(max(0, int(event.active_requests_at_admission or 0)) for event in completed_events), event_count),
        "active_requests_at_admission_peak": max([0] + [max(0, int(event.active_requests_at_admission or 0)) for event in completed_events]),
        "execution_total_ms": execution_total_ms,
        "execution_avg_ms": _average(execution_total_ms, event_count),
        "execution_max_ms": max([0.0] + [max(0.0, float(event.execution_ms or 0.0)) for event in completed_events]),
        "p0_queue_wait_total_ms": p0_wait_total,
        "p0_queue_wait_avg_ms": p0_wait_avg,
        "p0_queue_wait_max_ms": p0_wait_max,
        "p0_execution_total_ms": p0_exec_total,
        "p0_execution_avg_ms": p0_exec_avg,
        "p0_execution_max_ms": p0_exec_max,
        "p1_queue_wait_total_ms": p1_wait_total,
        "p1_queue_wait_avg_ms": p1_wait_avg,
        "p1_queue_wait_max_ms": p1_wait_max,
        "p1_execution_total_ms": p1_exec_total,
        "p1_execution_avg_ms": p1_exec_avg,
        "p1_execution_max_ms": p1_exec_max,
        "occupied_execution_ms": occupied_execution_ms,
        "qualified_capacity_slots": capacity_slots,
        "qualified_capacity_ms": qualified_capacity_ms,
        "qualified_compute_occupancy_pct": occupancy_pct,
        "input_units_total": sum(max(0, int(event.input_units or 0)) for event in completed_events),
        "output_units_total": sum(max(0, int(event.output_units or 0)) for event in completed_events),
        "snapshot_count": snapshot_count,
        "reachable_snapshot_count": sum(1 for row in snapshots if row.service_reachable),
        "ready_snapshot_count": sum(1 for row in snapshots if str(row.service_status or "").lower() == "ready"),
        "circuit_open_snapshot_count": sum(1 for row in snapshots if row.circuit_open),
        "active_requests_avg": _average(sum(max(0, int(row.active_requests or 0)) for row in snapshots), snapshot_count),
        "active_requests_peak": max([0] + [max(0, int(row.active_requests or 0)) for row in snapshots]),
        "waiting_requests_avg": _average(sum(max(0, int(row.waiting_requests or 0)) for row in snapshots), snapshot_count),
        "waiting_requests_peak": max([0] + [max(0, int(row.waiting_requests or 0)) for row in snapshots]),
        "oldest_wait_max_ms": max([0.0] + [max(0.0, float(row.oldest_wait_ms or 0.0)) for row in snapshots]),
        "spool_backlog_avg": _average(sum(max(0, int(row.spool_backlog or 0)) for row in snapshots), snapshot_count),
        "spool_backlog_peak": max([0] + [max(0, int(row.spool_backlog or 0)) for row in snapshots]),
        "spool_in_flight_avg": _average(sum(max(0, int(row.spool_in_flight or 0)) for row in snapshots), snapshot_count),
        "spool_in_flight_peak": max([0] + [max(0, int(row.spool_in_flight or 0)) for row in snapshots]),
        "oldest_backlog_age_max_seconds": max([0.0] + backlog_ages),
        "max_consecutive_failures": max([0] + [max(0, int(row.consecutive_failures or 0)) for row in snapshots]),
        "service_event_count": len(service_events),
        "availability_transition_count": len(availability_events),
        "unavailable_transition_count": unavailable_transitions,
        "recovery_transition_count": recovery_transitions,
    }


def _daily_capacity_rollup_values(
    connection,
    *,
    node_name: str,
    period_start: datetime,
    period_end: datetime,
) -> dict[str, Any] | None:
    hourly_rows = [
        SimpleNamespace(**dict(row))
        for row in connection.execute(
            select(IntelligenceCapacityRollup.__table__).where(
                IntelligenceCapacityRollup.node_name == node_name,
                IntelligenceCapacityRollup.period_grain == "hour",
                IntelligenceCapacityRollup.period_start >= period_start,
                IntelligenceCapacityRollup.period_start < period_end,
            ).order_by(IntelligenceCapacityRollup.period_start.asc())
        ).mappings().all()
    ]
    if not hourly_rows:
        return None

    observed_from_values = [
        value
        for value in (_utc_datetime(row.observed_from_at) for row in hourly_rows)
        if value is not None
    ]
    observed_through_values = [
        value
        for value in (_utc_datetime(row.observed_through_at) for row in hourly_rows)
        if value is not None
    ]
    event_count = sum(max(0, int(row.compute_event_count or 0)) for row in hourly_rows)
    p0_count = sum(max(0, int(row.p0_event_count or 0)) for row in hourly_rows)
    p1_count = sum(max(0, int(row.p1_event_count or 0)) for row in hourly_rows)
    snapshot_count = sum(max(0, int(row.snapshot_count or 0)) for row in hourly_rows)
    occupied_execution_ms = sum(max(0.0, float(row.occupied_execution_ms or 0.0)) for row in hourly_rows)
    qualified_capacity_ms = sum(max(0.0, float(row.qualified_capacity_ms or 0.0)) for row in hourly_rows)

    queue_wait_total_ms = sum(max(0.0, float(row.queue_wait_total_ms or 0.0)) for row in hourly_rows)
    execution_total_ms = sum(max(0.0, float(row.execution_total_ms or 0.0)) for row in hourly_rows)
    p0_wait_total = sum(max(0.0, float(row.p0_queue_wait_total_ms or 0.0)) for row in hourly_rows)
    p0_exec_total = sum(max(0.0, float(row.p0_execution_total_ms or 0.0)) for row in hourly_rows)
    p1_wait_total = sum(max(0.0, float(row.p1_queue_wait_total_ms or 0.0)) for row in hourly_rows)
    p1_exec_total = sum(max(0.0, float(row.p1_execution_total_ms or 0.0)) for row in hourly_rows)

    def weighted_snapshot_average(attribute: str) -> float:
        if snapshot_count <= 0:
            return 0.0
        total = sum(
            max(0.0, float(getattr(row, attribute, 0.0) or 0.0))
            * max(0, int(row.snapshot_count or 0))
            for row in hourly_rows
        )
        return total / snapshot_count

    return {
        "node_name": node_name,
        "period_grain": "day",
        "period_start": period_start,
        "period_end": period_end,
        "observed_from_at": min(observed_from_values) if observed_from_values else None,
        "observed_through_at": max(observed_through_values) if observed_through_values else None,
        "observation_window_ms": sum(max(0.0, float(row.observation_window_ms or 0.0)) for row in hourly_rows),
        "refreshed_at": datetime.now(timezone.utc),
        "compute_event_count": event_count,
        "successful_event_count": sum(max(0, int(row.successful_event_count or 0)) for row in hourly_rows),
        "failed_event_count": sum(max(0, int(row.failed_event_count or 0)) for row in hourly_rows),
        "p0_event_count": p0_count,
        "p1_event_count": p1_count,
        "p2_event_count": sum(max(0, int(row.p2_event_count or 0)) for row in hourly_rows),
        "p3_event_count": sum(max(0, int(row.p3_event_count or 0)) for row in hourly_rows),
        "workload_counts_json": _merge_count_mappings(hourly_rows, "workload_counts_json") or None,
        "transport_counts_json": _merge_count_mappings(hourly_rows, "transport_counts_json") or None,
        "queue_wait_total_ms": queue_wait_total_ms,
        "queue_wait_avg_ms": _average(queue_wait_total_ms, event_count),
        "queue_wait_max_ms": max([0.0] + [max(0.0, float(row.queue_wait_max_ms or 0.0)) for row in hourly_rows]),
        "queue_depth_at_admission_avg": _average(sum(max(0.0, float(row.queue_depth_at_admission_avg or 0.0)) * max(0, int(row.compute_event_count or 0)) for row in hourly_rows), event_count),
        "queue_depth_at_admission_peak": max([0] + [max(0, int(row.queue_depth_at_admission_peak or 0)) for row in hourly_rows]),
        "active_requests_at_admission_avg": _average(sum(max(0.0, float(row.active_requests_at_admission_avg or 0.0)) * max(0, int(row.compute_event_count or 0)) for row in hourly_rows), event_count),
        "active_requests_at_admission_peak": max([0] + [max(0, int(row.active_requests_at_admission_peak or 0)) for row in hourly_rows]),
        "execution_total_ms": execution_total_ms,
        "execution_avg_ms": _average(execution_total_ms, event_count),
        "execution_max_ms": max([0.0] + [max(0.0, float(row.execution_max_ms or 0.0)) for row in hourly_rows]),
        "p0_queue_wait_total_ms": p0_wait_total,
        "p0_queue_wait_avg_ms": _average(p0_wait_total, p0_count),
        "p0_queue_wait_max_ms": max([0.0] + [max(0.0, float(row.p0_queue_wait_max_ms or 0.0)) for row in hourly_rows]),
        "p0_execution_total_ms": p0_exec_total,
        "p0_execution_avg_ms": _average(p0_exec_total, p0_count),
        "p0_execution_max_ms": max([0.0] + [max(0.0, float(row.p0_execution_max_ms or 0.0)) for row in hourly_rows]),
        "p1_queue_wait_total_ms": p1_wait_total,
        "p1_queue_wait_avg_ms": _average(p1_wait_total, p1_count),
        "p1_queue_wait_max_ms": max([0.0] + [max(0.0, float(row.p1_queue_wait_max_ms or 0.0)) for row in hourly_rows]),
        "p1_execution_total_ms": p1_exec_total,
        "p1_execution_avg_ms": _average(p1_exec_total, p1_count),
        "p1_execution_max_ms": max([0.0] + [max(0.0, float(row.p1_execution_max_ms or 0.0)) for row in hourly_rows]),
        "occupied_execution_ms": occupied_execution_ms,
        "qualified_capacity_slots": max([1] + [max(1, int(row.qualified_capacity_slots or 1)) for row in hourly_rows]),
        "qualified_capacity_ms": qualified_capacity_ms,
        "qualified_compute_occupancy_pct": min(100.0, (occupied_execution_ms / qualified_capacity_ms) * 100.0) if qualified_capacity_ms > 0.0 else 0.0,
        "input_units_total": sum(max(0, int(row.input_units_total or 0)) for row in hourly_rows),
        "output_units_total": sum(max(0, int(row.output_units_total or 0)) for row in hourly_rows),
        "snapshot_count": snapshot_count,
        "reachable_snapshot_count": sum(max(0, int(row.reachable_snapshot_count or 0)) for row in hourly_rows),
        "ready_snapshot_count": sum(max(0, int(row.ready_snapshot_count or 0)) for row in hourly_rows),
        "circuit_open_snapshot_count": sum(max(0, int(row.circuit_open_snapshot_count or 0)) for row in hourly_rows),
        "active_requests_avg": weighted_snapshot_average("active_requests_avg"),
        "active_requests_peak": max([0] + [max(0, int(row.active_requests_peak or 0)) for row in hourly_rows]),
        "waiting_requests_avg": weighted_snapshot_average("waiting_requests_avg"),
        "waiting_requests_peak": max([0] + [max(0, int(row.waiting_requests_peak or 0)) for row in hourly_rows]),
        "oldest_wait_max_ms": max([0.0] + [max(0.0, float(row.oldest_wait_max_ms or 0.0)) for row in hourly_rows]),
        "spool_backlog_avg": weighted_snapshot_average("spool_backlog_avg"),
        "spool_backlog_peak": max([0] + [max(0, int(row.spool_backlog_peak or 0)) for row in hourly_rows]),
        "spool_in_flight_avg": weighted_snapshot_average("spool_in_flight_avg"),
        "spool_in_flight_peak": max([0] + [max(0, int(row.spool_in_flight_peak or 0)) for row in hourly_rows]),
        "oldest_backlog_age_max_seconds": max([0.0] + [max(0.0, float(row.oldest_backlog_age_max_seconds or 0.0)) for row in hourly_rows]),
        "max_consecutive_failures": max([0] + [max(0, int(row.max_consecutive_failures or 0)) for row in hourly_rows]),
        "service_event_count": sum(max(0, int(row.service_event_count or 0)) for row in hourly_rows),
        "availability_transition_count": sum(max(0, int(row.availability_transition_count or 0)) for row in hourly_rows),
        "unavailable_transition_count": sum(max(0, int(row.unavailable_transition_count or 0)) for row in hourly_rows),
        "recovery_transition_count": sum(max(0, int(row.recovery_transition_count or 0)) for row in hourly_rows),
    }


def _refresh_capacity_rollups(node_name: str, observed_at: datetime) -> bool:
    """Refresh bounded hourly/daily summaries from authoritative raw history."""

    point = _utc_datetime(observed_at) or datetime.now(timezone.utc)
    hour_start, hour_end = _period_bounds(point, "hour")
    hourly_periods = [(hour_start, hour_end)]
    if point.minute < 10:
        previous_start = hour_start - timedelta(hours=1)
        hourly_periods.append((previous_start, hour_start))

    try:
        with engine.begin() as connection:
            refreshed_days: set[datetime] = set()
            for start, end in hourly_periods:
                values = _hourly_capacity_rollup_values(
                    connection,
                    node_name=node_name,
                    period_start=start,
                    period_end=end,
                    as_of=point,
                )
                if values is not None:
                    _replace_capacity_rollup(connection, values)
                    refreshed_days.add(start.replace(hour=0, minute=0, second=0, microsecond=0))

            current_day_start, current_day_end = _period_bounds(point, "day")
            refreshed_days.add(current_day_start)
            for day_start in sorted(refreshed_days):
                values = _daily_capacity_rollup_values(
                    connection,
                    node_name=node_name,
                    period_start=day_start,
                    period_end=day_start + timedelta(days=1),
                )
                if values is not None:
                    _replace_capacity_rollup(connection, values)

        logger.debug(
            "[SIS][CAPACITY_ROLLUPS_REFRESHED] node=%s hour=%s",
            node_name,
            hour_start.isoformat(),
        )
        return True
    except SQLAlchemyError as exc:
        logger.warning("[SIS][CAPACITY_ROLLUP_DB_FAILURE] node=%s error=%s", node_name, exc)
        return False
    except Exception as exc:
        logger.exception("[SIS][CAPACITY_ROLLUP_FAILURE] node=%s error=%s", node_name, exc)
        return False


def _refresh_crossed_hour_rollups(
    *,
    node_name: str,
    observed_at: datetime,
    execution_ms: float,
) -> None:
    """Repair completed hour buckets crossed by a newly persisted execution."""

    event_end = _utc_datetime(observed_at) or datetime.now(timezone.utc)
    event_start = event_end - timedelta(milliseconds=max(0.0, float(execution_ms)))
    current_hour_start, _ = _period_bounds(event_end, "hour")
    start_hour, _ = _period_bounds(event_start, "hour")
    if start_hour >= current_hour_start:
        return

    period_count = int((current_hour_start - start_hour).total_seconds() // 3600)
    if period_count > 48:
        logger.warning(
            "[SIS][CAPACITY_ROLLUP_CROSS_HOUR_BOUNDED] node=%s hours=%s",
            node_name,
            period_count,
        )
        start_hour = current_hour_start - timedelta(hours=48)

    try:
        with engine.begin() as connection:
            affected_days: set[datetime] = set()
            cursor = start_hour
            while cursor < current_hour_start:
                values = _hourly_capacity_rollup_values(
                    connection,
                    node_name=node_name,
                    period_start=cursor,
                    period_end=cursor + timedelta(hours=1),
                    as_of=event_end,
                )
                if values is not None:
                    _replace_capacity_rollup(connection, values)
                    affected_days.add(cursor.replace(hour=0, minute=0, second=0, microsecond=0))
                cursor += timedelta(hours=1)

            for day_start in sorted(affected_days):
                values = _daily_capacity_rollup_values(
                    connection,
                    node_name=node_name,
                    period_start=day_start,
                    period_end=day_start + timedelta(days=1),
                )
                if values is not None:
                    _replace_capacity_rollup(connection, values)
    except SQLAlchemyError as exc:
        logger.warning("[SIS][CAPACITY_ROLLUP_CROSS_HOUR_DB_FAILURE] node=%s error=%s", node_name, exc)
    except Exception as exc:
        logger.exception("[SIS][CAPACITY_ROLLUP_CROSS_HOUR_FAILURE] node=%s error=%s", node_name, exc)

def persist_compute_execution_telemetry(
    payload: Any,
    *,
    transport_path: str,
) -> bool:
    """Persist one bounded telemetry packet without affecting compute success.

    Operational telemetry must never become a new failure authority for Chat,
    RAG, ingestion, or summary execution. Invalid or unavailable persistence is
    therefore logged and isolated from the governed compute result.
    """

    if not isinstance(payload, dict) or not payload:
        return False

    try:
        telemetry = deserialize_compute_execution_telemetry(payload)
        observed_at = _observed_datetime(telemetry.observed_at)
        event_key = _event_key(telemetry)
        clean_transport_path = (
            str(transport_path or "unknown").strip()[:64] or "unknown"
        )

        values = {
            "event_key": event_key,
            "observed_at": observed_at,
            "node_name": telemetry.node,
            "workload_type": telemetry.workload_type,
            "priority": telemetry.priority.value,
            "request_id": telemetry.request_id,
            "fairness_bucket": telemetry.fairness_bucket,
            "call_site": telemetry.call_site,
            "transport_path": clean_transport_path,
            "queue_wait_ms": telemetry.queue_wait_ms,
            "execution_ms": telemetry.execution_ms,
            "queue_depth_at_admission": telemetry.queue_depth_at_admission,
            "active_requests_at_admission": (
                telemetry.active_requests_at_admission
            ),
            "max_concurrent_requests": telemetry.max_concurrent_requests,
            "input_units": telemetry.input_units,
            "output_units": telemetry.output_units,
            "success": telemetry.success,
        }

        try:
            with engine.begin() as connection:
                connection.execute(
                    IntelligenceComputeEvent.__table__.insert().values(**values)
                )
        except IntegrityError:
            logger.debug(
                "[SIS][COMPUTE_TELEMETRY_DUPLICATE] key=%s request_id=%s",
                event_key,
                telemetry.request_id,
            )
            return False

        _refresh_crossed_hour_rollups(
            node_name=telemetry.node,
            observed_at=observed_at,
            execution_ms=telemetry.execution_ms,
        )

        logger.info(
            "[SIS][COMPUTE_TELEMETRY_PERSISTED] node=%s workload=%s "
            "priority=%s request_id=%s wait_ms=%.3f execution_ms=%.3f "
            "success=%s",
            telemetry.node,
            telemetry.workload_type,
            telemetry.priority.value,
            telemetry.request_id,
            telemetry.queue_wait_ms,
            telemetry.execution_ms,
            telemetry.success,
        )
        return True
    except (ValueError, TypeError) as exc:
        logger.warning(
            "[SIS][COMPUTE_TELEMETRY_INVALID] transport=%s error=%s",
            transport_path,
            exc,
        )
        return False
    except SQLAlchemyError as exc:
        logger.warning(
            "[SIS][COMPUTE_TELEMETRY_DB_FAILURE] transport=%s error=%s",
            transport_path,
            exc,
        )
        return False
    except Exception as exc:
        logger.exception(
            "[SIS][COMPUTE_TELEMETRY_PERSISTENCE_FAILURE] transport=%s error=%s",
            transport_path,
            exc,
        )
        return False


def persist_compute_request_event(
    *,
    attempt_id: str,
    request_id: str | None,
    workload_type: str,
    priority: Any,
    call_site: str | None,
    transport_path: str,
    request_bytes: int = 0,
    response_bytes: int = 0,
    round_trip_ms: float = 0.0,
    http_status: int | None = None,
    outcome_class: str,
    failure_code: str | None = None,
    telemetry_payload: Any = None,
) -> bool:
    """Persist one bounded LOCAL compute-request observation.

    This is the internal correlation/transport companion to the authoritative
    execution event. It may exist without REMOTE execution telemetry when a
    request fails before SIS can return an execution result. No prompt, answer,
    evidence, file, user, Group, or permission data is accepted here.
    """

    clean_attempt_id = str(attempt_id or "").strip()[:64]
    if not clean_attempt_id:
        return False

    telemetry: ComputeExecutionTelemetry | None = None
    compute_event_key: str | None = None
    if isinstance(telemetry_payload, dict) and telemetry_payload:
        try:
            telemetry = deserialize_compute_execution_telemetry(telemetry_payload)
            compute_event_key = _event_key(telemetry)
        except (ValueError, TypeError):
            telemetry = None
            compute_event_key = None

    normalized_priority = str(getattr(priority, "value", priority) or "P0").strip().upper()[:8] or "P0"
    normalized_outcome = str(outcome_class or "unknown").strip().lower()[:32] or "unknown"
    telemetry_failure = (
        str(telemetry.failure_code or "").strip().lower()[:64] or None
        if telemetry is not None
        else None
    )
    normalized_failure = telemetry_failure or (
        str(failure_code or "").strip().lower()[:64] or None
    )

    values = {
        "observed_at": datetime.now(timezone.utc),
        "attempt_id": clean_attempt_id,
        "request_id": str(request_id or "").strip()[:128] or None,
        "compute_event_key": compute_event_key,
        "node_name": telemetry.node if telemetry is not None else None,
        "workload_type": str(workload_type or "compute").strip().lower()[:64] or "compute",
        "priority": normalized_priority,
        "call_site": str(call_site or "").strip()[:128] or None,
        "transport_path": str(transport_path or "unknown").strip()[:64] or "unknown",
        "request_bytes": _nonnegative_int(request_bytes),
        "response_bytes": _nonnegative_int(response_bytes),
        "round_trip_ms": _nonnegative_float(round_trip_ms),
        "http_status": (
            _nonnegative_int(http_status)
            if http_status is not None
            else None
        ),
        "remote_execution_observed": telemetry is not None,
        "remote_success": telemetry.success if telemetry is not None else None,
        "outcome_class": normalized_outcome,
        "failure_code": normalized_failure,
        "model_name": telemetry.model_name if telemetry is not None else None,
        "runtime_profile": telemetry.runtime_profile if telemetry is not None else None,
        "runtime_fingerprint": (
            telemetry.runtime_fingerprint if telemetry is not None else None
        ),
    }

    try:
        with engine.begin() as connection:
            connection.execute(
                IntelligenceComputeRequestEvent.__table__.insert().values(**values)
            )
        logger.debug(
            "[SIS][COMPUTE_REQUEST_EVENT_PERSISTED] attempt_id=%s request_id=%s "
            "workload=%s priority=%s outcome=%s failure=%s round_trip_ms=%.3f",
            clean_attempt_id,
            values["request_id"],
            values["workload_type"],
            normalized_priority,
            normalized_outcome,
            normalized_failure,
            values["round_trip_ms"],
        )
        return True
    except IntegrityError:
        logger.debug(
            "[SIS][COMPUTE_REQUEST_EVENT_DUPLICATE] attempt_id=%s",
            clean_attempt_id,
        )
        return False
    except SQLAlchemyError as exc:
        logger.warning(
            "[SIS][COMPUTE_REQUEST_EVENT_DB_FAILURE] attempt_id=%s error=%s",
            clean_attempt_id,
            exc,
        )
        return False
    except Exception as exc:
        logger.exception(
            "[SIS][COMPUTE_REQUEST_EVENT_FAILURE] attempt_id=%s error=%s",
            clean_attempt_id,
            exc,
        )
        return False



def persist_request_usage_attribution(
    *,
    request_id: str,
    user_id: int,
    organization_id: str | None = None,
    group_id: str | None = None,
    conversation_id: str | None = None,
    case_id: str | None = None,
    request_surface: str,
    scope_type: str,
    attribution_source: str,
) -> bool:
    """Persist one authoritative LOCAL request-attribution record.

    Compute execution and transport history remains content-free and joins to
    this business context only through request_id. The caller must supply only
    authority it has already resolved; this repository never infers tenant or
    Group identity from files, memberships, retrieval hits, or SIS telemetry.
    """

    clean_request_id = str(request_id or "").strip()[:128]
    if not clean_request_id:
        return False

    try:
        clean_user_id = int(user_id or 0)
    except (TypeError, ValueError):
        clean_user_id = 0

    if clean_user_id <= 0:
        return False

    clean_organization_id = str(organization_id or "").strip()[:64] or None
    clean_group_id = str(group_id or "").strip()[:64] or None
    clean_surface = str(request_surface or "governed_request").strip().lower()[:64]
    clean_scope_type = str(scope_type or "user").strip().lower()[:32]
    clean_source = str(attribution_source or "authenticated_request").strip().lower()[:64]

    # A Group-scoped attribution must be explicit at the caller. No Group id is
    # synthesized from organization scope or resource authority here.
    if clean_group_id:
        clean_scope_type = "group"
    elif clean_organization_id and clean_scope_type == "group":
        clean_scope_type = "organization"

    values = {
        "request_id": clean_request_id,
        "observed_at": datetime.now(timezone.utc),
        "user_id": clean_user_id,
        "organization_id": clean_organization_id,
        "group_id": clean_group_id,
        "conversation_id": str(conversation_id or "").strip()[:64] or None,
        "case_id": str(case_id or "").strip()[:64] or None,
        "request_surface": clean_surface or "governed_request",
        "scope_type": clean_scope_type or "user",
        "attribution_source": clean_source or "authenticated_request",
    }

    try:
        with engine.begin() as connection:
            connection.execute(
                IntelligenceRequestAttribution.__table__.insert().values(**values)
            )
        logger.debug(
            "[SIS][REQUEST_USAGE_ATTRIBUTION_PERSISTED] request_id=%s "
            "user_id=%s organization_id=%s group_id=%s scope=%s surface=%s",
            clean_request_id,
            clean_user_id,
            clean_organization_id,
            clean_group_id,
            values["scope_type"],
            values["request_surface"],
        )
        return True
    except IntegrityError:
        logger.debug(
            "[SIS][REQUEST_USAGE_ATTRIBUTION_DUPLICATE] request_id=%s",
            clean_request_id,
        )
        return False
    except SQLAlchemyError as exc:
        logger.warning(
            "[SIS][REQUEST_USAGE_ATTRIBUTION_DB_FAILURE] request_id=%s error=%s",
            clean_request_id,
            exc,
        )
        return False
    except Exception as exc:
        logger.exception(
            "[SIS][REQUEST_USAGE_ATTRIBUTION_FAILURE] request_id=%s error=%s",
            clean_request_id,
            exc,
        )
        return False

def persist_capacity_snapshot(
    health: Any,
    *,
    service_reachable: bool,
) -> bool:
    """Persist one bounded capacity observation from the existing health probe.

    This function performs no remote probing. It records the already-observed
    Portable SIS capacity packet together with a same-transaction read of the
    LOCAL durable Intelligence Spool, keeping Solomon authoritative for history.
    """

    if not isinstance(health, dict) or not health:
        return False

    try:
        capacity = _bounded_mapping(health.get("capacity"))
        active_by_priority = _bounded_mapping(capacity.get("active_by_priority"))
        waiting_by_priority = _bounded_mapping(capacity.get("waiting_by_priority"))
        runtime = _bounded_mapping(health.get("runtime"))
        embedding = _bounded_mapping(health.get("embedding"))
        node_name = str(health.get("node") or "unknown").strip()[:128] or "unknown"
        service_status = (
            str(health.get("status") or "unknown").strip().lower()[:32]
            or "unknown"
        )

        values = {
            "observed_at": _epoch_datetime(health.get("observed_at")),
            "node_name": node_name,
            "service_status": service_status,
            "service_reachable": bool(service_reachable),
            "interactive_ready": bool(health.get("interactive_ready")),
            "embedding_ready": bool(health.get("embedding_ready")),
            "circuit_open": bool(health.get("circuit_open")),
            "health_source": (
                str(health.get("health_source") or "health").strip()[:64]
                or "health"
            ),
            "consecutive_failures": _nonnegative_int(
                health.get("consecutive_failures")
            ),
            "max_concurrent_requests": max(
                1,
                _nonnegative_int(
                    capacity.get("max_concurrent_requests"),
                    default=1,
                ),
            ),
            "active_requests": _nonnegative_int(capacity.get("active_requests")),
            "waiting_requests": _nonnegative_int(capacity.get("waiting_requests")),
            "foreground_waiting": _nonnegative_int(capacity.get("foreground_waiting")),
            "background_waiting": _nonnegative_int(capacity.get("background_waiting")),
            "oldest_wait_ms": _nonnegative_float(capacity.get("oldest_wait_ms")),
            "p0_active_requests": _priority_count(active_by_priority, "P0"),
            "p1_active_requests": _priority_count(active_by_priority, "P1"),
            "p2_active_requests": _priority_count(active_by_priority, "P2"),
            "p3_active_requests": _priority_count(active_by_priority, "P3"),
            "p0_waiting_requests": _priority_count(waiting_by_priority, "P0"),
            "p1_waiting_requests": _priority_count(waiting_by_priority, "P1"),
            "p2_waiting_requests": _priority_count(waiting_by_priority, "P2"),
            "p3_waiting_requests": _priority_count(waiting_by_priority, "P3"),
            "runtime_fingerprint": _runtime_fingerprint(runtime),
            "runtime_json": runtime or None,
            "embedding_json": embedding or None,
        }

        with engine.begin() as connection:
            values.update(_spool_capacity_values(connection))
            connection.execute(
                IntelligenceCapacitySnapshot.__table__.insert().values(**values)
            )

        _refresh_capacity_rollups(
            node_name=node_name,
            observed_at=values["observed_at"],
        )

        logger.debug(
            "[SIS][CAPACITY_SNAPSHOT_PERSISTED] node=%s status=%s "
            "active=%s waiting=%s backlog=%s reachable=%s",
            node_name,
            service_status,
            values["active_requests"],
            values["waiting_requests"],
            values["spool_backlog"],
            bool(service_reachable),
        )
        return True
    except SQLAlchemyError as exc:
        logger.warning("[SIS][CAPACITY_SNAPSHOT_DB_FAILURE] error=%s", exc)
        return False
    except Exception as exc:
        logger.exception("[SIS][CAPACITY_SNAPSHOT_FAILURE] error=%s", exc)
        return False


def persist_service_state_transition(
    *,
    previous_status: str,
    current_status: str,
    previous_circuit_open: bool,
    current_circuit_open: bool,
    health: Any,
    service_reachable: bool,
) -> bool:
    """Persist one availability/circuit transition without affecting service."""

    if (
        str(previous_status or "") == str(current_status or "")
        and bool(previous_circuit_open) == bool(current_circuit_open)
    ):
        return False

    payload = health if isinstance(health, dict) else {}
    details: dict[str, Any] = {
        "interactive_ready": bool(payload.get("interactive_ready")),
        "embedding_ready": bool(payload.get("embedding_ready")),
    }
    if payload.get("http_status") is not None:
        details["http_status"] = _nonnegative_int(payload.get("http_status"))
    stage = str(payload.get("stage") or "").strip()[:128]
    if stage:
        details["stage"] = stage
    error_text = str(payload.get("error") or "").strip()[:1024]
    if error_text:
        details["error"] = error_text

    try:
        values = {
            "observed_at": _epoch_datetime(payload.get("observed_at")),
            "node_name": (
                str(payload.get("node") or "unknown").strip()[:128]
                or "unknown"
            ),
            "event_type": "availability_state_changed",
            "from_status": str(previous_status or "unknown").strip()[:32] or None,
            "to_status": str(current_status or "unknown").strip()[:32] or "unknown",
            "from_circuit_open": bool(previous_circuit_open),
            "to_circuit_open": bool(current_circuit_open),
            "service_reachable": bool(service_reachable),
            "health_source": (
                str(payload.get("health_source") or "health").strip()[:64]
                or "health"
            ),
            "consecutive_failures": _nonnegative_int(
                payload.get("consecutive_failures")
            ),
            "details_json": details,
        }
        with engine.begin() as connection:
            connection.execute(
                IntelligenceServiceEvent.__table__.insert().values(**values)
            )
        return True
    except SQLAlchemyError as exc:
        logger.warning("[SIS][SERVICE_EVENT_DB_FAILURE] error=%s", exc)
        return False
    except Exception as exc:
        logger.exception("[SIS][SERVICE_EVENT_PERSISTENCE_FAILURE] error=%s", exc)
        return False

# ===============================================================
# RESOURCE USAGE REPORTING READ MODEL
# ===============================================================

def _report_iso(value: Any) -> str | None:
    point = _utc_datetime(value)
    return point.isoformat() if point else None


def _report_average(values: list[float]) -> float:
    if not values:
        return 0.0
    return float(sum(values)) / float(len(values))


def _report_percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(max(0.0, float(value or 0.0)) for value in values)
    index = max(0, min(len(ordered) - 1, int((len(ordered) * percentile) + 0.999999) - 1))
    return float(ordered[index])


def _report_counts(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or '').strip()
        if value:
            counts[value] = counts.get(value, 0) + 1
    return counts


def _organization_request_predicate(model, organization_id: str):
    attribution_exists = select(IntelligenceRequestAttribution.id).where(
        IntelligenceRequestAttribution.request_id == model.request_id,
        IntelligenceRequestAttribution.organization_id == organization_id,
    ).exists()
    job_exists = select(IntelligenceJob.id).where(
        IntelligenceJob.request_id == model.request_id,
        IntelligenceJob.organization_id == organization_id,
    ).exists()
    return or_(attribution_exists, job_exists)


def _report_event_rows(
    connection,
    *,
    organization_id: str,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(
            IntelligenceComputeEvent.observed_at,
            IntelligenceComputeEvent.node_name,
            IntelligenceComputeEvent.workload_type,
            IntelligenceComputeEvent.priority,
            IntelligenceComputeEvent.request_id,
            IntelligenceComputeEvent.queue_wait_ms,
            IntelligenceComputeEvent.execution_ms,
            IntelligenceComputeEvent.queue_depth_at_admission,
            IntelligenceComputeEvent.active_requests_at_admission,
            IntelligenceComputeEvent.max_concurrent_requests,
            IntelligenceComputeEvent.success,
        ).where(
            IntelligenceComputeEvent.observed_at >= start_at,
            IntelligenceComputeEvent.observed_at < end_at,
            IntelligenceComputeEvent.request_id.is_not(None),
            _organization_request_predicate(
                IntelligenceComputeEvent,
                organization_id,
            ),
        ).order_by(IntelligenceComputeEvent.observed_at.asc())
    ).mappings().all()
    return [dict(row) for row in rows]


def _report_request_rows(
    connection,
    *,
    organization_id: str,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(
            IntelligenceComputeRequestEvent.observed_at,
            IntelligenceComputeRequestEvent.request_id,
            IntelligenceComputeRequestEvent.workload_type,
            IntelligenceComputeRequestEvent.priority,
            IntelligenceComputeRequestEvent.round_trip_ms,
            IntelligenceComputeRequestEvent.outcome_class,
            IntelligenceComputeRequestEvent.failure_code,
        ).where(
            IntelligenceComputeRequestEvent.observed_at >= start_at,
            IntelligenceComputeRequestEvent.observed_at < end_at,
            IntelligenceComputeRequestEvent.request_id.is_not(None),
            _organization_request_predicate(
                IntelligenceComputeRequestEvent,
                organization_id,
            ),
        ).order_by(IntelligenceComputeRequestEvent.observed_at.asc())
    ).mappings().all()
    return [dict(row) for row in rows]


def _hour_bucket(value: datetime) -> datetime:
    point = _utc_datetime(value) or datetime.now(timezone.utc)
    return point.replace(minute=0, second=0, microsecond=0)


def _organization_hourly_usage(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[datetime, list[dict[str, Any]]] = {}
    for row in rows:
        observed_at = _utc_datetime(row.get('observed_at'))
        if not observed_at:
            continue
        buckets.setdefault(_hour_bucket(observed_at), []).append(row)

    series: list[dict[str, Any]] = []
    for period_start in sorted(buckets):
        period_rows = buckets[period_start]
        waits = [float(row.get('queue_wait_ms') or 0.0) for row in period_rows]
        executions = [float(row.get('execution_ms') or 0.0) for row in period_rows]
        priorities = _report_counts(period_rows, 'priority')
        workloads = _report_counts(period_rows, 'workload_type')
        series.append({
            'period_start': period_start.isoformat(),
            'period_end': (period_start + timedelta(hours=1)).isoformat(),
            'compute_event_count': len(period_rows),
            'successful_event_count': sum(1 for row in period_rows if bool(row.get('success'))),
            'failed_event_count': sum(1 for row in period_rows if not bool(row.get('success'))),
            'priority_counts': priorities,
            'workload_counts': workloads,
            'queue_wait_avg_ms': _report_average(waits),
            'queue_wait_max_ms': max(waits, default=0.0),
            'execution_avg_ms': _report_average(executions),
            'execution_total_ms': float(sum(executions)),
        })
    return series


def _customer_capacity_rollups(
    connection,
    *,
    start_at: datetime,
    end_at: datetime,
) -> list[dict[str, Any]]:
    rows = connection.execute(
        select(IntelligenceCapacityRollup.__table__).where(
            IntelligenceCapacityRollup.period_grain == "hour",
            IntelligenceCapacityRollup.period_start
            >= start_at.replace(minute=0, second=0, microsecond=0),
            IntelligenceCapacityRollup.period_start < end_at,
        ).order_by(
            IntelligenceCapacityRollup.period_start.asc(),
            IntelligenceCapacityRollup.node_name.asc(),
        )
    ).mappings().all()

    buckets: dict[datetime, list[Any]] = {}
    for row in rows:
        period_start = _utc_datetime(row["period_start"])
        if period_start is None:
            continue
        buckets.setdefault(period_start, []).append(row)

    result: list[dict[str, Any]] = []
    for period_start in sorted(buckets):
        period_rows = buckets[period_start]
        qualified_capacity_ms = sum(
            float(row["qualified_capacity_ms"] or 0.0)
            for row in period_rows
        )
        occupied_execution_ms = sum(
            float(row["occupied_execution_ms"] or 0.0)
            for row in period_rows
        )
        occupancy_pct = (
            min(
                100.0,
                (occupied_execution_ms / qualified_capacity_ms) * 100.0,
            )
            if qualified_capacity_ms > 0.0
            else 0.0
        )
        compute_event_count = sum(
            int(row["compute_event_count"] or 0)
            for row in period_rows
        )
        p0_count = sum(int(row["p0_event_count"] or 0) for row in period_rows)
        p1_count = sum(int(row["p1_event_count"] or 0) for row in period_rows)
        p2_count = sum(int(row["p2_event_count"] or 0) for row in period_rows)
        p3_count = sum(int(row["p3_event_count"] or 0) for row in period_rows)

        def weighted_average(field: str, count: int) -> float:
            if count <= 0:
                return 0.0
            total = 0.0
            for row in period_rows:
                row_count = int(row["compute_event_count"] or 0)
                if field.startswith("p0_"):
                    row_count = int(row["p0_event_count"] or 0)
                elif field.startswith("p1_"):
                    row_count = int(row["p1_event_count"] or 0)
                total += float(row[field] or 0.0) * row_count
            return total / float(count)

        result.append({
            "period_start": period_start.isoformat(),
            "period_end": (period_start + timedelta(hours=1)).isoformat(),
            "qualified_compute_occupancy_pct": occupancy_pct,
            "headroom_pct": max(0.0, 100.0 - occupancy_pct),
            "compute_event_count": compute_event_count,
            "p0_event_count": p0_count,
            "p1_event_count": p1_count,
            "p2_event_count": p2_count,
            "p3_event_count": p3_count,
            "p0_queue_wait_avg_ms": weighted_average(
                "p0_queue_wait_avg_ms",
                p0_count,
            ),
            "p0_queue_wait_max_ms": max(
                [float(row["p0_queue_wait_max_ms"] or 0.0) for row in period_rows],
                default=0.0,
            ),
            "p1_queue_wait_avg_ms": weighted_average(
                "p1_queue_wait_avg_ms",
                p1_count,
            ),
            "p1_queue_wait_max_ms": max(
                [float(row["p1_queue_wait_max_ms"] or 0.0) for row in period_rows],
                default=0.0,
            ),
            "p0_execution_avg_ms": weighted_average(
                "p0_execution_avg_ms",
                p0_count,
            ),
            "p1_execution_avg_ms": weighted_average(
                "p1_execution_avg_ms",
                p1_count,
            ),
            "waiting_requests_peak": max(
                [int(row["waiting_requests_peak"] or 0) for row in period_rows],
                default=0,
            ),
            "spool_backlog_avg": max(
                [float(row["spool_backlog_avg"] or 0.0) for row in period_rows],
                default=0.0,
            ),
            "spool_backlog_peak": max(
                [int(row["spool_backlog_peak"] or 0) for row in period_rows],
                default=0,
            ),
            "oldest_backlog_age_max_seconds": max(
                [
                    float(row["oldest_backlog_age_max_seconds"] or 0.0)
                    for row in period_rows
                ],
                default=0.0,
            ),
            "availability_transition_count": sum(
                int(row["availability_transition_count"] or 0)
                for row in period_rows
            ),
            "unavailable_transition_count": sum(
                int(row["unavailable_transition_count"] or 0)
                for row in period_rows
            ),
            "recovery_transition_count": sum(
                int(row["recovery_transition_count"] or 0)
                for row in period_rows
            ),
        })

    return result

def get_organization_resource_usage_report(
    *,
    organization_id: str,
    start_at: datetime,
    end_at: datetime,
    include_installation_capacity: bool = False,
) -> dict[str, Any]:
    """Return a customer-safe, organization-authorized usage report.

    Business identity remains LOCAL. Request usage is limited to compute whose
    request_id is authoritatively attributable either through the explicit
    request-attribution record or a durable IntelligenceJob owned by the same
    organization. Installation-wide capacity is returned only when the caller
    has separately proven that exposing installation totals cannot cross a
    tenant boundary.
    """

    clean_organization_id = str(organization_id or '').strip()[:64]
    start_point = _utc_datetime(start_at)
    end_point = _utc_datetime(end_at)
    if not clean_organization_id or not start_point or not end_point or end_point <= start_point:
        raise ValueError('A valid organization and reporting window are required.')

    with engine.connect() as connection:
        event_rows = _report_event_rows(
            connection,
            organization_id=clean_organization_id,
            start_at=start_point,
            end_at=end_point,
        )
        request_rows = _report_request_rows(
            connection,
            organization_id=clean_organization_id,
            start_at=start_point,
            end_at=end_point,
        )
        capacity_rows = (
            _customer_capacity_rollups(
                connection,
                start_at=start_point,
                end_at=end_point,
            )
            if include_installation_capacity
            else []
        )

    waits = [float(row.get('queue_wait_ms') or 0.0) for row in event_rows]
    executions = [float(row.get('execution_ms') or 0.0) for row in event_rows]
    realtime_rows = [row for row in event_rows if str(row.get('priority') or '') in {'P0', 'P1'}]
    realtime_waits = [float(row.get('queue_wait_ms') or 0.0) for row in realtime_rows]
    realtime_executions = [float(row.get('execution_ms') or 0.0) for row in realtime_rows]
    request_round_trips = [float(row.get('round_trip_ms') or 0.0) for row in request_rows]
    window_ms = max(0.0, (end_point - start_point).total_seconds() * 1000.0)
    max_slots = max([1] + [max(1, int(row.get('max_concurrent_requests') or 1)) for row in event_rows])
    occupied_ms = float(sum(executions))
    attributable_capacity_ms = window_ms * max_slots

    return {
        'organization_id': clean_organization_id,
        'window': {
            'start_at': start_point.isoformat(),
            'end_at': end_point.isoformat(),
        },
        'capacity_scope': (
            'installation'
            if include_installation_capacity
            else 'organization_attributed_only'
        ),
        'summary': {
            'request_count': len({str(row.get('request_id')) for row in event_rows if row.get('request_id')}),
            'compute_event_count': len(event_rows),
            'successful_event_count': sum(1 for row in event_rows if bool(row.get('success'))),
            'failed_event_count': sum(1 for row in event_rows if not bool(row.get('success'))),
            'priority_counts': _report_counts(event_rows, 'priority'),
            'workload_counts': _report_counts(event_rows, 'workload_type'),
            'queue_wait_avg_ms': _report_average(waits),
            'queue_wait_p95_ms': _report_percentile(waits, 0.95),
            'queue_wait_max_ms': max(waits, default=0.0),
            'execution_avg_ms': _report_average(executions),
            'execution_p95_ms': _report_percentile(executions, 0.95),
            'realtime_queue_wait_avg_ms': _report_average(realtime_waits),
            'realtime_queue_wait_p95_ms': _report_percentile(realtime_waits, 0.95),
            'realtime_execution_avg_ms': _report_average(realtime_executions),
            'realtime_execution_p95_ms': _report_percentile(realtime_executions, 0.95),
            'qualified_compute_usage_ms': occupied_ms,
            'qualified_compute_occupancy_contribution_pct': (
                min(100.0, (occupied_ms / attributable_capacity_ms) * 100.0)
                if attributable_capacity_ms > 0.0
                else 0.0
            ),
            'compute_request_attempt_count': len(request_rows),
            'compute_request_failure_count': sum(
                1 for row in request_rows if str(row.get('outcome_class') or '') != 'success'
            ),
            'remote_round_trip_avg_ms': _report_average(request_round_trips),
            'remote_round_trip_p95_ms': _report_percentile(request_round_trips, 0.95),
        },
        'hourly_usage': _organization_hourly_usage(event_rows),
        'installation_capacity': capacity_rows,
        'group_usage': [],
        'coverage': {
            'interactive_request_attribution': True,
            'durable_job_organization_attribution': True,
            'explicit_group_attribution': False,
            'customer_token_accounting': False,
        },
    }


def get_internal_resource_usage_report(
    *,
    start_at: datetime,
    end_at: datetime,
    event_limit: int = 200,
) -> dict[str, Any]:
    """Return bounded installation-admin diagnostics from authoritative history."""

    start_point = _utc_datetime(start_at)
    end_point = _utc_datetime(end_at)
    if not start_point or not end_point or end_point <= start_point:
        raise ValueError("A valid reporting window is required.")
    limit = max(1, min(500, int(event_limit or 200)))

    with engine.connect() as connection:
        compute_rows = connection.execute(
            select(IntelligenceComputeEvent.__table__).where(
                IntelligenceComputeEvent.observed_at >= start_point,
                IntelligenceComputeEvent.observed_at < end_point,
            ).order_by(IntelligenceComputeEvent.observed_at.desc()).limit(limit)
        ).mappings().all()
        request_rows = connection.execute(
            select(IntelligenceComputeRequestEvent.__table__).where(
                IntelligenceComputeRequestEvent.observed_at >= start_point,
                IntelligenceComputeRequestEvent.observed_at < end_point,
            ).order_by(IntelligenceComputeRequestEvent.observed_at.desc()).limit(limit)
        ).mappings().all()
        service_rows = connection.execute(
            select(IntelligenceServiceEvent.__table__).where(
                IntelligenceServiceEvent.observed_at >= start_point,
                IntelligenceServiceEvent.observed_at < end_point,
            ).order_by(IntelligenceServiceEvent.observed_at.desc()).limit(limit)
        ).mappings().all()
        attribution_rows = connection.execute(
            select(IntelligenceRequestAttribution.__table__).where(
                IntelligenceRequestAttribution.observed_at >= start_point,
                IntelligenceRequestAttribution.observed_at < end_point,
            ).order_by(IntelligenceRequestAttribution.observed_at.desc()).limit(limit)
        ).mappings().all()
        rollup_rows = connection.execute(
            select(IntelligenceCapacityRollup.__table__).where(
                IntelligenceCapacityRollup.period_grain == "hour",
                IntelligenceCapacityRollup.period_start
                >= start_point.replace(minute=0, second=0, microsecond=0),
                IntelligenceCapacityRollup.period_start < end_point,
            ).order_by(
                IntelligenceCapacityRollup.period_start.desc(),
                IntelligenceCapacityRollup.node_name.asc(),
            )
        ).mappings().all()

    return {
        "window": {
            "start_at": start_point.isoformat(),
            "end_at": end_point.isoformat(),
        },
        "capacity_rollups": [
            {
                "rollup_id": row["rollup_id"],
                "node": row["node_name"],
                "period_start": _report_iso(row["period_start"]),
                "period_end": _report_iso(row["period_end"]),
                "qualified_compute_occupancy_pct": float(
                    row["qualified_compute_occupancy_pct"] or 0.0
                ),
                "qualified_capacity_slots": int(row["qualified_capacity_slots"] or 1),
                "compute_event_count": int(row["compute_event_count"] or 0),
                "priority_counts": {
                    "P0": int(row["p0_event_count"] or 0),
                    "P1": int(row["p1_event_count"] or 0),
                    "P2": int(row["p2_event_count"] or 0),
                    "P3": int(row["p3_event_count"] or 0),
                },
                "workload_counts": row["workload_counts_json"] or {},
                "transport_counts": row["transport_counts_json"] or {},
                "queue_wait_avg_ms": float(row["queue_wait_avg_ms"] or 0.0),
                "queue_wait_max_ms": float(row["queue_wait_max_ms"] or 0.0),
                "spool_backlog_peak": int(row["spool_backlog_peak"] or 0),
                "oldest_backlog_age_max_seconds": float(
                    row["oldest_backlog_age_max_seconds"] or 0.0
                ),
                "service_event_count": int(row["service_event_count"] or 0),
                "unavailable_transition_count": int(
                    row["unavailable_transition_count"] or 0
                ),
                "recovery_transition_count": int(row["recovery_transition_count"] or 0),
            }
            for row in rollup_rows
        ],
        "compute_events": [
            {
                "event_id": row["event_id"],
                "event_key": row["event_key"],
                "observed_at": _report_iso(row["observed_at"]),
                "node": row["node_name"],
                "workload_type": row["workload_type"],
                "priority": row["priority"],
                "request_id": row["request_id"],
                "fairness_bucket": row["fairness_bucket"],
                "call_site": row["call_site"],
                "transport_path": row["transport_path"],
                "queue_wait_ms": float(row["queue_wait_ms"] or 0.0),
                "execution_ms": float(row["execution_ms"] or 0.0),
                "queue_depth_at_admission": int(
                    row["queue_depth_at_admission"] or 0
                ),
                "active_requests_at_admission": int(
                    row["active_requests_at_admission"] or 0
                ),
                "max_concurrent_requests": int(
                    row["max_concurrent_requests"] or 1
                ),
                "input_units": row["input_units"],
                "output_units": row["output_units"],
                "success": bool(row["success"]),
            }
            for row in compute_rows
        ],
        "request_events": [
            {
                "request_event_id": row["request_event_id"],
                "attempt_id": row["attempt_id"],
                "request_id": row["request_id"],
                "compute_event_key": row["compute_event_key"],
                "observed_at": _report_iso(row["observed_at"]),
                "node": row["node_name"],
                "workload_type": row["workload_type"],
                "priority": row["priority"],
                "call_site": row["call_site"],
                "transport_path": row["transport_path"],
                "request_bytes": int(row["request_bytes"] or 0),
                "response_bytes": int(row["response_bytes"] or 0),
                "round_trip_ms": float(row["round_trip_ms"] or 0.0),
                "http_status": row["http_status"],
                "remote_execution_observed": bool(row["remote_execution_observed"]),
                "remote_success": row["remote_success"],
                "outcome_class": row["outcome_class"],
                "failure_code": row["failure_code"],
                "model_name": row["model_name"],
                "runtime_profile": row["runtime_profile"],
                "runtime_fingerprint": row["runtime_fingerprint"],
            }
            for row in request_rows
        ],
        "service_events": [
            {
                "event_id": row["event_id"],
                "observed_at": _report_iso(row["observed_at"]),
                "node": row["node_name"],
                "event_type": row["event_type"],
                "from_status": row["from_status"],
                "to_status": row["to_status"],
                "from_circuit_open": bool(row["from_circuit_open"]),
                "to_circuit_open": bool(row["to_circuit_open"]),
                "service_reachable": bool(row["service_reachable"]),
                "health_source": row["health_source"],
                "consecutive_failures": int(row["consecutive_failures"] or 0),
                "details": row["details_json"] or {},
            }
            for row in service_rows
        ],
        "request_attributions": [
            {
                "attribution_id": row["attribution_id"],
                "request_id": row["request_id"],
                "observed_at": _report_iso(row["observed_at"]),
                "user_id": row["user_id"],
                "organization_id": row["organization_id"],
                "group_id": row["group_id"],
                "conversation_id": row["conversation_id"],
                "case_id": row["case_id"],
                "request_surface": row["request_surface"],
                "scope_type": row["scope_type"],
                "attribution_source": row["attribution_source"],
            }
            for row in attribution_rows
        ],
    }


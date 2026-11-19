# solomon_core/solomon_tools/health_check.py
# ---------------------------------------------------------------------------
# Phase 47.3 — Pre-Phase Health Contract (ADVISORY ONLY)
# Phase 60  — ECB Awareness (ADVISORY, NON-AUTHORITATIVE)
# ---------------------------------------------------------------------------
# PURPOSE:
#   Provide a canonical, operator-only pre-phase health check that
#   summarizes system readiness as GREEN / YELLOW / RED.
#
# INVARIANTS:
#   • READ-ONLY
#   • ADVISORY ONLY (no enforcement, no blocking)
#   • OPERATOR-ONLY surface
#   • LLM-OPAQUE (must never flow into LLM prompts / skills / packets)
#   • No UI changes
#
# DESIGN:
#   • Sits on top of existing diagnostics (does not replace them)
#   • Produces a simple, deterministic status + reasons
# ---------------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Literal, Optional
from datetime import datetime

from solomon_core.logger import get_logger
from solomon_core.solomon_tools import diagnostics

logger = get_logger("health_check")

# ---------------------------------------------------------------------------
# Phase 47.3 Structural Markers
# ---------------------------------------------------------------------------
IS_DIAGNOSTIC_MODULE = True
OPERATOR_ONLY = True
LLM_OPAQUE = True
EXECUTION_AUTHORITY = False  # advisory-only, never execute or enforce

HealthStatus = Literal["GREEN", "YELLOW", "RED"]


@dataclass(frozen=True)
class PrePhaseHealthResult:
    """
    Advisory-only health contract result.
    """
    status: HealthStatus
    reasons: List[str]
    timestamp_utc: str
    details: Dict[str, Any]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "__diagnostic__": True,
            "is_diagnostic": True,
            "operator_only": True,
            "llm_opaque": True,
            "health_contract": {
                "status": self.status,
                "reasons": self.reasons,
                "timestamp_utc": self.timestamp_utc,
                "details": self.details,
            },
        }


# ---------------------------------------------------------------------------
# Canonical Rules (Advisory Only)
# ---------------------------------------------------------------------------
def _compute_status(
    core_ok: bool,
    db_ok: bool,
    mem_ok: bool,
    ecb_ok: bool,
) -> tuple[HealthStatus, List[str]]:
    """
    Deterministic, advisory-only mapping.

    GREEN:
        • core_ok AND db_ok AND mem_ok

    YELLOW:
        • core_ok AND db_ok AND mem_ok AND NOT ecb_ok

    RED:
        • NOT core_ok
        • OR NOT db_ok
    """
    reasons: List[str] = []

    if not core_ok:
        reasons.append("core_not_ok")

    if not db_ok:
        reasons.append("database_not_ok")

    if not mem_ok:
        reasons.append("memory_not_ok")

    if not ecb_ok:
        reasons.append("ecb_not_ok")

    if (not core_ok) or (not db_ok):
        return "RED", reasons

    if not mem_ok or not ecb_ok:
        return "YELLOW", reasons

    return "GREEN", reasons


# ---------------------------------------------------------------------------
# ECB Advisory Probe (PUBLIC API ONLY)
# ---------------------------------------------------------------------------
def _probe_ecb_state() -> Dict[str, Any]:
    """
    Advisory-only ECB probe.

    RULES:
    • Public API only
    • No mutation
    • No storage inspection
    • Presence = callable contract
    """
    try:
        from solomon_core.context.ecb_registry import get_context

        # Non-mutating, empty read
        _ = get_context("__healthcheck__")

        return {
            "present": True,
            "note": "public_ecb_api_callable",
        }

    except Exception as exc:
        return {
            "present": False,
            "error": str(exc),
        }


# ---------------------------------------------------------------------------
# Public API (Operator-Only)
# ---------------------------------------------------------------------------
def run_pre_phase_health_check(
    extra_checks: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Canonical Phase 47.3 pre-phase health check.
    Advisory only.
    """
    logger.info("[HealthCheck] Running pre-phase health contract (advisory only)")

    core_report = diagnostics.check_core()
    db_report = diagnostics.check_database()
    mem_report = diagnostics.check_memory()
    ecb_report = _probe_ecb_state()

    core_ok = bool(core_report.get("ok", False))
    db_ok = bool(db_report.get("ok", False))
    mem_ok = bool(mem_report.get("ok", False))
    ecb_ok = bool(ecb_report.get("present", False))

    status, reasons = _compute_status(
        core_ok=core_ok,
        db_ok=db_ok,
        mem_ok=mem_ok,
        ecb_ok=ecb_ok,
    )

    details: Dict[str, Any] = {
        "core_ok": core_ok,
        "database_ok": db_ok,
        "memory_ok": mem_ok,
        "ecb_ok": ecb_ok,
        "core": core_report,
        "database": db_report,
        "memory": mem_report,
        "ecb": ecb_report,
    }

    if isinstance(extra_checks, dict) and extra_checks:
        details["extra_checks"] = extra_checks

    result = PrePhaseHealthResult(
        status=status,
        reasons=reasons,
        timestamp_utc=datetime.utcnow().isoformat(),
        details=details,
    )

    return result.as_dict()


def format_pre_phase_health_summary(health_payload: Dict[str, Any]) -> str:
    """
    Optional operator convenience formatter.
    Presentation-only.
    """
    try:
        hc = (health_payload or {}).get("health_contract", {})
        status = hc.get("status", "UNKNOWN")
        reasons = hc.get("reasons", [])
        ts = hc.get("timestamp_utc", "")

        if not isinstance(reasons, list):
            reasons = []

        line_reasons = ", ".join(reasons) if reasons else "(none)"
        return (
            "SOLOMON PRE-PHASE HEALTH CONTRACT\n"
            f"Timestamp (UTC): {ts}\n"
            f"Status: {status}\n"
            f"Reasons: {line_reasons}\n"
        )
    except Exception as exc:
        return f"Health summary unavailable ({exc})"


__all__ = [
    "run_pre_phase_health_check",
    "format_pre_phase_health_summary",
]

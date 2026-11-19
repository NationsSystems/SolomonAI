# ---------------------------------------------------------------------------
# FILE: solomon_core/signals/signal_telemetry.py
# ---------------------------------------------------------------------------
# Signal Survivability Telemetry (Phase 85)
# Deterministic, auditable, no behavior changes
# ---------------------------------------------------------------------------

from typing import Dict


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def init_signal_telemetry() -> Dict[str, Dict]:
    """Initialize survivability tracking for core signal families."""
    return {
        "monetary_signals": _blank_family(),
        "exclusion_signals": _blank_family(),
    }


def _blank_family() -> Dict:
    return {
        "deterministic_count": 0,
        "recovery_attempted": False,
        "recovery_items_found": 0,
        "recovery_items_accepted": 0,
        "ledger_written": False,
        "bei_consumed": False,
        "snapshot_visible": False,
    }


# ---------------------------------------------------------------------------
# Health Evaluation
# ---------------------------------------------------------------------------

def signal_family_healthy(fam: Dict) -> bool:
    """End-to-end survivability check."""
    return (
        (fam.get("deterministic_count", 0)
         + fam.get("recovery_items_accepted", 0)) > 0
        and fam.get("ledger_written", False)
        and fam.get("bei_consumed", False)
        and fam.get("snapshot_visible", False)
    )


def build_signal_health_report(telemetry: Dict[str, Dict]) -> Dict:
    """Return health status per signal family."""
    return {
        name: {
            "healthy": signal_family_healthy(data),
            **data,
        }
        for name, data in telemetry.items()
    }
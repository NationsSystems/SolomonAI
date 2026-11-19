"""
solomon_core/ingress/shadow_sensor.py

Phase 48 — Shadow Sensor (CLOSED, Inert)

PURPOSE
-------
Provide a non-authoritative, read-only observation stub at the
Layer 1 (Orchestrator / Ingress) boundary.

This module:
- DOES NOT route
- DOES NOT execute
- DOES NOT influence planners, skills, or learning
- DOES NOT persist state
- DOES NOT modify UX
- FAILS SILENTLY and BYPASSES by default

The Shadow Sensor is CLOSED by default and must be fully removable
without any behavior change.
"""

from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# Configuration (LOCKED)
# ---------------------------------------------------------------------------

DEFAULT_ENABLED = False


# ---------------------------------------------------------------------------
# Shadow Sensor
# ---------------------------------------------------------------------------

class ShadowSensor:
    """
    Inert observation stub.

    When disabled (default), all calls are no-ops.
    When enabled (future-facing), observation remains read-only.
    """

    def __init__(self, enabled: bool = DEFAULT_ENABLED) -> None:
        self.enabled = bool(enabled)

    def observe(self, payload: Optional[Dict[str, Any]] = None) -> None:
        """
        Observe ingress classification metadata.

        This method:
        - Never raises
        - Never returns data
        - Never mutates input
        - Never influences routing or execution
        """
        if not self.enabled:
            return

        # Future-facing observation hook intentionally omitted.
        # Observation ≠ influence.
        return

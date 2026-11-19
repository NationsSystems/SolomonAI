# solomon_core/diagnostics/planner_diagnostics.py
# ------------------------------------------------------------------
# Phase 46 — Tier-3 Planner Diagnostics (SIGNAL-ONLY)
# Phase 47.4 — Planner & Drift Signal Cleanup
#
# PURPOSE (Tier-3):
#   Expose raw planner and cognition diagnostics for
#   observability and presentation layers.
#
# PHASE 47.4 CHANGES:
#   • Retire legacy pre-packet assumptions
#   • Re-scope drift probes as observational only
#   • Clarify structural vs functional signals
#   • Eliminate misleading “missing structure” implications
#
# GUARANTEES:
#   • READ-ONLY
#   • SIGNAL-ONLY (no scoring, no interpretation)
#   • No conclusions or recommendations
#   • No exceptions propagated upward
# ------------------------------------------------------------------

import json
import importlib.util

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from solomon_core.models import PlanLog, ExecutionLog

# Strict planner components
from solomon_core.planner.planner_backend import build_strict_plan
from solomon_core.planner.plan_validator import validate_strict_plan

logger = get_logger("diagnostics.planner")


# -----------------------------------------------------------
# Structural awareness helpers (READ-ONLY)
# -----------------------------------------------------------

def _module_exists(module_path: str) -> bool:
    """Check whether a module exists without importing it."""
    try:
        spec = importlib.util.find_spec(module_path)
        return spec is not None
    except Exception:
        return False


def _check_orchestrator_present():
    """
    Detect orchestrator / packet router presence (STRUCTURAL).

    NOTE (Phase 47.4):
        Presence confirms packet-router architecture.
        Absence would indicate a broken install, not a planner issue.
    """
    return _module_exists("solomon_core.solomon_core")


def _check_packet_header_defined():
    """
    Detect PacketHeader schema definition (STRUCTURAL).

    NOTE (Phase 47.4):
        PacketHeader is a first-class artifact.
        This signal reflects schema presence, not runtime emission.
    """
    return _module_exists("solomon_core.packets.packet_header")


# -----------------------------------------------------------
# Planner bootstrap validation (MECHANICAL)
# -----------------------------------------------------------

def _check_planner_boot():
    """
    Validate planner can build a plan object.

    NOTE:
        This does NOT imply execution authority.
    """
    try:
        _ = build_strict_plan("diagnostic_probe", {})
        return True
    except Exception as e:
        logger.error(f"[planner_bootstrap] failed: {e}")
        return False


# -----------------------------------------------------------
# Last executed plan status (RAW)
# -----------------------------------------------------------

def _last_plan_status():
    session = SessionLocal()
    try:
        row = session.query(PlanLog).order_by(PlanLog.created_at.desc()).first()

        if not row:
            return {
                "exists": False,
                "validated": False,
                "execution_ok": False,
            }

        plan_raw = row.plan_json

        if isinstance(plan_raw, dict):
            plan_obj = plan_raw
        elif isinstance(plan_raw, str):
            try:
                plan_obj = json.loads(plan_raw)
            except Exception as e:
                logger.error(f"[planner] JSON decode failed for plan: {e}")
                return {
                    "exists": True,
                    "validated": False,
                    "execution_ok": False,
                }
        else:
            return {
                "exists": True,
                "validated": False,
                "execution_ok": False,
            }

        validation = validate_strict_plan(plan_obj)
        validated = bool(validation.get("ok", False))

        last_exec = (
            session.query(ExecutionLog)
            .filter(ExecutionLog.plan_id == row.id)
            .order_by(ExecutionLog.started_at.desc())
            .first()
        )

        execution_ok = bool(last_exec and last_exec.status == "success")

        return {
            "exists": True,
            "validated": validated,
            "execution_ok": execution_ok,
        }

    except Exception as e:
        logger.error(f"[planner] last plan validation failed: {e}")
        return {
            "exists": True,
            "validated": False,
            "execution_ok": False,
        }
    finally:
        try:
            session.close()
        except Exception:
            pass


# -----------------------------------------------------------
# Planner cognition state (RAW)
# -----------------------------------------------------------

def _planner_cognition_state():
    """
    Observational cognition state.
    No authority, no control.
    """
    try:
        from solomon_core.operational_cognition_controller import get_current_mode
        mode = get_current_mode()
    except Exception:
        mode = None

    return {
        "active_mode": mode,
    }


# -----------------------------------------------------------
# Cognitive drift probe (OBSERVATIONAL)
# -----------------------------------------------------------

def _drift_probe_observational():
    """
    Observational drift probe.

    NOTE (Phase 47.4):
        This probe indicates availability of drift-related
        reasoning structures, NOT planner authority or control.
    """
    try:
        from solomon_core.reasoning.reasoning_graph import ReasoningGraph
        ReasoningGraph()
        return True
    except Exception:
        return False


# -----------------------------------------------------------
# Tier-3 diagnostics entrypoint (SIGNAL-ONLY)
# -----------------------------------------------------------

def run(arguments=None):
    """
    Tier-3 planner diagnostics.
    Emits raw, post-packet diagnostic signals only.
    """

    try:
        boot_ok = _check_planner_boot()
        last_plan = _last_plan_status()
        cognition = _planner_cognition_state()
        drift_available = _drift_probe_observational()

        signals = {
            # ---------------------------------
            # Planner mechanics (RAW)
            # ---------------------------------
            "planner_boot_ok": boot_ok,
            "last_plan_exists": last_plan["exists"],
            "last_plan_validated": last_plan["validated"],
            "last_plan_execution_ok": last_plan["execution_ok"],
            "cognition_active_mode": cognition["active_mode"],

            # ---------------------------------
            # Drift (OBSERVATIONAL)
            # ---------------------------------
            "drift_signals_available": drift_available,

            # ---------------------------------
            # Structural awareness (POST-PACKET)
            # ---------------------------------
            "orchestrator_present": _check_orchestrator_present(),
            "packet_header_defined": _check_packet_header_defined(),

            # ---------------------------------
            # Planner posture (EXPLICIT)
            # ---------------------------------
            "planner_is_authority": False,   # enforced by architecture
            "planner_emits_packets": False, # orchestrator-only responsibility
        }

        return {
            "ok": True,
            "signals": signals,
        }

    except Exception as e:
        logger.exception("Planner diagnostics failure")
        return {
            "ok": False,
            "signals": {},
            "error": str(e),
        }

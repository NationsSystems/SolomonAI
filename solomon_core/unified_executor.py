# unified_executor.py — Phase 39 Strict Micro-Skill Executor (NON-AUTHORITATIVE, FOM-39)
# ------------------------------------------------------------------------------------
# Phase 52 UPDATE (Execution-Order Correction):
#   • Grounded DocIntel skill output is treated as a first-class emission candidate
#   • No conversational fallback text is emitted from this layer
#   • Silent failure is preferred over human phrasing
#   • DEPC behavior is preserved exactly (no weakening, no bypass)
#   • No skill logic, prompts, or domain logic modified
#
# Phase 38 & Phase 39 guarantees remain fully intact.
# ------------------------------------------------------------------------------------

import copy
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError

from solomon_core.logger import get_logger
from solomon_core.skill_executor import execute_skill as _run_skill

from solomon_core.db import SessionLocal
from solomon_core.models import ExecutionLog

from solomon_core.error_sentinel import record_error
from solomon_core.epistemic_layer import EpistemicLayer

from solomon_core.domains import (
    BID, PROPOSAL, ESTIMATE, CONTRACT, INVOICE,
    SPECIFICATION, PROCUREMENT, GENERIC_DOCUMENT,
)

from config import settings

DOCINTEL_SET = {
    BID, PROPOSAL, ESTIMATE, CONTRACT, INVOICE,
    SPECIFICATION, PROCUREMENT, GENERIC_DOCUMENT,
    "compare_documents",
    "extract_structured_data",
}

logger = get_logger("unified_executor")


class ExecutionTimeout(Exception):
    """Phase 34 hard execution timeout."""
    pass


class UnifiedExecutor:
    EXECUTOR_VERSION = "28.5-docintel-grounded-first"

    def __init__(self):
        logger.info(
            "[Phase39][EXECUTOR_INIT] UnifiedExecutor initialized",
            extra={"version": self.EXECUTOR_VERSION},
        )
        self.epistemic = EpistemicLayer()
        logger.debug("[UnifiedExecutor] Epistemic layer attached (observation-only)")

    # =================================================================
    # INTERNAL EXECUTION BODY (worker thread)
    # =================================================================
    def _execute_skill_body(
        self,
        *,
        skill_name: str,
        intent: str,
        entities: dict,
        reasoning_source: str,
        execution_lane: str,
        plan_id: str,
        step_number: int,
        orchestrator_event_id: str | None = None,
        orchestrator_state: str | None = None,
    ):
        db = SessionLocal()
        start = datetime.utcnow()

        try:
            logger.info(
                "[Phase39][EXECUTE]",
                extra={
                    "skill": skill_name,
                    "intent": intent,
                    "orch_event": orchestrator_event_id,
                    "orch_state": orchestrator_state,
                },
            )

            exec_log = ExecutionLog(
                task_id=f"{start.timestamp()}-{skill_name}",
                intent=intent,
                skill_name=skill_name,
                plan_id=plan_id if isinstance(plan_id, int) else None,
                executor_version=self.EXECUTOR_VERSION,
                status="running",
                started_at=start,
                metadata_json={
                    "entities": entities,
                    "reasoning_source": reasoning_source,
                    "execution_lane": execution_lane,
                    "orchestrator_event_id": orchestrator_event_id,
                    "orchestrator_state": orchestrator_state,
                },
                reasoning_type="skill",
                reasoning_source=reasoning_source,
            )
            db.add(exec_log)
            db.commit()
            db.refresh(exec_log)

            # -------------------------------
            # Execute skill deterministically
            # -------------------------------
            args = copy.deepcopy(entities)
            args.pop("intent", None)

            if intent in DOCINTEL_SET and "docs" in entities:
                args["docs"] = entities["docs"]

            result_packet = _run_skill(skill_name, args)

            execution_ok = bool(result_packet.get("ok", False))
            schema = result_packet.get("schema", "")

            grounded = bool(
                execution_ok and (
                    schema.startswith("DocumentCompare.")
                    or result_packet.get("result") is not None
                )
            )

            # -------------------------------
            # Epistemic observation (read-only)
            # -------------------------------
            try:
                self.epistemic.evaluate(
                    task_type="skill_execution",
                    evidence={
                        "skill_name": skill_name,
                        "intent": intent,
                        "execution_ok": execution_ok,
                        "grounded": grounded,
                        "schema": schema,
                        "execution_lane": execution_lane,
                        "task_present": bool(entities.get("task_present")),
                    },
                    context={
                        "plan_id": plan_id,
                        "step_number": step_number,
                    },
                )
            except Exception as epi_err:
                logger.error(
                    "[Phase39][EPISTEMIC_OBSERVE_FAIL]",
                    extra={"error": str(epi_err)},
                )

            # -------------------------------
            # Persist execution record
            # -------------------------------
            exec_log.status = "success" if execution_ok else "error"
            exec_log.finished_at = datetime.utcnow()
            exec_log.result_snippet = str(result_packet.get("result"))[:8000]
            exec_log.error_message = None if execution_ok else None
            exec_log.metadata_json.update({
                "execution_ok": execution_ok,
                "grounded": grounded,
                "schema": schema,
            })
            db.commit()

            # ============================================================
            # 🔑 PHASE 52 FIX — PROMOTE GROUNDED DOCINTEL OUTPUT
            # ============================================================
            if execution_ok and grounded:
                result_packet = dict(result_packet)  # defensive copy
                result_packet["docintel_reasoning"] = result_packet.get("result")

            # -------------------------------
            # Phase 52 RULE:
            # Do NOT inject conversational fallback text.
            # Return result packet as-is; silence is handled upstream.
            # -------------------------------
            if execution_ok:
                return result_packet

            return {
                "ok": False,
                "error": result_packet.get("error") or "ExecutionFailed",
            }

        finally:
            db.close()

    # =================================================================
    # PUBLIC EXECUTION ENTRYPOINT (TIME-BOUNDED, NON-AUTHORITATIVE)
    # =================================================================
    def execute_skill(
        self,
        *,
        skill_name: str,
        intent: str,
        entities: dict,
        reasoning_source: str,
        execution_lane: str = "planner_gated",
        plan_id: str = None,
        step_number: int = None,
        orchestrator_event_id: str | None = None,
        orchestrator_state: str | None = None,
    ):
        # -------------------------------------------------------------
        # Phase 38 HARD CONTRACT — FACTUAL QUERIES FORBIDDEN
        # -------------------------------------------------------------
        if intent == "factual_query" or skill_name == "factual_query":
            logger.critical(
                "[Phase38][CONTRACT_VIOLATION][FACTUAL_EXEC]",
                extra={
                    "skill": skill_name,
                    "intent": intent,
                    "orch_event": orchestrator_event_id,
                    "orch_state": orchestrator_state,
                },
            )
            record_error(
                phase="unified-executor",
                error_type="FactualExecutorViolation",
                message="factual_query must never enter UnifiedExecutor",
                tb="",
            )
            return {"ok": False, "error": "FactualExecutorViolation"}

        # -------------------------------------------------------------
        # Phase 38 AUTHORITY GATE
        # -------------------------------------------------------------
        if orchestrator_state != "EXECUTING":
            logger.error(
                "[Phase38][AUTH_VIOLATION][EXECUTOR]",
                extra={
                    "skill": skill_name,
                    "intent": intent,
                    "orch_state": orchestrator_state,
                    "orch_event": orchestrator_event_id,
                },
            )
            return {"ok": False, "error": "ExecutionNotAuthorized"}

        start = datetime.utcnow()

        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(
                self._execute_skill_body,
                skill_name=skill_name,
                intent=intent,
                entities=entities,
                reasoning_source=reasoning_source,
                execution_lane=execution_lane,
                plan_id=plan_id,
                step_number=step_number,
                orchestrator_event_id=orchestrator_event_id,
                orchestrator_state=orchestrator_state,
            )

            try:
                return future.result(
                    timeout=settings.EXECUTION_TIMEOUT_SECONDS
                )

            except FutureTimeoutError:
                duration = (datetime.utcnow() - start).total_seconds()
                logger.error(
                    "[Phase39][TIMEOUT]",
                    extra={
                        "skill": skill_name,
                        "intent": intent,
                        "duration": duration,
                        "lane": execution_lane,
                        "orch_event": orchestrator_event_id,
                    },
                )
                record_error(
                    phase="unified-executor",
                    error_type="ExecutionTimeout",
                    message="Execution exceeded hard timeout",
                    tb="",
                )
                return {"ok": False, "error": "ExecutionTimeout"}

            except Exception as e:
                logger.error(
                    "[Phase39][EXEC_FATAL]",
                    extra={
                        "skill": skill_name,
                        "orch_event": orchestrator_event_id,
                        "error": str(e),
                    },
                )
                record_error(
                    phase="unified-executor",
                    error_type=type(e).__name__,
                    message=str(e),
                    tb="",
                )
                return {"ok": False, "error": str(e)}

    # =================================================================
    # EXTERNAL ENTRYPOINT (LEGACY CALLERS SUPPORTED)
    # =================================================================
    def execute(self, **kwargs):
        if "task_text" in kwargs:
            entities = kwargs.get("entities", {}) or {}

            logger.warning(
                "[Phase39][LEGACY_EXECUTOR_CALL]",
                extra={"entities_keys": list(entities.keys())},
            )

            intent = entities.get("intent") or "generic_task"
            skill_name = intent

            return self.execute_skill(
                skill_name=skill_name,
                intent=intent,
                entities=entities,
                reasoning_source="executor",
                execution_lane=kwargs.get("execution_lane", "planner_gated"),
                orchestrator_event_id=kwargs.get("orchestrator_event_id"),
                orchestrator_state=kwargs.get("orchestrator_state", "EXECUTING"),
            )

        return self.execute_skill(
            skill_name=kwargs["skill_name"],
            intent=kwargs["intent"],
            entities=kwargs["entities"],
            reasoning_source="executor",
            execution_lane=kwargs.get("execution_lane", "planner_gated"),
            orchestrator_event_id=kwargs.get("orchestrator_event_id"),
            orchestrator_state=kwargs.get("orchestrator_state"),
        )


# EXPORT SINGLETON
executor = UnifiedExecutor()

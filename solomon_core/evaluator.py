# evaluator.py — Solomon Evaluation Bridge (Phase 6.10)
# --------------------------------------------------------------------
# Purpose:
#   Provides a top-level evaluator interface that connects Solomon's
#   core modules (solomon_core.py, reinforcement_store, etc.) with
#   the internal solomon_tools.evaluator system.
#
#   This avoids deep imports and keeps compatibility with any modules
#   that expect `from solomon_core.evaluator import evaluate_task`.

from solomon_core.solomon_tools import evaluator as tool_evaluator
from solomon_core.logger import get_logger

logger = get_logger("evaluator_bridge")


def evaluate_task(task_id: str,
                  intent: str,
                  reasoning_source: str,
                  success: bool,
                  confidence: float = None,
                  summary: str = None):
    """
    Bridge wrapper to record task evaluations through solomon_tools.evaluator.

    Args:
        task_id (str): Unique ID of the executed task
        intent (str): Detected intent label
        reasoning_source (str): Which reasoning mode handled the task
        success (bool): Whether the task succeeded
        confidence (float, optional): Model confidence score
        summary (str, optional): Summary or context of task outcome
    """
    try:
        if hasattr(tool_evaluator, "record_evaluation"):
            tool_evaluator.record_evaluation(
                task_id=task_id,
                intent=intent,
                reasoning_source=reasoning_source,
                success=success,
                confidence=confidence,
                summary=summary,
            )
            logger.debug(
                f"[EvaluatorBridge] Recorded evaluation for {task_id} | "
                f"{intent} | {reasoning_source} | success={success}"
            )
        elif hasattr(tool_evaluator, "evaluate_task"):
            # Backward compatibility: if solomon_tools.evaluator already defines evaluate_task()
            tool_evaluator.evaluate_task(
                task_id=task_id,
                intent=intent,
                reasoning_source=reasoning_source,
                success=success,
                confidence=confidence,
                summary=summary,
            )
            logger.debug(f"[EvaluatorBridge] Delegated to internal evaluate_task() successfully.")
        else:
            logger.warning("[EvaluatorBridge] No compatible evaluation function found in solomon_tools.evaluator")
    except Exception as e:
        logger.error(f"[EvaluatorBridge] Failed to record evaluation: {e}")

# solomon_core/solomon_core.py
# ------------------------------------------------------------------
# Solomon Orchestrator Public Entry
#
# Thin compatibility layer.
# Keeps legacy import surface stable.
# ------------------------------------------------------------------

from solomon_core.logger import get_logger
from solomon_core.orchestrator_runtime import run_task

logger = get_logger("solomon_core")
logger.info("[ORCHESTRATOR][IMPORT] solomon_core.py loaded")


def execute_task(task_text: str, **kwargs):
    request_id = kwargs.pop("request_id", None)
    return run_task(user_text=task_text, request_id=request_id, **kwargs)

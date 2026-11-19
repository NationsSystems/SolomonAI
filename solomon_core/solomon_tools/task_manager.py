# task_manager.py — Phase 38 Signal-Only Task Wrapper (NON-AUTHORITATIVE)
# ---------------------------------------------------------------------
# Phase 38 FIX:
#   • NO independent execution authority
#   • NO callable execution unless orchestrator explicitly authorizes
#   • Preserves interface + logging for compatibility
# ---------------------------------------------------------------------

import os
import tempfile
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, TimeoutError

from solomon_core.logger import get_logger
from solomon_core.solomon_tools.errors import SolomonError, InternalError
from config import settings


logger = get_logger("task_manager")

_executor = ThreadPoolExecutor(max_workers=4)

# ---------------------------------------------------------------------
# Phase-38 Authority Declaration
# ---------------------------------------------------------------------
EXECUTION_AUTHORITY = False  # This module may NEVER execute independently


def run_task(task_fn, *args, **kwargs):
    """
    Phase-38 GUARANTEE:
        • This function does NOT execute tasks unless explicitly authorized
        • It is a signal-compatible wrapper only
        • Orchestrator must set execution_authorized=True
    """
    execution_authorized = kwargs.pop("execution_authorized", False)

    if not execution_authorized:
        logger.error(
            "[Phase38Violation] task_manager.run_task() invoked without authorization"
        )
        return False, None, InternalError(
            "Execution blocked: orchestrator authorization required"
        )

    task_id = kwargs.get("task_id", f"task_{int(time.time() * 1000)}")
    temp_dir = tempfile.mkdtemp(prefix=f"{task_id}_", dir=settings.RUNTIME_DIR)
    logger.info(f"[task_manager] Authorized task {task_id} started in {temp_dir}")

    def _wrapped():
        try:
            return task_fn(*args, **kwargs)
        except SolomonError as se:
            raise se
        except Exception as e:
            raise InternalError(str(e))

    start = time.time()
    future = _executor.submit(_wrapped)

    try:
        result = future.result(timeout=settings.TASK_TIMEOUT_S)
        duration = (time.time() - start) * 1000
        logger.info(
            f"[task_manager] Authorized task {task_id} completed in {duration:.0f} ms"
        )
        return True, result, None

    except TimeoutError:
        logger.error(
            f"[task_manager] Authorized task {task_id} timed out "
            f"after {settings.TASK_TIMEOUT_S}s"
        )
        return False, None, InternalError("Task timed out")

    except SolomonError as e:
        logger.error(f"[task_manager] Authorized task {task_id} failed: {e.message}")
        return False, None, e

    except Exception:
        logger.error(
            f"[task_manager] Authorized task {task_id} unexpected error:\n"
            f"{traceback.format_exc()}"
        )
        return False, None, InternalError("Unexpected error")

    finally:
        try:
            os.rmdir(temp_dir)
        except OSError:
            pass


__all__ = [
    "run_task",
    "EXECUTION_AUTHORITY",
]

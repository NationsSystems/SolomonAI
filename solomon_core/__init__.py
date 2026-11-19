# -------------------------------------------------------------------
# FILE: __init__.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Public package interface for Solomon Core.
#
# GUARANTEES:
#   - No bootstrap
#   - No runtime execution
#   - No competing execution authority
# -------------------------------------------------------------------

from solomon_core.intent_parser import parse_task_with_embeddings
from solomon_core.solomon_core import execute_task

__ENTRYPOINT__ = "solomon_core.solomon_core.execute_task"

__all__ = [
    "execute_task",
    "parse_task_with_embeddings",
    "__ENTRYPOINT__",
]
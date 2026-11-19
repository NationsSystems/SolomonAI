# solomon_core/skills/__init__.py
# ---------------------------------------------------------------
# Phase 22 — Skills Package Initializer (Corrected)
#
# Purpose:
#   • Mark skills/ as a Python package
#   • Expose built-in micro-skills (diagnostics suite, etc.)
#   • Provide a clean namespace for dynamically loaded skills
#
# Notes:
#   • Do NOT perform heavy imports here (prevents circular issues)
#   • Do NOT execute logic at import time
#   • Only expose registrable skill entrypoints
# ---------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("skills")

# ---------------------------------------------------------------
# Built-in micro-skill entrypoints (Phase 22)
# ---------------------------------------------------------------
try:
    # Aggregator entrypoint is execute()
    from .run_diagnostics import execute as skill_run_diagnostics
except Exception as e:
    logger.warning(f"[skills] Could not load diagnostics aggregator: {e}")
    skill_run_diagnostics = None

__all__ = [
    "skill_run_diagnostics",
]

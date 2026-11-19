# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/reconciliation_logging.py
#
# PURPOSE:
# Emit structural lifecycle events.
#
# AUTHORITY:
# Observational only.
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("reconciliation")


def log_relationship_created(rid: str, rtype: str):
    logger.info(f"[T2] relationship_created id={rid} type={rtype}")


def log_conflict_detected(cid: str):
    logger.info(f"[T2] conflict_detected id={cid}")

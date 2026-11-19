# -------------------------------------------------------------------
# FILE: solomon_intelligence_worker.py
# DIRECTORY: ./
# -------------------------------------------------------------------
# Canonical local durable Intelligence Spool worker composition for Solomon.
#
# AUTHORITY CONTRACT
#   - Owns local database/file-bound background job orchestration only.
#   - Does not expose an SIS HTTP listener and does not load the LLM locally
#     while Portable SIS remote compute mode is active.
#   - Sends bounded LLM/embedding computation to the one configured SIS
#     execution endpoint, then validates/persists results locally.
#   - The normal Solomon application may own this worker in-process; this file
#     remains directly executable only as an explicit operational fallback.
# -------------------------------------------------------------------

from __future__ import annotations

from threading import Event
from typing import Optional

from config import settings
from solomon_core.intelligence_service.document_embedding_contract import (
    DOCUMENT_EMBEDDING_JOB_TYPE,
)
from solomon_core.intelligence_service.document_embedding_processor import (
    process_generate_document_embeddings,
)
from solomon_core.intelligence_service.document_summary_contract import (
    AUTO_SUMMARY_JOB_TYPE,
)
from solomon_core.intelligence_service.document_summary_processor import (
    process_generate_document_summary,
)
from solomon_core.intelligence_service.intelligence_service_client import (
    get_intelligence_service_endpoint,
    get_intelligence_service_health,
)
from solomon_core.intelligence_service.intelligence_spool_worker import (
    IntelligenceSpoolWorker,
)
from solomon_core.logger import get_logger


logger = get_logger("intelligence_worker")
_STOP = Event()
_EXTENSION_WORKER = "solomon_intelligence_spool_worker"
_EXTENSION_ERROR = "solomon_intelligence_spool_worker_error"
_EXTENSION_STARTING = "solomon_intelligence_spool_worker_starting"


def _sis_ready() -> bool:
    health = get_intelligence_service_health()
    return bool(health.get("interactive_ready"))


def _embedding_ready() -> bool:
    if not bool(settings.SIS_EMBEDDING_ENABLED):
        return False

    health = get_intelligence_service_health()
    embedding = health.get("embedding")
    if not isinstance(embedding, dict):
        return False

    return bool(embedding.get("enabled")) and bool(embedding.get("ready"))


def build_intelligence_spool_worker() -> IntelligenceSpoolWorker:
    """Build the one configured local durable worker composition."""

    worker = IntelligenceSpoolWorker()

    if bool(settings.SIS_AUTO_SUMMARY_ENABLED):
        worker.register_processor(
            AUTO_SUMMARY_JOB_TYPE,
            process_generate_document_summary,
            available=_sis_ready,
        )
        logger.info(
            "[INTELLIGENCE_WORKER][SUMMARY_REGISTERED] job_type=%s",
            AUTO_SUMMARY_JOB_TYPE,
        )

    if bool(settings.SIS_EMBEDDING_ENABLED):
        worker.register_processor(
            DOCUMENT_EMBEDDING_JOB_TYPE,
            process_generate_document_embeddings,
            available=_embedding_ready,
        )
        logger.info(
            "[INTELLIGENCE_WORKER][EMBEDDING_REGISTERED] job_type=%s",
            DOCUMENT_EMBEDDING_JOB_TYPE,
        )

    return worker


def _set_app_worker_state(
    app,
    *,
    worker: Optional[IntelligenceSpoolWorker],
    error: str = "",
    starting: bool = False,
) -> None:
    if app is None:
        return

    app.extensions[_EXTENSION_WORKER] = worker
    app.extensions[_EXTENSION_ERROR] = str(error or "")
    app.extensions[_EXTENSION_STARTING] = bool(starting)


def start_intelligence_spool_worker(app=None) -> Optional[IntelligenceSpoolWorker]:
    """Start the canonical durable worker without creating another app/process."""

    if not bool(settings.SIS_SPOOL_WORKER_ENABLED):
        _set_app_worker_state(
            app,
            worker=None,
            error="",
            starting=False,
        )
        logger.warning("[INTELLIGENCE_WORKER][DISABLED]")
        return None

    existing = None
    if app is not None:
        existing = app.extensions.get(_EXTENSION_WORKER)
    if isinstance(existing, IntelligenceSpoolWorker):
        snapshot = existing.get_snapshot()
        if bool(snapshot.get("running")):
            return existing

    _set_app_worker_state(
        app,
        worker=None,
        error="",
        starting=True,
    )

    endpoint = get_intelligence_service_endpoint()
    logger.info(
        "[INTELLIGENCE_WORKER][STARTING] sis_endpoint=%s compute_mode=%s",
        endpoint or "-",
        str(settings.SIS_COMPUTE_MODE or "local"),
    )

    try:
        worker = build_intelligence_spool_worker()
        _set_app_worker_state(
            app,
            worker=worker,
            error="",
            starting=True,
        )
        worker.start()
        _set_app_worker_state(
            app,
            worker=worker,
            error="",
            starting=False,
        )
        logger.info(
            "[INTELLIGENCE_WORKER][READY] sis_endpoint=%s worker_id=%s",
            endpoint or "-",
            worker.worker_id,
        )
        return worker
    except Exception as exc:
        logger.exception("[INTELLIGENCE_WORKER][START_FAILED]")
        _set_app_worker_state(
            app,
            worker=None,
            error=str(exc),
            starting=False,
        )
        return None


def stop_intelligence_spool_worker(
    *,
    app=None,
    worker: Optional[IntelligenceSpoolWorker] = None,
) -> None:
    """Stop the canonical durable worker owned by the current application."""

    active_worker = worker
    if active_worker is None and app is not None:
        candidate = app.extensions.get(_EXTENSION_WORKER)
        if isinstance(candidate, IntelligenceSpoolWorker):
            active_worker = candidate

    if active_worker is None:
        _set_app_worker_state(
            app,
            worker=None,
            error=(
                app.extensions.get(_EXTENSION_ERROR, "")
                if app is not None
                else ""
            ),
            starting=False,
        )
        return

    try:
        active_worker.stop(wait=True)
        logger.info(
            "[INTELLIGENCE_WORKER][STOPPED] worker_id=%s",
            active_worker.worker_id,
        )
    except Exception as exc:
        logger.exception("[INTELLIGENCE_WORKER][STOP_FAILED]")
        _set_app_worker_state(
            app,
            worker=None,
            error=str(exc),
            starting=False,
        )
        return

    _set_app_worker_state(
        app,
        worker=None,
        error="",
        starting=False,
    )


def main() -> None:
    """Explicit fallback runner; normal Solomon owns this worker in-process."""

    worker = start_intelligence_spool_worker()
    if worker is None:
        return

    try:
        while not _STOP.wait(1.0):
            pass
    except KeyboardInterrupt:
        logger.info("[INTELLIGENCE_WORKER][STOP_REQUESTED]")
    finally:
        stop_intelligence_spool_worker(worker=worker)


if __name__ == "__main__":
    main()

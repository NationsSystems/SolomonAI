# -------------------------------------------------------------------
# FILE: solomon_intelligence_service.py
# DIRECTORY: ./
# -------------------------------------------------------------------
# Standalone local SIS entry point retained for explicit rollback only.
# In Portable SIS remote mode this entry point refuses to start so Solomon
# cannot accidentally run a second local SIS execution service.
# -------------------------------------------------------------------

from __future__ import annotations

from threading import Thread

from config import settings
from solomon_core.logger import get_logger
from solomon_intelligence_worker import (
    start_intelligence_spool_worker,
    stop_intelligence_spool_worker,
)


logger = get_logger("intelligence_service")


def _schedule_spool_worker_start(app) -> None:
    """Schedule canonical durable spool initialization after listener startup."""

    app.extensions["solomon_intelligence_spool_worker"] = None
    app.extensions["solomon_intelligence_spool_worker_error"] = ""
    app.extensions["solomon_intelligence_spool_worker_starting"] = bool(
        settings.SIS_SPOOL_WORKER_ENABLED
    )

    Thread(
        target=start_intelligence_spool_worker,
        args=(app,),
        name="sis-spool-bootstrap",
        daemon=True,
    ).start()


def main() -> None:
    if not bool(settings.SIS_ENABLED):
        logger.warning("[SIS][DISABLED] SIS_ENABLED is false; service not started.")
        return

    compute_mode = str(settings.SIS_COMPUTE_MODE or "local").strip().lower()
    if compute_mode == "remote":
        logger.warning(
            "[SIS][LOCAL_START_BLOCKED] Portable SIS remote mode is active; "
            "no localhost SIS execution service will be started. The normal "
            "Solomon application owns local durable intelligence work."
        )
        return

    from waitress import create_server
    from solomon_core.intelligence_service.intelligence_service_api import (
        create_intelligence_service_app,
        start_intelligence_service_runtime_warmup,
    )

    logger.info(
        "[SIS][STARTING] host=%s port=%s",
        settings.SIS_BIND_HOST,
        settings.SIS_BIND_PORT,
    )

    app = create_intelligence_service_app()
    server = create_server(
        app,
        host=str(settings.SIS_BIND_HOST),
        port=int(settings.SIS_BIND_PORT),
        threads=max(1, int(settings.SIS_WAITRESS_THREADS)),
        connection_limit=max(1, int(settings.SIS_WAITRESS_CONNECTION_LIMIT)),
        backlog=max(1, int(settings.SIS_WAITRESS_BACKLOG)),
        channel_timeout=max(1, int(settings.SIS_WAITRESS_CHANNEL_TIMEOUT_SECONDS)),
        ident="Solomon Intelligence Service",
    )

    # Waitress has acquired the local rollback listener before model warmup or
    # spool initialization begins. Both are scheduled asynchronously so neither
    # can delay the SIS HTTP accept loop.
    logger.info(
        "[SIS][LISTENING] host=%s port=%s status=warming",
        settings.SIS_BIND_HOST,
        settings.SIS_BIND_PORT,
    )
    start_intelligence_service_runtime_warmup()
    _schedule_spool_worker_start(app)

    try:
        server.run()
    finally:
        stop_intelligence_spool_worker(app=app)


if __name__ == "__main__":
    main()

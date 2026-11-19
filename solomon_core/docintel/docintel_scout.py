# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/docintel_scout.py
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger

logger = get_logger("docintel_scout")


def _run_semantic_scout_if_available(execution_context, reasoning_payload):
    try:
        if execution_context.get("scout_candidates") is not None:
            return

        inputs = reasoning_payload.get("inputs") or {}
        documents = inputs.get("documents") or []

        text_parts = []
        for d in documents:
            txt = d.get("text")
            if isinstance(txt, str) and txt.strip():
                text_parts.append(txt)

        text_blob = "\n\n".join(text_parts).strip()

        if not text_blob:
            return

        from solomon_core.orchestrator_runtime import _run_semantic_scout

        execution_context["docintel_text"] = text_blob

        resolved_paths = execution_context.get("resolved_paths") or []
        _run_semantic_scout(resolved_paths, execution_context)

        logger.info("[SCOUT] invoked post-ingestion")

    except Exception as e:
        logger.warning(f"[SCOUT] late invocation failed: {e}")
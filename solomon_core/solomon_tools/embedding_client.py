# ---------------------------------------------------------------------------
# FILE: embedding_client.py
# DIRECTORY: solomon_core/solomon_tools/
# ---------------------------------------------------------------------------
# Shared SIS Embedding Client
#
# PURPOSE:
#   Preserve Solomon's existing embedding helper interface while routing all
#   production embedding work through the canonical Qwen runtime owned by the
#   separately running Solomon Intelligence Service (SIS).
#
# CONTRACT:
#   - Does not load Torch/Transformers model weights in the Flask process.
#   - Does not launch subprocesses or supervise SIS lifecycle.
#   - Does not select actions, route workflows, or grant authority.
#   - Returns deterministic zero-vector fallbacks only when SIS embedding
#     execution fails, preserving the existing helper failure behavior.
# ---------------------------------------------------------------------------

from __future__ import annotations

import time
from typing import Iterable, List

from config import settings
from solomon_core.intelligence_service.intelligence_service_client import (
    execute_embeddings_via_intelligence_service,
)
from solomon_core.logger import get_logger

logger = get_logger("embedding_client")


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

EMBED_MODEL = str(
    settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME
).strip() or "qwen3_embedding_0_6b"

EMBED_DIM = max(1, int(settings.EMBED_DIM))


# ---------------------------------------------------------------------------
# Fallback Helpers
# ---------------------------------------------------------------------------

def _zero_vector() -> List[float]:
    return [0.0] * EMBED_DIM


def _valid_vector(value) -> bool:
    if not isinstance(value, list) or len(value) != EMBED_DIM:
        return False

    return all(
        isinstance(item, (int, float))
        for item in value
    )


# ---------------------------------------------------------------------------
# SIS Embedding Calls
# ---------------------------------------------------------------------------

def embed_text(
    text: str,
    model: str | None = None,
    *,
    priority: str = "P0",
    request_id: str | None = None,
    fairness_bucket: str | None = None,
) -> List[float]:
    """
    Return one normalized embedding from the SIS-owned local model.

    The optional model argument is retained for backward compatibility. The
    canonical Solomon embedding model remains configuration-owned and callers
    cannot override the SIS runtime through this compatibility surface.
    """

    del model

    clean_text = str(text or "").strip()
    if not clean_text:
        return _zero_vector()

    started_at = time.perf_counter()
    logger.info(
        "[SIS][LOCAL_EMBEDDING_CALL_START] call_site=embedding_client_single "
        "priority=%s request_id=%s chars=%s",
        str(priority or "P0").strip().upper(),
        str(request_id or "unbound"),
        len(clean_text),
    )

    try:
        vectors = execute_embeddings_via_intelligence_service(
            [clean_text],
            call_site="embedding_client_single",
            priority=priority,
            request_id=request_id,
            fairness_bucket=fairness_bucket,
        )
        vector = vectors[0] if vectors else []

        if not _valid_vector(vector):
            logger.error(
                "[EMBEDDING][INVALID_VECTOR] model=%s",
                EMBED_MODEL,
            )
            return _zero_vector()

        logger.info(
            "[SIS][LOCAL_EMBEDDING_CALL_COMPLETE] call_site=embedding_client_single "
            "priority=%s request_id=%s total_ms=%.3f valid=%s",
            str(priority or "P0").strip().upper(),
            str(request_id or "unbound"),
            (time.perf_counter() - started_at) * 1000.0,
            True,
        )
        return [float(value) for value in vector]
    except Exception as exc:
        logger.exception(
            "[EMBEDDING][SIS_FAILURE] model=%s error=%s",
            EMBED_MODEL,
            exc,
        )
        return _zero_vector()


def embed_texts(
    texts: Iterable[str],
    model: str | None = None,
    *,
    priority: str = "P0",
    request_id: str | None = None,
    fairness_bucket: str | None = None,
) -> List[List[float]]:
    """
    Return normalized SIS embeddings for a batch of texts.

    Empty values preserve positional alignment by receiving the deterministic
    zero-vector fallback.
    """

    del model

    text_list = [str(text or "").strip() for text in texts]
    if not text_list:
        return []

    nonempty_indexes = [
        index
        for index, text in enumerate(text_list)
        if text
    ]
    output = [_zero_vector() for _ in text_list]

    if not nonempty_indexes:
        return output

    nonempty_texts = [text_list[index] for index in nonempty_indexes]

    try:
        vectors = execute_embeddings_via_intelligence_service(
            nonempty_texts,
            call_site="embedding_client_batch",
            priority=priority,
            request_id=request_id,
            fairness_bucket=fairness_bucket,
        )

        if len(vectors) != len(nonempty_texts):
            raise ValueError(
                "SIS embedding batch returned an unexpected number of vectors."
            )

        for index, vector in zip(nonempty_indexes, vectors):
            if not _valid_vector(vector):
                logger.error(
                    "[EMBEDDING][INVALID_BATCH_VECTOR] model=%s index=%s",
                    EMBED_MODEL,
                    index,
                )
                continue

            output[index] = [float(value) for value in vector]

        return output
    except Exception as exc:
        logger.exception(
            "[EMBEDDING][SIS_BATCH_FAILURE] model=%s error=%s",
            EMBED_MODEL,
            exc,
        )
        return output


# ---------------------------------------------------------------------------
# Manual Verification
# ---------------------------------------------------------------------------

def quick_test() -> None:
    sample = "This is a test embedding for Solomon."
    vector = embed_text(sample)

    print(f"Model: {EMBED_MODEL}")
    print(f"Length: {len(vector)}")
    print(f"Prefix: {vector[:8]}")


if __name__ == "__main__":
    quick_test()

# skill_faiss_sync.py — Phase 22 FAISS Wrapper (FINAL SAFE v3.1)
# -----------------------------------------------------------

import numpy as np
from solomon_core.logger import get_logger
from solomon_core.solomon_tools import faiss_store

logger = get_logger("skill_faiss_sync")

FAISS_EXPECTED_DIM = 768


def _normalize_embedding_to_float32(embedding):
    """
    Accepts:
      • bytes  -> DB stored embedding
      • list   -> embed_text output
      • np.ndarray
    Returns:
      • np.ndarray float32 (768-dim)
    """

    if embedding is None:
        return None

    # Case 1 — DB bytes
    if isinstance(embedding, (bytes, bytearray)):
        vec = np.frombuffer(embedding, dtype=np.float32)

    # Case 2 — Python list
    elif isinstance(embedding, list):
        vec = np.array(embedding, dtype=np.float32)

    # Case 3 — Already NumPy
    elif isinstance(embedding, np.ndarray):
        vec = embedding.astype(np.float32)

    else:
        logger.error(f"[FAISS] Unsupported embedding type: {type(embedding)}")
        return None

    # Enforce dimension consistency
    if vec.shape[0] != FAISS_EXPECTED_DIM:
        logger.error(
            f"[FAISS] Invalid embedding dimension: {vec.shape[0]} (expected {FAISS_EXPECTED_DIM})"
        )
        return None

    return vec


def ensure_faiss_index_for_skill(name: str, description: str = "", embedding_override=None):
    """
    Safely insert a skill embedding into FAISS.

    Accepts:
      • DB LargeBinary embeddings
      • Python list embeddings
      • NumPy vector embeddings

    Always enforces:
      • float32
      • 768-dim
    """

    try:
        if embedding_override is None:
            logger.debug(f"[FAISS] No embedding for skill '{name}', skipping.")
            return

        vector = _normalize_embedding_to_float32(embedding_override)

        if vector is None:
            logger.error(f"[FAISS] Normalization failed for skill '{name}', skipping.")
            return

        # Correct Phase-22 FAISS API
        result = faiss_store.add_vector(name, vector)

        # ----- FIX: Downgrade "already indexed" to DEBUG instead of ERROR -----
        if not isinstance(result, dict) or not result.get("ok", False):

            error_msg = ""
            if isinstance(result, dict):
                error_msg = str(result.get("error", "")).lower()

            if "already indexed" in error_msg:
                logger.debug(f"[FAISS] Skill '{name}' already indexed — skipping reinsert.")
            else:
                logger.error(f"[FAISS] Could not index skill '{name}': {result}")

        else:
            logger.debug(f"[FAISS] Indexed skill '{name}'")

    except Exception as e:
        logger.error(f"[FAISS] Failed to sync index for '{name}': {e}")


def sync_faiss_with_db():
    """Persist FAISS index + metadata to disk."""
    try:
        faiss_store.save_index()
        logger.info("[FAISS] Persisted FAISS index + metadata.")
        return {"ok": True}
    except Exception as e:
        logger.error(f"[FAISS] Sync failed: {e}")
        return {"ok": False, "error": str(e)}

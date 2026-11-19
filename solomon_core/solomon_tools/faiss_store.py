# faiss_store.py — Phase 22 Strict FAISS Store (768-Dim Fixed)
# --------------------------------------------------------------------
# Absolute Rules (Phase 22):
#   • FAISS vector dim is permanently 768
#   • No runtime embedding — vectors come ONLY from DB or rebuild script
#   • Safe initialization, strict dimension checks
#   • No planner helpers, no fallback embedding
#   • Fully deterministic + thread-safe
# --------------------------------------------------------------------

import os
import json
import faiss
import numpy as np
from threading import RLock

from config import settings

# -----------------------------------------------------------
# Paths
# -----------------------------------------------------------

FAISS_DIR = os.path.join(settings.DATA_DIR, "faiss")
os.makedirs(FAISS_DIR, exist_ok=True)

INDEX_PATH = os.path.join(FAISS_DIR, "index.faiss")
META_PATH = os.path.join(FAISS_DIR, "meta.json")

# -----------------------------------------------------------
# Globals (PERMANENTLY 768-DIM)
# -----------------------------------------------------------

DIMENSION = 768
lock = RLock()

_index = None
_meta = {}          # skill_name → metadata
_next_id = 0        # FAISS row counter


# -----------------------------------------------------------
# Metadata I/O
# -----------------------------------------------------------

def _save_meta():
    """Persist metadata safely."""
    try:
        with open(META_PATH, "w", encoding="utf-8") as f:
            json.dump({"next_id": _next_id, "meta": _meta}, f, indent=2)
    except Exception:
        pass


def _load_meta():
    """Load metadata from disk or bootstrap new."""
    global _next_id, _meta

    if not os.path.exists(META_PATH):
        _meta = {}
        _next_id = 0
        return

    try:
        with open(META_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            _next_id = int(data.get("next_id", 0))
            _meta = data.get("meta", {})
            if not isinstance(_meta, dict):
                _meta = {}
    except Exception:
        _meta = {}
        _next_id = 0


# -----------------------------------------------------------
# FAISS index initialization
# -----------------------------------------------------------

def load_index():
    """
    Load FAISS index from disk.
    If incompatible, rebuild a fresh 768-dim index.
    """
    global _index

    with lock:
        _load_meta()

        # Try loading an existing index
        if os.path.exists(INDEX_PATH):
            try:
                idx = faiss.read_index(INDEX_PATH)

                # STRICT: verify dimensionality
                if idx.d != DIMENSION:
                    raise ValueError(
                        f"Incompatible FAISS index dimension {idx.d}; expected {DIMENSION}"
                    )

                _index = idx
                return True

            except Exception:
                # Fall through to rebuild
                pass

        # BUILD NEW 768-DIM INDEX
        _index = faiss.IndexFlatL2(DIMENSION)
        try:
            faiss.write_index(_index, INDEX_PATH)
        except Exception:
            pass

        # Reset metadata
        _save_meta()
        return True


def save_index():
    """Persist the FAISS index + metadata."""
    with lock:
        try:
            faiss.write_index(_index, INDEX_PATH)
        except Exception:
            pass

        _save_meta()


# -----------------------------------------------------------
# Phase 22 — STRICT VECTOR INGESTION
# -----------------------------------------------------------

def add_vector(name: str, vec: np.ndarray):
    """
    Add a precomputed 768-dim vector (from DB) to FAISS.

    STRICT:
        • vec MUST be float32
        • vec MUST be 768-dim
        • Runtime embedding forbidden
    """
    global _next_id

    if isinstance(vec, list):
        vec = np.array(vec, dtype="float32")

    if vec.ndim == 1:
        vec = vec.reshape(1, -1)

    if vec.shape[1] != DIMENSION:
        raise ValueError(
            f"FAISS vector must be {DIMENSION}-dim; got {vec.shape[1]}"
        )

    with lock:
        key = name.lower()

        if key in _meta:
            return {"ok": False, "error": f"Skill '{name}' already indexed."}

        _index.add(vec)

        _meta[key] = {
            "id": _next_id,
            "description": "",
            "created": "direct",
            "embedding_source": "db",
        }

        _next_id += 1
        save_index()

        return {"ok": True, "id": _next_id - 1}


# -----------------------------------------------------------
# Phase 22 — STRICT SEARCH
# -----------------------------------------------------------

def search(vector: np.ndarray, top_k=5):
    """
    STRICT SEARCH:
        • Must receive a real 768-dim vector
        • Zero fallback embedding attempts allowed
    """
    if vector is None:
        return []

    if isinstance(vector, list):
        vector = np.array(vector, dtype="float32")

    if vector.ndim == 1:
        vector = vector.reshape(1, -1)

    if vector.shape[1] != DIMENSION:
        # Invalid vector shape: return empty (strict)
        return []

    with lock:
        distances, indices = _index.search(vector, top_k)

        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:
                continue

            for name, meta in _meta.items():
                if meta["id"] == idx:
                    results.append({
                        "name": name,
                        "distance": float(dist),
                        "metadata": meta,
                    })
                    break

        return results


# -----------------------------------------------------------
# Diagnostics
# -----------------------------------------------------------

def get_vector_by_name(name: str):
    """Return stored vector for admin inspection."""
    key = name.lower()
    if key not in _meta:
        return None

    row = _meta[key]["id"]

    with lock:
        try:
            return _index.reconstruct(row)
        except Exception:
            return None


# -----------------------------------------------------------
# Hard reset (admin / manual)
# -----------------------------------------------------------

def reset_faiss_index():
    """Erase FAISS index + metadata."""
    global _index, _meta, _next_id

    with lock:
        _index = faiss.IndexFlatL2(DIMENSION)
        _meta = {}
        _next_id = 0

        try:
            if os.path.exists(INDEX_PATH):
                os.remove(INDEX_PATH)
            if os.path.exists(META_PATH):
                os.remove(META_PATH)
        except Exception:
            pass

        try:
            faiss.write_index(_index, INDEX_PATH)
        except Exception:
            pass

        _save_meta()

        print("[FAISS] ✔ Reset FAISS index and metadata.")
        return {"ok": True}


# -----------------------------------------------------------
# Load index immediately
# -----------------------------------------------------------

load_index()


# -----------------------------------------------------------
# Exports
# -----------------------------------------------------------

__all__ = [
    "add_vector",
    "search",
    "get_vector_by_name",
    "reset_faiss_index",
    "_meta",
]

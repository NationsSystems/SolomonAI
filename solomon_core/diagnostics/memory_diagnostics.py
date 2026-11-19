# solomon_core/diagnostics/memory_diagnostics.py
# ------------------------------------------------------------------
# Phase 40G — Tier-3 Memory Diagnostics (SIGNAL-ONLY)
# Phase 47.4 — Planner & Drift Signal Cleanup (Memory Alignment)
#
# PURPOSE (Tier-3):
#   Expose raw, mechanical memory and FAISS diagnostics
#   for observability and presentation layers.
#
# PHASE 47.4 CHANGES:
#   • Clarify signals as observational only
#   • Align terminology with post-packet execution reality
#   • Ensure no signal implies enforcement or authority
#
# GUARANTEES:
#   • READ-ONLY
#   • SIGNAL-ONLY (no scoring, no interpretation)
#   • No exceptions propagated upward
#   • No conclusions, no recommendations
# ------------------------------------------------------------------

import numpy as np
from solomon_core.logger import get_logger

# Memory store (module)
from solomon_core import memory_store

# FAISS utilities
from solomon_core.solomon_tools.fileops import ensure_faiss_index

logger = get_logger("diagnostics.memory")


# -----------------------------------------------------------
# FAISS recall sanity test (MECHANICAL / OBSERVATIONAL)
# -----------------------------------------------------------
def _embedding_recall_test(index):
    """
    Observational recall probe.

    NOTE (Phase 47.4):
        Indicates index usability only.
        Does NOT measure quality, accuracy, or fitness.
    """
    try:
        if index is None or index.ntotal == 0:
            return False

        dim = index.d
        test_vec = np.zeros((1, dim)).astype("float32")
        index.search(test_vec, 1)

        return True

    except Exception:
        return False


# -----------------------------------------------------------
# Tier-3 diagnostics entrypoint (SIGNAL-ONLY)
# -----------------------------------------------------------
def run(arguments=None):
    """
    Tier-3 memory diagnostics.
    Emits raw, post-packet diagnostic signals only.
    """

    try:
        # Load FAISS index (read-only)
        index = ensure_faiss_index()

        faiss_size = int(index.ntotal) if index else 0
        faiss_dim = int(index.d) if index else 0

        # Pull memory entries from DB (read-only)
        try:
            memory_items = memory_store.get_recent_memory(limit=500)
            memory_count = len(memory_items)
        except Exception:
            memory_items = []
            memory_count = 0

        recall_available = _embedding_recall_test(index)

        # ---------------------------------------------------
        # Raw observational signals
        # ---------------------------------------------------
        signals = {
            "faiss_index_present": bool(index),
            "faiss_index_size": faiss_size,
            "faiss_index_dimensionality": faiss_dim,
            "memory_entry_count": memory_count,
            "memory_recall_available": recall_available,

            # Reserved future signals (explicitly neutral)
            # These keys intentionally signal *absence*, not failure
            "orphaned_embeddings": None,      # Phase 23+
            "stale_memory_entries": None,     # Phase 24+
            "embedding_drift_score": None,    # Phase 26+
            "similarity_heatmap_report": None,
        }

        return {
            "ok": True,
            "signals": signals,
        }

    except Exception as e:
        logger.exception("Memory diagnostics failure")
        return {
            "ok": False,
            "signals": {},
            "error": str(e),
        }

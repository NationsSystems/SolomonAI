# solomon_core/solomon_tools/prototype_store.py — Phase 38
# ---------------------------------------------------------------------------
# PURPOSE:
#   • Load intent prototypes from disk
#   • Embed them ONCE
#   • Expose vectors as READ-ONLY data
#
# GUARANTEES:
#   • NO routing
#   • NO thresholds
#   • NO decisions
#   • NO execution
#   • NO semantic authority
#   • Safe to import anywhere
# ---------------------------------------------------------------------------

import json
import os
import copy
from typing import List, Dict

from solomon_core.logger import get_logger
from solomon_core.solomon_tools.embedding_client import embed_text

logger = get_logger("prototype_store")

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------
_PROTOTYPE_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
    "data",
    "intent_prototypes.json",
)

_loaded: bool = False
_prototypes: List[Dict] = []


# ---------------------------------------------------------------------------
# Internal loader (fail-safe, single-pass)
# ---------------------------------------------------------------------------
def _load_prototypes() -> None:
    global _loaded, _prototypes

    if _loaded:
        return

    # Prototype support is OPTIONAL.
    # Absence of the file is a normal condition and not an error.
    if not os.path.exists(_PROTOTYPE_FILE):
        logger.debug(
            "Intent prototype file not present (optional) | path=%s",
            _PROTOTYPE_FILE,
        )
        _loaded = True
        _prototypes = []
        return

    try:
        with open(_PROTOTYPE_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        if not isinstance(raw, list):
            raise ValueError("intent_prototypes.json must contain a list")

        enriched: List[Dict] = []

        for item in raw:
            if not isinstance(item, dict):
                continue

            proto_id = item.get("id")
            text = item.get("text")

            if not proto_id or not text:
                continue

            try:
                vector = embed_text(text)
            except Exception:
                vector = None

            enriched.append({
                "id": proto_id,
                "text": text,
                "vector": vector,
                "meta": item.get("meta", {}),
            })

        _prototypes = enriched
        _loaded = True

        logger.info(
            "Loaded intent prototypes | count=%s",
            len(_prototypes),
        )

    except Exception as e:
        logger.error(
            "Failed to load intent prototypes",
            extra={"error": str(e)},
        )
        _prototypes = []
        _loaded = True


# ---------------------------------------------------------------------------
# Public accessor (READ-ONLY, DEFENSIVE)
# ---------------------------------------------------------------------------
def get_intent_prototypes() -> List[Dict]:
    """
    Returns a READ-ONLY snapshot of intent prototypes.

    Shape:
        {
            "id": str,
            "text": str,
            "vector": embedding | None,
            "meta": dict
        }

    NOTE:
        Callers MUST treat returned data as immutable.
        Defensive copies are returned to enforce this.
    """
    _load_prototypes()
    return copy.deepcopy(_prototypes)


__all__ = ["get_intent_prototypes"]

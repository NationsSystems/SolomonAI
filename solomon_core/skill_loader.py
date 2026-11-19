# skill_loader.py — Phase 21 Minimal Persistent Skill Loader
# -----------------------------------------------------------
# Phase 21 removes dynamic skill loading entirely.
#
# Responsibilities:
#   • Fetch persistent skills from the DB
#   • Trigger FAISS sync calls (via skill_faiss_sync)
#   • Ensure clean boot without touching any dynamic code
#
# No code execution.
# No register_skill_local().
# No dynamic modules.
# No skill_system dependencies.
# -----------------------------------------------------------

import traceback

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from solomon_core.models import SkillRegistry
from solomon_core.skill_faiss_sync import (
    ensure_faiss_index_for_skill,
    sync_faiss_with_db,
)

logger = get_logger("skill_loader")


# --------------------------------------------------------
# Load a single persistent skill (FAISS metadata only)
# --------------------------------------------------------
def load_single_persistent_skill(rec: SkillRegistry):
    """
    Phase 21:
        Load only the minimal metadata needed for FAISS.
        • name        -> skill_name
        • description -> description
        • embedding   -> embedding (precomputed, may be None)
    """
    name = rec.skill_name
    desc = rec.description or ""
    embedding = rec.embedding  # May be None

    try:
        ensure_faiss_index_for_skill(
            name=name,
            description=desc,
            embedding_override=embedding,
        )
    except Exception as e:
        logger.error(f"[loader] Failed to sync FAISS for '{name}': {e}")


# --------------------------------------------------------
# Load all persistent skills
# --------------------------------------------------------
def load_persistent_skills():
    """
    Phase 21 loader:
        • Fetch all DB skills (active only)
        • Trigger FAISS sync for each (metadata-only)
        • Persist FAISS index to disk
    """

    session = SessionLocal()

    try:
        records = (
            session.query(SkillRegistry)
            .filter_by(is_active=True)
            .all()
        )
    except Exception as e:
        logger.error(f"[loader] Could not read persistent skills from DB: {e}")
        return {"ok": False, "error": str(e)}

    for rec in records:
        try:
            load_single_persistent_skill(rec)
        except Exception:
            traceback.print_exc()

    try:
        sync_faiss_with_db()
    except Exception as e:
        logger.warning(f"[loader] Final FAISS sync failed: {e}")
        return {"ok": False, "error": str(e)}

    logger.info(f"[loader] Loaded {len(records)} persistent skills into FAISS.")
    return {"ok": True, "count": len(records)}


__all__ = [
    "load_persistent_skills",
    "load_single_persistent_skill",
]

# solomon_core/diagnostics/skill_diagnostics.py
# ------------------------------------------------------------------
# Phase 40G — Tier-3 Skill Diagnostics (SIGNAL-ONLY)
# Phase 47.4 — Planner & Drift Signal Cleanup (Skill Alignment)
#
# PURPOSE (Tier-3):
#   Expose raw skill- and registry-related diagnostics for
#   observability and presentation layers.
#
# PHASE 47.4 CHANGES:
#   • Clarify all skill metrics as observational only
#   • Ensure no signal implies enforcement, ranking, or authority
#   • Align terminology with post-packet execution model
#
# GUARANTEES:
#   • READ-ONLY
#   • SIGNAL-ONLY (no scoring, no interpretation)
#   • No conclusions or recommendations
#   • No exceptions propagated upward
# ------------------------------------------------------------------

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from solomon_core.models import SkillRegistry
from solomon_core.skill_registry import MICRO_SKILL_MAP

logger = get_logger("diagnostics.skills")


# -----------------------------------------------------------
# Compute recent skill execution success availability (RAW)
# -----------------------------------------------------------
def _execution_success_availability(limit: int = 50):
    """
    Observational execution signal.

    NOTE (Phase 47.4):
        This value indicates recent execution outcomes only.
        It does NOT imply skill quality, fitness, or gating.
    """
    try:
        session = SessionLocal()
        rows = session.execute(
            "SELECT status FROM execution_log ORDER BY id DESC LIMIT :limit",
            {"limit": limit},
        ).fetchall()
        session.close()

        if not rows:
            return None

        successes = sum(1 for r in rows if r[0] == "success")
        return round(successes / len(rows), 3)

    except Exception:
        return None


# -----------------------------------------------------------
# Tier-3 diagnostics entrypoint (SIGNAL-ONLY)
# -----------------------------------------------------------
def run(arguments=None):
    """
    Tier-3 skill diagnostics.
    Emits raw, post-packet diagnostic signals only.
    """

    try:
        session = SessionLocal()

        # DB-backed skills (RAW inventory)
        skills = session.query(SkillRegistry).all()
        skill_names = [s.skill_name for s in skills if s.skill_name]

        # Micro-skills from registry map (RAW inventory)
        micro_skill_names = list(MICRO_SKILL_MAP.keys())

        # Invalid DB skill entries (RAW)
        invalid_skills = [s.skill_name for s in skills if not s.skill_name]

        # Orphaned micro-skills (map present, DB absent)
        orphaned_micro_skills = []
        for mk in micro_skill_names:
            if not session.query(SkillRegistry).filter_by(skill_name=mk).first():
                orphaned_micro_skills.append(mk)

        # Embedding presence (RAW)
        skills_missing_embeddings = [
            s.skill_name for s in skills if not s.embedding
        ]

        execution_availability = _execution_success_availability()

        session.close()

        signals = {
            # ---------------------------------
            # Registry inventory (RAW)
            # ---------------------------------
            "skill_count": len(skill_names),
            "micro_skill_count": len(micro_skill_names),

            # ---------------------------------
            # Structural integrity (RAW)
            # ---------------------------------
            "invalid_skill_entries": invalid_skills,
            "orphaned_micro_skills": orphaned_micro_skills,
            "skills_missing_embeddings": skills_missing_embeddings,

            # ---------------------------------
            # Execution signals (OBSERVATIONAL)
            # ---------------------------------
            "execution_success_availability": execution_availability,
        }

        return {
            "ok": True,
            "signals": signals,
        }

    except Exception as e:
        logger.exception("Skill diagnostics failure")
        return {
            "ok": False,
            "signals": {},
            "error": str(e),
        }

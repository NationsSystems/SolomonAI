# skill_lifecycle_manager.py — Phase 12.9 (Phase 18 Stability + Option H1)
# ---------------------------------------------------------------------------
# Solomon Skill Lifecycle Manager
#
# Phase 18 Option H1 rules:
#   • Lifecycle stays lightweight and safe.
#   • References ONLY stable public APIs from other modules.
#   • No HFLO logic, no KG dependency, no reinforcement math here.
#   • Promotion decisions rely ONLY on:
#         - stability score
#         - candidate metadata
#         - cooldown
#         - simulation validity
#   • Zero cross-module writes.
#   • Non-blocking: lifecycle never causes cognition to fail.
# ---------------------------------------------------------------------------

import datetime
from collections import defaultdict

from solomon_core.logger import get_logger
from solomon_core.skill_registry import lookup_skill
from solomon_core.knowledge.skill_patching_engine import simulate_patch_execution
from solomon_core.autonomy.strict_autonomy_controller import should_autonomy_run
from solomon_core.knowledge.skill_weakness_engine import score_skill_stability

logger = get_logger("skill_lifecycle_manager")


# =============================================================
# Version Tracking Store (pure in-memory)
# =============================================================

SKILL_VERSIONS = defaultdict(lambda: {
    "active": None,
    "versions": {},               # version_name → metadata
    "last_promoted_at": None,     # cooldown enforcement
    "last_score_before_promote": None,
})


def _canon(name):
    return str(name).strip().lower()


# =============================================================
# Version Utilities
# =============================================================

def get_latest_version(skill_name):
    skill_name = _canon(skill_name)
    return SKILL_VERSIONS[skill_name].get("active")


def generate_new_version_name(skill_name):
    skill_name = _canon(skill_name)
    entry = SKILL_VERSIONS[skill_name]
    index = len(entry["versions"]) + 1
    return f"{skill_name}_v{index}"


# =============================================================
# Promotion
# =============================================================

def promote_skill_version(skill_name, version_name, code_callable):
    skill_name = _canon(skill_name)
    version_name = _canon(version_name)

    SKILL_VERSIONS[skill_name]["active"] = version_name
    SKILL_VERSIONS[skill_name]["versions"][version_name] = {
        "callable": code_callable,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "status": "active",
    }

    # Stability snapshot at promotion time
    SKILL_VERSIONS[skill_name]["last_promoted_at"] = datetime.datetime.utcnow()
    SKILL_VERSIONS[skill_name]["last_score_before_promote"] = (
        score_skill_stability(skill_name)
    )

    logger.info(f"[Lifecycle] Promoted {skill_name} → {version_name}")
    return True


# =============================================================
# Archival
# =============================================================

def archive_skill_version(skill_name, version_name):
    skill_name = _canon(skill_name)
    version_name = _canon(version_name)

    entry = SKILL_VERSIONS[skill_name]["versions"].get(version_name)
    if not entry:
        return False

    entry["status"] = "archived"
    entry["archived_at"] = datetime.datetime.utcnow().isoformat()

    logger.info(f"[Lifecycle] Archived {skill_name}:{version_name}")
    return True


# =============================================================
# Rollback
# =============================================================

def rollback_skill(skill_name):
    skill_name = _canon(skill_name)
    versions = SKILL_VERSIONS[skill_name]["versions"]

    if len(versions) <= 1:
        return {"success": False, "reason": "Only one version exists; cannot rollback."}

    active = SKILL_VERSIONS[skill_name]["active"]

    candidates = [
        (v, meta) for v, meta in versions.items()
        if v != active and meta.get("status") != "archived"
    ]

    if not candidates:
        return {"success": False, "reason": "No rollback candidate found."}

    candidates.sort(key=lambda x: x[1]["timestamp"], reverse=True)
    rollback_to, _ = candidates[0]

    SKILL_VERSIONS[skill_name]["active"] = rollback_to

    logger.warning(f"[Lifecycle] Rolled back {skill_name} to version {rollback_to}")

    return {"success": True, "rolled_back_to": rollback_to}


# =============================================================
# Patch Staging
# =============================================================

def apply_patch_record(prepared_patch: dict):
    skill_name = _canon(prepared_patch["skill"])
    version_name = _canon(prepared_patch["new_version"])
    patch_code = prepared_patch["patch_code"]

    SKILL_VERSIONS[skill_name]["versions"][version_name] = {
        "callable": patch_code,
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "status": "candidate",
        "stability_score_at_create": score_skill_stability(skill_name),
    }

    logger.info(f"[Lifecycle] Stored candidate patch version {version_name}")
    return True


# =============================================================
# Set Active Version
# =============================================================

def set_active_skill_version(skill_name, version_name):
    skill_name = _canon(skill_name)
    version_name = _canon(version_name)

    entry = SKILL_VERSIONS[skill_name]["versions"].get(version_name)
    if not entry:
        return {"success": False, "reason": "version not found"}

    SKILL_VERSIONS[skill_name]["active"] = version_name
    entry["status"] = "active"

    # record stability snapshot
    SKILL_VERSIONS[skill_name]["last_promoted_at"] = datetime.datetime.utcnow()
    SKILL_VERSIONS[skill_name]["last_score_before_promote"] = score_skill_stability(skill_name)

    logger.info(f"[Lifecycle] Skill {skill_name} now active version {version_name}")

    return {"success": True}


# =============================================================
# Phase 18 — Option H1: Minimalist Autonomous Promotion Cycle
# =============================================================

PROMOTION_COOLDOWN_MINUTES = 20

def autonomous_promotion_cycle(skill_name: str):
    """
    Option H1 — lifecycle remains safe, simple, conservative:
        • No HFLO logic here
        • No KG logic here
        • No reinforcement logic here
        • Only: stability score, candidate metadata, simulation validity
    """

    skill_name = _canon(skill_name)

    # Basic autonomy gating
    gate = should_autonomy_run()
    if not gate.get("allowed", False):
        return {"success": False, "reason": f"Autonomy gating: {gate.get('reason')}"}

    entry = SKILL_VERSIONS[skill_name]
    active = entry["active"]

    # Cooldown enforcement
    last_promo = entry.get("last_promoted_at")
    if last_promo:
        minutes = (datetime.datetime.utcnow() - last_promo).total_seconds() / 60
        if minutes < PROMOTION_COOLDOWN_MINUTES:
            return {
                "success": False,
                "reason": f"Cooldown in effect ({minutes:.1f}m)"
            }

    # Candidate discovery
    candidates = [
        v for v, meta in entry["versions"].items()
        if meta.get("status") == "candidate"
    ]
    if not candidates:
        return {"success": False, "reason": "No candidate versions"}

    # Latest candidate
    candidate = sorted(
        candidates,
        key=lambda v: entry["versions"][v]["timestamp"],
        reverse=True
    )[0]

    version_meta = entry["versions"][candidate]

    # Compare stability vs baseline
    stab = score_skill_stability(skill_name)
    baseline = version_meta.get("stability_score_at_create", {}).get("score", 0)

    if stab["score"] <= baseline:
        return {
            "success": False,
            "reason": "Stability did not improve",
            "current": stab["score"],
            "baseline": baseline,
        }

    # Simulation test
    sim = simulate_patch_execution(skill_name, version_meta["callable"])
    if not sim.get("valid", False):
        # archive invalid candidate
        archive_skill_version(skill_name, candidate)
        return {
            "success": False,
            "reason": "Candidate failed simulation",
            "archived": candidate
        }

    # All gates passed → promote
    set_active_skill_version(skill_name, candidate)

    logger.info(f"[Lifecycle] Option H1 promotion of {candidate}")

    return {
        "success": True,
        "promoted": candidate,
        "previous": active,
    }


# =============================================================
# Public API
# =============================================================

def get_lifecycle_info(skill_name):
    return SKILL_VERSIONS[_canon(skill_name)]


def list_all_skills():
    return list(SKILL_VERSIONS.keys())

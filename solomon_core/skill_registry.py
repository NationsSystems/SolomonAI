# solomon_core/skill_registry.py — Phase 38 LOCKED (Non-Authoritative Registry)
# ---------------------------------------------------------------------
# ROLE:
#   • Canonical micro-skill lookup and registration
#   • Domain classification ONLY
#   • Import + resolution ONLY
#
# GUARANTEES:
#   • NO routing authority
#   • NO orchestration authority
#   • NO continuation / flow decisions
#   • NO clarification authority
#   • NO execution logic
#
# Phase 38 invariant:
#   • Orchestrator is the sole traffic cop
#   • This registry is a passive lookup table
# ---------------------------------------------------------------------

from datetime import datetime
from importlib import import_module

from solomon_core.logger import get_logger
from solomon_core.db import SessionLocal
from solomon_core.models import SkillRegistry
from solomon_core.solomon_tools.embedding_client import embed_text
from solomon_core.skill_faiss_sync import sync_faiss_with_db as _faiss_sync

from solomon_core.domains import (
    DOMAIN_CORE,
    DOMAIN_DIAGNOSTICS,
    DOMAIN_GENERIC,
    DOMAIN_DOCINTEL,
)

logger = get_logger("skill_registry")

# =============================================================================
# SKILL → DOMAIN MAP (CLASSIFICATION ONLY)
# =============================================================================
SKILL_DOMAIN_MAP = {

    # Diagnostics
    "skill_run_diagnostics": DOMAIN_DIAGNOSTICS,
    "skill_run_system_diagnostics": DOMAIN_DIAGNOSTICS,
    "skill_run_skill_diagnostics": DOMAIN_DIAGNOSTICS,
    "skill_run_planner_diagnostics": DOMAIN_DIAGNOSTICS,
    "skill_run_memory_diagnostics": DOMAIN_DIAGNOSTICS,
    "skill_run_safety_diagnostics": DOMAIN_DIAGNOSTICS,

    # DocIntel
    "skill_extract_text": DOMAIN_DOCINTEL,
    "skill_summarize_document": DOMAIN_DOCINTEL,
    "skill_summarize_many": DOMAIN_DOCINTEL,
    "skill_compare_documents": DOMAIN_DOCINTEL,
    "skill_highlight_differences": DOMAIN_DOCINTEL,
    "skill_analyze_bid": DOMAIN_DOCINTEL,

    "skill_export_xlsx": DOMAIN_DOCINTEL,
    "skill_import_xlsx": DOMAIN_DOCINTEL,

    "skill_reconcile_bid_against_contract": DOMAIN_DOCINTEL,
    "skill_scope_obligation_mismatch": DOMAIN_DOCINTEL,

    "skill_docintel_extract_scope": DOMAIN_DOCINTEL,
    "skill_docintel_normalize_scope": DOMAIN_DOCINTEL,
    "skill_docintel_semantic_match": DOMAIN_DOCINTEL,
    "skill_docintel_compare_documents": DOMAIN_DOCINTEL,
    "skill_docintel_generate_comparison_table": DOMAIN_DOCINTEL,
    "skill_docintel_analyze_documents": DOMAIN_DOCINTEL,
    "skill_docintel_extract_text_blocks": DOMAIN_DOCINTEL,
    "skill_docintel_extract_structured_data": DOMAIN_DOCINTEL,

    "skill_multi_document_compare": DOMAIN_DOCINTEL,
    "skill_semantic_document_compare": DOMAIN_DOCINTEL,

    # 🔧 Phase 31 — alias domain
    "semantic_document_compare": DOMAIN_DOCINTEL,

    "skill_generic_llm_reasoning": DOMAIN_GENERIC,
}


def get_skill_domain(skill_name: str) -> str:
    return SKILL_DOMAIN_MAP.get(skill_name, DOMAIN_CORE)


# =============================================================================
# MICRO-SKILL MAP (RESOLUTION ONLY)
# =============================================================================
MICRO_SKILL_MAP = {

    "skill_run_diagnostics": "solomon_core.skills.run_diagnostics.run",
    "run diagnostics": "solomon_core.skills.run_diagnostics.run",

    "skill_run_system_diagnostics": "solomon_core.diagnostics.system_diagnostics.run",
    "skill_run_skill_diagnostics": "solomon_core.diagnostics.skill_diagnostics.run",
    "skill_run_planner_diagnostics": "solomon_core.diagnostics.planner_diagnostics.run",
    "skill_run_memory_diagnostics": "solomon_core.diagnostics.memory_diagnostics.run",
    "skill_run_safety_diagnostics": "solomon_core.diagnostics.safety_diagnostics.run",

    "skill_extract_text": "solomon_core.skills.semantic.extract_text.execute",
    "skill_summarize_document": "solomon_core.skills.semantic.summarize_document.execute",
    "skill_summarize_many": "solomon_core.skills.semantic.summarize_many.execute",
    "skill_compare_documents": "solomon_core.skills.semantic.compare_documents.execute",
    "skill_highlight_differences": "solomon_core.skills.semantic.highlight_differences.execute",
    "skill_analyze_bid": "solomon_core.skills.semantic.analyze_bid.execute",

    "skill_export_xlsx": "solomon_core.skills.semantic.docintel_export_xlsx.execute",
    "skill_import_xlsx": "solomon_core.skills.semantic.docintel_import_xlsx.execute",

    "skill_reconcile_bid_against_contract":
        "solomon_core.skills.semantic.docintel_reconcile_bid_contract.execute",

    "skill_scope_obligation_mismatch":
        "solomon_core.skills.semantic.docintel_scope_obligation_mismatch.execute",

    "skill_multi_document_compare":
        "solomon_core.skills.semantic.multi_document_compare.execute",

    "skill_semantic_document_compare":
        "solomon_core.skills.semantic.semantic_document_compare.execute",

    # 🔧 Phase 31 — REQUIRED ALIAS
    "semantic_document_compare":
        "solomon_core.skills.semantic.semantic_document_compare.execute",

    "skill_generic_llm_reasoning":
        "solomon_core.skills.generic_llm_reasoning.execute",
}


# =============================================================================
# RESOLUTION (NO AUTHORITY)
# =============================================================================
def resolve_micro_skill(name: str):
    if not isinstance(name, str):
        return None

    key = name.strip().lower()
    dotted = MICRO_SKILL_MAP.get(key) or MICRO_SKILL_MAP.get(f"skill_{key}")

    if not dotted:
        return None

    module_name, func_name = dotted.rsplit(".", 1)

    try:
        module = import_module(module_name)
        fn = getattr(module, func_name, None)
    except Exception as e:
        logger.error(f"[skill_registry] Import error for {module_name}: {e}")
        return None

    if fn is None:
        logger.error(f"[skill_registry] Function {func_name} missing in {module_name}")
        return None

    return lambda args=None: fn(args or {})


# =============================================================================
# PUBLIC ACCESSORS (READ-ONLY)
# =============================================================================
def lookup_skill(name: str):
    session = SessionLocal()
    try:
        return session.query(SkillRegistry).filter_by(skill_name=name).first()
    finally:
        session.close()


def get_skill(name: str, active_only=True):
    return lookup_skill(name)


def get_skill_info(name: str):
    return lookup_skill(name)


def get_all_skill_metadata():
    session = SessionLocal()
    try:
        return session.query(SkillRegistry).all()
    finally:
        session.close()


# =============================================================================
# FAISS SYNC (MAINTENANCE ONLY)
# =============================================================================
def sync_faiss_with_db():
    return _faiss_sync()


# =============================================================================
# REGISTRATION (BOOTSTRAP ONLY)
# =============================================================================
def register_builtin_micro_skills():
    session = SessionLocal()
    canonical = sorted(k for k in MICRO_SKILL_MAP if k.startswith("skill_"))

    for skill in canonical:
        if session.query(SkillRegistry).filter_by(skill_name=skill).first():
            continue

        record = SkillRegistry(
            skill_name=skill,
            description=f"[domain={get_skill_domain(skill)}] Built-in micro-skill",
            python_code=None,
            embedding=embed_text(skill),
            model_name="builtin",
            version=1,
            auto_generated=False,
            needs_review=False,
            usage_count=0,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        session.add(record)

    session.commit()
    session.close()
    _faiss_sync()

    logger.info("[skill_registry] ✅ Micro-skills registered and FAISS synced")

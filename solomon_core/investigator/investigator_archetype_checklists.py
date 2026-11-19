# solomon_core/investigator/investigator_archetype_checklists.py
# ------------------------------------------------------------------
# Investigator Archetype Checklist Registry (Design-Binding)
#
# Location:
#   solomon_core/investigator/investigator_archetype_checklists.py
#
# Purpose:
#   Defines the authoritative, explicit investigative checklist
#   indicators for each supported archetype in Phase 69.
#
# Governing Rules:
#   - Archetypes are declared upstream by the Orchestrator
#   - The Investigator trusts the declared archetype_id
#   - Each archetype owns a fixed, explicit checklist
#   - Indicators are boolean (0 | 1) only
#   - Checklist changes require a new archetype version
#
# Notes:
#   - No dynamic composition
#   - No inheritance or implicit reuse
#   - Indicator reuse is explicit and intentional
#   - This file is DATA, not logic
# ------------------------------------------------------------------

from typing import Dict, List


# ------------------------------------------------------------------
# Archetype Checklist Registry
# ------------------------------------------------------------------
# Key:
#   archetype_id (stable, versioned)
#
# Value:
#   ordered list of indicator_id strings
# ------------------------------------------------------------------

ARCHETYPE_CHECKLISTS: Dict[str, List[str]] = {

    # --------------------------------------------------------------
    # Ambient Public Queries (e.g., weather, time, public facts)
    # --------------------------------------------------------------
    "AMBIENT_PUBLIC_v1": [
        "subject_identified",
        "public_domain_subject",
        "temporal_scope_specified",
        "location_specified",
        "external_data_required",
    ],

    # --------------------------------------------------------------
    # Single Document Analysis (summarize, analyze, extract)
    # --------------------------------------------------------------
    "SINGLE_DOCUMENT_ANALYSIS_v1": [
        "document_present",
        "document_readable",
        "analysis_goal_specified",
        "scope_defined",
        "output_format_specified",
    ],

    # --------------------------------------------------------------
    # Multi-Document Relational Operations (compare, diff, reconcile)
    # --------------------------------------------------------------
    "MULTI_DOCUMENT_RELATIONAL_v1": [
        "multiple_documents_present",
        "documents_distinguishable",
        "relational_operation_specified",
        "left_document_identified",
        "right_document_identified",
    ],

    # --------------------------------------------------------------
    # Extraction / Transformation (structured outputs)
    # --------------------------------------------------------------
    "EXTRACTION_TRANSFORMATION_v1": [
        "source_material_present",
        "extraction_target_specified",
        "output_structure_defined",
        "transformation_rules_defined",
        "loss_constraints_defined",
    ],

    # --------------------------------------------------------------
    # Generic Conversational (no tools, no documents)
    # --------------------------------------------------------------
    "GENERIC_CONVERSATIONAL_v1": [
        "question_or_prompt_present",
        "referents_resolved",
        "context_sufficient",
        "no_external_dependencies",
        "response_scope_clear",
    ],
}


def get_checklist_for_archetype(archetype_id: str) -> List[str]:
    """
    Return the explicit checklist for a given archetype_id.

    Contract (Binding):
    - archetype_id must be declared upstream by the Orchestrator
    - absence of an archetype_id is a hard error
    - this function performs no fallback, inference, or defaults
    """
    if archetype_id not in ARCHETYPE_CHECKLISTS:
        raise KeyError(
            f"Unknown archetype_id '{archetype_id}'. "
            "All archetypes must be explicitly registered."
        )

    return ARCHETYPE_CHECKLISTS[archetype_id]

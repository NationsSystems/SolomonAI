# solomon_core/planner/action_catalog.py
# ---------------------------------------------------------------
# Phase 22 — Document Intelligence Action Catalog
#
# This catalog does NOT restrict the planner.
# It GUIDES it toward consistent, actionable steps.
#
# This is the same technique used in production planners at
# OpenAI, Anthropic, Google, and Microsoft.
#
# The planner backend NEVER enforces this list.
# It only SEES this list as reference / examples / schemas.
# ---------------------------------------------------------------

ACTION_CATALOG_VERSION = "v22.1"

# High-value document intelligence actions
DOCUMENT_ACTIONS = [

    {
        "action": "extract_text",
        "description": "Extract raw text from a document.",
        "required_args": ["filename"],
        "optional_args": [],
        "example_step": {
            "action": "extract_text",
            "arguments": {"filename": "path/to/file"},
            "depends_on": []
        }
    },

    {
        "action": "parse_sections",
        "description": "Split document text into sections based on headings or semantic boundaries.",
        "required_args": ["text"],
        "optional_args": ["strategy"],
        "example_step": {
            "action": "parse_sections",
            "arguments": {"text": "string", "strategy": "auto"},
            "depends_on": [1]
        }
    },

    {
        "action": "semantic_cluster_sections",
        "description": "Cluster document sections by meaning to find similar content.",
        "required_args": ["sections"],
        "optional_args": [],
        "example_step": {
            "action": "semantic_cluster_sections",
            "arguments": {"sections": []},
            "depends_on": [2]
        }
    },

    {
        "action": "compare_documents",
        "description": "Compare two documents to find differences, similarities, or conflicts.",
        "required_args": ["doc1", "doc2"],
        "optional_args": ["granularity"],
        "example_step": {
            "action": "compare_documents",
            "arguments": {"doc1": "path1", "doc2": "path2", "granularity": "auto"},
            "depends_on": []
        }
    },

    {
        "action": "summarize_document",
        "description": "Produce a summary of a document or extracted text.",
        "required_args": ["text"],
        "optional_args": ["style", "length"],
        "example_step": {
            "action": "summarize_document",
            "arguments": {"text": "string", "style": "brief"},
            "depends_on": []
        }
    },

    {
        "action": "classify_document_type",
        "description": "Classify a document into a type (contract, bid, invoice, spec, etc).",
        "required_args": ["text"],
        "optional_args": [],
        "example_step": {
            "action": "classify_document_type",
            "arguments": {"text": "string"},
            "depends_on": []
        }
    },

    {
        "action": "extract_entities",
        "description": "Extract structured entities such as people, dates, vendor names, bid amounts, etc.",
        "required_args": ["text"],
        "optional_args": ["entity_types"],
        "example_step": {
            "action": "extract_entities",
            "arguments": {"text": "string", "entity_types": ["vendor", "amount"]},
            "depends_on": []
        }
    },

    {
        "action": "extract_tables",
        "description": "Extract tabular data from structured or semi-structured documents.",
        "required_args": ["filename"],
        "optional_args": ["format"],
        "example_step": {
            "action": "extract_tables",
            "arguments": {"filename": "path/to/file"},
            "depends_on": []
        }
    },

    {
        "action": "analyze_bid_comparison",
        "description": "Compare multiple bid files and produce structured insights.",
        "required_args": ["documents"],
        "optional_args": ["focus"],
        "example_step": {
            "action": "analyze_bid_comparison",
            "arguments": {"documents": ["file1", "file2"], "focus": "pricing"},
            "depends_on": []
        }
    },

]

def get_action_catalog():
    """Return full catalog."""
    return {
        "version": ACTION_CATALOG_VERSION,
        "document_actions": DOCUMENT_ACTIONS,
    }

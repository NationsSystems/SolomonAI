"""
File: solomon_core/docintel/results/result_serializer.py
Phase: 54 — Document Intelligence System Completion
Purpose: Deterministic serialization of governed execution results

This module defines serialization utilities for ExecutionResultEnvelope.
Serialization is purely structural and must not alter, infer, redact,
or enrich the underlying result.

CRITICAL INVARIANTS:
- Serialization is deterministic and lossless
- No inference, summarization, or interpretation
- No authority or execution logic
"""

from __future__ import annotations

from typing import Any, Dict

from solomon_core.docintel.results.execution_result_envelope import (
    ExecutionResultEnvelope,
)
from solomon_core.docintel.evidence.evidence_reference import EvidenceReference


def serialize_execution_result(
    envelope: ExecutionResultEnvelope,
) -> Dict[str, Any]:
    """
    Serialize an ExecutionResultEnvelope into a JSON-safe dictionary.

    This function performs structural serialization only.
    """

    envelope.assert_valid()
    result = envelope.result

    return {
        "execution_id": result.execution_identity.execution_id,
        "emitted_utc": envelope.emitted_utc,
        "primitive": {
            "name": result.primitive_result.primitive_name,
            "version": result.primitive_result.primitive_version,
        },
        "payload": result.primitive_result.payload,
        "evidence": _serialize_evidence_binding(result.evidence_binding),
    }


# ----------------------------------------------------------------------
# Internal helpers
# ----------------------------------------------------------------------

def _serialize_evidence_binding(binding) -> Dict[str, Any]:
    binding.assert_valid()

    return {
        "policy": {
            "required_anchor_types": [
                t.__name__ for t in binding.policy.required_anchor_types
            ],
            "minimum_references": binding.policy.minimum_references,
        },
        "references": [
            _serialize_evidence_reference(ref)
            for ref in binding.evidence.references
        ],
    }


def _serialize_evidence_reference(ref: EvidenceReference) -> Dict[str, Any]:
    ref.assert_valid()

    anchor = ref.anchor

    anchor_repr = {"type": type(anchor).__name__}

    for field in vars(anchor):
        anchor_repr[field] = getattr(anchor, field)

    return {
        "document_id": ref.document_id,
        "anchor": anchor_repr,
        "description": ref.description,
    }

"""
File: solomon_core/docintel/results/result_redaction.py
Phase: 54 — Document Intelligence System Completion
Purpose: Deterministic redaction of governed results for GUI display

This module defines controlled redaction utilities used to present
EvidenceBoundResults safely in user-facing surfaces. Redaction removes
*data*, never structure, and never alters evidence relationships.

CRITICAL INVARIANTS:
- Redaction is explicit and deterministic
- No inference, summarization, or interpretation
- No mutation of underlying governed objects
- CLI may bypass redaction; GUI must not
"""

from __future__ import annotations

from typing import Any, Dict

from solomon_core.docintel.results.execution_result_envelope import (
    ExecutionResultEnvelope,
)


def redact_for_gui(
    envelope: ExecutionResultEnvelope,
) -> Dict[str, Any]:
    """
    Produce a GUI-safe representation of an ExecutionResultEnvelope.

    Payload content may be omitted or truncated, but evidence structure
    and execution identity must remain intact.
    """

    envelope.assert_valid()
    result = envelope.result

    return {
        "execution_id": result.execution_identity.execution_id,
        "primitive": {
            "name": result.primitive_result.primitive_name,
            "version": result.primitive_result.primitive_version,
        },
        "payload_present": result.primitive_result.payload is not None,
        "evidence": {
            "reference_count": len(result.evidence_binding.evidence.references),
            "document_ids": result.evidence_binding.evidence.document_ids(),
        },
        "emitted_utc": envelope.emitted_utc,
    }

# solomon_core/due_process/due_process_engine.py
# ------------------------------------------------------------------
# Solomon AI — Due Process Engine (DPE)
# Law Interpreter (Runtime / Pure / Deterministic)
#
# PURPOSE:
#   Evaluate collected Evidence against a compiled law artifact and
#   emit a single authoritative verdict.
#
# CONTRACT:
#   • Pure function (no side effects)
#   • Deterministic
#   • No I/O, no logging, no mutation
#   • No intent inference
#   • Evaluates ALL applicable laws
#
# CONSTITUTIONAL ORDERING:
#   PROHIBITED > REQUIRES_ACTION > AUTHORIZED
# ------------------------------------------------------------------

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import List

from solomon_core.due_process.evidence import EvidencePacket, TriState
from solomon_core.due_process.law_compiler import CompiledLawArtifact


# ============================================================================
# Verdict Ordering (Authority)
# ============================================================================

_VERDICT_PRIORITY = {
    "PROHIBITED": 3,
    "REQUIRES_ACTION": 2,
    "AUTHORIZED": 1,
}


# ============================================================================
# DPE Result
# ============================================================================

@dataclass(frozen=True, slots=True)
class DueProcessResult:
    verdict: str
    matched_law_ids: List[str]
    law_artifact_version: str
    basis: dict
    evaluation_timestamp: str
    evidence_hash: str


# ============================================================================
# Interpreter
# ============================================================================

def evaluate_due_process(
    *,
    evidence: EvidencePacket,
    compiled_laws: CompiledLawArtifact,
) -> DueProcessResult:
    """
    Evaluate evidence against compiled laws and emit a verdict.
    """

    matched_laws = []

    for law in compiled_laws.laws:
        satisfied = True

        for fact_key, required_value in law.conditions.items():
            actual = evidence.fact(fact_key)
            if actual.value != required_value:
                satisfied = False
                break

        if satisfied:
            matched_laws.append(law)

    # Default verdict (innocent until proven otherwise)
    final_verdict = "AUTHORIZED"
    matched_ids: List[str] = []
    basis_summary = ""

    for law in matched_laws:
        if _VERDICT_PRIORITY[law.verdict] > _VERDICT_PRIORITY[final_verdict]:
            final_verdict = law.verdict
            basis_summary = law.basis_summary

    matched_ids = [l.law_id for l in matched_laws]

    return DueProcessResult(
        verdict=final_verdict,
        matched_law_ids=matched_ids,
        law_artifact_version=compiled_laws.version,
        basis={"summary": basis_summary} if basis_summary else {},
        evaluation_timestamp=datetime.utcnow().isoformat(),
        evidence_hash=str(hash(tuple(sorted(evidence.facts.items())))),
    )

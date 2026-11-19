# solomon_core/due_process/law_compiler.py
# ------------------------------------------------------------------
# Solomon AI — Due Process Engine (DPE)
# Law Compilation Pipeline (Build-Time Only)
#
# PURPOSE:
#   Compile human-authored JSON law files into a single immutable
#   runtime artifact suitable for constant-time evaluation.
#
# CONTRACT:
#   • Build-time only (never called at runtime)
#   • Compilation failure is fatal
#   • Output is immutable and versioned
#   • Runtime must never read source JSON
#
# NON-GOALS:
#   • No evaluation
#   • No inference
#   • No execution
#   • No hot reload
# ------------------------------------------------------------------

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Mapping

from solomon_core.due_process.law_schema import (
    LawBook,
    LawDefinition,
    LawConditions,
    validate_law_book,
)


# ============================================================================
# Compiled Law Representation (Runtime-Facing)
# ============================================================================

@dataclass(frozen=True, slots=True)
class CompiledLaw:
    """
    Normalized, runtime-ready law.
    """
    law_id: str
    verdict: str
    conditions: Mapping[str, str]
    basis_summary: str


@dataclass(frozen=True, slots=True)
class CompiledLawArtifact:
    """
    Immutable artifact loaded by the Due Process Engine at runtime.
    """
    version: str
    content_hash: str
    laws: List[CompiledLaw]


# ============================================================================
# Compilation
# ============================================================================

def compile_law_books(
    *,
    law_books: List[LawBook],
    artifact_version: str,
) -> CompiledLawArtifact:
    """
    Compile multiple LawBooks into a single immutable artifact.

    Raises:
      - ValueError on any structural or semantic violation
    """

    compiled: List[CompiledLaw] = []

    for book in law_books:
        validate_law_book(book)

        for law in book.laws:
            compiled.append(
                CompiledLaw(
                    law_id=law.law_id,
                    verdict=law.verdict,
                    conditions=dict(law.conditions.requires),
                    basis_summary=law.basis_summary,
                )
            )

    # Stable ordering for hashing / determinism
    compiled_sorted = sorted(compiled, key=lambda l: l.law_id)

    # Deterministic hash
    hash_payload = json.dumps(
        [
            {
                "law_id": l.law_id,
                "verdict": l.verdict,
                "conditions": dict(l.conditions),
                "basis_summary": l.basis_summary,
            }
            for l in compiled_sorted
        ],
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")

    content_hash = hashlib.sha256(hash_payload).hexdigest()

    return CompiledLawArtifact(
        version=artifact_version,
        content_hash=content_hash,
        laws=compiled_sorted,
    )


# ============================================================================
# Serialization (Optional Build Output)
# ============================================================================

def serialize_compiled_artifact(artifact: CompiledLawArtifact) -> Dict[str, object]:
    """
    Serialize a compiled artifact for disk storage or embedding.
    """
    return {
        "version": artifact.version,
        "content_hash": artifact.content_hash,
        "laws": [
            {
                "law_id": law.law_id,
                "verdict": law.verdict,
                "conditions": dict(law.conditions),
                "basis_summary": law.basis_summary,
            }
            for law in artifact.laws
        ],
    }

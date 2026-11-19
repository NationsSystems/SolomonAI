# ------------------------------------------------------------------
# FILE: solomon_core/fis/fis_pipeline.py
# DIRECTORY: solomon_core/fis/
# ------------------------------------------------------------------
# Fingerprint Identity System (FIS) Pipeline
# ------------------------------------------------------------------

from __future__ import annotations

from typing import List

from .fis_components import (
    tokenize,
    normalize,
    validate,
    fingerprint,
)
from .fis_registry import FISRegistry
from .fis_types import (
    FISToken,
    FISTokenStatus,
    FISIdentifierResult,
    FISIdentifierStatus,
    FISSummary,
    FISPipelineResult,
)


class FISPipeline:
    def __init__(self, registry: FISRegistry) -> None:
        self._registry = registry

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def process(self, raw_input: str) -> FISPipelineResult:

        raw_tokens: List[str] = tokenize(raw_input)
        results: List[FISIdentifierResult] = []

        valid_count = 0
        rejected_count = 0
        bound_count = 0
        unbound_count = 0

        for raw in raw_tokens:
            normalized = normalize(raw)

            token = FISToken(raw=raw, normalized=normalized)

            # ----------------------------------------------------------
            # 🔒 VALIDATION IS THE ONLY ADMISSIBILITY AUTHORITY
            # (Removed destructive pre-filter that dropped real tokens
            # like "dns?" and "http?")
            # ----------------------------------------------------------
            validation = validate(token)

            # ----------------------------------------------------------
            # REJECTED TOKEN
            # ----------------------------------------------------------
            if validation.status == FISTokenStatus.REJECTED:
                rejected_count += 1

                results.append(
                    FISIdentifierResult(
                        token=token,
                        status=FISTokenStatus.REJECTED,
                        fingerprint=None,
                        identifier_status=None,
                        record=None,
                        reason=validation.reason,
                    )
                )
                continue

            # ----------------------------------------------------------
            # VALID TOKEN → FINGERPRINT
            # ----------------------------------------------------------
            valid_count += 1

            fp_result = fingerprint(token)

            record = self._registry.upsert(
                fingerprint=fp_result.fingerprint,
                canonical_value=token.normalized,
            )

            identifier_status = record.status

            if identifier_status == FISIdentifierStatus.BOUND:
                bound_count += 1
            else:
                unbound_count += 1

            results.append(
                FISIdentifierResult(
                    token=token,
                    status=FISTokenStatus.VALID,
                    fingerprint=fp_result.fingerprint,
                    identifier_status=identifier_status,
                    record=record,
                    reason=None,
                )
            )

        summary = FISSummary(
            total_tokens=len(raw_tokens),
            valid_tokens=valid_count,
            rejected_tokens=rejected_count,
            bound_identifiers=bound_count,
            unbound_identifiers=unbound_count,
        )

        return FISPipelineResult(
            raw_input=raw_input,
            tokens=tuple(results),
            summary=summary,
        )
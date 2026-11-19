# ------------------------------------------------------------------
# FILE: solomon_core/fis/fis_registry.py
# DIRECTORY: solomon_core/fis/
# ------------------------------------------------------------------
# Fingerprint Identity System (FIS) In-Memory Registry (v2)
#
# Purpose:
#   Provides a deterministic, in-memory identity registry for:
#     - lookup by fingerprint
#     - insert (new identifier)
#     - update (seen_count, timestamps)
#     - deterministic promotion (UNBOUND → BOUND)
#
# Design Rules:
#   - No external dependencies (no DB yet)
#   - Deterministic behavior only
#   - No heuristics or inference
#   - Single responsibility: identity persistence + recurrence-based promotion
# ------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Optional

from .fis_types import (
    FISRegistryRecord,
    FISIdentifierStatus,
)


# ------------------------------------------------------------------
# Promotion Configuration (Deterministic)
# ------------------------------------------------------------------

PROMOTION_THRESHOLD = 3
"""
Number of observations required before an identifier is promoted
from UNBOUND → BOUND.

This is a deterministic rule based solely on recurrence count.
"""


def _utc_now_iso() -> str:
    """
    Generate a UTC ISO-8601 timestamp.
    """
    return datetime.now(timezone.utc).isoformat()


class FISRegistry:
    """
    In-memory registry keyed by fingerprint.

    v2 Enhancements:
      - Deterministic promotion based on seen_count
      - No semantic interpretation
      - No external dependencies

    Persistence (DB) can replace this later without changing interface.
    """

    def __init__(self) -> None:
        self._store: Dict[str, FISRegistryRecord] = {}

    # ------------------------------------------------------------------
    # Lookup
    # ------------------------------------------------------------------

    def get(self, fingerprint: str) -> Optional[FISRegistryRecord]:
        """
        Retrieve existing record by fingerprint.
        """
        return self._store.get(fingerprint)

    # ------------------------------------------------------------------
    # Upsert
    # ------------------------------------------------------------------

    def upsert(self, fingerprint: str, canonical_value: str) -> FISRegistryRecord:
        """
        Insert or update an identifier record.

        Behavior:
          - If fingerprint exists:
              - increment seen_count
              - update last_seen
              - apply deterministic promotion rule
          - If not:
              - create new UNBOUND record
        """

        existing = self._store.get(fingerprint)
        now = _utc_now_iso()

        if existing:
            new_seen_count = existing.seen_count + 1

            # ----------------------------------------------------------
            # Deterministic Promotion Logic
            # ----------------------------------------------------------
            if (
                existing.status == FISIdentifierStatus.UNBOUND
                and new_seen_count >= PROMOTION_THRESHOLD
            ):
                new_status = FISIdentifierStatus.BOUND
            else:
                new_status = existing.status

            updated = FISRegistryRecord(
                fingerprint=existing.fingerprint,
                canonical_value=existing.canonical_value,
                status=new_status,
                seen_count=new_seen_count,
                first_seen=existing.first_seen,
                last_seen=now,
            )

            self._store[fingerprint] = updated
            return updated

        # --------------------------------------------------------------
        # New Identifier (Always UNBOUND Initially)
        # --------------------------------------------------------------
        new_record = FISRegistryRecord(
            fingerprint=fingerprint,
            canonical_value=canonical_value,
            status=FISIdentifierStatus.UNBOUND,
            seen_count=1,
            first_seen=now,
            last_seen=now,
        )

        self._store[fingerprint] = new_record
        return new_record

    # ------------------------------------------------------------------
    # Status Update (Explicit)
    # ------------------------------------------------------------------

    def set_status(
        self,
        fingerprint: str,
        status: FISIdentifierStatus,
    ) -> Optional[FISRegistryRecord]:
        """
        Update identifier status explicitly.

        This method remains available for higher-layer control,
        but is not required for promotion logic.
        """

        existing = self._store.get(fingerprint)
        if not existing:
            return None

        updated = FISRegistryRecord(
            fingerprint=existing.fingerprint,
            canonical_value=existing.canonical_value,
            status=status,
            seen_count=existing.seen_count,
            first_seen=existing.first_seen,
            last_seen=_utc_now_iso(),
        )

        self._store[fingerprint] = updated
        return updated

    # ------------------------------------------------------------------
    # Introspection (Debug / Testing)
    # ------------------------------------------------------------------

    def size(self) -> int:
        """
        Return number of stored identifiers.
        """
        return len(self._store)

    def all_records(self) -> Dict[str, FISRegistryRecord]:
        """
        Return a shallow copy of all records (for testing/debugging).
        """
        return dict(self._store)
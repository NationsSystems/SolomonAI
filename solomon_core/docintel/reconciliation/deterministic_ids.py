# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/deterministic_ids.py
#
# PURPOSE:
# Provide reproducible, deterministic identifiers for Phase-75
# relationship and conflict objects.
#
# AUTHORITY:
# Mechanical only.
# Never encodes precedence or interpretation.
#
# PHASE-75 GUARANTEES:
# • Same inputs → same IDs
# • Order independent
# • Rebuild safe
# ---------------------------------------------------------------------------

import hashlib
from typing import Iterable


# ---------------------------------------------------------------------------
# Stable Hash Helper
# ---------------------------------------------------------------------------

def _stable_hash(parts: Iterable[str]) -> str:
    """
    Produce deterministic hash from ordered textual components.
    """
    h = hashlib.sha256()
    for p in parts:
        h.update(p.encode("utf-8"))
        h.update(b"|")
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Relationship ID
# ---------------------------------------------------------------------------

def build_relationship_id(
    relationship_type: str,
    member_ids: Iterable[str],
    basis: str,
) -> str:
    """
    Deterministic recipe for relationship identity.
    """
    ordered_members = sorted(member_ids)
    return _stable_hash(
        ["REL", relationship_type, basis, *ordered_members]
    )


# ---------------------------------------------------------------------------
# Conflict ID
# ---------------------------------------------------------------------------

def build_conflict_id(
    relationship_id: str,
    member_ids: Iterable[str],
    basis: str,
) -> str:
    """
    Deterministic recipe for conflict identity.
    """
    ordered_members = sorted(member_ids)
    return _stable_hash(
        ["CON", relationship_id, basis, *ordered_members]
    )

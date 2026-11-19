"""
File: solomon_core/docintel/certified_primitive_registry.py

Solomon AI — Certified Analysis Primitive Registry
Phase: 53 — Axial Control Genesis
Status: CONTROL-ONLY · FAIL-CLOSED

This module defines the mechanical registry for Certified Analysis Primitives.
It provides static registration, certification enforcement, and explicit
rejection semantics.

HARD CONSTRAINTS:
- No authority
- No execution
- No intent inference
- No dynamic composition
- No primitive-to-primitive calls
- Static, inspectable state only
"""

from dataclasses import dataclass, field
from typing import Any, Dict, Mapping, Optional, Tuple
from enum import Enum


# ---------------------------------------------------------------------------
# Certification States
# ---------------------------------------------------------------------------

class CertificationStatus(str, Enum):
    CERTIFIED = "certified"
    DEPRECATED = "deprecated"
    REVOKED = "revoked"


# ---------------------------------------------------------------------------
# Registry Records
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PrimitiveIdentity:
    name: str
    version: str


@dataclass(frozen=True)
class EvidenceRequirements:
    """
    Declarative evidence requirements.
    No inference, no defaults.
    """
    required_sources: Tuple[str, ...]
    allow_ambiguity: bool = False


@dataclass(frozen=True)
class IOContract:
    """
    Declarative input/output schema references.
    Schemas are identifiers only (no runtime validation here).
    """
    input_schema_id: str
    output_schema_id: str


@dataclass(frozen=True)
class StaticComposition:
    """
    Static, non-branching composition.
    Declared at certification time only.
    """
    components: Tuple[PrimitiveIdentity, ...]


@dataclass(frozen=True)
class CertifiedPrimitiveRecord:
    identity: PrimitiveIdentity
    status: CertificationStatus
    io_contract: IOContract
    evidence: EvidenceRequirements
    composition: Optional[StaticComposition] = None
    metadata: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Registry Errors
# ---------------------------------------------------------------------------

class RegistryError(Exception):
    pass


class CertificationViolation(RegistryError):
    pass


class RegistrationError(RegistryError):
    pass


# ---------------------------------------------------------------------------
# Registry (Control-Only)
# ---------------------------------------------------------------------------

class CertifiedPrimitiveRegistry:
    """
    Static registry for Certified Analysis Primitives.

    NOTE:
    - This registry does NOT execute primitives.
    - This registry does NOT validate schemas.
    - This registry does NOT infer anything.
    - This registry only enforces certification presence and static rules.
    """

    def __init__(self) -> None:
        self._records: Dict[Tuple[str, str], CertifiedPrimitiveRecord] = {}

    # ---------------------------------------------------------------------
    # Registration
    # ---------------------------------------------------------------------

    def register(self, record: CertifiedPrimitiveRecord) -> None:
        key = (record.identity.name, record.identity.version)

        if key in self._records:
            raise RegistrationError(
                f"Primitive already registered: {record.identity.name}@{record.identity.version}"
            )

        # Static composition rules
        if record.composition is not None:
            if not record.composition.components:
                raise CertificationViolation(
                    "Static composition must declare components."
                )

        self._records[key] = record

    # ---------------------------------------------------------------------
    # Lookup & Enforcement
    # ---------------------------------------------------------------------

    def get(self, name: str, version: str) -> CertifiedPrimitiveRecord:
        key = (name, version)
        if key not in self._records:
            raise CertificationViolation(
                f"Primitive not certified: {name}@{version}"
            )
        return self._records[key]

    def assert_certified(self, name: str, version: str) -> CertifiedPrimitiveRecord:
        record = self.get(name, version)

        if record.status is not CertificationStatus.CERTIFIED:
            raise CertificationViolation(
                f"Primitive not executable due to status '{record.status.value}': "
                f"{name}@{version}"
            )

        return record

    # ---------------------------------------------------------------------
    # Introspection (Read-Only)
    # ---------------------------------------------------------------------

    def list_certified(self) -> Tuple[CertifiedPrimitiveRecord, ...]:
        return tuple(
            r for r in self._records.values()
            if r.status is CertificationStatus.CERTIFIED
        )

    def list_all(self) -> Tuple[CertifiedPrimitiveRecord, ...]:
        return tuple(self._records.values())

    # ---------------------------------------------------------------------
    # Explicit Non-Capabilities
    # ---------------------------------------------------------------------

    def __getattr__(self, name: str):
        raise AttributeError(
            f"CertifiedPrimitiveRegistry has no capability '{name}'. "
            "Registry is static and control-only."
        )

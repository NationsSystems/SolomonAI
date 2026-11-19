"""
solomon_core/ingress/posture.py

Phase 48 — Ingress Posture Model (Declarative)

PURPOSE
-------
Provide a minimal, explicit posture structure used to represent
classification outcomes at the ingress boundary.

This model:
- Encodes authority, determinism, and presentation explicitly
- Prevents ad-hoc dict drift
- Carries no execution semantics
- Is safe to remove
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class IngressPosture:
    """
    Declarative posture for ingress classification.
    """
    authority: str
    determinism: str
    presentation: str
    execution_eligible: bool = False
    disallowed: bool = False
    collapsed: bool = False


def posture_from_dict(data: dict) -> IngressPosture:
    """
    Convert a posture dict into a frozen IngressPosture.

    This is a defensive conversion layer to prevent mutation
    and enforce explicit fields.
    """
    return IngressPosture(
        authority=data.get("authority"),
        determinism=data.get("determinism"),
        presentation=data.get("presentation"),
        execution_eligible=bool(data.get("execution_eligible", False)),
        disallowed=bool(data.get("disallowed", False)),
        collapsed=bool(data.get("collapsed", False)),
    )

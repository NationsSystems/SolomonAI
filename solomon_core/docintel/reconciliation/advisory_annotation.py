# ---------------------------------------------------------------------------
# FILE: solomon_core/docintel/reconciliation/advisory_annotation.py
#
# PURPOSE:
# Provide container for professional or system advisory notes
# attached to reconciliation artifacts.
#
# AUTHORITY:
# No mutation.
# No override.
# Advisory visibility only.
# ---------------------------------------------------------------------------

from dataclasses import dataclass, field
from typing import Dict, Any


@dataclass(frozen=True)
class AdvisoryAnnotation:
    """
    Non-authoritative commentary bound to a structural object.

    This object never:
        • changes Tier-1 facts
        • resolves conflicts
        • establishes precedence
    """

    target_id: str
    note: str
    metadata: Dict[str, Any] = field(default_factory=dict)

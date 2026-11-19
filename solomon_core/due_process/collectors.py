# solomon_core/due_process/collectors.py
# ------------------------------------------------------------------
# Solomon AI — Due Process Engine (DPE)
# Evidence Collectors (Interfaces / Contracts Only)
#
# PURPOSE:
#   Define the constitutional interfaces for evidence collectors.
#   Collectors observe and record facts only — NO inference, NO execution,
#   NO I/O side effects, NO defaults, NO authority.
#
# CONTRACT:
#   • Collectors emit explicit TriState facts.
#   • Collector failure or absence yields UNKNOWN, never FALSE.
#   • Collectors may be composed, but never infer or recommend.
#   • This file defines interfaces and enums only.
# ------------------------------------------------------------------

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, Mapping

from solomon_core.due_process.evidence import TriState


# ============================================================================
# Collector Identity
# ============================================================================

class CollectorId(str, Enum):
    """
    Canonical collector identifiers.
    These are stable and auditable.
    """
    INPUT_REGISTRAR = "INPUT_REGISTRAR"
    GUI_STATE_RECORDER = "GUI_STATE_RECORDER"
    REGISTRY_OBSERVER = "REGISTRY_OBSERVER"
    MEASUREMENT_INSTRUMENT = "MEASUREMENT_INSTRUMENT"
    USER_AFFIRMATION_RECORDER = "USER_AFFIRMATION_RECORDER"


# ============================================================================
# Collector Interface
# ============================================================================

class EvidenceCollector(ABC):
    """
    Abstract base class for all evidence collectors.

    Implementations MUST:
      - Observe only
      - Emit explicit TriState facts
      - Never infer missing facts
      - Never mutate global state
    """

    @property
    @abstractmethod
    def collector_id(self) -> CollectorId:
        """Return the stable collector identifier."""
        raise NotImplementedError

    @abstractmethod
    def collect(self) -> Mapping[str, TriState]:
        """
        Collect evidence facts.

        Returns:
          Mapping[str, TriState]:
            - Keys MUST be canonical EvidenceKeys
            - Values MUST be TriState
            - Missing keys are interpreted as UNKNOWN
        """
        raise NotImplementedError


# ============================================================================
# Collector Output Envelope (Optional Utility)
# ============================================================================

class CollectorOutput:
    """
    Simple, explicit container for collector results.
    Useful for aggregation without inference.
    """

    def __init__(self, collector_id: CollectorId, facts: Mapping[str, TriState]):
        self.collector_id = collector_id
        self.facts: Dict[str, TriState] = dict(facts)

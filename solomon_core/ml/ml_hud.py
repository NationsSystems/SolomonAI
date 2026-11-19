# solomon_core/ml/ml_hud.py
# ---------------------------------------------------------------------------
# Phase 45 — ML HUD No-Op + Minimal Advisory Signal
# ---------------------------------------------------------------------------
# PURPOSE:
#   Provide a safe, non-authoritative ML HUD implementation that:
#     • Emits advisory-only situational awareness signals
#     • Never affects routing or execution
#     • Is fully removable / disableable by the orchestrator
#
# PHASE 45 SCOPE:
#   • Emit a minimal, deterministic HUD signal:
#       "Multiple documents detected"
#
# ---------------------------------------------------------------------------

from solomon_core.logger import get_logger
from solomon_core.ml.ml_hud_contract import (
    MLHUDInterface,
    MLHUDContext,
    MLHUDOutput,
    HUDSignal,
)

logger = get_logger("ml_hud")


# ---------------------------------------------------------------------------
# ML HUD Implementation (SAFE, ADVISORY)
# ---------------------------------------------------------------------------

class NoOpMLHUD(MLHUDInterface):
    """
    ML HUD implementation with a minimal advisory signal.

    Guarantees:
      • No authority
      • No routing
      • No execution impact
      • Safe failure behavior
      • No configuration awareness
    """

    def evaluate(self, context: MLHUDContext) -> MLHUDOutput:
        """
        Evaluate the provided context and emit advisory-only signals.

        This method MUST:
          • Never throw
          • Never read configuration
          • Never mutate state
          • Always return MLHUDOutput
        """
        try:
            signals = []

            # --------------------------------------------------
            # Phase 45 — Minimal HUD Signal
            # --------------------------------------------------
            doc_count = len(context.active_documents or [])
            if doc_count > 1:
                signals.append(
                    HUDSignal(
                        signal_type="document_context",
                        description=f"{doc_count} documents are active for this request.",
                        confidence=1.0,
                        metadata={
                            "document_count": doc_count,
                            "documents": context.active_documents,
                        },
                    )
                )

            return MLHUDOutput(signals=signals)

        except Exception as exc:
            # Absolute safety: ML HUD must never affect execution
            logger.warning(
                "ML HUD evaluation failed (ignored)",
                extra={"error": str(exc)},
            )
            return MLHUDOutput()


# ---------------------------------------------------------------------------
# Singleton Accessor
# ---------------------------------------------------------------------------

_ml_hud_instance: MLHUDInterface = NoOpMLHUD()


def get_ml_hud() -> MLHUDInterface:
    """
    Retrieve the active ML HUD instance.

    The HUD is:
      • Side-band only
      • Advisory only
      • Removable
    """
    return _ml_hud_instance


__all__ = [
    "get_ml_hud",
]

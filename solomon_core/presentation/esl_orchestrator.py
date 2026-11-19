# ---------------------------------------------------------------------------
# FILE: esl_orchestrator.py
# DIRECTORY: solomon_core/presentation/
# ---------------------------------------------------------------------------
# Estimator Synthesis Layer (ESL) — Deterministic Orchestrator
#
# Purpose:
#   Deterministically synthesize output from certified reasoning inputs.
#
# Hard Rules:
#   - No LLM
#   - Evidence-bound
#   - Single-doc safe (Phase 85 scope)
#   - Silent failure allowed (caller handles fallback)
#
# NOTE (Phase 88 correction):
#   ESL is now a PURE RENDERER.
#   It does NOT determine domain or presentation mode.
#   Presentation authority must be decided upstream and passed via:
#       decision["presentation_mode"] ∈ {"estimator", "generic"}
# ---------------------------------------------------------------------------

from __future__ import annotations

from typing import Dict, Any, List

from solomon_core.logger import get_logger

logger = get_logger("esl_orchestrator")


# ---------------------------------------------------------------------------
# Section Order (LOCKED — estimator mode only)
# ---------------------------------------------------------------------------

SECTION_ORDER = [
    "executive",
    "scope",
    "risk",
    "exclusions",
    "commercial",
    "bottom_line",
]

SEPARATOR = "\n________________________________________\n"
MAX_LEN = 12000

GENERIC_PASSTHROUGH_KEYS = (
    "answer_source",
    "summary_source",
    "summary_mode",
    "narration_mode",
    "generation_mode",
    "rendering_mode",
    "mode",
    "source",
    "used_fallback",
    "fallback_used",
    "raw_narration_success",
    "narration_brief_chars",
    "source_text_chars",
    "llm_error_present",
    "llm_error_signals",
)


# ---------------------------------------------------------------------------
# Safe Builder Imports (lazy pattern avoids circulars)
# ---------------------------------------------------------------------------

def _load_estimators():
    from solomon_core.presentation.esl_builders import (
        build_executive_section,
        build_scope_summary,
        build_risk_section,
        build_exclusion_posture,
        build_commercial_terms,
        synthesize_bottom_line,
    )

    return {
        "executive": build_executive_section,
        "scope": build_scope_summary,
        "risk": build_risk_section,
        "exclusions": build_exclusion_posture,
        "commercial": build_commercial_terms,
        "bottom_line": synthesize_bottom_line,
    }


def _load_generic_presenter():
    """
    Domain-neutral presenter for generic DocIntel.
    Lazy import to avoid circulars.
    """
    from solomon_core.presentation.docintel_generic_single_summary import (
        build_generic_single_summary,
    )

    return build_generic_single_summary


# ---------------------------------------------------------------------------
# Input Normalizer
# ---------------------------------------------------------------------------

def _normalize_esl_input(*args, **kwargs) -> Dict[str, Any]:
    """
    Accept both legacy and modern call shapes.
    """

    if args and isinstance(args[0], dict):
        return args[0]

    return {
        "documents": kwargs.get("documents") or [],
        "evidence": kwargs.get("evidence") or {},
        "decision": kwargs.get("decision") or {},
    }


# ---------------------------------------------------------------------------
# Presentation Mode Resolver (AUTHORITATIVE INPUT ONLY)
# ---------------------------------------------------------------------------

def _resolve_presentation_mode(decision: Dict[str, Any]) -> str:
    """
    STRICT RULE:

    ESL does NOT infer mode.

    Expected upstream contract:
        decision["presentation_mode"] ∈ {"estimator", "generic"}

    Fallback (safe):
        If missing → estimator (preserves legacy BEI behavior)
    """

    mode = (decision or {}).get("presentation_mode")

    if mode in ("estimator", "generic"):
        return mode

    # Safe fallback preserves yesterday's working BEI behavior
    return "estimator"


def _build_generic_payload(
    *,
    result: Dict[str, Any],
    answer: str,
) -> Dict[str, Any]:
    """
    Return generic presenter output without stripping DocIntel metadata.

    Generic DocIntel summaries use payload-level metadata as the product
    authority for whether the visible answer came from raw narration or the
    deterministic fallback path. ESL must preserve that metadata rather than
    reducing the result to answer/sections/posture/confidence only.
    """

    payload: Dict[str, Any] = {
        "answer": answer,
        "sections": result.get("sections") or {},
        "posture": result.get("posture"),
        "confidence": result.get("confidence"),
    }

    for key in GENERIC_PASSTHROUGH_KEYS:
        if key in result:
            payload[key] = result.get(key)

    return payload


# ---------------------------------------------------------------------------
# Public Entry
# ---------------------------------------------------------------------------

def run_esl_orchestrator(*args, **kwargs) -> Dict[str, Any]:
    """
    Deterministic presentation execution.
    ESL is rendering-only.
    """

    try:
        esl_input = _normalize_esl_input(*args, **kwargs)

        documents: List[Dict[str, Any]] = esl_input.get("documents") or []
        evidence: Dict[str, Any] = esl_input.get("evidence") or {}
        decision: Dict[str, Any] = esl_input.get("decision") or {}

        if not documents:
            logger.warning("[ESL] no documents provided")
            return _empty_result()

        # ------------------------------------------------------------------
        # Mode provided by upstream authority (NOT inferred here)
        # ------------------------------------------------------------------
        mode = _resolve_presentation_mode(decision)

        primary_doc = documents[0]

        context = {
            "display_name": primary_doc.get("display_name"),
            "evidence": evidence,
            "decision": decision,
        }

        # ------------------------------------------------------------------
        # GENERIC MODE (domain-neutral)
        # ------------------------------------------------------------------
        if mode == "generic":
            try:
                presenter = _load_generic_presenter()
                result = presenter(context)

                if not isinstance(result, dict):
                    logger.warning("[ESL] generic presenter returned non-dict")
                    return _empty_result()

                answer = (result.get("answer") or "").strip()

                if len(answer) > MAX_LEN:
                    answer = answer[:MAX_LEN]

                answer = answer.replace("\u00a0", " ")

                return _build_generic_payload(
                    result=result,
                    answer=answer,
                )

            except Exception:
                logger.exception("[ESL] generic presenter failure")
                return _empty_result()

        # ------------------------------------------------------------------
        # ESTIMATOR MODE (existing behavior preserved EXACTLY)
        # ------------------------------------------------------------------

        builders = _load_estimators()
        section_outputs: Dict[str, Any] = {}

        for name in SECTION_ORDER:
            builder = builders.get(name)
            if not builder:
                logger.warning(f"[ESL] missing builder: {name}")
                section_outputs[name] = {"text": ""}
                continue

            try:
                section_outputs[name] = builder(context)
            except Exception as e:
                logger.warning(f"[ESL] builder failure: {name} → {e}")
                section_outputs[name] = {"text": ""}

        bottom = section_outputs.get("bottom_line") or {}
        posture = bottom.get("posture")
        confidence = bottom.get("confidence")

        parts: List[str] = []

        for name in SECTION_ORDER:
            txt = (section_outputs.get(name) or {}).get("text")
            if txt:
                parts.append(txt)

        answer = SEPARATOR.join(parts).strip()

        if not answer:
            answer = "No estimator synthesis available for this document."

        if len(answer) > MAX_LEN:
            answer = answer[:MAX_LEN]

        answer = answer.replace("\u00a0", " ")

        return {
            "answer": answer,
            "sections": section_outputs,
            "posture": posture,
            "confidence": confidence,
        }

    except Exception:
        logger.exception("[ESL] orchestrator failure")
        return _empty_result()


# ---------------------------------------------------------------------------
# Failsafe
# ---------------------------------------------------------------------------

def _empty_result() -> Dict[str, Any]:
    return {
        "answer": "",
        "sections": {},
        "posture": None,
        "confidence": None,
    }
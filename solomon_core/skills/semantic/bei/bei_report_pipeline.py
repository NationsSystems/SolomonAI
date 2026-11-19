# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_report_pipeline.py
# DIRECTORY: solomon_core/skills/semantic/bei/
# ---------------------------------------------------------------------------
# BEI Report Pipeline
#
# PURPOSE
#   Provide the V3 report-pipeline entrypoint while preserving the restored
#   deterministic BEI v1 estimator renderer and optionally applying the direct
#   custom model as a bounded report-writing voice layer.
#
# AUTHORITY CONTRACT
#   This module is not a router and does not authorize execution. It receives
#   already-routed DocIntel/BEI evidence and adapts it into the shape expected
#   by the V3 UI.
#
# MODEL CONTRACT
#   The custom model may add a short executive readout only after deterministic
#   BEI has produced governed evidence and report content. If model generation
#   fails validation, the deterministic report is returned unchanged.
# ---------------------------------------------------------------------------

from __future__ import annotations

import json
import re
from html import escape
from typing import Any, Dict, List, Optional

from solomon_core.logger import get_logger
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
)
from solomon_core.llm.llm_executor import execute_llm

logger = get_logger("bei_report_pipeline")

_REPORT_METADATA = {
    "source": "bei_document_extract_v1",
    "renderer": "deterministic_estimator_renderer",
    "status": "restored",
}

_MODEL_REPORT_METADATA = {
    "source": "bei_document_extract_v1",
    "renderer": "direct_custom_report_writer",
    "status": "model_brief_with_deterministic_report",
}

_BEI_CALL_SITE = "bei_report_writer"
_MAX_MODEL_REPORT_CONTEXT_CHARS = 1300
_MAX_MODEL_FACTS_CHARS = 700

_REPLACEMENTS = (
    (re.compile(r"\baward-ready\b", re.I), "ready for final leveling"),
    (re.compile(r"\bsafe to award\b", re.I), "ready for decision review"),
    (re.compile(r"\baward recommendation\b", re.I), "bid review summary"),
    (re.compile(r"\baward reliance\b", re.I), "use in bid leveling"),
    (re.compile(r"\bbefore reliance\b", re.I), "before use in leveling"),
    (re.compile(r"\baffect reliance\b", re.I), "affect bid leveling"),
    (re.compile(r"\bcommercially viable\b", re.I), "usable for leveling"),
    (re.compile(r"\bbest value\b", re.I), "pricing position"),
    (re.compile(r"\bbefore it should be used\b", re.I), "before it is used"),
)

_RESTRICTED_OUTPUT_PHRASES = (
    "award-ready",
    "safe to award",
    "award recommendation",
    "award reliance",
    "commercially viable",
    "best value",
    "before reliance",
    "affect reliance",
    "before it should be used",
)

_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_CODE_FENCE_START_RE = re.compile(r"(?is)^```(?:html|text)?\s*")
_CODE_FENCE_END_RE = re.compile(r"(?is)```\s*$")


# ---------------------------------------------------------------------------
# Base Helpers
# ---------------------------------------------------------------------------

def _safe_documents(documents: Any) -> List[Dict[str, Any]]:
    if not isinstance(documents, list):
        return []

    return [document for document in documents if isinstance(document, dict)]


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _limit_text(value: str, max_chars: int) -> str:
    cleaned = re.sub(r"\n{3,}", "\n\n", _safe_text(value))
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned)

    if len(cleaned) <= max_chars:
        return cleaned

    return cleaned[:max_chars].rstrip() + "\n...[truncated]"


def _strip_html(value: str) -> str:
    cleaned = _HTML_COMMENT_RE.sub("", _safe_text(value))
    cleaned = _HTML_TAG_RE.sub(" ", cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip()


def _compact_json(value: Any, max_chars: int) -> str:
    if value in (None, "", [], {}):
        return "{}"

    try:
        compact = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    except Exception:
        compact = str(value)

    return _limit_text(compact, max_chars)


def _raw_text_from_documents(documents: List[Dict[str, Any]]) -> str:
    parts: List[str] = []

    for document in documents:
        text = document.get("text")
        if isinstance(text, str) and text.strip():
            parts.append(text.strip())

    return "\n\n".join(parts)


def _payload_from_packet(packet: Any) -> Optional[Dict[str, Any]]:
    if not packet:
        return None

    if isinstance(packet, dict):
        payload = packet.get("payload")
        if isinstance(payload, dict):
            return dict(payload)

        answer = packet.get("answer")
        if isinstance(answer, str) and answer.strip():
            return {"answer": answer.strip()}

        return None

    payload = getattr(packet, "payload", None)
    if isinstance(payload, dict):
        return dict(payload)

    return None


def _packet_bool(packet: Any, key: str, default: bool) -> bool:
    if isinstance(packet, dict) and isinstance(packet.get(key), bool):
        return packet[key]

    return default


def _packet_verdict(packet: Any, default: str = "AUTHORIZED") -> str:
    if isinstance(packet, dict):
        verdict = packet.get("verdict")
        if isinstance(verdict, str) and verdict.strip():
            return verdict.strip()

    return default


def _build_reasoning_payload(
    *,
    documents: List[Dict[str, Any]],
    reconciliation: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    return {
        "inputs": {"documents": documents},
        "execution_context": {"renderer": "bei_v1_restored"},
        "reconciliation": reconciliation or {},
    }


def _requires_action_packet(message: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "packet_type": "docintel",
        "payload": {
            "answer": message,
            "bridge": "",
            "report_kind": "bid_scope_review",
            "suggestions": [],
        },
        "verdict": "REQUIRES_ACTION",
    }


def _error_packet(message: str) -> Dict[str, Any]:
    return {
        "ok": False,
        "packet_type": "docintel",
        "payload": {
            "answer": message,
            "bridge": "",
            "report_kind": "bid_scope_review",
            "suggestions": [],
        },
        "verdict": "ERROR",
    }


def _normalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    normalized_payload = dict(payload)
    normalized_payload["answer"] = _safe_text(payload.get("answer"))
    normalized_payload["report_kind"] = "bid_scope_review"
    normalized_payload.setdefault("bridge", "")
    normalized_payload.setdefault("suggestions", [])

    report = normalized_payload.get("report")
    if not isinstance(report, dict):
        normalized_payload["report"] = dict(_REPORT_METADATA)

    return normalized_payload


def _adapt_bei_packet(packet: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    verdict = _packet_verdict(packet)
    ok = _packet_bool(packet, "ok", verdict == "AUTHORIZED")

    return {
        "ok": ok,
        "packet_type": "docintel",
        "payload": _normalize_payload(payload),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# Direct Report Writer
# ---------------------------------------------------------------------------

def _extract_document_name(document: Dict[str, Any]) -> str:
    for key in ("display_name", "original_name", "filename", "name"):
        value = document.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()

    return "Document"


def _facts_from_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    evidence = payload.get("evidence")

    if not isinstance(evidence, dict):
        return {}

    facts = evidence.get("facts")
    return facts if isinstance(facts, dict) else {}


def _build_report_context(payload: Dict[str, Any]) -> str:
    answer = _strip_html(payload.get("answer"))
    return _limit_text(answer, _MAX_MODEL_REPORT_CONTEXT_CHARS)


def _build_writer_prompt(
    *,
    document_name: str,
    payload: Dict[str, Any],
) -> str:
    report_context = _build_report_context(payload)
    facts_summary = _compact_json(
        _facts_from_payload(payload),
        _MAX_MODEL_FACTS_CHARS,
    )

    return (
        "You are the Nations Systems BEI report voice layer.\n"
        "Write a short executive readout from governed BEI context only.\n"
        "Do not add facts, prices, dates, exclusions, risks, or conclusions.\n"
        "Do not make an award decision.\n"
        "Do not use award-ready, safe to award, award recommendation, "
        "award reliance, commercially viable, best value, before reliance, "
        "affect reliance, or before it should be used.\n"
        "Use bid leveling, final review, verification, reconciliation, and "
        "clarification language.\n"
        "Return plain text only, two short sentences maximum.\n\n"
        f"Document: {document_name}\n"
        f"Facts: {facts_summary}\n"
        f"Governed report context: {report_context}\n"
        "Executive readout:"
    )


def _strip_code_fences(value: str) -> str:
    cleaned = _safe_text(value)
    cleaned = _CODE_FENCE_START_RE.sub("", cleaned)
    cleaned = _CODE_FENCE_END_RE.sub("", cleaned)
    return cleaned.strip()


def _apply_output_replacements(value: str) -> str:
    cleaned = value

    for pattern, replacement in _REPLACEMENTS:
        cleaned = pattern.sub(replacement, cleaned)

    return cleaned.strip()


def _contains_restricted_phrase(value: str) -> bool:
    lowered = value.lower()
    return any(phrase in lowered for phrase in _RESTRICTED_OUTPUT_PHRASES)


def _normalize_model_brief(model_text: str) -> str:
    cleaned = _strip_code_fences(model_text)
    cleaned = _HTML_COMMENT_RE.sub("", cleaned)
    cleaned = _HTML_TAG_RE.sub(" ", cleaned)
    cleaned = _apply_output_replacements(cleaned)
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()

    if not cleaned:
        return ""

    if _contains_restricted_phrase(cleaned):
        logger.warning("[BEI_REPORT_PIPELINE][MODEL_REJECTED] restricted phrase remains")
        return ""

    sentences = re.split(r"(?<=[.!?])\s+", cleaned)
    concise = " ".join(sentence.strip() for sentence in sentences[:2] if sentence.strip())

    return concise.strip()


def _build_model_brief_html(model_brief: str) -> str:
    escaped_brief = escape(model_brief, quote=False)

    return (
        '<div class="bei-model-brief">'
        "<b>SolomonAI Readout</b>"
        f"<p>{escaped_brief}</p>"
        "</div>"
    )


def _merge_model_brief_with_report(report_html: str, brief_html: str) -> str:
    source_html = _safe_text(report_html)
    if not source_html:
        return brief_html

    if "bei-model-brief" in source_html:
        return source_html

    title_match = re.search(
        r"(?is)(<b>\s*Bid Summary\s*—.*?</b>)",
        source_html,
    )

    if title_match:
        return (
            source_html[:title_match.end()]
            + "\n"
            + brief_html
            + "\n"
            + source_html[title_match.end():]
        )

    div_match = re.search(
        r"(?is)(<div\s+class=[\"']bei-single-summary[\"'][^>]*>)",
        source_html,
    )

    if div_match:
        return (
            source_html[:div_match.end()]
            + "\n"
            + brief_html
            + "\n"
            + source_html[div_match.end():]
        )

    return brief_html + "\n" + source_html


def _apply_direct_report_writer(
    *,
    documents: List[Dict[str, Any]],
    payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if len(documents) != 1:
        return None

    document_name = _extract_document_name(documents[0])
    prompt = _build_writer_prompt(document_name=document_name, payload=payload)

    logger.info(
        "[BEI_REPORT_PIPELINE][MODEL_PROMPT_READY] call_site=%s prompt_chars=%s",
        _BEI_CALL_SITE,
        len(prompt),
    )

    result = execute_llm(
        LLMExecutionInput(
            user_query=prompt,
            mode=LLMExecutionMode.INFORMATIONAL_ONLY,
            context=None,
            call_site=_BEI_CALL_SITE,
        )
    )

    if not result or not result.output:
        logger.warning("[BEI_REPORT_PIPELINE][MODEL_FALLBACK] no direct model output")
        return None

    model_brief = _normalize_model_brief(result.output.text)

    if not model_brief:
        logger.warning("[BEI_REPORT_PIPELINE][MODEL_FALLBACK] unusable model output")
        return None

    source_answer = _safe_text(payload.get("answer"))
    model_brief_html = _build_model_brief_html(model_brief)
    final_answer = _merge_model_brief_with_report(source_answer, model_brief_html)

    polished_payload = dict(payload)
    polished_payload["answer"] = final_answer
    polished_payload["report"] = dict(_MODEL_REPORT_METADATA)

    logger.info(
        "[BEI_REPORT_PIPELINE][MODEL_OK] call_site=%s brief_chars=%s answer_chars=%s",
        _BEI_CALL_SITE,
        len(model_brief),
        len(final_answer),
    )

    return polished_payload


# ---------------------------------------------------------------------------
# Public Entry
# ---------------------------------------------------------------------------

def build_bei_report_packet(
    *,
    documents: List[Dict[str, Any]],
    reconciliation: Optional[Dict[str, Any]] = None,
    use_llm_wording: bool = True,
) -> Dict[str, Any]:
    """
    Build the BEI report output expected by the V3 UI.

    Deterministic BEI v1 remains the authority. When enabled, the direct
    custom model may add a short executive readout after the deterministic
    renderer has already produced governed content.
    """

    safe_documents = _safe_documents(documents)

    if not safe_documents:
        return _requires_action_packet("Bid & Scope Review requires at least one document.")

    try:
        from solomon_core.skills.semantic.bei_document_extract_v1 import (
            run_bei_document_extract_v1,
        )

        reasoning_payload = _build_reasoning_payload(
            documents=safe_documents,
            reconciliation=reconciliation,
        )

        legacy_packet = run_bei_document_extract_v1(
            reasoning_payload,
            _raw_text_from_documents(safe_documents),
        )

        payload = _payload_from_packet(legacy_packet)
        if not payload:
            return _error_packet("Bid & Scope Review produced no report payload.")

        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            return _error_packet("Bid & Scope Review produced an empty report.")

        logger.info(
            "[BEI_REPORT_PIPELINE] deterministic BEI renderer returned verdict=%s",
            _packet_verdict(legacy_packet),
        )

        if use_llm_wording and _packet_verdict(legacy_packet) == "AUTHORIZED":
            polished_payload = _apply_direct_report_writer(
                documents=safe_documents,
                payload=payload,
            )

            if polished_payload:
                return _adapt_bei_packet(legacy_packet, polished_payload)

        return _adapt_bei_packet(legacy_packet, payload)

    except Exception:
        logger.exception("[BEI_REPORT_PIPELINE] BEI report build failed")
        return _error_packet("Bid & Scope Review failed while building the report.")
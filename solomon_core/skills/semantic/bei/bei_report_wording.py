# ---------------------------------------------------------------------------
# FILE: solomon_core/skills/semantic/bei/bei_report_wording.py
# DIRECTORY: solomon_core/skills/semantic/bei/
# ---------------------------------------------------------------------------
# BEI Report Wording
#
# PURPOSE
#   Use the governed V3 LLM execution contract to rewrite customer-facing
#   BEI prose after deterministic report or comparison facts already exist.
#
# AUTHORITY CONTRACT
#   This module does not classify risk, add findings, remove findings, route
#   work, or change commercial facts. It may only rewrite approved wording
#   fields while preserving deterministic structure and locked facts.
# ---------------------------------------------------------------------------

from __future__ import annotations

import ast
import json
import re
from copy import deepcopy
from typing import Any, Dict, List

from solomon_core.logger import get_logger
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
    LLMResponseFormat,
)
from solomon_core.llm.llm_executor import execute_llm

logger = get_logger("bei_report_wording")

_STRING_LIST_FIELDS = (
    "key_findings",
    "estimator_impact",
    "recommended_actions",
)

_RISK_LIST_FIELDS = (
    "scope_gaps",
    "coordination_risks",
    "exclusion_risks",
    "schedule_risks",
)

_ALLOWED_TOP_LEVEL_FIELDS = {
    "primary_risk",
    "key_findings",
    "scope_gaps",
    "coordination_risks",
    "exclusion_risks",
    "schedule_risks",
    "estimator_impact",
    "recommended_actions",
}

_COMPARE_ALLOWED_FIELDS = {
    "comparison_summary",
    "qualification_summary",
    "review_notes",
    "overall",
}

_LOCKED_TOKEN_RE = re.compile(
    r"(\$[\d,]+(?:\.\d{2})?|\b\d+(?:\.\d+)?%)"
)


# ---------------------------------------------------------------------------
# Text / Shape Helpers
# ---------------------------------------------------------------------------

def _clean_string(value: Any, max_len: int = 700) -> str:
    if not isinstance(value, str):
        return ""

    text = " ".join(value.strip().split())
    return text[:max_len].strip()


def _clean_string_list(value: Any, limit: int, max_len: int = 700) -> List[str]:
    if not isinstance(value, list):
        return []

    cleaned: List[str] = []

    for item in value:
        text = _clean_string(item, max_len)

        if not text:
            return []

        cleaned.append(text)

        if len(cleaned) >= limit:
            break

    return cleaned


def _strip_code_fence(text: str) -> str:
    cleaned = text.strip()

    if cleaned.startswith("```"):
        lines = cleaned.splitlines()

        if lines and lines[0].strip().startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        cleaned = "\n".join(lines).strip()

    return cleaned


def _extract_json_span(text: str) -> str:
    cleaned = _strip_code_fence(text)
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start < 0 or end <= start:
        return ""

    return cleaned[start:end + 1].strip()


def _parse_object(text: str) -> Dict[str, Any]:
    if not text:
        return {}

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        pass

    try:
        parsed = ast.literal_eval(text)
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _unwrap_candidate(parsed: Dict[str, Any], allowed_fields: set[str]) -> Dict[str, Any]:
    if not isinstance(parsed, dict):
        return {}

    if any(key in parsed for key in allowed_fields):
        return parsed

    for wrapper_key in ("editable_fields", "report", "result", "rewritten_fields"):
        nested = parsed.get(wrapper_key)

        if isinstance(nested, dict) and any(key in nested for key in allowed_fields):
            return nested

    return {}


def _extract_json_object(text: str, allowed_fields: set[str]) -> Dict[str, Any]:
    if not isinstance(text, str):
        return {}

    direct = _parse_object(_strip_code_fence(text))

    if direct:
        return _unwrap_candidate(direct, allowed_fields)

    span = _extract_json_span(text)
    parsed = _parse_object(span)
    return _unwrap_candidate(parsed, allowed_fields)


def _metadata(source: str, status: str) -> Dict[str, str]:
    return {
        "source": source,
        "status": status,
    }


def _locked_tokens(value: Any) -> set[str]:
    text = json.dumps(value, ensure_ascii=False) if not isinstance(value, str) else value
    return {
        match.group(0).replace("$ ", "$").strip()
        for match in _LOCKED_TOKEN_RE.finditer(text)
    }


def _document_names(compare_packet: Dict[str, Any]) -> List[str]:
    documents = compare_packet.get("documents")

    if not isinstance(documents, list):
        return []

    names: List[str] = []

    for document in documents:
        if not isinstance(document, dict):
            continue

        name = _clean_string(document.get("name"), 180)
        if name:
            names.append(name)

    return names


# ---------------------------------------------------------------------------
# Single-Document Prompt Builder
# ---------------------------------------------------------------------------

def _editable_payload(report: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "primary_risk": report.get("primary_risk"),
        "key_findings": report.get("key_findings"),
        "scope_gaps": report.get("scope_gaps"),
        "coordination_risks": report.get("coordination_risks"),
        "exclusion_risks": report.get("exclusion_risks"),
        "schedule_risks": report.get("schedule_risks"),
        "estimator_impact": report.get("estimator_impact"),
        "recommended_actions": report.get("recommended_actions"),
    }


def _build_wording_prompt(report: Dict[str, Any]) -> str:
    control = {
        "locked_context": {
            "source": report.get("source"),
            "analyzed_at": report.get("analyzed_at"),
            "scope_completeness": report.get("scope_completeness"),
            "risk_level": report.get("risk_level"),
            "pricing": report.get("pricing"),
            "commercial_terms": report.get("commercial_terms"),
        },
        "editable_fields": _editable_payload(report),
        "required_output_keys": list(_ALLOWED_TOP_LEVEL_FIELDS),
    }

    return (
        "You are SolomonAI's guarded BEI report wording editor.\n"
        "Improve wording quality only for editable prose fields.\n"
        "Return JSON only. Do not add facts, remove facts, alter list counts, "
        "or change pricing, dates, quantities, severity, or commercial terms.\n\n"
        "Return this shape:\n"
        "{"
        '"primary_risk":"string",'
        '"key_findings":["string"],'
        '"scope_gaps":[{"title":"string","impact":"string"}],'
        '"coordination_risks":[{"title":"string","impact":"string"}],'
        '"exclusion_risks":[{"title":"string","impact":"string"}],'
        '"schedule_risks":[{"title":"string","impact":"string"}],'
        '"estimator_impact":["string"],'
        '"recommended_actions":["string"]'
        "}\n\n"
        f"INPUT_CONTRACT:\n{json.dumps(control, ensure_ascii=False)}"
    )


# ---------------------------------------------------------------------------
# Single-Document Guarded Application
# ---------------------------------------------------------------------------

def _apply_primary_risk(report: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    text = _clean_string(candidate.get("primary_risk"), 900)

    if not text:
        return False

    report["primary_risk"] = text
    return True


def _apply_string_list(report: Dict[str, Any], field: str, candidate: Dict[str, Any]) -> bool:
    current = report.get(field)
    proposed = candidate.get(field)

    if not isinstance(current, list) or not isinstance(proposed, list):
        return False

    if len(current) != len(proposed):
        return False

    cleaned = _clean_string_list(proposed, len(current), 500)

    if len(cleaned) != len(current):
        return False

    report[field] = cleaned
    return True


def _apply_risk_list(report: Dict[str, Any], field: str, candidate: Dict[str, Any]) -> bool:
    current = report.get(field)
    proposed = candidate.get(field)

    if not isinstance(current, list) or not isinstance(proposed, list):
        return False

    if len(current) != len(proposed):
        return False

    changed = False

    for index, item in enumerate(current):
        proposed_item = proposed[index]

        if not isinstance(item, dict) or not isinstance(proposed_item, dict):
            return False

        title = _clean_string(proposed_item.get("title"), 180)
        impact = _clean_string(proposed_item.get("impact"), 700)

        if title:
            item["title"] = title
            changed = True

        if impact:
            item["impact"] = impact
            changed = True

    return changed


def _apply_candidate_wording(report: Dict[str, Any], candidate: Dict[str, Any]) -> bool:
    changed = _apply_primary_risk(report, candidate)

    for field in _STRING_LIST_FIELDS:
        changed = _apply_string_list(report, field, candidate) or changed

    for field in _RISK_LIST_FIELDS:
        changed = _apply_risk_list(report, field, candidate) or changed

    return changed


# ---------------------------------------------------------------------------
# Multi-Document Prompt / Guarded Application
# ---------------------------------------------------------------------------

def _build_compare_wording_prompt(compare_packet: Dict[str, Any]) -> str:
    locked_context = {
        "documents": compare_packet.get("documents"),
        "pricing_position": compare_packet.get("pricing_position"),
        "deterministic_draft": {
            "comparison_summary": compare_packet.get("comparison_summary"),
            "qualification_summary": compare_packet.get("qualification_summary"),
            "review_notes": compare_packet.get("review_notes"),
            "overall": compare_packet.get("overall"),
        },
    }

    return (
        "You are SolomonAI's guarded bid comparison wording editor.\n"
        "The bid comparison facts are already locked. Your job is to improve the "
        "customer-facing wording only.\n\n"
        "Rules:\n"
        "1. Return JSON only.\n"
        "2. Do not add or remove documents.\n"
        "3. Do not change bidder names, prices, spread, percentages, counts, exclusions, clarifications, notes, or qualifications.\n"
        "4. Do not infer missing exclusions, clarifications, alternates, allowances, or scope.\n"
        "5. Do not say a bid is complete, safe, compliant, lowest responsible, or award-ready.\n"
        "6. Rewrite raw evidence strings into concise construction-estimator prose.\n"
        "7. If a document has no extracted qualifications, say that no qualifications were extracted for that document; do not invent any.\n"
        "8. Use short paragraphs or concise list items. Avoid semicolon-heavy evidence dumps.\n"
        "9. Do not mention LLMs, prompts, deterministic logic, or internal systems.\n\n"
        "Return exactly this JSON shape:\n"
        "{"
        '"comparison_summary":["string"],'
        '"qualification_summary":["string"],'
        '"review_notes":["string"],'
        '"overall":"string"'
        "}\n\n"
        "Writing target:\n"
        "- comparison_summary: 1-2 estimator-style sentences about pricing position.\n"
        "- qualification_summary: one concise item per document, focused on what must be reconciled.\n"
        "- review_notes: 1-3 concise reminders for bid leveling.\n"
        "- overall: one concise paragraph.\n\n"
        f"LOCKED_CONTEXT:\n{json.dumps(locked_context, ensure_ascii=False)}"
    )


def _compare_candidate_has_required_shape(candidate: Dict[str, Any]) -> bool:
    if not isinstance(candidate, dict):
        return False

    summary = _clean_string_list(candidate.get("comparison_summary"), 4, 700)
    qualifications = _clean_string_list(candidate.get("qualification_summary"), 6, 900)
    notes = _clean_string_list(candidate.get("review_notes"), 4, 700)
    overall = _clean_string(candidate.get("overall"), 900)

    return bool(summary and qualifications and notes and overall)


def _compare_candidate_preserves_documents(
    candidate: Dict[str, Any],
    locked_packet: Dict[str, Any],
) -> bool:
    names = _document_names(locked_packet)

    if not names:
        return True

    candidate_text = json.dumps(candidate, ensure_ascii=False)

    for name in names:
        if name not in candidate_text:
            logger.warning("[BEI_COMPARE_WORDING][MISSING_DOCUMENT_NAME] %s", name)
            return False

    return True


def _compare_candidate_is_safe(
    candidate: Dict[str, Any],
    locked_packet: Dict[str, Any],
) -> bool:
    if not _compare_candidate_has_required_shape(candidate):
        logger.warning("[BEI_COMPARE_WORDING][BAD_SHAPE]")
        return False

    if not _compare_candidate_preserves_documents(candidate, locked_packet):
        return False

    candidate_tokens = _locked_tokens(candidate)
    allowed_tokens = _locked_tokens(locked_packet)

    if candidate_tokens - allowed_tokens:
        logger.warning(
            "[BEI_COMPARE_WORDING][UNSUPPORTED_TOKENS] %s",
            sorted(candidate_tokens - allowed_tokens),
        )
        return False

    return True


def _apply_compare_candidate(
    compare_packet: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Dict[str, Any]:
    worded = deepcopy(compare_packet)

    summary = _clean_string_list(candidate.get("comparison_summary"), 4, 700)
    qualifications = _clean_string_list(candidate.get("qualification_summary"), 6, 900)
    notes = _clean_string_list(candidate.get("review_notes"), 4, 700)
    overall = _clean_string(candidate.get("overall"), 900)

    if summary:
        worded["comparison_summary"] = summary

    if qualifications:
        worded["qualification_summary"] = qualifications

    if notes:
        worded["review_notes"] = notes

    if overall:
        worded["overall"] = overall

    worded["wording"] = _metadata("llm_guarded", "applied")
    logger.info("[BEI_COMPARE_WORDING][APPLIED]")
    return worded


# ---------------------------------------------------------------------------
# LLM Execution Helper
# ---------------------------------------------------------------------------

def _execute_wording_prompt(prompt: str) -> str:
    packet = LLMExecutionInput(
        user_query=prompt,
        context=None,
        mode=LLMExecutionMode.INFORMATIONAL_ONLY,
        response_format=LLMResponseFormat.JSON_OBJECT,
    )

    result = execute_llm(packet)

    if result is None:
        raise ValueError("LLM returned None")

    if getattr(result, "failure", None):
        reason = getattr(result.failure, "reason", "unknown")
        raise ValueError(f"LLM failed: {reason}")

    output = getattr(result, "output", None)
    return getattr(output, "text", "") if output else ""


# ---------------------------------------------------------------------------
# Public Entries
# ---------------------------------------------------------------------------

def word_bei_report(report: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(report, dict):
        return report

    worded_report = deepcopy(report)

    try:
        model_text = _execute_wording_prompt(_build_wording_prompt(report))
        candidate = _extract_json_object(model_text, _ALLOWED_TOP_LEVEL_FIELDS)

        if not candidate:
            logger.warning("[BEI_WORDING][INVALID_JSON] model_chars=%s", len(model_text or ""))
            worded_report["wording"] = _metadata("deterministic_fallback", "llm_invalid_json")
            return worded_report

        changed = _apply_candidate_wording(worded_report, candidate)
        worded_report["wording"] = (
            _metadata("llm_guarded", "applied")
            if changed
            else _metadata("deterministic_fallback", "no_approved_changes")
        )
        return worded_report

    except Exception as exc:
        logger.warning("[BEI_WORDING][FALLBACK] %s", exc)
        worded_report["wording"] = _metadata("deterministic_fallback", "llm_exception")
        return worded_report


def word_bei_compare(compare_packet: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(compare_packet, dict):
        return compare_packet

    fallback = deepcopy(compare_packet)
    fallback["wording"] = _metadata("deterministic_fallback", "not_applied")

    try:
        prompt = _build_compare_wording_prompt(compare_packet)
        model_text = _execute_wording_prompt(prompt)
        candidate = _extract_json_object(model_text, _COMPARE_ALLOWED_FIELDS)

        if not candidate:
            logger.warning(
                "[BEI_COMPARE_WORDING][INVALID_JSON] model_chars=%s",
                len(model_text or ""),
            )
            fallback["wording"] = _metadata("deterministic_fallback", "llm_invalid_json")
            return fallback

        if not _compare_candidate_is_safe(candidate, compare_packet):
            fallback["wording"] = _metadata("deterministic_fallback", "llm_rejected")
            return fallback

        return _apply_compare_candidate(compare_packet, candidate)

    except Exception as exc:
        logger.warning("[BEI_COMPARE_WORDING][FALLBACK] %s", exc)
        fallback["wording"] = _metadata("deterministic_fallback", "llm_exception")
        return fallback
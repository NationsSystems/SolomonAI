# -------------------------------------------------------------
# FILE: workspace_artifact_context.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------
# Workspace Artifact Context Helpers
#
# PURPOSE
#   Load compact, backend-owned artifact facts for Workspace-Aware SolomonAI.
#
# CONTRACT
#   - Transport callers may attach bounded context, not routing authority.
#   - Browser workspace hints identify the active artifact, but are not proof.
#   - Records are loaded only through authenticated user ownership.
#   - Full report HTML is never injected blindly into Assistant prompts.
# -------------------------------------------------------------

from dataclasses import replace
from html import unescape
import json
import re

from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger
from solomon_core.models import BidReviewRecord

logger = get_logger("workspace_artifact_context")

_ARTIFACT_CONTEXT_SCHEMA = "solomon_workspace_artifact_context_v1"
_MAX_TITLE_CHARS = 220
_MAX_DOCUMENT_CHARS = 420
_MAX_SUMMARY_CHARS = 1800
_MAX_FACT_CHARS = 900

BID_SCOPE_REVIEW_RECORD_KIND = "bid_scope_review"
BID_SCOPE_REVIEW_REPORT_RECORD_KIND = "bid_scope_review_report"
DOCUMENT_ANALYSIS_RECORD_KIND = "document_analysis"
DOCUMENT_ANALYSIS_REPORT_RECORD_KIND = "document_analysis_report"

_SUPPORTED_RECORD_KINDS = {
    BID_SCOPE_REVIEW_RECORD_KIND,
    BID_SCOPE_REVIEW_REPORT_RECORD_KIND,
    DOCUMENT_ANALYSIS_RECORD_KIND,
    DOCUMENT_ANALYSIS_REPORT_RECORD_KIND,
}

_PUBLIC_RECORD_KIND_BY_INTERNAL_KIND = {
    BID_SCOPE_REVIEW_RECORD_KIND: DOCUMENT_ANALYSIS_RECORD_KIND,
    BID_SCOPE_REVIEW_REPORT_RECORD_KIND: DOCUMENT_ANALYSIS_REPORT_RECORD_KIND,
}


def _legacy_completeness_column_name():
    return "_".join(("scope", "completeness"))


def _clean_string(value, fallback="", max_chars=240):
    if not isinstance(value, str):
        return fallback

    return value.strip()[:max_chars]


def _clean_fact_text(value, max_chars=180):
    text = _clean_string(value, "", max_chars)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def _safe_json_loads(value):
    if not isinstance(value, str) or not value.strip():
        return None

    try:
        return json.loads(value)
    except Exception:
        return None


def _record_id_from_workspace(workspace_context):
    if not isinstance(workspace_context, dict):
        return None

    raw_value = (
        workspace_context.get("active_record_id")
        or workspace_context.get("review_id")
    )

    try:
        record_id = int(str(raw_value).strip())
    except Exception:
        return None

    return record_id if record_id > 0 else None


def _record_kind_from_workspace(workspace_context):
    if not isinstance(workspace_context, dict):
        return ""

    return _clean_string(
        workspace_context.get("active_record_kind"),
        "",
        120,
    ).lower()


def _public_record_kind(record_kind):
    clean_record_kind = _clean_string(record_kind, "", 120).lower()

    return (
        _PUBLIC_RECORD_KIND_BY_INTERNAL_KIND.get(
            clean_record_kind,
            clean_record_kind,
        )
        or DOCUMENT_ANALYSIS_RECORD_KIND
    )


def _html_to_text(value):
    if not isinstance(value, str) or not value.strip():
        return ""

    text = value
    text = re.sub(r"(?is)<\s*li[^>]*>", "\n- ", text)
    text = re.sub(r"(?is)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?is)</\s*(p|div|li|ul|ol|h[1-6])\s*>", "\n", text)
    text = re.sub(r"(?is)<[^>]+>", " ", text)
    text = unescape(text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def _limit_text(value, max_chars):
    text = _clean_string(value, "", max_chars + 1)

    if len(text) <= max_chars:
        return text

    return text[:max_chars].rsplit(" ", 1)[0].rstrip() + "..."


def _document_names_from_record(record):
    parsed = _safe_json_loads(record.document_names)

    if isinstance(parsed, list):
        names = [
            _clean_string(name, "", 160)
            for name in parsed
            if isinstance(name, str) and name.strip()
        ]
        return ", ".join(names)[:_MAX_DOCUMENT_CHARS]

    return _clean_string(record.document_names, "", _MAX_DOCUMENT_CHARS)


def _payload_from_structured_payload(record):
    parsed = _safe_json_loads(record.structured_payload)

    if not isinstance(parsed, dict):
        return {}

    payload = parsed.get("payload")
    return payload if isinstance(payload, dict) else {}


def _format_fact_key(value):
    label = str(value or "").strip().replace("_", " ")
    return label[:1].upper() + label[1:] if label else ""


def _compact_value(value, max_chars=180):
    if isinstance(value, str):
        return _limit_text(value, max_chars)

    if isinstance(value, (int, float, bool)):
        return str(value)

    if isinstance(value, list):
        items = [
            _compact_value(item, 80)
            for item in value[:6]
            if item is not None
        ]
        return "; ".join(item for item in items if item)[:max_chars]

    return ""


def _iter_payload_facts(payload):
    if not isinstance(payload, dict):
        return

    excluded_keys = {
        "answer",
        "bridge",
        "suggestions",
        "type",
        "report_html",
        "rendered_report",
        "output",
    }

    for key, value in payload.items():
        clean_key = str(key or "").strip()

        if not clean_key or clean_key in excluded_keys:
            continue

        if isinstance(value, dict):
            for child_key, child_value in value.items():
                clean_child_key = str(child_key or "").strip()

                if not clean_child_key or clean_child_key in excluded_keys:
                    continue

                compact = _compact_value(child_value)

                if compact:
                    yield f"{_format_fact_key(clean_child_key)}: {compact}"

            continue

        compact = _compact_value(value)

        if compact:
            yield f"{_format_fact_key(clean_key)}: {compact}"


def _payload_fact_summary(payload):
    facts = []

    for fact in _iter_payload_facts(payload):
        cleaned = _clean_fact_text(fact, 240)

        if cleaned and cleaned not in facts:
            facts.append(cleaned)

        if len(facts) >= 10:
            break

    return _limit_text("; ".join(facts), _MAX_FACT_CHARS)


def _record_completeness(record):
    return _clean_string(
        getattr(
            record,
            _legacy_completeness_column_name(),
            "",
        ),
        "",
        80,
    )


def _artifact_context_from_record(record, record_kind, record_id):
    payload = _payload_from_structured_payload(record)
    report_text = _html_to_text(record.report_html or payload.get("answer") or "")
    completeness = _record_completeness(record)

    return {
        "schema": _ARTIFACT_CONTEXT_SCHEMA,
        "source": "backend_saved_record",
        "record_kind": record_kind,
        "public_record_kind": _public_record_kind(record_kind),
        "internal_record_kind": BID_SCOPE_REVIEW_RECORD_KIND,
        "record_id": str(record_id),
        "title": _clean_string(record.review_title, "", _MAX_TITLE_CHARS),
        "review_mode": _clean_string(record.review_mode, "", 80),
        "documents": _document_names_from_record(record),
        "risk_level": _clean_string(record.risk_level, "", 80),
        "scope_completeness": completeness,
        "completeness": completeness,
        "fact_summary": _payload_fact_summary(payload),
        "report_summary": _limit_text(report_text, _MAX_SUMMARY_CHARS),
    }


def _attach_artifact_context(casefile, artifact_context):
    if casefile is None or not isinstance(artifact_context, dict):
        return casefile

    current_snapshot = getattr(casefile, "intent_snapshot", None)
    if not isinstance(current_snapshot, dict):
        current_snapshot = {}

    next_snapshot = {
        **current_snapshot,
        "workspace_artifact_context": artifact_context,
    }

    try:
        return replace(casefile, intent_snapshot=next_snapshot)
    except Exception:
        logger.warning("[API][WORKSPACE_ARTIFACT_ATTACH_FAILED]")
        return casefile


def _attach_workspace_artifact_context(
    *,
    casefile,
    workspace_context,
    current_user,
    request_id,
):
    record_id = _record_id_from_workspace(workspace_context)
    record_kind = _record_kind_from_workspace(workspace_context)

    if not record_id or not record_kind:
        return casefile

    if record_kind not in _SUPPORTED_RECORD_KINDS:
        return casefile

    if not current_user:
        return casefile

    db = SessionLocal()

    try:
        record = (
            db.query(BidReviewRecord)
            .filter(
                BidReviewRecord.id == record_id,
                BidReviewRecord.user_id == int(current_user),
                BidReviewRecord.deleted_at.is_(None),
            )
            .first()
        )

        if not record:
            logger.info(
                "[API][WORKSPACE_ARTIFACT_NOT_FOUND] request_id=%s kind=%s id=%s",
                request_id,
                record_kind,
                record_id,
            )
            return casefile

        artifact_context = _artifact_context_from_record(
            record=record,
            record_kind=record_kind,
            record_id=record_id,
        )

        logger.info(
            "[API][WORKSPACE_ARTIFACT_ATTACHED] request_id=%s kind=%s id=%s chars=%s",
            request_id,
            record_kind,
            record_id,
            len(artifact_context.get("report_summary") or ""),
        )

        return _attach_artifact_context(casefile, artifact_context)

    except Exception:
        logger.exception(
            "[API][WORKSPACE_ARTIFACT_LOAD_FAILED] request_id=%s kind=%s id=%s",
            request_id,
            record_kind,
            record_id,
        )
        return casefile

    finally:
        db.close()
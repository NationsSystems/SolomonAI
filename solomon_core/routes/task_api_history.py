# -------------------------------------------------------------
# FILE: task_api_history.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------
# Bid Review History Helpers
#
# PURPOSE
#   Persist completed BEI review records without bloating the API
#   transport route.
# -------------------------------------------------------------

from datetime import datetime
import json

from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger
from solomon_core.models import BidReviewRecord

logger = get_logger("task_api_history")

BID_SCOPE_REVIEW_OPERATION_KEY = "bid_scope_review"
DOCUMENT_ANALYSIS_OPERATION_KEY = "document_analysis"
DOCUMENT_REVIEW_COMPATIBILITY_KEY = "document_review"
BID_SCOPE_REVIEW_LABEL = "Document Analysis"
BID_REVIEW_HISTORY_VERSION = "docintel-bei-v1"
BID_REVIEW_SAVE_KEYS = frozenset({
    BID_SCOPE_REVIEW_OPERATION_KEY,
    DOCUMENT_ANALYSIS_OPERATION_KEY,
    DOCUMENT_REVIEW_COMPATIBILITY_KEY,
})


def _json_dumps(value):
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _clean_key(value):
    return str(value or "").strip().lower()


def _document_name_list_from_context(execution_context):
    docs = execution_context.get("docs") or []
    names = []

    if not isinstance(docs, list):
        return names

    for doc in docs:
        if not isinstance(doc, dict):
            continue

        name = (
            doc.get("original_name")
            or doc.get("display_name")
            or doc.get("document_id")
            or doc.get("random_name")
        )

        if isinstance(name, str) and name.strip() and name.strip() not in names:
            names.append(name.strip())

    return names


def _document_names_display(document_names):
    if not isinstance(document_names, list):
        return ""

    return ", ".join(
        name for name in document_names
        if isinstance(name, str) and name.strip()
    )


def _build_review_title(document_names_display, document_count):
    if document_count == 1 and document_names_display:
        return f"{BID_SCOPE_REVIEW_LABEL} — {document_names_display[:200]}"

    if document_count > 1:
        return f"{BID_SCOPE_REVIEW_LABEL} — {document_count} Documents"

    return BID_SCOPE_REVIEW_LABEL


def _extract_optional_payload_value(payload, *keys):
    for key in keys:
        value = payload.get(key)

        if isinstance(value, str) and value.strip():
            return value.strip()[:64]

    return None


def _should_save_bid_review(response, execution_context):
    if response.get("packet_type") not in {"docintel", "bei"}:
        return False

    payload = response.get("payload")
    if not isinstance(payload, dict):
        return False

    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        return False

    workflow_context = execution_context.get("workflow_context") or {}

    candidates = (
        response.get("operation"),
        response.get("operation_key"),
        payload.get("operation"),
        payload.get("operation_key"),
        payload.get("report_kind"),
        workflow_context.get("workflow_id"),
        execution_context.get("operation"),
    )

    return any(
        _clean_key(value) in BID_REVIEW_SAVE_KEYS
        for value in candidates
    )


def _save_bid_review_history(response, execution_context):
    if not _should_save_bid_review(response, execution_context):
        return None

    payload = response.get("payload") or {}
    docs = execution_context.get("docs") or []
    document_count = len(docs) if isinstance(docs, list) else 0
    document_names = _document_name_list_from_context(execution_context)
    document_names_display = _document_names_display(document_names)
    review_title = _build_review_title(document_names_display, document_count)

    structured_payload = {
        "request_id": execution_context.get("request_id"),
        "conversation_id": execution_context.get("conversation_id"),
        "packet_type": response.get("packet_type"),
        "payload": payload,
        "documents": docs,
        "document_names": document_names,
        "workflow_context": execution_context.get("workflow_context"),
        "command_context": execution_context.get("command_context"),
        "workspace_context": execution_context.get("workspace_context"),
        "case_id": getattr(execution_context.get("casefile"), "case_id", None),
        "saved_at": datetime.utcnow().isoformat(),
    }

    db = SessionLocal()

    try:
        record = BidReviewRecord(
            user_id=execution_context.get("user_id"),
            review_title=review_title,
            review_mode="multi_document" if document_count > 1 else "single_document",
            document_names=_json_dumps(document_names),
            scope_completeness=_extract_optional_payload_value(
                payload,
                "scope_completeness",
                "scopeCompleteness",
                "scope_status",
                "completeness",
                "document_completeness",
            ),
            risk_level=_extract_optional_payload_value(
                payload,
                "risk_level",
                "riskLevel",
                "risk",
            ),
            report_html=payload.get("answer") or "",
            structured_payload=_json_dumps(structured_payload),
            status="completed",
            analysis_version=BID_REVIEW_HISTORY_VERSION,
        )

        db.add(record)
        db.commit()
        db.refresh(record)

        logger.info(
            "[API][HISTORY_SAVED] request_id=%s review_id=%s",
            execution_context.get("request_id"),
            record.id,
        )

        return record.id

    except Exception:
        db.rollback()
        logger.exception(
            "[API][HISTORY_SAVE_FAILED] request_id=%s",
            execution_context.get("request_id"),
        )
        return None

    finally:
        db.close()


def _should_save_document_analysis_history(response, execution_context):
    return _should_save_bid_review(
        response,
        execution_context,
    )


def _save_document_analysis_history(response, execution_context):
    return _save_bid_review_history(
        response,
        execution_context,
    )
# -------------------------------------------------------------------
# FILE: saved_reviews.py
# DIRECTORY: solomon_core/document_operations/
# -------------------------------------------------------------------
# Database-backed V3 workspace artifact persistence.
#
# Governed execution produces the result. This module saves completed
# document operation reviews into the generic WorkspaceArtifact schema
# so Solomon can support many report types without one table per report.
# -------------------------------------------------------------------

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from html import unescape
from typing import Any
import re

from solomon_core.db import SessionLocal
from solomon_core.logger import get_logger
from solomon_core.models import (
    WorkspaceArtifact,
    WorkspaceArtifactAuditPayload,
    WorkspaceArtifactFinding,
    WorkspaceArtifactSection,
    WorkspaceArtifactSource,
)

logger = get_logger("saved_document_reviews")

BID_SCOPE_REVIEW_OPERATION_KEY = "bid_scope_review"
DOCUMENT_ANALYSIS_OPERATION_KEY = "document_analysis"
DOCUMENT_REVIEW_COMPATIBILITY_KEY = "document_review"
BEI_WORKFLOW_OPERATION_KEY = "pre_award_risk_review"

DOCUMENT_ANALYSIS_LABEL = "Document Analysis"
SAVED_REVIEW_STATUS = "completed"
SAVED_REVIEW_ANALYSIS_VERSION = "workspace_artifact_bid_scope_review_1"

SAVED_REVIEW_OPERATION_KEYS = frozenset({
    BID_SCOPE_REVIEW_OPERATION_KEY,
    DOCUMENT_ANALYSIS_OPERATION_KEY,
    DOCUMENT_REVIEW_COMPATIBILITY_KEY,
    BEI_WORKFLOW_OPERATION_KEY,
})

PUBLIC_OPERATION_KEY_BY_INTERNAL_KEY = {
    BID_SCOPE_REVIEW_OPERATION_KEY: DOCUMENT_ANALYSIS_OPERATION_KEY,
    BEI_WORKFLOW_OPERATION_KEY: DOCUMENT_ANALYSIS_OPERATION_KEY,
    DOCUMENT_REVIEW_COMPATIBILITY_KEY: DOCUMENT_ANALYSIS_OPERATION_KEY,
}

_HTML_BREAK_RE = re.compile(r"(?i)<\s*br\s*/?\s*>")
_HTML_BLOCK_RE = re.compile(r"(?i)</\s*(?:div|p|section|article|li|tr|h[1-6])\s*>")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def safe_string(value: Any) -> str:
    """Return a stripped display string."""

    return str(value or "").strip()


def normalize_key(value: Any) -> str:
    """Return a normalized lowercase key string."""

    return safe_string(value).lower()


def legacy_completeness_column_name() -> str:
    """Return the existing database column name for review completeness."""

    return "_".join(("scope", "completeness"))


def legacy_completeness_payload_key() -> str:
    """Return the prior packet key accepted for compatibility."""

    return "_".join(("scope", "completeness"))


def legacy_status_payload_key() -> str:
    """Return the prior status packet key accepted for compatibility."""

    return "_".join(("scope", "status"))


def html_to_text(value: Any) -> str:
    """Return readable text from lightweight HTML or plain text."""

    text = safe_string(value)

    if not text:
        return ""

    text = _HTML_BREAK_RE.sub("\n", text)
    text = _HTML_BLOCK_RE.sub("\n", text)
    text = _HTML_TAG_RE.sub("", text)
    text = unescape(text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def nested_value(source: Any, path: str):
    """Read a dotted path from a nested dictionary."""

    current = source

    for key in safe_string(path).split("."):
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def first_nested_value(source: dict, paths: tuple[str, ...]):
    """Return the first non-empty value from a list of dotted paths."""

    for path in paths:
        value = nested_value(source, path)

        if value not in (None, "", [], {}):
            return value

    return None


def json_safe_payload(value: Any):
    """Return a JSON-column-safe copy of a payload."""

    if isinstance(value, dict):
        return {
            safe_string(key): json_safe_payload(item)
            for key, item in value.items()
        }

    if isinstance(value, list):
        return [json_safe_payload(item) for item in value]

    if isinstance(value, tuple):
        return [json_safe_payload(item) for item in value]

    if isinstance(value, (str, int, float, bool)) or value is None:
        return value

    return safe_string(value)


def saved_review_storage_key(value: Any) -> str:
    """Return the internal saved-review storage contract key."""

    clean_value = normalize_key(value)

    if clean_value in SAVED_REVIEW_OPERATION_KEYS:
        return BID_SCOPE_REVIEW_OPERATION_KEY

    return clean_value


def public_operation_key(value: Any) -> str:
    """Return the browser-facing operation key for a saved review payload."""

    clean_value = normalize_key(value)

    return (
        PUBLIC_OPERATION_KEY_BY_INTERNAL_KEY.get(
            clean_value,
            clean_value,
        )
        or DOCUMENT_ANALYSIS_OPERATION_KEY
    )


def saved_review_candidate_keys(job, result_packet: dict) -> tuple[str, ...]:
    """Return operation/report keys that may identify a savable review."""

    payload = (
        result_packet.get("payload")
        if isinstance(result_packet.get("payload"), dict)
        else {}
    )
    workflow_response = (
        result_packet.get("workflow_response")
        if isinstance(result_packet.get("workflow_response"), dict)
        else {}
    )
    workflow_payload = (
        workflow_response.get("payload")
        if isinstance(workflow_response.get("payload"), dict)
        else {}
    )

    candidates = (
        getattr(job, "operation_key", ""),
        getattr(job, "operation", ""),
        getattr(job, "workflow_id", ""),
        result_packet.get("operation"),
        result_packet.get("operation_key"),
        result_packet.get("report_kind"),
        payload.get("operation"),
        payload.get("operation_key"),
        payload.get("report_kind"),
        workflow_response.get("operation"),
        workflow_response.get("operation_key"),
        workflow_response.get("report_kind"),
        workflow_payload.get("operation"),
        workflow_payload.get("operation_key"),
        workflow_payload.get("report_kind"),
    )

    return tuple(
        normalize_key(value)
        for value in candidates
        if normalize_key(value)
    )


def resolve_saved_review_storage_key(job, result_packet: dict) -> str:
    """Return the internal key used to persist this saved review."""

    for candidate in saved_review_candidate_keys(job, result_packet):
        if candidate in SAVED_REVIEW_OPERATION_KEYS:
            return saved_review_storage_key(candidate)

    return ""


def compatible_report_type_keys(operation_key: str) -> tuple[str, ...]:
    """Return report-type keys that may already exist for the same job."""

    clean_operation_key = normalize_key(operation_key)

    if clean_operation_key in SAVED_REVIEW_OPERATION_KEYS:
        return (
            BID_SCOPE_REVIEW_OPERATION_KEY,
            DOCUMENT_ANALYSIS_OPERATION_KEY,
            DOCUMENT_REVIEW_COMPATIBILITY_KEY,
            BEI_WORKFLOW_OPERATION_KEY,
        )

    if not clean_operation_key:
        return (
            BID_SCOPE_REVIEW_OPERATION_KEY,
            DOCUMENT_ANALYSIS_OPERATION_KEY,
        )

    return (clean_operation_key,)


def should_save_review(job, result_packet: dict) -> bool:
    """Return whether a completed operation should be saved as an artifact."""

    if not job or not isinstance(result_packet, dict):
        return False

    storage_key = resolve_saved_review_storage_key(job, result_packet)

    if not storage_key:
        return False

    status = normalize_key(result_packet.get("status"))
    ok = result_packet.get("ok")

    return status == "complete" and ok is not False


def document_display_name(document: dict) -> str:
    """Return the best available display name for a source document."""

    if not isinstance(document, dict):
        return ""

    return safe_string(
        document.get("original_name")
        or document.get("filename")
        or document.get("display_name")
        or document.get("document_id")
        or document.get("random_name")
        or document.get("file_id")
    )


def document_identifier(document: dict) -> str:
    """Return the best available stable identifier for a source document."""

    if not isinstance(document, dict):
        return ""

    return safe_string(
        document.get("document_id")
        or document.get("random_name")
        or document.get("file_id")
    )


def file_registry_id(document: dict):
    """Return a numeric FileRegistry id when available."""

    if not isinstance(document, dict):
        return None

    file_id = safe_string(document.get("file_id"))

    if file_id.isdigit():
        return int(file_id)

    return None


def extract_summary(result_packet: dict) -> str:
    """Return the best available artifact summary."""

    value = first_nested_value(
        result_packet,
        (
            "result.summary",
            "workflow_response.payload.summary",
            "workflow_response.payload.bridge",
            "workflow_response.payload.answer",
            "workflow_response.summary",
            "workflow_response.user_output",
        ),
    )

    if isinstance(value, (dict, list)):
        return safe_string(value)

    return html_to_text(value)


def extract_report_body(result_packet: dict) -> str:
    """Return the best available rendered report body."""

    value = first_nested_value(
        result_packet,
        (
            "workflow_response.payload.rendered_report",
            "workflow_response.payload.report_html",
            "workflow_response.payload.report",
            "workflow_response.payload.answer",
            "workflow_response.report_html",
            "workflow_response.report",
            "result.summary",
        ),
    )

    if isinstance(value, (dict, list)):
        return safe_string(value)

    return safe_string(value)


def extract_review_title(job, result_packet: dict) -> str:
    """Return a useful saved-review title."""

    title = first_nested_value(
        result_packet,
        (
            "workflow_response.payload.title",
            "workflow_response.title",
            "result.title",
        ),
    )

    if safe_string(title):
        return safe_string(title)

    operation_label = safe_string(getattr(job, "operation_label", ""))

    return operation_label or DOCUMENT_ANALYSIS_LABEL


def extract_risk_level(result_packet: dict) -> str:
    """Return the best available risk level."""

    value = first_nested_value(
        result_packet,
        (
            "workflow_response.payload.risk_level",
            "workflow_response.payload.risk",
            "workflow_response.risk_level",
            "workflow_response.risk",
            "result.risk_level",
        ),
    )

    return safe_string(value)


def extract_completeness(result_packet: dict) -> str:
    """Return the best available document completeness label."""

    prior_completeness_key = legacy_completeness_payload_key()
    prior_status_key = legacy_status_payload_key()

    value = first_nested_value(
        result_packet,
        (
            "workflow_response.payload.completeness",
            "workflow_response.payload.document_completeness",
            f"workflow_response.payload.{prior_completeness_key}",
            f"workflow_response.payload.{prior_status_key}",
            "workflow_response.completeness",
            "workflow_response.document_completeness",
            f"workflow_response.{prior_completeness_key}",
            f"workflow_response.{prior_status_key}",
            "result.completeness",
            "result.document_completeness",
            f"result.{prior_completeness_key}",
        ),
    )

    return safe_string(value)


def extract_confidence_level(result_packet: dict) -> str:
    """Return the best available confidence label."""

    value = first_nested_value(
        result_packet,
        (
            "workflow_response.payload.confidence_level",
            "workflow_response.payload.confidence",
            "workflow_response.confidence_level",
            "workflow_response.confidence",
            "result.confidence_level",
        ),
    )

    return safe_string(value)


def extract_section_candidates(result_packet: dict) -> list:
    """Return section-like payloads from common response shapes."""

    candidates = first_nested_value(
        result_packet,
        (
            "workflow_response.payload.sections",
            "workflow_response.sections",
            "result.sections",
        ),
    )

    if isinstance(candidates, list):
        return candidates

    return []


def extract_finding_candidates(result_packet: dict) -> list:
    """Return finding-like payloads from common response shapes."""

    for path in (
        "workflow_response.payload.findings",
        "workflow_response.payload.risk_signals",
        "workflow_response.payload.risks",
        "workflow_response.payload.issues",
        "workflow_response.findings",
        "result.findings",
    ):
        value = nested_value(result_packet, path)

        if isinstance(value, list):
            return value

    return []


def build_source_rows(job) -> list[WorkspaceArtifactSource]:
    """Build source rows from operation documents."""

    rows = []
    seen = set()

    for index, document in enumerate(getattr(job, "documents", []) or []):
        if not isinstance(document, dict):
            continue

        source_document_id = document_identifier(document)
        source_name = document_display_name(document)

        if not source_document_id and not source_name:
            continue

        dedupe_key = source_document_id or source_name

        if dedupe_key in seen:
            continue

        seen.add(dedupe_key)

        rows.append(
            WorkspaceArtifactSource(
                file_registry_id=file_registry_id(document),
                source_document_id=source_document_id or None,
                source_name=source_name or source_document_id,
                source_type="document",
                source_order=index,
            )
        )

    return rows


def build_section_rows(result_packet: dict) -> list[WorkspaceArtifactSection]:
    """Build normalized report sections."""

    rows = []

    for index, section in enumerate(extract_section_candidates(result_packet)):
        if isinstance(section, dict):
            section_key = safe_string(
                section.get("section_key")
                or section.get("key")
                or section.get("id")
            )
            title = safe_string(
                section.get("section_title")
                or section.get("title")
                or section_key
                or f"Section {index + 1}"
            )
            body_html = safe_string(
                section.get("body_html")
                or section.get("html")
                or section.get("body")
                or section.get("content")
                or section.get("text")
            )
            body_text = safe_string(
                section.get("body_text")
                or section.get("text")
                or html_to_text(body_html)
            )
        else:
            section_key = f"section_{index + 1}"
            title = f"Section {index + 1}"
            body_html = safe_string(section)
            body_text = html_to_text(body_html)

        if not body_html and not body_text:
            continue

        rows.append(
            WorkspaceArtifactSection(
                section_key=section_key or None,
                section_title=title,
                section_order=index,
                body_html=body_html or None,
                body_text=body_text or None,
            )
        )

    if rows:
        return rows

    report_body = extract_report_body(result_packet)
    summary = extract_summary(result_packet)

    if not report_body and not summary:
        return []

    return [
        WorkspaceArtifactSection(
            section_key="report",
            section_title="Report",
            section_order=0,
            body_html=report_body or None,
            body_text=html_to_text(report_body or summary) or None,
        )
    ]


def build_finding_rows(result_packet: dict) -> list[WorkspaceArtifactFinding]:
    """Build normalized findings from common response shapes."""

    rows = []

    for index, finding in enumerate(extract_finding_candidates(result_packet)):
        if isinstance(finding, dict):
            title = safe_string(
                finding.get("title")
                or finding.get("label")
                or finding.get("name")
                or f"Finding {index + 1}"
            )
            finding_text = safe_string(
                finding.get("finding_text")
                or finding.get("text")
                or finding.get("summary")
                or finding.get("description")
                or finding.get("body")
            )
            recommendation = safe_string(
                finding.get("recommendation")
                or finding.get("recommended_action")
                or finding.get("action")
            )
            severity = safe_string(
                finding.get("severity")
                or finding.get("risk_level")
                or finding.get("risk")
            )
            finding_type = safe_string(
                finding.get("finding_type")
                or finding.get("type")
                or finding.get("category")
            )
            source_document_id = safe_string(
                finding.get("source_document_id")
                or finding.get("document_id")
                or finding.get("random_name")
            )
            page_number_value = finding.get("page_number") or finding.get("page")
        else:
            title = f"Finding {index + 1}"
            finding_text = safe_string(finding)
            recommendation = ""
            severity = ""
            finding_type = ""
            source_document_id = ""
            page_number_value = None

        if not title and not finding_text:
            continue

        try:
            page_number = int(page_number_value) if page_number_value else None
        except (TypeError, ValueError):
            page_number = None

        rows.append(
            WorkspaceArtifactFinding(
                finding_type=finding_type or None,
                severity=severity or None,
                title=title or f"Finding {index + 1}",
                finding_text=finding_text or None,
                recommendation=recommendation or None,
                source_document_id=source_document_id or None,
                page_number=page_number,
                sort_order=index,
            )
        )

    return rows


def artifact_completeness(artifact: WorkspaceArtifact) -> str:
    """Return a generic completeness value from the artifact row."""

    return safe_string(
        getattr(
            artifact,
            legacy_completeness_column_name(),
            "",
        )
    )


def artifact_to_payload(artifact: WorkspaceArtifact) -> dict:
    """Return a workspace-safe artifact payload."""

    if not artifact:
        return {}

    completeness = artifact_completeness(artifact)
    operation_key = public_operation_key(
        artifact.operation_key
        or artifact.report_type
    )

    return {
        "ok": True,
        "saved": True,
        "review_id": artifact.id,
        "artifact_id": artifact.id,
        "record_id": artifact.id,
        "artifact_type": artifact.artifact_type,
        "report_type": artifact.report_type,
        "review_title": artifact.title,
        "title": artifact.title,
        "summary": artifact.summary,
        "status": artifact.status,
        "risk_level": artifact.risk_level,
        "completeness": completeness,
        "document_completeness": completeness,
        "confidence_level": artifact.confidence_level,
        "operation_key": operation_key,
        "job_id": artifact.job_id,
        "request_id": artifact.request_id,
        "analysis_version": artifact.analysis_version,
        "created_at": artifact.created_at.isoformat() if artifact.created_at else "",
        "updated_at": artifact.updated_at.isoformat() if artifact.updated_at else "",
        "sources": [
            {
                "source_id": source.id,
                "file_registry_id": source.file_registry_id,
                "source_document_id": source.source_document_id,
                "source_name": source.source_name,
                "source_type": source.source_type,
                "source_order": source.source_order,
            }
            for source in artifact.sources
        ],
        "sections": [
            {
                "section_id": section.id,
                "section_key": section.section_key,
                "section_title": section.section_title,
                "section_order": section.section_order,
                "body_html": section.body_html,
                "body_text": section.body_text,
            }
            for section in artifact.sections
        ],
        "findings": [
            {
                "finding_id": finding.id,
                "finding_type": finding.finding_type,
                "severity": finding.severity,
                "title": finding.title,
                "finding_text": finding.finding_text,
                "recommendation": finding.recommendation,
                "source_document_id": finding.source_document_id,
                "page_number": finding.page_number,
                "sort_order": finding.sort_order,
            }
            for finding in artifact.findings
        ],
    }


def find_existing_artifact(
    db_session,
    user_id: int,
    job_id: str,
    operation_key: str,
):
    """Return an existing artifact for the same operation job."""

    clean_job_id = safe_string(job_id)
    report_type_keys = compatible_report_type_keys(operation_key)

    if not clean_job_id:
        return None

    return (
        db_session.query(WorkspaceArtifact)
        .filter(WorkspaceArtifact.user_id == int(user_id or 0))
        .filter(WorkspaceArtifact.report_type.in_(report_type_keys))
        .filter(WorkspaceArtifact.job_id == clean_job_id)
        .filter(WorkspaceArtifact.deleted_at.is_(None))
        .first()
    )


def load_saved_reviews(user_id: int) -> list[dict]:
    """Return saved review artifacts for one user from SQL."""

    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        return []

    db_session = SessionLocal()

    try:
        artifacts = (
            db_session.query(WorkspaceArtifact)
            .filter(WorkspaceArtifact.user_id == clean_user_id)
            .filter(WorkspaceArtifact.artifact_type == "review")
            .filter(WorkspaceArtifact.deleted_at.is_(None))
            .order_by(WorkspaceArtifact.created_at.desc())
            .all()
        )

        return [artifact_to_payload(artifact) for artifact in artifacts]
    finally:
        db_session.close()


def get_saved_review(user_id: int, review_id: str) -> dict | None:
    """Return one saved review artifact for a user from SQL."""

    clean_user_id = int(user_id or 0)
    clean_review_id = safe_string(review_id)

    if not clean_user_id or not clean_review_id or not clean_review_id.isdigit():
        return None

    db_session = SessionLocal()

    try:
        artifact = (
            db_session.query(WorkspaceArtifact)
            .filter(WorkspaceArtifact.id == int(clean_review_id))
            .filter(WorkspaceArtifact.user_id == clean_user_id)
            .filter(WorkspaceArtifact.artifact_type == "review")
            .filter(WorkspaceArtifact.deleted_at.is_(None))
            .first()
        )

        return artifact_to_payload(artifact) if artifact else None
    finally:
        db_session.close()


def save_document_operation_review(job, result_packet: dict) -> dict:
    """Persist a completed document operation as a WorkspaceArtifact."""

    if not should_save_review(job, result_packet):
        return {
            "ok": False,
            "saved": False,
            "reason": "not_a_completed_review",
        }

    user_id = int(getattr(job, "user_id", 0) or 0)

    if not user_id:
        return {
            "ok": False,
            "saved": False,
            "reason": "missing_user",
        }

    job_id = safe_string(getattr(job, "job_id", ""))
    storage_operation_key = resolve_saved_review_storage_key(
        job,
        result_packet,
    )

    if not storage_operation_key:
        storage_operation_key = saved_review_storage_key(
            getattr(job, "operation_key", "")
        )

    created_at = utc_now()

    db_session = SessionLocal()

    try:
        existing_artifact = find_existing_artifact(
            db_session=db_session,
            user_id=user_id,
            job_id=job_id,
            operation_key=storage_operation_key,
        )

        if existing_artifact:
            return {
                "ok": True,
                "saved": True,
                "review_id": existing_artifact.id,
                "artifact_id": existing_artifact.id,
                "record_id": existing_artifact.id,
                "reason": "already_saved",
            }

        artifact = WorkspaceArtifact(
            user_id=user_id,
            artifact_type="review",
            report_type=storage_operation_key,
            title=extract_review_title(job, result_packet),
            summary=extract_summary(result_packet) or None,
            status=SAVED_REVIEW_STATUS,
            risk_level=extract_risk_level(result_packet) or None,
            confidence_level=extract_confidence_level(result_packet) or None,
            operation_key=storage_operation_key,
            job_id=job_id or None,
            request_id=safe_string(getattr(job, "request_id", "")) or None,
            analysis_version=SAVED_REVIEW_ANALYSIS_VERSION,
            created_at=created_at,
            updated_at=created_at,
        )
        setattr(
            artifact,
            legacy_completeness_column_name(),
            extract_completeness(result_packet) or None,
        )

        artifact.sources.extend(build_source_rows(job))
        artifact.sections.extend(build_section_rows(result_packet))
        artifact.findings.extend(build_finding_rows(result_packet))
        artifact.audit_payloads.append(
            WorkspaceArtifactAuditPayload(
                payload_kind="operation_result_packet",
                payload_json=json_safe_payload(result_packet),
                payload_text=None,
                created_at=created_at,
            )
        )

        db_session.add(artifact)
        db_session.commit()
        db_session.refresh(artifact)

        logger.info(
            "[saved_reviews.artifact_saved] user_id=%s artifact_id=%s report_type=%s job_id=%s",
            user_id,
            artifact.id,
            artifact.report_type,
            job_id,
        )

        return {
            "ok": True,
            "saved": True,
            "review_id": artifact.id,
            "artifact_id": artifact.id,
            "record_id": artifact.id,
        }
    except Exception as exc:
        db_session.rollback()
        logger.warning(
            "[saved_reviews.artifact_save_failed] user_id=%s job_id=%s error=%s",
            user_id,
            job_id,
            exc,
        )

        return {
            "ok": False,
            "saved": False,
            "reason": "artifact_save_failed",
        }
    finally:
        db_session.close()


__all__ = [
    "get_saved_review",
    "load_saved_reviews",
    "save_document_operation_review",
]
# ------------------------------------------------------------------
# FILE: generic_business_source.py
# DIRECTORY: solomon_core/database_connectivity/
# ------------------------------------------------------------------
# Generic business-system source adapter used for structured-data qualification.
#
# Physical relation names are intentionally isolated here. The source adapter
# emits engine-neutral read plans and generic Solomon semantic entities; it does
# not contain SQL Server TOP syntax, MySQL LIMIT syntax, or browser/LLM SQL.
# ------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any, Dict, Optional

from .contracts import (
    ApprovedReadQuery,
    ReadFilter,
    ReadOrder,
    StructuredEvidencePacket,
    StructuredEvidenceRecord,
)


SOURCE_ID = "synthetic_business_fixture"
SOURCE_TYPE = "external_database"

_PROJECT_REF_RE = re.compile(
    r"\bproject\s+(?P<value>[\w][\w _.-]{0,60})",
    re.IGNORECASE,
)
_PARTY_REF_RE = re.compile(
    r"\b(?:vendor|firm|business\s+party|subcontractor)\s+(?P<value>[\w][\w &'’._-]{0,80})",
    re.IGNORECASE,
)
_QUOTED_REF_RE = re.compile(r"['\"](?P<value>[^'\"]{1,96})['\"]")
_COUNT_PHRASE_RE = re.compile(r"\b(?:how\s+many|number\s+of|count)\b", re.IGNORECASE)


def _clean_reference(value: str) -> str:
    clean = " ".join(str(value or "").strip().split())
    clean = re.split(
        r"\b(?:with|that|which|who|where|and|has|have|currently|right\s+now|are|is)\b",
        clean,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0]
    return clean.strip(" .,:;?!")[:96]


def _quoted_reference(task_text: str) -> str:
    quoted = _QUOTED_REF_RE.search(task_text or "")
    return _clean_reference(quoted.group("value")) if quoted else ""


def _project_reference(task_text: str) -> str:
    match = _PROJECT_REF_RE.search(task_text or "")
    if match:
        return _clean_reference(match.group("value"))
    return _quoted_reference(task_text)


def _party_reference(task_text: str) -> str:
    match = _PARTY_REF_RE.search(task_text or "")
    if match:
        return _clean_reference(match.group("value"))
    return _quoted_reference(task_text)


def _token_set(task_text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(task_text or "").lower()))


class GenericBusinessSourceAdapter:
    """Approved semantic operations over a mature-business integration surface."""

    def __init__(self, database_adapter):
        self.database_adapter = database_adapter

    def resolve_operation(self, task_text: str) -> Optional[Dict[str, Any]]:
        text = str(task_text or "")
        tokens = _token_set(text)
        project_ref = _project_reference(text)
        party_ref = _party_reference(text)

        issue_signal = bool(
            tokens & {"issue", "issues", "risk", "risks", "finding", "findings"}
        )
        ball_signal = "ball" in tokens and "court" in tokens
        change_signal = bool(tokens & {"change", "changes", "exposure", "exposures"})
        pending_signal = bool(tokens & {"pending", "unapproved", "approval"})
        ranking_signal = bool(tokens & {"largest", "highest", "rank", "ranking", "top"})
        project_signal = "project" in tokens or "projects" in tokens
        party_signal = bool(tokens & {"vendor", "vendors", "firm", "firms", "subcontractor", "subcontractors"})

        if issue_signal or ball_signal:
            if not project_ref:
                return None
            count_requested = bool(_COUNT_PHRASE_RE.search(text))
            return {
                "operation_id": (
                    "project_issues.open_count_by_project"
                    if count_requested
                    else "project_issues.open_by_project"
                ),
                "semantic_entity": (
                    "ProjectIssueSummary" if count_requested else "ProjectIssue"
                ),
                "project_ref": project_ref,
                "dataset_id": (
                    "project_issue_counts" if count_requested else "project_issues"
                ),
            }

        if change_signal and (pending_signal or ranking_signal) and not project_ref:
            return {
                "operation_id": "change_exposure.pending_ranked",
                "semantic_entity": "ChangeExposure",
                "dataset_id": "pending_change_exposure",
            }

        if change_signal and project_ref:
            return {
                "operation_id": "change_events.by_project",
                "semantic_entity": "ChangeEvent",
                "project_ref": project_ref,
                "dataset_id": "change_events",
            }

        if party_signal and party_ref:
            return {
                "operation_id": "business_party.lookup",
                "semantic_entity": "BusinessParty",
                "party_ref": party_ref,
                "dataset_id": "business_parties",
            }

        if project_signal and project_ref:
            return {
                "operation_id": "project.lookup",
                "semantic_entity": "Project",
                "project_ref": project_ref,
                "dataset_id": "projects",
            }

        return None

    def _approved_query(self, operation: Dict[str, Any]) -> ApprovedReadQuery:
        operation_id = str(operation["operation_id"])
        project_ref = str(operation.get("project_ref") or "")

        if operation_id == "project.lookup":
            return ApprovedReadQuery(
                operation_id=operation_id,
                dataset_id="projects",
                relation="dbo.vw_SolomonProjects",
                columns=(
                    "ProjectSourceKey",
                    "CompanyCode",
                    "ProjectCode",
                    "ProjectName",
                    "ProjectStatus",
                    "ProjectManager",
                    "StartDate",
                    "ContractAmount",
                    "CustomRegion",
                    "CustomerProjectAlias",
                    "CustomerPortfolioCode",
                ),
                match_any_filters=(
                    ReadFilter("ProjectCode", "eq", project_ref),
                    ReadFilter("ProjectName", "contains", project_ref),
                    ReadFilter("CustomerProjectAlias", "contains", project_ref),
                ),
                order_by=(ReadOrder("ProjectName", "asc"),),
                max_rows=10,
            )

        if operation_id == "business_party.lookup":
            party_ref = str(operation.get("party_ref") or "")
            return ApprovedReadQuery(
                operation_id=operation_id,
                dataset_id="business_parties",
                relation="dbo.vw_SolomonBusinessParties",
                columns=(
                    "PartySourceKey",
                    "PartyCode",
                    "PartyName",
                    "PartyType",
                    "TaxRegion",
                    "CustomDiversityCode",
                ),
                match_any_filters=(
                    ReadFilter("PartyCode", "eq", party_ref),
                    ReadFilter("PartyName", "contains", party_ref),
                ),
                order_by=(ReadOrder("PartyName", "asc"),),
                max_rows=20,
            )

        if operation_id == "project_issues.open_by_project":
            return ApprovedReadQuery(
                operation_id=operation_id,
                dataset_id="project_issues",
                relation="dbo.vw_SolomonProjectIssues",
                columns=(
                    "IssueSourceKey",
                    "ProjectSourceKey",
                    "ProjectCode",
                    "ProjectName",
                    "IssueCode",
                    "IssueType",
                    "IssueDescription",
                    "IssueStatus",
                    "DateInitiated",
                    "DueDate",
                    "ResponsibleParty",
                    "ResponsibleContact",
                    "BallInCourt",
                    "CostImpact",
                    "DaysImpact",
                    "ROMImpact",
                    "LocationCode",
                    "AttachmentCount",
                    "CustomRiskCategory",
                    "CustomerWorkflowStage",
                    "CustomerReviewOwner",
                    "CustomerEscalationFlag",
                ),
                match_any_filters=(
                    ReadFilter("ProjectCode", "eq", project_ref),
                    ReadFilter("ProjectName", "contains", project_ref),
                ),
                required_filters=(
                    ReadFilter(
                        "IssueStatus",
                        "not_in",
                        ("Resolved", "Closed", "Cancelled"),
                    ),
                ),
                order_by=(
                    ReadOrder("DueDate", "asc"),
                    ReadOrder("IssueCode", "asc"),
                ),
                max_rows=50,
            )

        if operation_id == "project_issues.open_count_by_project":
            return ApprovedReadQuery(
                operation_id=operation_id,
                dataset_id="project_issue_counts",
                relation="dbo.vw_SolomonOpenProjectIssueCounts",
                columns=(
                    "ProjectSourceKey",
                    "ProjectCode",
                    "ProjectName",
                    "OpenIssueCount",
                ),
                match_any_filters=(
                    ReadFilter("ProjectCode", "eq", project_ref),
                    ReadFilter("ProjectName", "contains", project_ref),
                ),
                order_by=(ReadOrder("ProjectName", "asc"),),
                max_rows=10,
            )

        if operation_id == "change_events.by_project":
            return ApprovedReadQuery(
                operation_id=operation_id,
                dataset_id="change_events",
                relation="dbo.vw_SolomonChangeEvents",
                columns=(
                    "ChangeSourceKey",
                    "ProjectSourceKey",
                    "ProjectCode",
                    "ProjectName",
                    "ChangeCode",
                    "ChangeType",
                    "ChangeDescription",
                    "ChangeStatus",
                    "PendingAmount",
                    "ApprovedAmount",
                    "BudgetImpact",
                    "FeeAmount",
                    "DateCreated",
                    "CustomChangeOrigin",
                ),
                match_any_filters=(
                    ReadFilter("ProjectCode", "eq", project_ref),
                    ReadFilter("ProjectName", "contains", project_ref),
                ),
                order_by=(
                    ReadOrder("DateCreated", "desc"),
                    ReadOrder("ChangeCode", "asc"),
                ),
                max_rows=50,
            )

        if operation_id == "change_exposure.pending_ranked":
            return ApprovedReadQuery(
                operation_id=operation_id,
                dataset_id="pending_change_exposure",
                relation="dbo.vw_SolomonPendingChangeExposure",
                columns=(
                    "ProjectSourceKey",
                    "ProjectCode",
                    "ProjectName",
                    "PendingChangeCount",
                    "PendingChangeExposure",
                ),
                order_by=(
                    ReadOrder("PendingChangeExposure", "desc"),
                    ReadOrder("ProjectName", "asc"),
                ),
                max_rows=25,
            )

        raise ValueError(f"Unsupported semantic operation: {operation_id}")

    @staticmethod
    def _record_id(row: Dict[str, Any], semantic_entity: str, index: int) -> str:
        candidates = (
            "IssueSourceKey",
            "ChangeSourceKey",
            "PartySourceKey",
            "ProjectSourceKey",
        )
        for key in candidates:
            value = row.get(key)
            if value is not None and str(value).strip():
                return f"{semantic_entity}:{value}"
        return f"{semantic_entity}:row:{index + 1}"

    def execute(self, operation: Dict[str, Any]) -> StructuredEvidencePacket:
        query = self._approved_query(operation)
        rows = self.database_adapter.execute_read(query)
        retrieved_at = datetime.now(timezone.utc).isoformat()
        semantic_entity = str(operation["semantic_entity"])
        records = []

        for index, row in enumerate(rows):
            provenance = {
                "source_type": SOURCE_TYPE,
                "connection_id": SOURCE_ID,
                "database_engine": self.database_adapter.engine,
                "dataset_id": query.dataset_id,
                "semantic_operation": query.operation_id,
                "semantic_entity": semantic_entity,
                "source_record_id": self._record_id(row, semantic_entity, index),
                "retrieved_at": retrieved_at,
            }
            records.append(
                StructuredEvidenceRecord(
                    record_id=provenance["source_record_id"],
                    semantic_entity=semantic_entity,
                    facts=dict(row),
                    provenance=provenance,
                )
            )

        return StructuredEvidencePacket(
            source_id=SOURCE_ID,
            source_type=SOURCE_TYPE,
            engine=self.database_adapter.engine,
            semantic_operation=query.operation_id,
            dataset_id=query.dataset_id,
            retrieved_at=retrieved_at,
            records=records,
        )

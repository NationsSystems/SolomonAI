# ------------------------------------------------------------------
# FILE: investigator_knowledge_observations.py
# DIRECTORY: solomon_core/investigator/
# ------------------------------------------------------------------
# Investigator Knowledge Layer Observations
#
# PURPOSE
#   Produce deterministic, non-authoritative observations from the raw
#   request, artifact metadata, and structured transport context.
#
# CONTRACT
#   - Runs inside the Investigator boundary
#   - Emits evidence only
#   - Does not select or recommend execution lanes
#   - Does not invoke an LLM or embedding model
#   - Does not use exact-phrase routing catalogs
#   - Does not infer BEI applicability from document contents
#   - Emits selected-source and authorized-corpus dependency evidence without routing
# ------------------------------------------------------------------

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from solomon_core.investigator.investigator_casefile_types import (
    AmbiguityItem,
    ArtifactInventory,
    EvidenceItem,
    StructuredEvidenceItem,
    KnowledgeLayerObservations,
    NegativeEvidenceItem,
    RequirementObservation,
    SkillLaneObservation,
    SufficiencyObservation,
)


_TOKEN_PATTERN = re.compile(r"[a-z0-9]+(?:['-][a-z0-9]+)*")
_URL_PATTERN = re.compile(r"\bhttps?://", re.IGNORECASE)
_QUOTED_CONTENT_PATTERNS = (
    re.compile(r"```.*?```", re.DOTALL),
    re.compile(r"`[^`]*`"),
    re.compile(r'"(?:\\.|[^"\\])*"', re.DOTALL),
    re.compile(r"“[^”]*”", re.DOTALL),
)

_OPERATION_TOKENS = {
    "analyze": "analyze",
    "analyse": "analyze",
    "compare": "compare",
    "contrast": "compare",
    "summarize": "summarize",
    "summarise": "summarize",
    "extract": "extract",
    "identify": "identify",
    "review": "review",
    "explain": "explain",
    "clarify": "clarify",
    "calculate": "calculate",
    "compute": "calculate",
    "rewrite": "rewrite",
    "draft": "draft",
    "search": "search",
    "find": "find",
    "verify": "verify",
    "check": "check",
}

_DOCUMENT_OPERATION_IDS = {
    "analyze",
    "compare",
    "summarize",
    "extract",
    "identify",
    "review",
}

_DOCUMENT_REFERENCE_TOKENS = {
    "attachment",
    "attachments",
    "bid",
    "document",
    "documents",
    "file",
    "files",
    "source",
    "sources",
    "specification",
    "specifications",
}

_STRONG_DOCUMENT_REFERENCE_TOKENS = {
    "attachment",
    "attachments",
    "document",
    "documents",
    "file",
    "files",
    "source",
    "sources",
    "specification",
    "specifications",
}

_INLINE_CONTENT_SCOPE_TOKENS = {
    "base",
    "below",
    "context",
    "corrected",
    "details",
    "email",
    "facts",
    "following",
    "given",
    "loop",
    "meeting",
    "message",
    "notes",
    "original",
    "paragraph",
    "provided",
    "quote",
    "quotes",
    "remembered",
    "sentence",
    "text",
    "these",
    "this",
    "those",
    "values",
}

_SPORTS_DOMAIN_TOKENS = {
    "baseball",
    "basketball",
    "club",
    "clubs",
    "college",
    "epl",
    "football",
    "game",
    "games",
    "league",
    "leagues",
    "match",
    "matches",
    "mlb",
    "nba",
    "ncaab",
    "ncaaf",
    "nfl",
    "nhl",
    "soccer",
    "sport",
    "sports",
    "team",
    "teams",
    "wnba",
}

_AMBIGUOUS_DOCUMENT_REFERENCE_TOKENS = {
    "proposal",
}

_REFERENTIAL_TOKENS = {
    "above",
    "again",
    "earlier",
    "it",
    "previous",
    "that",
    "these",
    "this",
    "those",
}

_STRUCTURAL_TOKENS = {
    "a",
    "about",
    "an",
    "and",
    "can",
    "could",
    "do",
    "for",
    "help",
    "i",
    "in",
    "is",
    "me",
    "of",
    "on",
    "please",
    "the",
    "to",
    "what",
    "will",
    "with",
    "would",
    "you",
}

_LIVE_INFORMATION_TOKENS = {
    "current",
    "currently",
    "latest",
    "live",
    "now",
    "recent",
    "recently",
    "today",
    "tonight",
    "tomorrow",
    "yesterday",
}

_LIVE_INFORMATION_TIME_WINDOW_PATTERN = re.compile(
    r"\b(?:this|last|past)\s+"
    r"(?:hour|day|week|month|year|morning|afternoon|evening)s?\b"
    r"|\b(?:last|past)\s+\d{1,3}\s+"
    r"(?:hours?|days?|weeks?|months?|years?)\b",
    flags=re.IGNORECASE,
)

_CURRENT_LIVE_FACT_TOKENS = {
    "availability",
    "forecast",
    "headlines",
    "news",
    "outage",
    "price",
    "prices",
    "quote",
    "quotes",
    "rate",
    "rates",
    "score",
    "scores",
    "standings",
    "status",
    "temperature",
    "weather",
}

_PUBLIC_EVENT_TOKENS = {
    "announce",
    "announced",
    "announcement",
    "announcements",
    "disclose",
    "disclosed",
    "disclosure",
    "disclosures",
    "publish",
    "published",
    "publicly",
}

_CONVERSATION_STATE_TOKENS = {
    "context",
    "correction",
    "details",
    "project",
    "retainage",
    "review",
    "scope",
    "state",
    "summary",
    "term",
    "terms",
    "value",
    "values",
}

_WEATHER_TOKENS = {
    "forecast",
    "rain",
    "snow",
    "storm",
    "temperature",
    "weather",
}

_SPORTS_LIVE_TOKENS = {
    "score",
    "scores",
    "schedule",
    "standings",
}

_MARKET_ENTITY_TOKENS = {
    "crypto",
    "equity",
    "market",
    "markets",
    "stock",
    "stocks",
    "ticker",
}

_MARKET_LIVE_TOKENS = {
    "price",
    "quote",
    "rate",
    "rates",
}

_CURRENT_EVENTS_TOKENS = {
    "headlines",
    "news",
}

_QUOTED_CONTENT_TRANSFORM_OPERATIONS = {
    "clarify",
    "draft",
    "explain",
    "rewrite",
    "summarize",
}

_BEI_WORKFLOW_IDS = {
    "bid_scope_review",
    "pre_award_risk_review",
}
_BEI_MODULE_ID = "preconstruction"
_BEI_REQUESTED_ACTION = "document_review"

_SOLOMON_SOURCE_ACTIONS = {
    "compare_sources": "compare",
    "identify_key_details": "identify",
    "summarize_sources": "summarize",
}

_SELECTED_CONVERSATION_AUTHORIZATION_STATUSES = {
    "conversation_selected",
}

_SELECTED_CONVERSATION_HANDOFF_CONTRACTS = {
    "explicit_authorized_conversation_sources",
    "explicit_owned_conversation_sources",
}

_SOURCE_CORPUS_AUTHORITY_CONTRACTS = {
    "sql_authorized_file_corpus_v1",
}

_STRUCTURED_EVIDENCE_AUTHORITY_CONTRACTS = {
    "solomon_structured_evidence_v1",
}

_AUTHORIZED_CORPUS_OWNERSHIP_TOKENS = {
    "company",
    "internal",
    "organisation",
    "organization",
    "our",
    "ours",
    "we",
}

_AUTHORIZED_CORPUS_DIRECTORY_FIELD_TOKENS = {
    "contact",
    "department",
    "email",
    "extension",
    "location",
    "manager",
    "office",
    "phone",
    "role",
    "title",
}

_POSSESSIVE_DIRECTORY_LOOKUP_PATTERN = re.compile(
    r"\b[a-z0-9][a-z0-9.-]*(?:\s+[a-z0-9][a-z0-9.-]*){0,3}"
    r"(?:['’]s|['’])\s+(?:"
    + "|".join(sorted(_AUTHORIZED_CORPUS_DIRECTORY_FIELD_TOKENS))
    + r")\b",
    flags=re.IGNORECASE,
)

_INLINE_ASSERTION_PATTERN = re.compile(
    r"\b(?:states?|says?|specifies?|provides?|requires?)\s+that\b",
    flags=re.IGNORECASE,
)

_CONVERSATION_SET_REFERENCE_PATTERN = re.compile(
    r"\b(?:which|one|each|all)\s+of\s+(?:the|these|those)\b",
    flags=re.IGNORECASE,
)

_SOURCE_GROUNDED_ACTION_TOKENS = {
    "answer",
    "check",
    "describe",
    "explain",
    "extract",
    "find",
    "identify",
    "include",
    "includes",
    "list",
    "mentions",
    "read",
    "references",
    "review",
    "say",
    "says",
    "show",
    "summarize",
    "tell",
    "verify",
}

_SOURCE_GROUNDED_QUESTION_TOKENS = {
    "are",
    "can",
    "could",
    "did",
    "do",
    "does",
    "has",
    "have",
    "how",
    "is",
    "should",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "will",
    "would",
}

_ASSISTANT_CAPABILITY_QUESTION_TOKENS = {
    "can",
    "could",
    "should",
    "will",
    "would",
}

_NON_SOURCE_GROUNDED_OPERATIONS = {
    "calculate",
    "draft",
    "rewrite",
}


@dataclass(frozen=True)
class KnowledgeObservationResult:
    observations: KnowledgeLayerObservations
    positive_evidence: List[EvidenceItem]
    negative_evidence: List[NegativeEvidenceItem]
    ambiguities: List[AmbiguityItem]


def _safe_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_list(value: Any) -> List[Any]:
    return value if isinstance(value, list) else []


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _tokens(value: str) -> List[str]:
    return _TOKEN_PATTERN.findall(_safe_text(value).lower())


def _unique(values: Iterable[str]) -> List[str]:
    output: List[str] = []
    seen = set()

    for value in values:
        clean_value = _safe_text(value)

        if not clean_value or clean_value in seen:
            continue

        output.append(clean_value)
        seen.add(clean_value)

    return output


def _read_attachment_value(attachment: Any, *names: str) -> Any:
    for name in names:
        value = (
            attachment.get(name)
            if isinstance(attachment, dict)
            else getattr(attachment, name, None)
        )

        if value not in (None, ""):
            return value

    return None


def _artifact_record(attachment: Any, index: int) -> Dict[str, Any]:
    document_id = _read_attachment_value(
        attachment,
        "document_id",
        "random_name",
        "upload_id",
        "file_id",
        "id",
    )
    original_name = _read_attachment_value(
        attachment,
        "original_name",
        "filename",
        "file_name",
        "name",
    )
    extension = _read_attachment_value(
        attachment,
        "extension",
        "file_extension",
    )
    resolved_path = _read_attachment_value(
        attachment,
        "resolved_path",
        "absolute_path",
        "file_path",
        "filepath",
        "stored_path",
        "saved_path",
        "path",
    )

    clean_document_id = _safe_text(document_id) or f"artifact_{index + 1}"
    clean_original_name = _safe_text(original_name) or clean_document_id
    clean_extension = _safe_text(extension).lower()

    if not clean_extension and "." in clean_original_name:
        clean_extension = clean_original_name.rsplit(".", 1)[-1].lower()
        clean_extension = f".{clean_extension}"

    return {
        "artifact_id": clean_document_id,
        "original_name": clean_original_name,
        "extension": clean_extension,
        "selected_for_workflow": bool(
            _read_attachment_value(
                attachment,
                "selected_for_workflow",
            )
        ),
        "selected_for_conversation": bool(
            _read_attachment_value(
                attachment,
                "selected_for_conversation",
            )
        ),
        "authorization_status": _safe_text(
            _read_attachment_value(
                attachment,
                "authorization_status",
            )
        ),
        "handoff_contract": _safe_text(
            _read_attachment_value(
                attachment,
                "handoff_contract",
            )
        ),
        "analysis_status": _safe_text(
            _read_attachment_value(
                attachment,
                "analysis_status",
            )
        ),
        "resolved_path_present": bool(_safe_text(resolved_path)),
    }


def _build_artifact_inventory(attachments: List[Any]) -> ArtifactInventory:
    artifacts = [
        _artifact_record(attachment, index)
        for index, attachment in enumerate(attachments)
        if attachment
    ]

    return ArtifactInventory(
        total_count=len(artifacts),
        document_count=len(artifacts),
        attachment_count=len(attachments),
        resolved_path_count=sum(
            1
            for artifact in artifacts
            if artifact.get("resolved_path_present")
        ),
        artifacts=artifacts,
    )


def _workflow_context(environmental_ctx: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(environmental_ctx.get("workflow_context"))


def _workspace_context(environmental_ctx: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(environmental_ctx.get("workspace_context"))


def _workflow_record(workflow_context: Dict[str, Any]) -> Dict[str, Any]:
    return _safe_dict(workflow_context.get("workflow"))


def _artifact_is_selected_conversation_source(
    artifact: Dict[str, Any],
) -> bool:
    if not isinstance(artifact, dict):
        return False

    authorization_status = _safe_text(
        artifact.get("authorization_status")
    ).lower()
    handoff_contract = _safe_text(
        artifact.get("handoff_contract")
    ).lower()

    return bool(
        artifact.get("selected_for_conversation")
        or authorization_status in _SELECTED_CONVERSATION_AUTHORIZATION_STATUSES
        or handoff_contract in _SELECTED_CONVERSATION_HANDOFF_CONTRACTS
    )


def _selected_conversation_source_count(
    artifact_inventory: Optional[ArtifactInventory],
) -> int:
    if not artifact_inventory:
        return 0

    return sum(
        1
        for artifact in artifact_inventory.artifacts
        if _artifact_is_selected_conversation_source(artifact)
    )


def _selected_conversation_sources_present(
    artifact_inventory: Optional[ArtifactInventory],
) -> bool:
    return _selected_conversation_source_count(artifact_inventory) > 0


def _source_corpus_records(
    environmental_ctx: Optional[Dict[str, Any]],
) -> List[Any]:
    if not isinstance(environmental_ctx, dict):
        return []

    return _safe_list(
        environmental_ctx.get("source_corpus")
    )


def _source_corpus_count(
    environmental_ctx: Optional[Dict[str, Any]],
) -> int:
    records = _source_corpus_records(
        environmental_ctx
    )

    if records:
        return len(records)

    if not isinstance(environmental_ctx, dict):
        return 0

    try:
        return max(
            0,
            int(
                environmental_ctx.get("source_corpus_count")
                or 0
            ),
        )
    except (TypeError, ValueError):
        return 0


def _authorized_source_corpus_present(
    environmental_ctx: Optional[Dict[str, Any]],
) -> bool:
    if not isinstance(environmental_ctx, dict):
        return False

    authority = _safe_text(
        environmental_ctx.get("source_corpus_authority")
    ).lower()

    return bool(
        authority in _SOURCE_CORPUS_AUTHORITY_CONTRACTS
        and _source_corpus_count(environmental_ctx) > 0
    )


def _structured_evidence_packet(
    environmental_ctx: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not isinstance(
        environmental_ctx,
        dict,
    ):
        return {}

    packet = _safe_dict(
        environmental_ctx.get(
            "structured_evidence"
        )
    )
    authority = _safe_text(
        packet.get("authority")
        or environmental_ctx.get(
            "structured_evidence_authority"
        )
    ).lower()

    if (
        authority
        not in _STRUCTURED_EVIDENCE_AUTHORITY_CONTRACTS
    ):
        return {}

    return packet


def _structured_evidence_records(
    environmental_ctx: Optional[Dict[str, Any]],
) -> List[Any]:
    return _safe_list(
        _structured_evidence_packet(
            environmental_ctx
        ).get("records")
    )


def _structured_evidence_matched(
    environmental_ctx: Optional[Dict[str, Any]],
) -> bool:
    packet = _structured_evidence_packet(
        environmental_ctx
    )

    return bool(
        packet
        and _safe_text(
            packet.get(
                "semantic_operation"
            )
        )
    )


def _knowledge_seeking_question_observed(
    raw_user_request: str,
) -> bool:
    """Return whether request grammar presents a knowledge-seeking question."""

    request_tokens = _tokens(raw_user_request)

    if not request_tokens:
        return False

    lead_token = request_tokens[0]

    if lead_token not in _SOURCE_GROUNDED_QUESTION_TOKENS:
        return False

    if (
        lead_token in _ASSISTANT_CAPABILITY_QUESTION_TOKENS
        and len(request_tokens) > 1
        and request_tokens[1] == "you"
    ):
        return False

    return True


def _source_grounded_request_signal_observed(
    raw_user_request: str,
    operation: Optional[str],
) -> bool:
    token_set = set(_tokens(raw_user_request))

    if not token_set:
        return False

    if operation in _NON_SOURCE_GROUNDED_OPERATIONS:
        return False

    if operation in _DOCUMENT_OPERATION_IDS:
        return True

    if operation in {"check", "explain", "find", "search", "verify"}:
        return True

    if _knowledge_seeking_question_observed(raw_user_request):
        return True

    return bool(token_set & _SOURCE_GROUNDED_ACTION_TOKENS)


def _authorized_corpus_request_signal_observed(
    raw_user_request: str,
    operation: Optional[str],
) -> bool:
    """
    Return whether the request positively scopes itself to authorized corpus evidence.

    Corpus availability is eligibility only. Background organizational files must not
    become authoritative merely because the request is phrased as a question or uses
    a document-style verb. The request must independently establish organizational,
    private-record, or explicit document/source scope.
    """

    if operation in _NON_SOURCE_GROUNDED_OPERATIONS:
        return False

    request_text = _safe_text(raw_user_request)
    token_set = set(_tokens(request_text))

    if not token_set:
        return False

    if _inline_content_scope_observed(request_text):
        return False

    if _INLINE_ASSERTION_PATTERN.search(request_text):
        return False

    if _CONVERSATION_SET_REFERENCE_PATTERN.search(request_text):
        return False

    explicit_source_scope = bool(
        token_set & _DOCUMENT_REFERENCE_TOKENS
    )
    organizational_ownership_scope = bool(
        token_set & _AUTHORIZED_CORPUS_OWNERSHIP_TOKENS
    )
    private_directory_lookup = bool(
        _POSSESSIVE_DIRECTORY_LOOKUP_PATTERN.search(request_text)
    )

    if not (
        explicit_source_scope
        or organizational_ownership_scope
        or private_directory_lookup
    ):
        return False

    scoped_question_observed = bool(
        token_set & _SOURCE_GROUNDED_QUESTION_TOKENS
    )

    if (
        scoped_question_observed
        and (
            explicit_source_scope
            or organizational_ownership_scope
            or private_directory_lookup
        )
    ):
        return True

    return _source_grounded_request_signal_observed(
        request_text,
        operation,
    )


def _source_evidence_dependency_observed(
    *,
    raw_user_request: str,
    operation: Optional[str],
    artifact_inventory: Optional[ArtifactInventory],
    environmental_ctx: Optional[Dict[str, Any]],
    external_requirement: Optional[RequirementObservation],
) -> bool:
    """
    Return whether authorized source resources create a source-dependency signal.

    This is deterministic evidence only. It does not select a lane. The
    Orchestrator remains solely responsible for using, ignoring, or resolving
    competing observations.
    """

    selected_conversation_sources_present = (
        _selected_conversation_sources_present(
            artifact_inventory
        )
    )
    authorized_source_corpus_present = (
        _authorized_source_corpus_present(
            environmental_ctx
        )
    )
    source_resources_present = bool(
        selected_conversation_sources_present
        or authorized_source_corpus_present
    )

    if not source_resources_present:
        return False

    if (
        external_requirement
        and external_requirement.state == "required"
    ):
        return False

    if operation in _NON_SOURCE_GROUNDED_OPERATIONS:
        return False

    request_tokens = set(
        _tokens(
            raw_user_request
        )
    )

    if selected_conversation_sources_present:
        if request_tokens & _SOURCE_GROUNDED_QUESTION_TOKENS:
            return True

        return _source_grounded_request_signal_observed(
            raw_user_request,
            operation,
        )

    if authorized_source_corpus_present:
        return _authorized_corpus_request_signal_observed(
            raw_user_request,
            operation,
        )

    return False


def _strong_document_scope_observed(
    token_set: set[str],
    artifact_inventory: Optional[ArtifactInventory],
) -> bool:
    """Return whether the request clearly points at an external document source."""

    if token_set & _STRONG_DOCUMENT_REFERENCE_TOKENS:
        return True

    if (
        artifact_inventory
        and artifact_inventory.document_count > 0
        and token_set & _AMBIGUOUS_DOCUMENT_REFERENCE_TOKENS
    ):
        return True

    return False


def _inline_content_scope_observed(raw_user_request: str) -> bool:
    """Return whether the request appears scoped to supplied text or chat context."""

    request_text = _safe_text(raw_user_request)
    token_set = set(_tokens(request_text))

    if not token_set:
        return False

    if token_set & _INLINE_CONTENT_SCOPE_TOKENS:
        return True

    return any(
        pattern.search(request_text)
        for pattern in _QUOTED_CONTENT_PATTERNS
    )


def _operation_is_inline_content_transform(
    *,
    operation: Optional[str],
    raw_user_request: str,
    artifact_inventory: Optional[ArtifactInventory],
) -> bool:
    """
    Return whether a document-style operation is actually scoped to inline text.

    This keeps the Knowledge Layer evidence-only while preventing raw chat
    summarization, comparison, or review requests from being mislabeled as
    document-source operations when no explicit document source is present.
    """

    if operation not in _DOCUMENT_OPERATION_IDS:
        return False

    token_set = set(_tokens(raw_user_request))

    if _strong_document_scope_observed(token_set, artifact_inventory):
        return False

    return _inline_content_scope_observed(raw_user_request)


def _strip_inline_supplied_content(raw_user_request: str) -> str:
    """
    Remove supplied inline content from live-information evidence checks.

    Content after an instruction colon may contain words such as "tomorrow" or
    "schedule" that describe the text being transformed rather than a request
    for external retrieval.
    """

    request_text = _safe_text(raw_user_request)

    if ":" not in request_text:
        return request_text

    prefix, suffix = request_text.split(":", 1)
    prefix_tokens = set(_tokens(prefix))
    suffix_tokens = set(_tokens(suffix))

    prefix_operations = {
        _OPERATION_TOKENS.get(token)
        for token in prefix_tokens
    }
    prefix_operations.discard(None)

    if not prefix_operations & _QUOTED_CONTENT_TRANSFORM_OPERATIONS:
        return request_text

    if not (
        prefix_tokens & _INLINE_CONTENT_SCOPE_TOKENS
        or suffix_tokens
    ):
        return request_text

    return prefix.strip()


def _explicit_operation_from_transport(
    workflow_context: Dict[str, Any],
) -> tuple[Optional[str], Optional[str], float]:
    source_action = _safe_text(
        workflow_context.get("solomon_ai_request_action")
    ).lower()

    if source_action in _SOLOMON_SOURCE_ACTIONS:
        return (
            _SOLOMON_SOURCE_ACTIONS[source_action],
            "transport:solomon_ai_request_action",
            1.0,
        )

    workflow = _workflow_record(workflow_context)

    for ref_id, value in (
        (
            "transport:workflow_requested_action",
            workflow.get("requested_action"),
        ),
        (
            "transport:workflow_input_mode",
            workflow_context.get("input_mode"),
        ),
    ):
        clean_value = _safe_text(value).lower()

        if clean_value:
            return clean_value, ref_id, 1.0

    return None, None, 0.0


def _explicit_operation_from_request(
    raw_user_request: str,
    artifact_inventory: Optional[ArtifactInventory],
) -> tuple[Optional[str], Optional[str], float]:
    for token in _tokens(raw_user_request):
        operation = _OPERATION_TOKENS.get(token)

        if not operation:
            continue

        if _operation_is_inline_content_transform(
            operation=operation,
            raw_user_request=raw_user_request,
            artifact_inventory=artifact_inventory,
        ):
            return None, None, 0.0

        return operation, "raw_user_input", 0.75

    return None, None, 0.0


def _resolve_explicit_operation(
    raw_user_request: str,
    workflow_context: Dict[str, Any],
    artifact_inventory: Optional[ArtifactInventory],
) -> tuple[Optional[str], Optional[str], float]:
    operation, ref_id, strength = _explicit_operation_from_transport(
        workflow_context
    )

    if operation:
        return operation, ref_id, strength

    return _explicit_operation_from_request(
        raw_user_request,
        artifact_inventory,
    )


def _external_information_evidence_text(
    raw_user_request: str,
    operation: Optional[str],
) -> str:
    """
    Return the request text eligible to establish live-information evidence.

    When the user explicitly asks SolomonAI to transform supplied quoted text,
    time words inside that quoted material describe the content being edited;
    they do not authorize external retrieval. The governing instruction outside
    the quoted material remains eligible evidence. Ordinary live-information
    requests and unquoted transformation requests remain unchanged.
    """

    request_text = _safe_text(raw_user_request)

    request_operations = {
        _OPERATION_TOKENS.get(token)
        for token in _tokens(request_text)
    }
    request_operations.discard(None)

    transform_scope = bool(
        operation in _QUOTED_CONTENT_TRANSFORM_OPERATIONS
        or request_operations & _QUOTED_CONTENT_TRANSFORM_OPERATIONS
    )

    if not transform_scope:
        return request_text

    evidence_text = _strip_inline_supplied_content(request_text)

    for pattern in _QUOTED_CONTENT_PATTERNS:
        evidence_text = pattern.sub(
            " ",
            evidence_text,
        )

    return " ".join(evidence_text.split())


def _external_information_observation(
    raw_user_request: str,
    operation: Optional[str],
) -> tuple[RequirementObservation, List[str]]:
    evidence_text = _external_information_evidence_text(
        raw_user_request,
        operation,
    )
    token_set = set(_tokens(evidence_text))
    evidence_refs: List[str] = []
    semantic_domains: List[str] = []

    explicit_url = bool(_URL_PATTERN.search(evidence_text))
    weather_domain = bool(token_set & _WEATHER_TOKENS)
    sports_domain = bool(token_set & _SPORTS_DOMAIN_TOKENS)
    sports_live = bool(
        sports_domain
        and token_set & _SPORTS_LIVE_TOKENS
    )
    current_events = bool(token_set & _CURRENT_EVENTS_TOKENS)
    market_domain = bool(token_set & _MARKET_ENTITY_TOKENS)
    market_live = bool(
        market_domain
        and token_set & _MARKET_LIVE_TOKENS
    )
    current_marker_observed = bool(
        token_set & {"current", "currently"}
    )
    strong_live_marker_observed = bool(
        token_set
        & (
            _LIVE_INFORMATION_TOKENS
            - {"current", "currently"}
        )
    )
    time_window_marker_observed = bool(
        _LIVE_INFORMATION_TIME_WINDOW_PATTERN.search(
            evidence_text
        )
    )
    public_event_marker_observed = bool(
        token_set & _PUBLIC_EVENT_TOKENS
    )
    current_live_fact = bool(
        token_set & _CURRENT_LIVE_FACT_TOKENS
    )
    conversation_state_reference = bool(
        token_set & _LIVE_INFORMATION_TOKENS
        and token_set & _CONVERSATION_STATE_TOKENS
        and not (
            weather_domain
            or sports_live
            or current_events
            or market_live
            or public_event_marker_observed
        )
    )
    live_marker = bool(
        (
            strong_live_marker_observed
            and not conversation_state_reference
        )
        or (
            time_window_marker_observed
            and public_event_marker_observed
        )
        or (
            current_marker_observed
            and not conversation_state_reference
            and (
                weather_domain
                or sports_live
                or current_events
                or market_live
                or current_live_fact
            )
        )
    )

    if explicit_url:
        evidence_refs.append("observation:explicit_url")
        semantic_domains.append("external_source")

    if live_marker:
        evidence_refs.append("observation:live_information_marker")

    if weather_domain:
        semantic_domains.append("weather")

    if sports_live:
        semantic_domains.append("sports")

    if current_events:
        semantic_domains.append("current_events")

    if market_live:
        semantic_domains.append("markets")

    required = bool(
        explicit_url
        or live_marker
        or weather_domain
        or sports_live
        or current_events
        or market_live
    )

    if required:
        evidence_refs.append("raw_user_input")

        return (
            RequirementObservation(
                state="required",
                evidence_refs=_unique(evidence_refs),
                negative_evidence_refs=[],
                strength=0.9 if explicit_url or live_marker else 0.8,
            ),
            _unique(["external_live_information", *semantic_domains]),
        )

    return (
        RequirementObservation(
            state="undetermined",
            evidence_refs=[],
            negative_evidence_refs=[
                "negative:external_information_not_established"
            ],
            strength=0.6,
        ),
        [],
    )


def _document_analysis_observation(
    *,
    raw_user_request: str,
    operation: Optional[str],
    operation_ref: Optional[str],
    artifact_inventory: ArtifactInventory,
    workflow_context: Dict[str, Any],
    external_requirement: RequirementObservation,
    source_evidence_dependency: bool,
    source_corpus_available: bool,
) -> RequirementObservation:
    token_set = set(_tokens(raw_user_request))
    source_action = _safe_text(
        workflow_context.get("solomon_ai_request_action")
    ).lower()

    explicit_source_operation = source_action in _SOLOMON_SOURCE_ACTIONS
    explicit_document_reference = bool(
        token_set & _DOCUMENT_REFERENCE_TOKENS
    )
    ambiguous_document_reference = bool(
        token_set & _AMBIGUOUS_DOCUMENT_REFERENCE_TOKENS
    )
    document_reference = bool(
        explicit_document_reference
        or (
            ambiguous_document_reference
            and artifact_inventory.document_count > 0
        )
    )
    document_operation = operation in _DOCUMENT_OPERATION_IDS

    if explicit_source_operation or source_evidence_dependency or (
        document_operation
        and (
            artifact_inventory.document_count > 0
            or document_reference
        )
    ):
        evidence_refs = ["raw_user_input"]

        if operation_ref:
            evidence_refs.append(operation_ref)

        if artifact_inventory.document_count:
            evidence_refs.append("artifact_inventory")

        if source_evidence_dependency:
            evidence_refs.append(
                "observation:source_evidence_dependency"
            )

        if source_corpus_available:
            evidence_refs.append(
                "source_corpus"
            )

        if explicit_source_operation:
            strength = 1.0
        elif source_evidence_dependency:
            strength = 0.92
        else:
            strength = 0.85

        return RequirementObservation(
            state="required",
            evidence_refs=_unique(evidence_refs),
            negative_evidence_refs=[],
            strength=strength,
        )

    return RequirementObservation(
        state="undetermined",
        evidence_refs=[],
        negative_evidence_refs=[
            "negative:document_analysis_not_established"
        ],
        strength=0.6,
    )


def _bei_skill_observation(
    workflow_context: Dict[str, Any],
    workspace_context: Dict[str, Any],
) -> SkillLaneObservation:
    workflow = _workflow_record(workflow_context)
    workflow_id = _safe_text(
        workflow_context.get("workflow_id")
        or workflow.get("id")
    ).lower()
    workflow_module = _safe_text(workflow.get("module")).lower()
    workspace_module = _safe_text(
        workspace_context.get("module")
    ).lower()
    requested_action = _safe_text(
        workflow.get("requested_action")
    ).lower()

    applicable = bool(
        workflow_id in _BEI_WORKFLOW_IDS
        and workflow_module == _BEI_MODULE_ID
        and workspace_module == _BEI_MODULE_ID
        and requested_action == _BEI_REQUESTED_ACTION
    )

    if applicable:
        return SkillLaneObservation(
            skill_id="bei",
            applicability="applicable",
            evidence_refs=[
                "transport:workflow_id",
                "transport:workflow_module",
                "transport:workflow_requested_action",
            ],
            negative_evidence_refs=[],
            strength=1.0,
        )

    return SkillLaneObservation(
        skill_id="bei",
        applicability="not_applicable",
        evidence_refs=[],
        negative_evidence_refs=[
            "negative:bei_contract_not_established"
        ],
        strength=1.0,
    )


def _referential_request_without_context(
    raw_user_request: str,
    artifact_inventory: ArtifactInventory,
    conversation_memory: Optional[Dict[str, Any]],
) -> bool:
    token_set = set(_tokens(raw_user_request))

    if not token_set or not token_set & _REFERENTIAL_TOKENS:
        return False

    meaningful_tokens = token_set - _STRUCTURAL_TOKENS - _REFERENTIAL_TOKENS

    return bool(
        not meaningful_tokens
        and artifact_inventory.total_count == 0
        and not conversation_memory
    )


def _sufficiency_observation(
    *,
    raw_user_request: str,
    operation: Optional[str],
    artifact_inventory: ArtifactInventory,
    document_requirement: RequirementObservation,
    conversation_memory: Optional[Dict[str, Any]],
    source_corpus_count: int,
) -> tuple[SufficiencyObservation, List[AmbiguityItem]]:
    missing_information: List[str] = []
    ambiguities: List[AmbiguityItem] = []

    if not _safe_text(raw_user_request):
        missing_information.append("user_request")

    available_document_count = max(
        artifact_inventory.document_count,
        source_corpus_count,
    )

    if (
        document_requirement.state == "required"
        and available_document_count == 0
    ):
        missing_information.append("document_source")

    if (
        operation == "compare"
        and document_requirement.state == "required"
        and available_document_count < 2
    ):
        missing_information.append("second_document_source")

    if _referential_request_without_context(
        raw_user_request,
        artifact_inventory,
        conversation_memory,
    ):
        missing_information.append("referenced_subject")

    for item in _unique(missing_information):
        ambiguities.append(
            AmbiguityItem(
                ambiguity_id=f"missing_{item}",
                description=f"Required information is missing: {item}.",
                scope=(
                    "artifacts"
                    if "document" in item
                    else "request"
                ),
            )
        )

    if missing_information:
        return (
            SufficiencyObservation(
                ambiguity_state="material",
                sufficiency_state="insufficient",
                missing_information=_unique(missing_information),
                evidence_refs=[
                    f"ambiguity:missing_{item}"
                    for item in _unique(missing_information)
                ],
                strength=1.0,
            ),
            ambiguities,
        )

    return (
        SufficiencyObservation(
            ambiguity_state="none",
            sufficiency_state="sufficient",
            missing_information=[],
            evidence_refs=["raw_user_input"],
            strength=0.9,
        ),
        ambiguities,
    )


def _positive_evidence(
    *,
    raw_user_request: str,
    artifact_inventory: ArtifactInventory,
    operation: Optional[str],
    operation_ref: Optional[str],
    document_requirement: RequirementObservation,
    external_requirement: RequirementObservation,
    sufficiency: SufficiencyObservation,
    skill_observation: SkillLaneObservation,
    source_evidence_dependency_observed: bool,
    source_corpus_count: int,
    structured_evidence_packet: Optional[Dict[str, Any]] = None,
) -> List[EvidenceItem]:
    evidence = [
        EvidenceItem(
            ref_id="raw_user_input",
            kind="observation",
            description=raw_user_request,
            source="user",
            confidence=1.0,
        )
    ]

    for artifact in artifact_inventory.artifacts:
        evidence.append(
            EvidenceItem(
                ref_id=f"artifact:{artifact['artifact_id']}",
                kind="artifact_metadata",
                description=(
                    f"Artifact supplied: {artifact['original_name']} "
                    f"({artifact['authorization_status'] or 'unclassified authority'})."
                ),
                source="artifact_intake",
                confidence=1.0,
            )
        )

    if operation:
        evidence.append(
            EvidenceItem(
                ref_id="observation:explicit_requested_operation",
                kind="operation_observation",
                description=f"Observed requested operation: {operation}.",
                source=operation_ref or "knowledge_layer",
                confidence=0.75 if operation_ref == "raw_user_input" else 1.0,
            )
        )

    if source_corpus_count:
        evidence.append(
            EvidenceItem(
                ref_id="source_corpus",
                kind="resource_inventory",
                description=(
                    "SQL-authorized searchable source corpus is available "
                    f"({source_corpus_count} file record(s))."
                ),
                source="resource_authority",
                confidence=1.0,
            )
        )

    structured_packet = _safe_dict(
        structured_evidence_packet
    )

    if structured_packet:
        structured_records = _safe_list(
            structured_packet.get(
                "records"
            )
        )
        structured_status = (
            _safe_text(
                structured_packet.get(
                    "status"
                )
            ).lower()
            or "unknown"
        )
        semantic_operation = _safe_text(
            structured_packet.get(
                "semantic_operation"
            )
        )
        dataset_id = _safe_text(
            structured_packet.get(
                "dataset_id"
            )
        )
        source_metadata = {
            "source_id": structured_packet.get(
                "source_id"
            ),
            "source_type": structured_packet.get(
                "source_type"
            ),
            "engine": structured_packet.get(
                "engine"
            ),
            "semantic_operation": semantic_operation,
            "dataset_id": dataset_id,
            "retrieved_at": structured_packet.get(
                "retrieved_at"
            ),
            "status": structured_status,
            "record_count": len(
                structured_records
            ),
            "error_code": structured_packet.get(
                "error_code"
            ),
        }

        evidence.append(
            StructuredEvidenceItem(
                ref_id="structured_evidence",
                kind="resource_inventory",
                description=(
                    "Governed external structured evidence matched "
                    "the request through operation "
                    f"{semantic_operation or 'unknown'} on approved "
                    f"dataset {dataset_id or 'unknown'}; "
                    f"status={structured_status}, "
                    f"records={len(structured_records)}."
                ),
                source="structured_resource_authority",
                confidence=1.0,
                metadata=source_metadata,
            )
        )

        if (
            structured_status == "ready"
            and structured_records
        ):
            for index, record in enumerate(
                structured_records
            ):
                if not isinstance(
                    record,
                    dict,
                ):
                    continue

                facts = _safe_dict(
                    record.get(
                        "facts"
                    )
                )
                provenance = _safe_dict(
                    record.get(
                        "provenance"
                    )
                )
                fact_parts = []

                for key, value in facts.items():
                    rendered = (
                        _safe_text(value)
                        if value is not None
                        else "null"
                    )
                    fact_parts.append(
                        f"{key}={rendered}"
                    )

                description = "; ".join(
                    fact_parts
                )[:2400]

                evidence.append(
                    StructuredEvidenceItem(
                        ref_id=(
                            "structured_record:"
                            + _safe_text(
                                record.get(
                                    "record_id"
                                )
                                or index
                            )
                        ),
                        kind="structured_record",
                        description=(
                            description
                            or (
                                "Structured record contains "
                                "no scalar facts."
                            )
                        ),
                        source="external_database",
                        confidence=1.0,
                        metadata=provenance,
                    )
                )
        elif structured_status == "ready":
            evidence.append(
                StructuredEvidenceItem(
                    ref_id="structured_source_status",
                    kind="structured_source_status",
                    description=(
                        "The approved external database read "
                        "completed successfully and returned "
                        "no matching records."
                    ),
                    source="external_database",
                    confidence=1.0,
                    metadata=source_metadata,
                )
            )
        else:
            evidence.append(
                StructuredEvidenceItem(
                    ref_id="structured_source_status",
                    kind="structured_source_status",
                    description=(
                        _safe_text(
                            structured_packet.get(
                                "user_message"
                            )
                        )
                        or (
                            "The governed external structured "
                            "source is unavailable."
                        )
                    ),
                    source="external_database",
                    confidence=1.0,
                    metadata=source_metadata,
                )
            )

        evidence.append(
            EvidenceItem(
                ref_id=(
                    "observation:"
                    "structured_evidence_dependency"
                ),
                kind="requirement_observation",
                description=(
                    "The request matched an approved "
                    "structured-data semantic operation and "
                    "the resulting governed evidence is "
                    "authoritative for that external source read."
                ),
                source="knowledge_layer",
                confidence=1.0,
            )
        )

    if source_evidence_dependency_observed:
        evidence.append(
            EvidenceItem(
                ref_id="observation:source_evidence_dependency",
                kind="requirement_observation",
                description=(
                    "Authorized source resources are available and the "
                    "request asks for source-grounded information."
                ),
                source="knowledge_layer",
                confidence=0.92,
            )
        )

    if document_requirement.state == "required":
        evidence.append(
            EvidenceItem(
                ref_id="observation:document_analysis_required",
                kind="requirement_observation",
                description="Document analysis is explicitly supported by request evidence.",
                source="knowledge_layer",
                confidence=document_requirement.strength,
            )
        )

    if external_requirement.state == "required":
        evidence.append(
            EvidenceItem(
                ref_id="observation:external_information_required",
                kind="requirement_observation",
                description="External or live information is explicitly required.",
                source="knowledge_layer",
                confidence=external_requirement.strength,
            )
        )

    if sufficiency.sufficiency_state == "sufficient":
        evidence.append(
            EvidenceItem(
                ref_id="observation:request_sufficient",
                kind="sufficiency_observation",
                description="No material missing input was observed.",
                source="knowledge_layer",
                confidence=sufficiency.strength,
            )
        )

    if skill_observation.applicability == "applicable":
        evidence.append(
            EvidenceItem(
                ref_id="observation:bei_applicable",
                kind="skill_applicability_observation",
                description="The explicit BEI workflow contract is present.",
                source="workflow_transport",
                confidence=skill_observation.strength,
            )
        )

    return evidence


def _negative_evidence(
    *,
    document_requirement: RequirementObservation,
    external_requirement: RequirementObservation,
    sufficiency: SufficiencyObservation,
    skill_observation: SkillLaneObservation,
) -> List[NegativeEvidenceItem]:
    evidence: List[NegativeEvidenceItem] = []

    if document_requirement.state != "required":
        evidence.append(
            NegativeEvidenceItem(
                indicator_id="document_analysis_required",
                description="No explicit document-analysis requirement was established.",
                expected_by="knowledge_layer",
            )
        )

    if external_requirement.state != "required":
        evidence.append(
            NegativeEvidenceItem(
                indicator_id="external_information_required",
                description="No explicit external or live-information requirement was established.",
                expected_by="knowledge_layer",
            )
        )

    if sufficiency.sufficiency_state == "insufficient":
        evidence.append(
            NegativeEvidenceItem(
                indicator_id="request_sufficient",
                description=(
                    "The request is missing required information: "
                    + ", ".join(sufficiency.missing_information)
                    + "."
                ),
                expected_by="knowledge_layer",
            )
        )

    if skill_observation.applicability != "applicable":
        evidence.append(
            NegativeEvidenceItem(
                indicator_id="bei_applicable",
                description="The explicit BEI workflow contract is absent.",
                expected_by="workflow_contract",
            )
        )

    return evidence


def build_knowledge_layer_observations(
    *,
    raw_user_request: str,
    attachments: Optional[List[Any]],
    environmental_ctx: Optional[Dict[str, Any]],
    conversation_memory: Optional[Dict[str, Any]],
) -> KnowledgeObservationResult:
    """
    Build deterministic Investigator observations without selecting a lane.
    """

    clean_request = _safe_text(raw_user_request)
    clean_attachments = _safe_list(attachments)
    clean_environment = _safe_dict(environmental_ctx)
    workflow_context = _workflow_context(clean_environment)
    workspace_context = _workspace_context(clean_environment)
    source_corpus_count = _source_corpus_count(
        clean_environment
    )
    source_corpus_available = _authorized_source_corpus_present(
        clean_environment
    )
    structured_packet = _structured_evidence_packet(
        clean_environment
    )
    structured_evidence_matched = _structured_evidence_matched(
        clean_environment
    )

    artifact_inventory = _build_artifact_inventory(clean_attachments)
    operation, operation_ref, operation_strength = _resolve_explicit_operation(
        clean_request,
        workflow_context,
        artifact_inventory,
    )

    external_requirement, external_domains = (
        _external_information_observation(
            clean_request,
            operation,
        )
    )
    source_evidence_dependency_observed = (
        _source_evidence_dependency_observed(
            raw_user_request=clean_request,
            operation=operation,
            artifact_inventory=artifact_inventory,
            environmental_ctx=clean_environment,
            external_requirement=external_requirement,
        )
    )
    document_requirement = _document_analysis_observation(
        raw_user_request=clean_request,
        operation=operation,
        operation_ref=operation_ref,
        artifact_inventory=artifact_inventory,
        workflow_context=workflow_context,
        external_requirement=external_requirement,
        source_evidence_dependency=source_evidence_dependency_observed,
        source_corpus_available=source_corpus_available,
    )
    skill_observation = _bei_skill_observation(
        workflow_context,
        workspace_context,
    )
    sufficiency, ambiguities = _sufficiency_observation(
        raw_user_request=clean_request,
        operation=operation,
        artifact_inventory=artifact_inventory,
        document_requirement=document_requirement,
        conversation_memory=conversation_memory,
        source_corpus_count=source_corpus_count,
    )

    semantic_domains = list(external_domains)

    if document_requirement.state == "required":
        semantic_domains.append("document_intelligence")

    if source_evidence_dependency_observed:
        semantic_domains.append("selected_source_evidence")

    if structured_evidence_matched:
        semantic_domains.append(
            "structured_business_evidence"
        )

    if skill_observation.applicability == "applicable":
        semantic_domains.extend(
            [
                "construction",
                "bid_scope_review",
            ]
        )

    if not semantic_domains:
        semantic_domains.append("general")

    positive_evidence = _positive_evidence(
        raw_user_request=clean_request,
        artifact_inventory=artifact_inventory,
        operation=operation,
        operation_ref=operation_ref,
        document_requirement=document_requirement,
        external_requirement=external_requirement,
        sufficiency=sufficiency,
        skill_observation=skill_observation,
        source_evidence_dependency_observed=(
            source_evidence_dependency_observed
        ),
        source_corpus_count=source_corpus_count,
        structured_evidence_packet=structured_packet,
    )
    negative_evidence = _negative_evidence(
        document_requirement=document_requirement,
        external_requirement=external_requirement,
        sufficiency=sufficiency,
        skill_observation=skill_observation,
    )

    evidence_strengths = [
        document_requirement.strength,
        external_requirement.strength,
        sufficiency.strength,
        skill_observation.strength,
    ]

    if operation:
        evidence_strengths.append(operation_strength)

    if source_evidence_dependency_observed:
        evidence_strengths.append(0.92)

    if source_corpus_available:
        evidence_strengths.append(1.0)

    if structured_evidence_matched:
        evidence_strengths.append(1.0)

    overall_strength = round(
        sum(evidence_strengths) / len(evidence_strengths),
        4,
    )

    observations = KnowledgeLayerObservations(
        raw_user_request=clean_request,
        artifact_inventory=artifact_inventory,
        semantic_domains=_unique(semantic_domains),
        explicit_requested_operation=operation,
        document_analysis_requirement=document_requirement,
        external_information_requirement=external_requirement,
        sufficiency=sufficiency,
        skill_lanes=[skill_observation],
        positive_evidence_refs=[
            item.ref_id
            for item in positive_evidence
        ],
        negative_evidence_refs=[
            item.indicator_id
            for item in negative_evidence
        ],
        overall_evidence_strength=overall_strength,
    )

    return KnowledgeObservationResult(
        observations=observations,
        positive_evidence=positive_evidence,
        negative_evidence=negative_evidence,
        ambiguities=ambiguities,
    )
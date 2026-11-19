# ------------------------------------------------------------------
# FILE: rag_lane_handler.py
# DIRECTORY: solomon_core/orchestrator_lanes/
# ------------------------------------------------------------------
# SolomonAI RAG Lane Handler
#
# PURPOSE
#   Execute an Orchestrator-authorized source-evidence request by retrieving
#   relevant chunks from authorized source resources and asking the bounded
#   local LLM to answer only from that evidence.
#
# CONTRACT
#   - Execution only
#   - No routing or lane selection
#   - No workflow authorization
#   - No attachment-presence routing
#   - Uses only authorized source resources supplied by execution_context
#   - Revalidates source resources against SQL query authority before use
#   - Retrieves only persisted, current-version Workspace Intelligence chunks
#   - Never re-extracts or re-embeds source files during an interactive query
#   - Uses hybrid semantic + BM25-style lexical retrieval with rank fusion
#   - Uses the LLM only to write from retrieved evidence
#   - Rejects unsupported numeric/date literals before response emission
#   - Marks explicit evidence-absence answers as not_established
# ------------------------------------------------------------------

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable

from config import settings

from solomon_core.db import SessionLocal
from solomon_core.intelligence_service.intelligence_service_contract import (
    build_opaque_fairness_bucket,
)
from solomon_core.intelligence_service.document_embedding_contract import (
    DOCUMENT_EMBEDDING_CHUNK_CHARS,
    DOCUMENT_EMBEDDING_CHUNK_OVERLAP,
    DOCUMENT_EMBEDDING_PROCESSOR_KEY,
    DOCUMENT_EMBEDDING_PROCESSOR_VERSION,
    DOCUMENT_EMBEDDING_SOURCE,
)
from solomon_core.llm.llm_execution_contract import (
    LLMExecutionInput,
    LLMExecutionMode,
    LLMResponseFormat,
)
from solomon_core.llm.llm_executor import execute_llm
from solomon_core.logger import get_logger
from solomon_core.models import (
    WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT,
    WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
    WorkspaceIntelligenceChunk,
    WorkspaceIntelligenceObject,
)
from solomon_core.solomon_tools.embedding_client import embed_text
from solomon_core.workspace_intelligence.workspace_intelligence_index import (
    WORKSPACE_INTELLIGENCE_READY_STATUS,
    clean_multiline_text,
    safe_metadata_payload,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    resolve_authorized_file_registry_entry,
)


logger = get_logger("rag_lane_handler")

_ASSISTANT_CALL_SITE = "solomon_assistant"
_ASSISTANT_MAX_NEW_TOKENS = 140
_TOP_K = 5
_RRF_K = 60.0
_BM25_K1 = 1.5
_BM25_B = 0.75
_QUERY_AUTHORIZATION_ACTION = "query"
_FOCUSED_EVIDENCE_MIN_QUERY_TERMS = 2
_FOCUSED_EVIDENCE_MAX_UNITS = 4
_FOCUSED_EVIDENCE_MAX_CHARS = 1200
_TEXT_GROUNDING_MIN_QUERY_TERMS = 4
_TEXT_GROUNDING_MAX_ANCHOR_TERMS = 4

_GROUNDED_NUMERIC_LITERAL_PATTERN = re.compile(
    r"(?:[$€£]\s*)?-?\d[\d,]*(?:\.\d+)?%?"
)

_DIRECT_GROUNDED_EVIDENCE_MAX_CHARS = 240

_NOT_ESTABLISHED_ANSWER_PATTERNS = (
    re.compile(
        r"\bnot established\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bnot listed in (?:the )?(?:available|authorized|provided|current) "
        r"(?:evidence|sources?)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\bno specific [^.\n]{0,100}\b(?:exists|is listed|is provided|"
        r"is stated)\b",
        flags=re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:could not|cannot) find\b",
        flags=re.IGNORECASE,
    ),
)

_SELECTED_SOURCE_STATUSES = {
    "conversation_selected",
}

_SELECTED_SOURCE_CONTRACTS = {
    "explicit_owned_conversation_sources",
}

_SOURCE_CORPUS_AUTHORITY_CONTRACTS = {
    "sql_authorized_file_corpus_v1",
}

_QUERY_STOPWORDS = {
    "a",
    "about",
    "access",
    "authorized",
    "company",
    "document",
    "documents",
    "file",
    "files",
    "from",
    "i",
    "know",
    "me",
    "my",
    "only",
    "source",
    "sources",
    "system",
    "tell",
    "the",
    "to",
    "using",
    "what",
}

_TEXT_GROUNDING_ANCHOR_STOPWORDS = {
    "also",
    "been",
    "being",
    "could",
    "does",
    "each",
    "have",
    "into",
    "more",
    "other",
    "should",
    "some",
    "such",
    "than",
    "that",
    "their",
    "them",
    "then",
    "there",
    "these",
    "they",
    "this",
    "those",
    "through",
    "very",
    "were",
    "which",
    "while",
    "with",
    "would",
}


@dataclass(frozen=True)
class SourceDocument:
    document_id: str
    file_registry_id: int
    source_hash: str
    version_number: int
    original_name: str
    source_scope: str


@dataclass(frozen=True)
class SourceChunk:
    chunk_id: str
    document_id: str
    original_name: str
    source_scope: str
    text: str
    vector: list[float]


@dataclass(frozen=True)
class RetrievalHit:
    chunk_id: str
    document_id: str
    original_name: str
    source_scope: str
    score: float
    vector_score: float
    keyword_boost: float
    text: str


def _safe_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _read_record_value(record: Any, *names: str) -> Any:
    for name in names:
        value = (
            record.get(name)
            if isinstance(record, dict)
            else getattr(record, name, None)
        )

        if value not in (None, ""):
            return value

    return None


def _current_user_id(
    execution_context: dict[str, Any],
) -> int:
    for key in (
        "current_user_id",
        "user_id",
    ):
        try:
            user_id = int(
                execution_context.get(key)
                or 0
            )
        except (TypeError, ValueError):
            user_id = 0

        if user_id:
            return user_id

    return 0


def _is_authorized_conversation_source(record: Any) -> bool:
    selected_for_conversation = bool(
        _read_record_value(record, "selected_for_conversation")
    )
    authorization_status = _safe_text(
        _read_record_value(record, "authorization_status")
    ).lower()
    handoff_contract = _safe_text(
        _read_record_value(record, "handoff_contract")
    ).lower()

    return bool(
        selected_for_conversation
        or authorization_status in _SELECTED_SOURCE_STATUSES
        or handoff_contract in _SELECTED_SOURCE_CONTRACTS
    )


def _source_corpus_authorized(
    execution_context: dict[str, Any],
) -> bool:
    authority = _safe_text(
        execution_context.get("source_corpus_authority")
    ).lower()

    return authority in _SOURCE_CORPUS_AUTHORITY_CONTRACTS


def _source_document_from_record(
    record: Any,
    *,
    source_scope: str,
) -> SourceDocument | None:
    document_id = _safe_text(
        _read_record_value(
            record,
            "document_id",
            "random_name",
            "file_id",
            "id",
        )
    )
    original_name = _safe_text(
        _read_record_value(
            record,
            "original_name",
            "filename",
            "name",
        )
    )

    try:
        file_registry_id = int(
            _read_record_value(
                record,
                "file_registry_id",
                "file_id",
                "id",
            )
            or 0
        )
    except (TypeError, ValueError):
        file_registry_id = 0

    try:
        version_number = int(
            _read_record_value(
                record,
                "version_number",
                "target_version",
            )
            or 0
        )
    except (TypeError, ValueError):
        version_number = 0

    source_hash = _safe_text(
        _read_record_value(
            record,
            "checksum",
            "source_hash",
        )
    )

    if not document_id:
        return None

    return SourceDocument(
        document_id=document_id,
        file_registry_id=file_registry_id,
        source_hash=source_hash,
        version_number=version_number,
        original_name=original_name or document_id,
        source_scope=source_scope,
    )


def _selected_source_documents(
    execution_context: dict[str, Any],
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []

    for record in _safe_list(execution_context.get("documents")):
        if not _is_authorized_conversation_source(record):
            continue

        document = _source_document_from_record(
            record,
            source_scope="selected_conversation_source",
        )

        if document:
            documents.append(document)

    return documents


def _corpus_source_documents(
    execution_context: dict[str, Any],
) -> list[SourceDocument]:
    if not _source_corpus_authorized(execution_context):
        return []

    documents: list[SourceDocument] = []

    for record in _safe_list(execution_context.get("source_corpus")):
        document = _source_document_from_record(
            record,
            source_scope=(
                _safe_text(
                    _read_record_value(record, "access_scope")
                )
                or "authorized_source_corpus"
            ),
        )

        if document:
            documents.append(document)

    return documents


def _authorized_source_documents(
    execution_context: dict[str, Any],
) -> list[SourceDocument]:
    documents: list[SourceDocument] = []
    seen: set[str] = set()

    for document in [
        *_selected_source_documents(execution_context),
        *_corpus_source_documents(execution_context),
    ]:
        if document.document_id in seen:
            continue

        documents.append(document)
        seen.add(document.document_id)

    return documents


def _revalidated_source_document(
    document: SourceDocument,
    *,
    user_id: int,
    request_id: str | None,
) -> SourceDocument | None:
    if not user_id:
        return None

    authorized_entry = resolve_authorized_file_registry_entry(
        user_id=user_id,
        identifier=document.document_id,
        request_id=request_id or "untracked",
        action=_QUERY_AUTHORIZATION_ACTION,
    )

    if not authorized_entry:
        logger.warning(
            "[RAG][SOURCE_REVALIDATION_DENIED] "
            "request_id=%s user_id=%s document_id=%s scope=%s",
            request_id,
            user_id,
            document.document_id,
            document.source_scope,
        )
        return None

    revalidated_document = _source_document_from_record(
        authorized_entry,
        source_scope=(
            _safe_text(
                authorized_entry.get("access_scope")
            )
            or document.source_scope
        ),
    )

    if not revalidated_document or not (
        revalidated_document.file_registry_id
        and revalidated_document.source_hash
        and revalidated_document.version_number > 0
    ):
        logger.warning(
            "[RAG][SOURCE_REVALIDATION_UNUSABLE] "
            "request_id=%s user_id=%s document_id=%s",
            request_id,
            user_id,
            document.document_id,
        )
        return None

    return revalidated_document


def _revalidated_source_documents(
    documents: Iterable[SourceDocument],
    *,
    user_id: int,
    request_id: str | None,
) -> list[SourceDocument]:
    revalidated: list[SourceDocument] = []
    seen: set[str] = set()

    for document in documents:
        revalidated_document = _revalidated_source_document(
            document,
            user_id=user_id,
            request_id=request_id,
        )

        if not revalidated_document:
            continue

        if revalidated_document.document_id in seen:
            continue

        revalidated.append(revalidated_document)
        seen.add(revalidated_document.document_id)

    return revalidated


def _revalidated_hits(
    hits: list[RetrievalHit],
    *,
    user_id: int,
    request_id: str | None,
) -> list[RetrievalHit]:
    revalidated: list[RetrievalHit] = []
    authorization_cache: dict[str, bool] = {}

    for hit in hits:
        if hit.document_id not in authorization_cache:
            authorization_cache[hit.document_id] = (
                resolve_authorized_file_registry_entry(
                    user_id=user_id,
                    identifier=hit.document_id,
                    request_id=request_id or "untracked",
                    action=_QUERY_AUTHORIZATION_ACTION,
                )
                is not None
            )

        if authorization_cache[hit.document_id]:
            revalidated.append(hit)
        else:
            logger.warning(
                "[RAG][HIT_REVALIDATION_DENIED] "
                "request_id=%s user_id=%s document_id=%s chunk_id=%s",
                request_id,
                user_id,
                hit.document_id,
                hit.chunk_id,
            )

    return revalidated


def _stable_hash(value: str) -> str:
    return hashlib.sha256(
        str(value or "").encode("utf-8")
    ).hexdigest()


def _embedding_model_key() -> str:
    return _safe_text(
        settings.WORKSPACE_ACTION_SELECTOR_MODEL_NAME
    )


def _embedding_checksum(
    *,
    content_hash: str,
    model_key: str,
    vector: list[float],
) -> str:
    payload = {
        "content_hash": content_hash,
        "embedding_contract": WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
        "model": model_key,
        "vector": [float(value) for value in vector],
    }
    return _stable_hash(
        json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
        )
    )


def _embedding_object_matches_document(
    intelligence_object: WorkspaceIntelligenceObject,
    document: SourceDocument,
) -> bool:
    metadata = safe_metadata_payload(
        intelligence_object.metadata_json
    )
    embedding_metadata = metadata.get(
        "document_embeddings"
    )

    if not isinstance(embedding_metadata, dict):
        return False

    return bool(
        intelligence_object.object_type == "file"
        and int(intelligence_object.file_registry_id or 0)
        == document.file_registry_id
        and intelligence_object.deleted_at is None
        and intelligence_object.status == "active"
        and intelligence_object.allow_ai_query is True
        and intelligence_object.embedding_status
        == WORKSPACE_INTELLIGENCE_READY_STATUS
        and _safe_text(intelligence_object.source_hash)
        == document.source_hash
        and _safe_text(intelligence_object.embedding_contract)
        == WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT
        and _safe_text(intelligence_object.embedding_model)
        == _embedding_model_key()
        and int(intelligence_object.embedding_dimension or 0)
        == int(settings.EMBED_DIM)
        and _safe_text(embedding_metadata.get("source"))
        == DOCUMENT_EMBEDDING_SOURCE
        and _safe_text(embedding_metadata.get("processor_key"))
        == DOCUMENT_EMBEDDING_PROCESSOR_KEY
        and _safe_text(embedding_metadata.get("processor_version"))
        == DOCUMENT_EMBEDDING_PROCESSOR_VERSION
        and _safe_text(embedding_metadata.get("source_hash"))
        == document.source_hash
        and int(embedding_metadata.get("target_version") or 0)
        == document.version_number
        and _safe_text(embedding_metadata.get("chunk_contract"))
        == WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT
        and _safe_text(embedding_metadata.get("embedding_contract"))
        == WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT
        and int(embedding_metadata.get("chunk_chars") or 0)
        == DOCUMENT_EMBEDDING_CHUNK_CHARS
        and int(embedding_metadata.get("chunk_overlap") or 0)
        == DOCUMENT_EMBEDDING_CHUNK_OVERLAP
    )


def _chunk_matches_document(
    row: WorkspaceIntelligenceChunk,
    document: SourceDocument,
) -> tuple[str, list[float]] | None:
    content = clean_multiline_text(row.content)
    content_hash = _safe_text(row.content_hash)
    model_key = _safe_text(row.embedding_model)
    vector = row.embedding_vector
    dimension = int(row.embedding_dimension or 0)
    checksum = _safe_text(row.embedding_checksum)
    row_metadata = safe_metadata_payload(row.metadata_json)
    locator = (
        dict(row.source_locator_json)
        if isinstance(row.source_locator_json, dict)
        else {}
    )

    try:
        locator_file_id = int(
            locator.get("file_registry_id")
            or 0
        )
        locator_version = int(
            locator.get("target_version")
            or 0
        )
    except (TypeError, ValueError):
        return None

    if not (
        content
        and content_hash
        and _stable_hash(content) == content_hash
        and _safe_text(row.chunk_id)
        and _safe_text(row.chunk_contract)
        == WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT
        and row.embedding_status == WORKSPACE_INTELLIGENCE_READY_STATUS
        and _safe_text(row.embedding_contract)
        == WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT
        and model_key == _embedding_model_key()
        and isinstance(vector, list)
        and vector
        and dimension == len(vector)
        and dimension == int(settings.EMBED_DIM)
        and checksum
        and _safe_text(row_metadata.get("source"))
        == DOCUMENT_EMBEDDING_SOURCE
        and _safe_text(row_metadata.get("processor_key"))
        == DOCUMENT_EMBEDDING_PROCESSOR_KEY
        and _safe_text(row_metadata.get("processor_version"))
        == DOCUMENT_EMBEDDING_PROCESSOR_VERSION
        and locator_file_id == document.file_registry_id
        and _safe_text(locator.get("document_id"))
        == document.document_id
        and _safe_text(locator.get("source_hash"))
        == document.source_hash
        and locator_version == document.version_number
    ):
        return None

    try:
        normalized_vector = [
            float(value)
            for value in vector
        ]
    except (TypeError, ValueError):
        return None

    if not all(math.isfinite(value) for value in normalized_vector):
        return None

    if _embedding_checksum(
        content_hash=content_hash,
        model_key=model_key,
        vector=normalized_vector,
    ) != checksum:
        return None

    return content, normalized_vector


def _source_chunks(
    documents: Iterable[SourceDocument],
) -> tuple[list[SourceChunk], set[str]]:
    document_list = list(documents)

    if not document_list:
        return [], set()

    documents_by_file_id = {
        document.file_registry_id: document
        for document in document_list
        if document.file_registry_id
    }

    if not documents_by_file_id:
        return [], set()

    db_session = SessionLocal()

    try:
        intelligence_objects = (
            db_session.query(WorkspaceIntelligenceObject)
            .filter(
                WorkspaceIntelligenceObject.object_type == "file",
                WorkspaceIntelligenceObject.file_registry_id.in_(
                    list(documents_by_file_id)
                ),
                WorkspaceIntelligenceObject.deleted_at.is_(None),
                WorkspaceIntelligenceObject.embedding_status
                == WORKSPACE_INTELLIGENCE_READY_STATUS,
                WorkspaceIntelligenceObject.embedding_contract
                == WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
                WorkspaceIntelligenceObject.embedding_model
                == _embedding_model_key(),
            )
            .all()
        )

        object_documents: dict[int, SourceDocument] = {}

        for intelligence_object in intelligence_objects:
            document = documents_by_file_id.get(
                int(intelligence_object.file_registry_id or 0)
            )

            if not document or not _embedding_object_matches_document(
                intelligence_object,
                document,
            ):
                continue

            object_documents[int(intelligence_object.id)] = document

        if not object_documents:
            return [], set()

        rows = (
            db_session.query(WorkspaceIntelligenceChunk)
            .filter(
                WorkspaceIntelligenceChunk.intelligence_object_id.in_(
                    list(object_documents)
                ),
                WorkspaceIntelligenceChunk.chunk_contract
                == WORKSPACE_INTELLIGENCE_CHUNK_CONTRACT,
                WorkspaceIntelligenceChunk.embedding_status
                == WORKSPACE_INTELLIGENCE_READY_STATUS,
                WorkspaceIntelligenceChunk.embedding_contract
                == WORKSPACE_INTELLIGENCE_EMBEDDING_CONTRACT,
                WorkspaceIntelligenceChunk.embedding_model
                == _embedding_model_key(),
                WorkspaceIntelligenceChunk.embedding_dimension
                == int(settings.EMBED_DIM),
            )
            .order_by(
                WorkspaceIntelligenceChunk.intelligence_object_id.asc(),
                WorkspaceIntelligenceChunk.chunk_order.asc(),
            )
            .all()
        )

        chunks: list[SourceChunk] = []
        ready_document_ids: set[str] = set()

        for row in rows:
            document = object_documents.get(
                int(row.intelligence_object_id or 0)
            )

            if not document:
                continue

            validated = _chunk_matches_document(
                row,
                document,
            )

            if not validated:
                logger.warning(
                    "[RAG][PERSISTED_CHUNK_REJECTED] "
                    "document_id=%s chunk_id=%s",
                    document.document_id,
                    row.chunk_id,
                )
                continue

            content, vector = validated
            chunks.append(
                SourceChunk(
                    chunk_id=_safe_text(row.chunk_id),
                    document_id=document.document_id,
                    original_name=document.original_name,
                    source_scope=document.source_scope,
                    text=content,
                    vector=vector,
                )
            )
            ready_document_ids.add(document.document_id)

        return chunks, ready_document_ids
    finally:
        db_session.close()


def _vector_norm(vector: list[float]) -> float:
    return math.sqrt(
        sum(float(value) * float(value) for value in vector)
    )


def _cosine(left: list[float], right: list[float]) -> float:
    left_norm = _vector_norm(left)
    right_norm = _vector_norm(right)

    if left_norm <= 0.0 or right_norm <= 0.0:
        return 0.0

    return sum(
        float(a) * float(b)
        for a, b in zip(left, right)
    ) / (left_norm * right_norm)


def _match_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(
            r"[a-z0-9]+",
            _safe_text(value).lower(),
        )
        if len(token) >= 3
    }


def _query_terms(query: str) -> set[str]:
    return {
        token
        for token in _match_tokens(query)
        if token not in _QUERY_STOPWORDS
    }


def _chunk_lexical_tokens(chunk: SourceChunk) -> list[str]:
    # Filename terms are included because exact resource-name matches are
    # useful in business retrieval, but the document body remains dominant.
    filename_tokens = list(_match_tokens(chunk.original_name))
    text_tokens = re.findall(
        r"[a-z0-9]+",
        _safe_text(chunk.text).lower(),
    )
    return [
        token
        for token in filename_tokens + text_tokens
        if len(token) >= 3
    ]


def _bm25_lexical_scores(
    query_terms: set[str],
    chunks: list[SourceChunk],
) -> dict[str, float]:
    if not query_terms or not chunks:
        return {
            chunk.chunk_id: 0.0
            for chunk in chunks
        }

    token_lists = {
        chunk.chunk_id: _chunk_lexical_tokens(chunk)
        for chunk in chunks
    }
    average_length = (
        sum(len(tokens) for tokens in token_lists.values())
        / max(1, len(token_lists))
    )
    average_length = max(1.0, float(average_length))

    document_frequency: dict[str, int] = {}
    for term in query_terms:
        document_frequency[term] = sum(
            1
            for tokens in token_lists.values()
            if term in set(tokens)
        )

    scores: dict[str, float] = {}
    document_count = len(chunks)

    for chunk in chunks:
        tokens = token_lists.get(chunk.chunk_id, [])
        token_count = max(1, len(tokens))
        frequencies: dict[str, int] = {}
        for token in tokens:
            if token in query_terms:
                frequencies[token] = frequencies.get(token, 0) + 1

        score = 0.0
        for term in query_terms:
            frequency = frequencies.get(term, 0)
            if frequency <= 0:
                continue

            df = document_frequency.get(term, 0)
            idf = math.log(
                1.0
                + (
                    (document_count - df + 0.5)
                    / (df + 0.5)
                )
            )
            length_norm = (
                1.0
                - _BM25_B
                + _BM25_B * (token_count / average_length)
            )
            numerator = frequency * (_BM25_K1 + 1.0)
            denominator = frequency + _BM25_K1 * length_norm
            score += idf * (numerator / max(denominator, 1e-9))

        # Exact filename overlap receives a modest lexical preference without
        # overwhelming body relevance.
        name_hits = query_terms & _match_tokens(chunk.original_name)
        if name_hits:
            score += 0.35 * len(name_hits)

        scores[chunk.chunk_id] = round(score, 6)

    return scores


def _reciprocal_rank(
    ordered_chunk_ids: list[str],
) -> dict[str, int]:
    return {
        chunk_id: rank
        for rank, chunk_id in enumerate(ordered_chunk_ids, start=1)
    }


def _retrieve(
    query: str,
    chunks: list[SourceChunk],
    *,
    request_id: str | None,
    fairness_bucket: str,
) -> list[RetrievalHit]:
    if not chunks:
        return []

    query_vector = embed_text(
        query,
        priority="P0",
        request_id=request_id,
        fairness_bucket=fairness_bucket,
    )
    terms = _query_terms(query)

    vector_scores = {
        chunk.chunk_id: round(
            _cosine(query_vector, chunk.vector),
            6,
        )
        for chunk in chunks
    }
    lexical_scores = _bm25_lexical_scores(
        terms,
        chunks,
    )

    semantic_order = sorted(
        chunks,
        key=lambda chunk: (
            vector_scores.get(chunk.chunk_id, 0.0),
            -len(chunk.text),
            chunk.chunk_id,
        ),
        reverse=True,
    )
    semantic_rank = _reciprocal_rank(
        [chunk.chunk_id for chunk in semantic_order]
    )

    lexical_candidates = [
        chunk
        for chunk in chunks
        if lexical_scores.get(chunk.chunk_id, 0.0) > 0.0
    ]
    lexical_candidates.sort(
        key=lambda chunk: (
            lexical_scores.get(chunk.chunk_id, 0.0),
            vector_scores.get(chunk.chunk_id, 0.0),
            chunk.chunk_id,
        ),
        reverse=True,
    )
    lexical_rank = _reciprocal_rank(
        [chunk.chunk_id for chunk in lexical_candidates]
    )

    scored: list[RetrievalHit] = []
    for chunk in chunks:
        semantic_component = 1.0 / (
            _RRF_K + float(semantic_rank[chunk.chunk_id])
        )
        lexical_component = 0.0
        if chunk.chunk_id in lexical_rank:
            lexical_component = 1.0 / (
                _RRF_K + float(lexical_rank[chunk.chunk_id])
            )

        final_score = round(
            semantic_component + lexical_component,
            8,
        )
        scored.append(
            RetrievalHit(
                chunk_id=chunk.chunk_id,
                document_id=chunk.document_id,
                original_name=chunk.original_name,
                source_scope=chunk.source_scope,
                score=final_score,
                vector_score=vector_scores.get(chunk.chunk_id, 0.0),
                keyword_boost=lexical_scores.get(chunk.chunk_id, 0.0),
                text=chunk.text,
            )
        )

    scored.sort(
        key=lambda hit: (
            hit.score,
            hit.vector_score,
            hit.keyword_boost,
        ),
        reverse=True,
    )

    logger.info(
        "[RAG][HYBRID_RETRIEVAL] request_id=%s chunks=%s top_k=%s "
        "query_terms=%s lexical_candidates=%s",
        request_id,
        len(chunks),
        _TOP_K,
        len(terms),
        len(lexical_candidates),
    )

    return scored[:_TOP_K]


def _evidence_units(value: str) -> list[str]:
    clean = _safe_text(value)

    if not clean:
        return []

    units: list[str] = []

    for raw_line in clean.splitlines():
        line = raw_line.strip().lstrip("-*\u2022").strip()

        if not line:
            continue

        sentence_parts = re.split(
            r"(?<=[.!?])\s+(?=[A-Z0-9])",
            line,
        )

        for sentence in sentence_parts:
            unit = _safe_text(sentence)

            if unit:
                units.append(unit)

    return units or [clean]


def _focused_evidence_text(
    query: str,
    evidence_text: str,
) -> str:
    """Narrow one retrieved chunk only when the question has strong lexical anchors.

    Retrieval remains semantic + lexical at the chunk boundary. This helper only
    reduces neighboring factual noise presented to the synthesis model when two
    or more meaningful query terms identify specific factual units. If no strong
    unit-level anchor exists, the complete retrieved chunk is preserved.
    """

    clean_evidence = _safe_text(evidence_text)
    query_terms = _query_terms(query)

    if not clean_evidence or not query_terms:
        return clean_evidence

    units = _evidence_units(clean_evidence)
    scored_units: list[tuple[int, int, str]] = []

    for index, unit in enumerate(units):
        overlap_count = len(
            query_terms & _match_tokens(unit)
        )

        if overlap_count >= _FOCUSED_EVIDENCE_MIN_QUERY_TERMS:
            scored_units.append((
                overlap_count,
                index,
                unit,
            ))

    if not scored_units:
        return clean_evidence

    strongest = sorted(
        scored_units,
        key=lambda item: (
            item[0],
            -item[1],
        ),
        reverse=True,
    )[:_FOCUSED_EVIDENCE_MAX_UNITS]
    strongest.sort(key=lambda item: item[1])

    focused = "\n".join(
        item[2]
        for item in strongest
    ).strip()

    if not focused:
        return clean_evidence

    return focused[:_FOCUSED_EVIDENCE_MAX_CHARS]


def _text_grounding_anchor_fallback(
    *,
    query: str,
    answer: str,
    evidence_texts: Iterable[str],
) -> str:
    """Return exact evidence only for a narrow high-confidence term mutation.

    This guard is intentionally conservative. It applies only when one concise
    evidence unit strongly overlaps the user's question and contributes a small
    set of distinctive answer terms that are absent from the question itself.
    If the model drops or mutates one of those terms, returning the exact
    authorized evidence unit is safer than accepting a near-miss paraphrase.
    """

    query_terms = _query_terms(query)

    if len(query_terms) < _TEXT_GROUNDING_MIN_QUERY_TERMS:
        return ""

    candidates: list[tuple[int, int, int, str, set[str]]] = []

    for evidence_index, evidence_text in enumerate(evidence_texts):
        for unit_index, unit in enumerate(_evidence_units(evidence_text)):
            clean_unit = _safe_text(unit)

            if (
                not clean_unit
                or len(clean_unit) > _DIRECT_GROUNDED_EVIDENCE_MAX_CHARS
            ):
                continue

            unit_terms = _match_tokens(clean_unit)
            overlap_count = len(query_terms & unit_terms)

            if overlap_count < _TEXT_GROUNDING_MIN_QUERY_TERMS:
                continue

            anchor_terms = {
                token
                for token in (unit_terms - query_terms)
                if (
                    len(token) >= 4
                    and token not in _TEXT_GROUNDING_ANCHOR_STOPWORDS
                )
            }

            if not (
                1
                <= len(anchor_terms)
                <= _TEXT_GROUNDING_MAX_ANCHOR_TERMS
            ):
                continue

            candidates.append((
                overlap_count,
                -len(anchor_terms),
                -(evidence_index * 1000 + unit_index),
                clean_unit,
                anchor_terms,
            ))

    if not candidates:
        return ""

    _, _, _, strongest_unit, anchor_terms = max(
        candidates,
        key=lambda item: (
            item[0],
            item[1],
            item[2],
        ),
    )
    answer_terms = _match_tokens(answer)

    if anchor_terms <= answer_terms:
        return ""

    return strongest_unit


def _build_prompt(
    query: str,
    hits: list[RetrievalHit],
) -> str:
    evidence = []

    for index, hit in enumerate(hits, start=1):
        evidence.extend([
            f"[EVIDENCE {index}]",
            f"source_name: {hit.original_name}",
            f"source_scope: {hit.source_scope}",
            f"chunk_id: {hit.chunk_id}",
            f"text: {_focused_evidence_text(query, hit.text)}",
            "",
        ])

    return "\n".join([
        "Answer using ONLY the currently retrieval-ready authorized source evidence below.",
        "Do not use outside knowledge or unauthorized files.",
        "Do not invent facts, numbers, names, dates, or source titles.",
        "Treat each evidence statement as an independent factual unit; preserve which subject each predicate, responsibility, exclusion, requirement, date, amount, or condition belongs to.",
        "Never transfer a fact or qualifier from one evidence statement to a different subject merely because the statements are nearby in the same chunk.",
        "Preserve distinctive source terms verbatim when they identify the answer, especially named responsibilities, items, entities, labels, or technical terms.",
        "Copy numeric and date values exactly from the evidence; do not alter, estimate, interpolate, or create them.",
        "Do not claim this evidence exhaustively represents every authorized file.",
        "If the evidence does not establish the answer, say that it is not established in the authorized sources.",
        "Write plain text only. Do not return JSON. Do not include code fences.",
        "Use 2 to 4 concise sentences.",
        "Do not include a Sources line or invent source filenames; Solomon adds authorized source provenance deterministically after retrieval.",
        "",
        "QUESTION:",
        query,
        "",
        "AUTHORIZED SOURCE EVIDENCE:",
        *evidence,
    ]).strip()


def _recover_jsonish_answer(raw_text: str) -> str:
    clean = _safe_text(raw_text)

    if not clean.startswith("{"):
        return clean

    try:
        parsed = json.loads(clean)

        if isinstance(parsed, dict):
            return _safe_text(
                parsed.get("answer")
                or parsed.get("a")
                or clean
            )
    except Exception:
        pass

    match = re.search(
        r'"(?:answer|a)"\s*:\s*"((?:\\.|[^"\\])*)"',
        clean,
        flags=re.DOTALL,
    )

    if not match:
        return clean

    try:
        return json.loads(
            f'"{match.group(1)}"'
        ).strip()
    except Exception:
        return match.group(1).strip()


def _strip_model_source_footer(answer: str) -> str:
    lines = _safe_text(answer).splitlines()

    while lines and not _safe_text(lines[-1]):
        lines.pop()

    if lines and re.match(
        r"^\s*sources?\s*:",
        lines[-1],
        flags=re.IGNORECASE,
    ):
        lines.pop()

    return "\n".join(lines).strip()


def _authorized_source_names(
    hits: Iterable[RetrievalHit],
) -> list[str]:
    names: list[str] = []
    seen: set[str] = set()

    for hit in hits:
        name = _safe_text(hit.original_name)

        if not name or name in seen:
            continue

        names.append(name)
        seen.add(name)

    return names


def _answer_with_authorized_sources(
    answer: str,
    hits: Iterable[RetrievalHit],
) -> str:
    clean_answer = _strip_model_source_footer(answer)
    source_names = _authorized_source_names(hits)

    if not source_names:
        return clean_answer

    source_footer = f"Sources: {', '.join(source_names)}"

    if not clean_answer:
        return source_footer

    return f"{clean_answer}\n{source_footer}"


def _normalized_numeric_literal(value: str) -> str:
    clean = _safe_text(value).replace(",", "").replace(" ", "")

    while clean[:1] in {"$", "€", "£"}:
        clean = clean[1:]

    percent = clean.endswith("%")

    if percent:
        clean = clean[:-1]

    sign = ""

    if clean.startswith("-"):
        sign = "-"
        clean = clean[1:]

    if "." in clean:
        whole, decimal = clean.split(".", 1)
        whole = whole.lstrip("0") or "0"
        decimal = decimal.rstrip("0")
        clean = (
            f"{whole}.{decimal}"
            if decimal
            else whole
        )
    else:
        clean = clean.lstrip("0") or "0"

    return (
        f"{sign}{clean}%"
        if percent
        else f"{sign}{clean}"
    )


def _numeric_literals(value: str) -> list[str]:
    return [
        match.group(0)
        for match in _GROUNDED_NUMERIC_LITERAL_PATTERN.finditer(
            _safe_text(value)
        )
    ]


def _unsupported_numeric_literals(
    *,
    answer: str,
    query: str,
    hits: list[RetrievalHit],
) -> list[str]:
    allowed_values = {
        _normalized_numeric_literal(literal)
        for literal in _numeric_literals(query)
    }

    for hit in hits:
        allowed_values.update(
            _normalized_numeric_literal(literal)
            for literal in _numeric_literals(
                hit.text
            )
        )

    unsupported: list[str] = []
    seen: set[str] = set()

    for literal in _numeric_literals(answer):
        normalized = _normalized_numeric_literal(
            literal
        )

        if normalized in allowed_values:
            continue

        if normalized in seen:
            continue

        unsupported.append(literal)
        seen.add(normalized)

    return unsupported


def _answer_support_status(answer: str) -> str:
    clean_answer = _safe_text(answer)

    if not clean_answer:
        return "not_established"

    if any(
        pattern.search(clean_answer)
        for pattern in _NOT_ESTABLISHED_ANSWER_PATTERNS
    ):
        return "not_established"

    return "supported"


def _numeric_grounding_fallback_answer(
    hits: list[RetrievalHit],
) -> str:
    snippet = _safe_text(
        hits[0].text if hits else ""
    )[:480]

    if (
        snippet
        and len(snippet)
        <= _DIRECT_GROUNDED_EVIDENCE_MAX_CHARS
    ):
        return snippet

    if snippet:
        return (
            "I found relevant authorized evidence, but I could not safely "
            "produce a narrative answer without introducing unsupported "
            "numeric or date details. Strongest retrieved evidence excerpt: "
            f"{snippet}"
        )

    return (
        "I found authorized evidence, but I could not safely produce a "
        "narrative answer without introducing unsupported numeric or date "
        "details."
    )


def _supporting_hits_for_answer(
    *,
    answer: str,
    query: str,
    hits: list[RetrievalHit],
) -> list[RetrievalHit]:
    query_values = {
        _normalized_numeric_literal(literal)
        for literal in _numeric_literals(query)
    }
    evidence_derived_values = {
        _normalized_numeric_literal(literal)
        for literal in _numeric_literals(answer)
    } - query_values

    if not evidence_derived_values:
        return hits

    supporting_hits = []

    for hit in hits:
        hit_values = {
            _normalized_numeric_literal(literal)
            for literal in _numeric_literals(hit.text)
        }

        if evidence_derived_values & hit_values:
            supporting_hits.append(hit)

    return supporting_hits or hits


def _deterministic_fallback_answer(
    hits: list[RetrievalHit],
) -> str:
    source_names = []
    seen = set()

    for hit in hits:
        if hit.original_name in seen:
            continue

        source_names.append(hit.original_name)
        seen.add(hit.original_name)

        if len(source_names) == 3:
            break

    lead_source = (
        ", ".join(source_names)
        if source_names
        else "the authorized sources"
    )
    snippet = _safe_text(
        hits[0].text if hits else ""
    )[:320]

    if snippet:
        return (
            f"I found relevant evidence in {lead_source}, but the model did "
            f"not return a clean narrative answer. Strongest retrieved "
            f"evidence excerpt: {snippet}"
        )

    return (
        "I found authorized evidence, but I could not produce a clean "
        "narrative answer from it."
    )


def _llm_answer(
    query: str,
    hits: list[RetrievalHit],
    *,
    request_id: str | None,
    fairness_bucket: str,
) -> dict[str, Any]:
    prompt = _build_prompt(query, hits)
    result = execute_llm(
        LLMExecutionInput(
            user_query=prompt,
            mode=LLMExecutionMode.INFORMATIONAL_ONLY,
            context=None,
            response_format=LLMResponseFormat.TEXT,
            call_site=_ASSISTANT_CALL_SITE,
            max_new_tokens=_ASSISTANT_MAX_NEW_TOKENS,
            timeout_seconds=45,
        ),
        priority="P0",
        request_id=request_id,
        fairness_bucket=fairness_bucket,
    )

    output_text = ""

    if result and result.output:
        output_text = _safe_text(
            getattr(result.output, "text", "")
        )

    answer = _strip_model_source_footer(
        _recover_jsonish_answer(
            output_text
        )
    )

    if not answer or len(answer) < 20:
        answer = _deterministic_fallback_answer(
            hits
        )

    text_grounding_fallback = _text_grounding_anchor_fallback(
        query=query,
        answer=answer,
        evidence_texts=[
            hit.text
            for hit in hits
        ],
    )

    if text_grounding_fallback:
        logger.warning(
            "[RAG][TEXT_GROUNDING_GUARD] "
            "model_answer=%r fallback=%r hits=%s",
            answer[:240],
            text_grounding_fallback[:240],
            len(hits),
        )
        answer = text_grounding_fallback

    unsupported_numeric_literals = (
        _unsupported_numeric_literals(
            answer=answer,
            query=query,
            hits=hits,
        )
    )

    if unsupported_numeric_literals:
        logger.warning(
            "[RAG][NUMERIC_GROUNDING_GUARD] unsupported=%s hits=%s",
            unsupported_numeric_literals,
            len(hits),
        )
        answer = _numeric_grounding_fallback_answer(
            hits
        )

    return {
        "answer": answer,
        "support_status": _answer_support_status(
            answer
        ),
        "used_chunk_ids": [
            hit.chunk_id
            for hit in hits
        ],
        "raw_output_chars": len(output_text),
    }


def _source_payload(hits: list[RetrievalHit]) -> list[dict[str, Any]]:
    sources = []

    for hit in hits:
        sources.append({
            "document_id": hit.document_id,
            "source_name": hit.original_name,
            "source_scope": hit.source_scope,
            "chunk_id": hit.chunk_id,
            "score": hit.score,
            "vector_score": hit.vector_score,
            "keyword_boost": hit.keyword_boost,
        })

    return sources


def run_rag_lane(
    *,
    task_text: str,
    execution_context: dict[str, Any],
    casefile=None,
    conversation_id: str | None = None,
    request_id: str | None = None,
) -> dict[str, Any]:
    """
    Execute authorized-source RAG after Orchestrator lane selection.
    """

    del casefile

    context = _safe_dict(execution_context)
    query = _safe_text(
        task_text
        or context.get("task_text")
        or context.get("raw_user_input")
    )
    user_id = _current_user_id(context)

    supplied_documents = _authorized_source_documents(context)
    documents = _revalidated_source_documents(
        supplied_documents,
        user_id=user_id,
        request_id=request_id,
    )

    logger.info(
        "[RAG][START] request_id=%s conversation_id=%s "
        "source_docs=%s revalidated_docs=%s corpus_authorized=%s "
        "corpus_count=%s user_id=%s",
        request_id,
        conversation_id,
        len(supplied_documents),
        len(documents),
        _source_corpus_authorized(context),
        len(_safe_list(context.get("source_corpus"))),
        user_id,
    )

    if not documents:
        return {
            "answer": (
                "I could not find an authorized company file source to answer "
                "from."
            ),
            "support_status": "not_established",
            "source_grounded": True,
            "sources": [],
            "used_chunk_ids": [],
            "retrieval_readiness": {
                "authorized_documents": 0,
                "ready_documents": 0,
                "pending_documents": 0,
            },
        }

    chunks, ready_document_ids = _source_chunks(documents)
    pending_document_count = max(
        0,
        len(documents) - len(ready_document_ids),
    )

    logger.info(
        "[RAG][PERSISTED_EVIDENCE_READY] request_id=%s "
        "authorized_docs=%s ready_docs=%s pending_docs=%s chunks=%s model=%s",
        request_id,
        len(documents),
        len(ready_document_ids),
        pending_document_count,
        len(chunks),
        _embedding_model_key(),
    )

    fairness_bucket = build_opaque_fairness_bucket(
        conversation_id or user_id,
        namespace="conversation",
    )
    hits = _retrieve(
        query,
        chunks,
        request_id=request_id,
        fairness_bucket=fairness_bucket,
    )
    hits = _revalidated_hits(
        hits,
        user_id=user_id,
        request_id=request_id,
    )

    if not hits:
        return {
            "answer": (
                "I could not find supporting information in the currently "
                "retrieval-ready authorized sources."
            ),
            "support_status": "not_established",
            "source_grounded": True,
            "sources": [],
            "used_chunk_ids": [],
            "retrieval_readiness": {
                "authorized_documents": len(documents),
                "ready_documents": len(ready_document_ids),
                "pending_documents": pending_document_count,
            },
        }

    llm_payload = _llm_answer(
        query,
        hits,
        request_id=request_id,
        fairness_bucket=fairness_bucket,
    )

    final_hits = _revalidated_hits(
        hits,
        user_id=user_id,
        request_id=request_id,
    )

    if not final_hits:
        logger.warning(
            "[RAG][FINAL_REVALIDATION_EMPTY] request_id=%s user_id=%s",
            request_id,
            user_id,
        )
        return {
            "answer": (
                "I could not find supporting information in the authorized "
                "sources."
            ),
            "support_status": "not_established",
            "source_grounded": True,
            "sources": [],
            "used_chunk_ids": [],
            "retrieval_readiness": {
                "authorized_documents": len(documents),
                "ready_documents": len(ready_document_ids),
                "pending_documents": pending_document_count,
            },
        }

    supporting_hits = _supporting_hits_for_answer(
        answer=llm_payload["answer"],
        query=query,
        hits=final_hits,
    )
    supporting_chunk_ids = {
        hit.chunk_id
        for hit in supporting_hits
    }

    payload = {
        "answer": _answer_with_authorized_sources(
            llm_payload["answer"],
            supporting_hits,
        ),
        "support_status": llm_payload["support_status"],
        "source_grounded": True,
        "sources": _source_payload(supporting_hits),
        "used_chunk_ids": [
            chunk_id
            for chunk_id in llm_payload["used_chunk_ids"]
            if chunk_id in supporting_chunk_ids
        ],
        "retrieval_readiness": {
            "authorized_documents": len(documents),
            "ready_documents": len(ready_document_ids),
            "pending_documents": pending_document_count,
        },
    }

    logger.info(
        "[RAG][OK] request_id=%s docs=%s chunks=%s hits=%s "
        "final_hits=%s supporting_hits=%s answer_chars=%s",
        request_id,
        len(documents),
        len(chunks),
        len(hits),
        len(final_hits),
        len(supporting_hits),
        len(payload["answer"]),
    )

    return payload
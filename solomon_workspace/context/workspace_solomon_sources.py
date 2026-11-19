# -------------------------------------------------------------------
# FILE: workspace_solomon_sources.py
# DIRECTORY: solomon_workspace/context/
# -------------------------------------------------------------------
# Permission-aware source resolution helpers for SolomonAI.
# This module validates source payloads and resolves user-owned files
# through the canonical SQL FileRegistry. It does not execute AI,
# mutate workspace state, or shape assistant responses.
# -------------------------------------------------------------------

import json
import os
from typing import Any, Dict, List, Optional, Tuple

from solomon_core.db import SessionLocal
from solomon_core.models import FileRegistry


FILE_ID_KEYS = (
    "document_id",
    "documentId",
    "file_id",
    "fileId",
    "id",
    "opaque_id",
    "opaqueId",
    "random_name",
    "stored_name",
)

WORKSPACE_SOLOMON_SOURCE_BRIEFING_REQUEST_TYPES = {
    "source_briefing",
    "source-briefing",
    "source_summary",
    "source-summary",
    "source_context",
    "source-context",
}

TRASH_STATUS_VALUES = {
    "trash",
    "trashed",
    "deleted",
}

ACTIVE_STATUS_VALUES = {
    "active",
    "available",
    "stored",
    "ready",
    "uploaded",
}


def unique_workspace_source_values(
    values: List[Any],
) -> List[str]:
    """Return unique, non-empty source identifiers in payload order."""

    seen = set()
    unique_values = []

    for value in values or []:
        clean_value = str(
            value or ""
        ).strip()

        if (
            not clean_value
            or clean_value in seen
        ):
            continue

        seen.add(clean_value)
        unique_values.append(
            clean_value
        )

    return unique_values


def normalize_workspace_solomon_source_mode(
    value: Any,
) -> str:
    """Normalize source mode from payload or browser source state."""

    clean_value = str(
        value or ""
    ).strip().lower()

    if clean_value in {
        "file",
        "selection",
        "trash",
    }:
        return clean_value

    return "workspace"


def get_workspace_solomon_source_context(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """Read source_context/sourceContext from a SolomonAI payload."""

    source_context = payload.get(
        "source_context"
    )

    if isinstance(
        source_context,
        dict,
    ):
        return source_context

    source_context = payload.get(
        "sourceContext"
    )

    if isinstance(
        source_context,
        dict,
    ):
        return source_context

    return {}


def get_workspace_solomon_context_mode(
    payload: Dict[str, Any],
) -> str:
    """Return the normalized source context mode."""

    source_context = (
        get_workspace_solomon_source_context(
            payload
        )
    )

    return normalize_workspace_solomon_source_mode(
        payload.get("mode")
        or payload.get("context_mode")
        or payload.get("contextMode")
        or source_context.get("mode")
        or source_context.get(
            "context_mode"
        )
        or source_context.get(
            "contextMode"
        )
    )


def get_workspace_solomon_request_type(
    payload: Dict[str, Any],
) -> str:
    """Return the normalized SolomonAI request type."""

    source_context = (
        get_workspace_solomon_source_context(
            payload
        )
    )

    return str(
        payload.get("request_type")
        or payload.get("requestType")
        or payload.get("intent")
        or source_context.get(
            "request_type"
        )
        or source_context.get(
            "requestType"
        )
        or ""
    ).strip().lower()


def is_workspace_solomon_source_briefing_request(
    payload: Dict[str, Any],
) -> bool:
    """Return whether the payload requests a passive source briefing."""

    return (
        get_workspace_solomon_request_type(
            payload
        )
        in WORKSPACE_SOLOMON_SOURCE_BRIEFING_REQUEST_TYPES
    )


def get_workspace_solomon_source_ids(
    payload: Dict[str, Any],
    *,
    max_source_count: int = 8,
) -> List[str]:
    """Extract candidate source ids from supported payload shapes."""

    source_context = (
        get_workspace_solomon_source_context(
            payload
        )
    )
    candidate_values = []

    for key in (
        "document_id",
        "documentId",
        "source_id",
        "sourceId",
    ):
        value = (
            payload.get(key)
            or source_context.get(key)
        )

        if value:
            candidate_values.append(
                value
            )

    for key in (
        "document_ids",
        "documentIds",
        "source_ids",
        "sourceIds",
        "selected_document_ids",
        "selectedDocumentIds",
    ):
        values = (
            payload.get(key)
            or source_context.get(key)
        )

        if isinstance(
            values,
            list,
        ):
            candidate_values.extend(
                values
            )

    for key in (
        "files",
        "selectedFiles",
        "selection",
    ):
        values = (
            source_context.get(key)
            or payload.get(key)
        )

        if not isinstance(
            values,
            list,
        ):
            continue

        for item in values:
            if isinstance(
                item,
                dict,
            ):
                candidate_values.append(
                    item.get("id")
                    or item.get(
                        "document_id"
                    )
                    or item.get(
                        "documentId"
                    )
                    or item.get(
                        "file_id"
                    )
                    or item.get(
                        "fileId"
                    )
                    or item.get(
                        "opaque_id"
                    )
                    or item.get(
                        "opaqueId"
                    )
                )
            else:
                candidate_values.append(
                    item
                )

    return unique_workspace_source_values(
        candidate_values
    )[:max_source_count]


def has_workspace_solomon_trash_context(
    payload: Dict[str, Any],
) -> bool:
    """Return whether browser source state indicates Trash context."""

    source_context = (
        get_workspace_solomon_source_context(
            payload
        )
    )
    mode = get_workspace_solomon_context_mode(
        payload
    )
    location = str(
        payload.get("location")
        or payload.get("collection")
        or source_context.get(
            "location"
        )
        or source_context.get(
            "collection"
        )
        or ""
    ).strip().lower()

    if (
        mode == "trash"
        or location == "trash"
    ):
        return True

    for key in (
        "files",
        "selectedFiles",
        "selection",
    ):
        values = (
            source_context.get(key)
            or payload.get(key)
        )

        if not isinstance(
            values,
            list,
        ):
            continue

        for item in values:
            if not isinstance(
                item,
                dict,
            ):
                continue

            if (
                item.get("isTrash") is True
                or item.get(
                    "is_trash"
                ) is True
                or item.get(
                    "trashed"
                ) is True
            ):
                return True

    return False


def _safe_meta_payload(
    value: Any,
) -> Dict[str, Any]:
    """Return FileRegistry metadata as a safe dictionary."""

    if isinstance(
        value,
        dict,
    ):
        return dict(value)

    if isinstance(
        value,
        str,
    ):
        try:
            parsed = json.loads(value)
        except (
            TypeError,
            ValueError,
        ):
            return {}

        if isinstance(
            parsed,
            dict,
        ):
            return parsed

    return {}


def _truthy_payload_flag(
    value: Any,
) -> bool:
    """Return whether a stored metadata flag is enabled."""

    if isinstance(
        value,
        bool,
    ):
        return value

    if isinstance(
        value,
        str,
    ):
        return (
            value.strip().lower()
            in {
                "1",
                "true",
                "yes",
                "on",
            }
        )

    return bool(value)


def get_file_registry_status(
    resolved: Dict[str, Any],
) -> str:
    """Return the normalized status of a FileRegistry source."""

    if not resolved:
        return ""

    return str(
        resolved.get(
            "document_status"
        )
        or resolved.get(
            "library_status"
        )
        or resolved.get(
            "storage_status"
        )
        or resolved.get("status")
        or resolved.get("mode")
        or ""
    ).strip().lower()


def is_resolved_file_in_trash(
    resolved: Dict[str, Any],
) -> bool:
    """Return whether a resolved FileRegistry source is in Trash."""

    if not resolved:
        return False

    status = get_file_registry_status(
        resolved
    )

    if status in TRASH_STATUS_VALUES:
        return True

    if (
        _truthy_payload_flag(
            resolved.get("trashed")
        )
        or _truthy_payload_flag(
            resolved.get("is_trash")
        )
        or _truthy_payload_flag(
            resolved.get("in_trash")
        )
        or _truthy_payload_flag(
            resolved.get("deleted")
        )
        or bool(
            resolved.get(
                "deleted_at"
            )
        )
        or bool(
            resolved.get(
                "trashed_at"
            )
        )
    ):
        return True

    if status in ACTIVE_STATUS_VALUES:
        return False

    return False


def _file_registry_record_payload(
    record: FileRegistry,
) -> Dict[str, Any]:
    """Build an internal source-resolution payload from one SQL row."""

    metadata = _safe_meta_payload(
        record.meta
    )
    path = str(
        record.path or ""
    ).strip()
    document_id = str(
        record.random_name or ""
    ).strip()

    return {
        **metadata,
        "document_id": document_id,
        "random_name": document_id,
        "file_id": str(record.id),
        "id": str(record.id),
        "original_name": str(
            record.original_name
            or document_id
        ).strip(),
        "extension": str(
            record.extension or ""
        ).strip(),
        "path": path,
        "size_bytes": record.size_bytes,
        "checksum": record.checksum,
        "uploader_id": record.uploader_id,
    }


def get_file_entry_match_values(
    entry: Dict[str, Any],
) -> set:
    """Return stable values that may identify a stored source."""

    values = set()

    for key in FILE_ID_KEYS:
        value = str(
            entry.get(key)
            or ""
        ).strip()

        if value:
            values.add(value)

    path = str(
        entry.get("path")
        or ""
    ).strip()

    if path:
        basename = os.path.basename(
            path
        )
        stem, _extension = os.path.splitext(
            basename
        )

        if basename:
            values.add(basename)

        if stem:
            values.add(stem)

    return values


def load_owned_file_entries(
    user_id: int,
) -> List[Dict[str, Any]]:
    """Load user-owned FileRegistry records for source resolution."""

    if not user_id:
        return []

    db_session = SessionLocal()

    try:
        records = (
            db_session.query(
                FileRegistry
            )
            .filter(
                FileRegistry.uploader_id
                == user_id
            )
            .all()
        )

        return [
            _file_registry_record_payload(
                record
            )
            for record in records
        ]
    finally:
        db_session.close()


def build_owned_file_index(
    entries: List[Dict[str, Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """Build an identifier index for owned FileRegistry records."""

    index: Dict[
        str,
        List[Dict[str, Any]],
    ] = {}

    for entry in entries or []:
        for value in get_file_entry_match_values(
            entry
        ):
            index.setdefault(
                value,
                [],
            ).append(entry)

    return index


def score_workspace_solomon_file_candidate(
    entry: Dict[str, Any],
) -> int:
    """Rank active, existing SQL records ahead of stale records."""

    score = 0

    if is_resolved_file_in_trash(
        entry
    ):
        score += 100

    path = str(
        entry.get("path")
        or ""
    ).strip()

    if (
        not path
        or not os.path.isfile(path)
    ):
        score += 1000

    return score


def resolve_workspace_solomon_owned_file(
    user_id: int,
    document_id: str,
    *,
    owned_file_index: Optional[
        Dict[str, List[Dict[str, Any]]]
    ] = None,
) -> Optional[Dict[str, Any]]:
    """Resolve one source id to an owned FileRegistry record."""

    clean_document_id = str(
        document_id or ""
    ).strip()

    if (
        not user_id
        or not clean_document_id
    ):
        return None

    if owned_file_index is None:
        owned_file_index = (
            build_owned_file_index(
                load_owned_file_entries(
                    user_id
                )
            )
        )

    candidates = list(
        owned_file_index.get(
            clean_document_id,
            [],
        )
    )

    if not candidates:
        return None

    resolved = sorted(
        candidates,
        key=(
            score_workspace_solomon_file_candidate
        ),
    )[0]

    path = str(
        resolved.get("path")
        or ""
    ).strip()

    if (
        not path
        or not os.path.isfile(path)
    ):
        return None

    return resolved


def build_workspace_solomon_source_record(
    requested_document_id: str,
    resolved: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the internal source record used by SolomonAI."""

    canonical_document_id = str(
        resolved.get("document_id")
        or resolved.get(
            "random_name"
        )
        or requested_document_id
    ).strip()
    original_name = str(
        resolved.get("original_name")
        or resolved.get("filename")
        or resolved.get("name")
        or canonical_document_id
    ).strip()
    path = str(
        resolved.get("path")
        or ""
    ).strip()
    extension = str(
        resolved.get("extension")
        or os.path.splitext(
            original_name or path
        )[1]
    ).lstrip(".").upper()
    source_in_trash = (
        is_resolved_file_in_trash(
            resolved
        )
    )
    registry_active = resolved.get(
        "active"
    )

    return {
        "document_id": (
            canonical_document_id
        ),
        "file_id": str(
            resolved.get("file_id")
            or resolved.get("id")
            or ""
        ).strip(),
        "name": (
            original_name
            or canonical_document_id
        ),
        "extension": extension,
        "mime_type": str(
            resolved.get("mime_type")
            or ""
        ).strip(),
        "size_bytes": resolved.get(
            "size_bytes"
        ),
        "active": not source_in_trash,
        "registry_active": (
            registry_active
            if isinstance(
                registry_active,
                bool,
            )
            else None
        ),
        "in_trash": source_in_trash,
        "fast_lane_available": (
            not source_in_trash
        ),
        "metadata_only": False,
        "_source_path": (
            os.path.abspath(path)
            if path
            else ""
        ),
    }


def resolve_workspace_solomon_sources(
    payload: Dict[str, Any],
    *,
    user_id: int,
    max_source_count: int = 8,
) -> Tuple[
    List[Dict[str, Any]],
    List[str],
    bool,
]:
    """Resolve connected sources with SQL ownership checks."""

    source_ids = get_workspace_solomon_source_ids(
        payload,
        max_source_count=max_source_count,
    )
    owned_file_index = (
        build_owned_file_index(
            load_owned_file_entries(
                user_id
            )
        )
    )
    sources = []
    missing_ids = []
    has_server_trash_source = False

    for document_id in source_ids:
        resolved = (
            resolve_workspace_solomon_owned_file(
                user_id,
                document_id,
                owned_file_index=(
                    owned_file_index
                ),
            )
        )

        if not resolved:
            missing_ids.append(
                document_id
            )
            continue

        if is_resolved_file_in_trash(
            resolved
        ):
            has_server_trash_source = True

        sources.append(
            build_workspace_solomon_source_record(
                document_id,
                resolved,
            )
        )

    return (
        sources,
        missing_ids,
        has_server_trash_source,
    )


def sanitize_workspace_solomon_source_record(
    source: Dict[str, Any],
) -> Dict[str, Any]:
    """Remove internal-only keys before records leave the server."""

    if not isinstance(
        source,
        dict,
    ):
        return {}

    return {
        key: value
        for key, value in source.items()
        if not str(
            key or ""
        ).startswith("_")
    }


def sanitize_workspace_solomon_sources(
    sources: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Return public-safe SolomonAI source records."""

    sanitized_sources = []

    for source in sources or []:
        sanitized = (
            sanitize_workspace_solomon_source_record(
                source
            )
        )

        if sanitized:
            sanitized_sources.append(
                sanitized
            )

    return sanitized_sources
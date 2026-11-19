# -------------------------------------------------------------------
# FILE: workspace_reader_file_catalog.py
# DIRECTORY: solomon_core/workspace_reader/
# -------------------------------------------------------------------
# Server-authoritative catalog of files eligible for workspace selection.
# FileRegistry remains canonical while ownership, organization custody,
# organization membership, group grants, direct grants, and storage state
# determine which documents may be presented to the authenticated user.
# -------------------------------------------------------------------

from typing import Optional

from solomon_core.logger import get_logger
from solomon_core.workspace_reader.workspace_reader_file_access import (
    resolve_authorized_file_registry_corpus,
)

logger = get_logger("workspace_reader.file_catalog")

MY_FILES_SCOPE = "my_files"
GROUP_LIBRARY_SCOPE = "group_library"
SHARED_WITH_ME_SCOPE = "shared_with_me"
SHARED_WITH_GROUP_SCOPE = "shared_with_group"

SUPPORTED_SCOPES = frozenset({
    MY_FILES_SCOPE,
    GROUP_LIBRARY_SCOPE,
    SHARED_WITH_ME_SCOPE,
    SHARED_WITH_GROUP_SCOPE,
})

CATALOG_AUTHORIZATION_ACTION = "discover"
CATALOG_LIMIT = 200


def _clean_value(value) -> str:
    return str(value or "").strip()


def _clean_scope(value) -> str:
    clean_scope = _clean_value(value).lower()
    return clean_scope if clean_scope in SUPPORTED_SCOPES else ""


def _iso_value(value) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else _clean_value(value)


def _catalog_sort_key(item: dict) -> tuple:
    return (
        item.get("updated_at") or item.get("uploaded_at") or "",
        item.get("original_name") or "",
        item.get("document_id") or "",
    )


def _selection_payload(entry: dict) -> Optional[dict]:
    if not isinstance(entry, dict):
        return None

    document_id = _clean_value(
        entry.get("document_id")
        or entry.get("random_name")
        or entry.get("file_id")
    )

    if not document_id:
        return None

    payload = dict(entry)
    payload.pop("path", None)
    payload.pop("checksum", None)

    payload["uploaded_at"] = _iso_value(payload.get("uploaded_at"))
    payload["updated_at"] = _iso_value(payload.get("updated_at"))

    return payload


def list_authorized_file_catalog(
    *,
    user_id: int,
    organization_id: str = "",
    access_scope: str = "",
) -> list:
    clean_user_id = int(user_id or 0)
    clean_organization_id = _clean_value(organization_id)
    clean_scope = _clean_scope(access_scope)

    if not clean_user_id:
        return []

    try:
        corpus = []

        if clean_organization_id and clean_scope != MY_FILES_SCOPE:
            corpus.extend(
                resolve_authorized_file_registry_corpus(
                    user_id=clean_user_id,
                    organization_id=clean_organization_id,
                    request_id="file_catalog.organization",
                    limit=CATALOG_LIMIT,
                    action=CATALOG_AUTHORIZATION_ACTION,
                )
            )

        if not clean_organization_id:
            corpus = resolve_authorized_file_registry_corpus(
                user_id=clean_user_id,
                organization_id="",
                request_id="file_catalog",
                limit=CATALOG_LIMIT,
                action=CATALOG_AUTHORIZATION_ACTION,
            )
        elif clean_scope in {"", MY_FILES_SCOPE}:
            personal_corpus = resolve_authorized_file_registry_corpus(
                user_id=clean_user_id,
                organization_id="",
                request_id="file_catalog.personal",
                limit=CATALOG_LIMIT,
                action=CATALOG_AUTHORIZATION_ACTION,
            )
            corpus.extend(
                entry
                for entry in personal_corpus
                if _clean_value(
                    entry.get("access_scope")
                ).lower() == MY_FILES_SCOPE
            )

        catalog = []
        seen_document_ids = set()

        for entry in corpus:
            entry_scope = _clean_value(
                entry.get("access_scope")
            ).lower()

            if clean_scope and entry_scope != clean_scope:
                continue

            payload = _selection_payload(entry)

            if not payload:
                continue

            document_id = _clean_value(
                payload.get("document_id")
                or payload.get("random_name")
                or payload.get("file_id")
            )

            if document_id in seen_document_ids:
                continue

            seen_document_ids.add(document_id)
            catalog.append(payload)

        catalog.sort(key=_catalog_sort_key, reverse=True)
        return catalog[:CATALOG_LIMIT]

    except Exception as exc:
        logger.warning(
            "[workspace.reader.file_catalog_failed] "
            "user_id=%s organization_id=%s access_scope=%s error=%s",
            clean_user_id,
            clean_organization_id,
            clean_scope,
            exc,
        )
        return []


__all__ = [
    "CATALOG_AUTHORIZATION_ACTION",
    "GROUP_LIBRARY_SCOPE",
    "MY_FILES_SCOPE",
    "SHARED_WITH_GROUP_SCOPE",
    "SHARED_WITH_ME_SCOPE",
    "SUPPORTED_SCOPES",
    "list_authorized_file_catalog",
]
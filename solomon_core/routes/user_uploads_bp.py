# -------------------------------------------------------------------
# FILE: user_uploads_bp.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Authorized file library listing, trash state, folder containers,
# and deletion safety for the Documents workspace.
# -------------------------------------------------------------------

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from urllib.parse import quote

from flask import (
    Blueprint,
    jsonify,
    request,
    session,
)
from sqlalchemy import and_, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from config import settings
from solomon_core.actions.solomon_file_actions import (
    build_solomon_file_action_projection,
)
from solomon_core.auth_utils import login_required
from solomon_core.db import SessionLocal
from solomon_core.document_operations.saved_reviews import load_saved_reviews
from solomon_core.logger import get_logger
from solomon_core.models import (
    FileRecentActivity,
    FileRegistry,
    FolderAccessGrant,
    FolderGroupAccessGrant,
    Organization,
    OrganizationGroup,
    OrganizationGroupMembership,
    OrganizationMembership,
    User,
    WorkspaceFolder,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    DISCOVER_ACTION,
    FILE_SURFACE_DEFAULT,
    FILE_SURFACE_RECENT,
    FILE_SURFACE_TRASH,
    READ_ACTION,
    build_file_capabilities,
    build_file_surface_actions,
    ensure_file_recent_activity_table,
    resolve_authorized_file_registry_corpus,
    resolve_authorized_file_registry_entry,
    resolve_workspace_folder_access_decision,
)

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python compatibility guard.
    ZoneInfo = None

user_uploads_bp = Blueprint("user_uploads", __name__, url_prefix="/uploads")
logger = get_logger("Solomon.user_uploads")

# Document intelligence completion remains durable server state. Workspace clients
# read that state through bounded request/response routes; this blueprint does not
# project completion through browser-lifetime streams.


def _settings_int(
    name: str,
    default: int,
    *,
    minimum: int = 0,
) -> int:
    """Return a bounded integer setting with a safe fallback."""

    value = getattr(settings, name, default)

    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default

    return max(minimum, parsed)


DEFAULT_DOCUMENTS_TIMEZONE_NAME = "America/Chicago"
FALLBACK_CENTRAL_TIMEZONE = timezone(timedelta(hours=-6), "CST")
DOCUMENT_OPERATION_KEY = "document_analysis"
DOCUMENT_OPERATION_LABEL = "Analyze document"
DOCUMENT_OPERATION_DISPLAY_LABEL = "Document Analysis"
DOCUMENT_OPERATION_ROUTE = "/workspace/document-operation/run"
DOCUMENT_OPERATION_CONTRACT = "stored_document_explicit_backend_operation"
DOCUMENTS_FILE_AUTHORIZATION_ACTION = DISCOVER_ACTION
DOCUMENTS_FILE_CATALOG_LIMIT = 200
SAVED_REVIEW_FRAGMENT_ROUTE = "/workspace/document-operation/review/fragment"
SAVED_REVIEW_RESULT_ROUTE = "/workspace/document-operation/review/result"
TRASH_STATUS_VALUES = {"trash", "trashed", "deleted"}
WORKSPACE_FOLDER_CONTRACT = "workspace_folder_v1"
WORKSPACE_FOLDER_CREATION_CONTRACT = "workspace_folder_create_v1"
WORKSPACE_FILE_MOVE_CONTRACT = "workspace_file_move_v1"
WORKSPACE_FOLDER_VISIBILITY_POLICY = "folder_visibility_only_v1"
WORKSPACE_FOLDER_ROOT_PARENT_KEY = "root"
WORKSPACE_FOLDER_OWNER_SCOPE = "owner"
WORKSPACE_FOLDER_ORGANIZATION_SCOPES = frozenset({
    "organization",
    "company",
    "organization_shared",
})
WORKSPACE_FOLDER_GROUP_SCOPES = frozenset({
    "group",
    "team",
    "group_shared",
})
WORKSPACE_FOLDER_SHARED_SCOPES = frozenset({
    "shared",
    *WORKSPACE_FOLDER_ORGANIZATION_SCOPES,
    *WORKSPACE_FOLDER_GROUP_SCOPES,
})
WORKSPACE_FOLDER_COLLECTION_PERSONAL = "personal"
WORKSPACE_FOLDER_COLLECTION_SHARED = "shared"
WORKSPACE_FOLDER_ACTIVE_STATUS = "active"
WORKSPACE_FOLDER_TRASH_STATUS = "trash"
WORKSPACE_FOLDER_MAX_DEPTH = _settings_int(
    "WORKSPACE_FOLDER_MAX_DEPTH",
    25,
    minimum=0,
)
WORKSPACE_FOLDER_MAX_NAME_LENGTH = _settings_int(
    "WORKSPACE_FOLDER_MAX_NAME_LENGTH",
    120,
    minimum=1,
)
WORKSPACE_FILE_MOVE_MAX_ITEMS = _settings_int(
    "WORKSPACE_FILE_MOVE_MAX_ITEMS",
    100,
    minimum=1,
)
WORKSPACE_FOLDER_RESERVED_NAMES = {".", ".."}
WORKSPACE_FOLDER_ROOT_ALIASES = {"root", "files", "my_files"}
RECENT_FILTER_CONTRACT = "server_owned_recent_filters_v1"
RECENT_FILTER_TYPE_LABELS = {
    "pdf": "PDFs",
    "document": "Documents",
    "spreadsheet": "Spreadsheets",
    "presentation": "Presentations",
    "image": "Images",
    "audio": "Audio",
    "video": "Video",
    "other": "Other",
}
RECENT_FILTER_MODIFIED_OPTIONS = (
    ("today", "Today"),
    ("last_7_days", "Last 7 days"),
    ("last_30_days", "Last 30 days"),
    ("this_year", "This year"),
)
RECENT_SORT_CONTRACT = "server_owned_recent_sort_v1"
RECENT_SORT_DEFAULT_KEY = "activity"
RECENT_SORT_FIELDS = {
    "name": {
        "label": "Name",
        "default_direction": "asc",
        "direction_mode": "text",
    },
    "activity": {
        "label": "Activity",
        "default_direction": "desc",
        "direction_mode": "date",
    },
    "owner": {
        "label": "Owner",
        "default_direction": "asc",
        "direction_mode": "text",
    },
    "location": {
        "label": "Location",
        "default_direction": "asc",
        "direction_mode": "text",
    },
    "size": {
        "label": "File size",
        "default_direction": "desc",
        "direction_mode": "size",
    },
}
RECENT_SORT_ALLOWED_DIRECTIONS = frozenset({"asc", "desc"})
WORKSPACE_FOLDER_PARENT_FIELDS = (
    "parent_folder_id",
    "parent_id",
    "folder_parent_id",
    "destination_folder_id",
    "location_folder_id",
)
WORKSPACE_FOLDER_QUERY_FIELDS = (
    "folder_id",
    "current_folder_id",
    "parent_folder_id",
)
WORKSPACE_FOLDER_CLIENT_AUTHORITY_FIELDS = {
    "id",
    "folder_id",
    "folder_contract",
    "user_id",
    "owner",
    "owner_id",
    "owner_user_id",
    "organization_id",
    "group_id",
    "visibility_scope",
    "status",
    "deleted_at",
    "created_by_user_id",
    "updated_by_user_id",
    "path_key",
    "depth",
    "sort_order",
    "metadata_json",
    "capabilities",
    "available_actions",
}
ACTIVE_DOCUMENT_SESSION_KEYS = (
    "document_operation_active_document_ids",
    "document_analysis_active_document_ids",
)
BROWSER_IMAGE_THUMBNAIL_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".gif",
    ".bmp",
}
TIFF_THUMBNAIL_EXTENSIONS = {
    ".tif",
    ".tiff",
}
PDF_THUMBNAIL_EXTENSIONS = {
    ".pdf",
}
OFFICE_DOCUMENT_THUMBNAIL_EXTENSIONS = {
    ".docx",
    ".doc",
}

FILE_AUTHORITY_PAYLOAD_FIELDS = (
    "access_scope",
    "permission",
    "authorized_action",
    "organization_id",
    "membership_id",
    "membership_role",
    "custody_id",
    "custody_mode",
    "library_scope",
    "group_id",
    "group_membership_id",
    "group_grant_id",
    "grant_id",
    "grant_type",
    "authority_basis",
    "policy_version",
    "is_discoverable",
    "allow_ai_query",
    "expires_at",
)


def _get_current_user_id() -> int:
    """Return the authenticated user id from session state."""

    try:
        return int(session.get("user_id") or 0)
    except (TypeError, ValueError):
        return 0


def _normalize_identifier(identifier: str) -> str:
    """Return a normalized file identifier."""

    return str(identifier or "").strip()


def _normalize_lookup_key(value) -> str:
    """Return a stable lowercase lookup key."""

    return str(value or "").strip().lower()


def _normalize_folder_name(value) -> str:
    """Return a safe display name for a workspace folder."""

    return " ".join(str(value or "").strip().split())


def _normalize_folder_lookup_name(value) -> str:
    """Return the duplicate-detection key for a folder name."""

    return _normalize_folder_name(value).casefold()


def _folder_name_validation_error(name: str) -> Optional[str]:
    """Return a validation message when a folder name is not allowed."""

    clean_name = _normalize_folder_name(name)

    if not clean_name:
        return "Folder name is required"

    if len(clean_name) > WORKSPACE_FOLDER_MAX_NAME_LENGTH:
        return (
            "Folder name must be "
            f"{WORKSPACE_FOLDER_MAX_NAME_LENGTH} characters or fewer"
        )

    if clean_name in WORKSPACE_FOLDER_RESERVED_NAMES:
        return "Folder name is reserved"

    if "/" in clean_name or "\\" in clean_name:
        return "Folder name cannot contain slashes"

    if any(ord(character) < 32 for character in clean_name):
        return "Folder name contains unsupported control characters"

    return None


def _request_payload() -> dict:
    """Return a merged JSON/form payload for a workspace mutation."""

    payload = {}

    if request.form:
        payload.update(request.form.to_dict())

    json_payload = request.get_json(silent=True)

    if isinstance(json_payload, dict):
        payload.update(json_payload)

    return payload


def _folder_create_authority_error_payload(
    payload: dict,
) -> Optional[dict]:
    """Return an error when a client submits server-owned fields."""

    if not isinstance(payload, dict):
        return None

    rejected_fields = sorted(
        field_name
        for field_name in WORKSPACE_FOLDER_CLIENT_AUTHORITY_FIELDS
        if payload.get(field_name) not in (None, "")
    )

    if not rejected_fields:
        return None

    return {
        "ok": False,
        "error": "Folder creation accepts name and location only",
        "detail": (
            "Ownership, visibility, status, folder authority, and "
            "file authority are resolved by the server."
        ),
        "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
        "rejected_fields": rejected_fields,
    }


def _folder_parent_identifier(payload: dict) -> str:
    """Return the requested folder parent from accepted location fields."""

    if not isinstance(payload, dict):
        return ""

    for field_name in WORKSPACE_FOLDER_PARENT_FIELDS:
        clean_identifier = _normalize_identifier(
            payload.get(field_name)
        )

        if clean_identifier:
            return clean_identifier

    return ""


def _is_workspace_root_parent(identifier: str) -> bool:
    """Return whether an identifier refers to the Documents root."""

    clean_identifier = _normalize_identifier(identifier)

    if not clean_identifier:
        return True

    return clean_identifier.lower() in WORKSPACE_FOLDER_ROOT_ALIASES


def _request_folder_identifier() -> str:
    """Return the requested Documents folder location from query args."""

    for field_name in WORKSPACE_FOLDER_QUERY_FIELDS:
        clean_identifier = _normalize_identifier(
            request.args.get(field_name)
        )

        if clean_identifier:
            return clean_identifier

    return ""


def _resolve_listing_parent_folder(
    db_session,
    user_id: int,
    identifier: str,
    *,
    access_context: Optional[dict] = None,
):
    """Resolve a Documents listing location using server-owned authority."""

    if _is_workspace_root_parent(identifier):
        return (
            None,
            WORKSPACE_FOLDER_ROOT_PARENT_KEY,
            "",
            None,
        )

    parent_folder = _resolve_folder_record(
        db_session,
        user_id,
        identifier,
        active_only=True,
        access_context=access_context,
    )

    if not parent_folder:
        return (
            None,
            "",
            "",
            (
                jsonify({
                    "ok": False,
                    "error": "Folder not found",
                    "contract": WORKSPACE_FOLDER_CONTRACT,
                }),
                404,
            ),
        )

    folder_id = _normalize_identifier(
        getattr(parent_folder, "folder_id", "")
    )

    return (
        parent_folder,
        _workspace_folder_parent_key(folder_id),
        folder_id,
        None,
    )


def _looks_like_display_filename(value) -> bool:
    """Return whether an identifier looks like a user-visible filename."""

    clean_value = str(value or "").strip()

    if not clean_value:
        return False

    basename = os.path.basename(clean_value)

    if basename != clean_value:
        return True

    extension = _get_filename_extension(clean_value)

    if extension:
        return True

    return " " in clean_value


def _display_identifier_error_payload(identifier: str) -> Optional[dict]:
    """Return an error when a mutation request appears to use display identity."""

    if not _looks_like_display_filename(identifier):
        return None

    return {
        "ok": False,
        "error": "File actions require document_id or file_id",
        "detail": (
            "Visible filenames are display-only and may not be used "
            "for mutation authority."
        ),
    }


def _encode_identifier(identifier: str) -> str:
    """Return a URL-safe file identifier."""

    return quote(_normalize_identifier(identifier), safe="")


def _build_reader_url(document_id: str) -> str:
    """Build the canonical first-party reader URL."""

    return f"/workspace/file/{_encode_identifier(document_id)}/reader"


def _build_workspace_folder_url(
    folder_id: str,
    *,
    shared: bool = False,
) -> str:
    """Build the canonical authorized Documents folder URL."""

    clean_folder_id = _normalize_identifier(folder_id)

    if not clean_folder_id:
        return ""

    base_route = "/shared" if shared else "/"

    return f"{base_route}?folder_id={_encode_identifier(clean_folder_id)}"


def _build_reader_original_url(document_id: str) -> str:
    """Build the protected original-file URL used for safe image thumbnails."""

    clean_document_id = _normalize_identifier(document_id)

    if not clean_document_id:
        return ""

    return (
        f"/workspace/file/{_encode_identifier(clean_document_id)}"
        "/reader/original"
    )


def _build_reader_image_preview_url(document_id: str) -> str:
    """Build the protected rendered TIFF preview URL for thumbnail display."""

    clean_document_id = _normalize_identifier(document_id)

    if not clean_document_id:
        return ""

    return (
        f"/workspace/file/{_encode_identifier(clean_document_id)}"
        "/reader/image/preview.png"
    )


def _build_reader_thumbnail_url(document_id: str) -> str:
    """Build the protected rendered document thumbnail URL."""

    clean_document_id = _normalize_identifier(document_id)

    if not clean_document_id:
        return ""

    return (
        f"/workspace/file/{_encode_identifier(clean_document_id)}"
        "/reader/thumbnail.png"
    )


def _get_filename_extension(filename: str) -> str:
    """Return the lowercase filename extension, including the leading dot."""

    return os.path.splitext(str(filename or "").strip())[1].lower()


def _is_browser_image_thumbnail_candidate(filename: str) -> bool:
    """Return whether protected original image can be used as thumbnail."""

    return (
        _get_filename_extension(filename)
        in BROWSER_IMAGE_THUMBNAIL_EXTENSIONS
    )


def _is_tiff_thumbnail_candidate(filename: str) -> bool:
    """Return whether the file should use rendered TIFF preview thumbnail."""

    return _get_filename_extension(filename) in TIFF_THUMBNAIL_EXTENSIONS


def _is_pdf_thumbnail_candidate(filename: str) -> bool:
    """Return whether the file should use rendered PDF thumbnail route."""

    return _get_filename_extension(filename) in PDF_THUMBNAIL_EXTENSIONS


def _is_office_document_thumbnail_candidate(filename: str) -> bool:
    """Return whether the file should use rendered Office thumbnail route."""

    return (
        _get_filename_extension(filename)
        in OFFICE_DOCUMENT_THUMBNAIL_EXTENSIONS
    )


def _build_fallback_thumbnail_payload() -> dict:
    """Return the stable fallback thumbnail payload."""

    return {
        "thumbnail_url": "",
        "preview_thumbnail_url": "",
        "workspace_thumbnail_url": "",
        "thumbnail_state": "fallback",
        "thumbnail_kind": "",
        "thumbnail_source": "",
    }


def _build_ready_thumbnail_payload(
    *,
    thumbnail_url: str,
    thumbnail_kind: str,
    thumbnail_source: str,
) -> dict:
    """Return a ready server-owned thumbnail payload."""

    clean_thumbnail_url = str(thumbnail_url or "").strip()

    if not clean_thumbnail_url:
        return _build_fallback_thumbnail_payload()

    return {
        "thumbnail_url": clean_thumbnail_url,
        "preview_thumbnail_url": clean_thumbnail_url,
        "workspace_thumbnail_url": clean_thumbnail_url,
        "thumbnail_state": "ready",
        "thumbnail_kind": thumbnail_kind,
        "thumbnail_source": thumbnail_source,
    }


def _build_upload_thumbnail_payload(
    document_id: str,
    original_name: str,
) -> dict:
    """Return passive server-owned thumbnail fields for a document payload."""

    clean_document_id = _normalize_identifier(document_id)

    if not clean_document_id:
        return _build_fallback_thumbnail_payload()

    if _is_browser_image_thumbnail_candidate(original_name):
        return _build_ready_thumbnail_payload(
            thumbnail_url=_build_reader_original_url(clean_document_id),
            thumbnail_kind="image",
            thumbnail_source="protected_original_image",
        )

    if _is_tiff_thumbnail_candidate(original_name):
        return _build_ready_thumbnail_payload(
            thumbnail_url=_build_reader_image_preview_url(clean_document_id),
            thumbnail_kind="image",
            thumbnail_source="rendered_tiff_preview",
        )

    if _is_pdf_thumbnail_candidate(original_name):
        return _build_ready_thumbnail_payload(
            thumbnail_url=_build_reader_thumbnail_url(clean_document_id),
            thumbnail_kind="pdf",
            thumbnail_source="rendered_pdf_first_page",
        )

    if _is_office_document_thumbnail_candidate(original_name):
        return _build_ready_thumbnail_payload(
            thumbnail_url=_build_reader_thumbnail_url(clean_document_id),
            thumbnail_kind="office",
            thumbnail_source="rendered_office_first_page",
        )

    return _build_fallback_thumbnail_payload()


def _build_saved_review_fragment_url(review_id) -> str:
    """Build the server-rendered saved-review fragment URL."""

    clean_review_id = _normalize_identifier(str(review_id or ""))

    if not clean_review_id:
        return ""

    return (
        f"{SAVED_REVIEW_FRAGMENT_ROUTE}/"
        f"{_encode_identifier(clean_review_id)}"
    )


def _build_saved_review_result_url(review_id) -> str:
    """Build the app-shell saved-review fallback URL."""

    clean_review_id = _normalize_identifier(str(review_id or ""))

    if not clean_review_id:
        return ""

    return (
        f"{SAVED_REVIEW_RESULT_ROUTE}/"
        f"{_encode_identifier(clean_review_id)}"
    )


def _build_document_operation_payload(document_id: str) -> dict:
    """Build the explicit backend document operation contract."""

    return {
        "label": DOCUMENT_OPERATION_LABEL,
        "method": "POST",
        "target": DOCUMENT_OPERATION_ROUTE,
        "operation": DOCUMENT_OPERATION_KEY,
        "operation_key": DOCUMENT_OPERATION_KEY,
        "contract": DOCUMENT_OPERATION_CONTRACT,
        "document_id": document_id,
        "analysis_status": "not_started",
        "target_region": "document_inspector",
    }


def _current_utc_datetime() -> datetime:
    """Return a timezone-aware UTC timestamp."""

    return datetime.now(timezone.utc)


def _current_utc_string() -> str:
    """Return a canonical UTC ISO timestamp."""

    return _current_utc_datetime().isoformat()


def _get_documents_timezone():
    """Return local machine timezone, falling back to Central time."""

    try:
        local_timezone = datetime.now().astimezone().tzinfo

        if local_timezone:
            return local_timezone
    except Exception:
        pass

    if ZoneInfo:
        try:
            return ZoneInfo(DEFAULT_DOCUMENTS_TIMEZONE_NAME)
        except Exception:
            pass

    return FALLBACK_CENTRAL_TIMEZONE


def _parse_datetime_value(value) -> Optional[datetime]:
    """Parse a stored timestamp as canonical UTC when timezone is missing."""

    if not value:
        return None

    if isinstance(value, datetime):
        parsed = value
    else:
        clean_value = str(value or "").strip()

        if not clean_value:
            return None

        normalized_value = clean_value

        if normalized_value.endswith("Z"):
            normalized_value = f"{normalized_value[:-1]}+00:00"

        try:
            parsed = datetime.fromisoformat(normalized_value)
        except ValueError:
            parsed = None

        if parsed is None:
            for date_format in (
                "%Y-%m-%d %H:%M:%S",
                "%Y-%m-%d %H:%M:%S.%f",
                "%Y-%m-%dT%H:%M:%S",
                "%Y-%m-%dT%H:%M:%S.%f",
            ):
                try:
                    parsed = datetime.strptime(
                        clean_value,
                        date_format,
                    )
                    break
                except ValueError:
                    continue

        if parsed is None:
            return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


def _datetime_to_string(value) -> Optional[str]:
    """Return a local/Central ISO string for Documents UI display."""

    parsed = _parse_datetime_value(value)

    if not parsed:
        return None

    return parsed.astimezone(_get_documents_timezone()).isoformat()


def _datetime_to_utc_string(value) -> Optional[str]:
    """Return the canonical UTC ISO string for audit/debug payloads."""

    parsed = _parse_datetime_value(value)

    if not parsed:
        return None

    return parsed.astimezone(timezone.utc).isoformat()


def _safe_meta_payload(value) -> dict:
    """Return FileRegistry metadata as a safe dictionary."""

    if isinstance(value, dict):
        return dict(value)

    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (TypeError, ValueError):
            return {}

        if isinstance(parsed, dict):
            return parsed

    return {}


def _truthy_payload_flag(value) -> bool:
    """Return whether a metadata flag should be treated as enabled."""

    if isinstance(value, bool):
        return value

    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    return bool(value)


def _is_trashed_meta(value) -> bool:
    """Return whether an upload metadata payload marks a file as trashed."""

    meta = _safe_meta_payload(value)
    document_status = _normalize_lookup_key(
        meta.get("document_status")
        or meta.get("library_status")
        or meta.get("storage_status")
    )

    return bool(
        _truthy_payload_flag(meta.get("trashed"))
        or meta.get("trashed_at")
        or document_status in TRASH_STATUS_VALUES
    )


def _trash_status_payload(user_id: int) -> dict:
    """Return metadata fields for a recoverable Trash move."""

    trashed_at = _current_utc_string()

    return {
        "trashed": True,
        "trashed_at": trashed_at,
        "document_status": "trash",
        "trashed_by_user_id": int(user_id or 0),
    }


def _clear_restore_status_fields(meta: dict) -> None:
    """Remove stale recoverable-delete metadata during restore."""

    if not isinstance(meta, dict):
        return

    for key in (
        "trashed_at",
        "trashed_by_user_id",
        "deleted_at",
        "deleted_by_user_id",
    ):
        meta.pop(key, None)

    for key in ("library_status", "storage_status"):
        if _normalize_lookup_key(meta.get(key)) in TRASH_STATUS_VALUES:
            meta.pop(key, None)


def _restore_status_payload(value) -> dict:
    """Return metadata fields for restoring a recoverably trashed upload."""

    meta = _safe_meta_payload(value)
    _clear_restore_status_fields(meta)

    meta["trashed"] = False
    meta["document_status"] = "active"

    return meta


def _uploads_root() -> str:
    """Return the absolute uploads root."""

    return os.path.abspath(settings.UPLOADS_DIR)


def _is_inside_uploads_root(path: str) -> bool:
    """Return whether a path is safely inside the uploads root."""

    if not path:
        return False

    try:
        absolute_path = os.path.abspath(path)

        return (
            os.path.commonpath([
                _uploads_root(),
                absolute_path,
            ])
            == _uploads_root()
        )
    except (OSError, ValueError):
        return False


def _set_active_ids(identifiers) -> set:
    """Persist canonical workflow selections in the server session."""

    clean_ids = []
    seen = set()

    for identifier in identifiers or []:
        clean_identifier = _normalize_identifier(identifier)

        if not clean_identifier or clean_identifier in seen:
            continue

        clean_ids.append(clean_identifier)
        seen.add(clean_identifier)

    for key in ACTIVE_DOCUMENT_SESSION_KEYS:
        if clean_ids:
            session[key] = list(clean_ids)
        else:
            session.pop(key, None)

    if not clean_ids:
        session.pop("document_operation_active_key", None)
        session.pop("document_analysis_handoff_contract", None)
        session.pop("document_analysis_handoff_request_id", None)

    session.modified = True

    return set(clean_ids)


def _get_active_ids(user_id: int) -> set:
    """Return authorized workflow selections from the server session."""

    if not user_id:
        return set()

    requested_ids = []
    seen = set()

    for key in ACTIVE_DOCUMENT_SESSION_KEYS:
        values = session.get(key)

        if isinstance(values, str):
            values = [values]

        if not isinstance(values, (list, tuple, set)):
            continue

        for value in values:
            clean_value = _normalize_identifier(value)

            if not clean_value or clean_value in seen:
                continue

            requested_ids.append(clean_value)
            seen.add(clean_value)

    if not requested_ids:
        return set()

    canonical_ids = []

    for identifier in requested_ids:
        authorized_file = resolve_authorized_file_registry_entry(
            user_id,
            identifier,
            request_id="uploads.active_ids",
            action=READ_ACTION,
            allow_trashed_owner_read=False,
        )

        if not authorized_file:
            continue

        document_id = _normalize_identifier(
            authorized_file.get("document_id")
            or authorized_file.get("random_name")
        )

        if document_id and document_id not in canonical_ids:
            canonical_ids.append(document_id)

    if set(requested_ids) != set(canonical_ids):
        return _set_active_ids(canonical_ids)

    return set(canonical_ids)


def _remove_active_id(identifier: str) -> set:
    """Remove one canonical document id from workflow session state."""

    clean_identifier = _normalize_identifier(identifier)
    remaining_ids = {
        document_id
        for document_id in _get_active_ids(
            _get_current_user_id()
        )
        if document_id != clean_identifier
    }

    return _set_active_ids(sorted(remaining_ids))


def _review_timestamp(review: dict) -> datetime:
    """Return the best sortable review timestamp."""

    parsed = (
        _parse_datetime_value(review.get("updated_at"))
        or _parse_datetime_value(review.get("created_at"))
    )

    if parsed:
        return parsed

    return datetime.min.replace(tzinfo=timezone.utc)


def _review_identifier(review: dict) -> int:
    """Return a numeric review identifier for deterministic tie-breaking."""

    for key in ("review_id", "artifact_id", "record_id"):
        value = str(review.get(key) or "").strip()

        if value.isdigit():
            return int(value)

    return 0


def _is_document_analysis_saved_review(review: dict) -> bool:
    """Return whether a saved artifact is a document analysis report."""

    if not isinstance(review, dict):
        return False

    operation_key = _normalize_lookup_key(
        review.get("operation_key")
    )
    report_type = _normalize_lookup_key(
        review.get("report_type")
    )
    artifact_type = _normalize_lookup_key(
        review.get("artifact_type")
    )
    status = _normalize_lookup_key(
        review.get("status")
    )

    if artifact_type and artifact_type != "review":
        return False

    if operation_key and operation_key != DOCUMENT_OPERATION_KEY:
        return False

    if report_type and report_type != DOCUMENT_OPERATION_KEY:
        return False

    if status and status not in {
        "complete",
        "completed",
        "finished",
        "ready",
    }:
        return False

    return True


def _newer_review(
    existing: Optional[dict],
    candidate: dict,
) -> dict:
    """Return the newer of two saved-review payloads."""

    if not existing:
        return candidate

    existing_stamp = _review_timestamp(existing)
    candidate_stamp = _review_timestamp(candidate)

    if candidate_stamp > existing_stamp:
        return candidate

    if (
        candidate_stamp == existing_stamp
        and _review_identifier(candidate)
        > _review_identifier(existing)
    ):
        return candidate

    return existing


def _set_review_index_value(
    index: dict,
    bucket: str,
    key,
    review: dict,
) -> None:
    """Store the newest review for one lookup key."""

    clean_key = _normalize_lookup_key(key)

    if not clean_key:
        return

    index[bucket][clean_key] = _newer_review(
        index[bucket].get(clean_key),
        review,
    )


def _load_saved_review_index(user_id: int) -> dict:
    """Build lookup indexes for the user's latest saved reviews."""

    index = {
        "document_id": {},
        "file_id": {},
    }

    try:
        reviews = load_saved_reviews(user_id)
    except Exception as exc:
        logger.warning(
            "[uploads.saved_reviews_unavailable] "
            "user_id=%s error=%s",
            user_id,
            exc,
        )
        return index

    for review in reviews:
        if not _is_document_analysis_saved_review(review):
            continue

        for source in review.get("sources") or []:
            if not isinstance(source, dict):
                continue

            _set_review_index_value(
                index,
                "document_id",
                source.get("source_document_id"),
                review,
            )
            _set_review_index_value(
                index,
                "file_id",
                source.get("file_registry_id"),
                review,
            )

    return index


def _find_saved_review_for_upload(
    payload: dict,
    saved_review_index: dict,
) -> Optional[dict]:
    """Return the latest saved review matching an upload payload."""

    if not isinstance(payload, dict):
        return None

    for value in (
        payload.get("document_id"),
        payload.get("random_name"),
    ):
        review = (
            saved_review_index
            .get("document_id", {})
            .get(_normalize_lookup_key(value))
        )

        if review:
            return review

    review = (
        saved_review_index
        .get("file_id", {})
        .get(_normalize_lookup_key(payload.get("file_id")))
    )

    if review:
        return review

    return None


def _saved_review_summary_payload(review: dict) -> dict:
    """Return a compact saved-review payload for upload records."""

    if not isinstance(review, dict):
        return {}

    review_id = (
        review.get("review_id")
        or review.get("artifact_id")
        or review.get("record_id")
        or ""
    )

    return {
        "saved": True,
        "has_report": True,
        "review_id": review_id,
        "artifact_id": (
            review.get("artifact_id")
            or review_id
        ),
        "record_id": (
            review.get("record_id")
            or review_id
        ),
        "status": (
            review.get("status")
            or "completed"
        ),
        "operation_key": DOCUMENT_OPERATION_KEY,
        "operation_label": DOCUMENT_OPERATION_DISPLAY_LABEL,
        "report_type": (
            review.get("report_type")
            or DOCUMENT_OPERATION_KEY
        ),
        "title": (
            review.get("title")
            or review.get("review_title")
            or DOCUMENT_OPERATION_DISPLAY_LABEL
        ),
        "review_title": (
            review.get("review_title")
            or review.get("title")
            or DOCUMENT_OPERATION_DISPLAY_LABEL
        ),
        "summary": review.get("summary") or "",
        "risk_level": review.get("risk_level") or "",
        "completeness": (
            review.get("completeness")
            or review.get("document_completeness")
            or ""
        ),
        "confidence_level": (
            review.get("confidence_level")
            or ""
        ),
        "job_id": review.get("job_id") or "",
        "request_id": review.get("request_id") or "",
        "analysis_version": (
            review.get("analysis_version")
            or ""
        ),
        "generated_at": (
            review.get("updated_at")
            or review.get("created_at")
            or ""
        ),
        "created_at": review.get("created_at") or "",
        "updated_at": review.get("updated_at") or "",
        "fragment_url": _build_saved_review_fragment_url(
            review_id
        ),
        "report_url": _build_saved_review_result_url(
            review_id
        ),
        "result_url": _build_saved_review_result_url(
            review_id
        ),
    }


def _attach_saved_review_to_upload(
    payload: dict,
    saved_review: Optional[dict],
) -> dict:
    """Attach saved-review metadata to an upload payload."""

    if not payload or not saved_review:
        return payload

    report_payload = _saved_review_summary_payload(
        saved_review
    )

    if not report_payload.get("review_id"):
        return payload

    payload["report"] = report_payload
    payload["saved_review"] = {
        "saved": True,
        "review_id": report_payload["review_id"],
        "artifact_id": report_payload["artifact_id"],
        "status": report_payload["status"],
        "operation_key": DOCUMENT_OPERATION_KEY,
        "operation_label": DOCUMENT_OPERATION_DISPLAY_LABEL,
        "title": report_payload["title"],
        "created_at": report_payload["created_at"],
        "updated_at": report_payload["updated_at"],
    }
    payload["has_saved_review"] = True
    payload["has_report"] = True
    payload["report_saved"] = True
    payload["report_status"] = report_payload["status"]
    payload["report_review_id"] = report_payload["review_id"]
    payload["report_job_id"] = report_payload["job_id"]
    payload["report_fragment_url"] = report_payload["fragment_url"]
    payload["report_url"] = report_payload["report_url"]
    payload["report_generated_at"] = report_payload["generated_at"]
    payload["workflow_status"] = "complete"
    payload["analysis_status"] = "complete"

    return payload


def _resolve_owned_file_record(
    db_session,
    user_id: int,
    identifier: str,
):
    """Resolve an owner-controlled FileRegistry row for mutation authority."""

    clean_identifier = _normalize_identifier(identifier)

    if not clean_identifier:
        return None

    record = None

    if clean_identifier.isdigit():
        record = db_session.get(
            FileRegistry,
            int(clean_identifier),
        )

    if not record:
        record = (
            db_session.query(FileRegistry)
            .filter(
                FileRegistry.random_name
                == clean_identifier
            )
            .first()
        )

    if (
        not record
        or str(record.uploader_id or "")
        != str(user_id or "")
    ):
        return None

    return record


def _workspace_folder_access_context(
    db_session,
    user_id: int,
) -> dict:
    """Return active organization and group memberships for folder discovery."""

    clean_user_id = int(user_id or 0)

    if not clean_user_id:
        return {
            "user_id": 0,
            "organization_ids": frozenset(),
            "group_ids": frozenset(),
        }

    organization_ids = {
        str(row[0])
        for row in (
            db_session.query(
                OrganizationMembership.organization_id
            )
            .join(
                Organization,
                Organization.organization_id
                == OrganizationMembership.organization_id,
            )
            .filter(
                OrganizationMembership.user_id == clean_user_id,
                OrganizationMembership.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
                OrganizationMembership.removed_at.is_(None),
                Organization.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
                Organization.suspended_at.is_(None),
            )
            .all()
        )
        if row[0]
    }

    group_query = (
        db_session.query(
            OrganizationGroupMembership.group_id,
            OrganizationGroup.organization_id,
        )
        .join(
            OrganizationGroup,
            OrganizationGroup.group_id
            == OrganizationGroupMembership.group_id,
        )
        .filter(
            OrganizationGroupMembership.user_id == clean_user_id,
            OrganizationGroupMembership.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
            OrganizationGroupMembership.removed_at.is_(None),
            OrganizationGroup.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
            OrganizationGroup.removed_at.is_(None),
        )
    )
    group_ids = {
        str(group_id)
        for group_id, organization_id in group_query.all()
        if group_id and str(organization_id or "") in organization_ids
    }

    return {
        "user_id": clean_user_id,
        "organization_ids": frozenset(organization_ids),
        "group_ids": frozenset(group_ids),
        "db_session": db_session,
    }


def _workspace_folder_scope(folder: WorkspaceFolder) -> str:
    """Return the normalized visibility scope for a folder."""

    return (
        _normalize_lookup_key(
            getattr(folder, "visibility_scope", "")
        )
        or WORKSPACE_FOLDER_OWNER_SCOPE
    )


def _workspace_folder_access_decision(
    folder: WorkspaceFolder,
    user_id: int,
    access_context: Optional[dict] = None,
) -> dict:
    """Return one fail-closed explicit-grant folder authorization decision."""

    context = access_context or {}
    clean_user_id = int(user_id or 0)
    is_owner = bool(
        clean_user_id
        and str(getattr(folder, "user_id", "")) == str(clean_user_id)
    )
    db_session = context.get("db_session")
    authority = None

    if db_session is not None and clean_user_id:
        authority = resolve_workspace_folder_access_decision(
            db_session,
            folder,
            clean_user_id,
            action=DISCOVER_ACTION,
        )
    elif is_owner:
        authority = {
            "permission": "owner",
            "authority_basis": "workspace_folder_owner",
            "access_scope": "my_files",
        }

    authorized = bool(authority)
    permission = str(
        (authority or {}).get("permission") or ""
    ).strip().lower()

    return {
        "authorized": authorized,
        "is_owner": bool(authorized and permission == "owner"),
        "is_shared": bool(authorized and permission != "owner"),
        "visibility_scope": _workspace_folder_scope(folder),
        "authority_basis": str(
            (authority or {}).get("authority_basis") or ""
        ),
        "permission": permission,
        "grant_id": (
            (authority or {}).get("folder_grant_id")
            or (authority or {}).get("folder_group_grant_id")
        ),
        "inherited_from_folder_id": (
            (authority or {}).get("inherited_from_folder_id")
        ),
        "access_scope": (
            "my_files"
            if authorized and permission == "owner"
            else "shared_with_me"
            if authorized
            else ""
        ),
    }

def _resolve_folder_record(
    db_session,
    user_id: int,
    identifier: str,
    *,
    active_only: bool = True,
    require_owner: bool = False,
    access_context: Optional[dict] = None,
):
    """Resolve one authorized folder without trusting browser hierarchy state."""

    clean_identifier = _normalize_identifier(identifier)

    if not clean_identifier:
        return None

    query = (
        db_session.query(WorkspaceFolder)
        .options(joinedload(WorkspaceFolder.owner_user))
    )

    if clean_identifier.isdigit():
        record = (
            query.filter(
                or_(
                    WorkspaceFolder.id == int(clean_identifier),
                    WorkspaceFolder.folder_id == clean_identifier,
                )
            )
            .first()
        )
    else:
        record = (
            query.filter(
                WorkspaceFolder.folder_id == clean_identifier
            )
            .first()
        )

    if not record:
        return None

    if active_only and _workspace_folder_status(record) != WORKSPACE_FOLDER_ACTIVE_STATUS:
        return None

    if active_only and (
        getattr(record, "deleted_at", None)
        or not bool(getattr(record, "is_discoverable", True))
    ):
        return None

    context = access_context or _workspace_folder_access_context(
        db_session,
        user_id,
    )
    decision = _workspace_folder_access_decision(
        record,
        user_id,
        context,
    )

    if not decision["authorized"]:
        return None

    if require_owner and not decision["is_owner"]:
        return None

    return record


def _workspace_folder_status(folder: WorkspaceFolder) -> str:
    """Return the UI document status for a folder record."""

    clean_status = _normalize_lookup_key(
        getattr(folder, "status", "")
    )

    if getattr(folder, "deleted_at", None) or clean_status in TRASH_STATUS_VALUES:
        return WORKSPACE_FOLDER_TRASH_STATUS

    return clean_status or WORKSPACE_FOLDER_ACTIVE_STATUS


def _workspace_folder_capabilities(
    folder_status: str,
    *,
    can_manage: bool,
) -> dict:
    """Return server-owned capabilities for one authorized folder."""

    is_active = folder_status == WORKSPACE_FOLDER_ACTIVE_STATUS
    is_trash = folder_status == WORKSPACE_FOLDER_TRASH_STATUS

    return {
        "can_open": is_active,
        "can_view_details": True,
        "can_create_child_folder": bool(is_active and can_manage),
        "can_rename": False,
        "can_move": False,
        "can_share_visibility": False,
        "can_move_to_trash": bool(is_active and can_manage),
        "can_restore": bool(is_trash and can_manage),
        "can_permanently_delete": bool(is_trash and can_manage),
        "can_open_reader": False,
        "can_run_document_operation": False,
        "can_select_for_solomon_ai": False,
        "file_authority_inherited": "dynamic_explicit_folder_grant",
    }


def _workspace_folder_available_actions(
    folder_status: str,
    *,
    can_manage: bool,
) -> list[str]:
    """Return capability-aligned actions for one authorized folder."""

    if folder_status == WORKSPACE_FOLDER_TRASH_STATUS:
        actions = ["view_details"]

        if can_manage:
            actions.extend([
                "restore",
                "permanent_delete",
            ])

        return actions

    if folder_status != WORKSPACE_FOLDER_ACTIVE_STATUS:
        return ["view_details"]

    actions = [
        "open",
        "view_details",
    ]

    if can_manage:
        actions.extend([
            "create_child_folder",
            "move_to_trash",
        ])

    return actions


def _workspace_folder_parent_key(parent_folder_id: str) -> str:
    """Return the canonical parent key used for folder uniqueness."""

    return (
        _normalize_identifier(parent_folder_id)
        or WORKSPACE_FOLDER_ROOT_PARENT_KEY
    )


def _workspace_folder_path_key(
    folder_id: str,
    parent_folder: Optional[WorkspaceFolder],
) -> str:
    """Return a stable folder path key based on opaque folder identifiers."""

    clean_folder_id = _normalize_identifier(folder_id)

    if not clean_folder_id:
        return ""

    if not parent_folder:
        return clean_folder_id

    parent_path = _normalize_identifier(
        getattr(parent_folder, "path_key", "")
        or getattr(parent_folder, "folder_id", "")
    )

    if not parent_path:
        return clean_folder_id

    return f"{parent_path}/{clean_folder_id}"


def _find_active_workspace_folder_conflict(
    db_session,
    user_id: int,
    visibility_scope: str,
    parent_folder_key: str,
    normalized_name: str,
):
    """Return an active folder with the same name in one container."""

    return (
        db_session.query(WorkspaceFolder)
        .filter(
            WorkspaceFolder.user_id == user_id,
            WorkspaceFolder.visibility_scope == visibility_scope,
            WorkspaceFolder.parent_folder_key == parent_folder_key,
            WorkspaceFolder.normalized_name == normalized_name,
            WorkspaceFolder.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
        )
        .first()
    )


def _find_trashed_workspace_folder_conflict(
    db_session,
    folder: WorkspaceFolder,
):
    """Return a sibling Trash conflict for the folder uniqueness contract."""

    query = db_session.query(WorkspaceFolder).filter(
        WorkspaceFolder.user_id == int(getattr(folder, "user_id", 0) or 0),
        WorkspaceFolder.visibility_scope == _workspace_folder_scope(folder),
        WorkspaceFolder.parent_folder_key == _workspace_folder_parent_key(
            getattr(folder, "parent_folder_key", "")
        ),
        WorkspaceFolder.normalized_name == _normalize_folder_lookup_name(
            getattr(folder, "name", "")
        ),
        WorkspaceFolder.status == WORKSPACE_FOLDER_TRASH_STATUS,
    )
    folder_row_id = int(getattr(folder, "id", 0) or 0)

    if folder_row_id:
        query = query.filter(WorkspaceFolder.id != folder_row_id)

    return query.first()


def _workspace_folder_content_counts(
    db_session,
    folder_id: str,
) -> tuple[int, int]:
    """Return direct folder and file counts without inferring recursion."""

    clean_folder_id = _normalize_identifier(folder_id)

    if not clean_folder_id:
        return 0, 0

    child_folder_count = (
        db_session.query(WorkspaceFolder.id)
        .filter(
            WorkspaceFolder.parent_folder_id == clean_folder_id,
        )
        .count()
    )
    file_count = (
        db_session.query(FileRegistry.id)
        .filter(
            FileRegistry.workspace_folder_id == clean_folder_id,
        )
        .count()
    )

    return int(child_folder_count or 0), int(file_count or 0)


def _workspace_folder_empty_error_payload(
    db_session,
    folder: WorkspaceFolder,
) -> Optional[dict]:
    """Reject folder lifecycle mutations that would imply recursion."""

    child_folder_count, file_count = _workspace_folder_content_counts(
        db_session,
        getattr(folder, "folder_id", ""),
    )

    if not child_folder_count and not file_count:
        return None

    return {
        "ok": False,
        "error": "Move or remove the folder contents before changing this folder's Trash state.",
        "contract": WORKSPACE_FOLDER_CONTRACT,
        "folder_non_recursive": True,
        "child_folder_count": child_folder_count,
        "file_count": file_count,
    }


def _safe_delete_storage_file(path: str) -> tuple[bool, str]:
    """Delete a stored file only when it is inside the uploads root."""

    clean_path = str(path or "").strip()

    if not clean_path:
        return False, "missing_path"

    absolute_path = os.path.abspath(clean_path)

    if not _is_inside_uploads_root(absolute_path):
        return False, "unsafe_path"

    if not os.path.exists(absolute_path):
        return False, "already_missing"

    if not os.path.isfile(absolute_path):
        return False, "not_a_file"

    try:
        os.remove(absolute_path)
    except OSError:
        return False, "delete_failed"

    return True, "deleted"


def _storage_delete_allows_metadata_removal(
    deleted: bool,
    status: str,
) -> bool:
    """Return whether database metadata can be removed after storage handling."""

    if deleted:
        return True

    return status in {
        "missing_path",
        "already_missing",
    }


def _file_authority_payload(access_payload: Optional[dict]) -> dict:
    """Return transport-safe authority fields for a file payload."""

    if not isinstance(access_payload, dict):
        return {
            "access_scope": "my_files",
            "permission": "manage",
            "authorized_action": READ_ACTION,
            "authority_basis": "personal_owner",
            "policy_version": "personal_file_permissions_v1",
            "is_discoverable": True,
            "allow_ai_query": True,
        }

    authority_payload = {}

    for field_name in FILE_AUTHORITY_PAYLOAD_FIELDS:
        field_value = access_payload.get(field_name)

        if field_value not in (None, ""):
            authority_payload[field_name] = field_value

    return authority_payload


def _file_registry_payload(
    record: FileRegistry,
    active_ids: set,
    *,
    trash_only: bool = False,
    access_payload: Optional[dict] = None,
    surface: str = FILE_SURFACE_DEFAULT,
) -> Optional[dict]:
    """Build a safe upload payload from a FileRegistry row."""

    if not record:
        return None

    document_id = str(
        record.random_name or ""
    ).strip()
    path = str(
        record.path or ""
    ).strip()

    if (
        not document_id
        or not path
        or not os.path.isfile(path)
    ):
        return None

    meta = _safe_meta_payload(record.meta)
    trashed = _is_trashed_meta(meta)

    if trash_only and not trashed:
        return None

    if trashed and not trash_only:
        return None

    try:
        size_bytes = int(
            record.size_bytes
            or os.path.getsize(path)
        )
    except (TypeError, OSError, ValueError):
        size_bytes = None

    selected_for_workflow = (
        False
        if trashed
        else document_id in active_ids
    )
    thumbnail_payload = _build_upload_thumbnail_payload(
        document_id,
        record.original_name or document_id,
    )
    authority_payload = _file_authority_payload(
        access_payload
    )
    resolved_capabilities = (
        dict(access_payload.get("capabilities"))
        if isinstance(access_payload, dict)
        and isinstance(access_payload.get("capabilities"), dict)
        else None
    )
    capabilities = (
        resolved_capabilities
        if resolved_capabilities is not None
        else build_file_capabilities(
            record,
            authority_payload,
            requesting_user_id=_get_current_user_id(),
        )
    )
    surface_actions = build_file_surface_actions(
        capabilities,
        surface=surface,
    )
    solomon_action_projection = (
        build_solomon_file_action_projection(
            capabilities
        )
    )

    return {
        "workspace_item_type": "file",
        "item_type": "file",
        "resource_type": "file",
        "document_kind": "file",
        "folder": False,
        "document_id": document_id,
        "file_id": str(record.id),
        "original_name": (
            record.original_name
            or document_id
        ),
        "random_name": document_id,
        "workspace_folder_id": _normalize_identifier(
            getattr(record, "workspace_folder_id", "")
        ),
        "parent_folder_id": _normalize_identifier(
            getattr(record, "workspace_folder_id", "")
        ),
        "size_bytes": size_bytes,
        "uploaded_at": _datetime_to_string(
            record.upload_time
        ),
        "updated_at": _datetime_to_string(
            record.updated_at
        ),
        "uploaded_at_utc": _datetime_to_utc_string(
            record.upload_time
        ),
        "updated_at_utc": _datetime_to_utc_string(
            record.updated_at
        ),
        "trashed": trashed,
        "trashed_at": _datetime_to_string(
            meta.get("trashed_at")
        ),
        "trashed_at_utc": _datetime_to_utc_string(
            meta.get("trashed_at")
        ),
        "document_status": (
            "trash"
            if trashed
            else meta.get("document_status")
            or "active"
        ),
        "active": selected_for_workflow,
        "selected_for_workflow": selected_for_workflow,
        "reader_url": _build_reader_url(document_id),
        "workspace_reader_url": _build_reader_url(
            document_id
        ),
        **thumbnail_payload,
        **authority_payload,
        "capabilities": capabilities,
        "surface_actions_authoritative": True,
        "surface_actions": surface_actions,
        "available_actions": surface_actions,
        "actions": surface_actions,
        **solomon_action_projection,
        "workflow_status": (
            meta.get("workflow_status")
            or "not_started"
        ),
        "analysis_status": (
            meta.get("analysis_status")
            or "not_started"
        ),
        "handoff_required": bool(
            meta.get("activation_required", True)
        ),
        "handoff": _build_document_operation_payload(
            document_id
        ),
        "document_operation": _build_document_operation_payload(
            document_id
        ),
    }


def _resolve_authorized_file_record(
    db_session,
    access_payload: dict,
):
    """Hydrate a FileRegistry row from a central-authority payload."""

    if not isinstance(access_payload, dict):
        return None

    file_id = _normalize_identifier(
        access_payload.get("file_id")
    )

    if file_id.isdigit():
        record = db_session.get(
            FileRegistry,
            int(file_id),
        )

        if record:
            return record

    document_id = _normalize_identifier(
        access_payload.get("document_id")
        or access_payload.get("random_name")
    )

    if not document_id:
        return None

    return (
        db_session.query(FileRegistry)
        .filter(
            FileRegistry.random_name
            == document_id
        )
        .first()
    )


def _authorized_file_payloads(
    db_session,
    user_id: int,
    active_ids: set,
    saved_review_index: dict,
    *,
    parent_folder_key: str = WORKSPACE_FOLDER_ROOT_PARENT_KEY,
    ownership_scope: str = "",
    include_any_parent: bool = False,
    excluded_folder_ids: Optional[set] = None,
) -> list[dict]:
    """Return file-authorized payloads for one governed Documents surface."""

    payloads = []
    seen = set()
    requested_parent_key = _workspace_folder_parent_key(
        parent_folder_key
    )
    excluded_ids = {
        _normalize_identifier(value)
        for value in (excluded_folder_ids or set())
        if _normalize_identifier(value)
    }

    authorized_files = resolve_authorized_file_registry_corpus(
        user_id=user_id,
        request_id="uploads.me",
        limit=DOCUMENTS_FILE_CATALOG_LIMIT,
        action=DOCUMENTS_FILE_AUTHORIZATION_ACTION,
    )

    for authorized_file in authorized_files:
        if not isinstance(authorized_file, dict):
            continue

        record = _resolve_authorized_file_record(
            db_session,
            authorized_file,
        )

        if not record:
            continue

        is_owner = str(getattr(record, "uploader_id", "")) == str(user_id)

        if ownership_scope == WORKSPACE_FOLDER_COLLECTION_PERSONAL and not is_owner:
            continue

        if ownership_scope == WORKSPACE_FOLDER_COLLECTION_SHARED and is_owner:
            continue

        payload = _file_registry_payload(
            record,
            active_ids,
            trash_only=False,
            access_payload=authorized_file,
        )

        if not payload:
            continue

        file_folder_id = _normalize_identifier(
            payload.get("workspace_folder_id")
            or payload.get("parent_folder_id")
        )

        if file_folder_id and file_folder_id in excluded_ids:
            continue

        if (
            include_any_parent
            and ownership_scope == WORKSPACE_FOLDER_COLLECTION_SHARED
        ):
            payload["workspace_folder_id"] = ""
            payload["parent_folder_id"] = ""

        if (
            not include_any_parent
            and not _file_payload_is_in_folder(
                payload,
                requested_parent_key,
            )
        ):
            continue

        document_id = _normalize_identifier(
            payload.get("document_id")
        )

        if not document_id or document_id in seen:
            continue

        _attach_saved_review_to_upload(
            payload,
            _find_saved_review_for_upload(
                payload,
                saved_review_index,
            ),
        )
        payloads.append(payload)
        seen.add(document_id)

    return payloads


def _recent_activity_reason(activity_kind: str) -> str:
    """Return user-facing Recent activity copy."""

    clean_kind = _normalize_identifier(activity_kind).lower()

    if clean_kind == "opened":
        return "Opened by me"

    if clean_kind == "modified":
        return "Modified by me"

    if clean_kind == "shared":
        return "Shared with me"

    return "Uploaded"


def _recent_activity_fallback(record: FileRegistry) -> tuple[datetime, str]:
    """Return the best existing activity when no explicit open exists."""

    uploaded_at = _parse_datetime_value(getattr(record, "upload_time", None))
    updated_at = _parse_datetime_value(getattr(record, "updated_at", None))

    if (
        updated_at
        and uploaded_at
        and updated_at > uploaded_at + timedelta(seconds=1)
    ):
        return updated_at, "modified"

    return (
        uploaded_at
        or updated_at
        or _current_utc_datetime(),
        "uploaded",
    )


def _recent_group_label(activity_at) -> str:
    """Return the Google Drive-style Recent time group label."""

    parsed = _parse_datetime_value(activity_at)

    if not parsed:
        return "Earlier"

    local_now = _current_utc_datetime().astimezone(
        _get_documents_timezone()
    )
    local_activity = parsed.astimezone(
        _get_documents_timezone()
    )
    day_delta = (local_now.date() - local_activity.date()).days

    if day_delta == 0:
        return "Today"

    if day_delta == 1:
        return "Yesterday"

    start_of_week = local_now.date() - timedelta(
        days=local_now.weekday()
    )
    previous_week_start = start_of_week - timedelta(days=7)

    if local_activity.date() >= start_of_week:
        return "Earlier this week"

    if local_activity.date() >= previous_week_start:
        return "Last week"

    if (
        local_activity.year == local_now.year
        and local_activity.month == local_now.month
    ):
        return "Earlier this month"

    previous_month = 12 if local_now.month == 1 else local_now.month - 1
    previous_month_year = (
        local_now.year - 1
        if local_now.month == 1
        else local_now.year
    )

    if (
        local_activity.year == previous_month_year
        and local_activity.month == previous_month
    ):
        return "Last month"

    if local_activity.year == local_now.year:
        return "Earlier this year"

    return str(local_activity.year)


def _recent_filter_type_value(payload: dict) -> str:
    """Return the server-owned Recent type-filter key for one file."""

    filename = _normalize_identifier(
        payload.get("original_name")
        or payload.get("display_name")
        or payload.get("name")
    )
    extension = _get_filename_extension(filename)

    if extension == ".pdf":
        return "pdf"

    if extension in {".doc", ".docx", ".odt", ".rtf", ".txt"}:
        return "document"

    if extension in {".csv", ".xls", ".xlsx", ".ods"}:
        return "spreadsheet"

    if extension in {".ppt", ".pptx", ".odp"}:
        return "presentation"

    if extension in {
        ".bmp",
        ".gif",
        ".jpeg",
        ".jpg",
        ".png",
        ".tif",
        ".tiff",
        ".webp",
    }:
        return "image"

    if extension in {".aac", ".flac", ".m4a", ".mp3", ".ogg", ".wav"}:
        return "audio"

    if extension in {".avi", ".m4v", ".mkv", ".mov", ".mp4", ".webm"}:
        return "video"

    return "other"


def _recent_filter_option_list(
    counts: dict,
    *,
    labels: Optional[dict] = None,
) -> list[dict]:
    """Return sorted transport options with server-calculated counts."""

    label_map = labels or {}
    options = []

    for value, count in counts.items():
        clean_value = _normalize_identifier(value)

        if not clean_value or int(count or 0) <= 0:
            continue

        options.append({
            "value": clean_value,
            "label": _normalize_identifier(
                label_map.get(clean_value)
            ) or clean_value,
            "count": int(count),
        })

    options.sort(
        key=lambda item: (
            item.get("label", "").lower(),
            item.get("value", "").lower(),
        )
    )
    return options


def _recent_matches_modified_filter(
    payload: dict,
    filter_value: str,
    *,
    local_now: Optional[datetime] = None,
) -> bool:
    """Return whether one Recent record matches a validated time filter."""

    clean_filter = _normalize_identifier(filter_value).lower()

    if not clean_filter:
        return True

    modified_at = _parse_datetime_value(
        payload.get("updated_at_utc")
        or payload.get("updated_at")
        or payload.get("uploaded_at_utc")
        or payload.get("uploaded_at")
    )

    if not modified_at:
        return False

    current_local = local_now or _current_utc_datetime().astimezone(
        _get_documents_timezone()
    )
    modified_local = modified_at.astimezone(
        _get_documents_timezone()
    )

    if clean_filter == "today":
        return modified_local.date() == current_local.date()

    if clean_filter == "last_7_days":
        return modified_local >= current_local - timedelta(days=7)

    if clean_filter == "last_30_days":
        return modified_local >= current_local - timedelta(days=30)

    if clean_filter == "this_year":
        return modified_local.year == current_local.year

    return False


def _recent_filter_options(payloads: list[dict]) -> dict:
    """Return only filter options derived from the authorized Recent corpus."""

    type_counts = {}
    people_counts = {}
    source_counts = {}
    local_now = _current_utc_datetime().astimezone(
        _get_documents_timezone()
    )

    for payload in payloads:
        type_value = _recent_filter_type_value(payload)
        people_value = _normalize_identifier(
            payload.get("owner_label")
        ) or "Me"
        source_value = _normalize_identifier(
            payload.get("source_label")
        ) or "My Files"

        type_counts[type_value] = type_counts.get(type_value, 0) + 1
        people_counts[people_value] = people_counts.get(people_value, 0) + 1
        source_counts[source_value] = source_counts.get(source_value, 0) + 1

    modified_options = []

    for value, label in RECENT_FILTER_MODIFIED_OPTIONS:
        modified_options.append({
            "value": value,
            "label": label,
            "count": sum(
                1
                for payload in payloads
                if _recent_matches_modified_filter(
                    payload,
                    value,
                    local_now=local_now,
                )
            ),
        })

    return {
        "type": _recent_filter_option_list(
            type_counts,
            labels=RECENT_FILTER_TYPE_LABELS,
        ),
        "people": _recent_filter_option_list(people_counts),
        "modified": modified_options,
        "source": _recent_filter_option_list(source_counts),
    }


def _recent_resolved_filters(filter_options: dict) -> dict:
    """Resolve request filters only against server-approved option values."""

    requested = {
        "type": _normalize_identifier(request.args.get("type")).lower(),
        "people": _normalize_identifier(request.args.get("people")),
        "modified": _normalize_identifier(request.args.get("modified")).lower(),
        "source": _normalize_identifier(request.args.get("source")),
    }
    resolved = {}

    for field_name, requested_value in requested.items():
        allowed_values = {
            _normalize_identifier(option.get("value"))
            for option in filter_options.get(field_name, [])
            if isinstance(option, dict)
        }
        resolved[field_name] = (
            requested_value
            if requested_value and requested_value in allowed_values
            else ""
        )

    return resolved


def _filter_recent_payloads(
    payloads: list[dict],
) -> tuple[list[dict], dict, dict]:
    """Apply validated Recent filters without changing authority membership."""

    filter_options = _recent_filter_options(payloads)
    selected_filters = _recent_resolved_filters(filter_options)
    filtered_payloads = []

    for payload in payloads:
        if (
            selected_filters["type"]
            and _recent_filter_type_value(payload)
            != selected_filters["type"]
        ):
            continue

        if (
            selected_filters["people"]
            and _normalize_identifier(payload.get("owner_label"))
            != selected_filters["people"]
        ):
            continue

        if (
            selected_filters["source"]
            and _normalize_identifier(payload.get("source_label"))
            != selected_filters["source"]
        ):
            continue

        if not _recent_matches_modified_filter(
            payload,
            selected_filters["modified"],
        ):
            continue

        filtered_payloads.append(payload)

    return filtered_payloads, selected_filters, filter_options


def _recent_sort_key(value) -> str:
    """Return one server-approved Recent sort key."""

    clean_key = _normalize_identifier(value).lower()
    aliases = {
        "date": "activity",
        "date_modified": "activity",
        "modified": "activity",
        "uploaded": "activity",
        "file_size": "size",
    }
    clean_key = aliases.get(clean_key, clean_key)

    if clean_key in RECENT_SORT_FIELDS:
        return clean_key

    return RECENT_SORT_DEFAULT_KEY


def _recent_sort_direction(value, *, sort_key: str) -> str:
    """Return one server-approved direction for a Recent sort key."""

    clean_direction = _normalize_identifier(value).lower()

    if clean_direction in RECENT_SORT_ALLOWED_DIRECTIONS:
        return clean_direction

    return str(
        RECENT_SORT_FIELDS.get(sort_key, {}).get(
            "default_direction",
            "desc",
        )
    )


def _recent_result_limit(value) -> Optional[int]:
    """Return a bounded server-approved post-filter Recent result limit."""

    clean_value = _normalize_identifier(value)

    if not clean_value:
        return None

    try:
        parsed_limit = int(clean_value)
    except (TypeError, ValueError):
        return None

    if parsed_limit <= 0:
        return None

    return min(parsed_limit, DOCUMENTS_FILE_CATALOG_LIMIT)


def _recent_sort_timestamp(payload: dict) -> float:
    """Return a comparable Recent activity timestamp."""

    parsed = _parse_datetime_value(
        payload.get("recent_activity_at_utc")
        or payload.get("recent_activity_at")
    )

    if not parsed:
        return 0.0

    try:
        return float(parsed.timestamp())
    except (OverflowError, OSError, ValueError):
        return 0.0


def _recent_sort_size(payload: dict) -> int:
    """Return a comparable byte count for a Recent file."""

    try:
        return int(payload.get("size_bytes") or 0)
    except (TypeError, ValueError):
        return 0


def _recent_sort_value(payload: dict, sort_key: str):
    """Return the server-owned ordering value for one Recent file."""

    if sort_key == "activity":
        return _recent_sort_timestamp(payload)

    if sort_key == "owner":
        return _normalize_identifier(payload.get("owner_label")).casefold()

    if sort_key == "location":
        return _normalize_identifier(payload.get("location_label")).casefold()

    if sort_key == "size":
        return _recent_sort_size(payload)

    return _normalize_identifier(
        payload.get("display_name")
        or payload.get("original_name")
        or payload.get("name")
        or payload.get("document_id")
    ).casefold()


def _sort_recent_payloads(
    payloads: list[dict],
    *,
    sort_key: str,
    direction: str,
) -> list[dict]:
    """Sort the already-filtered Recent result set deterministically."""

    return sorted(
        payloads,
        key=lambda payload: _recent_sort_value(payload, sort_key),
        reverse=direction == "desc",
    )


def _recent_sort_response(sort_key: str, direction: str) -> dict:
    """Return the browser projection of server-owned Recent sort authority."""

    return {
        "contract": RECENT_SORT_CONTRACT,
        "key": sort_key,
        "direction": direction,
        "default_key": RECENT_SORT_DEFAULT_KEY,
        "default_direction": RECENT_SORT_FIELDS[
            RECENT_SORT_DEFAULT_KEY
        ]["default_direction"],
        "allowed_keys": list(RECENT_SORT_FIELDS.keys()),
        "allowed_directions": sorted(RECENT_SORT_ALLOWED_DIRECTIONS),
        "folder_placement_supported": False,
        "options": [
            {
                "value": value,
                "label": field["label"],
                "default_direction": field["default_direction"],
                "direction_mode": field["direction_mode"],
            }
            for value, field in RECENT_SORT_FIELDS.items()
        ],
    }


def _recent_file_payloads(
    db_session,
    user_id: int,
    active_ids: set,
    saved_review_index: dict,
) -> list[dict]:
    """Return active authorized files ordered by per-user Recent activity."""

    ensure_file_recent_activity_table(db_session)
    resolved_records = []
    seen = set()
    authorized_files = resolve_authorized_file_registry_corpus(
        user_id=user_id,
        request_id="uploads.me.recent",
        limit=DOCUMENTS_FILE_CATALOG_LIMIT,
        action=DOCUMENTS_FILE_AUTHORIZATION_ACTION,
    )

    for authorized_file in authorized_files:
        if not isinstance(authorized_file, dict):
            continue

        record = _resolve_authorized_file_record(
            db_session,
            authorized_file,
        )

        if not record or _is_trashed_meta(_safe_meta_payload(record.meta)):
            continue

        document_id = _normalize_identifier(record.random_name)

        if not document_id or document_id in seen:
            continue

        resolved_records.append((record, authorized_file))
        seen.add(document_id)

    file_ids = [record.id for record, _ in resolved_records]
    uploader_ids = {
        int(record.uploader_id)
        for record, _ in resolved_records
        if getattr(record, "uploader_id", None)
    }
    folder_ids = {
        _normalize_identifier(record.workspace_folder_id)
        for record, _ in resolved_records
        if _normalize_identifier(record.workspace_folder_id)
    }
    activity_by_file_id = {
        activity.file_id: activity
        for activity in (
            db_session.query(FileRecentActivity)
            .filter(
                FileRecentActivity.user_id == user_id,
                FileRecentActivity.file_id.in_(file_ids),
            )
            .all()
            if file_ids
            else []
        )
    }
    users_by_id = {
        user.id: user
        for user in (
            db_session.query(User)
            .filter(User.id.in_(uploader_ids))
            .all()
            if uploader_ids
            else []
        )
    }
    folders_by_id = {
        folder.folder_id: folder
        for folder in (
            db_session.query(WorkspaceFolder)
            .filter(WorkspaceFolder.folder_id.in_(folder_ids))
            .all()
            if folder_ids
            else []
        )
    }
    payloads = []

    for record, authorized_file in resolved_records:
        payload = _file_registry_payload(
            record,
            active_ids,
            trash_only=False,
            access_payload=authorized_file,
            surface=FILE_SURFACE_RECENT,
        )

        if not payload:
            continue

        activity = activity_by_file_id.get(record.id)

        if activity:
            activity_at = _parse_datetime_value(activity.activity_at)
            activity_kind = _normalize_identifier(activity.activity_kind) or "opened"
        else:
            activity_at, activity_kind = _recent_activity_fallback(record)

        uploader_id = int(record.uploader_id or 0)
        owner = users_by_id.get(uploader_id)
        folder_id = _normalize_identifier(record.workspace_folder_id)
        folder = folders_by_id.get(folder_id)
        is_owner = uploader_id == user_id
        owner_label = "Me" if is_owner else (
            _normalize_identifier(getattr(owner, "username", ""))
            or _normalize_identifier(getattr(owner, "email", ""))
            or "Shared"
        )

        if folder and int(getattr(folder, "user_id", 0) or 0) == user_id:
            location_label = _normalize_identifier(folder.name) or "My Files"
        elif is_owner:
            location_label = "My Files"
        else:
            location_label = "Shared with me"

        source_label = "My Files" if is_owner else "Shared with me"

        payload.update({
            "recent_activity_at": _datetime_to_string(activity_at),
            "recent_activity_at_utc": _datetime_to_utc_string(activity_at),
            "recent_activity_kind": activity_kind,
            "recent_activity_reason": _recent_activity_reason(activity_kind),
            "recent_group_label": _recent_group_label(activity_at),
            "owner_label": owner_label,
            "source_label": source_label,
            "location_label": location_label,
            "workspace_location_label": location_label,
            "authorized_location_label": location_label,
        })
        _attach_saved_review_to_upload(
            payload,
            _find_saved_review_for_upload(
                payload,
                saved_review_index,
            ),
        )
        payloads.append(payload)

    payloads.sort(
        key=lambda item: item.get("recent_activity_at_utc") or "",
        reverse=True,
    )
    return payloads


def _recent_uploads_response_payload():
    """Return the current user's server-owned Recent activity view."""

    user_id = _get_current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    active_ids = _get_active_ids(user_id)
    saved_review_index = _load_saved_review_index(user_id)
    db_session = SessionLocal()

    try:
        recent_corpus = _recent_file_payloads(
            db_session,
            user_id,
            active_ids,
            saved_review_index,
        )
        uploads, selected_filters, filter_options = (
            _filter_recent_payloads(recent_corpus)
        )
        sort_key = _recent_sort_key(request.args.get("sort"))
        sort_direction = _recent_sort_direction(
            request.args.get("direction"),
            sort_key=sort_key,
        )
        uploads = _sort_recent_payloads(
            uploads,
            sort_key=sort_key,
            direction=sort_direction,
        )
        matched_count = len(uploads)
        result_limit = _recent_result_limit(
            request.args.get("limit")
        )

        if result_limit is not None:
            uploads = uploads[:result_limit]
    finally:
        db_session.close()

    return jsonify({
        "ok": True,
        "status": "ok",
        "owner": user_id,
        "current_user": user_id,
        "collection": "recent",
        "recent": True,
        "trash": False,
        "file_authority": "authorized_discover",
        "filter_contract": RECENT_FILTER_CONTRACT,
        "filters": selected_filters,
        "filter_options": filter_options,
        "filtered": any(selected_filters.values()),
        "sort_contract": RECENT_SORT_CONTRACT,
        "sort": _recent_sort_response(sort_key, sort_direction),
        "unfiltered_count": len(recent_corpus),
        "matched_count": matched_count,
        "limit": result_limit,
        "count": len(uploads),
        "folder_count": 0,
        "workspace_item_count": len(uploads),
        "document_operation_contract": DOCUMENT_OPERATION_CONTRACT,
        "document_operation_route": DOCUMENT_OPERATION_ROUTE,
        "operation_key": DOCUMENT_OPERATION_KEY,
        "analysis_status": "not_started",
        "uploads": uploads,
        "folders": [],
        "items": uploads,
        "workspace_items": uploads,
    }), 200


def _owned_trash_file_payloads(
    db_session,
    user_id: int,
    active_ids: set,
    saved_review_index: dict,
) -> list[dict]:
    """Return recoverably trashed files controlled by the current owner."""

    payloads = []
    records = (
        db_session.query(FileRegistry)
        .filter(
            FileRegistry.uploader_id
            == user_id
        )
        .order_by(
            FileRegistry.upload_time.desc()
        )
        .all()
    )

    for record in records:
        payload = _file_registry_payload(
            record,
            active_ids,
            trash_only=True,
            access_payload={
                "access_scope": "my_trash",
                "permission": "manage",
                "authorized_action": READ_ACTION,
                "authority_basis": "personal_owner_trash",
                "policy_version": "personal_file_permissions_v1",
                "is_discoverable": False,
                "allow_ai_query": False,
            },
            surface=FILE_SURFACE_TRASH,
        )

        if not payload:
            continue

        _attach_saved_review_to_upload(
            payload,
            _find_saved_review_for_upload(
                payload,
                saved_review_index,
            ),
        )
        payloads.append(payload)

    return payloads


def _workspace_folder_owner_display(
    folder: WorkspaceFolder,
    requesting_user_id: int = 0,
) -> str:
    """Return an owner label without triggering detached lazy loading."""

    owner_user_id = int(getattr(folder, "user_id", 0) or 0)

    if requesting_user_id and owner_user_id == int(requesting_user_id):
        return "Me"

    owner = getattr(folder, "__dict__", {}).get("owner_user")

    for field_name in ("name", "username", "email"):
        value = _normalize_identifier(
            getattr(owner, field_name, "")
            if owner
            else ""
        )

        if value:
            return value

    return "Owner"


def _workspace_folder_payload(
    folder: WorkspaceFolder,
    *,
    requesting_user_id: int = 0,
    access_context: Optional[dict] = None,
    has_authorized_children: bool = False,
    authorized_parent: Optional[WorkspaceFolder] = None,
) -> Optional[dict]:
    """Build a safe, authority-filtered Documents folder payload."""

    if not folder:
        return None

    folder_id = _normalize_identifier(
        getattr(folder, "folder_id", "")
    )
    folder_name = _normalize_folder_name(
        getattr(folder, "name", "")
    )

    if not folder_id or not folder_name:
        return None

    context = access_context or {}
    decision = _workspace_folder_access_decision(
        folder,
        requesting_user_id,
        context,
    )

    if requesting_user_id and not decision["authorized"]:
        return None

    folder_status = _workspace_folder_status(folder)
    is_shared = bool(decision["is_shared"])
    can_manage = bool(decision["is_owner"])
    parent_id = _normalize_identifier(
        getattr(authorized_parent, "folder_id", "")
        if authorized_parent
        else ""
    )
    parent_name = _normalize_folder_name(
        getattr(authorized_parent, "name", "")
        if authorized_parent
        else ""
    )
    folder_url = _build_workspace_folder_url(
        folder_id,
        shared=is_shared,
    )
    folder_capabilities = _workspace_folder_capabilities(
        folder_status,
        can_manage=can_manage,
    )
    folder_actions = _workspace_folder_available_actions(
        folder_status,
        can_manage=can_manage,
    )

    return {
        "workspace_item_type": "folder",
        "item_type": "folder",
        "resource_type": "folder",
        "document_kind": "folder",
        "folder": True,
        "folder_id": folder_id,
        "workspace_item_id": folder_id,
        "object_type": "folder",
        "container_type": "workspace_folder",
        "canonical_url": folder_url,
        "folder_url": folder_url,
        "open_url": folder_url,
        "document_id": "",
        "file_id": "",
        "original_name": folder_name,
        "display_name": folder_name,
        "name": folder_name,
        "random_name": folder_id,
        "folder_contract": (
            getattr(folder, "folder_contract", "")
            or WORKSPACE_FOLDER_CONTRACT
        ),
        "parent_folder_id": parent_id,
        "authorized_parent_id": parent_id,
        "parent_folder_name": parent_name,
        "parent_folder_key": (
            parent_id
            or WORKSPACE_FOLDER_ROOT_PARENT_KEY
        ),
        "path_key": (
            folder_id
            if is_shared
            else _normalize_identifier(
                getattr(folder, "path_key", "")
            )
        ),
        "depth": (
            1
            if is_shared and authorized_parent
            else 0
            if is_shared
            else int(getattr(folder, "depth", 0) or 0)
        ),
        "sort_order": int(getattr(folder, "sort_order", 0) or 0),
        "visibility_scope": decision["visibility_scope"],
        "access_scope": decision["access_scope"],
        "authority_basis": decision["authority_basis"],
        "shared": is_shared,
        "root_scope": (
            WORKSPACE_FOLDER_COLLECTION_SHARED
            if is_shared
            else WORKSPACE_FOLDER_COLLECTION_PERSONAL
        ),
        "owner_display": _workspace_folder_owner_display(
            folder,
            requesting_user_id,
        ),
        "authorized_location": (
            "Shared with me"
            if is_shared
            else "My Drive"
        ),
        "has_authorized_children": bool(has_authorized_children),
        "folder_visibility_policy": WORKSPACE_FOLDER_VISIBILITY_POLICY,
        "folder_permission_scope": "explicit_folder_grants_v1",
        "file_authority_inherited": "dynamic_explicit_folder_grant",
        "allow_ai_query": False,
        "organization_id": _normalize_identifier(
            getattr(folder, "organization_id", "")
        ),
        "group_id": _normalize_identifier(
            getattr(folder, "group_id", "")
        ),
        "size_bytes": None,
        "uploaded_at": _datetime_to_string(
            getattr(folder, "created_at", None)
        ),
        "created_at": _datetime_to_string(
            getattr(folder, "created_at", None)
        ),
        "updated_at": _datetime_to_string(
            getattr(folder, "updated_at", None)
        ),
        "uploaded_at_utc": _datetime_to_utc_string(
            getattr(folder, "created_at", None)
        ),
        "created_at_utc": _datetime_to_utc_string(
            getattr(folder, "created_at", None)
        ),
        "updated_at_utc": _datetime_to_utc_string(
            getattr(folder, "updated_at", None)
        ),
        "trashed": folder_status == WORKSPACE_FOLDER_TRASH_STATUS,
        "trashed_at": _datetime_to_string(
            getattr(folder, "deleted_at", None)
        ),
        "trashed_at_utc": _datetime_to_utc_string(
            getattr(folder, "deleted_at", None)
        ),
        "document_status": folder_status,
        "active": False,
        "selected_for_workflow": False,
        "reader_url": "",
        "workspace_reader_url": "",
        "thumbnail_url": "",
        "preview_thumbnail_url": "",
        "workspace_thumbnail_url": "",
        "thumbnail_state": "folder",
        "thumbnail_kind": "folder",
        "thumbnail_source": "workspace_folder",
        "workflow_status": "not_applicable",
        "analysis_status": "not_applicable",
        "handoff_required": False,
        "handoff": {},
        "document_operation": {},
        "capabilities": folder_capabilities,
        "surface_actions_authoritative": True,
        "surface_actions": list(folder_actions),
        "available_actions": list(folder_actions),
        "actions": list(folder_actions),
        "action_surface": (
            "trash"
            if folder_status == WORKSPACE_FOLDER_TRASH_STATUS
            else "shared"
            if is_shared
            else "files"
        ),
    }


def _load_authorized_workspace_folder_records(
    db_session,
    user_id: int,
    *,
    trash_only: bool = False,
    access_context: Optional[dict] = None,
) -> tuple[list[WorkspaceFolder], dict]:
    """Load owner folders plus explicit-grant roots and their descendants."""

    context = access_context or _workspace_folder_access_context(
        db_session,
        user_id,
    )

    if trash_only:
        candidates = (
            db_session.query(WorkspaceFolder)
            .options(joinedload(WorkspaceFolder.owner_user))
            .filter(WorkspaceFolder.user_id == user_id)
            .order_by(WorkspaceFolder.updated_at.desc())
            .all()
        )
    else:
        candidates_by_id = {
            str(record.folder_id): record
            for record in (
                db_session.query(WorkspaceFolder)
                .options(joinedload(WorkspaceFolder.owner_user))
                .filter(
                    WorkspaceFolder.user_id == user_id,
                    WorkspaceFolder.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
                    WorkspaceFolder.deleted_at.is_(None),
                )
                .all()
            )
        }

        shared_root_ids = {
            str(folder_id)
            for (folder_id,) in (
                db_session.query(FolderAccessGrant.workspace_folder_id)
                .filter(
                    FolderAccessGrant.granted_to_user_id == user_id,
                    FolderAccessGrant.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
                    FolderAccessGrant.revoked_at.is_(None),
                )
                .all()
            )
            if folder_id
        }

        group_ids = tuple(context.get("group_ids") or ())
        if group_ids:
            shared_root_ids.update(
                str(folder_id)
                for (folder_id,) in (
                    db_session.query(FolderGroupAccessGrant.workspace_folder_id)
                    .filter(
                        FolderGroupAccessGrant.group_id.in_(group_ids),
                        FolderGroupAccessGrant.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
                        FolderGroupAccessGrant.revoked_at.is_(None),
                    )
                    .all()
                )
                if folder_id
            )

        frontier = set(shared_root_ids)
        visited = set()

        while frontier:
            current = frontier - visited
            if not current:
                break
            visited.update(current)

            rows = (
                db_session.query(WorkspaceFolder)
                .options(joinedload(WorkspaceFolder.owner_user))
                .filter(
                    WorkspaceFolder.status == WORKSPACE_FOLDER_ACTIVE_STATUS,
                    WorkspaceFolder.deleted_at.is_(None),
                    or_(
                        WorkspaceFolder.folder_id.in_(tuple(current)),
                        WorkspaceFolder.parent_folder_id.in_(tuple(current)),
                    ),
                )
                .all()
            )

            next_frontier = set()
            for row in rows:
                row_id = _normalize_identifier(getattr(row, "folder_id", ""))
                if row_id:
                    candidates_by_id[row_id] = row
                parent_id = _normalize_identifier(
                    getattr(row, "parent_folder_id", "")
                )
                if parent_id in current and row_id and row_id not in visited:
                    next_frontier.add(row_id)
            frontier = next_frontier

        candidates = list(candidates_by_id.values())

    records = []
    for record in candidates:
        status = _workspace_folder_status(record)

        if trash_only and status != WORKSPACE_FOLDER_TRASH_STATUS:
            continue
        if not trash_only and status != WORKSPACE_FOLDER_ACTIVE_STATUS:
            continue

        decision = _workspace_folder_access_decision(
            record,
            user_id,
            context,
        )
        if decision["authorized"]:
            records.append(record)

    return records, context

def _workspace_folder_collection_scope(
    folder: WorkspaceFolder,
    user_id: int,
) -> str:
    """Return the virtual root that contains an authorized folder."""

    return (
        WORKSPACE_FOLDER_COLLECTION_PERSONAL
        if str(getattr(folder, "user_id", "")) == str(user_id)
        else WORKSPACE_FOLDER_COLLECTION_SHARED
    )


def _load_workspace_folder_payloads(
    db_session,
    user_id: int,
    *,
    trash_only: bool = False,
    parent_folder_key: Optional[str] = None,
    collection_scope: str = WORKSPACE_FOLDER_COLLECTION_PERSONAL,
    records: Optional[list[WorkspaceFolder]] = None,
    access_context: Optional[dict] = None,
) -> list[dict]:
    """Return direct authorized folders for one virtual or durable container."""

    if not user_id:
        return []

    if records is None:
        records, access_context = _load_authorized_workspace_folder_records(
            db_session,
            user_id,
            trash_only=trash_only,
            access_context=access_context,
        )

    context = access_context or _workspace_folder_access_context(
        db_session,
        user_id,
    )
    scoped_records = [
        record
        for record in records
        if trash_only
        or _workspace_folder_collection_scope(record, user_id)
        == collection_scope
    ]
    by_id = {
        _normalize_identifier(getattr(record, "folder_id", "")): record
        for record in scoped_records
        if _normalize_identifier(getattr(record, "folder_id", ""))
    }
    scoped_ids = {
        _normalize_identifier(getattr(record, "folder_id", ""))
        for record in scoped_records
    }
    requested_parent_key = (
        _workspace_folder_parent_key(parent_folder_key)
        if parent_folder_key is not None
        else None
    )
    candidates = []

    for record in scoped_records:
        record_parent_id = _normalize_identifier(
            getattr(record, "parent_folder_id", "")
        )
        record_parent_key = _workspace_folder_parent_key(
            getattr(record, "parent_folder_key", "")
        )

        if trash_only and requested_parent_key is None:
            candidates.append(record)
        elif requested_parent_key is not None:
            if record_parent_key == requested_parent_key:
                candidates.append(record)
        elif collection_scope == WORKSPACE_FOLDER_COLLECTION_SHARED:
            if not record_parent_id or record_parent_id not in scoped_ids:
                candidates.append(record)
        elif record_parent_key == WORKSPACE_FOLDER_ROOT_PARENT_KEY:
            candidates.append(record)

    child_parent_ids = {
        _normalize_identifier(getattr(record, "parent_folder_id", ""))
        for record in scoped_records
        if _normalize_identifier(getattr(record, "parent_folder_id", ""))
    }
    payloads = []

    for record in candidates:
        folder_id = _normalize_identifier(
            getattr(record, "folder_id", "")
        )
        parent = by_id.get(
            _normalize_identifier(
                getattr(record, "parent_folder_id", "")
            )
        )
        payload = _workspace_folder_payload(
            record,
            requesting_user_id=user_id,
            access_context=context,
            has_authorized_children=folder_id in child_parent_ids,
            authorized_parent=parent,
        )

        if payload:
            payloads.append(payload)

    payloads.sort(
        key=lambda item: (
            _normalize_folder_lookup_name(item.get("name")),
            item.get("folder_id") or "",
        )
    )

    return payloads


def _workspace_folder_breadcrumbs(
    current_folder: Optional[WorkspaceFolder],
    user_id: int,
    records: list[WorkspaceFolder],
    access_context: dict,
    collection_scope: str,
) -> list[dict]:
    """Return only authorized breadcrumb nodes for the current folder."""

    root_route = (
        "/shared"
        if collection_scope == WORKSPACE_FOLDER_COLLECTION_SHARED
        else "/"
    )
    breadcrumbs = [{
        "object_type": "virtual_root",
        "folder_id": "",
        "name": (
            "Shared with me"
            if collection_scope == WORKSPACE_FOLDER_COLLECTION_SHARED
            else "My Files"
        ),
        "route": root_route,
    }]

    if not current_folder:
        return breadcrumbs

    by_id = {
        _normalize_identifier(getattr(record, "folder_id", "")): record
        for record in records
    }
    chain = []
    cursor = current_folder
    seen = set()

    while cursor:
        folder_id = _normalize_identifier(
            getattr(cursor, "folder_id", "")
        )

        if not folder_id or folder_id in seen:
            break

        seen.add(folder_id)
        decision = _workspace_folder_access_decision(
            cursor,
            user_id,
            access_context,
        )

        if not decision["authorized"]:
            break

        if _workspace_folder_collection_scope(cursor, user_id) != collection_scope:
            break

        chain.append(cursor)
        parent_id = _normalize_identifier(
            getattr(cursor, "parent_folder_id", "")
        )
        cursor = by_id.get(parent_id)

    for folder in reversed(chain):
        decision = _workspace_folder_access_decision(
            folder,
            user_id,
            access_context,
        )
        folder_id = _normalize_identifier(
            getattr(folder, "folder_id", "")
        )
        breadcrumbs.append({
            "object_type": "folder",
            "folder_id": folder_id,
            "name": _normalize_folder_name(
                getattr(folder, "name", "")
            ),
            "route": _build_workspace_folder_url(
                folder_id,
                shared=bool(decision["is_shared"]),
            ),
        })

    return breadcrumbs


def _workspace_item_sort_key(item: dict) -> str:
    """Return the preferred sort key for files and folders together."""

    if not isinstance(item, dict):
        return ""

    return (
        item.get("updated_at_utc")
        or item.get("uploaded_at_utc")
        or item.get("created_at_utc")
        or ""
    )


def _workspace_file_parent_key(payload: dict) -> str:
    """Return the canonical folder container key for a file payload."""

    if not isinstance(payload, dict):
        return WORKSPACE_FOLDER_ROOT_PARENT_KEY

    return _workspace_folder_parent_key(
        payload.get("workspace_folder_id")
        or payload.get("parent_folder_id")
    )


def _file_payload_is_in_folder(
    payload: dict,
    parent_folder_key: str,
) -> bool:
    """Return whether a file payload belongs in the requested folder."""

    return (
        _workspace_file_parent_key(payload)
        == _workspace_folder_parent_key(parent_folder_key)
    )


def _uploads_sort_key(
    item: dict,
    trash_only: bool,
) -> str:
    """Return the preferred sort key for an upload collection."""

    if trash_only:
        return (
            item.get("trashed_at_utc")
            or item.get("updated_at_utc")
            or ""
        )

    return item.get("uploaded_at_utc") or ""


def _uploads_response_payload(
    *,
    trash_only: bool = False,
    collection_scope: str = WORKSPACE_FOLDER_COLLECTION_PERSONAL,
):
    """Return an authority-filtered mixed listing for one Documents location."""

    user_id = _get_current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    active_ids = _get_active_ids(user_id)
    saved_review_index = _load_saved_review_index(
        user_id
    )
    requested_folder_id = (
        ""
        if trash_only
        else _request_folder_identifier()
    )
    current_folder = None
    current_folder_id = ""
    current_folder_key = WORKSPACE_FOLDER_ROOT_PARENT_KEY
    uploads = []
    folders = []
    db_session = SessionLocal()

    try:
        access_context = _workspace_folder_access_context(
            db_session,
            user_id,
        )
        visible_records, access_context = (
            _load_authorized_workspace_folder_records(
                db_session,
                user_id,
                trash_only=trash_only,
                access_context=access_context,
            )
        )

        if not trash_only:
            (
                current_folder,
                current_folder_key,
                current_folder_id,
                location_error,
            ) = _resolve_listing_parent_folder(
                db_session,
                user_id,
                requested_folder_id,
                access_context=access_context,
            )

            if location_error:
                return location_error

            if (
                current_folder
                and _workspace_folder_collection_scope(
                    current_folder,
                    user_id,
                ) != collection_scope
            ):
                return jsonify({
                    "ok": False,
                    "error": "Folder not found",
                    "contract": WORKSPACE_FOLDER_CONTRACT,
                }), 404

        folders = _load_workspace_folder_payloads(
            db_session,
            user_id,
            trash_only=trash_only,
            parent_folder_key=(
                None
                if trash_only
                else current_folder_key
                if current_folder
                else None
            ),
            collection_scope=collection_scope,
            records=visible_records,
            access_context=access_context,
        )

        if trash_only:
            uploads = _owned_trash_file_payloads(
                db_session,
                user_id,
                active_ids,
                saved_review_index,
            )
        elif current_folder:
            uploads = _authorized_file_payloads(
                db_session,
                user_id,
                active_ids,
                saved_review_index,
                parent_folder_key=current_folder_key,
            )
        elif collection_scope == WORKSPACE_FOLDER_COLLECTION_SHARED:
            shared_folder_ids = {
                _normalize_identifier(getattr(record, "folder_id", ""))
                for record in visible_records
                if _workspace_folder_collection_scope(record, user_id)
                == WORKSPACE_FOLDER_COLLECTION_SHARED
            }
            uploads = _authorized_file_payloads(
                db_session,
                user_id,
                active_ids,
                saved_review_index,
                ownership_scope=WORKSPACE_FOLDER_COLLECTION_SHARED,
                include_any_parent=True,
                excluded_folder_ids=shared_folder_ids,
            )
        else:
            uploads = _authorized_file_payloads(
                db_session,
                user_id,
                active_ids,
                saved_review_index,
                parent_folder_key=WORKSPACE_FOLDER_ROOT_PARENT_KEY,
                ownership_scope=WORKSPACE_FOLDER_COLLECTION_PERSONAL,
            )

        current_folder_payload = (
            _workspace_folder_payload(
                current_folder,
                requesting_user_id=user_id,
                access_context=access_context,
                has_authorized_children=any(
                    _normalize_identifier(
                        getattr(record, "parent_folder_id", "")
                    ) == current_folder_id
                    and _workspace_folder_collection_scope(
                        record,
                        user_id,
                    ) == collection_scope
                    for record in visible_records
                ),
                authorized_parent=next((
                    record
                    for record in visible_records
                    if _normalize_identifier(
                        getattr(record, "folder_id", "")
                    ) == _normalize_identifier(
                        getattr(current_folder, "parent_folder_id", "")
                    )
                    and _workspace_folder_collection_scope(
                        record,
                        user_id,
                    ) == collection_scope
                ), None),
            )
            if current_folder
            else None
        )
        breadcrumbs = _workspace_folder_breadcrumbs(
            current_folder,
            user_id,
            visible_records,
            access_context,
            collection_scope,
        )
    finally:
        db_session.close()

    uploads.sort(
        key=lambda item: _uploads_sort_key(
            item,
            trash_only,
        ),
        reverse=True,
    )
    workspace_items = sorted(
        [*folders, *uploads],
        key=_workspace_item_sort_key,
        reverse=True,
    )

    return jsonify({
        "ok": True,
        "status": "ok",
        "owner": user_id,
        "current_user": user_id,
        "file_authority": (
            "owner_trash"
            if trash_only
            else "authorized_discover"
        ),
        "folder_authority": (
            "owner_trash"
            if trash_only
            else "server_authorized_folder_visibility"
        ),
        "folder_contract": WORKSPACE_FOLDER_CONTRACT,
        "folder_visibility_policy": WORKSPACE_FOLDER_VISIBILITY_POLICY,
        "collection": (
            "trash"
            if trash_only
            else "shared"
            if collection_scope == WORKSPACE_FOLDER_COLLECTION_SHARED
            else "all"
        ),
        "root_scope": collection_scope,
        "virtual_root": not bool(current_folder_id),
        "trash": trash_only,
        "folder_id": current_folder_id,
        "current_folder_id": current_folder_id,
        "parent_folder_id": current_folder_id,
        "parent_folder_key": current_folder_key,
        "current_folder": current_folder_payload,
        "breadcrumbs": breadcrumbs,
        "is_root_folder": not bool(current_folder_id),
        "count": len(uploads),
        "folder_count": len(folders),
        "workspace_item_count": len(workspace_items),
        "active_count": len(active_ids),
        "document_operation_contract": DOCUMENT_OPERATION_CONTRACT,
        "document_operation_route": DOCUMENT_OPERATION_ROUTE,
        "operation_key": DOCUMENT_OPERATION_KEY,
        "analysis_status": "not_started",
        "uploads": uploads,
        "folders": folders,
        "items": workspace_items,
        "workspace_items": workspace_items,
    }), 200


def _normalize_folder_collection_scope(value: str) -> str:
    """Return a supported virtual folder root."""

    clean_scope = _normalize_lookup_key(value)

    if clean_scope == WORKSPACE_FOLDER_COLLECTION_SHARED:
        return WORKSPACE_FOLDER_COLLECTION_SHARED

    return WORKSPACE_FOLDER_COLLECTION_PERSONAL


def _folders_response_payload(
    *,
    trash_only: bool = False,
    collection_scope: str = WORKSPACE_FOLDER_COLLECTION_PERSONAL,
):
    """Return authorized direct child folders for one navigation node."""

    user_id = _get_current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    requested_folder_id = (
        ""
        if trash_only
        else _request_folder_identifier()
    )
    current_folder = None
    current_folder_id = ""
    current_folder_key = WORKSPACE_FOLDER_ROOT_PARENT_KEY
    db_session = SessionLocal()

    try:
        access_context = _workspace_folder_access_context(
            db_session,
            user_id,
        )
        visible_records, access_context = (
            _load_authorized_workspace_folder_records(
                db_session,
                user_id,
                trash_only=trash_only,
                access_context=access_context,
            )
        )

        if not trash_only:
            (
                current_folder,
                current_folder_key,
                current_folder_id,
                location_error,
            ) = _resolve_listing_parent_folder(
                db_session,
                user_id,
                requested_folder_id,
                access_context=access_context,
            )

            if location_error:
                return location_error

            if (
                current_folder
                and _workspace_folder_collection_scope(
                    current_folder,
                    user_id,
                ) != collection_scope
            ):
                return jsonify({
                    "ok": False,
                    "error": "Folder not found",
                    "contract": WORKSPACE_FOLDER_CONTRACT,
                }), 404

        folders = _load_workspace_folder_payloads(
            db_session,
            user_id,
            trash_only=trash_only,
            parent_folder_key=(
                None
                if trash_only
                else current_folder_key
                if current_folder
                else None
            ),
            collection_scope=collection_scope,
            records=visible_records,
            access_context=access_context,
        )
        current_folder_payload = (
            _workspace_folder_payload(
                current_folder,
                requesting_user_id=user_id,
                access_context=access_context,
            )
            if current_folder
            else None
        )
        breadcrumbs = _workspace_folder_breadcrumbs(
            current_folder,
            user_id,
            visible_records,
            access_context,
            collection_scope,
        )
    finally:
        db_session.close()

    return jsonify({
        "ok": True,
        "status": "ok",
        "owner": user_id,
        "collection": (
            "trash_folders"
            if trash_only
            else "shared_folders"
            if collection_scope == WORKSPACE_FOLDER_COLLECTION_SHARED
            else "folders"
        ),
        "root_scope": collection_scope,
        "trash": trash_only,
        "folder_contract": WORKSPACE_FOLDER_CONTRACT,
        "folder_visibility_policy": WORKSPACE_FOLDER_VISIBILITY_POLICY,
        "folder_id": current_folder_id,
        "current_folder_id": current_folder_id,
        "parent_folder_id": current_folder_id,
        "parent_folder_key": current_folder_key,
        "current_folder": current_folder_payload,
        "breadcrumbs": breadcrumbs,
        "is_root_folder": not bool(current_folder_id),
        "count": len(folders),
        "folder_count": len(folders),
        "folders": folders,
    }), 200


@user_uploads_bp.route(
    "/me/folders",
    methods=["GET"],
)
@login_required
def list_my_workspace_folders():
    """Return active folders controlled by the current user."""

    return _folders_response_payload(
        trash_only=False,
        collection_scope=_normalize_folder_collection_scope(
            request.args.get("scope")
        ),
    )


@user_uploads_bp.route(
    "/me/folders",
    methods=["POST"],
)
@login_required
def create_my_workspace_folder():
    """Create one server-owned folder in the Documents workspace."""

    user_id = _get_current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    payload = _request_payload()
    authority_error = _folder_create_authority_error_payload(
        payload
    )

    if authority_error:
        logger.warning(
            (
                "[uploads.folder_create_rejected_client_authority] "
                "user_id=%s rejected_fields=%s"
            ),
            user_id,
            ",".join(authority_error["rejected_fields"]),
        )
        return jsonify(authority_error), 400

    folder_name = _normalize_folder_name(
        payload.get("name")
        or payload.get("folder_name")
    )
    name_error = _folder_name_validation_error(folder_name)

    if name_error:
        return jsonify({
            "ok": False,
            "error": name_error,
            "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
        }), 400

    parent_identifier = _folder_parent_identifier(payload)
    parent_folder = None
    parent_folder_key = WORKSPACE_FOLDER_ROOT_PARENT_KEY
    folder_scope = WORKSPACE_FOLDER_OWNER_SCOPE
    normalized_name = _normalize_folder_lookup_name(folder_name)
    db_session = SessionLocal()

    try:
        access_context = _workspace_folder_access_context(
            db_session,
            user_id,
        )

        if not _is_workspace_root_parent(parent_identifier):
            parent_folder = _resolve_folder_record(
                db_session,
                user_id,
                parent_identifier,
                active_only=True,
                require_owner=True,
                access_context=access_context,
            )

            if not parent_folder:
                return jsonify({
                    "ok": False,
                    "error": "Parent folder not found",
                    "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
                }), 404

            parent_folder_key = _workspace_folder_parent_key(
                getattr(parent_folder, "folder_id", "")
            )
            folder_scope = WORKSPACE_FOLDER_OWNER_SCOPE

        existing_folder = _find_active_workspace_folder_conflict(
            db_session,
            user_id,
            folder_scope,
            parent_folder_key,
            normalized_name,
        )

        if existing_folder:
            return jsonify({
                "ok": False,
                "error": "A folder with that name already exists here",
                "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
                "folder": _workspace_folder_payload(
                    existing_folder,
                    requesting_user_id=user_id,
                    access_context=access_context,
                ),
            }), 409

        parent_depth = int(
            getattr(parent_folder, "depth", -1)
            if parent_folder
            else -1
        )
        folder_depth = parent_depth + 1

        if folder_depth > WORKSPACE_FOLDER_MAX_DEPTH:
            return jsonify({
                "ok": False,
                "error": "Folder nesting is too deep",
                "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
                "max_depth": WORKSPACE_FOLDER_MAX_DEPTH,
            }), 400

        folder_id = uuid.uuid4().hex
        now = _current_utc_datetime()
        folder = WorkspaceFolder(
            folder_id=folder_id,
            folder_contract=WORKSPACE_FOLDER_CONTRACT,
            user_id=user_id,
            parent_folder_id=(
                getattr(parent_folder, "folder_id", None)
                if parent_folder
                else None
            ),
            parent_folder_key=parent_folder_key,
            organization_id=None,
            group_id=None,
            name=folder_name,
            normalized_name=normalized_name,
            path_key=_workspace_folder_path_key(
                folder_id,
                parent_folder,
            ),
            depth=folder_depth,
            sort_order=0,
            status=WORKSPACE_FOLDER_ACTIVE_STATUS,
            visibility_scope=folder_scope,
            is_discoverable=True,
            metadata_json={
                "created_from": "documents_workspace",
                "creation_contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
                "folder_status": WORKSPACE_FOLDER_ACTIVE_STATUS,
                "folder_visibility_policy": (
                    WORKSPACE_FOLDER_VISIBILITY_POLICY
                ),
                "file_authority_inherited": "dynamic_explicit_folder_grant",
            },
            created_by_user_id=user_id,
            updated_by_user_id=user_id,
            created_at=now,
            updated_at=now,
        )

        db_session.add(folder)
        db_session.commit()
        db_session.refresh(folder)

        folder_payload = _workspace_folder_payload(
            folder,
            requesting_user_id=user_id,
            access_context=access_context,
        )

        logger.info(
            (
                "[uploads.folder_created] "
                "user_id=%s folder_id=%s parent_folder_key=%s "
                "contract=%s"
            ),
            user_id,
            folder_id,
            parent_folder_key,
            WORKSPACE_FOLDER_CREATION_CONTRACT,
        )

        return jsonify({
            "ok": True,
            "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
            "created": folder_payload,
            "folder": folder_payload,
        }), 201
    except IntegrityError:
        db_session.rollback()
        existing_folder = _find_active_workspace_folder_conflict(
            db_session,
            user_id,
            folder_scope,
            parent_folder_key,
            normalized_name,
        )

        if existing_folder:
            return jsonify({
                "ok": False,
                "error": "A folder with that name already exists here",
                "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
                "folder": _workspace_folder_payload(
                    existing_folder,
                    requesting_user_id=user_id,
                    access_context=access_context,
                ),
            }), 409

        logger.warning(
            (
                "[uploads.folder_create_integrity_conflict] "
                "user_id=%s parent_folder_key=%s"
            ),
            user_id,
            parent_folder_key,
        )
        return jsonify({
            "ok": False,
            "error": "Folder could not be created because it conflicts "
                     "with an existing workspace folder",
            "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
        }), 409
    except Exception as exc:
        db_session.rollback()
        logger.error(
            (
                "[uploads.folder_create_failed] "
                "user_id=%s parent_folder_id=%s error=%s"
            ),
            user_id,
            parent_identifier,
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "Failed to create folder",
            "contract": WORKSPACE_FOLDER_CREATION_CONTRACT,
        }), 500
    finally:
        db_session.close()


def _workspace_folder_mutation_payload(
    folder: WorkspaceFolder,
    user_id: int,
    access_context: dict,
) -> dict:
    """Return one authoritative folder lifecycle mutation payload."""

    return _workspace_folder_payload(
        folder,
        requesting_user_id=user_id,
        access_context=access_context,
    ) or {}


@user_uploads_bp.route(
    "/me/folders/<identifier>",
    methods=["DELETE"],
)
@login_required
def move_my_workspace_folder_to_trash(identifier):
    """Move one empty user-owned folder into recoverable Trash."""

    user_id = _get_current_user_id()
    clean_identifier = _normalize_identifier(identifier)

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    if not clean_identifier:
        return jsonify({
            "ok": False,
            "error": "Missing folder identifier",
            "contract": WORKSPACE_FOLDER_CONTRACT,
        }), 400

    db_session = SessionLocal()

    try:
        access_context = _workspace_folder_access_context(
            db_session,
            user_id,
        )
        folder = _resolve_folder_record(
            db_session,
            user_id,
            clean_identifier,
            active_only=True,
            require_owner=True,
            access_context=access_context,
        )

        if not folder:
            return jsonify({
                "ok": False,
                "error": "Folder not found",
                "contract": WORKSPACE_FOLDER_CONTRACT,
            }), 404

        empty_error = _workspace_folder_empty_error_payload(
            db_session,
            folder,
        )

        if empty_error:
            return jsonify(empty_error), 409

        if _find_trashed_workspace_folder_conflict(db_session, folder):
            return jsonify({
                "ok": False,
                "error": "A folder with that name already exists in Trash.",
                "contract": WORKSPACE_FOLDER_CONTRACT,
            }), 409

        now = _current_utc_datetime()
        folder.status = WORKSPACE_FOLDER_TRASH_STATUS
        folder.is_discoverable = False
        folder.deleted_at = now
        folder.updated_at = now
        folder.updated_by_user_id = user_id
        db_session.commit()
        db_session.refresh(folder)
        moved_payload = _workspace_folder_mutation_payload(
            folder,
            user_id,
            access_context,
        )

        logger.info(
            "[uploads.folder_move_to_trash] user_id=%s folder_id=%s",
            user_id,
            clean_identifier,
        )

        return jsonify({
            "ok": True,
            "contract": WORKSPACE_FOLDER_CONTRACT,
            "folder_non_recursive": True,
            "moved_to_trash": moved_payload,
            "folder": moved_payload,
        }), 200
    except IntegrityError:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "A folder with that name already exists in Trash.",
            "contract": WORKSPACE_FOLDER_CONTRACT,
        }), 409
    except Exception as exc:
        db_session.rollback()
        logger.error(
            "[uploads.folder_move_to_trash_failed] user_id=%s folder_id=%s error=%s",
            user_id,
            clean_identifier,
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "Failed to move folder to Trash",
            "contract": WORKSPACE_FOLDER_CONTRACT,
        }), 500
    finally:
        db_session.close()


@user_uploads_bp.route(
    "/me/folders/trash/<identifier>/restore",
    methods=["POST"],
)
@login_required
def restore_my_workspace_folder(identifier):
    """Restore one empty user-owned folder without restoring contents."""

    user_id = _get_current_user_id()
    clean_identifier = _normalize_identifier(identifier)

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    if not clean_identifier:
        return jsonify({
            "ok": False,
            "error": "Missing folder identifier",
            "contract": WORKSPACE_FOLDER_CONTRACT,
        }), 400

    db_session = SessionLocal()

    try:
        access_context = _workspace_folder_access_context(
            db_session,
            user_id,
        )
        folder = _resolve_folder_record(
            db_session,
            user_id,
            clean_identifier,
            active_only=False,
            require_owner=True,
            access_context=access_context,
        )

        if not folder:
            return jsonify({
                "ok": False,
                "error": "Folder not found",
                "contract": WORKSPACE_FOLDER_CONTRACT,
            }), 404

        if _workspace_folder_status(folder) != WORKSPACE_FOLDER_TRASH_STATUS:
            return jsonify({
                "ok": False,
                "error": "Folder is not in Trash",
                "contract": WORKSPACE_FOLDER_CONTRACT,
            }), 409

        empty_error = _workspace_folder_empty_error_payload(
            db_session,
            folder,
        )

        if empty_error:
            return jsonify(empty_error), 409

        parent_folder_id = _normalize_identifier(
            getattr(folder, "parent_folder_id", "")
        )

        if parent_folder_id:
            parent_folder = _resolve_folder_record(
                db_session,
                user_id,
                parent_folder_id,
                active_only=True,
                require_owner=True,
                access_context=access_context,
            )

            if not parent_folder:
                return jsonify({
                    "ok": False,
                    "error": "Restore the parent folder before restoring this folder.",
                    "contract": WORKSPACE_FOLDER_CONTRACT,
                }), 409

        conflict = _find_active_workspace_folder_conflict(
            db_session,
            user_id,
            _workspace_folder_scope(folder),
            _workspace_folder_parent_key(
                getattr(folder, "parent_folder_key", "")
            ),
            _normalize_folder_lookup_name(
                getattr(folder, "name", "")
            ),
        )

        if conflict:
            return jsonify({
                "ok": False,
                "error": "An active folder with that name already exists in the destination.",
                "contract": WORKSPACE_FOLDER_CONTRACT,
            }), 409

        now = _current_utc_datetime()
        folder.status = WORKSPACE_FOLDER_ACTIVE_STATUS
        folder.is_discoverable = True
        folder.deleted_at = None
        folder.updated_at = now
        folder.updated_by_user_id = user_id
        db_session.commit()
        db_session.refresh(folder)
        restored_payload = _workspace_folder_mutation_payload(
            folder,
            user_id,
            access_context,
        )

        logger.info(
            "[uploads.folder_restore] user_id=%s folder_id=%s",
            user_id,
            clean_identifier,
        )

        return jsonify({
            "ok": True,
            "contract": WORKSPACE_FOLDER_CONTRACT,
            "folder_non_recursive": True,
            "restored": restored_payload,
            "folder": restored_payload,
        }), 200
    except IntegrityError:
        db_session.rollback()
        return jsonify({
            "ok": False,
            "error": "An active folder with that name already exists in the destination.",
            "contract": WORKSPACE_FOLDER_CONTRACT,
        }), 409
    except Exception as exc:
        db_session.rollback()
        logger.error(
            "[uploads.folder_restore_failed] user_id=%s folder_id=%s error=%s",
            user_id,
            clean_identifier,
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "Failed to restore folder",
            "contract": WORKSPACE_FOLDER_CONTRACT,
        }), 500
    finally:
        db_session.close()


@user_uploads_bp.route(
    "/me/folders/trash/<identifier>",
    methods=["DELETE"],
)
@login_required
def permanently_delete_my_workspace_folder(identifier):
    """Permanently delete one empty user-owned folder already in Trash."""

    user_id = _get_current_user_id()
    clean_identifier = _normalize_identifier(identifier)

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    if not clean_identifier:
        return jsonify({
            "ok": False,
            "error": "Missing folder identifier",
            "contract": WORKSPACE_FOLDER_CONTRACT,
        }), 400

    db_session = SessionLocal()

    try:
        access_context = _workspace_folder_access_context(
            db_session,
            user_id,
        )
        folder = _resolve_folder_record(
            db_session,
            user_id,
            clean_identifier,
            active_only=False,
            require_owner=True,
            access_context=access_context,
        )

        if not folder:
            return jsonify({
                "ok": False,
                "error": "Folder not found",
                "contract": WORKSPACE_FOLDER_CONTRACT,
            }), 404

        if _workspace_folder_status(folder) != WORKSPACE_FOLDER_TRASH_STATUS:
            return jsonify({
                "ok": False,
                "error": "Move the folder to Trash before permanent deletion.",
                "contract": WORKSPACE_FOLDER_CONTRACT,
            }), 409

        empty_error = _workspace_folder_empty_error_payload(
            db_session,
            folder,
        )

        if empty_error:
            return jsonify(empty_error), 409

        deleted_payload = {
            "folder_id": _normalize_identifier(folder.folder_id),
            "workspace_item_id": _normalize_identifier(folder.folder_id),
            "original_name": _normalize_folder_name(folder.name),
            "display_name": _normalize_folder_name(folder.name),
            "object_type": "folder",
        }
        db_session.delete(folder)
        db_session.commit()

        logger.info(
            "[uploads.folder_permanent_delete] user_id=%s folder_id=%s",
            user_id,
            clean_identifier,
        )

        return jsonify({
            "ok": True,
            "contract": WORKSPACE_FOLDER_CONTRACT,
            "folder_non_recursive": True,
            "permanently_deleted": deleted_payload,
            "deleted": deleted_payload,
        }), 200
    except Exception as exc:
        db_session.rollback()
        logger.error(
            "[uploads.folder_permanent_delete_failed] user_id=%s folder_id=%s error=%s",
            user_id,
            clean_identifier,
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "Failed to permanently delete folder",
            "contract": WORKSPACE_FOLDER_CONTRACT,
        }), 500
    finally:
        db_session.close()


@user_uploads_bp.route(
    "/me/intelligence-events",
    methods=["GET"],
)
@login_required
def retired_my_intelligence_events():
    """Terminate legacy browser completion streams without reconnecting."""

    return "", 204


@user_uploads_bp.route(
    "/me",
    methods=["GET"],
)
@login_required
def list_my_uploads():
    """Return active files authorized for the current user."""

    return _uploads_response_payload(
        trash_only=False
    )


@user_uploads_bp.route(
    "/me/shared",
    methods=["GET"],
)
@login_required
def list_my_shared_uploads():
    """Return the current user's authorized Shared with me projection."""

    return _uploads_response_payload(
        trash_only=False,
        collection_scope=WORKSPACE_FOLDER_COLLECTION_SHARED,
    )


@user_uploads_bp.route(
    "/me/recent",
    methods=["GET"],
)
@login_required
def list_my_recent_uploads():
    """Return active files ordered by the current user's Recent activity."""

    return _recent_uploads_response_payload()


@user_uploads_bp.route(
    "/me/trash",
    methods=["GET"],
)
@login_required
def list_my_trashed_uploads():
    """Return recoverably trashed files owned by the current user."""

    return _uploads_response_payload(
        trash_only=True
    )


@user_uploads_bp.route(
    "/me/move",
    methods=["POST"],
)
@login_required
def move_my_uploads():
    """Move owned active files into one owned My Files folder atomically."""

    user_id = _get_current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    payload = _request_payload()
    raw_document_ids = payload.get("document_ids")

    if isinstance(raw_document_ids, str):
        raw_document_ids = [
            value
            for value in raw_document_ids.split(",")
            if _normalize_identifier(value)
        ]

    if not isinstance(raw_document_ids, (list, tuple)):
        raw_document_ids = [
            payload.get("document_id")
            or payload.get("file_id")
            or payload.get("identifier")
        ]

    document_ids = []
    seen = set()

    for value in raw_document_ids:
        clean_identifier = _normalize_identifier(value)
        if not clean_identifier or clean_identifier in seen:
            continue
        seen.add(clean_identifier)
        document_ids.append(clean_identifier)

    if not document_ids:
        return jsonify({
            "ok": False,
            "error": "Select at least one file to move.",
        }), 400

    if len(document_ids) > WORKSPACE_FILE_MOVE_MAX_ITEMS:
        return jsonify({
            "ok": False,
            "error": (
                f"Move up to {WORKSPACE_FILE_MOVE_MAX_ITEMS} files "
                "at one time."
            ),
        }), 400

    destination_folder_id = _normalize_identifier(
        payload.get("destination_folder_id")
        or payload.get("folder_id")
        or payload.get("parent_folder_id")
    )

    db_session = SessionLocal()

    try:
        destination_folder = None

        if destination_folder_id:
            destination_folder = _resolve_folder_record(
                db_session,
                user_id,
                destination_folder_id,
                active_only=True,
                require_owner=True,
            )

            if not destination_folder:
                return jsonify({
                    "ok": False,
                    "error": (
                        "The destination folder is not an active "
                        "My Files folder owned by this account."
                    ),
                }), 404

            destination_folder_id = _normalize_identifier(
                getattr(destination_folder, "folder_id", "")
            )

        records = []

        for identifier in document_ids:
            record = _resolve_owned_file_record(
                db_session,
                user_id,
                identifier,
            )

            if not record:
                db_session.rollback()
                return jsonify({
                    "ok": False,
                    "error": (
                        "One or more selected files are unavailable "
                        "or are not owned by this account."
                    ),
                }), 404

            if _is_trashed_meta(record.meta):
                db_session.rollback()
                return jsonify({
                    "ok": False,
                    "error": (
                        "Restore files from Trash before moving them."
                    ),
                }), 409

            records.append(record)

        now = _current_utc_datetime()
        destination_value = destination_folder_id or None
        moved = []

        for record in records:
            record.workspace_folder_id = destination_value
            record.updated_at = now
            moved.append({
                "document_id": _normalize_identifier(record.random_name),
                "file_id": str(record.id),
                "original_name": record.original_name or record.random_name,
                "workspace_folder_id": destination_folder_id,
            })

        db_session.commit()

        logger.info(
            (
                "[uploads.move_files] user_id=%s count=%s "
                "destination_folder_id=%s"
            ),
            user_id,
            len(moved),
            destination_folder_id or "root",
        )

        return jsonify({
            "ok": True,
            "contract": WORKSPACE_FILE_MOVE_CONTRACT,
            "moved_count": len(moved),
            "destination_folder_id": destination_folder_id,
            "moved": moved,
        }), 200
    except Exception as exc:
        db_session.rollback()
        logger.error(
            (
                "[uploads.move_files_failed] user_id=%s count=%s "
                "destination_folder_id=%s error=%s"
            ),
            user_id,
            len(document_ids),
            destination_folder_id or "root",
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "The selected files could not be moved.",
        }), 500
    finally:
        db_session.close()


@user_uploads_bp.route(
    "/me/<identifier>",
    methods=["DELETE"],
)
@login_required
def delete_my_upload(identifier):
    """Move one user-owned upload into recoverable Trash state."""

    user_id = _get_current_user_id()
    clean_identifier = _normalize_identifier(
        identifier
    )

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    if not clean_identifier:
        return jsonify({
            "ok": False,
            "error": "Missing file identifier",
        }), 400

    display_identifier_error = (
        _display_identifier_error_payload(
            clean_identifier
        )
    )

    if display_identifier_error:
        logger.warning(
            (
                "[uploads.move_to_trash_rejected_display_identifier] "
                "user_id=%s identifier=%s"
            ),
            user_id,
            clean_identifier,
        )
        return jsonify(
            display_identifier_error
        ), 400

    db_session = SessionLocal()

    try:
        record = _resolve_owned_file_record(
            db_session,
            user_id,
            clean_identifier,
        )

        if not record:
            return jsonify({
                "ok": False,
                "error": "File not found",
            }), 404

        random_name = _normalize_identifier(
            record.random_name
        )
        original_name = (
            record.original_name
            or random_name
        )
        storage_path = str(
            record.path or ""
        ).strip()
        file_id = str(record.id)

        if (
            storage_path
            and not _is_inside_uploads_root(
                storage_path
            )
        ):
            return jsonify({
                "ok": False,
                "error": "Unsafe file path",
            }), 400

        _remove_active_id(random_name)

        trashed_meta = _trash_status_payload(
            user_id
        )
        current_meta = _safe_meta_payload(
            record.meta
        )
        current_meta.update(trashed_meta)
        record.meta = current_meta
        record.updated_at = _current_utc_datetime()
        db_session.commit()

        logger.info(
            (
                "[uploads.move_to_trash] "
                "user_id=%s document_id=%s file_id=%s"
            ),
            user_id,
            random_name,
            file_id,
        )

        deleted_payload = {
            "document_id": random_name,
            "file_id": file_id,
            "original_name": original_name,
            "storage_deleted": False,
            "storage_status": "retained_for_trash",
            "trashed_at": trashed_meta["trashed_at"],
        }

        return jsonify({
            "ok": True,
            "moved_to_trash": deleted_payload,
            "deleted": deleted_payload,
        }), 200
    except Exception as exc:
        db_session.rollback()
        logger.error(
            (
                "[uploads.move_to_trash_failed] "
                "user_id=%s identifier=%s error=%s"
            ),
            user_id,
            clean_identifier,
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "Failed to move file to Trash",
        }), 500
    finally:
        db_session.close()


@user_uploads_bp.route(
    "/me/trash/<identifier>/restore",
    methods=["POST"],
)
@login_required
def restore_my_upload(identifier):
    """Restore one trashed upload to the active Documents library."""

    user_id = _get_current_user_id()
    clean_identifier = _normalize_identifier(
        identifier
    )

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    if not clean_identifier:
        return jsonify({
            "ok": False,
            "error": "Missing file identifier",
        }), 400

    display_identifier_error = (
        _display_identifier_error_payload(
            clean_identifier
        )
    )

    if display_identifier_error:
        logger.warning(
            (
                "[uploads.restore_from_trash_rejected_display_identifier] "
                "user_id=%s identifier=%s"
            ),
            user_id,
            clean_identifier,
        )
        return jsonify(
            display_identifier_error
        ), 400

    db_session = SessionLocal()

    try:
        record = _resolve_owned_file_record(
            db_session,
            user_id,
            clean_identifier,
        )

        if not record:
            return jsonify({
                "ok": False,
                "error": "File not found",
            }), 404

        random_name = _normalize_identifier(
            record.random_name
        )
        original_name = (
            record.original_name
            or random_name
        )
        storage_path = str(
            record.path or ""
        ).strip()
        file_id = str(record.id)

        if (
            storage_path
            and not _is_inside_uploads_root(
                storage_path
            )
        ):
            return jsonify({
                "ok": False,
                "error": "Unsafe file path",
            }), 400

        if not _is_trashed_meta(record.meta):
            return jsonify({
                "ok": False,
                "error": "File is not in Trash",
            }), 409

        record.meta = _restore_status_payload(
            record.meta
        )
        record.updated_at = _current_utc_datetime()
        db_session.commit()

        logger.info(
            (
                "[uploads.restore_from_trash] "
                "user_id=%s document_id=%s file_id=%s"
            ),
            user_id,
            random_name,
            file_id,
        )

        return jsonify({
            "ok": True,
            "restored": {
                "document_id": random_name,
                "file_id": file_id,
                "original_name": original_name,
                "document_status": "active",
            },
        }), 200
    except Exception as exc:
        db_session.rollback()
        logger.error(
            (
                "[uploads.restore_from_trash_failed] "
                "user_id=%s identifier=%s error=%s"
            ),
            user_id,
            clean_identifier,
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "Failed to restore file",
        }), 500
    finally:
        db_session.close()


@user_uploads_bp.route(
    "/me/trash/<identifier>",
    methods=["DELETE"],
)
@login_required
def permanently_delete_my_upload(identifier):
    """Permanently delete one upload already in recoverable Trash."""

    user_id = _get_current_user_id()
    clean_identifier = _normalize_identifier(
        identifier
    )

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Not logged in",
        }), 401

    if not clean_identifier:
        return jsonify({
            "ok": False,
            "error": "Missing file identifier",
        }), 400

    display_identifier_error = (
        _display_identifier_error_payload(
            clean_identifier
        )
    )

    if display_identifier_error:
        logger.warning(
            (
                "[uploads.permanent_delete_rejected_display_identifier] "
                "user_id=%s identifier=%s"
            ),
            user_id,
            clean_identifier,
        )
        return jsonify(
            display_identifier_error
        ), 400

    db_session = SessionLocal()

    try:
        record = _resolve_owned_file_record(
            db_session,
            user_id,
            clean_identifier,
        )

        if not record:
            return jsonify({
                "ok": False,
                "error": "File not found",
            }), 404

        random_name = _normalize_identifier(
            record.random_name
        )
        original_name = (
            record.original_name
            or random_name
        )
        storage_path = str(
            record.path or ""
        ).strip()
        file_id = str(record.id)

        if not _is_trashed_meta(record.meta):
            return jsonify({
                "ok": False,
                "error": (
                    "Move the file to Trash before "
                    "permanent deletion"
                ),
            }), 409

        storage_deleted, storage_status = (
            _safe_delete_storage_file(
                storage_path
            )
        )

        if not _storage_delete_allows_metadata_removal(
            storage_deleted,
            storage_status,
        ):
            return jsonify({
                "ok": False,
                "error": (
                    "Storage file could not be safely deleted"
                ),
                "storage_status": storage_status,
            }), (
                400
                if storage_status
                in {"unsafe_path", "not_a_file"}
                else 500
            )

        _remove_active_id(random_name)
        db_session.delete(record)
        db_session.commit()

        logger.info(
            (
                "[uploads.permanent_delete] "
                "user_id=%s document_id=%s "
                "file_id=%s storage_status=%s"
            ),
            user_id,
            random_name,
            file_id,
            storage_status,
        )

        deleted_payload = {
            "document_id": random_name,
            "file_id": file_id,
            "original_name": original_name,
            "storage_deleted": storage_deleted,
            "storage_status": storage_status,
        }

        return jsonify({
            "ok": True,
            "permanently_deleted": deleted_payload,
            "deleted": deleted_payload,
        }), 200
    except Exception as exc:
        db_session.rollback()
        logger.error(
            (
                "[uploads.permanent_delete_failed] "
                "user_id=%s identifier=%s error=%s"
            ),
            user_id,
            clean_identifier,
            exc,
        )
        return jsonify({
            "ok": False,
            "error": "Failed to permanently delete file",
        }), 500
    finally:
        db_session.close()


__all__ = [
    "user_uploads_bp",
]
# -------------------------------------------------------------------
# FILE: app.py
# DIRECTORY: webui/
# -------------------------------------------------------------------
# Flask web interface for Solomon
# File workspace, dedicated SolomonAI conversation blueprint, explicit
# workflow entrypoints, and shell bootstrap.
# -------------------------------------------------------------------

import logging
import os
import sys
from datetime import datetime, timedelta
from io import BytesIO
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlencode, urlsplit

from flask import (
    Flask,
    g,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_file,
    session,
)
from flask_session import Session
from sqlalchemy import or_
from werkzeug.middleware.proxy_fix import ProxyFix
from werkzeug.serving import (
    WSGIRequestHandler,
)


class _WerkzeugAccessLogFilter(logging.Filter):
    """Suppress noisy Flask dev-server HTTP access lines by default."""

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not _looks_like_werkzeug_access_log(message)


def _startup_truthy_setting(value) -> bool:
    if isinstance(value, str):
        return value.strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

    return bool(value)


def _looks_like_werkzeug_access_log(message: str) -> bool:
    clean_message = str(message or "").strip()

    if " - - [" not in clean_message:
        return False

    return any(
        marker in clean_message
        for marker in (
            '"GET ',
            '"POST ',
            '"PUT ',
            '"PATCH ',
            '"DELETE ',
            '"OPTIONS ',
            '"HEAD ',
        )
    )


def _suppress_werkzeug_request_log(
    self,
    code="-",
    size="-",
) -> None:
    """Disable Werkzeug access logging without touching Solomon logs."""

    return None


def _silence_werkzeug_request_logs() -> None:
    """Patch the development server request logger at the source."""

    if not hasattr(
        WSGIRequestHandler,
        "_solomon_original_log_request",
    ):
        WSGIRequestHandler._solomon_original_log_request = (
            WSGIRequestHandler.log_request
        )

    WSGIRequestHandler.log_request = (
        _suppress_werkzeug_request_log
    )


def _restore_werkzeug_request_logs() -> None:
    """Restore Werkzeug request logging when explicitly enabled."""

    original_log_request = getattr(
        WSGIRequestHandler,
        "_solomon_original_log_request",
        None,
    )

    if not original_log_request:
        return

    WSGIRequestHandler.log_request = original_log_request

    try:
        delattr(
            WSGIRequestHandler,
            "_solomon_original_log_request",
        )
    except AttributeError:
        pass


def _remove_filter_type(
    target,
    filter_type,
) -> None:
    for existing_filter in list(
        getattr(target, "filters", [])
    ):
        if isinstance(
            existing_filter,
            filter_type,
        ):
            target.removeFilter(
                existing_filter
            )


def _configure_werkzeug_logging(
    verbose_enabled: bool,
) -> None:
    werkzeug_logger = logging.getLogger(
        "werkzeug"
    )
    show_http_access_logs = bool(
        settings.HTTP_ACCESS_LOGS_ENABLED
    )

    werkzeug_logger.setLevel(
        logging.INFO
        if verbose_enabled
        else logging.WARNING
    )

    _remove_filter_type(
        werkzeug_logger,
        _WerkzeugAccessLogFilter,
    )

    for handler in list(
        werkzeug_logger.handlers
    ):
        _remove_filter_type(
            handler,
            _WerkzeugAccessLogFilter,
        )

    if show_http_access_logs:
        _restore_werkzeug_request_logs()
        return

    werkzeug_logger.addFilter(
        _WerkzeugAccessLogFilter()
    )

    for handler in list(
        werkzeug_logger.handlers
    ):
        handler.addFilter(
            _WerkzeugAccessLogFilter()
        )

    _silence_werkzeug_request_logs()


def _configure_startup_logging() -> None:
    verbose_enabled = (
        str(
            settings.CONSOLE_LOG_LEVEL
        ).strip().upper()
        == "DEBUG"
    )

    solomon_level = (
        logging.DEBUG
        if verbose_enabled
        else logging.INFO
    )

    _configure_werkzeug_logging(
        verbose_enabled
    )
    logging.getLogger(
        "Solomon"
    ).setLevel(
        solomon_level
    )


BASE_DIR = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        "..",
    )
)

if BASE_DIR not in sys.path:
    sys.path.insert(
        0,
        BASE_DIR,
    )

from command_console_registry import (
    get_command_department,
)
from config import (
    init_flask_config,
    settings,
)
from solomon_core.auth import (
    auth_bp,
    resolve_account_context_for_user,
)
from solomon_core.auth_utils import (
    login_required,
)
from solomon_core.db import (
    SessionLocal,
    init_db,
    register_database_teardown,
)
from solomon_core.logger import get_logger
from solomon_core.llm.llm_executor import (
    warm_direct_model_worker,
    warm_direct_runtime_profile_worker,
)
from solomon_core.memory_store import (
    get_recent_tasks,
)
from solomon_core.models import (
    FileAccessGrant,
    FileGroupAccessGrant,
    FileRegistry,
    OrganizationGroupMembership,
    OrganizationMembership,
    WorkspaceIntelligenceObject,
)
from solomon_core.routes import (
    register_all_blueprints,
)
from solomon_core.routes.document_operations_bp import (
    solomon_conversations_bp,
)
from solomon_core.routes.task_api import (
    task_api,
)
from solomon_core.workspace_reader.workspace_reader_file_access import (
    DISCOVER_ACTION,
    FILE_SURFACE_SEARCH,
    QUERY_ACTION,
    READ_ACTION,
    build_file_capabilities,
    build_file_surface_actions,
    is_file_record_trashed,
    resolve_authorized_file_registry_entry,
    resolve_file_access_decision,
)
from solomon_workspace.actions.open_document import (
    open_workspace_document,
)
from solomon_workspace.context.workspace_context_packet import (
    build_workspace_context_packet,
)
from solomon_workspace.documents.document_session import (
    WorkspaceDocumentSession,
    build_workspace_document_session_from_dict,
)
from solomon_workspace.panels.panel_state import (
    WorkspacePanelState,
    build_workspace_panel_state_from_dict,
)

_configure_startup_logging()

logger = get_logger(
    "Solomon.app"
)

_DOCINTEL_SUMMARY_WARMUP_CALL_SITE = (
    "docintel_summary_narration"
)
_DOCINTEL_SUMMARY_WARMUP_RUNTIME_PROFILE = (
    "static_cache"
)
_DOCINTEL_SUMMARY_WARMUP_MAX_NEW_TOKENS = 480
_DOCINTEL_SUMMARY_WARMUP_TARGET_INPUT_TOKENS = 2336
_DOCINTEL_SUMMARY_WARMUP_SOURCE_CHARS = 8515
_DOCINTEL_SUMMARY_WARMUP_SOURCE_SEED = (
    "Proposal scope includes roofing, wall panels, wood blocking, nailers, "
    "pricing, alternates, exclusions, insurance, schedule dates, escalation "
    "terms, unit costs, addenda, qualifications, and trade coordination. "
)

app = Flask(
    __name__,
    template_folder="templates",
    static_folder="static",
)

init_flask_config(app)

if settings.PROXY_FIX_ENABLED:
    app.wsgi_app = ProxyFix(
        app.wsgi_app,
        x_for=settings.PROXY_FIX_X_FOR,
        x_proto=settings.PROXY_FIX_X_PROTO,
        x_host=settings.PROXY_FIX_X_HOST,
        x_port=settings.PROXY_FIX_X_PORT,
        x_prefix=settings.PROXY_FIX_X_PREFIX,
    )

Session(app)
init_db()
register_database_teardown(app)


# ============================================================
# COMMAND CENTER REGISTRY
# ============================================================
COMMAND_MODULES = {
    "documents": {
        "label": "Workspace",
        "nav_label": "Workspace",
        "path": "/",
        "status": "active",
        "description": (
            "Default workspace entry for files, records, "
            "reports, and document inspection."
        ),
    },
    "search": {
        "label": "Search",
        "nav_label": "Search",
        "path": "/search",
        "status": "active",
        "description": (
            "Workspace-wide discovery for files, conversations, "
            "people, and groups."
        ),
    },
    "preconstruction": {
        "label": "Preconstruction",
        "nav_label": "Precon",
        "path": "/preconstruction",
        "status": "active",
        "description": (
            "Pre-award review, bid leveling, scope risk, "
            "clarifications, and handoff preparation."
        ),
    },
    "preconstruction_review": {
        "label": "Bid & Scope Review",
        "nav_label": "Precon",
        "path": (
            "/preconstruction/bid-scope-review"
        ),
        "status": "active",
        "description": (
            "Review bid, proposal, scope, and commercial "
            "documents through the governed Preconstruction "
            "workflow."
        ),
    },
    "management": {
        "label": "Operations",
        "nav_label": "Ops",
        "path": "/management",
        "status": "building",
        "description": (
            "Project controls, open issues, risk exposure, "
            "decisions, handoffs, and operating visibility."
        ),
    },
    "field": {
        "label": "Field Operations",
        "nav_label": "Field",
        "path": "/field",
        "status": "building",
        "description": (
            "Site activity, daily reports, work orders, "
            "manpower, photos, and field records."
        ),
    },
    "quality": {
        "label": "Quality",
        "nav_label": "Quality",
        "path": "/quality",
        "status": "building",
        "description": (
            "Inspections, audits, punch items, corrective "
            "actions, and closeout readiness."
        ),
    },
    "safety": {
        "label": "Safety",
        "nav_label": "Safety",
        "path": "/safety",
        "status": "building",
        "description": (
            "Safety observations, incident records, job "
            "hazard notes, compliance items, and corrective "
            "actions."
        ),
    },
    "communication": {
        "label": "Coordination",
        "nav_label": "Coord",
        "path": "/comms",
        "status": "building",
        "description": (
            "Meetings, action items, stakeholder updates, "
            "subcontractor coordination, and decision logs."
        ),
    },
    "finance": {
        "label": "Finance",
        "nav_label": "Finance",
        "path": "/finance",
        "status": "building",
        "description": (
            "Billing, cost exposure, budget review, pay "
            "applications, change exposure, and financial "
            "summaries."
        ),
    },
    "people": {
        "label": "People",
        "nav_label": "People",
        "path": "/people",
        "status": "building",
        "description": (
            "Onboarding, employee records, roles, team "
            "status, training records, and certifications."
        ),
    },
}


# ============================================================
# EXPLICIT WORKFLOW REGISTRY
# ============================================================
SUPPORTED_WORKFLOWS = {
    "pre_award_risk_review": {
        "label": "Bid & Scope Review",
        "input_modes": [
            "upload",
            "paste_text",
        ],
        "description": (
            "Creates a focused review from bid, proposal, "
            "scope, and commercial documents."
        ),
    }
}


# ============================================================
# WORKSPACE SHELL RENDERING
# ============================================================
WORKSPACE_RENDER_TEMPLATE = (
    "components/workspace_content.html"
)
WORKSPACE_RENDER_MODE_HEADER = (
    "X-Solomon-Render-Mode"
)
WORKSPACE_RENDER_MODE_WORKSPACE = (
    "workspace"
)
LEGACY_INTERNAL_QUERY_PARAMETERS = frozenset({
    "partial",
})
DOCUMENT_WORKSPACE_SECTIONS = {
    "files",
    "reports",
    "recent",
    "shared",
    "trash",
}
WORKSPACE_SEARCH_CONTRACT = (
    "nations_global_search_v1"
)
WORKSPACE_DOCUMENT_METADATA_CONTRACT = (
    "workspace_document_metadata_v1"
)
WORKSPACE_SEARCH_PERMISSION_MODE = (
    "authorized_only"
)
WORKSPACE_SEARCH_ALLOWED_TYPES = {
    "all",
    "files",
    "conversations",
    "people",
    "groups",
}
WORKSPACE_SEARCH_ALLOWED_CONTEXTS = {
    "global",
    "home",
    "solomon_ai",
    "people",
    "recent",
    "shared",
    "trash",
}
WORKSPACE_SEARCH_OBJECT_TYPES = {
    "all": (
        "file",
        "conversation",
        "person",
        "group",
    ),
    "files": (
        "file",
    ),
    "conversations": (
        "conversation",
    ),
    "people": (
        "person",
    ),
    "groups": (
        "group",
    ),
}
WORKSPACE_SEARCH_OBJECT_LABELS = {
    "file": "File",
    "conversation": "Conversation",
    "person": "Person",
    "group": "Group",
}
WORKSPACE_SEARCH_DEFAULT_ICONS = {
    "file": "description",
    "conversation": "forum",
    "person": "person",
    "group": "groups",
}
WORKSPACE_SEARCH_MODULE_BY_OBJECT_TYPE = {
    "file": "documents",
    "conversation": "solomon_ai",
    "person": "people",
    "group": "people",
}
WORKSPACE_SEARCH_ACTIONS_BY_OBJECT_TYPE = {
    "file": (
        "open",
        "ask_about_this",
        "add_to_conversation",
    ),
    "conversation": (
        "open",
        "continue_conversation",
    ),
    "person": (
        "open",
    ),
    "group": (
        "open",
    ),
}
WORKSPACE_FILE_THUMBNAIL_EXTENSIONS = {
    "pdf",
    "png",
    "jpg",
    "jpeg",
    "webp",
    "gif",
    "bmp",
    "tif",
    "tiff",
}
WORKSPACE_FILE_IMAGE_THUMBNAIL_EXTENSIONS = (
    WORKSPACE_FILE_THUMBNAIL_EXTENSIONS - {
        "pdf",
    }
)

WORKSPACE_SEARCH_CAPABILITY_ACTION_TERMS = {
    "add",
    "approve",
    "assign",
    "build",
    "connect",
    "create",
    "delete",
    "export",
    "generate",
    "import",
    "invite",
    "make",
    "remove",
    "schedule",
    "send",
    "share",
    "sync",
    "update",
}
WORKSPACE_SEARCH_MAX_QUERY_CHARS = 140
WORKSPACE_SEARCH_MAX_RESULTS = 48
WORKSPACE_SEARCH_MAX_API_RESULTS = 8
WORKSPACE_SEARCH_ALLOWED_SORT_KEYS = {
    "relevance",
    "name",
    "modified",
    "type",
    "size",
}
WORKSPACE_SEARCH_DEFAULT_SORT_DIRECTIONS = {
    "relevance": "desc",
    "name": "asc",
    "modified": "desc",
    "type": "asc",
    "size": "desc",
}
WORKSPACE_SEARCH_ALLOWED_DIRECTIONS = {
    "asc",
    "desc",
}
WORKSPACE_SEARCH_ALLOWED_FOLDER_PLACEMENTS = {
    "top",
    "mixed",
}
WORKSPACE_SEARCH_ALLOWED_LAYOUTS = {
    "list",
    "grid",
}
WORKSPACE_SEARCH_MODIFIED_FILTERS = (
    ("today", "Today"),
    ("last_7_days", "Last 7 days"),
    ("last_30_days", "Last 30 days"),
    ("this_year", "This year"),
)
DEFAULT_COMMAND_MODULE = "documents"
DEFAULT_DOCUMENT_WORKSPACE_SECTION = "files"
GROUP_SETUP_PATH = "/people/groups/setup"
GROUP_SETUP_EXEMPT_PATHS = frozenset({
    "/auth/logout",
    "/auth/session-check",
    "/auth/me",
    "/auth/change-password",
})
GROUP_SETUP_EXEMPT_PREFIXES = (
    "/static/",
    f"{GROUP_SETUP_PATH}/",
)


def is_workspace_render_request() -> bool:
    render_mode = str(
        request.headers.get(
            WORKSPACE_RENDER_MODE_HEADER,
            "",
        )
    ).strip().lower()

    return (
        render_mode
        == WORKSPACE_RENDER_MODE_WORKSPACE
    )


@app.before_request
def remove_legacy_internal_query_parameters():
    if request.method not in {
        "GET",
        "HEAD",
    }:
        return None

    has_legacy_parameter = any(
        str(
            key or ""
        ).strip().lower()
        in LEGACY_INTERNAL_QUERY_PARAMETERS
        for key in request.args.keys()
    )

    if not has_legacy_parameter:
        return None

    public_query_items = [
        (
            key,
            value,
        )
        for key, value
        in request.args.items(
            multi=True
        )
        if str(
            key or ""
        ).strip().lower()
        not in LEGACY_INTERNAL_QUERY_PARAMETERS
    ]

    public_query = urlencode(
        public_query_items
    )
    public_url = request.path

    if public_query:
        public_url = (
            f"{public_url}?{public_query}"
        )

    return redirect(
        public_url,
        code=302,
    )


def normalize_document_workspace_section(
    section: Optional[str],
) -> str:
    clean_section = str(
        section or "files"
    ).strip().lower()

    if clean_section in DOCUMENT_WORKSPACE_SECTIONS:
        return clean_section

    return DEFAULT_DOCUMENT_WORKSPACE_SECTION


def normalize_workspace_search_query(
    value: Optional[str],
) -> str:
    """Return a compact search query for workspace discovery."""

    clean_query = " ".join(
        str(value or "")
        .replace("\x00", " ")
        .replace("\r", " ")
        .replace("\n", " ")
        .replace("\t", " ")
        .split()
    ).strip()

    return clean_query[:WORKSPACE_SEARCH_MAX_QUERY_CHARS]


def normalize_workspace_search_type(
    value: Optional[str],
) -> str:
    """Return a supported workspace search filter."""

    clean_type = str(
        value or "all"
    ).strip().lower()

    if clean_type in WORKSPACE_SEARCH_ALLOWED_TYPES:
        return clean_type

    return "all"


def normalize_workspace_search_context(
    value: Optional[str],
) -> str:
    """Return a supported frontend search context label."""

    clean_context = str(
        value or "global"
    ).strip().lower()

    if clean_context in WORKSPACE_SEARCH_ALLOWED_CONTEXTS:
        return clean_context

    return "global"


def normalize_workspace_search_limit(
    value: Optional[str],
    *,
    default_limit: int,
) -> int:
    """Return a safe bounded search result limit."""

    try:
        parsed_limit = int(
            value or default_limit
        )
    except (
        TypeError,
        ValueError,
    ):
        parsed_limit = default_limit

    return max(
        1,
        min(
            parsed_limit,
            WORKSPACE_SEARCH_MAX_RESULTS,
        ),
    )


def normalize_workspace_search_filter_value(
    value: Optional[str],
) -> str:
    """Return a compact public filter token."""

    clean_value = str(
        value or ""
    ).strip().lower()
    normalized_characters = []
    previous_separator = False

    for character in clean_value:
        if character.isalnum():
            normalized_characters.append(
                character
            )
            previous_separator = False
            continue

        if character in {
            "-",
            "_",
            " ",
        } and not previous_separator:
            normalized_characters.append(
                "_"
            )
            previous_separator = True

    return "".join(
        normalized_characters
    ).strip("_")[:80]


def normalize_workspace_search_modified_filter(
    value: Optional[str],
) -> str:
    """Return a supported modified-date filter token."""

    clean_value = normalize_workspace_search_filter_value(
        value
    )
    allowed_values = {
        option_value
        for option_value, _
        in WORKSPACE_SEARCH_MODIFIED_FILTERS
    }

    if clean_value in allowed_values:
        return clean_value

    return ""


def normalize_workspace_search_sort_key(
    value: Optional[str],
) -> str:
    """Return a supported server-owned Search sort key."""

    clean_value = normalize_workspace_search_filter_value(
        value
    )
    aliases = {
        "date": "modified",
        "date_modified": "modified",
        "uploaded": "modified",
        "upload_time": "modified",
        "file_type": "type",
        "file_size": "size",
    }
    clean_value = aliases.get(
        clean_value,
        clean_value,
    )

    if clean_value in WORKSPACE_SEARCH_ALLOWED_SORT_KEYS:
        return clean_value

    return "relevance"


def normalize_workspace_search_direction(
    value: Optional[str],
    *,
    sort_key: str,
) -> str:
    """Return a supported direction for the selected sort key."""

    clean_value = normalize_workspace_search_filter_value(
        value
    )

    if clean_value in WORKSPACE_SEARCH_ALLOWED_DIRECTIONS:
        return clean_value

    return WORKSPACE_SEARCH_DEFAULT_SORT_DIRECTIONS.get(
        sort_key,
        "desc",
    )


def normalize_workspace_search_folder_placement(
    value: Optional[str],
) -> str:
    """Return the canonical folder placement projection."""

    clean_value = normalize_workspace_search_filter_value(
        value
    )

    if clean_value in WORKSPACE_SEARCH_ALLOWED_FOLDER_PLACEMENTS:
        return clean_value

    return "top"


def normalize_workspace_search_layout(
    value: Optional[str],
) -> str:
    """Return the canonical Search results layout."""

    clean_value = normalize_workspace_search_filter_value(
        value
    )

    if clean_value in WORKSPACE_SEARCH_ALLOWED_LAYOUTS:
        return clean_value

    return "list"


def build_workspace_search_like_pattern(
    query: str,
) -> str:
    """Return an escaped SQL LIKE pattern for user search text."""

    escaped_characters = []

    for character in str(
        query or ""
    ):
        if character in {
            "%",
            "_",
            "\\",
        }:
            escaped_characters.append(
                f"\\{character}"
            )
        else:
            escaped_characters.append(
                character
            )

    return (
        "%"
        + "".join(
            escaped_characters
        )
        + "%"
    )


def build_workspace_search_snippet(
    intelligence_object: WorkspaceIntelligenceObject,
) -> str:
    """Return compact display text for one search result."""

    for candidate in (
        intelligence_object.short_summary,
        intelligence_object.detailed_summary,
        intelligence_object.search_text,
        intelligence_object.subtitle,
    ):
        clean_candidate = " ".join(
            str(candidate or "").split()
        ).strip()

        if clean_candidate:
            return clean_candidate[:220]

    return ""


def build_workspace_search_scope(
    *,
    user_id: int,
    context: str,
    organization_ids: tuple,
    group_ids: tuple,
) -> Dict[str, Any]:
    """Build the user-facing search authority scope."""

    return {
        "owner": "current_user",
        "user_id": user_id,
        "context": context,
        "organization_ids": list(
            organization_ids
        ),
        "group_ids": list(
            group_ids
        ),
        "permission_mode": (
            WORKSPACE_SEARCH_PERMISSION_MODE
        ),
        "authority": "database",
    }


def build_workspace_search_empty_state(
    *,
    query: str,
    search_type: str,
) -> Optional[Dict[str, Any]]:
    """Build the full-search empty state payload."""

    if not query:
        return {
            "title": (
                "Search across Nations Systems"
            ),
            "message": (
                "Search files, conversations, people, "
                "and groups you are allowed to access."
            ),
            "search_type": search_type,
        }

    return {
        "title": "No matching results",
        "message": (
            "No files, conversations, people, or groups "
            "matched this search in your authorized workspace."
        ),
        "search_type": search_type,
    }


def should_offer_workspace_capability_request(
    query: str,
    result_count: int,
) -> bool:
    """Return whether a no-result query reads like a missing action."""

    if result_count:
        return False

    clean_query = normalize_workspace_search_query(
        query
    ).lower()

    if not clean_query:
        return False

    first_word = clean_query.split(
        " ",
        1,
    )[0]

    return first_word in WORKSPACE_SEARCH_CAPABILITY_ACTION_TERMS


def build_workspace_capability_request(
    *,
    query: str,
    result_count: int,
) -> Optional[Dict[str, Any]]:
    """Build a non-persistent missing-capability request draft."""

    if not should_offer_workspace_capability_request(
        query,
        result_count,
    ):
        return None

    return {
        "id": "capability_request_draft",
        "type": "capability_request",
        "type_label": "Request",
        "title": "Request this capability",
        "summary": (
            "Solomon does not have that action yet. "
            "Send this request to your group admin?"
        ),
        "requested_text": query,
        "authority": "server",
        "permission": "can_request",
        "actions": [
            "send_to_group_admin",
        ],
    }


def get_active_workspace_organization_ids(
    db_session,
    user_id: int,
) -> tuple:
    """Return active organizations the user belongs to."""

    if not user_id:
        return tuple()

    records = (
        db_session.query(
            OrganizationMembership.organization_id
        )
        .filter(
            OrganizationMembership.user_id == user_id,
            OrganizationMembership.status == "active",
            OrganizationMembership.removed_at.is_(None),
        )
        .all()
    )

    return tuple(
        str(record[0] or "").strip()
        for record in records
        if str(record[0] or "").strip()
    )


def get_active_workspace_group_ids(
    db_session,
    user_id: int,
) -> tuple:
    """Return active groups the user belongs to."""

    if not user_id:
        return tuple()

    records = (
        db_session.query(
            OrganizationGroupMembership.group_id
        )
        .filter(
            OrganizationGroupMembership.user_id == user_id,
            OrganizationGroupMembership.status == "active",
            OrganizationGroupMembership.removed_at.is_(None),
        )
        .all()
    )

    return tuple(
        str(record[0] or "").strip()
        for record in records
        if str(record[0] or "").strip()
    )


def build_workspace_search_authorization_filter(
    db_session,
    *,
    user_id: int,
    organization_ids: tuple,
    group_ids: tuple,
):
    """Build server-side Search discovery authority without derived-intelligence grants."""

    direct_file_grant_query = (
        db_session.query(
            FileAccessGrant.file_registry_id
        )
        .filter(
            FileAccessGrant.granted_to_user_id == user_id,
            FileAccessGrant.status == "active",
            FileAccessGrant.revoked_at.is_(None),
            FileAccessGrant.is_discoverable.is_(True),
            or_(
                FileAccessGrant.expires_at.is_(None),
                FileAccessGrant.expires_at > datetime.utcnow(),
            ),
        )
    )

    file_registry_authorization_filters = [
        FileRegistry.uploader_id == user_id,
        FileRegistry.id.in_(direct_file_grant_query),
    ]

    if group_ids:
        group_file_grant_query = (
            db_session.query(
                FileGroupAccessGrant.file_registry_id
            )
            .filter(
                FileGroupAccessGrant.group_id.in_(group_ids),
                FileGroupAccessGrant.status == "active",
                FileGroupAccessGrant.revoked_at.is_(None),
                FileGroupAccessGrant.is_discoverable.is_(True),
                or_(
                    FileGroupAccessGrant.expires_at.is_(None),
                    FileGroupAccessGrant.expires_at > datetime.utcnow(),
                ),
            )
        )
        file_registry_authorization_filters.append(
            FileRegistry.id.in_(group_file_grant_query)
        )

    authorized_file_registry_query = (
        db_session.query(FileRegistry.id)
        .filter(
            FileRegistry.status == "active",
            FileRegistry.deleted_at.is_(None),
            or_(*file_registry_authorization_filters),
        )
    )

    authorization_filters = [
        (
            (WorkspaceIntelligenceObject.object_type == "file")
            & WorkspaceIntelligenceObject.file_registry_id.in_(
                authorized_file_registry_query
            )
        ),
        (
            (WorkspaceIntelligenceObject.object_type != "file")
            & (WorkspaceIntelligenceObject.user_id == user_id)
        ),
    ]

    if organization_ids:
        authorization_filters.append(
            (WorkspaceIntelligenceObject.object_type != "file")
            & WorkspaceIntelligenceObject.organization_id.in_(
                organization_ids
            )
        )

    if group_ids:
        authorization_filters.append(
            (WorkspaceIntelligenceObject.object_type != "file")
            & WorkspaceIntelligenceObject.group_id.in_(
                group_ids
            )
        )

    return or_(*authorization_filters)


def resolve_workspace_search_permission(
    intelligence_object: WorkspaceIntelligenceObject,
    *,
    user_id: int,
    organization_ids: tuple,
    group_ids: tuple,
) -> Dict[str, str]:
    """Resolve the display permission label for a search result."""

    object_group_id = str(
        intelligence_object.group_id or ""
    ).strip()
    object_organization_id = str(
        intelligence_object.organization_id or ""
    ).strip()

    if intelligence_object.user_id == user_id:
        return {
            "permission": "owner",
            "scope_label": "My workspace",
        }

    if object_group_id and object_group_id in group_ids:
        return {
            "permission": "can_view",
            "scope_label": "Group",
        }

    if (
        object_organization_id
        and object_organization_id in organization_ids
    ):
        return {
            "permission": "can_view",
            "scope_label": "Company",
        }

    return {
        "permission": "can_view",
        "scope_label": "Shared",
    }


def build_workspace_search_actions(
    intelligence_object: WorkspaceIntelligenceObject,
) -> list:
    """Return actions the frontend can present for one search result."""

    object_type = str(
        intelligence_object.object_type or "item"
    ).strip().lower()
    actions = list(
        WORKSPACE_SEARCH_ACTIONS_BY_OBJECT_TYPE.get(
            object_type,
            (
                "open",
            ),
        )
    )

    if not intelligence_object.allow_ai_query:
        actions = [
            action
            for action in actions
            if action != "ask_about_this"
        ]

    return actions


def build_workspace_search_result(
    db_session,
    intelligence_object: WorkspaceIntelligenceObject,
    *,
    user_id: int,
    organization_ids: tuple,
    group_ids: tuple,
) -> Optional[Dict[str, Any]]:
    """Build one Search result after a current exposure-time authorization check."""

    object_type = str(
        intelligence_object.object_type or "item"
    ).strip().lower()

    result_label = WORKSPACE_SEARCH_OBJECT_LABELS.get(
        object_type,
        "Item",
    )
    icon_key = str(
        intelligence_object.icon_key
        or WORKSPACE_SEARCH_DEFAULT_ICONS.get(
            object_type,
            "search",
        )
    ).strip()
    route = intelligence_object.canonical_url or "#"

    allow_ai_query = bool(intelligence_object.allow_ai_query)

    if object_type == "file":
        file_registry_id = intelligence_object.file_registry_id

        if not file_registry_id:
            return None

        file_record = db_session.get(
            FileRegistry,
            file_registry_id,
        )

        if not file_record:
            return None

        permission_payload = resolve_workspace_file_registry_permission(
            db_session,
            file_record,
            user_id=user_id,
            organization_ids=organization_ids,
            group_ids=group_ids,
        )

        if not permission_payload.get("authorized", False):
            return None

        allow_ai_query = bool(
            permission_payload.get("allow_ai_query", False)
        )
    else:
        permission_payload = resolve_workspace_search_permission(
            intelligence_object,
            user_id=user_id,
            organization_ids=organization_ids,
            group_ids=group_ids,
        )

    summary = build_workspace_search_snippet(
        intelligence_object
    )
    if object_type == "file":
        actions = list(
            WORKSPACE_SEARCH_ACTIONS_BY_OBJECT_TYPE.get(
                "file",
                ("open",),
            )
        )
        if not allow_ai_query:
            actions = [
                action
                for action in actions
                if action != "ask_about_this"
            ]
    else:
        actions = build_workspace_search_actions(
            intelligence_object
        )

    return {
        "id": intelligence_object.intelligence_id,
        "type": object_type,
        "type_label": result_label,
        "title": intelligence_object.title or "Untitled",
        "summary": summary,
        "url": route,
        "route": route,
        "module": WORKSPACE_SEARCH_MODULE_BY_OBJECT_TYPE.get(
            object_type,
            "search",
        ),
        "icon": icon_key or "search",
        "meta": intelligence_object.subtitle or result_label,
        "snippet": summary,
        "source": "workspace_intelligence",
        "source_kind": object_type,
        "authority": "database",
        "permission": permission_payload["permission"],
        "scope_label": permission_payload["scope_label"],
        "actions": actions,
        "record_id": {
            "intelligence_id": intelligence_object.intelligence_id,
            "file_registry_id": intelligence_object.file_registry_id,
            "conversation_id": intelligence_object.conversation_id,
            "subject_user_id": intelligence_object.subject_user_id,
            "organization_id": intelligence_object.organization_id,
            "group_id": intelligence_object.group_id,
        },
        "evidence": {
            "short_summary": intelligence_object.short_summary,
            "source_locator": (
                intelligence_object.source_locator_json or {}
            ),
        },
        "index_status": intelligence_object.index_status or "pending",
        "summary_status": intelligence_object.summary_status or "pending",
        "facts_status": intelligence_object.facts_status or "pending",
        "allow_ai_query": allow_ai_query,
        "modified_at": serialize_workspace_file_datetime(
            intelligence_object.updated_at
        ),
        "modified_label": format_workspace_file_datetime_label(
            intelligence_object.updated_at
        ),
    }



def get_workspace_file_search_type_label(
    file_record: FileRegistry,
) -> str:
    """Return a stable file type label for registry-backed results."""

    extension = str(
        file_record.extension
        or ""
    ).strip().lower().lstrip(".")

    if not extension:
        original_name = str(
            file_record.original_name
            or ""
        ).strip().lower()

        if "." in original_name:
            extension = original_name.rsplit(
                ".",
                1,
            )[-1]

    if extension == "pdf":
        return "PDF Document"

    if extension in {
        "doc",
        "docx",
        "rtf",
        "odt",
    }:
        return "Document"

    if extension in {
        "xls",
        "xlsx",
        "xlsm",
        "csv",
        "tsv",
        "ods",
    }:
        return "Spreadsheet"

    if extension in {
        "ppt",
        "pptx",
        "odp",
    }:
        return "Presentation"

    if extension in {
        "png",
        "jpg",
        "jpeg",
        "gif",
        "webp",
        "svg",
        "bmp",
        "tif",
        "tiff",
    }:
        return "Image"

    return "File"


def get_workspace_file_search_icon(
    file_record: FileRegistry,
) -> str:
    """Return a file icon key for registry-backed results."""

    type_label = get_workspace_file_search_type_label(
        file_record
    )

    if type_label == "PDF Document":
        return "picture_as_pdf"

    if type_label == "Document":
        return "article"

    if type_label == "Spreadsheet":
        return "table_chart"

    if type_label == "Presentation":
        return "slideshow"

    if type_label == "Image":
        return "image"

    return "description"


def get_workspace_file_search_extension(
    file_record: FileRegistry,
) -> str:
    """Return the normalized extension for a FileRegistry record."""

    extension = str(
        file_record.extension
        or ""
    ).strip().lower().lstrip(".")

    if extension:
        return extension

    original_name = str(
        file_record.original_name
        or ""
    ).strip().lower()

    if "." not in original_name:
        return ""

    return original_name.rsplit(
        ".",
        1,
    )[-1].strip()


def normalize_workspace_file_size_bytes(
    value: Any,
) -> Optional[int]:
    """Return safe file size bytes for workspace metadata display."""

    if value is None:
        return None

    if isinstance(
        value,
        bool,
    ):
        return None

    try:
        size_bytes = int(
            value
        )
    except (
        TypeError,
        ValueError,
    ):
        return None

    if size_bytes < 0:
        return None

    return size_bytes


def format_workspace_file_size_label(
    value: Any,
) -> str:
    """Return the shared human-readable file size label."""

    size_bytes = normalize_workspace_file_size_bytes(
        value
    )

    if size_bytes is None:
        return ""

    if size_bytes == 1:
        return "1 byte"

    if size_bytes < 1024:
        return f"{size_bytes} bytes"

    size_value = float(
        size_bytes
    )
    units = (
        "KB",
        "MB",
        "GB",
        "TB",
    )

    for unit in units:
        size_value = size_value / 1024.0

        if size_value < 1024.0 or unit == units[-1]:
            if size_value >= 100:
                display_value = f"{size_value:.0f}"
            elif size_value >= 10:
                display_value = f"{size_value:.1f}"
            else:
                display_value = f"{size_value:.1f}"

            return f"{display_value} {unit}"

    return ""


def parse_workspace_file_datetime(
    value: Any,
) -> Optional[datetime]:
    """Return a datetime object for registry timestamps when possible."""

    if value is None:
        return None

    if isinstance(
        value,
        datetime,
    ):
        return value

    clean_value = str(
        value or ""
    ).strip()

    if not clean_value:
        return None

    if clean_value.endswith(
        "Z"
    ):
        clean_value = (
            f"{clean_value[:-1]}+00:00"
        )

    try:
        return datetime.fromisoformat(
            clean_value
        )
    except ValueError:
        return None


def serialize_workspace_file_datetime(
    value: Any,
) -> str:
    """Return a stable timestamp string for data attributes and JSON."""

    parsed_value = parse_workspace_file_datetime(
        value
    )

    if not parsed_value:
        return ""

    return parsed_value.isoformat()


def format_workspace_file_datetime_label(
    value: Any,
) -> str:
    """Return the shared uploaded timestamp display label."""

    parsed_value = parse_workspace_file_datetime(
        value
    )

    if not parsed_value:
        return ""

    hour_value = parsed_value.hour % 12 or 12
    meridiem = (
        "AM"
        if parsed_value.hour < 12
        else "PM"
    )

    return (
        f"{parsed_value.strftime('%b')} "
        f"{parsed_value.day}, "
        f"{parsed_value.year}, "
        f"{hour_value}:{parsed_value.minute:02d} "
        f"{meridiem}"
    )


def get_workspace_file_upload_timestamp(
    file_record: FileRegistry,
) -> Any:
    """Return upload time without using updated-at as a substitute."""

    for attribute_name in (
        "upload_time",
        "uploaded_at",
        "created_at",
    ):
        timestamp_value = getattr(
            file_record,
            attribute_name,
            None,
        )

        if timestamp_value:
            return timestamp_value

    return None


def resolve_workspace_file_location_label(
    result: Dict[str, Any],
    *,
    prefer_original: bool = False,
) -> str:
    """Return an authorized current or original location display label."""

    source_result = (
        result
        if isinstance(
            result,
            dict,
        )
        else {}
    )
    original_fields = (
        "original_location_label",
        "originalLocationLabel",
        "trash_original_location_label",
        "trashOriginalLocationLabel",
        "original_parent_name",
        "originalParentName",
    )
    current_fields = (
        "location_label",
        "workspace_location_label",
        "authorized_location_label",
        "folder_location_label",
        "parent_folder_name",
        "parentFolderName",
        "folder_name",
        "folderName",
    )
    field_groups = (
        (original_fields, current_fields)
        if prefer_original
        else (current_fields, original_fields)
    )
    location_sources = [
        source_result,
    ]

    for nested_key in (
        "source_locator",
        "sourceLocator",
        "metadata",
        "document_metadata",
        "workspace_metadata",
    ):
        nested_value = source_result.get(
            nested_key
        )

        if isinstance(
            nested_value,
            dict,
        ):
            location_sources.append(
                nested_value
            )

    evidence = source_result.get(
        "evidence"
    )

    if isinstance(
        evidence,
        dict,
    ):
        location_sources.append(
            evidence
        )

        for nested_key in (
            "source_locator",
            "sourceLocator",
        ):
            nested_value = evidence.get(
                nested_key
            )

            if isinstance(
                nested_value,
                dict,
            ):
                location_sources.append(
                    nested_value
                )

    for field_group in field_groups:
        for location_source in location_sources:
            for field_name in field_group:
                clean_value = str(
                    location_source.get(
                        field_name,
                        "",
                    )
                    or ""
                ).strip()

                if (
                    clean_value
                    and not (
                        prefer_original
                        and clean_value.lower() in {
                            "trash",
                            "in trash",
                        }
                    )
                ):
                    return clean_value

    scope_label = str(
        source_result.get(
            "scope_label",
            "",
        )
        or ""
    ).strip()

    normalized_scope = (
        scope_label.lower()
        .replace("-", "_")
        .replace(" ", "_")
    )

    if normalized_scope in {
        "my_workspace",
        "owner",
        "owned",
        "current_user",
    }:
        return "My Files"

    if normalized_scope == "group":
        return "Group"

    if normalized_scope in {
        "company",
        "organization",
        "organization_library",
        "company_library",
    }:
        return "Company"

    if normalized_scope == "shared":
        return "Shared"

    if scope_label:
        return scope_label

    return "My Files"


def resolve_workspace_file_status_token(
    file_record: FileRegistry,
) -> str:
    """Return canonical storage status for transport-only metadata."""

    if is_file_record_trashed(
        file_record
    ):
        return "trash"

    clean_status = str(
        getattr(
            file_record,
            "status",
            "",
        )
        or ""
    ).strip().lower()

    if clean_status:
        return (
            clean_status
            .replace("-", "_")
            .replace(" ", "_")
        )

    return "stored"


def resolve_workspace_file_status_label(
    status_token: str,
) -> str:
    """Return storage status label for legacy consumers."""

    clean_token = str(
        status_token or ""
    ).strip().lower()

    if clean_token in {
        "trash",
        "trashed",
        "deleted",
    }:
        return "In Trash"

    if clean_token in {
        "active",
        "stored",
        "ready",
    }:
        return "Stored"

    if not clean_token:
        return "Stored"

    return clean_token.replace(
        "_",
        " ",
    ).title()


def build_workspace_file_metadata_payload(
    result: Dict[str, Any],
    file_record: FileRegistry,
) -> Dict[str, Any]:
    """Return the shared Details-pane file metadata contract."""

    type_label = get_workspace_file_search_type_label(
        file_record
    )
    size_bytes = normalize_workspace_file_size_bytes(
        getattr(
            file_record,
            "size_bytes",
            None,
        )
    )
    size_label = format_workspace_file_size_label(
        size_bytes
    )
    uploaded_at_value = get_workspace_file_upload_timestamp(
        file_record
    )
    modified_at_value = (
        getattr(
            file_record,
            "updated_at",
            None,
        )
        or uploaded_at_value
    )
    uploaded_at = serialize_workspace_file_datetime(
        uploaded_at_value
    )
    uploaded_label = format_workspace_file_datetime_label(
        uploaded_at_value
    )
    modified_at = serialize_workspace_file_datetime(
        modified_at_value
    )
    modified_label = format_workspace_file_datetime_label(
        modified_at_value
    )
    status_token = resolve_workspace_file_status_token(
        file_record
    )
    location_label = resolve_workspace_file_location_label(
        result,
        prefer_original=(
            status_token == "trash"
        ),
    )
    status_label = resolve_workspace_file_status_label(
        status_token
    )

    return {
        "contract": WORKSPACE_DOCUMENT_METADATA_CONTRACT,
        "type_label": type_label,
        "file_type_label": type_label,
        "size_bytes": size_bytes,
        "size_label": size_label,
        "uploaded_at": uploaded_at,
        "uploaded_label": uploaded_label,
        "modified_at": modified_at,
        "modified_label": modified_label,
        "location_label": location_label,
        "original_location_label": (
            location_label
            if status_token == "trash"
            else ""
        ),
        "status": status_token,
        "status_token": status_token,
        "status_label": status_label,
    }


def build_workspace_document_thumbnail_url(
    random_name: str,
) -> str:
    """Return the authorized thumbnail route for a workspace file."""

    clean_random_name = str(
        random_name
        or ""
    ).strip()

    if not clean_random_name:
        return ""

    return (
        f"/workspace/document/{clean_random_name}/thumbnail"
    )


def build_workspace_file_search_thumbnail_url(
    file_record: FileRegistry,
) -> str:
    """Return a preview thumbnail URL when the file can expose one."""

    extension = get_workspace_file_search_extension(
        file_record
    )
    random_name = str(
        file_record.random_name
        or ""
    ).strip()

    if (
        not random_name
        or extension not in WORKSPACE_FILE_THUMBNAIL_EXTENSIONS
    ):
        return ""

    return build_workspace_document_thumbnail_url(
        random_name
    )


def apply_workspace_file_search_preview_fields(
    result: Dict[str, Any],
    file_record: FileRegistry,
) -> Dict[str, Any]:
    """Attach Home-compatible file authority and thumbnail fields."""

    if not isinstance(
        result,
        dict,
    ):
        return result

    extension = get_workspace_file_search_extension(
        file_record
    )
    random_name = str(
        file_record.random_name
        or ""
    ).strip()
    title = str(
        file_record.original_name
        or file_record.random_name
        or result.get(
            "title",
            "",
        )
        or "Untitled"
    ).strip()
    type_label = get_workspace_file_search_type_label(
        file_record
    )
    object_route = (
        f"/workspace/file/{random_name}"
        if random_name
        else "#"
    )
    reader_route = (
        f"{object_route}/reader"
        if object_route != "#"
        else "#"
    )
    thumbnail_url = build_workspace_file_search_thumbnail_url(
        file_record
    )

    result["title"] = title
    result["type"] = "file"
    result["type_label"] = type_label
    result["meta"] = type_label
    result["icon"] = get_workspace_file_search_icon(
        file_record
    )

    metadata_payload = build_workspace_file_metadata_payload(
        result,
        file_record,
    )
    size_bytes = metadata_payload.get(
        "size_bytes"
    )
    size_label = metadata_payload.get(
        "size_label",
        "",
    )
    uploaded_at = metadata_payload.get(
        "uploaded_at",
        "",
    )
    uploaded_label = metadata_payload.get(
        "uploaded_label",
        "",
    )
    modified_at = metadata_payload.get(
        "modified_at",
        "",
    )
    modified_label = metadata_payload.get(
        "modified_label",
        "",
    )
    location_label = metadata_payload.get(
        "location_label",
        "",
    )
    status_token = metadata_payload.get(
        "status",
        "",
    )
    status_label = metadata_payload.get(
        "status_label",
        "",
    )

    result["extension"] = extension
    result["file_extension"] = extension
    result["size_bytes"] = size_bytes
    result["file_size_bytes"] = size_bytes
    result["size_label"] = size_label
    result["file_size_label"] = size_label
    result["formatted_size"] = size_label
    result["display_size"] = size_label
    result["uploaded_at"] = uploaded_at
    result["uploadedAt"] = uploaded_at
    result["upload_time"] = uploaded_at
    result["uploadTime"] = uploaded_at
    result["uploaded_label"] = uploaded_label
    result["uploadedLabel"] = uploaded_label
    result["upload_label"] = uploaded_label
    result["uploadLabel"] = uploaded_label
    result["modified_at"] = modified_at
    result["modifiedAt"] = modified_at
    result["modified_label"] = modified_label
    result["modifiedLabel"] = modified_label
    result["owner_user_id"] = int(
        getattr(
            file_record,
            "uploader_id",
            0,
        )
        or 0
    )
    result["location_label"] = location_label
    result["workspace_location_label"] = location_label
    result["authorized_location_label"] = location_label

    if status_token == "trash":
        result["original_location_label"] = location_label

    result["storage_status"] = status_token
    result["library_status"] = status_token
    result["document_status"] = status_token
    result["storage_status_label"] = status_label
    result["document_status_label"] = status_label
    result["status_label"] = status_label
    result["metadata_contract"] = WORKSPACE_DOCUMENT_METADATA_CONTRACT
    result["metadata"] = dict(
        metadata_payload
    )
    result["document_metadata"] = dict(
        metadata_payload
    )
    result["workspace_metadata"] = dict(
        metadata_payload
    )

    if random_name:
        result["document_id"] = random_name
        result["documentId"] = random_name
        result["file_id"] = random_name
        result["fileId"] = random_name
        result["random_name"] = random_name
        result["randomName"] = random_name
        result["workspace_object_route"] = object_route
        result["workspaceObjectRoute"] = object_route
        result["document_route"] = object_route
        result["documentRoute"] = object_route
        result["file_route"] = object_route
        result["fileRoute"] = object_route
        result["url"] = reader_route
        result["route"] = reader_route
        result["reader_url"] = reader_route
        result["readerUrl"] = reader_route
        result["workspace_reader_url"] = reader_route
        result["workspaceReaderUrl"] = reader_route
        result["document_reader_url"] = reader_route
        result["documentReaderUrl"] = reader_route

    if thumbnail_url:
        result["thumbnail_url"] = thumbnail_url
        result["preview_thumbnail_url"] = thumbnail_url
        result["workspace_thumbnail_url"] = thumbnail_url
        result["preview_image_url"] = thumbnail_url

    return result


def hydrate_workspace_search_preview_fields(
    db_session,
    results: list,
    *,
    user_id: int,
) -> list:
    """Hydrate file search results with FileRegistry preview metadata."""

    if not results:
        return results

    file_registry_ids = {
        int(
            result.get(
                "record_id",
                {},
            ).get(
                "file_registry_id",
                0,
            )
            or 0
        )
        for result in results
        if isinstance(
            result,
            dict,
        )
        and result.get(
            "type",
        ) == "file"
    }
    file_registry_ids.discard(
        0
    )

    if not file_registry_ids:
        return results

    file_records = {
        file_record.id: file_record
        for file_record in (
            db_session.query(
                FileRegistry
            )
            .filter(
                FileRegistry.id.in_(
                    file_registry_ids
                )
            )
            .all()
        )
    }

    for result in results:
        if not isinstance(
            result,
            dict,
        ):
            continue

        file_registry_id = int(
            result.get(
                "record_id",
                {},
            ).get(
                "file_registry_id",
                0,
            )
            or 0
        )
        file_record = file_records.get(
            file_registry_id
        )

        if not file_record:
            continue

        apply_workspace_file_search_preview_fields(
            result,
            file_record,
        )

        access_decision = resolve_file_access_decision(
            db_session,
            file_record,
            user_id,
            action=READ_ACTION,
            allow_trashed_owner_read=True,
        )
        capabilities = build_file_capabilities(
            file_record,
            access_decision,
            requesting_user_id=user_id,
        )
        surface_actions = build_file_surface_actions(
            capabilities,
            surface=FILE_SURFACE_SEARCH,
        )

        result["capabilities"] = capabilities
        result["surface_actions"] = surface_actions
        result["available_actions"] = surface_actions
        result["actions"] = surface_actions
        result["action_surface"] = FILE_SURFACE_SEARCH
        result["allow_ai_query"] = bool(
            capabilities.get(
                "can_select_for_solomon_ai",
                False,
            )
        )

    return results


def get_workspace_search_file_type_filter(
    result: Dict[str, Any],
) -> Tuple[str, str]:
    """Return the user-facing file/result type filter projection."""

    result_type = normalize_workspace_search_filter_value(
        result.get(
            "type",
            "item",
        )
    )

    if result_type != "file":
        labels = {
            "conversation": "Conversations",
            "person": "People",
            "group": "Groups",
            "folder": "Folders",
        }
        return (
            result_type or "item",
            labels.get(
                result_type,
                str(
                    result.get(
                        "type_label",
                        "Items",
                    )
                    or "Items"
                ).strip(),
            ),
        )

    extension = normalize_workspace_search_filter_value(
        result.get(
            "extension",
            "",
        )
    )
    type_groups = {
        "pdf": ("pdf", "PDFs"),
        "doc": ("document", "Documents"),
        "docx": ("document", "Documents"),
        "odt": ("document", "Documents"),
        "rtf": ("document", "Documents"),
        "xls": ("spreadsheet", "Spreadsheets"),
        "xlsx": ("spreadsheet", "Spreadsheets"),
        "ods": ("spreadsheet", "Spreadsheets"),
        "csv": ("spreadsheet", "Spreadsheets"),
        "png": ("image", "Images"),
        "jpg": ("image", "Images"),
        "jpeg": ("image", "Images"),
        "webp": ("image", "Images"),
        "gif": ("image", "Images"),
        "bmp": ("image", "Images"),
        "tif": ("image", "Images"),
        "tiff": ("image", "Images"),
        "txt": ("text", "Text files"),
        "md": ("text", "Text files"),
    }

    return type_groups.get(
        extension,
        ("other_file", "Other files"),
    )


def get_workspace_search_people_filter(
    result: Dict[str, Any],
    *,
    user_id: int,
) -> Tuple[str, str]:
    """Return a non-authoritative display grouping for People filtering."""

    owner_user_id = int(
        result.get(
            "owner_user_id",
            0,
        )
        or 0
    )

    if owner_user_id and owner_user_id == user_id:
        return (
            "me",
            "Me",
        )

    scope_label = str(
        result.get(
            "scope_label",
            "Shared",
        )
        or "Shared"
    ).strip()
    normalized_scope = normalize_workspace_search_filter_value(
        scope_label
    )
    scope_projections = {
        "my_workspace": ("me", "Me"),
        "owner": ("me", "Me"),
        "group": ("group", "Group"),
        "company": ("company", "Company"),
        "organization": ("company", "Company"),
        "shared": ("shared", "Shared with me"),
    }

    return scope_projections.get(
        normalized_scope,
        (
            normalized_scope or "shared",
            scope_label or "Shared with me",
        ),
    )


def get_workspace_search_source_filter(
    result: Dict[str, Any],
) -> Tuple[str, str]:
    """Return the authorized result source projection."""

    result_type = normalize_workspace_search_filter_value(
        result.get(
            "type",
            "item",
        )
    )

    if result_type == "file":
        source_label = str(
            result.get(
                "location_label",
                "My Files",
            )
            or "My Files"
        ).strip()
    else:
        module = normalize_workspace_search_filter_value(
            result.get(
                "module",
                "search",
            )
        )
        module_labels = {
            "solomon_ai": "SolomonAI",
            "people": "People",
            "documents": "Documents",
        }
        source_label = module_labels.get(
            module,
            str(
                result.get(
                    "scope_label",
                    "Workspace",
                )
                or "Workspace"
            ).strip(),
        )

    return (
        normalize_workspace_search_filter_value(
            source_label
        ) or "workspace",
        source_label or "Workspace",
    )


def build_workspace_search_relevance_score(
    query: str,
    result: Dict[str, Any],
) -> int:
    """Return deterministic relevance for one authorized result."""

    clean_query = normalize_workspace_search_query(
        query
    ).lower()

    if not clean_query:
        return 0

    title = " ".join(
        str(
            result.get(
                "title",
                "",
            )
            or ""
        ).lower().split()
    )
    meta = " ".join(
        str(
            result.get(
                "meta",
                "",
            )
            or ""
        ).lower().split()
    )
    summary = " ".join(
        str(
            result.get(
                "summary",
                result.get(
                    "snippet",
                    "",
                ),
            )
            or ""
        ).lower().split()
    )
    source_label = " ".join(
        str(
            result.get(
                "search_source_label",
                "",
            )
            or ""
        ).lower().split()
    )
    score = 0

    if title == clean_query:
        score += 10000
    elif title.startswith(
        clean_query
    ):
        score += 6000
    elif clean_query in title:
        score += 4000

    if clean_query in meta:
        score += 1200

    if clean_query in summary:
        score += 600

    if clean_query in source_label:
        score += 200

    query_terms = [
        term
        for term in clean_query.split()
        if term
    ]

    for term in query_terms:
        if term in title:
            score += 350

        if term in meta:
            score += 90

        if term in summary:
            score += 35

    return score


def decorate_workspace_search_results(
    results: list,
    *,
    user_id: int,
    query: str,
) -> list:
    """Attach filter and sort projections after authority resolution."""

    for result in results:
        if not isinstance(
            result,
            dict,
        ):
            continue

        type_value, type_label = get_workspace_search_file_type_filter(
            result
        )
        people_value, people_label = get_workspace_search_people_filter(
            result,
            user_id=user_id,
        )
        source_value, source_label = get_workspace_search_source_filter(
            result
        )

        result["search_filter_type"] = type_value
        result["search_filter_type_label"] = type_label
        result["search_people"] = people_value
        result["search_people_label"] = people_label
        result["search_source"] = source_value
        result["search_source_label"] = source_label
        result["relevance_score"] = build_workspace_search_relevance_score(
            query,
            result,
        )

    return results


def build_public_workspace_search_result(
    result: Dict[str, Any],
) -> Dict[str, Any]:
    """Remove server-only scoring and filter projection fields."""

    public_result = dict(
        result
    )

    for field_name in (
        "owner_user_id",
        "relevance_score",
        "search_filter_type",
        "search_filter_type_label",
        "search_people",
        "search_people_label",
        "search_source",
        "search_source_label",
    ):
        public_result.pop(
            field_name,
            None,
        )

    return public_result


def get_workspace_search_timestamp(
    result: Dict[str, Any],
) -> Optional[datetime]:
    """Return the canonical modified timestamp for Search ordering."""

    for field_name in (
        "modified_at",
        "uploaded_at",
        "upload_time",
    ):
        parsed_value = parse_workspace_file_datetime(
            result.get(
                field_name
            )
        )

        if parsed_value:
            return parsed_value

    return None


def workspace_search_datetime_number(
    value: Optional[datetime],
) -> float:
    """Return a sortable timestamp without mixing aware and naive values."""

    if not value:
        return 0.0

    try:
        return float(
            value.timestamp()
        )
    except (
        OSError,
        OverflowError,
        ValueError,
    ):
        return 0.0


def workspace_search_matches_modified_filter(
    result: Dict[str, Any],
    filter_value: str,
    *,
    now: Optional[datetime] = None,
) -> bool:
    """Return whether one result belongs to a requested date window."""

    if not filter_value:
        return True

    modified_at = get_workspace_search_timestamp(
        result
    )

    if not modified_at:
        return False

    reference_now = now or datetime.now(
        tz=modified_at.tzinfo
    )

    if modified_at.tzinfo and not reference_now.tzinfo:
        reference_now = reference_now.replace(
            tzinfo=modified_at.tzinfo
        )
    elif reference_now.tzinfo and not modified_at.tzinfo:
        modified_at = modified_at.replace(
            tzinfo=reference_now.tzinfo
        )

    if filter_value == "today":
        return modified_at.date() == reference_now.date()

    if filter_value == "last_7_days":
        return modified_at >= reference_now - timedelta(
            days=7
        )

    if filter_value == "last_30_days":
        return modified_at >= reference_now - timedelta(
            days=30
        )

    if filter_value == "this_year":
        return modified_at.year == reference_now.year

    return True


def build_workspace_search_choice_options(
    results: list,
    *,
    value_field: str,
    label_field: str,
) -> list:
    """Build sorted filter options and authorized match counts."""

    option_map = {}

    for result in results:
        if not isinstance(
            result,
            dict,
        ):
            continue

        option_value = normalize_workspace_search_filter_value(
            result.get(
                value_field,
                "",
            )
        )
        option_label = str(
            result.get(
                label_field,
                "",
            )
            or ""
        ).strip()

        if not option_value or not option_label:
            continue

        option_payload = option_map.setdefault(
            option_value,
            {
                "value": option_value,
                "label": option_label,
                "count": 0,
            },
        )
        option_payload["count"] += 1

    return sorted(
        option_map.values(),
        key=lambda option: (
            str(
                option.get(
                    "label",
                    "",
                )
            ).lower(),
            str(
                option.get(
                    "value",
                    "",
                )
            ),
        ),
    )


def build_workspace_search_filter_options(
    results: list,
) -> Dict[str, list]:
    """Build Type, People, Modified, and Source options."""

    modified_options = []

    for option_value, option_label in WORKSPACE_SEARCH_MODIFIED_FILTERS:
        option_count = sum(
            1
            for result in results
            if isinstance(
                result,
                dict,
            )
            and workspace_search_matches_modified_filter(
                result,
                option_value,
            )
        )

        if option_count:
            modified_options.append({
                "value": option_value,
                "label": option_label,
                "count": option_count,
            })

    return {
        "type": build_workspace_search_choice_options(
            results,
            value_field="search_filter_type",
            label_field="search_filter_type_label",
        ),
        "people": build_workspace_search_choice_options(
            results,
            value_field="search_people",
            label_field="search_people_label",
        ),
        "modified": modified_options,
        "source": build_workspace_search_choice_options(
            results,
            value_field="search_source",
            label_field="search_source_label",
        ),
    }


def validate_workspace_search_choice(
    value: str,
    options: list,
) -> str:
    """Return a selected dynamic filter only when the server offers it."""

    if not value:
        return ""

    allowed_values = {
        normalize_workspace_search_filter_value(
            option.get(
                "value",
                "",
            )
        )
        for option in options
        if isinstance(
            option,
            dict,
        )
    }

    if value in allowed_values:
        return value

    return ""


def filter_workspace_search_results(
    results: list,
    *,
    filter_type: str,
    people: str,
    modified: str,
    source: str,
) -> list:
    """Apply authorized Search filters before the public result limit."""

    return [
        result
        for result in results
        if isinstance(
            result,
            dict,
        )
        and (
            not filter_type
            or result.get(
                "search_filter_type"
            ) == filter_type
        )
        and (
            not people
            or result.get(
                "search_people"
            ) == people
        )
        and workspace_search_matches_modified_filter(
            result,
            modified,
        )
        and (
            not source
            or result.get(
                "search_source"
            ) == source
        )
    ]


def get_workspace_search_sort_value(
    result: Dict[str, Any],
    sort_key: str,
):
    """Return one deterministic Search sorting value."""

    title = str(
        result.get(
            "title",
            "",
        )
        or ""
    ).strip().lower()

    if sort_key == "relevance":
        return (
            int(
                result.get(
                    "relevance_score",
                    0,
                )
                or 0
            ),
            workspace_search_datetime_number(
                get_workspace_search_timestamp(
                    result
                )
            ),
            title,
        )

    if sort_key == "modified":
        return (
            workspace_search_datetime_number(
                get_workspace_search_timestamp(
                    result
                )
            ),
            title,
        )

    if sort_key == "type":
        return (
            str(
                result.get(
                    "type_label",
                    "",
                )
                or ""
            ).strip().lower(),
            title,
        )

    if sort_key == "size":
        return (
            int(
                result.get(
                    "size_bytes",
                    0,
                )
                or 0
            ),
            title,
        )

    return (
        title,
        workspace_search_datetime_number(
            get_workspace_search_timestamp(
                result
            )
        ),
    )


def sort_workspace_search_results(
    results: list,
    *,
    sort_key: str,
    direction: str,
    folder_placement: str,
) -> list:
    """Sort authorized filtered results using the canonical Search state."""

    reverse = direction == "desc"

    def sort_group(group):
        return sorted(
            group,
            key=lambda result: get_workspace_search_sort_value(
                result,
                sort_key,
            ),
            reverse=reverse,
        )

    if folder_placement != "top":
        return sort_group(
            results
        )

    folders = [
        result
        for result in results
        if normalize_workspace_search_filter_value(
            result.get(
                "type",
                "",
            )
        ) == "folder"
    ]
    other_results = [
        result
        for result in results
        if normalize_workspace_search_filter_value(
            result.get(
                "type",
                "",
            )
        ) != "folder"
    ]

    return [
        *sort_group(
            folders
        ),
        *sort_group(
            other_results
        ),
    ]


def build_workspace_search_route(
    *,
    query: str,
    search_type: str,
    filter_type: str,
    people: str,
    modified: str,
    source: str,
    sort_key: str,
    direction: str,
    folder_placement: str,
    layout: str,
) -> str:
    """Return the canonical public Search route for restoration."""

    query_items = [
        ("q", query),
        ("type", search_type),
        ("sort", sort_key),
        ("direction", direction),
        ("folders", folder_placement),
        ("layout", layout),
    ]

    for parameter_name, parameter_value in (
        ("filter_type", filter_type),
        ("people", people),
        ("modified", modified),
        ("source", source),
    ):
        if parameter_value:
            query_items.append(
                (
                    parameter_name,
                    parameter_value,
                )
            )

    return f"/search?{urlencode(query_items)}"


def resolve_workspace_file_registry_permission(
    db_session,
    file_record: FileRegistry,
    *,
    user_id: int,
    organization_ids: tuple,
    group_ids: tuple,
) -> Dict[str, Any]:
    """Resolve Search permission from the canonical current file authority."""

    discover_decision = resolve_file_access_decision(
        db_session,
        file_record,
        user_id,
        action=DISCOVER_ACTION,
    )

    if not discover_decision:
        return {
            "authorized": False,
            "permission": "none",
            "scope_label": "Unavailable",
            "allow_ai_query": False,
        }

    access_scope = str(
        discover_decision.get("access_scope") or ""
    ).strip().lower()
    scope_label = {
        "my_files": "My workspace",
        "shared_with_me": "Shared",
        "shared_with_group": "Group",
    }.get(
        access_scope,
        "Shared",
    )

    query_decision = resolve_file_access_decision(
        db_session,
        file_record,
        user_id,
        action=QUERY_ACTION,
    )

    return {
        "authorized": True,
        "permission": str(
            discover_decision.get("permission") or "view"
        ).strip().lower(),
        "scope_label": scope_label,
        "allow_ai_query": bool(query_decision),
    }


def build_workspace_file_registry_search_result(
    db_session,
    file_record: FileRegistry,
    *,
    user_id: int,
    organization_ids: tuple,
    group_ids: tuple,
) -> Optional[Dict[str, Any]]:
    """Build a canonical search result from FileRegistry authority."""

    title = str(
        file_record.original_name
        or file_record.random_name
        or "Untitled"
    ).strip()
    random_name = str(
        file_record.random_name
        or ""
    ).strip()
    object_route = (
        f"/workspace/file/{random_name}"
        if random_name
        else "#"
    )
    reader_route = (
        f"{object_route}/reader"
        if object_route != "#"
        else "#"
    )
    type_label = get_workspace_file_search_type_label(
        file_record
    )
    permission_payload = resolve_workspace_file_registry_permission(
        db_session,
        file_record,
        user_id=user_id,
        organization_ids=organization_ids,
        group_ids=group_ids,
    )
    if not permission_payload.get("authorized", False):
        return None

    allow_ai_query = bool(
        permission_payload.get(
            "allow_ai_query",
            False,
        )
    )
    summary = (
        f"{type_label} stored in the file registry."
    )

    result = {
        "id": f"file_registry_{file_record.id}",
        "type": "file",
        "type_label": type_label,
        "title": title,
        "summary": summary,
        "url": reader_route,
        "route": reader_route,
        "reader_url": reader_route,
        "workspace_reader_url": reader_route,
        "document_reader_url": reader_route,
        "workspace_object_route": object_route,
        "document_route": object_route,
        "file_route": object_route,
        "module": "documents",
        "icon": get_workspace_file_search_icon(
            file_record
        ),
        "meta": type_label,
        "snippet": summary,
        "source": "file_registry",
        "source_kind": "file",
        "authority": "database",
        "permission": permission_payload["permission"],
        "scope_label": permission_payload["scope_label"],
        "actions": [
            action
            for action in WORKSPACE_SEARCH_ACTIONS_BY_OBJECT_TYPE["file"]
            if action != "ask_about_this" or allow_ai_query
        ],
        "record_id": {
            "intelligence_id": None,
            "file_registry_id": file_record.id,
            "conversation_id": None,
            "subject_user_id": None,
            "organization_id": None,
            "group_id": None,
        },
        "evidence": {
            "short_summary": summary,
            "source_locator": {
                "source": "file_registry",
                "random_name": random_name,
            },
        },
        "index_status": "ready",
        "summary_status": "registry",
        "facts_status": "registry",
        "allow_ai_query": allow_ai_query,
        "document_id": random_name,
        "file_id": random_name,
        "random_name": random_name,
        "extension": str(
            file_record.extension
            or ""
        ).strip().lower().lstrip("."),
        "size_bytes": file_record.size_bytes,
    }

    return apply_workspace_file_search_preview_fields(
        result,
        file_record,
    )


def build_workspace_file_registry_authorization_filter(
    db_session,
    *,
    user_id: int,
    organization_ids: tuple,
    group_ids: tuple,
):
    """Build FileRegistry Search authority from Owner/direct/Group grants only."""

    authorization_filters = [
        FileRegistry.uploader_id == user_id,
    ]

    direct_file_grant_query = (
        db_session.query(
            FileAccessGrant.file_registry_id
        )
        .filter(
            FileAccessGrant.granted_to_user_id == user_id,
            FileAccessGrant.status == "active",
            FileAccessGrant.revoked_at.is_(None),
            FileAccessGrant.is_discoverable.is_(True),
            or_(
                FileAccessGrant.expires_at.is_(None),
                FileAccessGrant.expires_at > datetime.utcnow(),
            ),
        )
    )
    authorization_filters.append(
        FileRegistry.id.in_(direct_file_grant_query)
    )

    if group_ids:
        group_file_grant_query = (
            db_session.query(
                FileGroupAccessGrant.file_registry_id
            )
            .filter(
                FileGroupAccessGrant.group_id.in_(group_ids),
                FileGroupAccessGrant.status == "active",
                FileGroupAccessGrant.revoked_at.is_(None),
                FileGroupAccessGrant.is_discoverable.is_(True),
                or_(
                    FileGroupAccessGrant.expires_at.is_(None),
                    FileGroupAccessGrant.expires_at > datetime.utcnow(),
                ),
            )
        )
        authorization_filters.append(
            FileRegistry.id.in_(group_file_grant_query)
        )

    return or_(*authorization_filters)


def extend_workspace_search_with_registry_files(
    db_session,
    *,
    user_id: int,
    query: str,
    allowed_object_types: tuple,
    organization_ids: tuple,
    group_ids: tuple,
    results: list,
    candidate_limit: Optional[int] = None,
) -> list:
    """Merge active FileRegistry matches missing from the intelligence index."""

    if "file" not in allowed_object_types:
        return results

    existing_file_registry_ids = {
        int(
            result.get(
                "record_id",
                {},
            ).get(
                "file_registry_id",
                0,
            )
            or 0
        )
        for result in results
        if isinstance(
            result,
            dict,
        )
    }
    existing_file_registry_ids.discard(
        0
    )

    like_pattern = build_workspace_search_like_pattern(
        query
    )
    authorization_filter = (
        build_workspace_file_registry_authorization_filter(
            db_session,
            user_id=user_id,
            organization_ids=organization_ids,
            group_ids=group_ids,
        )
    )

    file_query = (
        db_session.query(
            FileRegistry
        )
        .filter(
            FileRegistry.status == "active",
            FileRegistry.deleted_at.is_(None),
            authorization_filter,
        )
        .filter(
            (
                FileRegistry.original_name.ilike(
                    like_pattern,
                    escape="\\",
                )
            )
            | (
                FileRegistry.random_name.ilike(
                    like_pattern,
                    escape="\\",
                )
            )
            | (
                FileRegistry.extension.ilike(
                    like_pattern,
                    escape="\\",
                )
            )
        )
        .order_by(
            FileRegistry.updated_at.desc(),
            FileRegistry.upload_time.desc(),
            FileRegistry.id.desc(),
        )
    )

    if existing_file_registry_ids:
        file_query = file_query.filter(
            FileRegistry.id.notin_(
                existing_file_registry_ids
            )
        )

    if candidate_limit:
        file_query = file_query.limit(
            candidate_limit
        )

    registry_results = [
        result
        for result in (
            build_workspace_file_registry_search_result(
                db_session,
                file_record,
                user_id=user_id,
                organization_ids=organization_ids,
                group_ids=group_ids,
            )
            for file_record in file_query.all()
        )
        if isinstance(result, dict)
    ]

    return [
        *results,
        *registry_results,
    ]


def search_workspace_intelligence(
    *,
    user_id: int,
    query: str,
    search_type: str,
    context: str = "global",
    limit: int = WORKSPACE_SEARCH_MAX_RESULTS,
    filter_type: str = "",
    people: str = "",
    modified: str = "",
    source: str = "",
    sort_key: str = "relevance",
    direction: str = "",
    folder_placement: str = "top",
    layout: str = "list",
    include_listing_controls: bool = True,
) -> Dict[str, Any]:
    """Search authorized Workspace Intelligence objects."""

    clean_query = normalize_workspace_search_query(
        query
    )
    clean_type = normalize_workspace_search_type(
        search_type
    )
    clean_context = normalize_workspace_search_context(
        context
    )
    clean_limit = normalize_workspace_search_limit(
        str(limit),
        default_limit=WORKSPACE_SEARCH_MAX_RESULTS,
    )
    clean_filter_type = normalize_workspace_search_filter_value(
        filter_type
    )
    clean_people = normalize_workspace_search_filter_value(
        people
    )
    clean_modified = normalize_workspace_search_modified_filter(
        modified
    )
    clean_source = normalize_workspace_search_filter_value(
        source
    )
    clean_sort_key = normalize_workspace_search_sort_key(
        sort_key
    )
    clean_direction = normalize_workspace_search_direction(
        direction,
        sort_key=clean_sort_key,
    )
    clean_folder_placement = normalize_workspace_search_folder_placement(
        folder_placement
    )
    clean_layout = normalize_workspace_search_layout(
        layout
    )
    response_state = {
        "filter_type": clean_filter_type,
        "people": clean_people,
        "modified": clean_modified,
        "source": clean_source,
        "sort_key": clean_sort_key,
        "direction": clean_direction,
        "folder_placement": clean_folder_placement,
        "layout": clean_layout,
    }

    if not user_id:
        return build_workspace_search_response(
            user_id=0,
            query=clean_query,
            search_type=clean_type,
            context=clean_context,
            organization_ids=tuple(),
            group_ids=tuple(),
            results=[],
            unfiltered_results=[],
            filtered_count=0,
            limit=clean_limit,
            **response_state,
        )

    db_session = SessionLocal()

    try:
        organization_ids = (
            get_active_workspace_organization_ids(
                db_session,
                user_id,
            )
        )
        group_ids = (
            get_active_workspace_group_ids(
                db_session,
                user_id,
            )
        )

        if not clean_query:
            return build_workspace_search_response(
                user_id=user_id,
                query=clean_query,
                search_type=clean_type,
                context=clean_context,
                organization_ids=organization_ids,
                group_ids=group_ids,
                results=[],
                unfiltered_results=[],
                filtered_count=0,
                limit=clean_limit,
                **response_state,
            )

        allowed_object_types = (
            WORKSPACE_SEARCH_OBJECT_TYPES.get(
                clean_type,
                WORKSPACE_SEARCH_OBJECT_TYPES["all"],
            )
        )
        like_pattern = build_workspace_search_like_pattern(
            clean_query
        )
        authorization_filter = (
            build_workspace_search_authorization_filter(
                db_session,
                user_id=user_id,
                organization_ids=organization_ids,
                group_ids=group_ids,
            )
        )

        query_set = (
            db_session.query(
                WorkspaceIntelligenceObject
            )
            .filter(
                WorkspaceIntelligenceObject.object_type.in_(
                    allowed_object_types
                ),
                WorkspaceIntelligenceObject.status == "active",
                WorkspaceIntelligenceObject.is_discoverable.is_(True),
                WorkspaceIntelligenceObject.deleted_at.is_(None),
                authorization_filter,
            )
            .filter(
                (
                    WorkspaceIntelligenceObject.title.ilike(
                        like_pattern,
                        escape="\\",
                    )
                )
                | (
                    WorkspaceIntelligenceObject.subtitle.ilike(
                        like_pattern,
                        escape="\\",
                    )
                )
                | (
                    WorkspaceIntelligenceObject.search_text.ilike(
                        like_pattern,
                        escape="\\",
                    )
                )
                | (
                    WorkspaceIntelligenceObject.short_summary.ilike(
                        like_pattern,
                        escape="\\",
                    )
                )
                | (
                    WorkspaceIntelligenceObject.detailed_summary.ilike(
                        like_pattern,
                        escape="\\",
                    )
                )
            )
            .order_by(
                WorkspaceIntelligenceObject.updated_at.desc(),
                WorkspaceIntelligenceObject.id.desc(),
            )
        )

        if not include_listing_controls:
            query_set = query_set.limit(
                clean_limit
            )

        results = [
            result
            for result in (
                build_workspace_search_result(
                    db_session,
                    intelligence_object,
                    user_id=user_id,
                    organization_ids=organization_ids,
                    group_ids=group_ids,
                )
                for intelligence_object in query_set.all()
            )
            if isinstance(result, dict)
        ]
        results = extend_workspace_search_with_registry_files(
            db_session,
            user_id=user_id,
            query=clean_query,
            allowed_object_types=allowed_object_types,
            organization_ids=organization_ids,
            group_ids=group_ids,
            results=results,
            candidate_limit=(
                None
                if include_listing_controls
                else clean_limit
            ),
        )
        results = hydrate_workspace_search_preview_fields(
            db_session,
            results,
            user_id=user_id,
        )
        unfiltered_results = decorate_workspace_search_results(
            results,
            user_id=user_id,
            query=clean_query,
        )
        available_filter_options = build_workspace_search_filter_options(
            unfiltered_results
        )
        clean_filter_type = validate_workspace_search_choice(
            clean_filter_type,
            available_filter_options.get(
                "type",
                [],
            ),
        )
        clean_people = validate_workspace_search_choice(
            clean_people,
            available_filter_options.get(
                "people",
                [],
            ),
        )
        clean_source = validate_workspace_search_choice(
            clean_source,
            available_filter_options.get(
                "source",
                [],
            ),
        )
        response_state.update({
            "filter_type": clean_filter_type,
            "people": clean_people,
            "source": clean_source,
        })
        filtered_results = filter_workspace_search_results(
            unfiltered_results,
            filter_type=clean_filter_type,
            people=clean_people,
            modified=clean_modified,
            source=clean_source,
        )
        filtered_count = len(
            filtered_results
        )
        sorted_results = sort_workspace_search_results(
            filtered_results,
            sort_key=clean_sort_key,
            direction=clean_direction,
            folder_placement=clean_folder_placement,
        )
        visible_results = [
            build_public_workspace_search_result(
                result
            )
            for result in sorted_results[:clean_limit]
        ]

        return build_workspace_search_response(
            user_id=user_id,
            query=clean_query,
            search_type=clean_type,
            context=clean_context,
            organization_ids=organization_ids,
            group_ids=group_ids,
            results=visible_results,
            unfiltered_results=unfiltered_results,
            filtered_count=filtered_count,
            limit=clean_limit,
            **response_state,
        )
    except Exception as exc:
        logger.exception(
            "[workspace.search.failed] "
            "request_id=%s user_id=%s query=%s type=%s error=%s",
            get_request_id(),
            user_id,
            clean_query,
            clean_type,
            exc,
        )

        return build_workspace_search_response(
            user_id=user_id,
            query=clean_query,
            search_type=clean_type,
            context=clean_context,
            organization_ids=tuple(),
            group_ids=tuple(),
            results=[],
            unfiltered_results=[],
            filtered_count=0,
            limit=clean_limit,
            ok=False,
            error=(
                "Search could not be completed."
            ),
            **response_state,
        )
    finally:
        db_session.close()


def build_workspace_search_response(
    *,
    user_id: int,
    query: str,
    search_type: str,
    context: str,
    organization_ids: tuple,
    group_ids: tuple,
    results: list,
    unfiltered_results: list,
    filtered_count: int,
    limit: int,
    filter_type: str,
    people: str,
    modified: str,
    source: str,
    sort_key: str,
    direction: str,
    folder_placement: str,
    layout: str,
    ok: bool = True,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the canonical Nations Global Search response."""

    result_count = len(
        results
    )
    unfiltered_count = len(
        unfiltered_results
    )
    active_filter_count = sum(
        1
        for filter_value in (
            filter_type,
            people,
            modified,
            source,
        )
        if filter_value
    )
    search_route = build_workspace_search_route(
        query=query,
        search_type=search_type,
        filter_type=filter_type,
        people=people,
        modified=modified,
        source=source,
        sort_key=sort_key,
        direction=direction,
        folder_placement=folder_placement,
        layout=layout,
    )
    filter_options = build_workspace_search_filter_options(
        unfiltered_results
    )
    payload = {
        "ok": ok,
        "contract": WORKSPACE_SEARCH_CONTRACT,
        "query": query,
        "type": search_type,
        "context": context,
        "permission_mode": WORKSPACE_SEARCH_PERMISSION_MODE,
        "result_count": result_count,
        "filtered_count": filtered_count,
        "unfiltered_count": unfiltered_count,
        "limit": limit,
        "has_more": filtered_count > result_count,
        "results": results,
        "route": search_route,
        "state": {
            "filter_type": filter_type,
            "people": people,
            "modified": modified,
            "source": source,
            "sort": sort_key,
            "direction": direction,
            "folders": folder_placement,
            "layout": layout,
            "active_filter_count": active_filter_count,
        },
        "filters": {
            "type": {
                "value": filter_type,
                "options": filter_options.get(
                    "type",
                    [],
                ),
            },
            "people": {
                "value": people,
                "options": filter_options.get(
                    "people",
                    [],
                ),
            },
            "modified": {
                "value": modified,
                "options": filter_options.get(
                    "modified",
                    [],
                ),
            },
            "source": {
                "value": source,
                "options": filter_options.get(
                    "source",
                    [],
                ),
            },
        },
        "sort": {
            "key": sort_key,
            "direction": direction,
            "folders": folder_placement,
            "default_key": "relevance",
            "allowed_keys": sorted(
                WORKSPACE_SEARCH_ALLOWED_SORT_KEYS
            ),
        },
        "layout": layout,
        "scope": build_workspace_search_scope(
            user_id=user_id,
            context=context,
            organization_ids=organization_ids,
            group_ids=group_ids,
        ),
        "empty_state": build_workspace_search_empty_state(
            query=query,
            search_type=search_type,
        ),
        "capability_request": build_workspace_capability_request(
            query=query,
            result_count=unfiltered_count,
        ),
    }

    if error:
        payload["error"] = error

    return payload


# ============================================================
# REQUEST / SESSION CONTEXT
# ============================================================
@app.before_request
def ensure_request_context():
    if "request_id" not in g:
        g.request_id = os.urandom(
            8
        ).hex()


def get_request_id() -> str:
    return getattr(
        g,
        "request_id",
        "unknown",
    )


def get_current_user_id() -> Optional[int]:
    user_id = session.get(
        "user_id"
    )

    if not user_id:
        return None

    try:
        return int(
            user_id
        )
    except (
        TypeError,
        ValueError,
    ):
        return None


def get_user_account_context() -> Dict[str, Any]:
    cached_context = getattr(
        g,
        "account_context",
        None,
    )

    if isinstance(
        cached_context,
        dict,
    ):
        return cached_context

    user_id = get_current_user_id()

    if not user_id:
        return {}

    account_context = resolve_account_context_for_user(
        user_id
    )

    if not isinstance(
        account_context,
        dict,
    ):
        account_context = {}

    g.account_context = account_context

    return account_context


def get_command_context() -> Dict[str, Any]:
    account_context = get_user_account_context()
    active_group_id = (
        account_context.get(
            "active_group_id"
        )
    )

    return {
        "user_id": get_current_user_id(),
        "account_context": account_context,
        "active_group_id": active_group_id,
    }


@app.context_processor
def inject_shell_context():
    account_context = get_user_account_context()
    active_group = (
        account_context.get(
            "active_group"
        )
        or {}
    )
    user_role = (
        account_context.get(
            "membership_role"
        )
        or "guest"
    )
    active_group_id = (
        account_context.get(
            "active_group_id"
        )
    )
    setup_complete = bool(
        account_context.get(
            "setup_complete"
        )
    )
    pending_setup_required = bool(
        account_context.get(
            "pending_setup_required"
        )
    )

    return {
        "command_modules": COMMAND_MODULES,
        "supported_workflows": SUPPORTED_WORKFLOWS,
        "request_id": get_request_id(),
        "account_context": account_context,
        "active_group": active_group,
        "active_group_id": active_group_id,
        "active_user_role": user_role,
        "group_setup_complete": setup_complete,
        "group_setup_required": pending_setup_required,
        "active_company_name": (
            account_context.get(
                "organization_name"
            )
            or account_context.get(
                "group_name"
            )
            or ""
        ),
    }


# ============================================================
# GROUP SETUP ACCESS GUARD
# ============================================================
@app.before_request
def enforce_group_setup_gate():
    path = str(
        request.path or ""
    )
    user_id = get_current_user_id()

    if not user_id:
        return None

    if path in GROUP_SETUP_EXEMPT_PATHS:
        return None

    if path.startswith(
        GROUP_SETUP_EXEMPT_PREFIXES
    ):
        return None

    account_context = get_user_account_context()

    if not bool(
        account_context.get(
            "pending_setup_required"
        )
    ):
        return None

    if path == GROUP_SETUP_PATH:
        return None

    if is_workspace_render_request():
        response = make_response(
            render_template(
                WORKSPACE_RENDER_TEMPLATE,
                active_module="people",
                active_section="setup",
                workspace_partial=True,
                workspace_content_template=(
                    "components/group_setup_required.html"
                ),
            )
        )
        response.headers[WORKSPACE_RENDER_MODE_HEADER] = (
            WORKSPACE_RENDER_MODE_WORKSPACE
        )
        response.status_code = 409
        return response

    return redirect(
        GROUP_SETUP_PATH
    )


def get_shell_identity() -> Dict[str, str]:
    return {
        "product_name": "General Contractor AI",
        "assistant_name": "SolomonAI",
        "company_name": "Nations Systems",
        "suite_name": "Operations Console",
    }


# ============================================================
# WORKSPACE RENDER HELPERS
# ============================================================
DOCUMENT_WORKSPACE_RETURN_PATHS = frozenset({
    "/",
    "/recent",
    "/search",
    "/shared",
    "/trash",
})


def normalize_document_workspace_return_route(
    value: Optional[str],
    *,
    fallback: str = "/",
) -> str:
    clean_fallback = str(fallback or "/").strip() or "/"

    if clean_fallback not in DOCUMENT_WORKSPACE_RETURN_PATHS:
        clean_fallback = "/"

    clean_value = str(value or "").strip()

    if not clean_value:
        return clean_fallback

    try:
        parsed = urlsplit(clean_value)
    except ValueError:
        return clean_fallback

    if parsed.scheme or parsed.netloc:
        return clean_fallback

    clean_path = str(parsed.path or "/").strip() or "/"

    if clean_path not in DOCUMENT_WORKSPACE_RETURN_PATHS:
        return clean_fallback

    return "".join((
        clean_path,
        f"?{parsed.query}" if parsed.query else "",
        f"#{parsed.fragment}" if parsed.fragment else "",
    ))


def render_workspace_content(
    *,
    active_module: str,
    active_section: Optional[str] = None,
    workspace_content_template: Optional[str] = None,
    **context,
):
    template_name = workspace_content_template

    if not template_name:
        template_name = (
            "components/document_workspace.html"
        )

    response = make_response(
        render_template(
            WORKSPACE_RENDER_TEMPLATE,
            active_module=active_module,
            active_section=active_section,
            workspace_partial=True,
            workspace_content_template=template_name,
            **context,
        )
    )

    response.headers[WORKSPACE_RENDER_MODE_HEADER] = (
        WORKSPACE_RENDER_MODE_WORKSPACE
    )

    return response


def get_command_module_payload(
    active_module: Optional[str],
) -> Tuple[str, Optional[Dict[str, Any]]]:
    clean_module = str(
        active_module
        or DEFAULT_COMMAND_MODULE
    ).strip().lower()

    if clean_module in {
        "home",
        "docs",
    }:
        clean_module = DEFAULT_COMMAND_MODULE

    return (
        clean_module,
        COMMAND_MODULES.get(
            clean_module
        ),
    )


def get_compat_browser_content(
    active_module: str,
    active_section: Optional[str] = None,
    workspace_content_template: Optional[str] = None,
    **context,
):
    module_id, command_module = get_command_module_payload(
        active_module
    )

    if command_module is None:
        return workflow_error(
            "CommandModuleNotFound",
            (
                "The selected command module "
                "is not available."
            ),
            status_code=404,
            extra={
                "module_id": module_id,
                "available_modules": list(
                    COMMAND_MODULES.keys()
                ),
            },
        )

    workspace_section = ""

    if module_id == DEFAULT_COMMAND_MODULE:
        workspace_section = normalize_document_workspace_section(
            active_section
            or DEFAULT_DOCUMENT_WORKSPACE_SECTION
        )

    template_name = (
        workspace_content_template
        or "components/document_workspace.html"
    )

    return render_template(
        "index.html",
        active_module=module_id,
        active_section=active_section,
        command_module=command_module,
        command_department=get_command_department(
            module_id,
            command_module,
        ),
        command_modules=COMMAND_MODULES,
        supported_workflows=SUPPORTED_WORKFLOWS,
        workspace_section=workspace_section,
        workspace_content_template=template_name,
        **context,
    )


def render_command_page(
    *,
    active_module: str,
    active_section: Optional[str] = None,
    workspace_content_template: Optional[str] = None,
    **context,
):
    account_context = get_user_account_context()
    active_group = (
        account_context.get(
            "active_group"
        )
        or {}
    )

    default_context = {
        "shell_identity": get_shell_identity(),
        "account_context": account_context,
        "active_group": active_group,
        "active_group_id": account_context.get(
            "active_group_id"
        ),
        "active_user_role": (
            account_context.get(
                "membership_role"
            )
            or "guest"
        ),
        "active_company_name": (
            account_context.get(
                "organization_name"
            )
            or account_context.get(
                "group_name"
            )
            or ""
        ),
        "group_setup_complete": bool(
            account_context.get(
                "setup_complete"
            )
        ),
        "group_setup_required": bool(
            account_context.get(
                "pending_setup_required"
            )
        ),
    }
    default_context.update(
        context
    )

    if active_module == "documents":
        current_folder_id = str(
            request.args.get("folder_id")
            or ""
        ).strip()
        return_fallback = (
            "/shared"
            if normalize_document_workspace_section(active_section) == "shared"
            else "/"
        )
        requested_return_route = request.args.get("return_to")

        if current_folder_id and not str(requested_return_route or "").strip():
            try:
                referrer = urlsplit(request.referrer or "")
            except ValueError:
                referrer = None

            if referrer and referrer.netloc == request.host:
                requested_return_route = "".join((
                    referrer.path or "/",
                    f"?{referrer.query}" if referrer.query else "",
                    f"#{referrer.fragment}" if referrer.fragment else "",
                ))

        default_context.setdefault(
            "workspace_return_route",
            normalize_document_workspace_return_route(
                requested_return_route,
                fallback=return_fallback,
            ),
        )

        if current_folder_id:
            default_context.setdefault(
                "workspace_window_closeable",
                True,
            )

    if is_workspace_render_request():
        return render_workspace_content(
            active_module=active_module,
            active_section=active_section,
            workspace_content_template=workspace_content_template,
            **default_context,
        )

    return get_compat_browser_content(
        active_module,
        active_section,
        workspace_content_template=workspace_content_template,
        **default_context,
    )


# ============================================================
# RESPONSE CACHE CONTROL
# ============================================================
@app.after_request
def add_no_store_header(response):
    path = str(
        request.path or ""
    )

    if (
        path == "/"
        or path.startswith(
            "/workspace"
        )
        or path.startswith(
            "/api/workspace"
        )
        or path.startswith(
            "/ai"
        )
        or path.startswith(
            "/search"
        )
        or path.startswith(
            "/recent"
        )
        or path.startswith(
            "/shared"
        )
        or path.startswith(
            "/trash"
        )
    ):
        response.headers[
            "Cache-Control"
        ] = "no-store, no-cache, must-revalidate, max-age=0"
        response.headers[
            "Pragma"
        ] = "no-cache"
        response.headers[
            "Expires"
        ] = "0"

    return response


# ============================================================
# BLUEPRINT ROUTES
# ============================================================
app.register_blueprint(
    auth_bp
)
register_all_blueprints(
    app
)

if (
    "solomon_conversations_bp"
    not in app.blueprints
):
    app.register_blueprint(
        solomon_conversations_bp
    )
    logger.info(
        "[BOOT] solomon_conversations_bp explicitly registered"
    )

if "task_api" not in app.blueprints:
    app.register_blueprint(
        task_api
    )
    logger.info(
        "[BOOT] task_api explicitly registered"
    )


# ============================================================
# CORE ROUTES
# ============================================================
@app.route("/")
@login_required
def index():
    return render_command_page(
        active_module="documents",
        active_section="files",
        workspace_content_template=(
            "components/document_workspace.html"
        ),
    )


@app.route("/management")
@login_required
def management():
    return render_command_page(
        active_module="management"
    )


@app.route("/field")
@login_required
def field():
    return render_command_page(
        active_module="field"
    )


@app.route("/quality")
@login_required
def quality():
    return render_command_page(
        active_module="quality"
    )


@app.route("/safety")
@login_required
def safety():
    return render_command_page(
        active_module="safety"
    )


@app.route("/finance")
@login_required
def finance():
    return render_command_page(
        active_module="finance"
    )


@app.route("/comms")
@login_required
def communications():
    return render_command_page(
        active_module="communication"
    )


@app.route("/people")
@login_required
def people():
    return render_command_page(
        active_module="people",
        workspace_content_template=(
            "components/people_workspace.html"
        ),
    )


@app.route(GROUP_SETUP_PATH)
@login_required
def people_group_setup():
    return render_command_page(
        active_module="people",
        active_section="setup",
        workspace_content_template=(
            "components/group_setup_required.html"
        ),
    )


@app.route("/recent")
@login_required
def recent():
    return render_command_page(
        active_module="documents",
        active_section="recent",
        workspace_content_template=(
            "components/document_workspace.html"
        ),
    )


@app.route("/shared")
@login_required
def shared_with_me():
    return render_command_page(
        active_module="documents",
        active_section="shared",
        workspace_content_template=(
            "components/document_workspace.html"
        ),
    )


@app.route("/trash")
@login_required
def trash():
    return render_command_page(
        active_module="documents",
        active_section="trash",
        workspace_content_template=(
            "components/document_workspace.html"
        ),
    )


@app.route("/preconstruction")
@login_required
def preconstruction():
    return render_command_page(
        active_module="preconstruction"
    )


@app.route("/preconstruction/bid-scope-review")
@login_required
def preconstruction_bid_scope_review():
    return render_command_page(
        active_module="preconstruction_review"
    )


@app.route("/search")
@login_required
def search():
    query = normalize_workspace_search_query(
        request.args.get(
            "q",
            "",
        )
    )
    search_type = normalize_workspace_search_type(
        request.args.get(
            "type",
            "all",
        )
    )
    user_id = get_current_user_id()

    workspace_search_response = search_workspace_intelligence(
        user_id=user_id or 0,
        query=query,
        search_type=search_type,
        context="global",
        limit=WORKSPACE_SEARCH_MAX_RESULTS,
        filter_type=request.args.get(
            "filter_type",
            "",
        ),
        people=request.args.get(
            "people",
            "",
        ),
        modified=request.args.get(
            "modified",
            "",
        ),
        source=request.args.get(
            "source",
            "",
        ),
        sort_key=request.args.get(
            "sort",
            "relevance",
        ),
        direction=request.args.get(
            "direction",
            "",
        ),
        folder_placement=request.args.get(
            "folders",
            "top",
        ),
        layout=request.args.get(
            "layout",
            "list",
        ),
    )

    return render_command_page(
        active_module="search",
        active_section="search",
        workspace_content_template=(
            "components/workspace_global_search.html"
        ),
        workspace_search_response=workspace_search_response,
        workspace_search_results=workspace_search_response.get(
            "results",
            [],
        ),
    )


@app.route("/api/workspace/search")
@login_required
def api_workspace_search():
    query = normalize_workspace_search_query(
        request.args.get(
            "q",
            "",
        )
    )
    search_type = normalize_workspace_search_type(
        request.args.get(
            "type",
            "all",
        )
    )
    context = normalize_workspace_search_context(
        request.args.get(
            "context",
            "global",
        )
    )
    limit = normalize_workspace_search_limit(
        request.args.get(
            "limit",
            str(WORKSPACE_SEARCH_MAX_API_RESULTS),
        ),
        default_limit=WORKSPACE_SEARCH_MAX_API_RESULTS,
    )
    user_id = get_current_user_id()

    payload = search_workspace_intelligence(
        user_id=user_id or 0,
        query=query,
        search_type=search_type,
        context=context,
        limit=limit,
        filter_type=request.args.get(
            "filter_type",
            "",
        ),
        people=request.args.get(
            "people",
            "",
        ),
        modified=request.args.get(
            "modified",
            "",
        ),
        source=request.args.get(
            "source",
            "",
        ),
        sort_key=request.args.get(
            "sort",
            "relevance",
        ),
        direction=request.args.get(
            "direction",
            "",
        ),
        folder_placement=request.args.get(
            "folders",
            "top",
        ),
        layout=request.args.get(
            "layout",
            "list",
        ),
        include_listing_controls=False,
    )

    return jsonify(
        payload
    )


# ============================================================
# WORKSPACE DOCUMENT ACTION BRIDGE
# ============================================================
def normalize_workspace_action_kind(
    value: Optional[str],
) -> str:
    clean_value = str(
        value or ""
    ).strip().lower()

    aliases = {
        "open_document": "open",
        "open_reader": "open",
        "reader": "open",
        "focus_document": "focus",
        "focus": "focus",
        "minimize_document": "minimize",
        "minimize": "minimize",
        "close_document": "close",
        "close_reader": "close",
        "details": "details",
    }

    return aliases.get(
        clean_value,
        clean_value,
    )


def normalize_workspace_document_id(
    value: Optional[str],
) -> str:
    return str(
        value or ""
    ).strip()


def normalize_workspace_document_payload(
    payload: Any,
) -> Dict[str, Any]:
    if not isinstance(
        payload,
        dict,
    ):
        return {}

    return payload


def normalize_workspace_document_session_payload(
    value: Any,
) -> Dict[str, Any]:
    if isinstance(
        value,
        dict,
    ):
        return value

    return {}


def build_workspace_action_response(
    *,
    ok: bool,
    action: str,
    document_id: str,
    document_session: Optional[WorkspaceDocumentSession] = None,
    panel_state: Optional[WorkspacePanelState] = None,
    message: str = "",
    status_code: int = 200,
):
    payload = {
        "ok": ok,
        "action": action,
        "document_id": document_id,
        "message": message,
    }

    if document_session:
        payload[
            "document_session"
        ] = document_session.to_dict()

    if panel_state:
        payload[
            "panel_state"
        ] = panel_state.to_dict()

    response = jsonify(
        payload
    )
    response.status_code = status_code
    return response


@app.post("/workspace/action/open-document")
@login_required
def workspace_action_open_document():
    user_id = get_current_user_id()
    payload = normalize_workspace_document_payload(
        request.get_json(
            silent=True
        )
    )

    document_id = normalize_workspace_document_id(
        payload.get(
            "document_id"
        )
        or payload.get(
            "documentId"
        )
        or payload.get(
            "file_id"
        )
        or payload.get(
            "fileId"
        )
        or payload.get(
            "random_name"
        )
        or payload.get(
            "randomName"
        )
    )

    back_route = normalize_workspace_document_id(
        payload.get(
            "back_route"
        )
        or payload.get(
            "backRoute"
        )
    )

    if not user_id:
        return build_workspace_action_response(
            ok=False,
            action="open",
            document_id=document_id,
            message="Authentication required.",
            status_code=401,
        )

    if not document_id:
        return build_workspace_action_response(
            ok=False,
            action="open",
            document_id="",
            message="No document was selected.",
            status_code=400,
        )

    db_session = SessionLocal()

    try:
        file_record = resolve_authorized_file_registry_entry(
            db_session,
            user_id=user_id,
            opaque_id=document_id,
            required_action=READ_ACTION,
        )

        if not file_record:
            return build_workspace_action_response(
                ok=False,
                action="open",
                document_id=document_id,
                message="You do not have permission to open this document.",
                status_code=403,
            )

        document_session = (
            WorkspaceDocumentSession.from_file_registry(
                file_record,
                action="open",
                back_route=back_route,
            )
        )
        panel_state = WorkspacePanelState.from_document_session(
            document_session,
            action="open",
        )

        response = build_workspace_action_response(
            ok=True,
            action="open",
            document_id=document_id,
            document_session=document_session,
            panel_state=panel_state,
            message="Document ready.",
        )
        response.headers[
            "X-Solomon-Workspace-Action"
        ] = "open"
        return response
    except Exception as exc:
        logger.exception(
            "[workspace.action.open.failed] "
            "request_id=%s user_id=%s document_id=%s error=%s",
            get_request_id(),
            user_id,
            document_id,
            exc,
        )
        return build_workspace_action_response(
            ok=False,
            action="open",
            document_id=document_id,
            message="Document could not be opened.",
            status_code=500,
        )
    finally:
        db_session.close()


@app.post("/workspace/action/focus-document")
@login_required
def workspace_action_focus_document():
    payload = normalize_workspace_document_payload(
        request.get_json(
            silent=True
        )
    )
    document_id = normalize_workspace_document_id(
        payload.get(
            "document_id"
        )
        or payload.get(
            "documentId"
        )
        or payload.get(
            "file_id"
        )
        or payload.get(
            "fileId"
        )
        or payload.get(
            "random_name"
        )
        or payload.get(
            "randomName"
        )
    )

    panel_state = WorkspacePanelState(
        active_document_id=document_id,
        reader_state="active",
        panel_mode="reader",
        action="focus",
        status="focused",
    )

    return build_workspace_action_response(
        ok=True,
        action="focus",
        document_id=document_id,
        panel_state=panel_state,
        message="Document focused.",
    )


@app.post("/workspace/action/minimize-document")
@login_required
def workspace_action_minimize_document():
    payload = normalize_workspace_document_payload(
        request.get_json(
            silent=True
        )
    )
    document_id = normalize_workspace_document_id(
        payload.get(
            "document_id"
        )
        or payload.get(
            "documentId"
        )
        or payload.get(
            "file_id"
        )
        or payload.get(
            "fileId"
        )
        or payload.get(
            "random_name"
        )
        or payload.get(
            "randomName"
        )
    )

    document_session_payload = normalize_workspace_document_session_payload(
        payload.get(
            "document_session"
        )
        or payload.get(
            "documentSession"
        )
    )
    document_session = build_workspace_document_session_from_dict(
        document_session_payload
    )

    document_session = document_session.with_state(
        viewer_state="minimized"
    )
    panel_state = WorkspacePanelState.from_document_session(
        document_session,
        action="minimize",
    )

    return build_workspace_action_response(
        ok=True,
        action="minimize",
        document_id=document_id,
        document_session=document_session,
        panel_state=panel_state,
        message="Document minimized.",
    )


@app.post("/workspace/action/close-document")
@login_required
def workspace_action_close_document():
    payload = normalize_workspace_document_payload(
        request.get_json(
            silent=True
        )
    )
    document_id = normalize_workspace_document_id(
        payload.get(
            "document_id"
        )
        or payload.get(
            "documentId"
        )
        or payload.get(
            "file_id"
        )
        or payload.get(
            "fileId"
        )
        or payload.get(
            "random_name"
        )
        or payload.get(
            "randomName"
        )
    )

    panel_state = WorkspacePanelState(
        active_document_id=document_id,
        reader_state="idle",
        panel_mode="list",
        action="close",
        status="closed",
    )

    return build_workspace_action_response(
        ok=True,
        action="close",
        document_id=document_id,
        panel_state=panel_state,
        message="Document closed.",
    )


# ============================================================
# WORKSPACE ACTION COMPATIBILITY ROUTE
# ============================================================
@app.post("/api/workspace/open")
@login_required
def api_workspace_open():
    return workspace_action_open_document()


# ============================================================
# WORKSPACE DOCUMENT THUMBNAIL ROUTES
# ============================================================
@app.route("/workspace/document/<path:opaque_id>/thumbnail")
@login_required
def workspace_document_thumbnail(opaque_id: str):
    request_id = get_request_id()
    user_id = get_current_user_id()

    if not user_id:
        return (
            "Authentication required.",
            401,
        )

    clean_opaque_id = normalize_workspace_document_id(
        opaque_id
    )

    if not clean_opaque_id:
        return (
            "Document not found.",
            404,
        )

    try:
        file_payload = resolve_authorized_file_registry_entry(
            user_id,
            clean_opaque_id,
            request_id=request_id,
            action=READ_ACTION,
            allow_trashed_owner_read=True,
        )

        if not file_payload:
            return (
                "Document not found.",
                404,
            )

        thumbnail_info = build_workspace_document_thumbnail_response(
            file_payload
        )

        if not thumbnail_info:
            return (
                "Preview unavailable.",
                404,
            )

        return send_file(
            thumbnail_info["stream"],
            mimetype=thumbnail_info["mimetype"],
            download_name=thumbnail_info["download_name"],
            max_age=300,
        )
    except Exception as exc:
        logger.exception(
            "[workspace.thumbnail.failed] "
            "request_id=%s user_id=%s document_id=%s error=%s",
            request_id,
            user_id,
            clean_opaque_id,
            exc,
        )
        return (
            "Preview unavailable.",
            500,
        )


def build_workspace_document_thumbnail_response(
    file_payload: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    if not isinstance(
        file_payload,
        dict,
    ):
        return None

    original_name = str(
        file_payload.get(
            "original_name",
            "",
        )
        or ""
    ).strip()
    random_name = str(
        file_payload.get(
            "random_name",
            "",
        )
        or file_payload.get(
            "document_id",
            "",
        )
        or ""
    ).strip()
    extension = str(
        file_payload.get(
            "extension",
            "",
        )
        or ""
    ).strip().lower().lstrip(".")

    if not extension and "." in original_name:
        extension = original_name.rsplit(
            ".",
            1,
        )[-1].strip().lower()

    storage_path = str(
        file_payload.get(
            "path",
            "",
        )
        or file_payload.get(
            "file_path",
            "",
        )
        or ""
    ).strip()

    if not storage_path or not os.path.isfile(
        storage_path
    ):
        return None

    image_mimetypes = {
        "png": "image/png",
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "gif": "image/gif",
        "webp": "image/webp",
        "bmp": "image/bmp",
        "tif": "image/tiff",
        "tiff": "image/tiff",
    }

    if extension in image_mimetypes:
        return {
            "stream": storage_path,
            "mimetype": image_mimetypes[extension],
            "download_name": (
                original_name
                or random_name
                or "preview"
            ),
        }

    if extension != "pdf":
        return None

    try:
        import pypdfium2 as pdfium

        pdf = pdfium.PdfDocument(
            storage_path
        )
        try:
            page = pdf[0]
            try:
                bitmap = page.render(
                    scale=0.25
                )
                pil_image = bitmap.to_pil()
            finally:
                page.close()
        finally:
            pdf.close()

        output = BytesIO()
        pil_image.save(
            output,
            format="PNG",
        )
        output.seek(
            0
        )

        return {
            "stream": output,
            "mimetype": "image/png",
            "download_name": (
                f"{random_name or 'preview'}.png"
            ),
        }
    except Exception as exc:
        logger.debug(
            "[workspace.thumbnail.unavailable] "
            "request_id=%s file_id=%s error=%s",
            get_request_id(),
            (
                file_payload.get("file_id")
                or file_payload.get("document_id")
                or random_name
                or "unknown"
            ),
            exc,
        )
        return None


# ============================================================
# LEGACY / MAPPED ROUTES
# ============================================================
@app.route("/history")
@login_required
def history():
    return redirect(
        "/ai/history"
    )


@app.route("/settings")
@login_required
def settings_page():
    return render_command_page(
        active_module="documents"
    )


@app.route("/dashboard")
@login_required
def dashboard():
    return redirect(
        "/"
    )


@app.route("/documents")
@login_required
def documents():
    return redirect(
        "/"
    )


@app.route("/docs")
@login_required
def docs():
    return redirect(
        "/"
    )


@app.route("/workspace")
@login_required
def workspace():
    return redirect(
        "/"
    )


@app.route("/uploads")
@login_required
def uploads():
    return redirect(
        "/"
    )


@app.route("/tasks")
@login_required
def tasks():
    return redirect(
        "/preconstruction"
    )


# ============================================================
# PRECONSTRUCTION / TASK ROUTES
# ============================================================
@app.route("/run", methods=["POST"])
@login_required
def run_task():
    selected_workflow = request.form.get(
        "workflow",
        "pre_award_risk_review",
    )

    uploaded_file = request.files.get(
        "file"
    )
    pasted_text = request.form.get(
        "pasted_text",
        "",
    )

    if (
        not uploaded_file
        and not pasted_text.strip()
    ):
        return render_command_page(
            active_module="preconstruction_review",
            error="Upload a file or paste text."
        )

    return task_api.run_legacy_task(
        selected_workflow=selected_workflow,
        uploaded_file=uploaded_file,
        pasted_text=pasted_text,
    )


# ============================================================
# DIRECT ROUTES FROM TASK API
# ============================================================
@app.route("/upload", methods=["POST"])
@login_required
def upload_task_alias():
    return task_api.run_task_upload()


@app.route("/history/json")
@login_required
def history_json_alias():
    return task_api.history_json()


@app.route("/history/<int:task_id>")
@login_required
def history_detail_alias(task_id: int):
    return task_api.history_detail(
        task_id
    )


@app.route("/download/<path:filename>")
@login_required
def download_alias(filename):
    return task_api.download_file(
        filename
    )


@app.route("/delete/<int:task_id>", methods=["POST"])
@login_required
def delete_task_alias(task_id: int):
    return task_api.delete_task(
        task_id
    )


# ============================================================
# APPLICATION LIFECYCLE
# ============================================================
def ensure_direct_generation_warmup():
    """Start the direct runtime warm-up before serving requests."""

    warm_direct_runtime_profile_worker(
        call_site=_DOCINTEL_SUMMARY_WARMUP_CALL_SITE,
        max_new_tokens=_DOCINTEL_SUMMARY_WARMUP_MAX_NEW_TOKENS,
        target_input_tokens=_DOCINTEL_SUMMARY_WARMUP_TARGET_INPUT_TOKENS,
        runtime_profile=_DOCINTEL_SUMMARY_WARMUP_RUNTIME_PROFILE,
        warmup_prompt=_DOCINTEL_SUMMARY_WARMUP_SOURCE_SEED,
    )


def _get_effective_debug_enabled() -> bool:
    """Require an explicit opt-in before running the Flask dev server.

    Legacy settings may enable DEBUG by default. Release startup uses the
    existing Waitress server unless the operator knowingly opts in to
    the local development server for troubleshooting.
    """
    return (
        _startup_truthy_setting(settings.DEBUG)
        and _startup_truthy_setting(
            os.environ.get("SOLOMON_ALLOW_DEV_SERVER", "")
        )
    )


def _get_effective_waitress_threads() -> int:
    default_threads = max(
        1,
        int(
            settings.WAITRESS_THREADS
            or 8
        ),
    )

    configured_threads = int(
        settings.WAITRESS_THREADS
        or default_threads
    )

    return max(
        1,
        configured_threads,
    )


def _get_effective_waitress_ident() -> str:
    return str(
        settings.WAITRESS_IDENT
        or "Solomon"
    )


def _get_effective_waitress_connection_limit() -> int:
    return int(
        settings.WAITRESS_CONNECTION_LIMIT
        or 100
    )


def _get_effective_waitress_channel_timeout() -> int:
    return int(
        settings.WAITRESS_CHANNEL_TIMEOUT
        or 30
    )


def _get_effective_waitress_cleanup_interval() -> int:
    return int(
        settings.WAITRESS_CLEANUP_INTERVAL
        or 30
    )


def _get_effective_waitress_outbuf_overflow() -> int:
    return int(
        settings.WAITRESS_OUTBUF_OVERFLOW
        or 1048576
    )


def _get_effective_waitress_inbuf_overflow() -> int:
    return int(
        settings.WAITRESS_INBUF_OVERFLOW
        or 524288
    )


def _get_effective_waitress_url_scheme() -> str:
    return str(
        settings.WAITRESS_URL_SCHEME
        or "http"
    )


def _get_effective_waitress_clear_untrusted_proxy_headers() -> bool:
    return _startup_truthy_setting(
        settings.WAITRESS_CLEAR_UNTRUSTED_PROXY_HEADERS
    )


def _get_effective_waitress_max_request_body_bytes() -> int:
    return int(
        settings.WAITRESS_MAX_REQUEST_BODY_BYTES
        or 1073741824
    )


def _get_effective_llm_warmup_enabled() -> bool:
    return (
        bool(
            settings.LLM_WARMUP_ENABLED
        )
        and bool(
            settings.LLM_ENABLED
        )
    )


def _get_effective_direct_generation_warmup_enabled() -> bool:
    return (
        _get_effective_llm_warmup_enabled()
        and bool(
            settings.DIRECT_GENERATION_WARMUP_ENABLED
        )
    )


def _get_effective_direct_generation_warmup_target() -> str:
    return str(
        settings.DIRECT_GENERATION_WARMUP_TARGET
        or ""
    ).strip().lower()


def _should_warm_direct_generation_runtime() -> bool:
    warmup_target = _get_effective_direct_generation_warmup_target()

    if not _get_effective_direct_generation_warmup_enabled():
        return False

    return warmup_target in {
        "all",
        "docintel",
        _DOCINTEL_SUMMARY_WARMUP_CALL_SITE,
    }


def _warm_direct_generation_runtime() -> None:
    logger.info(
        "[BOOT][DOCINTEL_SUMMARY_WARMUP] "
        "call_site=%s max_new_tokens=%s target_input_tokens=%s",
        _DOCINTEL_SUMMARY_WARMUP_CALL_SITE,
        _DOCINTEL_SUMMARY_WARMUP_MAX_NEW_TOKENS,
        _DOCINTEL_SUMMARY_WARMUP_TARGET_INPUT_TOKENS,
    )

    warm_direct_model_worker()

    ensure_direct_generation_warmup()


def _serve_with_waitress(
    bind_host: str,
    bind_port: int,
) -> None:
    from waitress import serve

    serve(
        app,
        host=bind_host,
        port=bind_port,
        threads=_get_effective_waitress_threads(),
        connection_limit=_get_effective_waitress_connection_limit(),
        channel_timeout=_get_effective_waitress_channel_timeout(),
        cleanup_interval=_get_effective_waitress_cleanup_interval(),
        outbuf_overflow=_get_effective_waitress_outbuf_overflow(),
        inbuf_overflow=_get_effective_waitress_inbuf_overflow(),
        url_scheme=_get_effective_waitress_url_scheme(),
        clear_untrusted_proxy_headers=(
            _get_effective_waitress_clear_untrusted_proxy_headers()
        ),
        max_request_body_size=(
            settings.WAITRESS_MAX_REQUEST_BODY_BYTES
        ),
        ident="Solomon",
    )


if __name__ == "__main__":
    bind_host = str(
        settings.WEB_BIND_HOST
        or "127.0.0.1"
    ).strip()

    bind_port = int(
        settings.WEB_BIND_PORT
        or settings.PORT
        or 8080
    )

    debug_enabled = (
        _get_effective_debug_enabled()
    )

    if bool(settings.SIS_ENABLED):
        logger.info(
            "[BOOT][SIS_EXTERNAL_RUNTIME] "
            "endpoint=%s local_llm_warmup=skipped",
            settings.SIS_BASE_URL,
        )
    elif _should_warm_direct_generation_runtime():
        _warm_direct_generation_runtime()
    else:
        logger.info(
            "[BOOT][LLM_WARMUP_DEFERRED] "
            "reason=disabled_by_configuration"
        )

    from solomon_core.intelligence_service.intelligence_service_client import (
        start_intelligence_service_health_monitor,
        stop_intelligence_service_health_monitor,
    )
    from solomon_intelligence_worker import (
        start_intelligence_spool_worker,
        stop_intelligence_spool_worker,
    )

    sis_health_monitor = (
        start_intelligence_service_health_monitor()
    )
    intelligence_spool_worker = (
        start_intelligence_spool_worker(app)
    )

    try:
        if debug_enabled:
            logger.warning(
                "[BOOT][DEVELOPMENT_SERVER] "
                "host=%s port=%s",
                bind_host,
                bind_port,
            )

            app.run(
                host=bind_host,
                port=bind_port,
                debug=True,
                use_reloader=False,
            )
        else:
            # The WSGI release path must not inherit Flask debug behavior.
            app.debug = False
            _serve_with_waitress(
                bind_host,
                bind_port,
            )
    finally:
        stop_intelligence_spool_worker(
            app=app,
            worker=intelligence_spool_worker,
        )
        stop_intelligence_service_health_monitor(
            sis_health_monitor
        )

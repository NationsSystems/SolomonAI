# -------------------------------------------------------------------
# FILE: auth_utils.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Authentication + role enforcement helpers
# -------------------------------------------------------------------

from functools import wraps

from flask import jsonify, redirect, request, session, url_for

from config import settings
from solomon_core.db import SessionLocal
from solomon_core.models import User


# -----------------------------------------------------------
# Internal: controlled test override gate
# -----------------------------------------------------------
def _is_test_admin_override_allowed():
    """
    Test admin override is disabled by default.

    It may only be used when explicitly enabled in settings. This prevents
    a stale session flag from bypassing authentication in normal V3 runtime.
    """

    return (
        bool(getattr(settings, "TEST_ADMIN_OVERRIDE_ENABLED", False))
        and session.get("test_admin_override") is True
    )


# -----------------------------------------------------------
# Helper: load current user
# -----------------------------------------------------------
def current_user():
    if _is_test_admin_override_allowed():
        class _TestAdmin:
            id = 999999
            username = "test_admin"
            role = "admin"
            email = "test@example.com"
            must_change_password = 0

        return _TestAdmin()

    uid = session.get("user_id")
    if not uid:
        return None

    db = SessionLocal()
    try:
        return db.query(User).filter(User.id == uid).first()
    finally:
        db.close()


# -----------------------------------------------------------
# Internal: login destination preservation
# -----------------------------------------------------------
def _safe_current_request_path() -> str:
    path = str(
        request.path
        or "/"
    ).strip()

    if not path.startswith("/"):
        return "/"

    if (
        path.startswith("/auth/login")
        or path.startswith("/auth/register")
        or path.startswith("/auth/logout")
        or path.startswith("/static/")
    ):
        return "/"

    query_string = (
        request.query_string.decode(
            "utf-8",
            errors="ignore",
        )
        if request.query_string
        else ""
    ).strip()

    if query_string:
        return f"{path}?{query_string}"

    return path


def _remember_post_login_redirect() -> str:
    redirect_target = _safe_current_request_path()

    if redirect_target != "/":
        session[
            "post_login_redirect"
        ] = redirect_target
        session.modified = True

    return redirect_target


# -----------------------------------------------------------
# Internal: API/browser auth failure response
# -----------------------------------------------------------
def _auth_required_response():
    if request.path.startswith("/api/") or request.path.startswith("/workflow/"):
        return jsonify({
            "ok": False,
            "error": "Authentication required",
            "error_code": "AUTH_REQUIRED",
        }), 401

    redirect_target = _remember_post_login_redirect()

    return redirect(
        url_for(
            "auth.login_page",
            next=redirect_target,
        )
    )


# -----------------------------------------------------------
# Internal: forced password change guard
# -----------------------------------------------------------
def _current_authentication_method() -> str:
    """Return the session authentication method with legacy-safe behavior."""

    authentication_context = session.get("authentication_context")
    if isinstance(authentication_context, dict):
        method = str(
            authentication_context.get("method")
            or ""
        ).strip().lower()
        if method:
            return method

    # Sessions created before the provider-capable contract were password-only.
    return "password"


def _enforce_password_change(user):
    if not hasattr(user, "must_change_password"):
        return None

    if not user.must_change_password:
        return None

    # must_change_password governs a Solomon password credential. An identity
    # authenticated by a verified external provider must not be blocked merely
    # because an optional local password is absent, temporary, or stale.
    if _current_authentication_method() != "password":
        return None

    path = request.path or ""

    if path.startswith("/auth/login") or path.startswith("/auth/register"):
        session.clear()
        return None

    if (
        path.startswith("/auth/change-password")
        or path.startswith("/auth/logout")
        or path.startswith("/static/")
    ):
        return None

    if path.startswith("/api/") or path.startswith("/workflow/"):
        return jsonify({
            "ok": False,
            "error": "Password change required",
            "error_code": "PASSWORD_CHANGE_REQUIRED",
        }), 403

    session[
        "post_login_redirect"
    ] = _safe_current_request_path()
    session.modified = True

    return redirect(url_for("auth.change_password_page"))


# -----------------------------------------------------------
# Decorator: login_required
# -----------------------------------------------------------
def login_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if _is_test_admin_override_allowed():
            return func(*args, **kwargs)

        if "user_id" not in session:
            return _auth_required_response()

        user = current_user()

        if not user:
            session.clear()
            return _auth_required_response()

        guard = _enforce_password_change(user)
        if guard:
            return guard

        return func(*args, **kwargs)

    return wrapper


# -----------------------------------------------------------
# Decorator: role_required
# -----------------------------------------------------------
def role_required(required_role):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            if _is_test_admin_override_allowed():
                return func(*args, **kwargs)

            user = current_user()

            if not user:
                session.clear()
                return _auth_required_response()

            guard = _enforce_password_change(user)
            if guard:
                return guard

            user_role = (user.role or "").lower()

            if user_role != required_role.lower():
                return jsonify({
                    "ok": False,
                    "error": "Access denied: insufficient permissions",
                    "required_role": required_role,
                    "user_role": user_role,
                }), 403

            return func(*args, **kwargs)

        return wrapper

    return decorator


# -----------------------------------------------------------
# Alias: admin_required
# -----------------------------------------------------------
def admin_required(func):
    return role_required("admin")(func)


# -----------------------------------------------------------
# secure_debug_required
# -----------------------------------------------------------
def secure_debug_required(func):
    if settings.DEBUG_ROUTES_REQUIRE_ADMIN:
        return admin_required(func)

    @wraps(func)
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


__all__ = [
    "login_required",
    "role_required",
    "admin_required",
    "secure_debug_required",
    "current_user",
]
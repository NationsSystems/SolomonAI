# ==========================================================================
# FILE: admin_bp.py
# DIRECTORY: SolomonV3/solomon_core/routes/
# ==========================================================================

from datetime import datetime
import secrets
import string

from flask import Blueprint, current_app, jsonify, render_template, request, session
from werkzeug.security import generate_password_hash

from solomon_core.auth_utils import admin_required, login_required
from solomon_core.db import SessionLocal
from solomon_core.models import User

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ==========================================================================
# HELPERS
# ==========================================================================

def _generate_temp_password(length=14):
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def _safe_count(db, model, *filters):
    query = db.query(model)

    for condition in filters:
        query = query.filter(condition)

    return query.count()


def _current_admin_identity():
    session_user = session.get("user")

    if isinstance(session_user, dict):
        return (
            session_user.get("email")
            or session_user.get("username")
            or "Admin"
        )

    return session.get("email") or session.get("username") or "Admin"


def _build_admin_dashboard():
    db = SessionLocal()

    try:
        total_users = _safe_count(db, User)
        active_users = _safe_count(db, User, User.is_active == True)
        admin_users = _safe_count(db, User, User.role == "admin")
        password_change_required = _safe_count(
            db,
            User,
            User.must_change_password == True,
        )

        dashboard = {
            "product_status": {
                "application": "Ready",
                "database": "Ready",
                "authentication": "Ready",
                "admin_access": "Ready",
            },
            "workflow_status": {
                "bei_analysis": "Available",
                "pdf_export": "Available",
                "input": "Available",
                "report_renderer": "Available",
            },
            "users": {
                "total": total_users,
                "active": active_users,
                "admins": admin_users,
                "password_change_required": password_change_required,
            },
            "errors": {
                "recent_count": 0,
                "last_error_at": None,
                "last_error_type": None,
            },
            "features": {
                "review_history": "Available",
            },
        }

        return dashboard

    except Exception:
        current_app.logger.exception("Admin dashboard data build failed")

        return {
            "product_status": {
                "application": "Ready",
                "database": "Unavailable",
                "authentication": "Ready",
                "admin_access": "Ready",
            },
            "workflow_status": {
                "bei_analysis": "Unknown",
                "pdf_export": "Unknown",
                "input": "Unknown",
                "report_renderer": "Unknown",
            },
            "users": {
                "total": 0,
                "active": 0,
                "admins": 0,
                "password_change_required": 0,
            },
            "errors": {
                "recent_count": 0,
                "last_error_at": None,
                "last_error_type": "Dashboard data unavailable",
            },
            "features": {
                "review_history": "Unknown",
            },
        }

    finally:
        db.close()


# ==========================================================================
# DASHBOARD
# ==========================================================================

@admin_bp.route("/", methods=["GET"])
@login_required
@admin_required
def admin_dashboard():
    dashboard = _build_admin_dashboard()

    return render_template(
        "admin.html",
        user=_current_admin_identity(),
        dashboard=dashboard,
    )


# ==========================================================================
# ADMIN PAGES
# ==========================================================================

@admin_bp.route("/skills", methods=["GET"])
@login_required
@admin_required
def admin_skills_page():
    return render_template("admin_skills.html")


@admin_bp.route("/users", methods=["GET"])
@login_required
@admin_required
def admin_users_page():
    return render_template("admin_users.html")


# ==========================================================================
# USER DATA
# ==========================================================================

@admin_bp.route("/users/data", methods=["GET"])
@login_required
@admin_required
def admin_users_data():
    db = SessionLocal()

    try:
        users = db.query(User).order_by(User.created_at.asc()).all()

        return jsonify({
            "ok": True,
            "users": [
                {
                    "id": user.id,
                    "email": user.email,
                    "display_name": user.email,
                    "role": user.role,
                    "is_active": user.is_active,
                    "created_at": (
                        user.created_at.isoformat()
                        if getattr(user, "created_at", None)
                        else None
                    ),
                    "last_login_at": (
                        user.last_login_at.isoformat()
                        if getattr(user, "last_login_at", None)
                        else None
                    ),
                }
                for user in users
            ],
        })

    finally:
        db.close()


# ==========================================================================
# USER ACTIONS
# ==========================================================================

@admin_bp.route("/users/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def toggle_admin_role(user_id):
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return jsonify({"ok": False, "error": "User not found"}), 404

        user.role = "admin" if user.role != "admin" else "user"
        db.commit()

        return jsonify({"ok": True, "new_role": user.role})

    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/toggle-active", methods=["POST"])
@login_required
@admin_required
def toggle_user_active(user_id):
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return jsonify({"ok": False, "error": "User not found"}), 404

        user.is_active = not user.is_active
        db.commit()

        return jsonify({"ok": True, "is_active": user.is_active})

    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/reset-password", methods=["POST"])
@login_required
@admin_required
def reset_user_password(user_id):
    db = SessionLocal()

    try:
        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return jsonify({"ok": False, "error": "User not found"}), 404

        temp_password = _generate_temp_password()

        user.password_hash = generate_password_hash(temp_password)
        user.must_change_password = True
        user.temp_password_issued_at = datetime.utcnow()

        db.commit()

        return jsonify({
            "ok": True,
            "temporary_password": temp_password,
            "warning": "This password will not be shown again.",
        })

    finally:
        db.close()


@admin_bp.route("/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def delete_user(user_id):
    db = SessionLocal()

    try:
        current_admin_id = session.get("user_id")

        if current_admin_id == user_id:
            return jsonify({
                "ok": False,
                "error": "You cannot delete your own account.",
            }), 400

        user = db.query(User).filter(User.id == user_id).first()

        if not user:
            return jsonify({"ok": False, "error": "User not found"}), 404

        if user.role == "admin":
            admin_count = db.query(User).filter(User.role == "admin").count()

            if admin_count <= 1:
                return jsonify({
                    "ok": False,
                    "error": "Cannot delete the last remaining admin.",
                }), 400

        db.delete(user)
        db.commit()

        return jsonify({"ok": True, "deleted_user_id": user_id})

    finally:
        db.close()


# ==========================================================================
# ROUTE REGISTRY
# ==========================================================================

@admin_bp.route("/routes", methods=["GET"])
@login_required
@admin_required
def list_routes():
    route_data = []

    for rule in current_app.url_map.iter_rules():
        methods = ",".join(sorted(rule.methods - {"HEAD", "OPTIONS"}))
        route_data.append({
            "endpoint": rule.endpoint,
            "url": str(rule),
            "methods": methods,
            "blueprint": (
                rule.endpoint.split(".")[0]
                if "." in rule.endpoint
                else "global"
            ),
        })

    route_data.sort(key=lambda item: item["url"])

    wants_json = (
        request.accept_mimetypes.best == "application/json"
        or request.args.get("format") == "json"
    )

    if wants_json:
        return jsonify({
            "count": len(route_data),
            "routes": route_data,
        }), 200

    return render_template(
        "routes.html",
        routes=route_data,
        count=len(route_data),
    )
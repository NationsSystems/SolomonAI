# ==========================================================================
# FILE: history_bp.py
# DIRECTORY: SolomonV3/solomon_core/routes/
# ==========================================================================

from flask import Blueprint, abort, jsonify, redirect, render_template, session, url_for

from solomon_core.auth_utils import login_required
from solomon_core.db import SessionLocal
from solomon_core.models import BidReviewRecord

history_bp = Blueprint("history_bp", __name__)


# ==========================================================================
# HELPERS
# ==========================================================================

def _current_user_id():
    user_id = session.get("user_id")

    if not user_id:
        return None

    try:
        return int(user_id)
    except (TypeError, ValueError):
        return None


def _get_user_review(db, review_id, user_id):
    return (
        db.query(BidReviewRecord)
        .filter(
            BidReviewRecord.id == review_id,
            BidReviewRecord.user_id == user_id,
            BidReviewRecord.deleted_at.is_(None),
        )
        .first()
    )


# ==========================================================================
# HISTORY ROUTES
# ==========================================================================

@history_bp.route("/history", methods=["GET"])
@login_required
def history():
    user_id = _current_user_id()

    if not user_id:
        return redirect(url_for("auth.login"))

    db = SessionLocal()

    try:
        reviews = (
            db.query(BidReviewRecord)
            .filter(
                BidReviewRecord.user_id == user_id,
                BidReviewRecord.deleted_at.is_(None),
            )
            .order_by(BidReviewRecord.created_at.desc())
            .all()
        )

        return render_template(
            "history.html",
            reviews=reviews,
        )

    finally:
        db.close()


@history_bp.route("/history/<int:review_id>", methods=["GET"])
@login_required
def history_detail(review_id):
    user_id = _current_user_id()

    if not user_id:
        return redirect(url_for("auth.login"))

    db = SessionLocal()

    try:
        review = _get_user_review(db, review_id, user_id)

        if not review:
            abort(404)

        return render_template(
            "history_detail.html",
            review=review,
        )

    finally:
        db.close()


@history_bp.route("/history/<int:review_id>/delete", methods=["POST"])
@login_required
def delete_history_review(review_id):
    user_id = _current_user_id()

    if not user_id:
        return jsonify({
            "ok": False,
            "error": "Authentication required.",
        }), 401

    db = SessionLocal()

    try:
        review = _get_user_review(db, review_id, user_id)

        if not review:
            return jsonify({
                "ok": False,
                "error": "Review not found.",
            }), 404

        from datetime import datetime

        review.deleted_at = datetime.utcnow()
        db.commit()

        return jsonify({
            "ok": True,
            "deleted_review_id": review_id,
        })

    finally:
        db.close()
# solomon_core/routes/task_api_support.py
# -------------------------------------------------------------
# TASK EXECUTION API — SUPPORT UTILITIES
# -------------------------------------------------------------

from flask import jsonify, session
import uuid
import threading
import queue
import os
import ipaddress
import re
import traceback

from solomon_core.db import SessionLocal
from solomon_core.models import User
from solomon_core.logger import get_logger

logger = get_logger("task_api_support")


# -------------------------------------------------------------
# Timeout Policy
# -------------------------------------------------------------

# BEI review can include OCR + local LLM report presentation.
# Keep this above the LLM executor timeout so the API wrapper does
# not kill the request before the LLM returns/fails.
ORCHESTRATOR_TIMEOUT_SECONDS = 75


# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def _err(message, code=400):
    return jsonify({"status": "error", "ok": False, "error": message}), code


def _get_or_create_conversation_id() -> str:
    cid = session.get("conversation_id")
    if not cid:
        cid = str(uuid.uuid4())
        session["conversation_id"] = cid
    return cid


def _effective_orchestrator_timeout(timeout_seconds=None) -> int:
    """
    Enforce a safe minimum request budget.

    Some callers still pass the older 30-second timeout. That is too short
    for OCR + governed BEI + local LLM presentation, so this helper raises
    the effective budget without requiring every caller to be updated at once.
    """
    try:
        requested = int(timeout_seconds or ORCHESTRATOR_TIMEOUT_SECONDS)
    except Exception:
        requested = ORCHESTRATOR_TIMEOUT_SECONDS

    return max(requested, ORCHESTRATOR_TIMEOUT_SECONDS)


def _run_orchestrator_with_timeout(fn, kwargs, timeout_seconds=ORCHESTRATOR_TIMEOUT_SECONDS):
    q = queue.Queue()
    effective_timeout = _effective_orchestrator_timeout(timeout_seconds)

    def _target():
        try:
            result = fn(**kwargs)
            q.put(("ok", result))

        except Exception as e:
            # --------------------------------------------------
            # CRITICAL: expose real traceback for debugging
            # --------------------------------------------------
            logger.error("[ORCHESTRATOR_THREAD_EXCEPTION]")
            logger.error(traceback.format_exc())

            q.put(("err", e))

    t = threading.Thread(target=_target, daemon=True)
    t.start()

    try:
        status, payload = q.get(timeout=effective_timeout)

    except queue.Empty:
        logger.error("[ORCHESTRATOR_TIMEOUT] exceeded %s seconds", effective_timeout)
        return "timeout", None

    return status, payload


# -------------------------------------------------------------
# Human Authority (selected_document normalization)
# -------------------------------------------------------------

def _normalize_selected_document(selected_document: str | None, docs: list[dict]) -> str | None:
    if not selected_document:
        return None

    s = str(selected_document).strip()
    if not s:
        return None

    if s.isdigit():
        n = int(s)
        if 1 <= n <= len(docs):
            return docs[n - 1].get("document_id")
        return None

    for d in docs:
        if d.get("document_id") == s:
            return d.get("document_id")

    for d in docs:
        if (d.get("original_name") or "") == s:
            return d.get("document_id")

    return None


# -------------------------------------------------------------
# External State Classification
# -------------------------------------------------------------

def _classify_external_state(task_text: str) -> str:
    t = task_text.lower()
    for m in ("weather", "temperature", "forecast"):
        if m in t:
            return "AMBIENT_PUBLIC"
    return "NON_AMBIENT"


def _parse_explicit_location_anchor(text: str) -> dict | None:
    m = re.match(
        r"^\s*i am located in\s+([^,]+)(?:,\s*([^,]+))?(?:,\s*([^\.]+))?\.",
        text.strip(),
        re.IGNORECASE,
    )
    if not m:
        return None

    city, region, country = m.groups()
    return {
        k: v.strip()
        for k, v in {
            "city": city,
            "region": region,
            "country": country,
            "authority": "user_declared",
        }.items()
        if v
    }


def _user_supplied_location_constraint(text: str) -> bool:
    if not text:
        return False

    t = text.lower()
    for p in (" in ", " at ", " near ", " for "):
        if p in t:
            return True

    return False


def _is_internal_ip(ip: str | None) -> bool:
    if not ip:
        return True
    try:
        ip_obj = ipaddress.ip_address(ip)
        return (
            ip_obj.is_private
            or ip_obj.is_loopback
            or ip_obj.is_reserved
            or ip_obj.is_link_local
        )
    except Exception:
        return True


# -------------------------------------------------------------
# Network Context
# -------------------------------------------------------------

def _read_user_network_context(user_id: int) -> dict | None:
    db = SessionLocal()
    try:
        user = db.get(User, user_id)
        if not user:
            return None

        ctx = {
            "ip": user.last_login_ip,
            "country": user.last_login_ip_country,
            "region": user.last_login_ip_region,
            "city": user.last_login_ip_city,
        }

        ctx = {k: v for k, v in ctx.items() if v}

        if not ctx or _is_internal_ip(ctx.get("ip")):
            return None

        ctx["authority"] = "user_network_signal"
        return ctx

    finally:
        db.close()
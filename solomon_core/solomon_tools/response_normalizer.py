# solomon_core/solomon_tools/response_normalizer.py — PACKET-AWARE FORMATTER
# ---------------------------------------------------------------------------
# ROLE:
#   • Format outbound responses ONLY
#   • Read PacketHeader (read-only)
#   • NEVER rewrite LLM language
#   • NEVER infer routing or authority
#   • NEVER override authoritative response_mode (Phase 57)
# ---------------------------------------------------------------------------

import json
import time
import uuid

from solomon_core.schemas import TaskResponse
from solomon_core.logger import get_logger

logger = get_logger("response_normalizer")


# ============================================================================
# Helpers (PURE, NON-SEMANTIC)
# ============================================================================

def _coerce_to_dict(obj):
    if obj is None:
        return {}
    if isinstance(obj, dict):
        return obj
    if isinstance(obj, str):
        try:
            parsed = json.loads(obj)
            return parsed if isinstance(parsed, dict) else {"result": obj}
        except Exception:
            return {"result": obj}
    return {"result": str(obj)}


def _is_internal_docintel_payload(val):
    if not isinstance(val, dict):
        return False
    return any(
        key in val
        for key in (
            "documents",
            "reasoning_request",
            "facts",
            "failures",
            "schema",
            "docintel_type",
        )
    )


def _extract_user_visible_text(val):
    if val is None:
        return None
    if isinstance(val, str):
        return val
    if isinstance(val, dict):
        if isinstance(val.get("user_output"), str):
            return val["user_output"]
        if isinstance(val.get("result"), str):
            return val["result"]
    return str(val)


# ============================================================================
# Normalizer (PACKET-AWARE, PHASE 57 SAFE)
# ============================================================================

def normalize_response(data: dict) -> dict:
    start = time.time()
    data = _coerce_to_dict(data)

    try:
        packet_header = data.get("packet_header") or {}

        # ------------------------------------------------------------
        # Phase 57 — RESPONSE MODE AUTHORITY
        # ------------------------------------------------------------
        # response_mode MUST come from packet or upstream executor
        # NEVER inferred here
        response_mode = (
            data.get("response_mode")
            or packet_header.get("response_mode")
            or "answer"
        )

        payload = data.get("user_output")

        # ------------------------------------------------------------
        # Phase 52 FIX (retained):
        # Silent non-emission is valid
        # ------------------------------------------------------------
        if payload is None:
            user_visible = None
        elif _is_internal_docintel_payload(payload):
            user_visible = None
        else:
            user_visible = _extract_user_visible_text(payload)

        resp = TaskResponse(
            task_id=packet_header.get("packet_id", str(uuid.uuid4())),
            success=True,
            response_mode=response_mode,
            user_output=user_visible,
        )

        out = resp.as_dict()
        out["ok"] = True
        out["packet_header"] = packet_header
        out["duration_ms"] = int((time.time() - start) * 1000)

        logger.info(
            "[RESPONSE][FORMAT]",
            extra={
                "response_mode": response_mode,
            },
        )

        return out

    except Exception as e:
        logger.error(
            "[RESPONSE][ERROR]",
            extra={"exception": str(e)},
        )
        return {
            "success": False,
            "ok": False,
            "reasoning_source": "response_normalizer",
            "summary": "Response formatting failed",
            "failure_type": "execution_failure",
            "error_message": str(e),
            "duration_ms": int((time.time() - start) * 1000),
            "result": str(data),
        }


__all__ = ["normalize_response"]

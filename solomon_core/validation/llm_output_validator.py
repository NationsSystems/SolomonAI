# ------------------------------------------------------------------
# FILE: solomon_core/validation/llm_output_validator.py
# DIRECTORY: solomon_core/validation/
# ------------------------------------------------------------------
# LLM Output Validator
#
# PURPOSE
#   Validate bounded LLM lane payloads before the orchestrator emits them.
#
# CONTRACT
#   - Requires a displayable answer.
#   - Allows fast Assistant responses with no bridge or suggestions.
#   - Does not require model-generated UI chips for a valid response.
#   - Returns corrected structural defaults without changing answer meaning.
# ------------------------------------------------------------------

from typing import Any, Dict


MAX_RETRY_ATTEMPTS = 2


def _result(*, valid, reason=None, corrected=None, retry=False):
    return {
        "valid": valid,
        "reason": reason,
        "corrected": corrected,
        "retry": retry,
    }


# ============================================================
# Helpers
# ============================================================

def _is_string(value):
    return isinstance(value, str) and bool(value.strip())


def _is_optional_string(value):
    return value is None or isinstance(value, str)


def _is_optional_list_of_strings(value):
    if value is None:
        return True

    if not isinstance(value, list):
        return False

    return all(isinstance(v, str) for v in value)


def _clean_bridge(value):
    if isinstance(value, str):
        return value.strip()

    return ""


def _clean_suggestions(value):
    if not isinstance(value, list):
        return []

    cleaned = []

    for item in value:
        if isinstance(item, str) and item.strip():
            cleaned.append(item.strip())

    return cleaned[:5]


# ============================================================
# Response Validation
# ============================================================

def _validate_response(payload: Dict[str, Any]):
    if "answer" not in payload:
        return _result(
            valid=False,
            reason="Missing field: answer",
            retry=True,
        )

    if not _is_string(payload.get("answer")):
        return _result(valid=False, reason="Invalid answer", retry=True)

    if not _is_optional_string(payload.get("bridge")):
        return _result(valid=False, reason="Invalid bridge", retry=False)

    if not _is_optional_list_of_strings(payload.get("suggestions")):
        return _result(valid=False, reason="Invalid suggestions", retry=False)

    corrected = dict(payload)
    corrected["type"] = "response"
    corrected["answer"] = str(payload.get("answer") or "").strip()
    corrected["bridge"] = _clean_bridge(payload.get("bridge"))
    corrected["suggestions"] = _clean_suggestions(payload.get("suggestions"))

    return _result(valid=True, corrected=corrected)


# ============================================================
# Main Entry
# ============================================================

def validate_llm_output(payload: Dict[str, Any], attempt: int = 0):
    if not isinstance(payload, dict):
        return _result(
            valid=False,
            reason="Payload not dict",
            retry=True,
        )

    payload_type = payload.get("type") or "response"

    if payload_type == "response":
        result = _validate_response(payload)
    else:
        return _result(
            valid=False,
            reason="Execution not implemented yet",
            retry=True,
        )

    if not result["valid"]:
        if attempt >= MAX_RETRY_ATTEMPTS:
            return _result(
                valid=False,
                reason="Max retries exceeded",
                retry=False,
            )
        return result

    return result


# ============================================================
# Fallback
# ============================================================

def build_fallback_response():
    return {
        "type": "response",
        "answer": "I’m having trouble processing that request. Could you clarify?",
        "bridge": "",
        "suggestions": [],
    }
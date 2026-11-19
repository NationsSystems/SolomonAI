# -------------------------------------------------------------------
# FILE: solomon_file_action_results.py
# DIRECTORY: solomon_core/actions/
# -------------------------------------------------------------------
# Durable MySQL result store for content-bound Solomon file Actions.
# Result reuse is keyed by Action contract + source content + parameters.
# These records never grant file authority; callers must authorize the current
# governed resource before resolving or exposing a persisted result.
# -------------------------------------------------------------------

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from solomon_core.db import SessionLocal
from solomon_core.models import (
    SOLOMON_ACTION_RESULT_STATUS_READY,
    SolomonActionResult,
    SolomonActionResultResource,
)


EMPTY_ACTION_PARAMETERS: dict = {}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _canonical_parameters(parameters: Optional[dict]) -> dict:
    return dict(parameters) if isinstance(parameters, dict) else {}


def _stable_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8", errors="ignore")
    return hashlib.sha256(encoded).hexdigest()


def action_parameters_hash(parameters: Optional[dict] = None) -> str:
    """Return the deterministic cache identity for Action parameters."""

    return _stable_json_hash(
        _canonical_parameters(parameters)
    )


def action_result_hash(
    *,
    result_type: str,
    result_text: str,
    result_json: Optional[dict] = None,
) -> str:
    """Return a stable hash for one persisted Action result payload."""

    return _stable_json_hash({
        "result_type": _clean_text(result_type),
        "result_text": _clean_text(result_text),
        "result_json": dict(result_json) if isinstance(result_json, dict) else {},
    })


def _result_payload(result: SolomonActionResult) -> dict:
    return {
        "result_id": _clean_text(result.result_id),
        "action_id": _clean_text(result.action_id),
        "action_contract_version": _clean_text(result.action_contract_version),
        "source_type": _clean_text(result.source_type),
        "source_hash": _clean_text(result.source_hash),
        "parameters_hash": _clean_text(result.parameters_hash),
        "parameters": dict(result.parameters_json or {}),
        "status": _clean_text(result.status),
        "result_type": _clean_text(result.result_type),
        "result_text": _clean_text(result.result_text),
        "result": dict(result.result_json or {}),
        "result_hash": _clean_text(result.result_hash),
        "processor_key": _clean_text(result.processor_key),
        "processor_version": _clean_text(result.processor_version),
        "model_key": _clean_text(result.model_key),
        "provenance": dict(result.provenance_json or {}),
        "evidence": dict(result.evidence_json or {}),
        "metadata": dict(result.metadata_json or {}),
        "completed_at": (
            result.completed_at.isoformat()
            if isinstance(result.completed_at, datetime)
            else _clean_text(result.completed_at)
        ),
    }


def _query_ready_result(
    db_session,
    *,
    action_id: str,
    action_contract_version: str,
    source_hash: str,
    parameters_hash: str,
):
    return (
        db_session.query(SolomonActionResult)
        .filter(
            SolomonActionResult.action_id == _clean_text(action_id).lower(),
            SolomonActionResult.action_contract_version
            == _clean_text(action_contract_version),
            SolomonActionResult.source_hash == _clean_text(source_hash),
            SolomonActionResult.parameters_hash == _clean_text(parameters_hash),
            SolomonActionResult.status == SOLOMON_ACTION_RESULT_STATUS_READY,
        )
        .first()
    )


def resolve_ready_solomon_file_action_result(
    *,
    action_id: str,
    action_contract_version: str,
    source_hash: str,
    parameters: Optional[dict] = None,
    db_session=None,
) -> Optional[dict]:
    """Resolve reusable content-bound intelligence without granting authority."""

    clean_source_hash = _clean_text(source_hash)

    if not clean_source_hash:
        return None

    parameters_hash = action_parameters_hash(parameters)
    owns_session = db_session is None
    session = db_session or SessionLocal()

    try:
        result = _query_ready_result(
            session,
            action_id=action_id,
            action_contract_version=action_contract_version,
            source_hash=clean_source_hash,
            parameters_hash=parameters_hash,
        )
        return _result_payload(result) if result else None
    finally:
        if owns_session:
            session.close()


def _link_result_to_resource(
    db_session,
    *,
    result: SolomonActionResult,
    file_registry_id: int,
    source_version: int,
    source_hash: str,
    linked_by_user_id: int = 0,
    trigger_type: str = "",
    request_id: str = "",
) -> None:
    if not result or not file_registry_id:
        return

    clean_source_hash = _clean_text(source_hash)
    result_source_hash = _clean_text(
        getattr(result, "source_hash", "")
    )

    if not clean_source_hash:
        raise ValueError(
            "Action result resource links require a source hash."
        )

    if result_source_hash != clean_source_hash:
        raise ValueError(
            "Action result source hash does not match the governed resource."
        )

    link = (
        db_session.query(SolomonActionResultResource)
        .filter(
            SolomonActionResultResource.action_result_id == result.result_id,
            SolomonActionResultResource.file_registry_id == int(file_registry_id),
            SolomonActionResultResource.source_version == int(source_version or 1),
        )
        .first()
    )

    if link is None:
        link = SolomonActionResultResource(
            action_result_id=result.result_id,
            file_registry_id=int(file_registry_id),
            source_version=int(source_version or 1),
            source_hash=clean_source_hash,
        )
        db_session.add(link)

    link.source_hash = clean_source_hash
    link.linked_by_user_id = int(linked_by_user_id or 0) or None
    link.trigger_type = _clean_text(trigger_type) or None
    link.request_id = _clean_text(request_id) or None
    link.updated_at = _utc_now()


def link_ready_solomon_file_action_result(
    *,
    result_id: str,
    file_registry_id: int,
    source_version: int,
    source_hash: str,
    linked_by_user_id: int = 0,
    trigger_type: str = "",
    request_id: str = "",
    db_session=None,
) -> Optional[dict]:
    """Associate a reusable result with a governed file version."""

    owns_session = db_session is None
    session = db_session or SessionLocal()

    try:
        result = (
            session.query(SolomonActionResult)
            .filter(
                SolomonActionResult.result_id == _clean_text(result_id),
                SolomonActionResult.status == SOLOMON_ACTION_RESULT_STATUS_READY,
            )
            .first()
        )

        if result is None:
            return None

        _link_result_to_resource(
            session,
            result=result,
            file_registry_id=file_registry_id,
            source_version=source_version,
            source_hash=source_hash,
            linked_by_user_id=linked_by_user_id,
            trigger_type=trigger_type,
            request_id=request_id,
        )

        if owns_session:
            session.commit()

        return _result_payload(result)
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


def persist_ready_solomon_file_action_result(
    *,
    action_id: str,
    action_contract_version: str,
    source_hash: str,
    result_type: str,
    result_text: str,
    result_json: Optional[dict] = None,
    parameters: Optional[dict] = None,
    processor_key: str = "",
    processor_version: str = "",
    model_key: str = "",
    provenance: Optional[dict] = None,
    evidence: Optional[dict] = None,
    metadata: Optional[dict] = None,
    file_registry_id: int = 0,
    source_version: int = 1,
    linked_by_user_id: int = 0,
    trigger_type: str = "",
    request_id: str = "",
    db_session=None,
) -> dict:
    """Persist or reuse one canonical Action result and link the current resource."""

    clean_action_id = _clean_text(action_id).lower()
    clean_contract_version = _clean_text(action_contract_version)
    clean_source_hash = _clean_text(source_hash)
    clean_result_type = _clean_text(result_type)
    clean_result_text = _clean_text(result_text)
    clean_parameters = _canonical_parameters(parameters)
    parameters_hash = action_parameters_hash(clean_parameters)

    if not (
        clean_action_id
        and clean_contract_version
        and clean_source_hash
        and clean_result_type
        and clean_result_text
    ):
        raise ValueError("Action result persistence requires complete result identity and content.")

    owns_session = db_session is None
    session = db_session or SessionLocal()

    try:
        result = _query_ready_result(
            session,
            action_id=clean_action_id,
            action_contract_version=clean_contract_version,
            source_hash=clean_source_hash,
            parameters_hash=parameters_hash,
        )
        reused = result is not None

        if result is None:
            now = _utc_now()
            clean_result_json = (
                dict(result_json)
                if isinstance(result_json, dict)
                else {"content": clean_result_text}
            )
            result = SolomonActionResult(
                action_id=clean_action_id,
                action_contract_version=clean_contract_version,
                source_type="file",
                source_hash=clean_source_hash,
                parameters_hash=parameters_hash,
                parameters_json=clean_parameters,
                status=SOLOMON_ACTION_RESULT_STATUS_READY,
                result_type=clean_result_type,
                result_text=clean_result_text,
                result_json=clean_result_json,
                result_hash=action_result_hash(
                    result_type=clean_result_type,
                    result_text=clean_result_text,
                    result_json=clean_result_json,
                ),
                processor_key=_clean_text(processor_key) or None,
                processor_version=_clean_text(processor_version) or None,
                model_key=_clean_text(model_key) or None,
                provenance_json=dict(provenance or {}),
                evidence_json=dict(evidence or {}),
                metadata_json=dict(metadata or {}),
                completed_at=now,
                created_at=now,
                updated_at=now,
            )
            session.add(result)
            session.flush()

        if file_registry_id:
            _link_result_to_resource(
                session,
                result=result,
                file_registry_id=int(file_registry_id),
                source_version=int(source_version or 1),
                source_hash=clean_source_hash,
                linked_by_user_id=linked_by_user_id,
                trigger_type=trigger_type,
                request_id=request_id,
            )

        if owns_session:
            session.commit()

        payload = _result_payload(result)
        payload["reused"] = reused
        return payload
    except Exception:
        if owns_session:
            session.rollback()
        raise
    finally:
        if owns_session:
            session.close()


__all__ = [
    "action_parameters_hash",
    "action_result_hash",
    "link_ready_solomon_file_action_result",
    "persist_ready_solomon_file_action_result",
    "resolve_ready_solomon_file_action_result",
]

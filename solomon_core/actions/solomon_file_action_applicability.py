# -------------------------------------------------------------------
# FILE: solomon_file_action_applicability.py
# DIRECTORY: solomon_core/actions/
# -------------------------------------------------------------------
# Durable deterministic applicability profiles for governed file Actions.
# Profiles are refreshable metadata caches, never authorization grants.
# Runtime Action resolution still applies current registry rules, authority,
# prerequisites/readiness, rollout policy, and entitlement before execution.
# -------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Optional

from solomon_core.db import SessionLocal
from solomon_core.models import SolomonActionApplicabilityProfile

from .solomon_file_actions import (
    build_solomon_file_action_applicability,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _clean_action_ids(values: Optional[Iterable[Any]]) -> list[str]:
    if values is None:
        return []

    seen: set[str] = set()
    clean_values: list[str] = []

    for value in values:
        action_id = _clean_text(value).lower()

        if not action_id or action_id in seen:
            continue

        seen.add(action_id)
        clean_values.append(action_id)

    return clean_values


def _resource_from_entry(entry: dict) -> dict:
    clean_entry = entry if isinstance(entry, dict) else {}
    return {
        "extension": _clean_text(clean_entry.get("extension")),
        "original_name": _clean_text(
            clean_entry.get("original_name")
            or clean_entry.get("name")
        ),
    }


def _profile_payload(profile: SolomonActionApplicabilityProfile) -> dict:
    return {
        "profile_id": _clean_text(profile.profile_id),
        "file_registry_id": _safe_int(profile.file_registry_id),
        "source_version": _safe_int(profile.source_version, 1),
        "source_hash": _clean_text(profile.source_hash),
        "registry_fingerprint": _clean_text(profile.registry_fingerprint),
        "applicable_action_ids": _clean_action_ids(
            profile.applicable_action_ids_json
        ),
        "resource_characteristics": dict(
            profile.resource_characteristics_json or {}
        ),
        "evaluated_at": (
            profile.evaluated_at.isoformat()
            if isinstance(profile.evaluated_at, datetime)
            else _clean_text(profile.evaluated_at)
        ),
    }


def _entry_profile_identity(entry: dict) -> tuple[int, int, str]:
    clean_entry = entry if isinstance(entry, dict) else {}
    return (
        _safe_int(clean_entry.get("file_id")),
        _safe_int(clean_entry.get("version_number"), 1),
        _clean_text(clean_entry.get("checksum")),
    )


def ensure_solomon_file_action_applicability_profiles(
    db_session,
    entries: list[dict],
) -> tuple[dict[int, dict], bool]:
    """Resolve and refresh deterministic applicability for governed file entries.

    The caller owns transaction boundaries. The returned mapping is authoritative
    for the current registry fingerprint even when a persistence refresh is needed.
    """

    clean_entries = [
        entry
        for entry in entries
        if isinstance(entry, dict)
    ]
    file_ids = sorted({
        file_id
        for file_id, _source_version, _source_hash in (
            _entry_profile_identity(entry)
            for entry in clean_entries
        )
        if file_id
    })
    profiles_by_file_id: dict[int, SolomonActionApplicabilityProfile] = {}

    if file_ids:
        profiles = (
            db_session.query(SolomonActionApplicabilityProfile)
            .filter(
                SolomonActionApplicabilityProfile.file_registry_id.in_(file_ids)
            )
            .all()
        )
        profiles_by_file_id = {
            _safe_int(profile.file_registry_id): profile
            for profile in profiles
            if _safe_int(profile.file_registry_id)
        }

    resolved: dict[int, dict] = {}
    changed = False
    now = _utc_now()

    for entry in clean_entries:
        file_id, source_version, source_hash = _entry_profile_identity(entry)
        resource = _resource_from_entry(entry)
        evaluated = build_solomon_file_action_applicability(resource)
        applicable_action_ids = _clean_action_ids(
            evaluated.get("applicable_action_ids")
        )
        registry_fingerprint = _clean_text(
            evaluated.get("registry_fingerprint")
        )
        resource_characteristics = dict(
            evaluated.get("resource_characteristics") or {}
        )

        if not file_id:
            continue

        profile = profiles_by_file_id.get(file_id)

        if profile is None:
            profile = SolomonActionApplicabilityProfile(
                file_registry_id=file_id,
                source_version=source_version,
                source_hash=source_hash or None,
                resource_type="file",
                resource_extension=_clean_text(
                    resource_characteristics.get("extension")
                ) or None,
                registry_fingerprint=registry_fingerprint,
                applicable_action_ids_json=applicable_action_ids,
                resource_characteristics_json=resource_characteristics,
                evaluated_at=now,
                created_at=now,
                updated_at=now,
            )
            db_session.add(profile)
            profiles_by_file_id[file_id] = profile
            changed = True
        else:
            stored_action_ids = _clean_action_ids(
                profile.applicable_action_ids_json
            )
            stored_characteristics = dict(
                profile.resource_characteristics_json or {}
            )
            is_current = bool(
                _safe_int(profile.source_version, 1) == source_version
                and _clean_text(profile.source_hash) == source_hash
                and _clean_text(profile.registry_fingerprint) == registry_fingerprint
                and stored_action_ids == applicable_action_ids
                and stored_characteristics == resource_characteristics
            )

            if not is_current:
                profile.source_version = source_version
                profile.source_hash = source_hash or None
                profile.resource_type = "file"
                profile.resource_extension = _clean_text(
                    resource_characteristics.get("extension")
                ) or None
                profile.registry_fingerprint = registry_fingerprint
                profile.applicable_action_ids_json = applicable_action_ids
                profile.resource_characteristics_json = resource_characteristics
                profile.evaluated_at = now
                profile.updated_at = now
                changed = True

        resolved[file_id] = {
            "profile_id": _clean_text(profile.profile_id),
            "file_registry_id": file_id,
            "source_version": source_version,
            "source_hash": source_hash,
            "registry_fingerprint": registry_fingerprint,
            "applicable_action_ids": applicable_action_ids,
            "resource_characteristics": resource_characteristics,
        }

    return resolved, changed


def register_solomon_file_action_applicability_for_record(
    *,
    db_session,
    record,
) -> dict:
    """Create or refresh upload-time Action applicability in the caller transaction."""

    if record is None:
        return {}

    entry = {
        "file_id": getattr(record, "id", None),
        "version_number": getattr(record, "version_number", 1),
        "checksum": getattr(record, "checksum", None),
        "extension": getattr(record, "extension", None),
        "original_name": getattr(record, "original_name", None),
    }
    resolved, _changed = ensure_solomon_file_action_applicability_profiles(
        db_session,
        [entry],
    )
    return resolved.get(_safe_int(entry.get("file_id")), {})


def resolve_solomon_file_action_applicability_for_entry(entry: dict) -> dict:
    """Return a current persisted applicability profile for one runtime entry.

    If persistence refresh fails, return a deterministic current-registry profile
    rather than weakening Action availability or authorization rules.
    """

    clean_entry = entry if isinstance(entry, dict) else {}
    file_id = _safe_int(clean_entry.get("file_id"))

    if not file_id:
        return build_solomon_file_action_applicability(
            _resource_from_entry(clean_entry)
        )

    db_session = SessionLocal()

    try:
        resolved, changed = ensure_solomon_file_action_applicability_profiles(
            db_session,
            [clean_entry],
        )

        if changed:
            db_session.commit()

        return resolved.get(file_id, {})
    except Exception:
        db_session.rollback()
        return build_solomon_file_action_applicability(
            _resource_from_entry(clean_entry)
        )
    finally:
        db_session.close()


__all__ = [
    "ensure_solomon_file_action_applicability_profiles",
    "register_solomon_file_action_applicability_for_record",
    "resolve_solomon_file_action_applicability_for_entry",
]

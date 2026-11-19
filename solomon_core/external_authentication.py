# -------------------------------------------------------------------
# FILE: external_authentication.py
# DIRECTORY: solomon_core/
# -------------------------------------------------------------------
# Provider-neutral OpenID Connect exchange for Nations Systems.
# Google and Microsoft authenticate identity only; Solomon-owned users,
# organizations, groups, shares, roles, and permissions remain authoritative.
# Provider access and refresh tokens are intentionally never persisted.
# -------------------------------------------------------------------

from __future__ import annotations

import base64
from dataclasses import dataclass
import json
import logging
import re
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen

from config import settings


_GOOGLE_PROVIDER = "google"
_MICROSOFT_PROVIDER = "microsoft"
_MICROSOFT_CONSUMER_TENANT_ID = "9188040d-6c67-4c5b-b112-36a304b66dad"

_DISCOVERY_CACHE: dict[str, tuple[float, dict[str, Any]]] = {}
_DISCOVERY_CACHE_LOCK = threading.Lock()
logger = logging.getLogger("Solomon.external_authentication")


class ExternalAuthenticationError(Exception):
    """Fail-closed external authentication error with safe user messaging."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "EXTERNAL_AUTHENTICATION_FAILED",
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.error_code = str(error_code or "EXTERNAL_AUTHENTICATION_FAILED")
        self.status_code = int(status_code or 400)


@dataclass(frozen=True)
class ExternalIdentityResult:
    """Verified external identity returned by a completed provider exchange."""

    provider: str
    issuer: str
    provider_subject: str
    provider_email: str
    normalized_email: str
    email_verified: bool
    authoritative_email: bool
    tenant_id: str
    display_name: str


def _clean_value(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_email(value: Any) -> str:
    return _clean_value(value).lower()


def _looks_like_email(value: Any) -> bool:
    email = _normalize_email(value)
    return bool(
        email
        and re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[A-Za-z0-9]+",
            email,
        )
    )


def _base64url_decode(value: str) -> bytes:
    clean_value = str(value or "").strip()
    clean_value += "=" * (-len(clean_value) % 4)
    return base64.urlsafe_b64decode(clean_value.encode("ascii"))


def _parse_id_token(id_token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    parts = str(id_token or "").split(".")
    if len(parts) != 3:
        raise ExternalAuthenticationError(
            "The authentication response could not be verified.",
            error_code="OIDC_ID_TOKEN_INVALID",
        )

    try:
        header = json.loads(_base64url_decode(parts[0]).decode("utf-8"))
        claims = json.loads(_base64url_decode(parts[1]).decode("utf-8"))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExternalAuthenticationError(
            "The authentication response could not be verified.",
            error_code="OIDC_ID_TOKEN_INVALID",
        ) from exc

    if not isinstance(header, dict) or not isinstance(claims, dict):
        raise ExternalAuthenticationError(
            "The authentication response could not be verified.",
            error_code="OIDC_ID_TOKEN_INVALID",
        )

    return header, claims


def _provider_settings(provider: str) -> dict[str, Any]:
    clean_provider = _clean_value(provider).lower()

    if clean_provider == _GOOGLE_PROVIDER:
        return {
            "provider": clean_provider,
            "client_id": _clean_value(settings.GOOGLE_OIDC_CLIENT_ID),
            "client_secret": _clean_value(settings.GOOGLE_OIDC_CLIENT_SECRET),
            "discovery_url": _clean_value(settings.GOOGLE_OIDC_DISCOVERY_URL),
            "enabled": bool(settings.GOOGLE_OIDC_ENABLED),
        }

    if clean_provider == _MICROSOFT_PROVIDER:
        return {
            "provider": clean_provider,
            "client_id": _clean_value(settings.MICROSOFT_OIDC_CLIENT_ID),
            "client_secret": _clean_value(settings.MICROSOFT_OIDC_CLIENT_SECRET),
            "discovery_url": _clean_value(settings.MICROSOFT_OIDC_DISCOVERY_URL),
            "enabled": bool(settings.MICROSOFT_OIDC_ENABLED),
        }

    raise ExternalAuthenticationError(
        "Unsupported authentication provider.",
        error_code="OIDC_PROVIDER_UNSUPPORTED",
        status_code=404,
    )


def provider_is_enabled(provider: str) -> bool:
    try:
        provider_settings = _provider_settings(provider)
    except ExternalAuthenticationError:
        return False

    return bool(
        provider_settings["enabled"]
        and provider_settings["client_id"]
        and provider_settings["client_secret"]
        and provider_settings["discovery_url"]
    )


def _endpoint_is_allowed(provider: str, endpoint: str) -> bool:
    parsed = urlparse(str(endpoint or "").strip())
    if parsed.scheme.lower() != "https" or not parsed.hostname:
        return False

    hostname = parsed.hostname.lower()

    if provider == _GOOGLE_PROVIDER:
        return (
            hostname == "accounts.google.com"
            or hostname.endswith(".google.com")
            or hostname.endswith(".googleapis.com")
        )

    if provider == _MICROSOFT_PROVIDER:
        return hostname in {
            "login.microsoftonline.com",
            "graph.microsoft.com",
        }

    return False


def _require_allowed_endpoint(provider: str, endpoint: str) -> str:
    clean_endpoint = str(endpoint or "").strip()
    if not _endpoint_is_allowed(provider, clean_endpoint):
        raise ExternalAuthenticationError(
            "The authentication provider returned an invalid endpoint.",
            error_code="OIDC_ENDPOINT_INVALID",
            status_code=502,
        )
    return clean_endpoint


def _http_json(
    *,
    method: str,
    url: str,
    form: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> dict[str, Any]:
    body = None
    request_headers = {
        "Accept": "application/json",
        "User-Agent": "NationsSystems-Authentication/1.0",
    }
    request_headers.update(headers or {})

    if form is not None:
        body = urlencode(
            {
                str(key): str(value)
                for key, value in form.items()
                if value is not None
            }
        ).encode("utf-8")
        request_headers["Content-Type"] = "application/x-www-form-urlencoded"

    request_object = Request(
        url=url,
        data=body,
        headers=request_headers,
        method=str(method or "GET").upper(),
    )

    try:
        with urlopen(
            request_object,
            timeout=float(settings.OIDC_HTTP_TIMEOUT_SECONDS),
        ) as response:
            payload = response.read()
    except HTTPError as exc:
        remote_error = ""
        try:
            error_payload = json.loads(
                exc.read().decode("utf-8")
            )
            if isinstance(error_payload, dict):
                remote_error = _clean_value(
                    error_payload.get("error")
                )
        except Exception:
            remote_error = ""

        logger.warning(
            "[external_auth.http_rejected] host=%s status=%s remote_error=%s",
            urlparse(url).netloc,
            getattr(exc, "code", ""),
            remote_error or "unknown",
        )
        raise ExternalAuthenticationError(
            "The authentication provider could not complete sign-in. Please try again.",
            error_code="OIDC_PROVIDER_REJECTED_REQUEST",
            status_code=502,
        ) from exc
    except (URLError, TimeoutError, OSError) as exc:
        logger.warning(
            "[external_auth.http_unavailable] host=%s error=%s",
            urlparse(url).netloc,
            type(exc).__name__,
        )
        raise ExternalAuthenticationError(
            "The authentication provider could not be reached. Please try again.",
            error_code="OIDC_PROVIDER_UNAVAILABLE",
            status_code=502,
        ) from exc

    try:
        decoded = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ExternalAuthenticationError(
            "The authentication provider returned an invalid response.",
            error_code="OIDC_PROVIDER_RESPONSE_INVALID",
            status_code=502,
        ) from exc

    if not isinstance(decoded, dict):
        raise ExternalAuthenticationError(
            "The authentication provider returned an invalid response.",
            error_code="OIDC_PROVIDER_RESPONSE_INVALID",
            status_code=502,
        )

    return decoded


def _get_discovery_document(provider: str) -> dict[str, Any]:
    provider_settings = _provider_settings(provider)
    discovery_url = _require_allowed_endpoint(
        provider_settings["provider"],
        provider_settings["discovery_url"],
    )

    now = time.monotonic()
    with _DISCOVERY_CACHE_LOCK:
        cached = _DISCOVERY_CACHE.get(provider_settings["provider"])
        if cached and cached[0] > now:
            return dict(cached[1])

    discovery = _http_json(
        method="GET",
        url=discovery_url,
    )

    for key in (
        "authorization_endpoint",
        "token_endpoint",
        "userinfo_endpoint",
    ):
        discovery[key] = _require_allowed_endpoint(
            provider_settings["provider"],
            discovery.get(key),
        )

    with _DISCOVERY_CACHE_LOCK:
        _DISCOVERY_CACHE[provider_settings["provider"]] = (
            now + float(settings.OIDC_DISCOVERY_CACHE_SECONDS),
            dict(discovery),
        )

    return discovery


def build_authorization_url(
    *,
    provider: str,
    redirect_uri: str,
    state: str,
    nonce: str,
    code_challenge: str,
    login_hint: str = "",
) -> str:
    provider_settings = _provider_settings(provider)
    if not provider_is_enabled(provider_settings["provider"]):
        raise ExternalAuthenticationError(
            f"{provider_settings['provider'].title()} sign-in is not configured yet.",
            error_code="OIDC_PROVIDER_DISABLED",
            status_code=503,
        )

    discovery = _get_discovery_document(provider_settings["provider"])

    scopes = [
        _clean_value(scope)
        for scope in (settings.OIDC_IDENTITY_SCOPES or ())
        if _clean_value(scope)
    ]

    parameters = {
        "client_id": provider_settings["client_id"],
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "scope": " ".join(scopes),
        "state": state,
        "nonce": nonce,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }

    clean_login_hint = _normalize_email(login_hint)
    if clean_login_hint:
        parameters["login_hint"] = clean_login_hint

    if provider_settings["provider"] == _MICROSOFT_PROVIDER:
        parameters["response_mode"] = "query"

    return (
        discovery["authorization_endpoint"]
        + "?"
        + urlencode(parameters)
    )


def _audience_matches(claim_audience: Any, client_id: str) -> bool:
    if isinstance(claim_audience, str):
        return claim_audience == client_id

    if isinstance(claim_audience, (list, tuple, set)):
        return client_id in claim_audience

    return False


def _validate_id_token_claims(
    *,
    provider: str,
    client_id: str,
    expected_nonce: str,
    header: dict[str, Any],
    claims: dict[str, Any],
) -> None:
    algorithm = _clean_value(header.get("alg")).upper()
    if algorithm != "RS256":
        raise ExternalAuthenticationError(
            "The authentication response used an unsupported signing algorithm.",
            error_code="OIDC_ID_TOKEN_ALGORITHM_INVALID",
        )

    if not _audience_matches(claims.get("aud"), client_id):
        raise ExternalAuthenticationError(
            "The authentication response was issued for a different application.",
            error_code="OIDC_ID_TOKEN_AUDIENCE_INVALID",
        )

    if _clean_value(claims.get("nonce")) != expected_nonce:
        raise ExternalAuthenticationError(
            "The authentication response could not be matched to this sign-in request.",
            error_code="OIDC_ID_TOKEN_NONCE_INVALID",
        )

    now = int(time.time())
    skew = int(settings.OIDC_CLOCK_SKEW_SECONDS)

    try:
        expires_at = int(claims.get("exp"))
        issued_at = int(claims.get("iat"))
    except (TypeError, ValueError) as exc:
        raise ExternalAuthenticationError(
            "The authentication response did not contain valid token timing information.",
            error_code="OIDC_ID_TOKEN_TIME_INVALID",
        ) from exc

    if expires_at < now - skew or issued_at > now + skew:
        raise ExternalAuthenticationError(
            "The authentication response is expired or not yet valid.",
            error_code="OIDC_ID_TOKEN_TIME_INVALID",
        )

    issuer = _clean_value(claims.get("iss"))
    if not issuer:
        raise ExternalAuthenticationError(
            "The authentication response did not identify its issuer.",
            error_code="OIDC_ID_TOKEN_ISSUER_INVALID",
        )

    if provider == _GOOGLE_PROVIDER:
        if issuer not in {
            "https://accounts.google.com",
            "accounts.google.com",
        }:
            raise ExternalAuthenticationError(
                "The Google authentication response had an invalid issuer.",
                error_code="OIDC_ID_TOKEN_ISSUER_INVALID",
            )
        return

    if provider == _MICROSOFT_PROVIDER:
        tenant_id = _clean_value(claims.get("tid")).lower()
        if (
            not tenant_id
            or tenant_id == _MICROSOFT_CONSUMER_TENANT_ID
            or not re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
                tenant_id,
            )
        ):
            raise ExternalAuthenticationError(
                "This Microsoft account is not an organizational work or school account.",
                error_code="MICROSOFT_TENANT_INVALID",
                status_code=403,
            )

        expected_issuer = (
            f"https://login.microsoftonline.com/{tenant_id}/v2.0"
        )
        if issuer.lower().rstrip("/") != expected_issuer.lower().rstrip("/"):
            raise ExternalAuthenticationError(
                "The Microsoft authentication response had an invalid tenant issuer.",
                error_code="OIDC_ID_TOKEN_ISSUER_INVALID",
            )
        return

    raise ExternalAuthenticationError(
        "Unsupported authentication provider.",
        error_code="OIDC_PROVIDER_UNSUPPORTED",
        status_code=404,
    )


def exchange_authorization_code(
    *,
    provider: str,
    authorization_code: str,
    redirect_uri: str,
    code_verifier: str,
    expected_nonce: str,
) -> ExternalIdentityResult:
    provider_settings = _provider_settings(provider)
    clean_provider = provider_settings["provider"]

    if not provider_is_enabled(clean_provider):
        raise ExternalAuthenticationError(
            f"{clean_provider.title()} sign-in is not configured yet.",
            error_code="OIDC_PROVIDER_DISABLED",
            status_code=503,
        )

    discovery = _get_discovery_document(clean_provider)

    token_response = _http_json(
        method="POST",
        url=discovery["token_endpoint"],
        form={
            "code": authorization_code,
            "client_id": provider_settings["client_id"],
            "client_secret": provider_settings["client_secret"],
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": code_verifier,
        },
    )

    id_token = _clean_value(token_response.get("id_token"))
    access_token = _clean_value(token_response.get("access_token"))

    if not id_token or not access_token:
        raise ExternalAuthenticationError(
            "The authentication provider did not return the required identity response.",
            error_code="OIDC_TOKEN_RESPONSE_INCOMPLETE",
            status_code=502,
        )

    header, id_claims = _parse_id_token(id_token)
    _validate_id_token_claims(
        provider=clean_provider,
        client_id=provider_settings["client_id"],
        expected_nonce=expected_nonce,
        header=header,
        claims=id_claims,
    )

    userinfo = _http_json(
        method="GET",
        url=discovery["userinfo_endpoint"],
        headers={
            "Authorization": f"Bearer {access_token}",
        },
    )

    provider_subject = _clean_value(
        userinfo.get("sub")
        or id_claims.get("sub")
    )
    id_token_subject = _clean_value(id_claims.get("sub"))

    if (
        not provider_subject
        or not id_token_subject
        or provider_subject != id_token_subject
    ):
        raise ExternalAuthenticationError(
            "The authentication provider returned inconsistent identity information.",
            error_code="OIDC_SUBJECT_MISMATCH",
            status_code=502,
        )

    display_name = _clean_value(
        userinfo.get("name")
        or id_claims.get("name")
    )

    issuer = _clean_value(id_claims.get("iss"))
    tenant_id = _clean_value(id_claims.get("tid")).lower()

    if clean_provider == _GOOGLE_PROVIDER:
        email_candidates = (
            userinfo.get("email"),
            id_claims.get("email"),
        )
        provider_email = next(
            (
                _normalize_email(candidate)
                for candidate in email_candidates
                if _looks_like_email(candidate)
            ),
            "",
        )
        raw_verified = (
            userinfo.get("email_verified")
            if "email_verified" in userinfo
            else id_claims.get("email_verified")
        )
        email_verified = (
            raw_verified is True
            or _clean_value(raw_verified).lower() == "true"
        )
        hosted_domain = _clean_value(
            userinfo.get("hd")
            or id_claims.get("hd")
        )
        authoritative_email = bool(
            provider_email
            and email_verified
            and (
                provider_email.endswith("@gmail.com")
                or hosted_domain
            )
        )
        issuer = "https://accounts.google.com"
    else:
        # Microsoft documents email as mutable and unsuitable as durable access
        # authority. Bootstrap account association from the authenticated
        # organizational username (preferred_username/UPN) instead; after the
        # first link, issuer + provider subject is the durable identity key.
        organizational_username_candidates = (
            id_claims.get("preferred_username"),
            id_claims.get("upn"),
            userinfo.get("preferred_username"),
            userinfo.get("upn"),
        )
        organizational_username = next(
            (
                _normalize_email(candidate)
                for candidate in organizational_username_candidates
                if _looks_like_email(candidate)
            ),
            "",
        )
        fallback_email_candidates = (
            userinfo.get("email"),
            id_claims.get("email"),
        )
        provider_email = organizational_username or next(
            (
                _normalize_email(candidate)
                for candidate in fallback_email_candidates
                if _looks_like_email(candidate)
            ),
            "",
        )
        raw_verified = (
            userinfo.get("email_verified")
            if "email_verified" in userinfo
            else id_claims.get("email_verified")
        )
        email_verified = (
            raw_verified is True
            or _clean_value(raw_verified).lower() == "true"
        )
        authoritative_email = bool(
            organizational_username
            and provider_email == organizational_username
            and tenant_id
            and tenant_id != _MICROSOFT_CONSUMER_TENANT_ID
        )

    return ExternalIdentityResult(
        provider=clean_provider,
        issuer=issuer,
        provider_subject=provider_subject,
        provider_email=provider_email,
        normalized_email=provider_email,
        email_verified=email_verified,
        authoritative_email=authoritative_email,
        tenant_id=tenant_id,
        display_name=display_name,
    )

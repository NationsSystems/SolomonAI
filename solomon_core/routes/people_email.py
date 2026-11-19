# -------------------------------------------------------------------
# FILE: people_email.py
# DIRECTORY: solomon_core/routes/
# -------------------------------------------------------------------
# Server-side email delivery for contextual Solomon sharing links.
# -------------------------------------------------------------------
# This module sends contextual notices only after People authority has created
# the durable invitation state. Email delivery is transport only and does not
# grant workspace membership, file access, Group membership, or AI sources.
# -------------------------------------------------------------------

from __future__ import annotations

from datetime import datetime
from email.message import EmailMessage
from email.utils import formataddr
import html
import smtplib
import ssl
from urllib.parse import urljoin, urlparse

from config import settings
from solomon_core.logger import get_logger


logger = get_logger(
    "Solomon.people_email"
)


_ROLE_LABELS = {
    "admin": "Admin",
    "member": "Member",
    "guest": "Guest",
}


_LOCAL_DEVELOPMENT_HOSTS = {
    "localhost",
    "127.0.0.1",
    "::1",
}


_REQUIRED_SMTP_SETTINGS = {
    "PEOPLE_GROUP_INVITATION_EMAIL_SMTP_HOST": (
        "SMTP host"
    ),
    "PEOPLE_GROUP_INVITATION_EMAIL_USERNAME": (
        "SMTP username"
    ),
    "PEOPLE_GROUP_INVITATION_EMAIL_PASSWORD": (
        "SMTP password"
    ),
    "PEOPLE_GROUP_INVITATION_EMAIL_FROM_EMAIL": (
        "from email"
    ),
}


def _clean_value(value) -> str:
    return str(
        value or ""
    ).strip()


def _clean_email(value) -> str:
    return _clean_value(
        value
    ).lower()


def _setting_value(name: str):
    return getattr(
        settings,
        name,
        "",
    )


def _setting_bool(name: str) -> bool:
    return bool(
        _setting_value(name)
    )


def _setting_int(
    name: str,
    default: int = 0,
) -> int:
    try:
        return int(
            _setting_value(name)
            or default
            or 0
        )
    except (
        TypeError,
        ValueError,
    ):
        return int(
            default or 0
        )


def _missing_smtp_settings() -> list[str]:
    missing = []

    for setting_name, label in _REQUIRED_SMTP_SETTINGS.items():
        if not _clean_value(
            _setting_value(setting_name)
        ):
            missing.append(label)

    port = _setting_int(
        "PEOPLE_GROUP_INVITATION_EMAIL_SMTP_PORT"
    )

    if port <= 0:
        missing.append("SMTP port")

    return missing


def _role_label(role: str) -> str:
    clean_role = _clean_value(
        role
    ).lower()

    return _ROLE_LABELS.get(
        clean_role,
        clean_role.title() or "Member",
    )


def _safe_group_name(value: str) -> str:
    return _clean_value(
        value
    ) or "your group"


def _safe_from_name() -> str:
    return _clean_value(
        _setting_value("PEOPLE_GROUP_INVITATION_EMAIL_FROM_NAME")
    ) or "Nations Systems"


def _safe_subject_prefix() -> str:
    return _clean_value(
        _setting_value("PEOPLE_GROUP_INVITATION_EMAIL_SUBJECT_PREFIX")
    ) or "Nations Systems"


def _safe_expires_label(value) -> str:
    if isinstance(
        value,
        datetime,
    ):
        return value.strftime(
            "%B %d, %Y"
        )

    return _clean_value(
        value
    ) or "the expiration date shown in Nations Systems"


def _is_safe_absolute_base_url(value: str) -> bool:
    parsed = urlparse(
        value
    )

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return False

    if not parsed.netloc:
        return False

    if parsed.username or parsed.password:
        return False

    return True


def _is_local_development_base_url(value: str) -> bool:
    parsed = urlparse(
        value
    )

    if not _is_safe_absolute_base_url(
        value
    ):
        return False

    hostname = _clean_value(
        parsed.hostname
    ).lower()

    return hostname in _LOCAL_DEVELOPMENT_HOSTS


def _join_base_and_relative_url(
    *,
    base_url: str,
    relative_url: str,
) -> str:
    if not base_url.endswith("/"):
        base_url = f"{base_url}/"

    return urljoin(
        base_url,
        relative_url.lstrip("/"),
    )


def build_people_invitation_accept_url(
    *,
    request_base_url: str,
    relative_accept_url: str,
) -> str:
    """Build a safe workspace invitation acceptance URL for email delivery.

    Production invite links must use the configured public base URL.
    The request base URL is only accepted for localhost development so a
    forged Host header cannot become public invitation authority.
    """

    clean_accept_url = _clean_value(
        relative_accept_url
    )

    if not clean_accept_url:
        return ""

    parsed_accept_url = urlparse(
        clean_accept_url
    )

    if parsed_accept_url.scheme or parsed_accept_url.netloc:
        logger.warning(
            "[people.invitation.absolute_accept_url_rejected] "
            "accept_url=%s",
            clean_accept_url,
        )
        return ""

    configured_base_url = _clean_value(
        _setting_value("PEOPLE_GROUP_INVITATION_EMAIL_PUBLIC_BASE_URL")
    )

    if configured_base_url:
        if not _is_safe_absolute_base_url(
            configured_base_url
        ):
            logger.warning(
                "[people.invitation.invalid_public_base_url] "
                "base_url=%s",
                configured_base_url,
            )
            return clean_accept_url

        return _join_base_and_relative_url(
            base_url=configured_base_url,
            relative_url=clean_accept_url,
        )

    clean_request_base_url = _clean_value(
        request_base_url
    )

    if _is_local_development_base_url(
        clean_request_base_url
    ):
        return _join_base_and_relative_url(
            base_url=clean_request_base_url,
            relative_url=clean_accept_url,
        )

    logger.warning(
        "[people.invitation.public_base_url_missing] "
        "using_relative_accept_url=true"
    )

    return clean_accept_url


def _build_plain_text_body(
    *,
    recipient_email: str,
    role: str,
    group_name: str,
    target_group_name: str,
    invited_by_email: str,
    accept_url: str,
    expires_at,
    was_refreshed: bool,
) -> str:
    target_group = _clean_value(target_group_name)
    inviter = _clean_email(invited_by_email)

    if target_group:
        action_line = (
            f"{inviter} invited you to {target_group} in Solomon."
            if inviter
            else f"You've been invited to {target_group} in Solomon."
        )
        if was_refreshed:
            action_line = f"Here's a new link to join {target_group} in Solomon."
        action_label = f"Join {target_group}"
    else:
        action_line = (
            f"{inviter} invited you to Solomon."
            if inviter
            else "You've been invited to Solomon."
        )
        if was_refreshed:
            action_line = "Here's a new link to continue to Solomon."
        action_label = "Continue to Solomon"

    return "\n".join([
        action_line,
        "",
        f"{action_label}:",
        accept_url,
        "",
        f"Use {recipient_email} when you sign in or create your account.",
        f"This link expires on {_safe_expires_label(expires_at)}.",
        "",
        "Group access never includes another person's private files.",
        "",
        "If you weren't expecting this, you can ignore this email.",
    ])



def _build_html_body(
    *,
    recipient_email: str,
    role: str,
    group_name: str,
    target_group_name: str,
    invited_by_email: str,
    accept_url: str,
    expires_at,
    was_refreshed: bool,
) -> str:
    safe_target_group = html.escape(
        _clean_value(target_group_name)
    )
    safe_email = html.escape(
        recipient_email
    )
    safe_inviter = html.escape(
        _clean_email(invited_by_email)
    )
    safe_accept_url = html.escape(
        accept_url,
        quote=True,
    )
    safe_expires = html.escape(
        _safe_expires_label(expires_at)
    )

    if safe_target_group:
        action_line = (
            f"{safe_inviter} invited you to {safe_target_group} in Solomon."
            if safe_inviter
            else f"You've been invited to {safe_target_group} in Solomon."
        )
        if was_refreshed:
            action_line = f"Here's a new link to join {safe_target_group} in Solomon."
        button_label = f"Join {safe_target_group}"
    else:
        action_line = (
            f"{safe_inviter} invited you to Solomon."
            if safe_inviter
            else "You've been invited to Solomon."
        )
        if was_refreshed:
            action_line = "Here's a new link to continue to Solomon."
        button_label = "Continue to Solomon"

    return f"""
<!doctype html>
<html>
  <body style="font-family: Arial, sans-serif; color: #172033; line-height: 1.5;">
    <p>{action_line}</p>
    <p>
      <a href="{safe_accept_url}" style="display: inline-block; padding: 10px 14px; background: #0f6fff; color: #ffffff; text-decoration: none; border-radius: 6px;">
        {button_label}
      </a>
    </p>
    <p>Use <strong>{safe_email}</strong> when you sign in or create your account.</p>
    <p>This link expires on {safe_expires}.</p>
    <p style="color: #5f6b7a;">Group access never includes another person's private files.</p>
    <p style="color: #5f6b7a;">If you weren't expecting this, you can ignore this email.</p>
  </body>
</html>
""".strip()



def _build_invitation_message(
    *,
    recipient_email: str,
    role: str,
    group_name: str,
    target_group_name: str,
    invited_by_email: str,
    accept_url: str,
    expires_at,
    was_refreshed: bool,
) -> EmailMessage:
    target_group = _clean_value(
        target_group_name
    )
    subject = (
        f"{_safe_subject_prefix()}: Join {target_group}"
        if target_group
        else f"{_safe_subject_prefix()}: Continue to Solomon"
    )

    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = formataddr((
        _safe_from_name(),
        _setting_value("PEOPLE_GROUP_INVITATION_EMAIL_FROM_EMAIL"),
    ))
    message["To"] = recipient_email

    reply_to = _clean_email(
        _setting_value("PEOPLE_GROUP_INVITATION_EMAIL_REPLY_TO")
    )

    if reply_to:
        message["Reply-To"] = reply_to

    message.set_content(
        _build_plain_text_body(
            recipient_email=recipient_email,
            role=role,
            group_name=group_name,
            target_group_name=target_group_name,
            invited_by_email=invited_by_email,
            accept_url=accept_url,
            expires_at=expires_at,
            was_refreshed=was_refreshed,
        )
    )
    message.add_alternative(
        _build_html_body(
            recipient_email=recipient_email,
            role=role,
            group_name=group_name,
            target_group_name=target_group_name,
            invited_by_email=invited_by_email,
            accept_url=accept_url,
            expires_at=expires_at,
            was_refreshed=was_refreshed,
        ),
        subtype="html",
    )

    return message


def _deliver_message(
    message: EmailMessage,
) -> None:
    host = _clean_value(
        _setting_value("PEOPLE_GROUP_INVITATION_EMAIL_SMTP_HOST")
    )
    port = _setting_int(
        "PEOPLE_GROUP_INVITATION_EMAIL_SMTP_PORT"
    )
    username = _clean_value(
        _setting_value("PEOPLE_GROUP_INVITATION_EMAIL_USERNAME")
    )
    password = _clean_value(
        _setting_value("PEOPLE_GROUP_INVITATION_EMAIL_PASSWORD")
    )
    timeout = _setting_int(
        "PEOPLE_GROUP_INVITATION_EMAIL_TIMEOUT_SECONDS",
        15,
    )
    use_ssl = _setting_bool(
        "PEOPLE_GROUP_INVITATION_EMAIL_USE_SSL"
    )
    use_starttls = _setting_bool(
        "PEOPLE_GROUP_INVITATION_EMAIL_USE_STARTTLS"
    )
    tls_context = ssl.create_default_context()

    if use_ssl:
        with smtplib.SMTP_SSL(
            host,
            port,
            timeout=timeout,
            context=tls_context,
        ) as smtp:
            smtp.login(
                username,
                password,
            )
            smtp.send_message(
                message
            )
        return

    with smtplib.SMTP(
        host,
        port,
        timeout=timeout,
    ) as smtp:
        smtp.ehlo()

        if use_starttls:
            smtp.starttls(
                context=tls_context
            )
            smtp.ehlo()

        smtp.login(
            username,
            password,
        )
        smtp.send_message(
            message
        )


def send_people_invitation_email(
    *,
    recipient_email: str,
    role: str,
    group_name: str,
    invited_by_email: str,
    accept_url: str,
    expires_at,
    was_refreshed: bool,
    target_group_name: str = "",
) -> dict:
    """Send a Solomon workspace invitation email without changing authority."""

    enabled = _setting_bool(
        "PEOPLE_GROUP_INVITATION_EMAIL_ENABLED"
    )
    result = {
        "enabled": enabled,
        "attempted": False,
        "sent": False,
        "provider": "smtp",
        "reason": "disabled",
    }

    if not enabled:
        return result

    clean_recipient = _clean_email(
        recipient_email
    )

    if not clean_recipient:
        result["reason"] = "recipient_missing"
        result["error"] = "Recipient email is required."
        return result

    missing_settings = _missing_smtp_settings()

    if missing_settings:
        result["reason"] = "smtp_not_configured"
        result["missing_settings"] = missing_settings
        logger.warning(
            "[people.invitation.email_not_configured] "
            "missing=%s",
            ", ".join(missing_settings),
        )
        return result

    message = _build_invitation_message(
        recipient_email=clean_recipient,
        role=role,
        group_name=group_name,
        target_group_name=target_group_name,
        invited_by_email=_clean_email(
            invited_by_email
        ),
        accept_url=accept_url,
        expires_at=expires_at,
        was_refreshed=was_refreshed,
    )

    result["attempted"] = True

    try:
        _deliver_message(
            message
        )
    except Exception as exc:
        logger.exception(
            "[people.invitation.email_failed] "
            "recipient=%s error=%s",
            clean_recipient,
            exc,
        )
        result["reason"] = "delivery_failed"
        result["error"] = "SMTP delivery failed."
        return result

    result["sent"] = True
    result["reason"] = "sent"
    return result


__all__ = [
    "build_people_invitation_accept_url",
    "send_people_invitation_email",
]
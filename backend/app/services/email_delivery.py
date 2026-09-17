from __future__ import annotations

from email.message import EmailMessage
import smtplib
from urllib.parse import urlencode

from backend.app.core.config import settings


class EmailDeliveryError(RuntimeError):
    """Raised when configured outbound email delivery fails."""


def verification_url(token: str) -> str:
    base = f"{settings.public_app_url.rstrip('/')}/verify-email"
    return f"{base}?{urlencode({'token': token})}"


def send_verification_email(email: str, token: str) -> bool:
    """Deliver a verification email without logging or persisting the raw token.

    False means outbound delivery is intentionally unconfigured, which preserves
    bootstrap/local operation until a provider is configured.
    """
    if not settings.smtp_host or not settings.email_from_address:
        return False

    message = EmailMessage()
    message["Subject"] = "Verify your Seldrune email"
    message["From"] = settings.email_from_address
    message["To"] = email
    message.set_content(
        "Verify your Seldrune email address using this link:\n\n"
        f"{verification_url(token)}\n\n"
        "If you did not request this, you can ignore this message."
    )

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as smtp:
            if settings.smtp_starttls:
                smtp.starttls()
            if settings.smtp_username and settings.smtp_password:
                smtp.login(settings.smtp_username, settings.smtp_password)
            smtp.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Verification email delivery failed") from exc
    return True

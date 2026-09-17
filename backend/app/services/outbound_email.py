from __future__ import annotations

from email.message import EmailMessage
import smtplib

from backend.app.core.config import settings


class EmailDeliveryError(RuntimeError):
    """Raised when configured outbound email delivery fails."""


def send_verification_email(*, recipient: str, token: str) -> bool:
    """Send a verification link when SMTP is configured.

    Returns False in environments where outbound email is intentionally not
    configured. Tokens are never logged or persisted by this service.
    """
    if not settings.smtp_host or not settings.email_from_address:
        return False

    verification_url = (
        f"{settings.public_app_url.rstrip('/')}/verify-email?token={token}"
    )
    message = EmailMessage()
    message["Subject"] = "Verify your Seldrune email"
    message["From"] = settings.email_from_address
    message["To"] = recipient
    message.set_content(
        "Verify your Seldrune email by opening this link:\n\n"
        f"{verification_url}\n\n"
        "This link expires in 24 hours and can only be used once."
    )

    try:
        with smtplib.SMTP(
            settings.smtp_host,
            settings.smtp_port,
            timeout=settings.smtp_timeout_seconds,
        ) as client:
            if settings.smtp_starttls:
                client.starttls()
            if settings.smtp_username and settings.smtp_password:
                client.login(settings.smtp_username, settings.smtp_password)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise EmailDeliveryError("Verification email delivery failed") from exc
    return True

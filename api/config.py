from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_SMTP_SERVER = "mail.voteforjulia.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_SECURITY = "auto"
DEFAULT_RECIPIENT_EMAIL = "info@voteforjulia.com"
DEFAULT_SHEETS_WORKSHEET = "Sheet1"
DEFAULT_YARDSIGN_SHEETS_WORKSHEET = "Yard Signs"

# Both network calls a submission makes are to third parties that can accept a
# connection and then stall. Without an explicit timeout, smtplib and httplib2
# both inherit `socket.getdefaulttimeout()`, which is None -- so a stalled peer
# parks the worker forever, and Passenger spawns workers per request rather
# than capping them (docs/hosting.md), so stalled ones accumulate.
#
# The values are upper bounds on pathological behaviour, not on the normal case:
# a healthy SMTP handshake is well under a second, and a Sheets write is a few
# hundred milliseconds. Sheets gets the larger budget because it runs *after*
# both emails are away, so giving up there loses a row that email already has.
DEFAULT_SMTP_TIMEOUT_SECONDS = 10.0
DEFAULT_SHEETS_TIMEOUT_SECONDS = 15.0

# The forms' combined field limits (api/models.py) come to roughly 1.5KB, so
# 64KB is generous for anything legitimate while keeping a hostile body from
# being buffered and parsed in full before validation rejects it.
DEFAULT_MAX_REQUEST_BYTES = 64 * 1024


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    return value if value else default


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if not value:
        return default

    return value.lower() in {"1", "true", "yes", "on"}


def env_positive_number(name: str, default: float) -> float:
    """A strictly positive number from the environment, or `default` if unset.

    Raises ValueError on a value that is unparseable or non-positive rather than
    silently falling back: a timeout typo'd to `1O` should surface, not quietly
    restore the unbounded-wait behaviour these settings exist to prevent.
    """
    raw = env(name)
    if not raw:
        return default

    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc

    if value <= 0:
        raise ValueError(f"{name} must be greater than zero, got {raw!r}")

    return value


def parse_recipients(value: str) -> list[str]:
    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


@dataclass(frozen=True)
class EmailConfig:
    smtp_server: str
    smtp_port: int
    smtp_security: str
    email_address: str
    email_password: str
    recipients: list[str]
    plain_text_confirmation_only: bool
    timeout_seconds: float = DEFAULT_SMTP_TIMEOUT_SECONDS
    # Published to supporters, so deliberately not the notification routing
    # above. See _supporter_reply_address in services/email_service.py.
    supporter_reply_address: str = DEFAULT_RECIPIENT_EMAIL


@dataclass(frozen=True)
class SheetsConfig:
    spreadsheet_id: str
    worksheet: str
    service_account_file: str
    service_account_json: str
    timeout_seconds: float = DEFAULT_SHEETS_TIMEOUT_SECONDS


def load_email_config(recipient_env: str = "RECIPIENT_EMAIL") -> EmailConfig:
    smtp_port_raw = env("SMTP_PORT", str(DEFAULT_SMTP_PORT))
    smtp_security = env("SMTP_SECURITY", DEFAULT_SMTP_SECURITY).lower()
    if smtp_security not in {"auto", "ssl", "starttls"}:
        raise ValueError("SMTP_SECURITY must be one of: auto, ssl, starttls")

    # Form-specific recipient vars (e.g. RECIPIENT_EMAIL_SIGNS) fall back to
    # RECIPIENT_EMAIL when unset.
    recipients_raw = env(recipient_env) or env("RECIPIENT_EMAIL", DEFAULT_RECIPIENT_EMAIL)

    return EmailConfig(
        smtp_server=env("SMTP_SERVER", DEFAULT_SMTP_SERVER),
        smtp_port=int(smtp_port_raw),
        smtp_security=smtp_security,
        email_address=env("EMAIL_ADDRESS"),
        email_password=env("EMAIL_PASSWORD"),
        recipients=parse_recipients(recipients_raw),
        plain_text_confirmation_only=env_bool("PLAIN_TEXT_CONFIRMATION_ONLY", False),
        timeout_seconds=env_positive_number("SMTP_TIMEOUT_SECONDS", DEFAULT_SMTP_TIMEOUT_SECONDS),
        supporter_reply_address=env("SUPPORTER_REPLY_EMAIL", DEFAULT_RECIPIENT_EMAIL),
    )


def load_sheets_config(
    worksheet_env: str = "GOOGLE_SHEETS_WORKSHEET",
    default_worksheet: str = DEFAULT_SHEETS_WORKSHEET,
) -> SheetsConfig:
    return SheetsConfig(
        spreadsheet_id=env("GOOGLE_SHEETS_SPREADSHEET_ID"),
        worksheet=env(worksheet_env, default_worksheet),
        service_account_file=env("GOOGLE_SERVICE_ACCOUNT_FILE"),
        service_account_json=env("GOOGLE_SERVICE_ACCOUNT_JSON"),
        timeout_seconds=env_positive_number(
            "SHEETS_TIMEOUT_SECONDS", DEFAULT_SHEETS_TIMEOUT_SECONDS
        ),
    )

from __future__ import annotations

from dataclasses import dataclass
import os

DEFAULT_SMTP_SERVER = "mail.voteforjulia.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_SMTP_SECURITY = "auto"
DEFAULT_RECIPIENT_EMAIL = "info@voteforjulia.com"
DEFAULT_SHEETS_WORKSHEET = "Sheet1"
DEFAULT_YARDSIGN_SHEETS_WORKSHEET = "Yard Signs"


def env(name: str, default: str = "") -> str:
    value = os.getenv(name, default).strip()
    return value if value else default


def env_bool(name: str, default: bool = False) -> bool:
    value = env(name)
    if not value:
        return default

    return value.lower() in {"1", "true", "yes", "on"}


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


@dataclass(frozen=True)
class SheetsConfig:
    spreadsheet_id: str
    worksheet: str
    service_account_file: str
    service_account_json: str



def load_email_config() -> EmailConfig:
    smtp_port_raw = env("SMTP_PORT", str(DEFAULT_SMTP_PORT))
    smtp_security = env("SMTP_SECURITY", DEFAULT_SMTP_SECURITY).lower()
    if smtp_security not in {"auto", "ssl", "starttls"}:
        raise ValueError("SMTP_SECURITY must be one of: auto, ssl, starttls")

    return EmailConfig(
        smtp_server=env("SMTP_SERVER", DEFAULT_SMTP_SERVER),
        smtp_port=int(smtp_port_raw),
        smtp_security=smtp_security,
        email_address=env("EMAIL_ADDRESS"),
        email_password=env("EMAIL_PASSWORD"),
        recipients=parse_recipients(env("RECIPIENT_EMAIL", DEFAULT_RECIPIENT_EMAIL)),
        plain_text_confirmation_only=env_bool("PLAIN_TEXT_CONFIRMATION_ONLY", False),
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
    )

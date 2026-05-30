from __future__ import annotations

from dataclasses import dataclass
import os

DEFAULT_SMTP_SERVER = "mail.voteforjulia.com"
DEFAULT_SMTP_PORT = 465
DEFAULT_RECIPIENT_EMAIL = "info@voteforjulia.com"
DEFAULT_SHEETS_WORKSHEET = "Sheet1"


def env(name: str, default: str = "") -> str:
    return os.getenv(name, default).strip()


def parse_recipients(value: str) -> list[str]:
    normalized = value.replace(";", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]


@dataclass(frozen=True)
class EmailConfig:
    smtp_server: str
    smtp_port: int
    email_address: str
    email_password: str
    recipients: list[str]


@dataclass(frozen=True)
class SheetsConfig:
    spreadsheet_id: str
    worksheet: str
    service_account_file: str
    service_account_json: str



def load_email_config() -> EmailConfig:
    smtp_port_raw = env("SMTP_PORT", str(DEFAULT_SMTP_PORT))
    return EmailConfig(
        smtp_server=env("SMTP_SERVER", DEFAULT_SMTP_SERVER),
        smtp_port=int(smtp_port_raw),
        email_address=env("EMAIL_ADDRESS"),
        email_password=env("EMAIL_PASSWORD"),
        recipients=parse_recipients(env("RECIPIENT_EMAIL", DEFAULT_RECIPIENT_EMAIL)),
    )



def load_sheets_config() -> SheetsConfig:
    return SheetsConfig(
        spreadsheet_id=env("GOOGLE_SHEETS_SPREADSHEET_ID"),
        worksheet=env("GOOGLE_SHEETS_WORKSHEET", DEFAULT_SHEETS_WORKSHEET),
        service_account_file=env("GOOGLE_SERVICE_ACCOUNT_FILE"),
        service_account_json=env("GOOGLE_SERVICE_ACCOUNT_JSON"),
    )

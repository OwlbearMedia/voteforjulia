from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re


MAX_FIRST_NAME_LENGTH = 80
MAX_LAST_NAME_LENGTH = 80
MAX_EMAIL_LENGTH = 254
MAX_PHONE_LENGTH = 32
MAX_MESSAGE_LENGTH = 500
MAX_HELP_WAYS_COUNT = 10
MAX_HELP_WAY_LENGTH = 100

_EMAIL_PATTERN = re.compile(
    r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9-]+(?:\.[A-Z0-9-]+)+$",
    re.IGNORECASE,
)


def looks_like_email(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or contains_disallowed_control_chars(normalized, allow_newlines=False):
        return False

    return bool(_EMAIL_PATTERN.fullmatch(normalized))


def contains_disallowed_control_chars(value: str, *, allow_newlines: bool) -> bool:
    for character in value:
        if character in {"\n", "\r"}:
            if allow_newlines:
                continue
            return True

        if ord(character) < 32 or ord(character) == 127:
            return True

    return False


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip(" \t")


def normalize_string_list(value: object) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        candidates = [item.strip() for item in value.split(",")]
        return [item for item in candidates if item]

    if isinstance(value, list):
        items: list[str] = []
        for item in value:
            if isinstance(item, str):
                normalized = item.strip()
                if normalized:
                    items.append(normalized)
        return items

    return []


def validate_submission(submission: "Submission") -> str:
    if contains_disallowed_control_chars(submission.first_name, allow_newlines=False):
        return "First name contains invalid characters."
    if contains_disallowed_control_chars(submission.last_name, allow_newlines=False):
        return "Last name contains invalid characters."
    if contains_disallowed_control_chars(submission.name, allow_newlines=False):
        return "Name contains invalid characters."
    if contains_disallowed_control_chars(submission.email, allow_newlines=False):
        return "Email contains invalid characters."
    if contains_disallowed_control_chars(submission.phone, allow_newlines=False):
        return "Phone contains invalid characters."
    if contains_disallowed_control_chars(submission.message, allow_newlines=True):
        return "Message contains invalid characters."

    for help_way in submission.help_ways:
        if contains_disallowed_control_chars(help_way, allow_newlines=False):
            return "Ways to help contains invalid characters."

    if len(submission.first_name) > MAX_FIRST_NAME_LENGTH:
        return f"First name must be {MAX_FIRST_NAME_LENGTH} characters or fewer."
    if len(submission.last_name) > MAX_LAST_NAME_LENGTH:
        return f"Last name must be {MAX_LAST_NAME_LENGTH} characters or fewer."
    if len(submission.email) > MAX_EMAIL_LENGTH:
        return f"Email must be {MAX_EMAIL_LENGTH} characters or fewer."
    if len(submission.phone) > MAX_PHONE_LENGTH:
        return f"Phone must be {MAX_PHONE_LENGTH} characters or fewer."
    if len(submission.message) > MAX_MESSAGE_LENGTH:
        return f"Message must be {MAX_MESSAGE_LENGTH} characters or fewer."
    if len(submission.help_ways) > MAX_HELP_WAYS_COUNT:
        return f"Please select no more than {MAX_HELP_WAYS_COUNT} ways to help."

    for help_way in submission.help_ways:
        if len(help_way) > MAX_HELP_WAY_LENGTH:
            return f"Each way to help must be {MAX_HELP_WAY_LENGTH} characters or fewer."

    return ""


def _compose_name(name_value: object, first_name_value: object, last_name_value: object) -> str:
    name = normalize_text(name_value)
    if name:
        return name

    first_name = normalize_text(first_name_value)
    last_name = normalize_text(last_name_value)
    return " ".join(part for part in (first_name, last_name) if part).strip()


def _split_name(name_value: object, first_name_value: object, last_name_value: object) -> tuple[str, str]:
    first_name = normalize_text(first_name_value)
    last_name = normalize_text(last_name_value)
    if first_name or last_name:
        return first_name, last_name

    name = normalize_text(name_value)
    if not name:
        return "", ""

    name_parts = name.split(None, 1)
    if len(name_parts) == 1:
        return name_parts[0], ""

    return name_parts[0], name_parts[1]


@dataclass(frozen=True)
class Submission:
    first_name: str
    last_name: str
    name: str
    email: str
    phone: str
    message: str
    help_ways: list[str]

    @classmethod
    def from_json(cls, payload: dict) -> "Submission":
        help_ways = normalize_string_list(payload.get("helpWays"))
        if not help_ways:
            help_ways = normalize_string_list(payload.get("helpWays[]"))

        first_name, last_name = _split_name(
            payload.get("name"),
            payload.get("firstName"),
            payload.get("lastName"),
        )

        return cls(
            first_name=first_name,
            last_name=last_name,
            name=_compose_name(
                payload.get("name"),
                payload.get("firstName"),
                payload.get("lastName"),
            ),
            email=normalize_text(payload.get("email")),
            phone=normalize_text(payload.get("phone")),
            message=normalize_text(payload.get("message")),
            help_ways=help_ways,
        )

    @classmethod
    def from_form(cls, form_data) -> "Submission":
        help_ways = [item.strip() for item in form_data.getlist("helpWays[]") if item.strip()]
        if not help_ways:
            help_ways = [item.strip() for item in form_data.getlist("helpWays") if item.strip()]
        if not help_ways:
            help_ways = normalize_string_list(form_data.get("helpWays"))

        first_name, last_name = _split_name(
            form_data.get("name"),
            form_data.get("firstName"),
            form_data.get("lastName"),
        )

        return cls(
            first_name=first_name,
            last_name=last_name,
            name=_compose_name(
                form_data.get("name"),
                form_data.get("firstName"),
                form_data.get("lastName"),
            ),
            email=normalize_text(form_data.get("email")),
            phone=normalize_text(form_data.get("phone")),
            message=normalize_text(form_data.get("message")),
            help_ways=help_ways,
        )

    def to_email_body(self) -> str:
        lines = [
            f"Name: {self.name}",
            f"Email: {self.email}",
        ]

        if self.phone:
            lines.append(f"Phone: {self.phone}")

        if self.help_ways:
            lines.append(f"Ways to help: {', '.join(self.help_ways)}")

        if self.message:
            lines.append("")
            lines.append("Message:")
            lines.append(self.message)

        return "\n".join(lines)

    def to_sheet_row(self) -> list[str]:
        return [
            datetime.now(timezone.utc).isoformat(),
            self.first_name,
            self.last_name,
            self.email,
            self.phone,
            ", ".join(self.help_ways),
            self.message,
        ]

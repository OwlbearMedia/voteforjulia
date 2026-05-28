from dataclasses import dataclass
from datetime import datetime, timezone


def looks_like_email(value: str) -> bool:
    if "@" not in value:
        return False
    local_part, _, domain = value.partition("@")
    return bool(local_part and domain and "." in domain)


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


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


@dataclass(frozen=True)
class Submission:
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

        return cls(
            name=normalize_text(payload.get("name")),
            email=normalize_text(payload.get("email")),
            phone=normalize_text(payload.get("phone")),
            message=normalize_text(payload.get("message")),
            help_ways=help_ways,
        )

    @classmethod
    def from_form(cls, form_data) -> "Submission":
        return cls(
            name=normalize_text(form_data.get("name")),
            email=normalize_text(form_data.get("email")),
            phone=normalize_text(form_data.get("phone")),
            message=normalize_text(form_data.get("message")),
            help_ways=[item.strip() for item in form_data.getlist("helpWays[]") if item.strip()],
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

    def to_sheet_row(self, path: str, user_agent: str, forwarded_for: str) -> list[str]:
        return [
            datetime.now(timezone.utc).isoformat(),
            self.name,
            self.email,
            self.phone,
            ", ".join(self.help_ways),
            self.message,
            path,
            user_agent,
            forwarded_for,
        ]

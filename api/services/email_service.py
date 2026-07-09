from __future__ import annotations

from contextlib import contextmanager
import secrets
import smtplib
from email.message import Message
from email.utils import formatdate
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

from api.config import EmailConfig
from api.models import Submission, YardSignRequest


_CONFIRMATION_TEMPLATE = Path(__file__).resolve().parents[1] / "email" / "email-template.html"
_YARD_SIGN_CONFIRMATION_TEMPLATE = (
    Path(__file__).resolve().parents[1] / "email" / "yard-sign-email-template.html"
)
_SENDER_DISPLAY_NAME = "Julia Hamann"


def _formatted_sender(email_address: str) -> str:
    return f"{_SENDER_DISPLAY_NAME} <{email_address}>"


def _message_id_domain(email_address: str) -> str:
    _, _, domain = email_address.partition("@")
    return domain or "localhost"


def _generate_message_id(domain: str) -> str:
    # A cryptographically random, purely alphanumeric (hex) local part tied to
    # our own sending domain. Some spam filters penalize Message-IDs whose
    # domain doesn't match the sender, or whose local part looks low-entropy
    # or bot-generated (e.g. sequential/short); 128 bits of secrets-grade
    # randomness avoids both.
    return f"<{secrets.token_hex(16)}@{domain}>"


def _set_common_headers(msg: Message, *, from_address: str, to_address: str, subject: str) -> None:
    msg["From"] = _formatted_sender(from_address)
    msg["To"] = to_address
    msg["Date"] = formatdate(localtime=True)
    msg["Message-ID"] = _generate_message_id(_message_id_domain(from_address))
    msg["Subject"] = subject


def _build_submission_message(config: EmailConfig, submission: Submission) -> MIMEMultipart:
    msg = MIMEMultipart()
    _set_common_headers(
        msg,
        from_address=config.email_address,
        to_address=", ".join(config.recipients),
        subject=f"New message from {submission.name}",
    )
    msg["Reply-To"] = submission.email
    msg.attach(MIMEText(submission.to_email_body(), "plain", "utf-8"))
    return msg


def _build_confirmation_content(submission: Submission) -> tuple[str, str]:
    greeting_name = submission.first_name or "there"
    plain_text_body = "\n".join([
        f"Hi {greeting_name}!",
        "",
        "Thank you so much for reaching out to help promote my campaign. I am incredibly grateful for your support!",
        "",
        "Right now, I am in the stage of gathering information and figuring out where volunteers are needed most. I will get you added to our volunteer list and be in touch as more direct needs arise.",
        "",
        "If you're looking for a yard sign, they will be coming soon as well. I'm gathering some donations to get those printing costs covered, and will get those shared out as soon as possible!",
        "",
        "For now, please keep planting my name in every ear you can and be sure they know about the primary vote coming up on August 11th! The primary narrows the mayoral candidates down to two for November.",
        "",
        "It's also super helpful if you follow my campaign on Facebook and Instagram, invite others, and share posts as they come up to encourage folks to get engaged or donate if they can.",
        "Facebook: https://www.facebook.com/profile.php?id=61590411090366",
        "Instagram: https://www.instagram.com/voteforjuliahamann",
        "",
        "We've got an exciting season ahead of us and I can't wait to connect with you in person!",
        "",
        "All my best,",
        "Julia",
        "",
        "Paid for by Julia Hamann for Mankato Mayor",
        "https://voteforjulia.com",
    ])

    template_html = _CONFIRMATION_TEMPLATE.read_text(encoding="utf-8")
    html_body = template_html.replace("{submission.name}", escape(greeting_name))

    return plain_text_body, html_body


def _build_confirmation_message(config: EmailConfig, submission: Submission) -> Message:
    plain_text_body, html_body = _build_confirmation_content(submission)

    if config.plain_text_confirmation_only:
        msg = MIMEText(plain_text_body, "plain", "utf-8")
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(plain_text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    _set_common_headers(
        msg,
        from_address=config.email_address,
        to_address=submission.email,
        subject="Thanks for reaching out to Julia Hamann for Mayor",
    )
    return msg


def _send_message(server: smtplib.SMTP, from_address: str, recipients: list[str], message: Message) -> dict:
    return server.sendmail(from_address, recipients, message.as_string())


def _should_use_starttls(config: EmailConfig) -> bool:
    if config.smtp_security == "starttls":
        return True
    if config.smtp_security == "ssl":
        return False

    # Auto mode: follow common provider defaults.
    return config.smtp_port == 587


@contextmanager
def _smtp_connection(config: EmailConfig):
    if _should_use_starttls(config):
        server = smtplib.SMTP(config.smtp_server, config.smtp_port)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.email_address, config.email_password)
            yield server
        finally:
            server.quit()
        return

    with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port) as server:
        server.login(config.email_address, config.email_password)
        yield server


def send_submission_email(config: EmailConfig, submission: Submission) -> dict:
    msg = _build_submission_message(config, submission)

    with _smtp_connection(config) as server:
        return _send_message(server, config.email_address, config.recipients, msg)


def send_confirmation_email(config: EmailConfig, submission: Submission) -> dict:
    msg = _build_confirmation_message(config, submission)

    with _smtp_connection(config) as server:
        return _send_message(server, config.email_address, [submission.email], msg)


def _build_yard_sign_request_message(config: EmailConfig, yard_sign_request: YardSignRequest) -> MIMEMultipart:
    msg = MIMEMultipart()
    _set_common_headers(
        msg,
        from_address=config.email_address,
        to_address=", ".join(config.recipients),
        subject=f"New yard sign request from {yard_sign_request.name}",
    )
    msg["Reply-To"] = yard_sign_request.email
    msg.attach(MIMEText(yard_sign_request.to_email_body(), "plain", "utf-8"))
    return msg


def _build_yard_sign_confirmation_content(yard_sign_request: YardSignRequest) -> tuple[str, str]:
    greeting_name = yard_sign_request.first_name or "there"
    plain_text_body = "\n".join([
        f"Hi {greeting_name}!",
        "",
        "Thanks so much for requesting a yard sign to support my campaign for Mankato Mayor!",
        "",
        "We'll be in touch soon with details on pickup or delivery.",
        "",
        "It's also super helpful if you follow my campaign on Facebook and Instagram, invite others, and share posts as they come up to encourage folks to get engaged or donate if they can.",
        "Facebook: https://www.facebook.com/profile.php?id=61590411090366",
        "Instagram: https://www.instagram.com/voteforjuliahamann",
        "",
        "Thank you again for your support!",
        "",
        "All my best,",
        "Julia",
        "",
        "Paid for by Julia Hamann for Mankato Mayor",
        "https://voteforjulia.com",
    ])

    template_html = _YARD_SIGN_CONFIRMATION_TEMPLATE.read_text(encoding="utf-8")
    html_body = template_html.replace("{submission.name}", escape(greeting_name))

    return plain_text_body, html_body


def _build_yard_sign_confirmation_message(config: EmailConfig, yard_sign_request: YardSignRequest) -> Message:
    plain_text_body, html_body = _build_yard_sign_confirmation_content(yard_sign_request)

    if config.plain_text_confirmation_only:
        msg = MIMEText(plain_text_body, "plain", "utf-8")
    else:
        msg = MIMEMultipart("alternative")
        msg.attach(MIMEText(plain_text_body, "plain", "utf-8"))
        msg.attach(MIMEText(html_body, "html", "utf-8"))

    _set_common_headers(
        msg,
        from_address=config.email_address,
        to_address=yard_sign_request.email,
        subject="Thanks for requesting a yard sign for Julia Hamann for Mayor",
    )
    return msg


def send_yard_sign_request_email(config: EmailConfig, yard_sign_request: YardSignRequest) -> dict:
    msg = _build_yard_sign_request_message(config, yard_sign_request)

    with _smtp_connection(config) as server:
        return _send_message(server, config.email_address, config.recipients, msg)


def send_yard_sign_confirmation_email(config: EmailConfig, yard_sign_request: YardSignRequest) -> dict:
    msg = _build_yard_sign_confirmation_message(config, yard_sign_request)

    with _smtp_connection(config) as server:
        return _send_message(server, config.email_address, [yard_sign_request.email], msg)

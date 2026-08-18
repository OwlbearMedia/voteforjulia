from __future__ import annotations

import secrets
import smtplib
import unicodedata
from contextlib import contextmanager
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formatdate
from html import escape
from pathlib import Path

from api.config import EmailConfig
from api.models import Submission, YardSignRequest

_CONFIRMATION_TEMPLATE = Path(__file__).resolve().parents[1] / "email" / "email-template.html"
_YARD_SIGN_CONFIRMATION_TEMPLATE = (
    Path(__file__).resolve().parents[1] / "email" / "yard-sign-email-template.html"
)
_SENDER_DISPLAY_NAME = "Julia Hamann"

# The greeting is the one piece of caller-supplied text in a message the
# campaign's own domain signs and sends to an address the caller also chose, so
# it is the one place someone could put chosen words in front of a stranger
# under Julia's name. Cut to a length and a character set that still fits every
# real first name. See ADR-0018.
_MAX_GREETING_LENGTH = 30

# No `.`, deliberately: it is what lets a domain survive the filter
# ("evil.example"), and some mail clients linkify one. The cost is that "J."
# greets as "J", which no real supporter will notice.
_GREETING_EXTRA_CHARS = frozenset(" '-")

# Letters and combining marks. `M` is not optional padding: in Indic and many
# other scripts the marks carry vowels, so dropping them rewrites the name.
_GREETING_CHARACTER_CATEGORIES = frozenset("LM")

# ZWNJ and ZWJ, allowed by codepoint rather than by category. They are `Cf`
# (format), and Persian, Urdu and Indic names use them to control joining --
# "علی‌رضا" renders as one word without the ZWNJ. Admitting the whole `Cf`
# category instead would also admit the bidi overrides (U+202D/U+202E), which
# exist to make text display in an order it is not written in.
_GREETING_JOINERS = frozenset("\u200c\u200d")

# Trimmed from the ends, where a joiner or a separator has nothing to join or
# separate. Kept out of the middle, where they are part of the name.
_GREETING_EDGE_CHARS = "".join(sorted(_GREETING_EXTRA_CHARS | _GREETING_JOINERS))


def _safe_greeting(raw: str, fallback: str) -> str:
    """A first name fit to put after "Hi", or `fallback` if nothing survives.

    Keeps Unicode letters (`L*`) **and combining marks** (`M*`), which is the
    whole difficulty. `str.isalpha()` is false for a mark, so filtering on it
    silently rewrites names rather than passing them: decomposed "José" loses
    its accent, and Indic names lose their vowel signs outright -- "अनुराधा"
    became "अनरध", which is not a spelling of anything. Caught by Copilot on
    PR #138.

    Digits and punctuation are still dropped, which is what keeps a phone
    number or a URL out of the greeting line, and at least one letter must
    survive so a string of bare marks cannot get through.

    Only the confirmation is sanitised -- the notification to the campaign and
    the sheet row keep the submitted value verbatim, because those are what a
    volunteer follows up on.
    """
    # NFC first, so a decomposed name is measured and truncated as the
    # characters a reader sees rather than as base-plus-mark pairs.
    normalized = unicodedata.normalize("NFC", raw)

    kept = "".join(
        ch
        for ch in normalized
        if unicodedata.category(ch)[0] in _GREETING_CHARACTER_CATEGORIES
        or ch in _GREETING_EXTRA_CHARS
        or ch in _GREETING_JOINERS
    )
    collapsed = " ".join(kept.split())[:_MAX_GREETING_LENGTH].strip(_GREETING_EDGE_CHARS)

    # Truncation can land inside a combining sequence and leave a mark with
    # nothing to attach to, which renders as a stray glyph.
    while collapsed and unicodedata.category(collapsed[0]).startswith("M"):
        collapsed = collapsed[1:]

    if not any(unicodedata.category(ch).startswith("L") for ch in collapsed):
        return fallback

    return unicodedata.normalize("NFC", collapsed)


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
    greeting_name = _safe_greeting(submission.first_name, "there")
    plain_text_body = "\n".join(
        [
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
        ]
    )

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


def _send_message(
    server: smtplib.SMTP, from_address: str, recipients: list[str], message: Message
) -> dict:
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
    # `timeout` is not optional dressing. Both constructors default it to
    # `socket._GLOBAL_DEFAULT_TIMEOUT`, which resolves to
    # `socket.getdefaulttimeout()` -- None -- so a mail server that completes
    # the TCP handshake and then stalls blocks the worker in connect() or
    # login() with no upper bound. That is the common failure; a refused
    # connection is the easy one. It applies to every socket operation on the
    # connection, so the send is covered too, not just the handshake.
    if _should_use_starttls(config):
        server = smtplib.SMTP(config.smtp_server, config.smtp_port, timeout=config.timeout_seconds)
        try:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(config.email_address, config.email_password)
            yield server
        finally:
            server.quit()
        return

    with smtplib.SMTP_SSL(
        config.smtp_server, config.smtp_port, timeout=config.timeout_seconds
    ) as server:
        server.login(config.email_address, config.email_password)
        yield server


def verify_smtp_credentials(config: EmailConfig) -> None:
    """Connect and authenticate, sending nothing. Raises on failure.

    Opening and immediately closing the connection exercises exactly the step
    that broke silently during the `$`-in-password incident: the server was
    reachable and /health was green, but LOGIN was rejected. No message is sent,
    so the mail server's one-message-per-connection limit is not in play.
    """
    with _smtp_connection(config):
        pass


def send_submission_email(config: EmailConfig, submission: Submission) -> dict:
    msg = _build_submission_message(config, submission)

    with _smtp_connection(config) as server:
        return _send_message(server, config.email_address, config.recipients, msg)


def send_confirmation_email(config: EmailConfig, submission: Submission) -> dict:
    msg = _build_confirmation_message(config, submission)

    with _smtp_connection(config) as server:
        return _send_message(server, config.email_address, [submission.email], msg)


def _build_yard_sign_request_message(
    config: EmailConfig, yard_sign_request: YardSignRequest
) -> MIMEMultipart:
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
    greeting_name = _safe_greeting(yard_sign_request.first_name, "friend")
    plain_text_body = "\n".join(
        [
            f"Thanks so much for your support, {greeting_name}!",
            "",
            "I'm so glad you're requesting a yard sign to help spread the word for my campaign for Mankato Mayor!",
            "",
            "Check your inbox to coordinate sign delivery. We'll be in touch soon!",
            "",
            'If you plan to pay online, you can make a donation at https://voteforjulia.com/donate and write "yard sign" in the comment section.',
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
        ]
    )

    template_html = _YARD_SIGN_CONFIRMATION_TEMPLATE.read_text(encoding="utf-8")
    html_body = template_html.replace("{submission.name}", escape(greeting_name))

    return plain_text_body, html_body


def _build_yard_sign_confirmation_message(
    config: EmailConfig, yard_sign_request: YardSignRequest
) -> Message:
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


def send_yard_sign_confirmation_email(
    config: EmailConfig, yard_sign_request: YardSignRequest
) -> dict:
    msg = _build_yard_sign_confirmation_message(config, yard_sign_request)

    with _smtp_connection(config) as server:
        return _send_message(server, config.email_address, [yard_sign_request.email], msg)

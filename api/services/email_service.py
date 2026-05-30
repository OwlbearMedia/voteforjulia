from __future__ import annotations

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape
from pathlib import Path

from api.config import EmailConfig
from api.models import Submission


_CONFIRMATION_TEMPLATE_PATH = Path(__file__).resolve().parents[1] / "email-template.html"


def _build_submission_message(config: EmailConfig, submission: Submission) -> MIMEMultipart:
    msg = MIMEMultipart()
    msg["From"] = config.email_address
    msg["To"] = ", ".join(config.recipients)
    msg["Subject"] = f"New message from {submission.name}"
    msg["Reply-To"] = submission.email
    msg.attach(MIMEText(submission.to_email_body(), "plain"))
    return msg


def _build_confirmation_message(config: EmailConfig, submission: Submission) -> MIMEMultipart:
    msg = MIMEMultipart("alternative")
    msg["From"] = config.email_address
    msg["To"] = submission.email
    msg["Subject"] = "Thanks for reaching out to Julia Hamann for Mayor"

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

    template_html = _CONFIRMATION_TEMPLATE_PATH.read_text(encoding="utf-8")
    html_body = template_html.replace("{submission.name}", escape(greeting_name))

    msg.attach(MIMEText(plain_text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    return msg


def _send_message(server: smtplib.SMTP_SSL, from_address: str, recipients: list[str], message: MIMEMultipart) -> dict:
    return server.sendmail(from_address, recipients, message.as_string())


def send_submission_email(config: EmailConfig, submission: Submission) -> dict:
    msg = _build_submission_message(config, submission)

    with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port) as server:
        server.login(config.email_address, config.email_password)
        return _send_message(server, config.email_address, config.recipients, msg)


def send_confirmation_email(config: EmailConfig, submission: Submission) -> dict:
    msg = _build_confirmation_message(config, submission)

    with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port) as server:
        server.login(config.email_address, config.email_password)
        return _send_message(server, config.email_address, [submission.email], msg)

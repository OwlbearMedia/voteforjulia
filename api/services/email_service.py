import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.config import EmailConfig
from api.models import Submission


def send_submission_email(config: EmailConfig, submission: Submission) -> dict:
    msg = MIMEMultipart()
    msg["From"] = config.email_address
    msg["To"] = ", ".join(config.recipients)
    msg["Subject"] = f"New message from {submission.name}"
    msg["Reply-To"] = submission.email
    msg.attach(MIMEText(submission.to_email_body(), "plain"))

    with smtplib.SMTP_SSL(config.smtp_server, config.smtp_port) as server:
        server.login(config.email_address, config.email_password)
        return server.sendmail(config.email_address, config.recipients, msg.as_string())

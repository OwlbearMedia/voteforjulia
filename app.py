import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from flask import Flask, jsonify, request

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Email configuration
SMTP_SERVER = os.getenv("SMTP_SERVER", "mail.voteforjulia.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS", "")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL", "info@voteforjulia.com")


def _missing_email_config() -> bool:
    return not EMAIL_ADDRESS or not EMAIL_PASSWORD


def _get_field(name: str) -> str:
    return (request.form.get(name) or "").strip()


def _looks_like_email(value: str) -> bool:
    if "@" not in value:
        return False
    local_part, _, domain = value.partition("@")
    return bool(local_part and domain and "." in domain)

@app.route('/send-email', methods=['POST'])
def send_email():
    if _missing_email_config():
        logger.error("Email service not configured: missing EMAIL_ADDRESS or EMAIL_PASSWORD")
        return jsonify({'error': 'Email service is not configured.'}), 500

    try:
        # Get form data
        name = _get_field('name')
        email = _get_field('email')
        message = _get_field('message')

        if not name or not email or not message:
            return jsonify({'error': 'All fields are required.'}), 400

        if not _looks_like_email(email):
            return jsonify({'error': 'Please provide a valid email address.'}), 400

        # Create email message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_ADDRESS
        msg['To'] = RECIPIENT_EMAIL
        msg['Subject'] = f'New message from {name}'

        body = f"Name: {name}\nEmail: {email}\n\nMessage:\n{message}"
        msg.attach(MIMEText(body, 'plain'))

        # Send email
        with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
            server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
            server.sendmail(EMAIL_ADDRESS, RECIPIENT_EMAIL, msg.as_string())

        return jsonify({'message': 'Email sent successfully!'}), 200

    except smtplib.SMTPAuthenticationError:
        logger.exception("SMTP authentication failed")
        return jsonify({'error': 'Unable to send email right now.'}), 502
    except smtplib.SMTPException:
        logger.exception("SMTP error while sending email")
        return jsonify({'error': 'Unable to send email right now.'}), 502
    except ValueError:
        logger.exception("Invalid SMTP configuration")
        return jsonify({'error': 'Server email configuration is invalid.'}), 500

    except Exception:
        logger.exception("Unexpected error while handling /send-email")
        return jsonify({'error': 'Internal server error.'}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('PORT', '5000')), debug=False)
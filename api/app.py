from __future__ import annotations

import logging
import smtplib

from flask import Flask, jsonify, request

try:
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover - fallback for environments without google libs
    class HttpError(Exception):
        pass

from api.config import EmailConfig, env, load_email_config, load_sheets_config
from api.models import Submission, looks_like_email
from api.services.email_service import send_confirmation_email, send_submission_email
from api.services.sheets_service import append_row

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def _validate_email_config(config: EmailConfig) -> str:
    if not config.email_address or not config.email_password:
        return "Email service not configured: missing EMAIL_ADDRESS or EMAIL_PASSWORD"

    if not config.recipients:
        return "Email service not configured: missing RECIPIENT_EMAIL"

    if not all(looks_like_email(item) for item in config.recipients):
        return "Email service misconfigured: RECIPIENT_EMAIL contains invalid address"

    return ""


def _submission_from_request() -> Submission | None:
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return Submission.from_json(payload)

    if request.form:
        return Submission.from_form(request.form)

    return None


def _missing_required_fields_message(submission: Submission) -> str:
    missing_name = not submission.name
    missing_email = not submission.email

    if missing_name and missing_email:
        return 'First name and email are required.'
    if missing_name:
        return 'First name is required.'
    if missing_email:
        return 'Email is required.'

    return ''


@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'path': request.path,
        'script_root': request.script_root,
    }), 200

@app.route('/send-email', methods=['POST'])
@app.route('/api/send-email', methods=['POST'])
def send_email():
    email_config = load_email_config()
    sheets_config = load_sheets_config()

    config_error = _validate_email_config(email_config)
    if config_error:
        logger.error(config_error)
        return jsonify({'error': 'Email service is not configured.'}), 500

    try:
        submission = _submission_from_request()
        if submission is None:
            return jsonify({'error': 'Request body must be valid JSON or form data.'}), 400

        missing_fields_message = _missing_required_fields_message(submission)
        if missing_fields_message:
            return jsonify({'error': missing_fields_message}), 400

        if not looks_like_email(submission.email):
            return jsonify({'error': 'Please provide a valid email address.'}), 400

        refused = send_submission_email(email_config, submission)

        if refused:
            logger.error("SMTP refused recipients: %s", ", ".join(refused.keys()))
            return jsonify({'error': 'Unable to deliver email to recipient.'}), 502

        confirmation_refused = send_confirmation_email(email_config, submission)
        if confirmation_refused:
            logger.warning(
                "Confirmation email refused for %s",
                ", ".join(confirmation_refused.keys()),
            )

        logger.info(
            "Email accepted by SMTP for %d recipient(s)",
            len(email_config.recipients),
        )

        sheet_row = submission.to_sheet_row()

        try:
            append_row(sheets_config, sheet_row)
            if sheets_config.spreadsheet_id:
                logger.info("Submission appended to Google Sheet")
        except (ValueError, OSError, HttpError):
            logger.exception("Failed to append submission to Google Sheet")
            return jsonify({'error': 'Email sent, but failed to save submission.'}), 502

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
    app.run(host='127.0.0.1', port=int(env('PORT', '5000')), debug=False)

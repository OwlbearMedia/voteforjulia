from __future__ import annotations

from collections import deque
import logging
import smtplib
from time import monotonic

from flask import Flask, jsonify, request

try:
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover - fallback for environments without google libs
    class HttpError(Exception):
        pass

from api.config import (
    DEFAULT_YARDSIGN_SHEETS_WORKSHEET,
    EmailConfig,
    env,
    load_email_config,
    load_sheets_config,
)
from api.models import (
    Submission,
    YardSignRequest,
    looks_like_email,
    validate_submission,
    validate_yard_sign_request,
)
from api.services.email_service import (
    send_confirmation_email,
    send_submission_email,
    send_yard_sign_confirmation_email,
    send_yard_sign_request_email,
)
from api.services.sheets_service import append_row

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

_RATE_LIMIT_WINDOW_SECONDS = max(int(env('RATE_LIMIT_WINDOW_SECONDS', '60')), 1)
_RATE_LIMIT_MAX_REQUESTS = max(int(env('RATE_LIMIT_MAX_REQUESTS', '5')), 1)
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}

_CORS_ALLOWED_ORIGINS = {
    item.strip()
    for item in env(
        'CORS_ALLOWED_ORIGINS',
        (
            'https://voteforjulia.com,'
            'https://www.voteforjulia.com,'
            'https://test.voteforjulia.com,'
            'https://test-api.voteforjulia.com,'
            'http://localhost:5173'
        ),
    ).split(',')
    if item.strip()
}


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get('Origin', '').strip()
    if origin and origin in _CORS_ALLOWED_ORIGINS:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin'
        response.headers['Access-Control-Allow-Methods'] = 'POST, OPTIONS'
        response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
        response.headers['Access-Control-Max-Age'] = '86400'

    return response

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


def _is_blank(value: str) -> bool:
    # A value made up entirely of whitespace/control characters (e.g. a lone
    # "\n") should be treated as missing rather than falling through to a
    # "contains invalid characters" validation error.
    return not value.strip()


def _missing_required_fields_message(submission: Submission) -> str:
    missing_first_name = _is_blank(submission.first_name)
    missing_email = _is_blank(submission.email)

    if missing_first_name and missing_email:
        return 'First name and email are required.'
    if missing_first_name:
        return 'First name is required.'
    if missing_email:
        return 'Email is required.'

    return ''


def _yard_sign_request_from_request() -> YardSignRequest | None:
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return YardSignRequest.from_json(payload)

    if request.form:
        return YardSignRequest.from_form(request.form)

    return None


def _missing_required_yard_sign_fields_message(yard_sign_request: YardSignRequest) -> str:
    missing_labels = []
    if _is_blank(yard_sign_request.first_name):
        missing_labels.append('First name')
    if _is_blank(yard_sign_request.email):
        missing_labels.append('Email')
    if _is_blank(yard_sign_request.address):
        missing_labels.append('Address')

    if not missing_labels:
        return ''
    if len(missing_labels) == 1:
        return f'{missing_labels[0]} is required.'

    return f"{', '.join(missing_labels[:-1])} and {missing_labels[-1]} are required."


def _rate_limit_key() -> str:
    # Prefer CF-Connecting-IP: Cloudflare overwrites it on proxied requests, so
    # the client can't forge it. X-Forwarded-For is only a fallback, and only
    # its *last* hop counts — proxies append the connecting address to whatever
    # list the client sent, so the first hop is attacker-controlled and would
    # let a caller mint a fresh rate-limit bucket per request.
    connecting_ip = request.headers.get('CF-Connecting-IP', '').strip()
    if connecting_ip:
        return connecting_ip

    forwarded_for = request.headers.get('X-Forwarded-For', '')
    if forwarded_for:
        last_hop = forwarded_for.rsplit(',', 1)[-1].strip()
        if last_hop:
            return last_hop

    return request.remote_addr or 'unknown'


def _consume_rate_limit(scope: str) -> int | None:
    now = monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS

    # Prune every bucket, not just the current key's: one-off client addresses
    # would otherwise leave empty deques behind forever, growing the dict
    # without bound over the life of the process.
    for stale_key, stale_bucket in list(_RATE_LIMIT_BUCKETS.items()):
        while stale_bucket and stale_bucket[0] <= cutoff:
            stale_bucket.popleft()
        if not stale_bucket:
            del _RATE_LIMIT_BUCKETS[stale_key]

    key = f"{scope}:{_rate_limit_key()}"
    bucket = _RATE_LIMIT_BUCKETS.setdefault(key, deque())

    if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
        retry_after = max(1, int(bucket[0] + _RATE_LIMIT_WINDOW_SECONDS - now))
        return retry_after

    bucket.append(now)
    return None


_SMTP_UNAVAILABLE_MESSAGE = 'Unable to send email right now.'

# Generous relative to the forms' combined field limits, but keeps an
# oversized/hostile payload from flooding the logs.
_MAX_LOGGED_BODY_CHARS = 4096


def _log_request_body(endpoint_name: str) -> None:
    # The browser sends only redacted form data to New Relic (see
    # src/lib/analytics.ts), so this server-side log is the one place the
    # submitted values are recoverable if anything later in the handler fails.
    raw_body = request.get_data(as_text=True)
    if len(raw_body) > _MAX_LOGGED_BODY_CHARS:
        raw_body = raw_body[:_MAX_LOGGED_BODY_CHARS] + '…[truncated]'
    logger.info("%s request body: %s", endpoint_name, raw_body)


def _rate_limited_response(retry_after: int):
    response = jsonify({'error': 'Too many requests. Please try again later.'})
    response.status_code = 429
    response.headers['Retry-After'] = str(retry_after)
    return response


def _handle_form_submission(
    *,
    sheets_config,
    parse_request,
    missing_fields_message,
    validate,
    get_email,
    send_notification_email,
    send_confirmation_email_fn,
    to_sheet_row,
    endpoint_name,
):
    _log_request_body(endpoint_name)

    try:
        # Inside the try so a malformed SMTP_SECURITY/SMTP_PORT env value
        # (ValueError) produces the JSON 500 below, not Flask's HTML error page.
        email_config = load_email_config()

        config_error = _validate_email_config(email_config)
        if config_error:
            logger.error(config_error)
            return jsonify({'error': 'Email service is not configured.'}), 500

        parsed = parse_request()
        if parsed is None:
            return jsonify({'error': 'Request body must be valid JSON or form data.'}), 400

        missing_message = missing_fields_message(parsed)
        if missing_message:
            return jsonify({'error': missing_message}), 400

        validation_error = validate(parsed)
        if validation_error:
            return jsonify({'error': validation_error}), 400

        if not looks_like_email(get_email(parsed)):
            return jsonify({'error': 'Please provide a valid email address.'}), 400

        refused = send_notification_email(email_config, parsed)

        if refused:
            logger.error("SMTP refused recipients: %s", ", ".join(refused.keys()))
            return jsonify({'error': 'Unable to deliver email to recipient.'}), 502

        try:
            confirmation_refused = send_confirmation_email_fn(email_config, parsed)
            if confirmation_refused:
                logger.warning(
                    "Confirmation email refused for %s",
                    ", ".join(confirmation_refused.keys()),
                )
        except (smtplib.SMTPException, OSError):
            logger.exception("Failed to send confirmation email to %s", get_email(parsed))

        logger.info(
            "Email accepted by SMTP for %d recipient(s)",
            len(email_config.recipients),
        )

        sheet_row = to_sheet_row(parsed)

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
        return jsonify({'error': _SMTP_UNAVAILABLE_MESSAGE}), 502
    except smtplib.SMTPException:
        logger.exception("SMTP error while sending email")
        return jsonify({'error': _SMTP_UNAVAILABLE_MESSAGE}), 502
    except ValueError:
        logger.exception("Invalid SMTP configuration")
        return jsonify({'error': 'Server email configuration is invalid.'}), 500

    except Exception:
        logger.exception("Unexpected error while handling %s", endpoint_name)
        return jsonify({'error': 'Internal server error.'}), 500


@app.route('/health', methods=['GET'])
@app.route('/api/health', methods=['GET'])
def health_check():
    return jsonify({
        'status': 'ok',
        'path': request.path,
        'script_root': request.script_root,
    }), 200

@app.route('/send-email', methods=['POST', 'OPTIONS'])
@app.route('/api/send-email', methods=['POST', 'OPTIONS'])
def send_email():
    if request.method == 'OPTIONS':
        return ('', 204)

    retry_after = _consume_rate_limit('send-email')
    if retry_after is not None:
        return _rate_limited_response(retry_after)

    return _handle_form_submission(
        sheets_config=load_sheets_config(),
        parse_request=_submission_from_request,
        missing_fields_message=_missing_required_fields_message,
        validate=validate_submission,
        get_email=lambda submission: submission.email,
        send_notification_email=send_submission_email,
        send_confirmation_email_fn=send_confirmation_email,
        to_sheet_row=lambda submission: submission.to_sheet_row(),
        endpoint_name='/send-email',
    )

@app.route('/yard-sign', methods=['POST', 'OPTIONS'])
@app.route('/api/yard-sign', methods=['POST', 'OPTIONS'])
def yard_sign():
    if request.method == 'OPTIONS':
        return ('', 204)

    retry_after = _consume_rate_limit('yard-sign')
    if retry_after is not None:
        return _rate_limited_response(retry_after)

    return _handle_form_submission(
        sheets_config=load_sheets_config(
            'GOOGLE_SHEETS_YARDSIGN_WORKSHEET', DEFAULT_YARDSIGN_SHEETS_WORKSHEET
        ),
        parse_request=_yard_sign_request_from_request,
        missing_fields_message=_missing_required_yard_sign_fields_message,
        validate=validate_yard_sign_request,
        get_email=lambda yard_sign_request: yard_sign_request.email,
        send_notification_email=send_yard_sign_request_email,
        send_confirmation_email_fn=send_yard_sign_confirmation_email,
        to_sheet_row=lambda yard_sign_request: yard_sign_request.to_sheet_row(),
        endpoint_name='/yard-sign',
    )

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(env('PORT', '5000')), debug=False)

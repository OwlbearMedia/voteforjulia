"""Alternate and failure paths through the shared submission pipeline.

[api/test_app.py](test_app.py) covers the happy paths, CORS, rate limiting, and
input validation. This module covers what those left untested:

- the **form-encoded** submission path — the site's `<form>` elements post
  `application/x-www-form-urlencoded` directly to this API's origin when
  JavaScript is unavailable, and nothing exercised that branch;
- every failure branch of `_handle_form_submission` — misconfiguration, SMTP
  refusal and errors, confirmation-email failure, and Google Sheets failure.

Both endpoints funnel through `_handle_form_submission`, so the shared-behaviour
tests are parametrized across the two: that is what proves a failure is handled
identically whichever entry point produced it.

Written as plain pytest functions (see `test_openapi_spec.py`). The `pipeline`
fixture replaces the collaborators the handler calls out to, using monkeypatch
so restoration is automatic rather than hand-rolled in a `tearDown`.
"""

import logging
import smtplib
from dataclasses import replace

import httplib2
import pytest

import api.app as app_module
from api.config import EmailConfig, SheetsConfig

VALID_EMAIL_CONFIG = EmailConfig(
    smtp_server="mail.example.com",
    smtp_port=465,
    smtp_security="ssl",
    email_address="info@example.com",
    email_password="placeholder-value",
    recipients=["team@example.com"],
    plain_text_confirmation_only=False,
)

CONTACT_PATH = "/send-email"
CONTACT_PAYLOAD = {"firstName": "Julia", "email": "julia@example.com"}

YARD_SIGN_PATH = "/yard-sign"
YARD_SIGN_PAYLOAD = {
    "firstName": "Julia",
    "email": "julia@example.com",
    "address": "123 Main St, Mankato, MN 56001",
}

# Every test marked with this runs once per endpoint, confirming the shared
# handler behaves the same through either route.
BOTH_ENDPOINTS = pytest.mark.parametrize(
    ("path", "payload"),
    [
        pytest.param(CONTACT_PATH, CONTACT_PAYLOAD, id="send-email"),
        pytest.param(YARD_SIGN_PATH, YARD_SIGN_PAYLOAD, id="yard-sign"),
    ],
)


def http_error(status: int = 500) -> app_module.HttpError:
    """A googleapiclient HttpError, as raised by a failing Sheets append."""
    return app_module.HttpError(httplib2.Response({"status": status}), b"boom")


class Pipeline:
    """Controllable stand-ins for everything `_handle_form_submission` calls.

    Set an `*_error` to make that collaborator raise, or an `*_refused` dict to
    make it report refused recipients the way smtplib does. The lists record
    what actually got through, so a test can assert the pipeline stopped where
    it should have.
    """

    def __init__(self) -> None:
        self.email_config = VALID_EMAIL_CONFIG
        self.sheets_config = SheetsConfig(
            spreadsheet_id="",
            worksheet="Sheet1",
            service_account_file="",
            service_account_json="",
        )
        self.notify_refused: dict = {}
        self.notify_error: Exception | None = None
        self.confirm_refused: dict = {}
        self.confirm_error: Exception | None = None
        self.append_error: Exception | None = None

        self.notifications: list = []
        self.confirmations: list = []
        self.rows: list = []
        self.recipient_envs: list[str] = []


@pytest.fixture
def pipeline(monkeypatch):
    state = Pipeline()

    def load_email_config(recipient_env="RECIPIENT_EMAIL"):
        state.recipient_envs.append(recipient_env)
        return state.email_config

    def load_sheets_config(*_args, **_kwargs):
        return state.sheets_config

    def send_notification(_config, parsed):
        if state.notify_error is not None:
            raise state.notify_error
        state.notifications.append(parsed)
        return state.notify_refused

    def send_confirmation(_config, parsed):
        if state.confirm_error is not None:
            raise state.confirm_error
        state.confirmations.append(parsed)
        return state.confirm_refused

    def append_row(_config, row):
        if state.append_error is not None:
            raise state.append_error
        state.rows.append(row)

    monkeypatch.setattr(app_module, "load_email_config", load_email_config)
    monkeypatch.setattr(app_module, "load_sheets_config", load_sheets_config)
    monkeypatch.setattr(app_module, "send_submission_email", send_notification)
    monkeypatch.setattr(app_module, "send_yard_sign_request_email", send_notification)
    monkeypatch.setattr(app_module, "send_confirmation_email", send_confirmation)
    monkeypatch.setattr(app_module, "send_yard_sign_confirmation_email", send_confirmation)
    monkeypatch.setattr(app_module, "append_row", append_row)

    # Rate limiting has its own tests; keep it from interfering here.
    monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})
    monkeypatch.setattr(app_module, "_RATE_LIMIT_MAX_REQUESTS", 1000)

    return state


@pytest.fixture
def client():
    return app_module.app.test_client()


# --------------------------------------------------------------------------
# Form-encoded submissions (the no-JavaScript fallback)
# --------------------------------------------------------------------------


@BOTH_ENDPOINTS
def test_form_encoded_submission_is_accepted(client, pipeline, path, payload):
    response = client.post(path, data=payload)

    assert response.status_code == 200
    assert response.get_json() == {"message": "Email sent successfully!"}
    assert len(pipeline.notifications) == 1
    assert pipeline.notifications[0].email == "julia@example.com"
    assert pipeline.notifications[0].first_name == "Julia"
    assert len(pipeline.rows) == 1


def test_form_encoded_repeated_help_ways_are_collected(client, pipeline):
    # Checkboxes post the same name once per checked box, which is why the
    # parser reads `helpWays[]` with getlist rather than get.
    response = client.post(
        CONTACT_PATH,
        data={
            "firstName": "Julia",
            "email": "julia@example.com",
            # A list value posts the field once per entry, which is what a set
            # of checked checkboxes sends.
            "helpWays[]": ["Canvassing", "Events"],
        },
    )

    assert response.status_code == 200
    assert pipeline.notifications[0].help_ways == ["Canvassing", "Events"]


def test_form_encoded_repeated_preferred_payment_is_collected(client, pipeline):
    response = client.post(
        YARD_SIGN_PATH,
        data={
            "firstName": "Julia",
            "email": "julia@example.com",
            "address": "123 Main St",
            "preferredPayment[]": ["Cash", "Check"],
        },
    )

    assert response.status_code == 200
    assert pipeline.notifications[0].preferred_payment == ["Cash", "Check"]


@BOTH_ENDPOINTS
def test_body_that_is_neither_json_nor_form_is_rejected(client, pipeline, path, payload):
    response = client.post(path, data="", content_type="application/json")

    assert response.status_code == 400
    assert response.get_json() == {"error": "Request body must be valid JSON or form data."}
    assert pipeline.notifications == []
    assert pipeline.rows == []


# --------------------------------------------------------------------------
# Email misconfiguration
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("bad_config", "expected_log"),
    [
        pytest.param(
            replace(VALID_EMAIL_CONFIG, email_address=""),
            "missing EMAIL_ADDRESS or EMAIL_PASSWORD",
            id="no-address",
        ),
        pytest.param(
            replace(VALID_EMAIL_CONFIG, email_password=""),
            "missing EMAIL_ADDRESS or EMAIL_PASSWORD",
            id="no-password",
        ),
        pytest.param(
            replace(VALID_EMAIL_CONFIG, recipients=[]),
            "missing RECIPIENT_EMAIL",
            id="no-recipients",
        ),
        pytest.param(
            replace(VALID_EMAIL_CONFIG, recipients=["not-an-address"]),
            "contains invalid address",
            id="unparseable-recipient",
        ),
    ],
)
def test_misconfigured_email_returns_500(client, pipeline, caplog, bad_config, expected_log):
    pipeline.email_config = bad_config

    with caplog.at_level(logging.ERROR, logger="api.app"):
        response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == 500
    assert response.get_json() == {"error": "Email service is not configured."}
    # The response is deliberately vague; the specific cause only reaches the log.
    assert expected_log in caplog.text
    assert pipeline.notifications == []


def test_config_is_checked_before_the_body_is_parsed(client, pipeline):
    # Documented in openapi.yaml: a misconfigured deployment returns 500 even
    # for a payload that would otherwise be a 400.
    pipeline.email_config = replace(VALID_EMAIL_CONFIG, email_address="")

    response = client.post(CONTACT_PATH, data="", content_type="application/json")

    assert response.status_code == 500


def test_yard_sign_uses_its_own_recipient_env(client, pipeline, caplog):
    pipeline.email_config = replace(VALID_EMAIL_CONFIG, recipients=[])

    with caplog.at_level(logging.ERROR, logger="api.app"):
        response = client.post(YARD_SIGN_PATH, json=YARD_SIGN_PAYLOAD)

    assert response.status_code == 500
    assert pipeline.recipient_envs == ["RECIPIENT_EMAIL_SIGNS"]
    assert "missing RECIPIENT_EMAIL_SIGNS" in caplog.text


# --------------------------------------------------------------------------
# Required-field messages
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param({"email": "julia@example.com"}, "First name is required.", id="no-first-name"),
        pytest.param({"firstName": "Julia"}, "Email is required.", id="no-email"),
        pytest.param({}, "First name and email are required.", id="neither"),
        pytest.param(
            {"firstName": " \t ", "email": "julia@example.com"},
            "First name is required.",
            id="whitespace-only-first-name",
        ),
    ],
)
def test_contact_required_field_messages(client, pipeline, payload, expected):
    response = client.post(CONTACT_PATH, json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": expected}


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        pytest.param(
            {"email": "julia@example.com", "address": "123 Main St"},
            "First name is required.",
            id="one-missing",
        ),
        pytest.param(
            {"address": "123 Main St"},
            "First name and Email are required.",
            id="two-missing",
        ),
        pytest.param(
            {},
            "First name, Email and Address are required.",
            id="all-three-missing",
        ),
    ],
)
def test_yard_sign_required_field_messages(client, pipeline, payload, expected):
    response = client.post(YARD_SIGN_PATH, json=payload)

    assert response.status_code == 400
    assert response.get_json() == {"error": expected}


# --------------------------------------------------------------------------
# Notification email failures
# --------------------------------------------------------------------------


@BOTH_ENDPOINTS
def test_refused_recipients_return_502_and_skip_the_sheet(client, pipeline, path, payload):
    pipeline.notify_refused = {"team@example.com": (550, b"mailbox unavailable")}

    response = client.post(path, json=payload)

    assert response.status_code == 502
    assert response.get_json() == {"error": "Unable to deliver email to recipient."}
    # The submission never reached the notification inbox, so it must not be
    # recorded as received either.
    assert pipeline.rows == []


@pytest.mark.parametrize(
    ("error", "status", "message"),
    [
        pytest.param(
            smtplib.SMTPAuthenticationError(535, b"bad credentials"),
            502,
            "Unable to send email right now.",
            id="auth-error",
        ),
        pytest.param(
            smtplib.SMTPException("connection reset"),
            502,
            "Unable to send email right now.",
            id="smtp-error",
        ),
        pytest.param(
            ValueError("SMTP_PORT is not a number"),
            500,
            "Server email configuration is invalid.",
            id="value-error",
        ),
        pytest.param(
            RuntimeError("something nobody anticipated"),
            500,
            "Internal server error.",
            id="unexpected-error",
        ),
    ],
)
def test_notification_email_errors_map_to_responses(client, pipeline, error, status, message):
    pipeline.notify_error = error

    response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == status
    assert response.get_json() == {"error": message}
    assert pipeline.rows == []


# --------------------------------------------------------------------------
# Confirmation email failures must NOT fail the request
# --------------------------------------------------------------------------


@BOTH_ENDPOINTS
def test_refused_confirmation_still_succeeds(client, pipeline, caplog, path, payload):
    pipeline.confirm_refused = {"julia@example.com": (550, b"mailbox unavailable")}

    with caplog.at_level(logging.WARNING, logger="api.app"):
        response = client.post(path, json=payload)

    # The campaign got the submission; failing to thank the submitter is not a
    # reason to tell them it didn't go through.
    assert response.status_code == 200
    assert "Confirmation email refused" in caplog.text
    assert len(pipeline.rows) == 1


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(smtplib.SMTPException("confirmation blew up"), id="smtp-error"),
        pytest.param(OSError("socket closed"), id="os-error"),
    ],
)
def test_confirmation_exception_still_succeeds(client, pipeline, caplog, error):
    pipeline.confirm_error = error

    with caplog.at_level(logging.ERROR, logger="api.app"):
        response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == 200
    assert "Failed to send confirmation email" in caplog.text
    assert len(pipeline.rows) == 1


# --------------------------------------------------------------------------
# Google Sheets
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(ValueError("worksheet gid not found"), id="value-error"),
        pytest.param(OSError("network unreachable"), id="os-error"),
        pytest.param(http_error(), id="http-error"),
    ],
)
def test_sheet_append_failure_returns_502_after_the_email_sent(client, pipeline, error):
    pipeline.append_error = error

    response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == 502
    assert response.get_json() == {"error": "Email sent, but failed to save submission."}
    # Partial success: the notification did go out before the sheet failed.
    assert len(pipeline.notifications) == 1


def test_successful_append_is_logged_when_a_spreadsheet_is_configured(client, pipeline, caplog):
    pipeline.sheets_config = replace(pipeline.sheets_config, spreadsheet_id="sheet-123")

    with caplog.at_level(logging.INFO, logger="api.app"):
        response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == 200
    assert "Submission appended to Google Sheet" in caplog.text


def test_no_sheet_log_when_no_spreadsheet_is_configured(client, pipeline, caplog):
    with caplog.at_level(logging.INFO, logger="api.app"):
        response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == 200
    assert "Submission appended to Google Sheet" not in caplog.text


# --------------------------------------------------------------------------
# Field-name logging (PII-safe) and rate-limit keying
# --------------------------------------------------------------------------


def test_non_string_field_values_are_counted_as_submitted(client, pipeline, caplog):
    # `_has_content` treats anything that is not None and not False as filled
    # in, so a numeric 0 counts but an unchecked boolean does not. Only names
    # are logged, never values.
    with caplog.at_level(logging.INFO, logger="api.app"):
        client.post(
            CONTACT_PATH,
            json={
                "firstName": "Julia",
                "email": "julia@example.com",
                "subscribe": True,
                "optOut": False,
                "nothing": None,
                "zero": 0,
            },
        )

    assert "submission fields: email, firstName, subscribe, zero" in caplog.text
    assert "julia@example.com" not in caplog.text


def test_yard_sign_is_rate_limited_separately(client, pipeline, monkeypatch):
    monkeypatch.setattr(app_module, "_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})
    headers = {"X-Forwarded-For": "203.0.113.99"}

    first = client.post(YARD_SIGN_PATH, json=YARD_SIGN_PAYLOAD, headers=headers)
    second = client.post(YARD_SIGN_PATH, json=YARD_SIGN_PAYLOAD, headers=headers)

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.get_json() == {"error": "Too many requests. Please try again later."}
    assert int(second.headers["Retry-After"]) >= 1
    # Scoped per endpoint, so the contact form is unaffected.
    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD, headers=headers).status_code == 200


def test_distinct_last_forwarded_hops_get_separate_buckets(client, pipeline, monkeypatch):
    """Pins that the last hop actually *keys* the bucket.

    `test_app.py`'s spoofing test sends two requests that share a last hop and
    expects them to collide — but that also passes if X-Forwarded-For were
    ignored outright, since both would then fall back to the same remote_addr.
    Deleting the whole X-Forwarded-For branch kept the rest of the suite green.
    This is the other half of the property: different last hops must not share
    a bucket.

    The header has to be trusted explicitly now. That is the point of
    ADR-0014 — untrusted is the default, because with nothing in front of the
    app the header is only ever the caller's own claim.
    """
    monkeypatch.setattr(app_module, "_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})
    monkeypatch.setattr(app_module, "_TRUSTED_CLIENT_IP_HEADER", "X-Forwarded-For")
    monkeypatch.setattr(app_module, "_next_bucket_sweep_at", 0.0)

    first = client.post(
        CONTACT_PATH, json=CONTACT_PAYLOAD, headers={"X-Forwarded-For": "198.51.100.1"}
    )
    second = client.post(
        CONTACT_PATH, json=CONTACT_PAYLOAD, headers={"X-Forwarded-For": "10.0.0.9, 198.51.100.2"}
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert sorted(app_module._RATE_LIMIT_BUCKETS) == [
        "send-email:198.51.100.1",
        "send-email:198.51.100.2",
    ]


def test_empty_last_forwarded_hop_falls_back_to_remote_addr(client, pipeline, monkeypatch):
    monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})
    monkeypatch.setattr(app_module, "_TRUSTED_CLIENT_IP_HEADER", "X-Forwarded-For")
    monkeypatch.setattr(app_module, "_next_bucket_sweep_at", 0.0)
    # A trailing comma leaves no usable last hop; the socket address is used
    # rather than trusting the attacker-controlled earlier entries.
    client.post(
        CONTACT_PATH,
        json=CONTACT_PAYLOAD,
        headers={"X-Forwarded-For": "203.0.113.5,"},
    )

    assert list(app_module._RATE_LIMIT_BUCKETS) == ["send-email:127.0.0.1"]

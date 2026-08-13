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
import re
import smtplib
from dataclasses import replace
from pathlib import Path

import httplib2
import pytest

import api.app as app_module
import api.rate_limit_store as rate_limit_store
from api.config import (
    DEFAULT_SHEETS_TIMEOUT_SECONDS,
    DEFAULT_SMTP_TIMEOUT_SECONDS,
    EmailConfig,
    SheetsConfig,
)

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


# --- Second-tier (long-window) rate limiting, ADR-0016 ----------------------
#
# The burst tier stays at its shipped 5/60s throughout, so anything that 429s
# here was refused by the hour-scale tier. Tightening both would make these
# tests pass regardless of which tier did the work.


def test_a_caller_under_the_burst_limit_is_still_stopped_by_the_long_window(
    client, pipeline, monkeypatch
):
    """The gap that let the 2026-08-10 abuse through.

    That traffic never exceeded three requests in a minute, so the per-minute
    limiter could not fire once. Four requests in four separate minutes is the
    same shape: each inside the burst allowance, the fourth still refused.
    """
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_MAX_REQUESTS", 3)
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_WINDOW_SECONDS", 3600)

    statuses = []
    for _minute in range(4):
        # A fresh burst bucket each time, which is what a caller pacing itself
        # minutes apart gets for free — the 60-second window has emptied.
        monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})
        monkeypatch.setattr(app_module, "_next_bucket_sweep_at", 0.0)
        statuses.append(client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code)

    assert statuses == [200, 200, 200, 429]
    # And the refusal happened before any of the expensive work.
    assert len(pipeline.notifications) == 3
    assert len(pipeline.confirmations) == 3
    assert len(pipeline.rows) == 3


def test_long_window_429_carries_a_retry_after_and_the_standard_body(client, pipeline, monkeypatch):
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_WINDOW_SECONDS", 3600)

    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200
    refused = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert refused.status_code == 429
    assert refused.get_json() == {"error": "Too many requests. Please try again later."}
    # Up to a full window, never zero or negative, and never past the window.
    assert 1 <= int(refused.headers["Retry-After"]) <= 3600


def test_long_window_is_scoped_per_endpoint(client, pipeline, monkeypatch):
    """Exhausting the contact form must not lock out the yard-sign form.

    Pins that the persistent tier inherits the burst tier's `{endpoint}:{client}`
    key instead of collapsing both forms into one hourly allowance.
    """
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_WINDOW_SECONDS", 3600)

    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200
    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 429
    assert client.post(YARD_SIGN_PATH, json=YARD_SIGN_PAYLOAD).status_code == 200


def test_burst_refusals_do_not_spend_the_hourly_allowance(client, pipeline, monkeypatch):
    """A 429 from the burst tier must not also be counted by the long one.

    Otherwise an accidental double-click burns hourly budget on requests that
    were never served.
    """
    monkeypatch.setattr(app_module, "_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})
    monkeypatch.setattr(app_module, "_next_bucket_sweep_at", 0.0)
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_MAX_REQUESTS", 3)
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_WINDOW_SECONDS", 3600)

    # One served, then four refused by the burst tier in the same window.
    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200
    for _ in range(4):
        assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 429

    # The hourly tier has seen exactly one request, so two more are available
    # once the burst window clears.
    monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})
    monkeypatch.setattr(app_module, "_next_bucket_sweep_at", 0.0)
    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200


def test_an_unusable_store_leaves_the_endpoint_working(client, pipeline, monkeypatch, tmp_path):
    """Fail open, end to end.

    `test_rate_limit_store.py` proves `consume` returns None on a broken database;
    this is the part a supporter notices — the sign-up still goes through.
    """
    broken = tmp_path / "not-a-database"
    broken.mkdir()
    monkeypatch.setattr(rate_limit_store, "DEFAULT_DB_PATH", broken)

    response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == 200
    assert len(pipeline.notifications) == 1


# --- Honeypot, ADR-0016 -----------------------------------------------------


@BOTH_ENDPOINTS
def test_a_filled_honeypot_is_refused_before_any_work(client, pipeline, path, payload):
    response = client.post(path, json={**payload, "referralCode": "https://spam.example"})

    assert response.status_code == 400
    assert "info@voteforjulia.com" in response.get_json()["error"]
    # The whole point: no mail to the campaign, no confirmation to whatever
    # address the caller supplied, and no row in the volunteers' sheet.
    assert pipeline.notifications == []
    assert pipeline.confirmations == []
    assert pipeline.rows == []


@BOTH_ENDPOINTS
def test_an_empty_honeypot_is_indistinguishable_from_an_absent_one(client, pipeline, path, payload):
    """The negative case, without which the test above proves nothing.

    Every real submission carries this field blank, so a check testing presence
    rather than content would 400 the whole site.
    """
    assert client.post(path, json={**payload, "referralCode": ""}).status_code == 200
    assert client.post(path, json={**payload, "referralCode": "   "}).status_code == 200
    assert client.post(path, json=payload).status_code == 200

    assert len(pipeline.notifications) == 3


@pytest.mark.parametrize(
    "blank",
    [
        pytest.param("\n", id="newline"),
        pytest.param("\r\n", id="crlf"),
        pytest.param("\t", id="tab"),
        pytest.param("\u00a0", id="non-breaking-space"),
        pytest.param(" \n\t ", id="mixed"),
    ],
)
def test_whitespace_only_honeypot_values_count_as_blank(client, pipeline, blank):
    """Every flavour of whitespace, not just the ones `normalize_text` strips.

    Caught by Copilot on PR #134. The check used to be a plain truthiness test
    on `normalize_text`, which strips only spaces and tabs -- so a lone newline
    or a non-breaking space read as a filled honeypot and rejected the
    submission. A pasted value or an odd keyboard layout is enough to produce
    one, and the person could not see the field to clear it.
    """
    response = client.post(CONTACT_PATH, json={**CONTACT_PAYLOAD, "referralCode": blank})

    assert response.status_code == 200
    assert len(pipeline.notifications) == 1


def test_a_filled_honeypot_is_caught_on_the_form_encoded_path(client, pipeline):
    """The encoding every one of the 2026-08-10 requests actually used.

    All 36 were form-encoded while the site's scripted path posts JSON, so a
    JSON-only check would have missed the whole attack it was written for.
    """
    response = client.post(
        CONTACT_PATH,
        data={**CONTACT_PAYLOAD, "referralCode": "buy-cheap-things"},
        content_type="application/x-www-form-urlencoded",
    )

    assert response.status_code == 400
    assert pipeline.notifications == []


def test_a_filled_honeypot_logs_the_body_so_a_false_positive_is_recoverable(
    client, pipeline, caplog
):
    """A person tripping this must not vanish silently.

    The field is invisible, so they cannot fix the form. The response tells them
    to email; this log line is how the campaign finds them if they do not.
    """
    with caplog.at_level(logging.WARNING):
        client.post(CONTACT_PATH, json={**CONTACT_PAYLOAD, "referralCode": "x"})

    assert "honeypot" in caplog.text
    assert "julia@example.com" in caplog.text, "the body is logged, so nothing is lost"


def test_the_honeypot_can_be_disabled_without_a_deploy(client, pipeline, monkeypatch, caplog):
    """The kill switch, for the day it rejects someone real.

    Unenforced still logs, so turning it off answers whether it was catching
    bots or catching people.
    """
    monkeypatch.setattr(app_module, "_HONEYPOT_ENFORCED", False)

    with caplog.at_level(logging.WARNING):
        response = client.post(CONTACT_PATH, json={**CONTACT_PAYLOAD, "referralCode": "x"})

    assert response.status_code == 200
    assert len(pipeline.notifications) == 1
    assert "honeypot" in caplog.text


# --- Origin trust boundary, ADR-0017 ----------------------------------------


SITE_ORIGIN = "https://voteforjulia.com"


@pytest.fixture
def allowed_origins(monkeypatch):
    """Pin the allowlist so these tests do not depend on `CORS_ALLOWED_ORIGINS`.

    The set is built from the environment at import, so a developer shell that
    exports the variable would otherwise change what these tests mean.
    """
    monkeypatch.setattr(app_module, "_CORS_ALLOWED_ORIGINS", {SITE_ORIGIN})


@pytest.mark.parametrize(
    "origin",
    [
        pytest.param("https://evil.example", id="unrelated-site"),
        # The reason this is a set membership test and not a substring or
        # suffix one. Both of these contain the real origin's text.
        pytest.param("https://voteforjulia.com.evil.example", id="suffix-lookalike"),
        pytest.param("https://evil.example/?https://voteforjulia.com", id="prefix-lookalike"),
        # What a sandboxed iframe or a `data:` URL sends. No supporter submits
        # from one, and it must not be read as "no origin".
        pytest.param("null", id="opaque-origin"),
        # Same host, wrong scheme: a page served over plain HTTP is a page an
        # active network attacker wrote.
        pytest.param("http://voteforjulia.com", id="insecure-scheme"),
    ],
)
def test_a_cross_site_submission_is_refused_before_any_work(
    client, pipeline, allowed_origins, origin
):
    response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD, headers={"Origin": origin})

    assert response.status_code == 403
    assert "info@voteforjulia.com" in response.get_json()["error"]
    # The point of doing this before anything else: no mail to the campaign, no
    # confirmation to whatever address the page supplied, no row in the sheet.
    assert pipeline.notifications == []
    assert pipeline.confirmations == []
    assert pipeline.rows == []


@BOTH_ENDPOINTS
def test_a_same_site_submission_is_accepted(client, pipeline, allowed_origins, path, payload):
    """The negative case, without which the test above proves nothing.

    Every scripted submission the site makes carries this header, so a check
    that rejected on presence rather than on value would take both forms down.
    """
    response = client.post(path, json=payload, headers={"Origin": SITE_ORIGIN})

    assert response.status_code == 200
    assert len(pipeline.notifications) == 1


def test_a_cross_site_form_post_is_refused(client, pipeline, allowed_origins):
    """The encoding that made this reachable in the first place.

    A form-encoded POST is a CORS simple request: the browser sends it with no
    preflight, so nothing consults the allowlist before it arrives. It is also
    the encoding all 36 recorded requests of the 2026-08-10 abuse used.
    """
    response = client.post(
        CONTACT_PATH,
        data=CONTACT_PAYLOAD,
        content_type="application/x-www-form-urlencoded",
        headers={"Origin": "https://evil.example"},
    )

    assert response.status_code == 403
    assert pipeline.notifications == []


def test_a_submission_with_no_origin_header_is_accepted(client, pipeline, allowed_origins):
    """Absent is not foreign, and that is deliberate.

    Only browsers attach `Origin`. curl, a monitor and anything server-side send
    none, and those are precisely the callers per-IP rate limiting does bound.
    Rejecting them would buy nothing and break every scripted client.
    """
    response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == 200
    assert len(pipeline.notifications) == 1


def test_a_cross_site_flood_does_not_spend_a_victims_rate_limit(
    client, pipeline, allowed_origins, monkeypatch
):
    """The reason the check runs ahead of the limiter.

    A cross-site attack arrives on its victims' addresses. If a rejected request
    consumed a bucket, the attacker would spend the allowance of the very people
    whose browsers were conscripted -- so a supporter who then submitted the form
    themselves would be turned away by a limit they never approached.
    """
    monkeypatch.setattr(app_module, "_RATE_LIMIT_MAX_REQUESTS", 3)
    monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})

    for _ in range(10):
        rejected = client.post(
            CONTACT_PATH, json=CONTACT_PAYLOAD, headers={"Origin": "https://evil.example"}
        )
        assert rejected.status_code == 403

    response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD, headers={"Origin": SITE_ORIGIN})

    assert response.status_code == 200, "the rejections should have cost this client nothing"
    assert len(pipeline.notifications) == 1


def test_a_rejected_origin_is_logged_without_the_body(client, pipeline, allowed_origins, caplog):
    """Logged, but not the way the honeypot logs.

    The honeypot dumps the body because a false positive there is a real person
    whose submission is otherwise lost. This path cannot afford that: it runs
    before the limiter, so nothing bounds how many times an attacker can reach
    it, and a body dump per request would be a way to fill the disk. The origin
    alone is what makes the kill switch usable, and it is bounded text.
    """
    with caplog.at_level(logging.WARNING):
        client.post(
            CONTACT_PATH,
            json={**CONTACT_PAYLOAD, "message": "unique-body-marker"},
            headers={"Origin": "https://evil.example"},
        )

    assert "https://evil.example" in caplog.text
    assert "unique-body-marker" not in caplog.text
    assert "julia@example.com" not in caplog.text


def test_an_oversized_origin_is_truncated_before_it_reaches_the_log(
    client, pipeline, allowed_origins, caplog
):
    """The header is attacker-chosen text on its way to a log file.

    Asserts the line is written *and* bounded. A bare length check passes just
    as well when nothing is logged at all, so on its own it would go green the
    day the rejection stopped happening.
    """
    with caplog.at_level(logging.WARNING):
        client.post(
            CONTACT_PATH,
            json=CONTACT_PAYLOAD,
            headers={"Origin": "https://" + "a" * 4000 + ".example"},
        )

    assert "rejected a submission from origin" in caplog.text
    assert "a" * 4000 not in caplog.text
    assert len(caplog.text) < 1000


def test_the_origin_check_can_be_disabled_without_a_deploy(
    client, pipeline, allowed_origins, monkeypatch, caplog
):
    """The kill switch, for the day it rejects someone real.

    Unenforced still logs, so turning it off answers whether it was catching
    attackers or catching people -- the same bargain `HONEYPOT_ENFORCED` makes.
    """
    monkeypatch.setattr(app_module, "_ORIGIN_ENFORCED", False)

    with caplog.at_level(logging.WARNING):
        response = client.post(
            CONTACT_PATH, json=CONTACT_PAYLOAD, headers={"Origin": "https://evil.example"}
        )

    assert response.status_code == 200
    assert len(pipeline.notifications) == 1
    assert "https://evil.example" in caplog.text


# --- /health/deep's own hourly allowance, ADR-0016 ---------------------------


def test_health_deep_has_a_larger_hourly_allowance_than_the_forms(client, pipeline, monkeypatch):
    """The scopes must not share a number.

    Caught by Copilot on PR #134: the persistent tier initially applied the
    forms' allowance to `/health/deep` too. A monitor polls on a schedule, so
    the forms' figure -- sized against "a supporter submits one form once" --
    would 429 it on a cadence that is entirely legitimate, and a 429 there is a
    false page rather than a blocked spammer.

    Asserts on "was it rate limited", not on the status code: the probes fail in
    a test environment with no SMTP or Sheets, so a served request is a 503.
    That is the property under test either way.
    """
    monkeypatch.setattr(app_module, "_LONG_RATE_LIMIT_MAX_REQUESTS", 1)
    monkeypatch.setattr(app_module, "_HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS", 5)
    # Keep the probes off the network; this test is about the limiter.
    monkeypatch.setattr(app_module, "verify_smtp_credentials", lambda config: None)
    monkeypatch.setattr(app_module, "verify_sheets_access", lambda config: None)

    def probe():
        monkeypatch.setattr(app_module, "_RATE_LIMIT_BUCKETS", {})
        monkeypatch.setattr(app_module, "_next_bucket_sweep_at", 0.0)
        return client.get("/health/deep").status_code

    # The form allowance is exhausted after one request; the health scope keeps
    # going, which is only true if the two are looked up separately.
    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200
    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 429
    assert [probe() for _ in range(5)] == [200] * 5
    assert probe() == 429


def test_health_deep_allowance_fits_the_synthetic_monitor():
    """The shipped defaults must leave the real monitor headroom.

    Reads the period straight out of `monitoring/alerts.graphql` rather than
    restating it, so shortening the monitor without raising the allowance fails
    here instead of paging with a 429 that looks like an outage. The monitor
    runs from two locations, and the worst case is both egressing from one
    address, so the arithmetic assumes they share a bucket.

    Parsed from the production monitor's own block, located by the name it
    creates -- an earlier version took the first period in the file, which meant
    a period New Relic spells without a trailing "S" (`EVERY_MINUTE`) silently
    matched the *test* monitor instead and the assertion passed regardless.

    `monitoring/` drifts silently against the live account (docs/monitoring.md),
    so this pins the checked-in intent -- it cannot see a change made in the UI.
    """
    graphql = (Path(__file__).resolve().parent.parent / "monitoring" / "alerts.graphql").read_text()

    # Every period enum New Relic accepts, in minutes. A value outside this map
    # fails loudly below rather than being skipped by a regex that misses it.
    period_minutes = {
        "EVERY_MINUTE": 1,
        "EVERY_5_MINUTES": 5,
        "EVERY_10_MINUTES": 10,
        "EVERY_15_MINUTES": 15,
        "EVERY_30_MINUTES": 30,
        "EVERY_HOUR": 60,
        "EVERY_6_HOURS": 360,
        "EVERY_12_HOURS": 720,
        "EVERY_DAY": 1440,
    }

    production = re.search(r'name: "voteforjulia-api /health/deep".*?\n    \}', graphql, re.DOTALL)
    assert production, "could not find the production monitor block in alerts.graphql"
    block = production.group(0)

    period = re.search(r"period: (\w+)", block)
    assert period, "the production monitor declares no period"
    assert period.group(1) in period_minutes, (
        f"unrecognised monitor period {period.group(1)!r} -- add it to period_minutes"
    )

    locations = re.search(r"locations: \{ public: \[([^\]]*)\]", block)
    assert locations, "the production monitor declares no locations"

    checks_per_hour = (60 / period_minutes[period.group(1)]) * len(locations.group(1).split(","))

    assert checks_per_hour * 2 <= app_module._HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS, (
        f"the production monitor makes {checks_per_hour:.0f} checks/hour "
        f"({period.group(1)} x {len(locations.group(1).split(','))} locations), which leaves no "
        f"margin under an allowance of {app_module._HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS}/hour -- "
        "raise HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS or lengthen the period"
    )


# --- Concurrent-submission cap, ADR-0018 ------------------------------------


@BOTH_ENDPOINTS
def test_a_submission_is_refused_when_every_slot_is_held(
    client, pipeline, monkeypatch, path, payload
):
    monkeypatch.setattr(app_module, "_MAX_CONCURRENT_SUBMISSIONS", 0)

    response = client.post(path, json=payload)

    assert response.status_code == 503
    assert response.headers["Retry-After"] == str(app_module._AT_CAPACITY_RETRY_AFTER_SECONDS)
    # Refused before the work, not during it: no mail, no sheet row.
    assert pipeline.notifications == []
    assert pipeline.rows == []


def test_a_finished_submission_gives_its_slot_back(client, pipeline, monkeypatch):
    """Without a release, the cap would ratchet shut one submission at a time.

    A single slot plus two sequential submissions is the smallest arrangement
    that can tell "released" apart from "never taken": the second can only
    succeed if the first gave its slot back.
    """
    monkeypatch.setattr(app_module, "_MAX_CONCURRENT_SUBMISSIONS", 1)

    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200
    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200

    assert len(pipeline.notifications) == 2


def test_a_failed_submission_gives_its_slot_back(client, pipeline, monkeypatch):
    """The `finally` clause, which is the half that matters under an outage.

    A slow or failing SMTP server is exactly when the cap fills, so a slot
    leaked on the error path would take the forms down for `INFLIGHT_TTL_SECONDS`
    on top of whatever broke -- turning an upstream blip into a longer outage of
    our own making.
    """
    monkeypatch.setattr(app_module, "_MAX_CONCURRENT_SUBMISSIONS", 1)
    pipeline.notify_error = smtplib.SMTPException("mail server is down")

    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 502

    pipeline.notify_error = None

    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200


def test_the_cap_counts_submissions_not_rejected_requests(client, pipeline, monkeypatch):
    """A request refused before the handler must not hold a slot.

    Rate-limited and cross-site requests are refused ahead of this, so a flood
    of them cannot exhaust the cap and lock out the submissions it exists to
    protect. Uses a cap of 1 and a rejected request that would, if it consumed
    a slot, leave nothing for the legitimate one behind it.
    """
    monkeypatch.setattr(app_module, "_MAX_CONCURRENT_SUBMISSIONS", 1)
    monkeypatch.setattr(app_module, "_CORS_ALLOWED_ORIGINS", {SITE_ORIGIN})

    for _ in range(5):
        refused = client.post(
            CONTACT_PATH, json=CONTACT_PAYLOAD, headers={"Origin": "https://evil.example"}
        )
        assert refused.status_code == 403

    assert client.post(CONTACT_PATH, json=CONTACT_PAYLOAD).status_code == 200


def test_the_cap_fails_open_when_the_store_is_unusable(client, pipeline, monkeypatch, tmp_path):
    """A disk problem must not be the reason a supporter cannot reach us."""
    broken = tmp_path / "not-a-database"
    broken.mkdir()
    monkeypatch.setattr(rate_limit_store, "DEFAULT_DB_PATH", broken)

    response = client.post(CONTACT_PATH, json=CONTACT_PAYLOAD)

    assert response.status_code == 200
    assert len(pipeline.notifications) == 1


def test_inflight_ttl_outlives_the_slowest_possible_request():
    """The TTL has to clear the worst case, or a slot is reused while in use.

    Derived from the timeouts rather than restated, so raising
    `SMTP_TIMEOUT_SECONDS` without raising the TTL fails here instead of
    handing a second caller a slot the first is still working in.
    """
    slowest = 2 * DEFAULT_SMTP_TIMEOUT_SECONDS + DEFAULT_SHEETS_TIMEOUT_SECONDS

    assert slowest < app_module._INFLIGHT_TTL_SECONDS, (
        f"a submission can take {slowest}s (two SMTP connections plus the sheet append) "
        f"but a slot expires after {app_module._INFLIGHT_TTL_SECONDS}s"
    )

from __future__ import annotations

import logging
import smtplib
from collections import deque
from math import ceil
from time import monotonic
from typing import NamedTuple

from flask import Flask, json, jsonify, request
from werkzeug.exceptions import HTTPException

try:
    from googleapiclient.errors import HttpError
except Exception:  # pragma: no cover - fallback for environments without google libs

    class HttpError(Exception):
        pass


from api.config import (
    DEFAULT_MAX_REQUEST_BYTES,
    DEFAULT_YARDSIGN_SHEETS_WORKSHEET,
    EmailConfig,
    env,
    env_bool,
    load_email_config,
    load_sheets_config,
)
from api.models import (
    Submission,
    YardSignRequest,
    looks_like_email,
    normalize_text,
    validate_submission,
    validate_yard_sign_request,
)
from api.rate_limit_store import consume as consume_persistent_rate_limit
from api.services.email_service import (
    send_confirmation_email,
    send_submission_email,
    send_yard_sign_confirmation_email,
    send_yard_sign_request_email,
    verify_smtp_credentials,
)
from api.services.sheets_service import append_row, verify_sheets_access

try:
    import newrelic.agent as _newrelic_agent
except Exception:  # pragma: no cover - the agent is absent locally and in CI
    _newrelic_agent = None

app = Flask(__name__)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _int_setting(name: str, default: int) -> int:
    """A positive integer from the environment, degrading to `default` if unusable.

    These are read at import, which is the whole reason this logs instead of
    raising: an exception here fails module import, and this module is the
    entry point for the API, so a mistyped value in cPanel would take every
    form on the site down rather than fall back to a working default. Same
    trade `passenger_wsgi._start_new_relic` makes, for the same reason.

    Contrast `load_email_config`, which does raise on a bad timeout: that runs
    per request, where app.py already renders a ValueError as a JSON 500.

    Parsed as an int rather than via `env_positive_number`, whose float return
    made a fractional value the one input class that mutated silently instead
    of degrading -- "2.5" became 2, and "0.5" became 1 via a clamp.
    """
    raw = env(name)
    if not raw:
        return default

    try:
        value = int(raw)
        if value < 1:
            raise ValueError
    except ValueError:
        logger.error(
            "%s must be a positive integer, got %r; falling back to %s", name, raw, default
        )
        return default

    return value


# Without this, `MAX_CONTENT_LENGTH` is None and a JSON body of any size is read
# and parsed in full before validation rejects it on a 500-character field
# limit. Form posts were already bounded by Flask's MAX_FORM_MEMORY_SIZE
# default, but that setting does not cover application/json, which is what the
# site actually posts.
app.config["MAX_CONTENT_LENGTH"] = _int_setting("MAX_REQUEST_BYTES", DEFAULT_MAX_REQUEST_BYTES)

_RATE_LIMIT_WINDOW_SECONDS = _int_setting("RATE_LIMIT_WINDOW_SECONDS", 60)
_RATE_LIMIT_MAX_REQUESTS = _int_setting("RATE_LIMIT_MAX_REQUESTS", 5)

# The second tier (ADR-0016): the patient caller the burst limit above cannot
# see. Sized from the 2026-08-10 abuse, which peaked at 23/hour while never
# exceeding three in any single minute.
_LONG_RATE_LIMIT_WINDOW_SECONDS = _int_setting("LONG_RATE_LIMIT_WINDOW_SECONDS", 3600)
_LONG_RATE_LIMIT_MAX_REQUESTS = _int_setting("LONG_RATE_LIMIT_MAX_REQUESTS", 10)

# `/health/deep` gets its own, larger hourly allowance. It is polled on a
# schedule rather than by people, so the form endpoints' figure -- chosen
# against "a supporter submits one form once" -- describes nothing about it, and
# a 429 here is a false alert rather than a blocked spammer.
#
# Sized against the synthetic monitor in monitoring/alerts.graphql, currently
# EVERY_15_MINUTES from two locations. Should the monitor and this ever drift
# apart, `test_health_deep_allowance_fits_the_synthetic_monitor` fails rather
# than the alert policy paging at 3am. Raise this before shortening the period.
_HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS = _int_setting("HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS", 30)

_HEALTH_DEEP_SCOPE = "health-deep"

# How long one probe result is reused (ADR-0017).
#
# The rate limit above bounds how often *one* address can ask; nothing bounded
# how much work the answer costs, and the answer is a real SMTP `LOGIN` against
# the campaign's own mail account plus a Google Sheets read. Spread across
# enough addresses that is an unauthenticated amplifier pointed at the two
# dependencies every form on the site needs -- and the plausible outcome is the
# mail host throttling or blocking us, which takes down sending, not just the
# probe.
#
# With a cache the ceiling stops scaling with the caller's address count and
# starts scaling with ours: at most one probe per worker per TTL, however many
# addresses ask. Sized well under the monitor's 15-minute period, so every
# scheduled poll still does real work and the cache only ever collapses a
# flood. The floor is 1 second (`_int_setting` rejects less), which is
# effectively "off" while still bounding a flood to one probe per second.
_HEALTH_DEEP_CACHE_SECONDS = _int_setting("HEALTH_DEEP_CACHE_SECONDS", 60)

# A ceiling on how many client keys are tracked at once, so the dict cannot grow
# without bound. Far above any plausible number of distinct clients in a
# 60-second window for a municipal campaign; it exists as a backstop, not as a
# limit anyone should reach. See `_evict_to_cap` for what crossing it costs.
_RATE_LIMIT_MAX_BUCKETS = _int_setting("RATE_LIMIT_MAX_BUCKETS", 10_000)

_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}

# Timestamp of the next full sweep. Starts in the past so the first request
# after boot sweeps, which keeps the scheduling logic identical on every path.
_next_bucket_sweep_at = 0.0

# The header naming the real client, for when something that overwrites it sits
# in front of the app. Unset by default, and that default is load-bearing:
# nothing currently fronts this API (ADR-0003), so a forwarding header is just
# a string the caller chose. Trusting one unconditionally let any caller mint a
# fresh bucket per request and bypass the limiter entirely -- see ADR-0014.
# Putting Cloudflare in front stays a config change (set this to
# `CF-Connecting-IP`), not a code change.
_TRUSTED_CLIENT_IP_HEADER = env("TRUSTED_CLIENT_IP_HEADER")

_CORS_ALLOWED_ORIGINS = {
    item.strip()
    for item in env(
        "CORS_ALLOWED_ORIGINS",
        (
            "https://voteforjulia.com,"
            "https://www.voteforjulia.com,"
            "https://test.voteforjulia.com,"
            "https://test-api.voteforjulia.com,"
            "http://localhost:5173"
        ),
    ).split(",")
    if item.strip()
}


@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin", "").strip()

    # Vary goes on every response, not just the allowed ones. The response
    # body/headers depend on Origin either way, so a shared cache that only
    # learns this on the allowed branch could serve a disallowed origin's
    # cached response (no Allow-Origin header) to an allowed one, or vice
    # versa. `.vary.add` merges into any existing Vary instead of clobbering.
    response.vary.add("Origin")

    if origin and origin in _CORS_ALLOWED_ORIGINS:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        # The trace headers are what let a browser AJAX call and the API
        # transaction it triggers join into one distributed trace. The browser
        # agent only sends them cross-origin when the origin is listed in its
        # own distributed_tracing.allowed_origins (src/lib/newrelic.ts), and
        # the preflight fails without them named here.
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, newrelic, traceparent, tracestate"
        )
        response.headers["Access-Control-Max-Age"] = "86400"

    return response


@app.errorhandler(HTTPException)
def json_http_error(exc: HTTPException):
    """Render framework-raised errors in the same JSON shape as the handlers.

    Every error the view functions produce themselves is `{"error": ...}`, but
    anything raised before or around them -- a 404, a 405, and now the 413 from
    the size cap above -- came back as Werkzeug's HTML page. A client calling
    `response.json()` on the error path got a parse exception instead of a
    message it could show, and the 413 is reachable from the real form.

    Flask routes uncaught non-HTTP exceptions through here as a 500 as well, so
    this is also the JSON fallback for an unhandled crash. `exc.description` is
    Werkzeug's own generic text in every one of those cases -- never anything
    derived from the request -- so this cannot leak internals into a response.

    Built from `exc.get_response()` rather than `jsonify` so headers that carry
    meaning survive: a 405 keeps its `Allow`, a 401 would keep `WWW-Authenticate`.
    """
    response = exc.get_response()
    response.set_data(json.dumps({"error": exc.description}))
    response.content_type = "application/json"
    return response


def _validate_email_config(config: EmailConfig, recipient_env: str = "RECIPIENT_EMAIL") -> str:
    if not config.email_address or not config.email_password:
        return "Email service not configured: missing EMAIL_ADDRESS or EMAIL_PASSWORD"

    if not config.recipients:
        return f"Email service not configured: missing {recipient_env}"

    if not all(looks_like_email(item) for item in config.recipients):
        return f"Email service misconfigured: {recipient_env} contains invalid address"

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
        return "First name and email are required."
    if missing_first_name:
        return "First name is required."
    if missing_email:
        return "Email is required."

    return ""


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
        missing_labels.append("First name")
    if _is_blank(yard_sign_request.email):
        missing_labels.append("Email")
    if _is_blank(yard_sign_request.address):
        missing_labels.append("Address")

    if not missing_labels:
        return ""
    if len(missing_labels) == 1:
        return f"{missing_labels[0]} is required."

    return f"{', '.join(missing_labels[:-1])} and {missing_labels[-1]} are required."


def _rate_limit_key() -> str:
    """Identify the client, trusting a forwarding header only when told to.

    A forwarding header is only evidence about the client if something between
    the client and this process overwrites it. Nothing does by default, so the
    socket address is the only thing here the caller cannot choose.

    When `TRUSTED_CLIENT_IP_HEADER` names one, its *last* hop is the value that
    counts, never the first: a proxy appends the connecting address to whatever
    list the client sent, so earlier entries are still caller-supplied. For a
    single-value header like `CF-Connecting-IP` this is simply the whole value.
    """
    if _TRUSTED_CLIENT_IP_HEADER:
        forwarded = request.headers.get(_TRUSTED_CLIENT_IP_HEADER, "")
        last_hop = forwarded.rsplit(",", 1)[-1].strip()
        if last_hop:
            return last_hop

    return request.remote_addr or "unknown"


def _sweep_expired_buckets(cutoff: float) -> None:
    """Drop timestamps older than the window, and any bucket left empty."""
    for stale_key, stale_bucket in list(_RATE_LIMIT_BUCKETS.items()):
        while stale_bucket and stale_bucket[0] <= cutoff:
            stale_bucket.popleft()
        if not stale_bucket:
            del _RATE_LIMIT_BUCKETS[stale_key]


def _evict_to_cap() -> None:
    """Force the bucket count under the cap, oldest activity first.

    Only reachable when more distinct clients are active within one window than
    the cap allows -- a sweep has already removed everything expired. Evicting a
    bucket resets that client's allowance, so this fails open: under genuine
    pressure the limiter gets more permissive rather than refusing real
    submissions or growing until the worker is killed. For a campaign form
    that is the right way round, and with the key space no longer caller-
    controlled it takes real traffic to get here.
    """
    if len(_RATE_LIMIT_BUCKETS) <= _RATE_LIMIT_MAX_BUCKETS:
        return

    # Trim to a low-water mark, not to the cap itself. Landing exactly on the
    # cap leaves the dict full, so the very next request crosses it again and
    # forces another sweep-and-sort -- which would turn this safety valve back
    # into the per-request O(n) cost it exists to remove. Headroom means it runs
    # once per (cap / 10) new keys instead.
    keep = max(_RATE_LIMIT_MAX_BUCKETS * 9 // 10, 1)
    excess = len(_RATE_LIMIT_BUCKETS) - keep

    # bucket[-1] is that key's most recent request; every bucket is non-empty
    # because the sweep runs first.
    by_least_recent = sorted(_RATE_LIMIT_BUCKETS.items(), key=lambda item: item[1][-1])
    for stale_key, _ in by_least_recent[:excess]:
        del _RATE_LIMIT_BUCKETS[stale_key]

    logger.warning(
        "Rate-limit bucket cap (%d) exceeded; evicted %d least-recently-active keys",
        _RATE_LIMIT_MAX_BUCKETS,
        excess,
    )


def _consume_rate_limit(scope: str) -> int | None:
    global _next_bucket_sweep_at

    now = monotonic()
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS

    # The sweep touches every bucket, so running it per request made the cost of
    # each request scale with the number of live keys. Once per window is enough
    # to bound memory -- nothing survives more than a window past its expiry --
    # and turns that into O(1) amortised. The cap is the safety valve for a
    # burst of new keys arriving between sweeps.
    if now >= _next_bucket_sweep_at or len(_RATE_LIMIT_BUCKETS) >= _RATE_LIMIT_MAX_BUCKETS:
        _sweep_expired_buckets(cutoff)
        _evict_to_cap()
        _next_bucket_sweep_at = now + _RATE_LIMIT_WINDOW_SECONDS

    key = f"{scope}:{_rate_limit_key()}"
    bucket = _RATE_LIMIT_BUCKETS.setdefault(key, deque())

    # Prune this key inline as well. Its count has to be exact on every request
    # regardless of how long ago the last sweep ran, or a client would be held
    # to a stale window.
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
        # Round up, not down: the oldest request leaves the window at
        # `bucket[0] + window`, and truncating that toward zero advertises a
        # wait that is still inside it -- so a client that honours Retry-After
        # exactly gets a second 429 for doing the right thing.
        retry_after = max(1, ceil(bucket[0] + _RATE_LIMIT_WINDOW_SECONDS - now))
        return retry_after

    bucket.append(now)

    # Second tier last: the cheap in-memory check short-circuits a burst before
    # anything touches the disk, and counting only requests the burst tier
    # allowed stops a refused request from spending the hourly allowance.
    return _consume_long_rate_limit(scope, key)


def _long_rate_limit_for(scope: str) -> int:
    """The hourly allowance for one scope.

    Read at call time rather than baked into a dict at import, so a test can
    monkeypatch either setting.
    """
    if scope == _HEALTH_DEEP_SCOPE:
        return _HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS

    return _LONG_RATE_LIMIT_MAX_REQUESTS


def _consume_long_rate_limit(scope: str, key: str) -> int | None:
    """The hour-scale tier, counted in SQLite so it outlives the worker.

    Separate from the burst tier because this one talks to a file and fails
    open, degrading to pre-ADR-0016 behaviour rather than taking the forms down.
    """
    return consume_persistent_rate_limit(
        key,
        limit=_long_rate_limit_for(scope),
        window_seconds=_LONG_RATE_LIMIT_WINDOW_SECONDS,
    )


# The honeypot (ADR-0016). Both forms render this as a `display: none` input no
# person can see, focus or tab into. The name is chosen to look worth filling to
# something enumerating inputs while matching no autofill heuristic -- an
# autofilled honeypot would reject a real volunteer.
_HONEYPOT_FIELD = "referralCode"

# Kill switch, so a honeypot that rejects someone real is a cPanel restart to
# disable rather than a release.
_HONEYPOT_ENFORCED = env_bool("HONEYPOT_ENFORCED", True)

# Shared by the honeypot and the origin check below, deliberately. Neither
# control can be corrected by editing the form -- one objects to a field the
# submitter cannot see, the other to the page they submitted from -- so the only
# useful thing to say in both cases is "reach us another way". Sharing it also
# means the response does not say which control fired.
_REFUSED_SUBMISSION_MESSAGE = (
    "We could not process this submission. "
    "Please email info@voteforjulia.com and we will follow up personally."
)

# The origin trust boundary (ADR-0017).
#
# A form-encoded POST is a CORS "simple request": no preflight, so the
# allowlist in `add_cors_headers` never gets a say in whether it is *made*.
# That is by design in CORS -- it governs who may read a response, not who may
# send a request -- and it means any page on the internet can auto-submit these
# forms from its visitors' browsers. Each visitor arrives on their own address,
# so per-IP limiting (ADR-0009, ADR-0016) counts one request per victim and
# never fires, and the honeypot is public in a public repo.
#
# Browsers attach `Origin` to every POST, including the no-JS `<form action>`
# navigation the site falls back to, and `voteforjulia.com` posting to
# `api.voteforjulia.com` is same-site -- so a legitimate submission always
# carries an origin that is already on the allowlist. One that carries a
# different one came from a page the campaign does not control.
#
# Absent means allowed: curl, a synthetic monitor and anything server-side send
# no `Origin` at all, and those are exactly the callers per-IP limiting does
# bound. This check closes the distributed-browser vector, not the scripted one.
_ORIGIN_ENFORCED = env_bool("ORIGIN_ENFORCED", True)

# The origin is attacker-chosen text on its way to a log line, so it is bounded
# before it gets there. Any real origin is a scheme and a host.
_MAX_LOGGED_ORIGIN_CHARS = 128


def _origin_rejected(endpoint_name: str) -> bool:
    """Whether this submission came from a page the campaign does not control.

    An absent or empty `Origin` is not a rejection: only browsers send one, and
    the callers that do not are the ones per-IP limiting already bounds. A
    present-but-unlisted origin is, and that includes the literal `null` a
    sandboxed iframe or a `data:` URL sends -- no supporter submits from one.

    Logged even when unenforced, so `ORIGIN_ENFORCED=false` answers whether this
    is catching attackers or catching people, exactly as the honeypot's switch
    does. Unlike the honeypot it does not log the body: nothing rate-limits a
    rejected origin (the check runs first, so a flood costs no I/O), and dumping
    4KB per request would hand an attacker the disk.
    """
    origin = request.headers.get("Origin", "").strip()
    if not origin or origin in _CORS_ALLOWED_ORIGINS:
        return False

    logger.warning(
        "%s rejected a submission from origin %r",
        endpoint_name,
        origin[:_MAX_LOGGED_ORIGIN_CHARS],
    )
    return _ORIGIN_ENFORCED


def _honeypot_value() -> str:
    """The honeypot field as submitted, over either encoding.

    Mirrors `_submission_from_request`'s JSON-then-form order rather than reading
    `request.values`, so the two cannot disagree about which body was read.
    """
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        return normalize_text(payload.get(_HONEYPOT_FIELD))

    if request.form:
        return normalize_text(request.form.get(_HONEYPOT_FIELD))

    return ""


def _honeypot_tripped(endpoint_name: str) -> bool:
    """Whether this request filled in the hidden field.

    Blankness is `_is_blank`, not merely falsiness. `normalize_text` strips only
    spaces and tabs, so a lone "\\n" or a non-breaking space survives it and
    would otherwise read as a filled honeypot and reject a real submission.

    Logged even when unenforced, so the kill switch can be flipped on evidence
    rather than on a hunch.
    """
    if _is_blank(_honeypot_value()):
        return False

    logger.warning("%s honeypot field %r was filled", endpoint_name, _HONEYPOT_FIELD)
    return _HONEYPOT_ENFORCED


_SMTP_UNAVAILABLE_MESSAGE = "Unable to send email right now."

# Generous relative to the forms' combined field limits, but keeps an
# oversized/hostile payload from flooding the logs.
_MAX_LOGGED_BODY_CHARS = 4096


def _has_content(value) -> bool:
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(_has_content(item) for item in value)

    return value is not None and value is not False


def _submitted_field_names() -> list[str]:
    payload = request.get_json(silent=True)
    if isinstance(payload, dict):
        source = payload
    elif request.form:
        source = request.form.to_dict(flat=False)
    else:
        return []

    return sorted(name for name, value in source.items() if _has_content(value))


def _log_request_fields(endpoint_name: str) -> None:
    # Submissions carry supporter PII (names, emails, phone numbers, home
    # addresses, free-text messages), so the routine per-request log records
    # only which fields were filled in — never their values. That is enough to
    # answer "did the phone field come through?" without turning the
    # application log into an uncontrolled store of voter data. The browser
    # applies the same rule before reporting to New Relic (see
    # src/lib/analytics.ts).
    names = _submitted_field_names()
    logger.info("%s submission fields: %s", endpoint_name, ", ".join(names) or "(none)")


def _log_request_body(endpoint_name: str) -> None:
    # Values are only logged on the failure paths where the submission is lost
    # for good and this log line is the sole way to recover it. Never called
    # for successful requests or client-side validation errors (4xx), where
    # the submitter still has their data and can retry.
    raw_body = request.get_data(as_text=True)
    if len(raw_body) > _MAX_LOGGED_BODY_CHARS:
        raw_body = raw_body[:_MAX_LOGGED_BODY_CHARS] + "…[truncated]"
    logger.error("%s unrecoverable request body: %s", endpoint_name, raw_body)


def _lost_submission_response(endpoint_name: str, message: str, status: int):
    """JSON error for a failure that dropped the submission, plus a body dump."""
    _log_request_body(endpoint_name)
    return jsonify({"error": message}), status


def _cross_site_response():
    """403, not 400: the body is fine, the page that sent it is not.

    A 400 invites the caller to fix their payload and retry, which is precisely
    what an attacker would do and precisely what will not help a real supporter.
    """
    return jsonify({"error": _REFUSED_SUBMISSION_MESSAGE}), 403


def _rate_limited_response(retry_after: int):
    response = jsonify({"error": "Too many requests. Please try again later."})
    response.status_code = 429
    response.headers["Retry-After"] = str(retry_after)
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
    recipient_env="RECIPIENT_EMAIL",
):
    _log_request_fields(endpoint_name)

    # Before the email config is even read, so a trip costs a log line and
    # nothing else -- no SMTP, no Sheets write, no mail to a supplied address.
    if _honeypot_tripped(endpoint_name):
        return _lost_submission_response(endpoint_name, _REFUSED_SUBMISSION_MESSAGE, 400)

    try:
        # Inside the try so a malformed SMTP_SECURITY/SMTP_PORT env value
        # (ValueError) produces the JSON 500 below, not Flask's HTML error page.
        email_config = load_email_config(recipient_env)

        config_error = _validate_email_config(email_config, recipient_env)
        if config_error:
            logger.error(config_error)
            return _lost_submission_response(endpoint_name, "Email service is not configured.", 500)

        parsed = parse_request()
        if parsed is None:
            return jsonify({"error": "Request body must be valid JSON or form data."}), 400

        missing_message = missing_fields_message(parsed)
        if missing_message:
            return jsonify({"error": missing_message}), 400

        validation_error = validate(parsed)
        if validation_error:
            return jsonify({"error": validation_error}), 400

        if not looks_like_email(get_email(parsed)):
            return jsonify({"error": "Please provide a valid email address."}), 400

        refused = send_notification_email(email_config, parsed)

        if refused:
            logger.error("SMTP refused recipients: %s", ", ".join(refused.keys()))
            return _lost_submission_response(
                endpoint_name, "Unable to deliver email to recipient.", 502
            )

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
            return _lost_submission_response(
                endpoint_name, "Email sent, but failed to save submission.", 502
            )

        return jsonify({"message": "Email sent successfully!"}), 200

    except smtplib.SMTPAuthenticationError:
        logger.exception("SMTP authentication failed")
        return _lost_submission_response(endpoint_name, _SMTP_UNAVAILABLE_MESSAGE, 502)
    except smtplib.SMTPException:
        logger.exception("SMTP error while sending email")
        return _lost_submission_response(endpoint_name, _SMTP_UNAVAILABLE_MESSAGE, 502)
    except ValueError:
        logger.exception("Invalid SMTP configuration")
        return _lost_submission_response(
            endpoint_name, "Server email configuration is invalid.", 500
        )

    except Exception:
        logger.exception("Unexpected error while handling %s", endpoint_name)
        return _lost_submission_response(endpoint_name, "Internal server error.", 500)


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "ok",
            "path": request.path,
            "script_root": request.script_root,
        }
    ), 200


def _report_probe_failure(name: str) -> None:
    """Attach the failed dependency to the current New Relic transaction.

    Swallowing the exception keeps credentials out of an unauthenticated
    response, but it also hides the failure from the agent: the transaction
    records a 503 and nothing about why. That gap cost an SSH session into
    `stderr.log` to find out that nine production 503s were all
    `BrokenPipeError` from Sheets. `notice_error` puts the traceback in the
    errors inbox and the attributes make it queryable:

        SELECT count(*) FROM TransactionError
        WHERE health.dependency IS NOT NULL FACET health.dependency

    Best-effort by design — the agent is absent locally and in CI, and
    monitoring must never be the thing that breaks a health check.
    """
    if _newrelic_agent is None:
        return

    try:
        _newrelic_agent.add_custom_attribute("health.dependency", name)
        _newrelic_agent.notice_error()
    except Exception:  # pragma: no cover - never let reporting break the probe
        logger.debug("Could not report the %s probe failure to New Relic", name, exc_info=True)


def _probe(name: str, check) -> tuple[str, bool]:
    """Run one dependency check, reducing any failure to "fail"."""
    try:
        check()
        return "ok", True
    except Exception:
        # Logged server-side in full; the response says only "fail". Exception
        # text from smtplib and googleapiclient quotes the credentials and
        # spreadsheet IDs it was given, and this endpoint is unauthenticated.
        logger.exception("Deep health check failed for %s", name)
        _report_probe_failure(name)
        return "fail", False


class _DeepHealthResult(NamedTuple):
    """One probe run, kept so the next caller within the TTL can reuse it."""

    produced_at: float
    payload: dict[str, str]
    status: int


# Per worker, like the burst rate-limit tier and for the same reason: Passenger
# reaps idle workers, so there is nothing longer-lived to hold it in. That makes
# the real ceiling one probe per worker per TTL rather than one globally --
# still bounded by our own worker count instead of the caller's address count,
# which is the property that matters.
_deep_health_cache: _DeepHealthResult | None = None


def _reset_deep_health_cache() -> None:
    """Forget the cached result, forcing the next request to probe. For tests."""
    global _deep_health_cache
    _deep_health_cache = None


def _run_deep_health_probes(produced_at: float) -> _DeepHealthResult:
    smtp_status, smtp_ok = _probe("smtp", lambda: verify_smtp_credentials(load_email_config()))
    sheets_status, sheets_ok = _probe("sheets", lambda: verify_sheets_access(load_sheets_config()))

    healthy = smtp_ok and sheets_ok
    return _DeepHealthResult(
        produced_at=produced_at,
        payload={
            "status": "ok" if healthy else "degraded",
            "smtp": smtp_status,
            "sheets": sheets_status,
        },
        status=200 if healthy else 503,
    )


@app.route("/health/deep", methods=["GET"])
def deep_health_check():
    global _deep_health_cache

    retry_after = _consume_rate_limit(_HEALTH_DEEP_SCOPE)
    if retry_after is not None:
        return _rate_limited_response(retry_after)

    # Stamped before the probes rather than after, so a slow run reports itself
    # as older than it is. Age may overstate; it must never understate.
    now = monotonic()

    cached = _deep_health_cache
    if cached is None or now - cached.produced_at >= _HEALTH_DEEP_CACHE_SECONDS:
        # Failures are cached too. Caching only the successes would restore the
        # full amplifier at exactly the moment a dependency is already in
        # trouble, which is when hammering it is least affordable.
        cached = _run_deep_health_probes(now)
        _deep_health_cache = cached

    response = jsonify(cached.payload)
    response.status_code = cached.status
    # Standard HTTP, and the only thing that makes the cache observable: 0 on
    # the response that ran the probes, then the age of the reused one. Without
    # it neither `curl` nor the monitor can tell a fresh answer from a held one.
    response.headers["Age"] = str(int(now - cached.produced_at))
    return response


@app.route("/send-email", methods=["POST", "OPTIONS"])
def send_email():
    if request.method == "OPTIONS":
        return ("", 204)

    # Ahead of the limiter, and that order is the point. A cross-site flood
    # arrives on its victims' addresses, so charging it to their buckets would
    # spend the allowance of people who did nothing -- and the check itself is a
    # header read and a set lookup, cheaper than the bucket it would consume.
    if _origin_rejected("/send-email"):
        return _cross_site_response()

    retry_after = _consume_rate_limit("send-email")
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
        endpoint_name="/send-email",
    )


@app.route("/yard-sign", methods=["POST", "OPTIONS"])
def yard_sign():
    if request.method == "OPTIONS":
        return ("", 204)

    # Before the limiter, for the reason given in `send_email`.
    if _origin_rejected("/yard-sign"):
        return _cross_site_response()

    retry_after = _consume_rate_limit("yard-sign")
    if retry_after is not None:
        return _rate_limited_response(retry_after)

    return _handle_form_submission(
        sheets_config=load_sheets_config(
            "GOOGLE_SHEETS_YARDSIGN_WORKSHEET", DEFAULT_YARDSIGN_SHEETS_WORKSHEET
        ),
        parse_request=_yard_sign_request_from_request,
        missing_fields_message=_missing_required_yard_sign_fields_message,
        validate=validate_yard_sign_request,
        get_email=lambda yard_sign_request: yard_sign_request.email,
        send_notification_email=send_yard_sign_request_email,
        send_confirmation_email_fn=send_yard_sign_confirmation_email,
        to_sheet_row=lambda yard_sign_request: yard_sign_request.to_sheet_row(),
        endpoint_name="/yard-sign",
        recipient_env="RECIPIENT_EMAIL_SIGNS",
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(env("PORT", "5000")), debug=False)

from __future__ import annotations

import hmac
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
    DEFAULT_SHEETS_TIMEOUT_SECONDS,
    DEFAULT_SMTP_TIMEOUT_SECONDS,
    DEFAULT_YARDSIGN_SHEETS_WORKSHEET,
    EmailConfig,
    env,
    env_bool,
    env_positive_number,
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
from api.rate_limit_store import Tier
from api.rate_limit_store import acquire as acquire_submission_slot
from api.rate_limit_store import consume as consume_rate_limit
from api.rate_limit_store import release as release_submission_slot
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

# `format` is load-bearing: the default omits the timestamp, and `stderr.log`
# is appended to across restarts. See docs/monitoring.md#is-it-real. New Relic
# is unaffected -- its agent forwards `record.getMessage()`, before formatting.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
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

# Which tier refused a request, reported to New Relic on every 429. Both tiers
# return an identical response, so this attribute is the only thing that tells
# a blocked burst apart from a patient caller. See ADR-0021.
_BURST_TIER = "burst"
_HOURLY_TIER = "hourly"

# How many submissions may be in flight at once, across every worker (ADR-0018).
# The rate limit tiers bound how often one client may ask; this bounds how much
# work can run at all, which is what an upstream slowdown turns into.
_MAX_CONCURRENT_SUBMISSIONS = _int_setting("MAX_CONCURRENT_SUBMISSIONS", 12)

# `/health/deep` needs its own, much smaller budget for the same reason it needs
# a cache: on a miss it does the same expensive I/O a submission does, so
# without one it is an uncapped path to the exhaustion the cap above prevents --
# and at 30/hour per client it is cheaper to abuse than the forms. Two, because
# the only legitimate caller is a monitor polling from two locations.
# Caught by Copilot on PR #138.
_MAX_CONCURRENT_HEALTH_PROBES = _int_setting("MAX_CONCURRENT_HEALTH_PROBES", 2)

# The scopes the concurrency budgets are counted under, kept apart so a flood of
# probes cannot spend the allowance a supporter's submission needs.
_SUBMISSION_SLOT_SCOPE = "submission"
_HEALTH_PROBE_SLOT_SCOPE = "health-probe"

# `SMTP_TIMEOUT_SECONDS` bounds each blocking socket operation, not the session,
# and one send is a dozen or so of them: connect, banner, EHLO, (STARTTLS,
# EHLO), AUTH, MAIL, RCPT, DATA, the body, QUIT. A server that answers every
# command just inside the timeout drags a submission out to that multiple of it.
# Caught by Copilot on PR #138 -- the first version summed the timeouts once and
# was short by an order of magnitude.
_SMTP_OPERATIONS_PER_SESSION = 12
_SMTP_SESSIONS_PER_SUBMISSION = 2

# The Sheets client can refresh its token before the append itself.
_SHEETS_OPERATIONS_PER_SUBMISSION = 2


def _worst_case_submission_seconds(smtp_timeout: float, sheets_timeout: float) -> float:
    """Upper bound on one submission, given the timeouts it will run under."""
    return (
        _SMTP_SESSIONS_PER_SUBMISSION * _SMTP_OPERATIONS_PER_SESSION * smtp_timeout
        + _SHEETS_OPERATIONS_PER_SUBMISSION * sheets_timeout
    )


def _worst_case_probe_seconds(smtp_timeout: float, sheets_timeout: float) -> float:
    """Upper bound on one `/health/deep` probe: one SMTP login, one sheet read."""
    return _SMTP_OPERATIONS_PER_SESSION * smtp_timeout + sheets_timeout


def _configured_timeouts() -> tuple[float, float]:
    """The SMTP and Sheets timeouts the next request will actually run under.

    Read here rather than taken from the DEFAULT_* constants, because both are
    per-request cPanel settings: sizing a slot lifetime off the defaults means
    raising `SMTP_TIMEOUT_SECONDS` silently breaks the guarantee below, while the
    test that checks it only ever sees CI's environment. Caught in review.

    Degrades to the default on an unusable value rather than raising, the same
    trade `_int_setting` makes: this decides a safety margin, not the response,
    so `_handle_form_submission` stays the thing that reports a bad config.
    """

    def timeout(name: str, default: float) -> float:
        try:
            return env_positive_number(name, default)
        except ValueError:
            logger.error("%s is unusable; sizing slot lifetime with %s instead", name, default)
            return default

    return (
        timeout("SMTP_TIMEOUT_SECONDS", DEFAULT_SMTP_TIMEOUT_SECONDS),
        timeout("SHEETS_TIMEOUT_SECONDS", DEFAULT_SHEETS_TIMEOUT_SECONDS),
    )


def _slot_ttl_seconds(worst_case: float) -> int:
    """How long a slot survives unreleased: the work's worst case, or an override."""
    return _INFLIGHT_TTL_OVERRIDE or ceil(worst_case)


def _submission_slot_ttl_seconds() -> int:
    return _slot_ttl_seconds(_worst_case_submission_seconds(*_configured_timeouts()))


def _probe_slot_ttl_seconds() -> int:
    return _slot_ttl_seconds(_worst_case_probe_seconds(*_configured_timeouts()))


# How long a slot survives without being released, for the worker that is killed
# mid-request and never gets to release its own.
#
# Derived per request from the configured timeouts, so raising a timeout raises
# this with it -- deriving it once at import from the DEFAULT_* constants left
# the guarantee unmet for exactly the deployments that changed a timeout, since
# both are per-request cPanel settings and CI never sees them. Expiring early is
# the failure that matters: it hands a live request's slot to someone else and
# admits callers above the cap, in the slow-upstream conditions the cap exists
# for. Expiring late only delays reclaiming a slot after a crash, which is rare
# and self-correcting -- so the bound is deliberately pessimistic.
#
# Unset (0) derives; a value pins it instead.
_INFLIGHT_TTL_OVERRIDE = _int_setting("INFLIGHT_TTL_SECONDS", 0)

# How long one probe result is reused. The rate limit above bounds how often one
# address may ask; this bounds what the answer costs. Keep it well under the
# synthetic monitor's period, or scheduled polls start grading a cached answer.
# See ADR-0017.
_HEALTH_DEEP_CACHE_SECONDS = _int_setting("HEALTH_DEEP_CACHE_SECONDS", 60)

# A ceiling on how many refusals are remembered at once, so the dict cannot
# grow without bound. Far above any plausible number of distinct clients in a
# 60-second window for a municipal campaign; it exists as a backstop, not as a
# limit anyone should reach. Both dictionaries below are bounded by it, and
# crossing it costs disk hits or an allowance reset, never correctness.
_RATE_LIMIT_MAX_TRACKED_KEYS = _int_setting("RATE_LIMIT_MAX_TRACKED_KEYS", 10_000)

# Refusals the store has already issued: key -> (monotonic deadline, tier).
# Not a counter, and deliberately not the limit -- see ADR-0024. A worker holds
# only what the shared tiers told it, so this can refuse a caller the store
# would refuse anyway and nobody else.
_RATE_LIMIT_REFUSALS: dict[str, tuple[float, str]] = {}

# The fallback burst counter, and the one piece of per-worker counting left:
# key -> the monotonic timestamps of requests this worker allowed *while the
# store was unreachable*. Empty in normal operation. See `_degraded_burst_limit`.
_DEGRADED_BURST_COUNTS: dict[str, deque[float]] = {}

# Timestamp of the next full sweep. Starts in the past so the first request
# after boot sweeps, which keeps the scheduling logic identical on every path.
_next_refusal_sweep_at = 0.0

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
def add_security_headers(response):
    """The subset of the site's edge policy that means anything for a JSON API.

    Set here rather than in an `.htaccess`, which is where ADR-0010 says edge
    policy belongs: the API subdomain's docroot is not in this repo, so a header
    added there would be untracked host state that no test or deploy can see.

    HSTS matters most. The apex sends `includeSubDomains`, but that only reaches
    a browser that has already been to the apex -- a client whose first contact
    with the estate is this API is unprotected until it does. The rest of the
    site's headers are about rendering documents and say nothing here.
    """
    response.headers.setdefault("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    return response


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


def _sweep_expired_refusals(now: float) -> None:
    """Drop refusals whose deadline has passed."""
    for key, (refused_until, _) in list(_RATE_LIMIT_REFUSALS.items()):
        if now >= refused_until:
            del _RATE_LIMIT_REFUSALS[key]


def _evict_to_cap() -> None:
    """Force the cache under its cap, soonest-to-expire first.

    Only reachable when at least as many distinct clients are refused within one
    window as the cap allows -- a sweep has already removed everything expired.
    Evicting an entry costs a store round trip on that caller's next request and
    nothing else: the tiers themselves live in SQLite, so a forgotten refusal is
    re-derived rather than lost. The entries nearest their deadline go first,
    because they are the ones with the least shielding left in them.

    **`<` and not `<=`, matching the `>=` in the arm that calls this.** At
    exactly the cap the arm fires and a `<=` guard returned without trimming, so
    the dict stayed full and every subsequent request swept and re-armed -- the
    per-request O(n) cost the low-water mark below exists to remove, reached by
    the one size the two comparisons disagreed about.
    """
    if len(_RATE_LIMIT_REFUSALS) < _RATE_LIMIT_MAX_TRACKED_KEYS:
        return

    # Trim to a low-water mark, not to the cap itself. Landing exactly on the
    # cap leaves the dict full, so the very next request crosses it again and
    # forces another sweep-and-sort -- which would turn this safety valve back
    # into the per-request O(n) cost it exists to remove. Headroom means it runs
    # once per (cap / 10) new keys instead.
    keep = max(_RATE_LIMIT_MAX_TRACKED_KEYS * 9 // 10, 1)
    excess = len(_RATE_LIMIT_REFUSALS) - keep

    by_soonest_deadline = sorted(_RATE_LIMIT_REFUSALS.items(), key=lambda item: item[1][0])
    for stale_key, _ in by_soonest_deadline[:excess]:
        del _RATE_LIMIT_REFUSALS[stale_key]

    logger.warning(
        "Rate-limit refusal cache cap (%d) exceeded; evicted %d entries",
        _RATE_LIMIT_MAX_TRACKED_KEYS,
        excess,
    )


def _rate_limit_tiers(scope: str) -> tuple[Tier, ...]:
    """The windows one scope is held to, narrowest first.

    Order is what a 429 reports: a caller over both tiers is told about the
    burst, which is the one that clears first.

    Read at call time rather than baked in at import, so a test can monkeypatch
    any of the settings.
    """
    return (
        Tier(_BURST_TIER, _RATE_LIMIT_MAX_REQUESTS, _RATE_LIMIT_WINDOW_SECONDS),
        Tier(_HOURLY_TIER, _long_rate_limit_for(scope), _LONG_RATE_LIMIT_WINDOW_SECONDS),
    )


def _long_rate_limit_for(scope: str) -> int:
    """The hourly allowance for one scope."""
    if scope == _HEALTH_DEEP_SCOPE:
        return _HEALTH_LONG_RATE_LIMIT_MAX_REQUESTS

    return _LONG_RATE_LIMIT_MAX_REQUESTS


def _sweep_degraded_counts(now: float) -> None:
    """Prune the fallback counters, and drop them wholesale if they run away.

    A bucket disappears one window after its last request, which is what bounds
    this in normal use -- and in normal use it is empty, because nothing writes
    to it unless the store is unreachable.

    The cap clears rather than evicting selectively, unlike `_evict_to_cap`.
    Both fail open; this one is allowed to be blunt about it, because it only
    has anything to lose during a disk incident and a reset allowance is the
    same failure the eviction would have caused one key at a time.
    """
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    for key, bucket in list(_DEGRADED_BURST_COUNTS.items()):
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if not bucket:
            del _DEGRADED_BURST_COUNTS[key]

    if len(_DEGRADED_BURST_COUNTS) >= _RATE_LIMIT_MAX_TRACKED_KEYS:
        logger.warning(
            "Degraded rate-limit counters exceeded %d keys; clearing them",
            _RATE_LIMIT_MAX_TRACKED_KEYS,
        )
        _DEGRADED_BURST_COUNTS.clear()


def _degraded_burst_limit(key: str, now: float) -> tuple[int, str] | None:
    """Hold the burst window in this worker's memory, for as long as the store is down.

    ADR-0009's original limiter, kept for the one case it is still the best
    available answer. It is per-worker, so the real ceiling is the shipped limit
    times however many workers are alive -- the defect ADR-0024 exists to
    remove. It runs only when the shared tiers cannot answer at all, where the
    alternative is not a correct limit but no limit, and `5 x N` beats
    unlimited on an endpoint that sends mail from the campaign's own account.

    Counts only what it allows, and only while degraded, so it starts from zero
    when an incident begins and stops being consulted the moment the store
    answers again. Both are deliberate: a shadow counter kept warm through
    normal operation would be a second limit nobody could see.
    """
    cutoff = now - _RATE_LIMIT_WINDOW_SECONDS
    bucket = _DEGRADED_BURST_COUNTS.setdefault(key, deque())

    # Inline, like the sweep it does not wait for: this key's count has to be
    # exact on every request however long ago the last sweep ran.
    while bucket and bucket[0] <= cutoff:
        bucket.popleft()

    if len(bucket) >= _RATE_LIMIT_MAX_REQUESTS:
        retry_after = max(1, ceil(bucket[0] + _RATE_LIMIT_WINDOW_SECONDS - now))
        return retry_after, _BURST_TIER

    bucket.append(now)
    return None


def _cached_refusal(key: str, now: float) -> tuple[int, str] | None:
    """Re-serve a refusal the store already issued, without touching the disk.

    Sound because the deadline is the store's own exact answer: until the
    request that filled the window leaves it, the count cannot fall, so every
    tier that refused still refuses. Exact matters -- deriving the deadline from
    the rounded-up header instead would hold the entry for up to a second past
    the window, which is this cache inventing a refusal rather than repeating
    one. The one way it still over-refuses is `reset()`, which clears the table
    under a worker that has not forgotten -- by hand, or in a test, never in the
    request path.
    """
    entry = _RATE_LIMIT_REFUSALS.get(key)
    if entry is None:
        return None

    refused_until, tier = entry
    if now >= refused_until:
        del _RATE_LIMIT_REFUSALS[key]
        return None

    return max(1, ceil(refused_until - now)), tier


def _consume_rate_limit(scope: str) -> tuple[int, str] | None:
    """Refuse the request, or let it through.

    Returns `(retry_after, tier)` when a tier refuses, so the caller can report
    which one did. `None` means allowed.

    Every tier counts in SQLite, because a limit held in process memory is
    multiplied by however many workers Passenger has alive -- the burst tier
    shipped at an effective 5 x N for a year. See ADR-0024. What stays in memory
    is the refusals that store has already issued, which is what keeps a flood
    from spending a disk round trip per request, and a fallback burst counter
    that runs only while the store is unreachable.
    """
    global _next_refusal_sweep_at

    now = monotonic()

    # The sweep touches every entry, so running it per request made the cost of
    # each request scale with the number of cached refusals. Once per window is
    # enough to bound memory -- nothing survives its deadline by more than a
    # window -- and turns that into O(1) amortised. The cap is the safety valve
    # for a burst of new keys arriving between sweeps, and it has to watch both
    # dictionaries: they fill in opposite conditions, the cache only while the
    # store is answering and the fallback counters only while it is not. Testing
    # the cache alone left the fallback bounded by the schedule and nothing
    # else, which is a whole window of unbounded growth during an incident.
    if (
        now >= _next_refusal_sweep_at
        or len(_RATE_LIMIT_REFUSALS) >= _RATE_LIMIT_MAX_TRACKED_KEYS
        or len(_DEGRADED_BURST_COUNTS) >= _RATE_LIMIT_MAX_TRACKED_KEYS
    ):
        _sweep_expired_refusals(now)
        _evict_to_cap()
        _sweep_degraded_counts(now)
        _next_refusal_sweep_at = now + _RATE_LIMIT_WINDOW_SECONDS

    key = f"{scope}:{_rate_limit_key()}"

    cached = _cached_refusal(key, now)
    if cached is not None:
        return cached

    verdict = consume_rate_limit(key, tiers=_rate_limit_tiers(scope))

    if not verdict.answered:
        # The store is unreachable and has counted nothing, so this worker holds
        # the burst window itself until it comes back.
        return _degraded_burst_limit(key, now)

    if verdict.refusal is None:
        return None

    # Only what the store refused, never what it allowed, and never what the
    # fallback above decided. Remembering either would make this a counter
    # again, and a per-worker counter is the defect ADR-0024 removes.
    #
    # `expires_in` and not `retry_after`: the rounded-up header value would keep
    # this entry alive for up to a second after the window clears, which is the
    # cache inventing a refusal of its own rather than repeating one.
    refusal = verdict.refusal
    _RATE_LIMIT_REFUSALS[key] = (now + refusal.expires_in, refusal.tier)
    return refusal.retry_after, refusal.tier


# The honeypot (ADR-0016). Both forms render this as a `display: none` input no
# person can see, focus or tab into. The name is chosen to look worth filling to
# something enumerating inputs while matching no autofill heuristic -- an
# autofilled honeypot would reject a real volunteer.
_HONEYPOT_FIELD = "referralCode"

# Kill switch, so a honeypot that rejects someone real is a cPanel restart to
# disable rather than a release.
_HONEYPOT_ENFORCED = env_bool("HONEYPOT_ENFORCED", True)

# Shared by the honeypot and the origin check: neither is correctable by editing
# the form, so both can only say "reach us another way". See ADR-0017.
_REFUSED_SUBMISSION_MESSAGE = (
    "We could not process this submission. "
    "Please email info@voteforjulia.com and we will follow up personally."
)

# The origin trust boundary (ADR-0017). CORS decides who may read a response,
# never who may send a request: a form-encoded POST is a simple request, so the
# allowlist above never sees it before it arrives. Per-IP limiting is blind to
# the same case, because each conscripted browser brings its own address.
_ORIGIN_ENFORCED = env_bool("ORIGIN_ENFORCED", True)

# Attacker-chosen text on its way to a log line.
_MAX_LOGGED_ORIGIN_CHARS = 128


def _origin_rejected(endpoint_name: str) -> bool:
    """Whether this submission came from a page the campaign does not control.

    Absent is allowed -- only browsers send `Origin`, and the callers that do
    not are the ones per-IP limiting bounds. Present-but-unlisted is not,
    including the `null` a sandboxed iframe sends. Logs the origin even when
    unenforced, but never the body: nothing rate-limits this path. See ADR-0017.
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


# The edge trust boundary (ADR-0020). Cloudflare stamps every proxied request
# with this header; a caller that read the origin address off the MX record and
# connected straight to it does not carry one. Distinct from the origin check
# above, which asks which page sent the request -- this only asks whether the
# request came through the edge at all.
_EDGE_TOKEN_HEADER = "X-Origin-Token"

# Matches MIN_TOKEN_LENGTH in scripts/arm-edge-gate.sh. The two ends read the
# same secret from different places, so they have to agree on what a valid one
# is; see ADR-0020 on why entropy is the control here.
_EDGE_TOKEN_MIN_LENGTH = 32


def _edge_token_setting() -> str:
    """The edge token, or empty if it fails the format the deploy enforces.

    The deploy validates the GitHub secret, but the API's copy is typed into
    cPanel by hand and that check never sees it -- so a value too weak to arm
    the frontend could still arm this. Degrades to unset for the reason
    `_int_setting` degrades, and never logs the value. See ADR-0020.
    """
    raw = env("EDGE_SHARED_TOKEN", "").strip()
    if not raw:
        return ""

    # `isalnum` alone accepts non-ASCII digits and letters; `isascii` is what
    # pins this to the deploy's [A-Za-z0-9].
    if not (raw.isascii() and raw.isalnum()):
        logger.error(
            "EDGE_SHARED_TOKEN must be ASCII alphanumeric; ignoring it and leaving the origin open."
        )
        return ""

    if len(raw) < _EDGE_TOKEN_MIN_LENGTH:
        logger.error(
            "EDGE_SHARED_TOKEN must be at least %d characters; got %d. "
            "Ignoring it and leaving the origin open.",
            _EDGE_TOKEN_MIN_LENGTH,
            len(raw),
        )
        return ""

    return raw


_EDGE_TOKEN = _edge_token_setting()

# Attacker-chosen text on its way to a log line, same as the origin above.
_MAX_LOGGED_PATH_CHARS = 128

# Defaults to OFF. Arming this before the Transform Rule is live refuses every
# caller including the synthetic monitors, so the ordering has to be: create the
# rule, confirm the header arrives, then switch this on. A token that is unset
# cannot enforce at all, which is the second guard on the same mistake.
_EDGE_TOKEN_ENFORCED = env_bool("EDGE_TOKEN_ENFORCED", False)

_UNPROXIED_MESSAGE = "This endpoint is not reachable directly."

# One line per window, carrying the count it stands for. A caller refused here
# never reached the edge's rate limiting, so nothing bounds how fast it can
# retry -- and an unbounded WARNING per refusal makes the log the cheapest thing
# to attack on the whole origin. The count is what keeps this a signal: silence
# and a flood have to stay distinguishable, which is what the rollout's audit
# step reads. See ADR-0020.
_EDGE_LOG_WINDOW_SECONDS = _int_setting("EDGE_LOG_WINDOW_SECONDS", 60)
_EDGE_LOG_STATE = {"next_at": 0.0, "suppressed": 0}


def _log_unproxied_request(path: str) -> None:
    """Warn about an unproxied caller, at most once per window *per worker*."""
    now = monotonic()
    if now < _EDGE_LOG_STATE["next_at"]:
        _EDGE_LOG_STATE["suppressed"] += 1
        return

    suppressed = _EDGE_LOG_STATE["suppressed"]
    _EDGE_LOG_STATE["suppressed"] = 0
    _EDGE_LOG_STATE["next_at"] = now + _EDGE_LOG_WINDOW_SECONDS
    logger.warning(
        "%r reached the origin without a valid %s header (%d more suppressed)",
        path[:_MAX_LOGGED_PATH_CHARS],
        _EDGE_TOKEN_HEADER,
        suppressed,
    )


@app.before_request
def _reject_unproxied_request():
    """Refuse requests that did not arrive through Cloudflare. See ADR-0020.

    A `before_request` rather than a per-route guard, because every route shares
    the property and a route added later should not have to remember it. This
    also runs for paths that match no route, so a scanner sweeping the origin
    gets the same answer everywhere.
    """
    if not _EDGE_TOKEN:
        return None

    # Compared as bytes: `compare_digest` raises TypeError on a str holding any
    # non-ASCII character, and a header byte >= 0x80 decodes to exactly that --
    # so the str form turns a hostile header into a 500 instead of a 403.
    # Constant-time because the token is a secret and a direct caller can retry
    # without limit, never having reached the edge's rate limiting.
    presented = request.headers.get(_EDGE_TOKEN_HEADER, "").encode("utf-8", "replace")
    if hmac.compare_digest(presented, _EDGE_TOKEN.encode("utf-8")):
        return None

    _log_unproxied_request(request.path)
    if not _EDGE_TOKEN_ENFORCED:
        return None

    return jsonify({"error": _UNPROXIED_MESSAGE}), 403


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
    """403, not 400: the body is fine, the page that sent it is not."""
    return jsonify({"error": _REFUSED_SUBMISSION_MESSAGE}), 403


_AT_CAPACITY_MESSAGE = "The site is busy right now. Please try again in a moment."

# Advertised on the 503. A slot frees when a request finishes, so the honest
# figure is seconds, not the minutes a rate-limit window needs.
_AT_CAPACITY_RETRY_AFTER_SECONDS = 5


def _at_capacity_response():
    response = jsonify({"error": _AT_CAPACITY_MESSAGE})
    response.status_code = 503
    response.headers["Retry-After"] = str(_AT_CAPACITY_RETRY_AFTER_SECONDS)
    return response


def _within_capacity(endpoint_name: str, run):
    """Run `run()` holding one of the concurrent-submission slots, or 503.

    Released in a `finally` so a raising handler frees its slot; the store's TTL
    covers the worker that dies without getting that far. See ADR-0018.
    """
    token = acquire_submission_slot(
        _SUBMISSION_SLOT_SCOPE,
        limit=_MAX_CONCURRENT_SUBMISSIONS,
        ttl_seconds=_submission_slot_ttl_seconds(),
    )
    if token is None:
        logger.warning(
            "%s refused: %d submissions already in flight",
            endpoint_name,
            _MAX_CONCURRENT_SUBMISSIONS,
        )
        return _at_capacity_response()

    try:
        return run()
    finally:
        release_submission_slot(token)


def _report_rate_limit(tier: str, scope: str) -> None:
    """Tag the transaction with which tier refused it, and on which endpoint.

    A 429 is a returned response, not a raised exception, so the agent records
    it with no error and nothing distinguishing the two tiers. These attributes
    are the whole signal the alert conditions run on. See ADR-0021.

    Never the client address: `_rate_limit_key()` is a caller identity and
    ADR-0014 keeps it out of anywhere it does not have to be.

    Best-effort, like `_report_probe_failure` -- the agent is absent locally and
    in CI, and reporting must never be the thing that refuses a supporter.
    """
    if _newrelic_agent is None:
        return

    try:
        _newrelic_agent.add_custom_attribute("rate_limit.tier", tier)
        _newrelic_agent.add_custom_attribute("rate_limit.scope", scope)
    except Exception:  # pragma: no cover - never let reporting break a response
        logger.debug("Could not report the %s rate-limit trip to New Relic", tier, exc_info=True)


def _rate_limited_response(retry_after: int, *, tier: str, scope: str):
    _report_rate_limit(tier, scope)

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


# The document the API root serves. Everything in it is decoration except the
# two endpoint paths, which are real. See docs/architecture.md.
#
# Ordered for reading, not sorted: `jsonify` would alphabetise it, so
# `service_root` serialises this by hand.
_MANKATO_CONFIG = {
    "campaign_status": "Active",
    "poking_around": True,
    "candidate": {
        "name": "Julia Hamann",
        "role": "Mayor of Mankato",
        "url": "https://voteforjulia.com",
    },
    "favorites": {
        "hangout": "Wine Cafe",
        "park": "Jackson Park with Food Not Bombs",
        "errand": "Farmers market",
        "software_engineer": "Dylan Whitney",
    },
    "get_involved": {
        "yard_sign": "/yard-sign",
        "volunteer": "/send-email",
    },
    "reminder": "Don't forget to vote on November 3rd!",
}

# Pretty-printed because the intended reader is a person with a terminal.
_MANKATO_CONFIG_BODY = json.dumps(_MANKATO_CONFIG, sort_keys=False, indent=2) + "\n"


@app.route("/", methods=["GET"])
def service_root():
    """Answer the root with a joke instead of a 404.

    Nothing is routed here and nothing needs to be, but the root is the most
    requested path on the origin -- scanners, near enough all of it -- so the
    404s were the loudest line in the log with no one reading them.
    """
    response = app.response_class(_MANKATO_CONFIG_BODY, mimetype="application/json")
    # Honest about a fixed document, but do not expect it to save an origin
    # hit: the free tier caches by extension (ADR-0019), so an extensionless
    # JSON body is passed through. A Cache Rule that changed that would need
    # the CORS echo in `add_cors_headers` dealt with first -- Cloudflare
    # honours only `Vary: Accept-Encoding`, so the `Vary: Origin` set there
    # would not stop one origin's `Access-Control-Allow-Origin` being served
    # to another.
    response.headers["Cache-Control"] = "public, max-age=3600"
    return response, 200


@app.route("/health", methods=["GET"])
def health_check():
    return jsonify(
        {
            "status": "ok",
            "path": request.path,
            "script_root": request.script_root,
            # The value every per-IP control is keyed on, echoed for the same
            # reason as `script_root`: to answer what the *deployed* app sees.
            # ADR-0009/0014/0016 all assume this is the caller rather than
            # something in front of it, and nothing had ever checked. A caller
            # only learns their own address. See ADR-0018.
            "client": _rate_limit_key(),
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


# Per worker, like the burst rate-limit tier: Passenger reaps idle workers, so
# the bound is one probe per worker per TTL rather than one globally.
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


def _refresh_deep_health(now: float) -> _DeepHealthResult | None:
    """Probe under the health budget, or None if every probe slot is taken."""
    # One SMTP session and one sheet read, so its own shorter bound: borrowing
    # the submission figure would double the window in which a worker killed
    # mid-probe leaves a cold cache answering 503.
    token = acquire_submission_slot(
        _HEALTH_PROBE_SLOT_SCOPE,
        limit=_MAX_CONCURRENT_HEALTH_PROBES,
        ttl_seconds=_probe_slot_ttl_seconds(),
    )
    if token is None:
        logger.warning(
            "/health/deep probe deferred: %d probes already running",
            _MAX_CONCURRENT_HEALTH_PROBES,
        )
        return None

    try:
        return _run_deep_health_probes(now)
    finally:
        release_submission_slot(token)


@app.route("/health/deep", methods=["GET"])
def deep_health_check():
    global _deep_health_cache

    refused = _consume_rate_limit(_HEALTH_DEEP_SCOPE)
    if refused is not None:
        retry_after, tier = refused
        return _rate_limited_response(retry_after, tier=tier, scope=_HEALTH_DEEP_SCOPE)

    # Stamped before the probes, so Age may overstate but never understates.
    now = monotonic()

    cached = _deep_health_cache
    if cached is None or now - cached.produced_at >= _HEALTH_DEEP_CACHE_SECONDS:
        # Failures too: caching only successes would restore the amplifier
        # exactly when a dependency is already in trouble.
        refreshed = _refresh_deep_health(now)

        if refreshed is None:
            # Every probe slot is busy. A stale answer with an honest `Age` is
            # worth more to a monitor than a refusal -- and it keeps a flood
            # from paging as though a dependency had failed. With nothing
            # cached at all there is nothing truthful to say.
            if cached is None:
                return _at_capacity_response()
        else:
            cached = refreshed
            _deep_health_cache = cached

    response = jsonify(cached.payload)
    response.status_code = cached.status
    # The cache's only outward sign; 0 means the probes ran for this request.
    response.headers["Age"] = str(int(now - cached.produced_at))
    return response


@app.route("/send-email", methods=["POST", "OPTIONS"])
def send_email():
    if request.method == "OPTIONS":
        return ("", 204)

    # Ahead of the limiter: a cross-site flood arrives on its victims'
    # addresses, so charging it to their buckets would spend real supporters'
    # allowance.
    if _origin_rejected("/send-email"):
        return _cross_site_response()

    scope = "send-email"
    refused = _consume_rate_limit(scope)
    if refused is not None:
        retry_after, tier = refused
        return _rate_limited_response(retry_after, tier=tier, scope=scope)

    return _within_capacity(
        "/send-email",
        lambda: _handle_form_submission(
            sheets_config=load_sheets_config(),
            parse_request=_submission_from_request,
            missing_fields_message=_missing_required_fields_message,
            validate=validate_submission,
            get_email=lambda submission: submission.email,
            send_notification_email=send_submission_email,
            send_confirmation_email_fn=send_confirmation_email,
            to_sheet_row=lambda submission: submission.to_sheet_row(),
            endpoint_name="/send-email",
        ),
    )


@app.route("/yard-sign", methods=["POST", "OPTIONS"])
def yard_sign():
    if request.method == "OPTIONS":
        return ("", 204)

    # Before the limiter, for the reason given in `send_email`.
    if _origin_rejected("/yard-sign"):
        return _cross_site_response()

    scope = "yard-sign"
    refused = _consume_rate_limit(scope)
    if refused is not None:
        retry_after, tier = refused
        return _rate_limited_response(retry_after, tier=tier, scope=scope)

    return _within_capacity(
        "/yard-sign",
        lambda: _handle_form_submission(
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
        ),
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(env("PORT", "5000")), debug=False)

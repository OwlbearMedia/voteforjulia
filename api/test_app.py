import json
import smtplib
import types
import unittest
from collections import deque
from time import monotonic
from unittest import mock

import api.app as app_module
import api.rate_limit_store as rate_limit_store
from api.config import EmailConfig, SheetsConfig
from api.models import (
    MAX_EMAIL_LENGTH,
    MAX_FIRST_NAME_LENGTH,
    MAX_HELP_WAY_LENGTH,
    MAX_HELP_WAYS_COUNT,
    MAX_LAST_NAME_LENGTH,
    MAX_MESSAGE_LENGTH,
    MAX_PHONE_LENGTH,
)


class AppCorsTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_allowed_origins = set(app_module._CORS_ALLOWED_ORIGINS)
        app_module._CORS_ALLOWED_ORIGINS = {
            "https://test.voteforjulia.com",
            "https://test-api.voteforjulia.com",
        }
        self.client = app_module.app.test_client()

    def tearDown(self) -> None:
        app_module._CORS_ALLOWED_ORIGINS = self._orig_allowed_origins

    def test_preflight_includes_cors_headers_for_allowed_origin(self) -> None:
        response = self.client.options(
            "/send-email",
            headers={
                "Origin": "https://test.voteforjulia.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 204)
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            "https://test.voteforjulia.com",
        )
        self.assertEqual(response.headers.get("Vary"), "Origin")
        self.assertEqual(response.headers.get("Access-Control-Allow-Methods"), "POST, OPTIONS")
        # The trace headers must survive preflight or the browser agent's
        # distributed tracing headers are stripped and browser/API telemetry
        # never correlates.
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Headers"),
            "Content-Type, newrelic, traceparent, tracestate",
        )

    def test_preflight_omits_cors_headers_for_disallowed_origin(self) -> None:
        response = self.client.options(
            "/send-email",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
        # Vary is unconditional so a shared cache never serves the allowed and
        # disallowed variants of this response interchangeably.
        self.assertEqual(response.headers.get("Vary"), "Origin")

    def test_vary_origin_is_set_when_no_origin_header_is_sent(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Vary"), "Origin")


class AppSecurityHeaderTests(unittest.TestCase):
    """Headers the API sends on its own, ADR-0018.

    The site's edge policy lives in `.htaccess` (ADR-0010), but the API
    subdomain's docroot is not in this repo, so these are the API's to set and
    the only place they can be tested.
    """

    def setUp(self) -> None:
        self.client = app_module.app.test_client()

    def test_hsts_and_nosniff_are_sent(self) -> None:
        response = self.client.get("/health")

        self.assertEqual(
            response.headers.get("Strict-Transport-Security"),
            "max-age=31536000; includeSubDomains",
        )
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")

    def test_they_are_sent_on_error_responses_too(self) -> None:
        # A 404 is rendered by the framework rather than a view, and an
        # after_request hook is what keeps the two paths from disagreeing.
        response = self.client.get("/no-such-endpoint")

        self.assertEqual(response.status_code, 404)
        self.assertIn("Strict-Transport-Security", response.headers)
        self.assertEqual(response.headers.get("X-Content-Type-Options"), "nosniff")


class AppClientKeyTests(unittest.TestCase):
    """`/health` echoes the key the limiter derives, ADR-0018.

    ADR-0009, 0014 and 0016 all assume `remote_addr` is the caller rather than
    something in front of the app, and nothing had ever confirmed that on the
    host. If it resolved to a proxy, every per-IP control would be one shared
    bucket and a single caller could 429 the whole site.
    """

    def setUp(self) -> None:
        self.client = app_module.app.test_client()

    def test_health_reports_the_key_the_limiter_uses(self) -> None:
        # Both sides derived from the same environment, so this pins "the
        # endpoint reports what the limiter keys on" rather than restating the
        # implementation -- plus the literal, so an echo of some other value
        # that happened to agree would still fail.
        environ = {"REMOTE_ADDR": "198.51.100.9"}

        with app_module.app.test_request_context("/health", environ_base=environ):
            expected = app_module._rate_limit_key()

        reported = self.client.get("/health", environ_base=environ).get_json()["client"]

        self.assertEqual(reported, expected)
        self.assertEqual(reported, "198.51.100.9")

    def test_it_follows_the_trusted_header_when_one_is_configured(self) -> None:
        # The diagnostic has to reflect whatever `_rate_limit_key` actually
        # does, including the ADR-0014 forwarding-header path, or reading it
        # after putting Cloudflare in front would mislead.
        with mock.patch.object(app_module, "_TRUSTED_CLIENT_IP_HEADER", "CF-Connecting-IP"):
            response = self.client.get("/health", headers={"CF-Connecting-IP": "203.0.113.7"})

        self.assertEqual(response.get_json()["client"], "203.0.113.7")


class AppErrorShapeTests(unittest.TestCase):
    """Framework-raised errors come back as JSON, like the handlers' own do."""

    def setUp(self) -> None:
        self.client = app_module.app.test_client()

    def test_unknown_route_returns_json(self) -> None:
        response = self.client.get("/does-not-exist")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.mimetype, "application/json")
        self.assertIn("error", response.get_json())

    def test_wrong_method_returns_json_and_keeps_allow(self) -> None:
        # `Allow` is the reason the handler rebuilds Werkzeug's own response
        # instead of calling jsonify: a 405 without it is a less useful 405, and
        # a jsonify-based handler would silently drop it.
        response = self.client.get("/send-email")

        self.assertEqual(response.status_code, 405)
        self.assertEqual(response.mimetype, "application/json")
        self.assertIn("error", response.get_json())
        self.assertIn("POST", response.headers.get("Allow", ""))

    def test_error_responses_still_carry_cors_headers(self) -> None:
        # The error handler returns a fresh response object, so it bypasses the
        # view entirely -- this checks the after_request hook still runs over
        # it. Without CORS headers the browser reports a generic network error
        # instead of surfacing the status the form could act on.
        response = self.client.get(
            "/does-not-exist", headers={"Origin": "https://voteforjulia.com"}
        )

        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"), "https://voteforjulia.com"
        )
        self.assertEqual(response.headers.get("Vary"), "Origin")


class AppServiceRootTests(unittest.TestCase):
    """`GET /` answers with the easter egg instead of a 404."""

    def setUp(self) -> None:
        self.client = app_module.app.test_client()

    def test_the_root_is_a_json_200(self) -> None:
        # The whole point: a scanner sweeping the origin gets an answer rather
        # than a 404, while a path that really matches nothing still does not.
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.mimetype, "application/json")
        self.assertEqual(self.client.get("/not-a-route").status_code, 404)

    def test_it_is_cacheable(self) -> None:
        # Pinned as a property of a fixed document, not as an origin-hit saving:
        # the free tier caches by extension (ADR-0019), so nothing at the edge
        # acts on this today. See the note in `service_root`.
        self.assertEqual(
            self.client.get("/").headers.get("Cache-Control"),
            "public, max-age=3600",
        )

    def test_the_keys_keep_their_written_order(self) -> None:
        # `jsonify` sorts keys, which would alphabetise the document and lose
        # the thing it is imitating. Asserting the served order rather than the
        # serializer's arguments, so a swap back to `jsonify` fails here.
        served = json.loads(self.client.get("/").get_data(as_text=True))

        self.assertEqual(list(served), list(app_module._MANKATO_CONFIG))
        self.assertEqual(
            list(served["favorites"]),
            list(app_module._MANKATO_CONFIG["favorites"]),
        )
        self.assertNotEqual(list(served), sorted(served))

    def test_every_path_it_quotes_is_a_real_route(self) -> None:
        # The decoration may say anything; the endpoint paths in it are the one
        # part a reader could act on. Renaming a route without editing the
        # document would leave it directing people at a 404.
        registered = {rule.rule for rule in app_module.app.url_map.iter_rules()}

        def paths(node):
            if isinstance(node, dict):
                for value in node.values():
                    yield from paths(value)
            elif isinstance(node, list):
                for value in node:
                    yield from paths(value)
            elif isinstance(node, str) and node.startswith("/"):
                yield node

        quoted = set(paths(app_module._MANKATO_CONFIG))

        self.assertTrue(quoted, "the document quotes no endpoint paths to check")
        self.assertEqual(quoted - registered, set())


class AppRequestSizeTests(unittest.TestCase):
    """A body past MAX_CONTENT_LENGTH is refused before it is buffered."""

    def setUp(self) -> None:
        self.client = app_module.app.test_client()
        self.oversized = "x" * (app_module.app.config["MAX_CONTENT_LENGTH"] + 1)

    def test_oversized_json_body_is_rejected(self) -> None:
        # The encoding that matters: form posts were already bounded by Flask's
        # MAX_FORM_MEMORY_SIZE default, but it does not cover application/json,
        # which is what the site actually posts. Before the cap this was read
        # and parsed in full, then rejected on a 500-character field limit.
        response = self.client.post(
            "/send-email",
            data=json.dumps(
                {"firstName": "A", "email": "a@example.com", "message": self.oversized}
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.mimetype, "application/json")
        self.assertIn("error", response.get_json())

    def test_oversized_form_body_is_rejected(self) -> None:
        response = self.client.post(
            "/send-email",
            data={"firstName": "A", "email": "a@example.com", "message": self.oversized},
            content_type="application/x-www-form-urlencoded",
        )

        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.mimetype, "application/json")

    def test_a_normal_submission_is_well_under_the_cap(self) -> None:
        # The negative half: a cap set below what the forms legitimately send
        # would reject real submissions, and every test above would still pass.
        # Every field at its documented maximum, plus JSON overhead.
        largest_legitimate = json.dumps(
            {
                "firstName": "x" * MAX_FIRST_NAME_LENGTH,
                "lastName": "x" * MAX_LAST_NAME_LENGTH,
                "email": "x" * MAX_EMAIL_LENGTH,
                "phone": "x" * MAX_PHONE_LENGTH,
                "message": "x" * MAX_MESSAGE_LENGTH,
                "helpWays": ["x" * MAX_HELP_WAY_LENGTH] * MAX_HELP_WAYS_COUNT,
            }
        )

        self.assertLess(
            len(largest_legitimate.encode()), app_module.app.config["MAX_CONTENT_LENGTH"]
        )


class AppRateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_rate_limit_window_seconds = app_module._RATE_LIMIT_WINDOW_SECONDS
        self._orig_rate_limit_max_requests = app_module._RATE_LIMIT_MAX_REQUESTS
        self._orig_rate_limit_buckets = app_module._RATE_LIMIT_BUCKETS
        self._orig_trusted_client_ip_header = app_module._TRUSTED_CLIENT_IP_HEADER
        self._orig_next_bucket_sweep_at = app_module._next_bucket_sweep_at
        self._orig_rate_limit_max_buckets = app_module._RATE_LIMIT_MAX_BUCKETS
        self._orig_load_email_config = app_module.load_email_config
        self._orig_load_sheets_config = app_module.load_sheets_config
        self._orig_send_submission_email = app_module.send_submission_email
        self._orig_send_confirmation_email = app_module.send_confirmation_email
        self._orig_append_row = app_module.append_row

        app_module._RATE_LIMIT_WINDOW_SECONDS = 60
        app_module._RATE_LIMIT_MAX_REQUESTS = 1
        app_module._RATE_LIMIT_BUCKETS = {}
        # No proxy trusted, matching the shipped default. Tests that need a
        # forwarding header honoured opt in explicitly.
        app_module._TRUSTED_CLIENT_IP_HEADER = ""
        # In the past, so the first request of each test sweeps. The sweep is
        # now scheduled rather than per-request, and the schedule is module
        # state that would otherwise leak between tests.
        app_module._next_bucket_sweep_at = 0.0

        self.sent_submissions = []
        self.confirmation_submissions = []
        self.sheet_rows = []

        self.email_config_calls = []

        def fake_load_email_config(recipient_env="RECIPIENT_EMAIL"):
            self.email_config_calls.append(recipient_env)
            return EmailConfig(
                smtp_server="mail.example.com",
                smtp_port=465,
                smtp_security="ssl",
                email_address="info@example.com",
                email_password="placeholder-value",
                recipients=["team@example.com"],
                plain_text_confirmation_only=False,
            )

        app_module.load_email_config = fake_load_email_config
        app_module.load_sheets_config = lambda: SheetsConfig(
            spreadsheet_id="",
            worksheet="Sheet1",
            service_account_file="",
            service_account_json="",
        )

        def fake_send_submission_email(config, submission):
            self.sent_submissions.append(submission)
            return {}

        def fake_send_confirmation_email(config, submission):
            self.confirmation_submissions.append(submission)
            return {}

        def fake_append_row(config, row):
            self.sheet_rows.append(row)

        app_module.send_submission_email = fake_send_submission_email
        app_module.send_confirmation_email = fake_send_confirmation_email
        app_module.append_row = fake_append_row
        self.client = app_module.app.test_client()

    def tearDown(self) -> None:
        app_module._RATE_LIMIT_WINDOW_SECONDS = self._orig_rate_limit_window_seconds
        app_module._RATE_LIMIT_MAX_REQUESTS = self._orig_rate_limit_max_requests
        app_module._RATE_LIMIT_BUCKETS = self._orig_rate_limit_buckets
        app_module._TRUSTED_CLIENT_IP_HEADER = self._orig_trusted_client_ip_header
        app_module._next_bucket_sweep_at = self._orig_next_bucket_sweep_at
        app_module._RATE_LIMIT_MAX_BUCKETS = self._orig_rate_limit_max_buckets
        app_module.load_email_config = self._orig_load_email_config
        app_module.load_sheets_config = self._orig_load_sheets_config
        app_module.send_submission_email = self._orig_send_submission_email
        app_module.send_confirmation_email = self._orig_send_confirmation_email
        app_module.append_row = self._orig_append_row

    def test_send_email_returns_429_after_rate_limit_is_exceeded(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
            "message": "Count me in",
        }

        first_response = self.client.post("/send-email", json=payload)
        second_response = self.client.post("/send-email", json=payload)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)
        # 60, not 59: both requests land in the same instant, so the oldest
        # leaves the window a full 60 seconds later. Rounding down here was the
        # bug -- it told the client to retry while still inside the window.
        self.assertEqual(second_response.headers.get("Retry-After"), "60")
        self.assertEqual(
            second_response.get_json(),
            {"error": "Too many requests. Please try again later."},
        )
        self.assertEqual(len(self.sent_submissions), 1)
        self.assertEqual(len(self.confirmation_submissions), 1)
        self.assertEqual(len(self.sheet_rows), 1)

    def test_burst_tier_429_is_reported_to_the_new_relic_agent(self) -> None:
        # A 429 is a returned response, not a raised exception, so the agent
        # records it with no error and nothing naming the tier. These two
        # attributes are the entire signal the alert condition runs on.
        agent = types.SimpleNamespace(
            attributes=[],
            add_custom_attribute=lambda k, v: agent.attributes.append((k, v)),
        )
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
            "message": "Count me in",
        }

        with mock.patch.object(app_module, "_newrelic_agent", agent):
            self.client.post("/send-email", json=payload)
            response = self.client.post("/send-email", json=payload)

        self.assertEqual(response.status_code, 429)
        self.assertIn(("rate_limit.tier", "burst"), agent.attributes)
        self.assertIn(("rate_limit.scope", "send-email"), agent.attributes)

    def test_an_allowed_request_reports_no_rate_limit_attributes(self) -> None:
        agent = types.SimpleNamespace(
            attributes=[],
            add_custom_attribute=lambda k, v: agent.attributes.append((k, v)),
        )
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
            "message": "Count me in",
        }

        with mock.patch.object(app_module, "_newrelic_agent", agent):
            response = self.client.post("/send-email", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(agent.attributes, [])

    def test_the_client_address_is_never_reported(self) -> None:
        # `_rate_limit_key()` is a caller identity (ADR-0014). A telemetry
        # backend is not a place it has to be, so it does not go there.
        app_module._TRUSTED_CLIENT_IP_HEADER = "X-Forwarded-For"
        agent = types.SimpleNamespace(
            attributes=[],
            add_custom_attribute=lambda k, v: agent.attributes.append((k, v)),
        )
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
            "message": "Count me in",
        }
        headers = {"X-Forwarded-For": "203.0.113.77"}

        with mock.patch.object(app_module, "_newrelic_agent", agent):
            self.client.post("/send-email", json=payload, headers=headers)
            response = self.client.post("/send-email", json=payload, headers=headers)

        self.assertEqual(response.status_code, 429)
        self.assertNotIn("203.0.113.77", str(agent.attributes))

    def test_a_refusal_survives_a_broken_agent(self) -> None:
        # Reporting may never be the thing that refuses a supporter.
        def explode(*args, **kwargs):
            raise RuntimeError("agent is unwell")

        agent = types.SimpleNamespace(add_custom_attribute=explode)
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
            "message": "Count me in",
        }

        with mock.patch.object(app_module, "_newrelic_agent", agent):
            self.client.post("/send-email", json=payload)
            response = self.client.post("/send-email", json=payload)

        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.headers.get("Retry-After"), "60")

    def test_forwarding_headers_do_not_key_the_bucket_by_default(self) -> None:
        # THE regression test for the bypass. Nothing fronts this API, so a
        # forwarding header is a string the caller picked. While these were
        # trusted unconditionally, a different value per request minted a fresh
        # bucket every time and the limiter did nothing at all -- twelve
        # requests against a limit of five, zero refused.
        payload = {"firstName": "Julia", "email": "julia@example.com"}

        first = self.client.post(
            "/send-email", json=payload, headers={"CF-Connecting-IP": "203.0.113.1"}
        )
        second = self.client.post(
            "/send-email", json=payload, headers={"CF-Connecting-IP": "203.0.113.2"}
        )
        third = self.client.post(
            "/send-email", json=payload, headers={"X-Forwarded-For": "203.0.113.3"}
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(third.status_code, 429)
        # All three collapsed onto the socket address, the only value here the
        # caller cannot choose.
        self.assertEqual(list(app_module._RATE_LIMIT_BUCKETS), ["send-email:127.0.0.1"])

    def test_configured_header_keys_the_bucket_when_trusted(self) -> None:
        # The other half: opting in has to actually work, or putting Cloudflare
        # in front would silently lump every visitor into a single bucket.
        app_module._TRUSTED_CLIENT_IP_HEADER = "CF-Connecting-IP"
        payload = {"firstName": "Julia", "email": "julia@example.com"}

        first = self.client.post(
            "/send-email", json=payload, headers={"CF-Connecting-IP": "203.0.113.1"}
        )
        second = self.client.post(
            "/send-email", json=payload, headers={"CF-Connecting-IP": "203.0.113.2"}
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(
            sorted(app_module._RATE_LIMIT_BUCKETS),
            ["send-email:203.0.113.1", "send-email:203.0.113.2"],
        )

    def test_only_the_configured_header_is_trusted(self) -> None:
        # Trusting one header must not re-trust the rest. With CF-Connecting-IP
        # configured, X-Forwarded-For is still caller input and must not split
        # the bucket.
        app_module._TRUSTED_CLIENT_IP_HEADER = "CF-Connecting-IP"
        payload = {"firstName": "Julia", "email": "julia@example.com"}

        first_response = self.client.post(
            "/send-email",
            json=payload,
            headers={"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "198.51.100.30"},
        )
        second_response = self.client.post(
            "/send-email",
            json=payload,
            headers={"CF-Connecting-IP": "203.0.113.7", "X-Forwarded-For": "198.51.100.31"},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)

    def test_trusted_header_uses_the_last_hop_only(self) -> None:
        # A proxy appends the connecting address to whatever the client sent,
        # so earlier entries stay caller-controlled even on a trusted header.
        app_module._TRUSTED_CLIENT_IP_HEADER = "X-Forwarded-For"
        payload = {"firstName": "Julia", "email": "julia@example.com"}

        first_response = self.client.post(
            "/send-email",
            json=payload,
            headers={"X-Forwarded-For": "spoofed-one, 203.0.113.5"},
        )
        second_response = self.client.post(
            "/send-email",
            json=payload,
            headers={"X-Forwarded-For": "spoofed-two, 203.0.113.5"},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)

    def test_retry_after_covers_the_full_remaining_wait(self) -> None:
        # Truncating this advertised a wait still inside the window, so a client
        # honouring Retry-After exactly earned a second 429 for doing the right
        # thing. Rounding up is what makes the header safe to obey literally.
        payload = {"firstName": "Julia", "email": "julia@example.com"}
        self.client.post("/send-email", json=payload)

        blocked = self.client.post("/send-email", json=payload)
        retry_after = int(blocked.headers["Retry-After"])

        bucket = app_module._RATE_LIMIT_BUCKETS["send-email:127.0.0.1"]
        true_wait = bucket[0] + app_module._RATE_LIMIT_WINDOW_SECONDS - monotonic()
        self.assertGreaterEqual(retry_after, true_wait)

    def test_rate_limit_evicts_stale_buckets(self) -> None:
        stale_key = "send-email:198.51.100.99"
        app_module._RATE_LIMIT_BUCKETS[stale_key] = deque(
            [monotonic() - app_module._RATE_LIMIT_WINDOW_SECONDS - 1]
        )

        response = self.client.post(
            "/send-email",
            json={"firstName": "Julia", "email": "julia@example.com"},
            headers={"X-Forwarded-For": "198.51.100.40"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(stale_key, app_module._RATE_LIMIT_BUCKETS)

    def test_sweep_is_scheduled_rather_than_run_per_request(self) -> None:
        # The sweep walks every bucket, so doing it per request made each
        # request cost O(live keys) -- measured at 0.23ms with 1k buckets and
        # 3.06ms with 20k. Once per window bounds memory just as well, because
        # nothing outlives its expiry by more than a window.
        app_module._next_bucket_sweep_at = monotonic() + 3600
        stale_key = "send-email:198.51.100.99"
        app_module._RATE_LIMIT_BUCKETS[stale_key] = deque([monotonic() - 10_000])

        self.client.post("/send-email", json={"firstName": "Julia", "email": "julia@example.com"})

        self.assertIn(stale_key, app_module._RATE_LIMIT_BUCKETS)

    def test_the_current_key_is_pruned_even_between_sweeps(self) -> None:
        # The counterpart: deferring the sweep must not let a client be judged
        # against a stale window. Its own bucket is pruned inline every time.
        app_module._next_bucket_sweep_at = monotonic() + 3600
        expired = monotonic() - app_module._RATE_LIMIT_WINDOW_SECONDS - 1
        app_module._RATE_LIMIT_BUCKETS["send-email:127.0.0.1"] = deque([expired])

        response = self.client.post(
            "/send-email", json={"firstName": "Julia", "email": "julia@example.com"}
        )

        self.assertEqual(response.status_code, 200)

    def test_bucket_count_is_capped(self) -> None:
        # The safety valve for a burst of new keys arriving between sweeps.
        # Eviction resets those clients' allowances, so it fails open by
        # design -- better than refusing real submissions or growing until the
        # worker is killed.
        app_module._RATE_LIMIT_MAX_BUCKETS = 20
        app_module._next_bucket_sweep_at = monotonic() + 3600
        now = monotonic()
        for index in range(50):
            app_module._RATE_LIMIT_BUCKETS[f"send-email:198.51.100.{index}"] = deque([now - index])

        self.client.post("/send-email", json={"firstName": "Julia", "email": "julia@example.com"})

        self.assertLessEqual(len(app_module._RATE_LIMIT_BUCKETS), 20)
        # Least-recently-active go first, so the freshest keys survive.
        self.assertIn("send-email:198.51.100.0", app_module._RATE_LIMIT_BUCKETS)
        self.assertNotIn("send-email:198.51.100.49", app_module._RATE_LIMIT_BUCKETS)

    def test_hitting_the_cap_does_not_force_a_sweep_on_every_request(self) -> None:
        # The property the low-water mark buys. Without headroom the dict sits
        # pinned at the cap and every subsequent request re-sweeps and re-sorts.
        app_module._RATE_LIMIT_MAX_BUCKETS = 20
        app_module._next_bucket_sweep_at = monotonic() + 3600
        now = monotonic()
        for index in range(25):
            app_module._RATE_LIMIT_BUCKETS[f"other:198.51.100.{index}"] = deque([now - index])

        sweeps = []
        real_sweep = app_module._sweep_expired_buckets
        app_module._sweep_expired_buckets = lambda cutoff: (
            sweeps.append(cutoff),
            real_sweep(cutoff),
        )[-1]
        try:
            for _ in range(5):
                self.client.post(
                    "/send-email", json={"firstName": "Julia", "email": "j@example.com"}
                )
        finally:
            app_module._sweep_expired_buckets = real_sweep

        self.assertEqual(len(sweeps), 1)

    def test_send_email_returns_json_error_when_email_config_is_invalid(self) -> None:
        def raise_config_error(recipient_env="RECIPIENT_EMAIL"):
            raise ValueError("SMTP_SECURITY must be one of: auto, ssl, starttls")

        app_module.load_email_config = raise_config_error

        response = self.client.post(
            "/send-email",
            json={"firstName": "Julia", "email": "julia@example.com"},
            headers={"X-Forwarded-For": "198.51.100.41"},
        )

        self.assertEqual(response.status_code, 500)
        self.assertEqual(
            response.get_json(),
            {"error": "Server email configuration is invalid."},
        )

    def test_send_email_rejects_control_characters_in_header_bound_fields(self) -> None:
        payload = {
            "firstName": "Julia\r",
            "email": "julia@example.com",
        }

        response = self.client.post(
            "/send-email",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.10"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"error": "First name contains invalid characters."},
        )
        self.assertEqual(len(self.sent_submissions), 0)

    def test_send_email_rejects_oversized_message(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
            "message": "x" * (MAX_MESSAGE_LENGTH + 1),
        }

        response = self.client.post(
            "/send-email",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.11"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"error": f"Message must be {MAX_MESSAGE_LENGTH} characters or fewer."},
        )
        self.assertEqual(len(self.sent_submissions), 0)

    def test_send_email_logs_field_names_without_values(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
            "phone": "507-555-0100",
            "message": "",
        }

        with self.assertLogs(app_module.logger, level="INFO") as captured:
            response = self.client.post(
                "/send-email",
                json=payload,
                headers={"X-Forwarded-For": "198.51.100.12"},
            )

        self.assertEqual(response.status_code, 200)
        field_logs = [line for line in captured.output if "submission fields" in line]
        self.assertEqual(len(field_logs), 1)
        self.assertIn("/send-email", field_logs[0])
        # Names of the filled-in fields only; the blank one is omitted.
        self.assertIn("email, firstName, phone", field_logs[0])
        self.assertNotIn("message", field_logs[0])
        # None of the submitted values appear anywhere in the log output.
        for value in ("Julia", "julia@example.com", "507-555-0100"):
            self.assertNotIn(value, "\n".join(captured.output))

    def test_send_email_does_not_log_values_for_validation_errors(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "not-an-email",
        }

        with self.assertLogs(app_module.logger, level="INFO") as captured:
            response = self.client.post(
                "/send-email",
                json=payload,
                headers={"X-Forwarded-For": "198.51.100.13"},
            )

        self.assertEqual(response.status_code, 400)
        # A 4xx means the submitter still has their data and can retry, so
        # there is nothing to recover and nothing to log.
        self.assertNotIn("not-an-email", "\n".join(captured.output))

    def test_send_email_logs_request_body_when_the_submission_is_lost(self) -> None:
        def raise_smtp_error(config, submission):
            raise smtplib.SMTPException("boom")

        app_module.send_submission_email = raise_smtp_error

        with self.assertLogs(app_module.logger, level="INFO") as captured:
            response = self.client.post(
                "/send-email",
                json={"firstName": "Julia", "email": "julia@example.com"},
                headers={"X-Forwarded-For": "198.51.100.14"},
            )

        self.assertEqual(response.status_code, 502)
        body_logs = [line for line in captured.output if "unrecoverable request body" in line]
        self.assertEqual(len(body_logs), 1)
        self.assertIn("julia@example.com", body_logs[0])

    def test_send_email_truncates_oversized_request_body_in_logs(self) -> None:
        def raise_smtp_error(config, submission):
            raise smtplib.SMTPException("boom")

        app_module.send_submission_email = raise_smtp_error
        # Padded with an unrecognised key so the body is oversized without
        # tripping the per-field length limits, which would 400 before the
        # send is ever attempted.
        oversized = "x" * (app_module._MAX_LOGGED_BODY_CHARS + 100)

        with self.assertLogs(app_module.logger, level="INFO") as captured:
            self.client.post(
                "/send-email",
                json={"firstName": "Julia", "email": "julia@example.com", "padding": oversized},
                headers={"X-Forwarded-For": "198.51.100.15"},
            )

        body_logs = [line for line in captured.output if "unrecoverable request body" in line]
        self.assertEqual(len(body_logs), 1)
        self.assertIn("…[truncated]", body_logs[0])
        self.assertNotIn(oversized, body_logs[0])


class AppYardSignTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_rate_limit_window_seconds = app_module._RATE_LIMIT_WINDOW_SECONDS
        self._orig_rate_limit_max_requests = app_module._RATE_LIMIT_MAX_REQUESTS
        self._orig_rate_limit_buckets = app_module._RATE_LIMIT_BUCKETS
        self._orig_trusted_client_ip_header = app_module._TRUSTED_CLIENT_IP_HEADER
        self._orig_next_bucket_sweep_at = app_module._next_bucket_sweep_at
        self._orig_rate_limit_max_buckets = app_module._RATE_LIMIT_MAX_BUCKETS
        self._orig_load_email_config = app_module.load_email_config
        self._orig_load_sheets_config = app_module.load_sheets_config
        self._orig_send_yard_sign_request_email = app_module.send_yard_sign_request_email
        self._orig_send_yard_sign_confirmation_email = app_module.send_yard_sign_confirmation_email
        self._orig_append_row = app_module.append_row

        app_module._RATE_LIMIT_WINDOW_SECONDS = 60
        app_module._RATE_LIMIT_MAX_REQUESTS = 5
        app_module._RATE_LIMIT_BUCKETS = {}

        self.sent_requests = []
        self.confirmation_requests = []
        self.sheet_rows = []
        self.sheets_config_calls = []
        self.email_config_calls = []

        def fake_load_email_config(recipient_env="RECIPIENT_EMAIL"):
            self.email_config_calls.append(recipient_env)
            return EmailConfig(
                smtp_server="mail.example.com",
                smtp_port=465,
                smtp_security="ssl",
                email_address="info@example.com",
                email_password="placeholder-value",
                recipients=["team@example.com"],
                plain_text_confirmation_only=False,
            )

        app_module.load_email_config = fake_load_email_config

        def fake_load_sheets_config(worksheet_env, default_worksheet):
            self.sheets_config_calls.append((worksheet_env, default_worksheet))
            return SheetsConfig(
                spreadsheet_id="",
                worksheet=default_worksheet,
                service_account_file="",
                service_account_json="",
            )

        def fake_send_yard_sign_request_email(config, yard_sign_request):
            self.sent_requests.append(yard_sign_request)
            return {}

        def fake_send_yard_sign_confirmation_email(config, yard_sign_request):
            self.confirmation_requests.append(yard_sign_request)
            return {}

        def fake_append_row(config, row):
            self.sheet_rows.append(row)

        app_module.load_sheets_config = fake_load_sheets_config
        app_module.send_yard_sign_request_email = fake_send_yard_sign_request_email
        app_module.send_yard_sign_confirmation_email = fake_send_yard_sign_confirmation_email
        app_module.append_row = fake_append_row
        self.client = app_module.app.test_client()

    def tearDown(self) -> None:
        app_module._RATE_LIMIT_WINDOW_SECONDS = self._orig_rate_limit_window_seconds
        app_module._RATE_LIMIT_MAX_REQUESTS = self._orig_rate_limit_max_requests
        app_module._RATE_LIMIT_BUCKETS = self._orig_rate_limit_buckets
        app_module._TRUSTED_CLIENT_IP_HEADER = self._orig_trusted_client_ip_header
        app_module._next_bucket_sweep_at = self._orig_next_bucket_sweep_at
        app_module._RATE_LIMIT_MAX_BUCKETS = self._orig_rate_limit_max_buckets
        app_module.load_email_config = self._orig_load_email_config
        app_module.load_sheets_config = self._orig_load_sheets_config
        app_module.send_yard_sign_request_email = self._orig_send_yard_sign_request_email
        app_module.send_yard_sign_confirmation_email = self._orig_send_yard_sign_confirmation_email
        app_module.append_row = self._orig_append_row

    def test_yard_sign_sends_emails_and_appends_sheet_row(self) -> None:
        payload = {
            "firstName": "Julia",
            "lastName": "Hamann",
            "email": "julia@example.com",
            "phone": "555-555-5555",
            "address": "123 Main St, Mankato, MN 56001",
            "preferredPayment": ["Online", "Check"],
        }

        response = self.client.post(
            "/yard-sign",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.20"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.sent_requests), 1)
        self.assertEqual(len(self.confirmation_requests), 1)
        self.assertEqual(len(self.sheet_rows), 1)
        self.assertEqual(self.sheet_rows[0][-1], "Online, Check")
        self.assertEqual(
            self.sheets_config_calls,
            [("GOOGLE_SHEETS_YARDSIGN_WORKSHEET", "Yard Signs")],
        )
        self.assertEqual(self.email_config_calls, ["RECIPIENT_EMAIL_SIGNS"])

    def test_yard_sign_requires_address(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
        }

        response = self.client.post(
            "/yard-sign",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.21"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json(), {"error": "Address is required."})
        self.assertEqual(len(self.sent_requests), 0)

    def test_yard_sign_rejects_control_characters_in_header_bound_fields(self) -> None:
        payload = {
            "firstName": "Julia\r",
            "email": "julia@example.com",
            "address": "123 Main St, Mankato, MN 56001",
        }

        response = self.client.post(
            "/yard-sign",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.22"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"error": "First name contains invalid characters."},
        )
        self.assertEqual(len(self.sent_requests), 0)


class AppDeepHealthTests(unittest.TestCase):
    """Covers /health/deep — the check a synthetic monitor watches.

    The dependency checks are replaced wholesale: a real one would open a
    socket to the live mail server and to Google.
    """

    def setUp(self) -> None:
        self._orig_verify_smtp = app_module.verify_smtp_credentials
        self._orig_verify_sheets = app_module.verify_sheets_access
        self._orig_rate_limit_max_requests = app_module._RATE_LIMIT_MAX_REQUESTS
        self._orig_rate_limit_buckets = app_module._RATE_LIMIT_BUCKETS

        app_module._RATE_LIMIT_MAX_REQUESTS = 5
        app_module._RATE_LIMIT_BUCKETS = {}
        self._ok()
        self.client = app_module.app.test_client()

    def tearDown(self) -> None:
        app_module.verify_smtp_credentials = self._orig_verify_smtp
        app_module.verify_sheets_access = self._orig_verify_sheets
        app_module._RATE_LIMIT_MAX_REQUESTS = self._orig_rate_limit_max_requests
        app_module._RATE_LIMIT_BUCKETS = self._orig_rate_limit_buckets

    def _ok(self) -> None:
        app_module.verify_smtp_credentials = lambda config: None
        app_module.verify_sheets_access = lambda config: None

    @staticmethod
    def _raise(exc: Exception):
        def _check(config):
            raise exc

        return _check

    def _get(self, path: str = "/health/deep", ip: str = "203.0.113.90"):
        return self.client.get(path, headers={"X-Forwarded-For": ip})

    def test_reports_ok_when_both_dependencies_pass(self) -> None:
        response = self._get()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"status": "ok", "smtp": "ok", "sheets": "ok"},
        )

    def test_smtp_auth_failure_reports_503(self) -> None:
        # The exact shape of the $-in-password incident: the mail server was
        # reachable and /health was green, but LOGIN was rejected.
        app_module.verify_smtp_credentials = self._raise(
            smtplib.SMTPAuthenticationError(535, b"Incorrect authentication data")
        )

        response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {"status": "degraded", "smtp": "fail", "sheets": "ok"},
        )

    def test_sheets_failure_reports_503(self) -> None:
        app_module.verify_sheets_access = self._raise(ValueError("credentials are not configured"))

        response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {"status": "degraded", "smtp": "ok", "sheets": "fail"},
        )

    def test_both_checks_run_even_when_the_first_fails(self) -> None:
        # Short-circuiting would report sheets as healthy without testing it,
        # so a two-dependency outage would look like a one-dependency outage.
        app_module.verify_smtp_credentials = self._raise(OSError("connection refused"))
        app_module.verify_sheets_access = self._raise(OSError("connection refused"))

        response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.get_json(),
            {"status": "degraded", "smtp": "fail", "sheets": "fail"},
        )

    def test_failure_response_does_not_leak_exception_text(self) -> None:
        # smtplib and googleapiclient quote the credentials they were handed,
        # and this endpoint is unauthenticated.
        app_module.verify_smtp_credentials = self._raise(
            smtplib.SMTPAuthenticationError(535, b"auth failed for hunter2@voteforjulia.com")
        )

        response = self._get()

        self.assertNotIn("hunter2", response.get_data(as_text=True))

    def _count_probes(self) -> dict[str, int]:
        """Replace both dependency checks with counters that always pass."""
        counts = {"smtp": 0, "sheets": 0}

        def smtp(_config):
            counts["smtp"] += 1

        def sheets(_config):
            counts["sheets"] += 1

        app_module.verify_smtp_credentials = smtp
        app_module.verify_sheets_access = sheets
        return counts

    def _age_the_cache(self, seconds: float) -> None:
        """Backdate the cached result instead of sleeping through the TTL."""
        cached = app_module._deep_health_cache
        app_module._deep_health_cache = cached._replace(produced_at=cached.produced_at - seconds)

    def test_repeated_calls_reuse_one_probe_result(self) -> None:
        """The amplification bound, and the whole reason the cache exists.

        A probe is a real SMTP `LOGIN` against the campaign's own mail account
        plus a Google Sheets read. Run per request, one cheap unauthenticated
        GET bought two expensive calls against the dependencies every form on
        the site needs, and enough of them gets the mail host to throttle us --
        which takes down sending, not just the probe.
        """
        counts = self._count_probes()
        app_module._RATE_LIMIT_MAX_REQUESTS = 50

        statuses = [self._get().status_code for _ in range(20)]

        self.assertEqual(statuses, [200] * 20)
        self.assertEqual(counts, {"smtp": 1, "sheets": 1})

    def test_a_failing_probe_is_cached_too(self) -> None:
        """Otherwise the amplifier returns exactly when it costs the most.

        Caching only successes would leave a dependency that is already failing
        to be hammered once per request for as long as it stays down.
        """
        calls = {"n": 0}

        def failing(_config):
            calls["n"] += 1
            raise OSError("connection refused")

        app_module.verify_smtp_credentials = failing
        app_module._RATE_LIMIT_MAX_REQUESTS = 50

        statuses = [self._get().status_code for _ in range(5)]

        self.assertEqual(statuses, [503] * 5)
        self.assertEqual(calls["n"], 1)

    def test_an_outage_is_reported_once_the_cached_result_expires(self) -> None:
        """Both halves of the trade the cache makes.

        Up to one TTL of staleness is the price, so the test asserts the stale
        window exists rather than pretending it does not — and then that it
        ends. The monitor polls every 15 minutes against a 60-second TTL, so a
        real outage is never hidden from more than one poll.
        """
        self._count_probes()
        self.assertEqual(self._get().status_code, 200)

        app_module.verify_smtp_credentials = self._raise(
            smtplib.SMTPAuthenticationError(535, b"Incorrect authentication data")
        )

        # Inside the TTL the outage is deliberately not visible yet.
        self.assertEqual(self._get().status_code, 200)

        self._age_the_cache(app_module._HEALTH_DEEP_CACHE_SECONDS + 1)

        self.assertEqual(self._get().status_code, 503)

    def test_the_age_header_reports_how_stale_the_answer_is(self) -> None:
        """The cache's only outward sign.

        Without it neither `curl -I` nor the monitor can tell a fresh answer
        from one held over, and a cache nobody can observe is a cache nobody can
        debug.
        """
        self._count_probes()

        self.assertEqual(self._get().headers.get("Age"), "0")

        self._age_the_cache(5)

        self.assertEqual(self._get().headers.get("Age"), "5")

    def test_a_probe_flood_cannot_exhaust_the_submission_budget(self) -> None:
        """The probe has its own slots, ADR-0018.

        Raised by Copilot on PR #138: the cap shipped covering submissions only,
        while `/health/deep` did the same expensive I/O on a cache miss under a
        *larger* per-client allowance (30/hour against the forms' 10). Counted
        together it would have been an uncapped path to the exhaustion the cap
        exists to prevent; counted apart, a probe flood cannot close the forms.
        """
        counts = self._count_probes()
        app_module._RATE_LIMIT_MAX_REQUESTS = 50

        # Hold every probe slot, as a flood of cold-cache probes would.
        held = [
            rate_limit_store.acquire(
                app_module._HEALTH_PROBE_SLOT_SCOPE,
                limit=app_module._MAX_CONCURRENT_HEALTH_PROBES,
                ttl_seconds=60,
            )
            for _ in range(app_module._MAX_CONCURRENT_HEALTH_PROBES)
        ]
        self.assertTrue(all(held))

        try:
            # Nothing cached yet, so there is nothing truthful to serve.
            self.assertEqual(self._get().status_code, 503)
            self.assertEqual(counts, {"smtp": 0, "sheets": 0}, "no probe ran")

            # A submission's budget is untouched.
            submission = rate_limit_store.acquire(
                app_module._SUBMISSION_SLOT_SCOPE,
                limit=app_module._MAX_CONCURRENT_SUBMISSIONS,
                ttl_seconds=60,
            )
            self.assertIsNotNone(submission)
        finally:
            for token in held:
                rate_limit_store.release(token)

    def test_a_deferred_probe_serves_the_stale_answer_rather_than_refusing(self) -> None:
        """A monitor gets an honest old answer instead of a false alarm.

        A 503 here trips the synthetic alert as though a dependency had broken,
        so under a flood the page would describe the wrong problem. The `Age`
        header is what keeps the stale answer honest.
        """
        self._count_probes()
        self.assertEqual(self._get().status_code, 200)

        self._age_the_cache(app_module._HEALTH_DEEP_CACHE_SECONDS + 1)

        held = [
            rate_limit_store.acquire(
                app_module._HEALTH_PROBE_SLOT_SCOPE,
                limit=app_module._MAX_CONCURRENT_HEALTH_PROBES,
                ttl_seconds=60,
            )
            for _ in range(app_module._MAX_CONCURRENT_HEALTH_PROBES)
        ]
        try:
            response = self._get()
        finally:
            for token in held:
                rate_limit_store.release(token)

        self.assertEqual(response.status_code, 200)
        self.assertGreater(int(response.headers["Age"]), app_module._HEALTH_DEEP_CACHE_SECONDS)

    def test_is_rate_limited(self) -> None:
        # Each call opens an SMTP connection and hits the Sheets API, so an
        # unlimited endpoint is a free amplifier against both.
        app_module._RATE_LIMIT_MAX_REQUESTS = 2

        for _ in range(2):
            self.assertEqual(self._get(ip="203.0.113.91").status_code, 200)

        response = self._get(ip="203.0.113.91")

        self.assertEqual(response.status_code, 429)
        self.assertIn("Retry-After", response.headers)

    def test_rate_limit_is_separate_from_the_form_endpoints(self) -> None:
        # A monitor polling every minute must never consume the budget a
        # supporter needs to submit a form.
        app_module._RATE_LIMIT_MAX_REQUESTS = 1
        self.assertEqual(self._get(ip="203.0.113.92").status_code, 200)
        self.assertEqual(self._get(ip="203.0.113.92").status_code, 429)

        # Same client, different scope — still has its full budget.
        with app_module.app.test_request_context(
            "/send-email", headers={"X-Forwarded-For": "203.0.113.92"}
        ):
            self.assertIsNone(app_module._consume_rate_limit("send-email"))

    def test_failure_is_reported_to_the_new_relic_agent(self) -> None:
        # Swallowing the exception keeps credentials out of the response, but
        # it also hid the reason from the agent: nine production 503s recorded
        # a status code and nothing else, and diagnosing them needed SSH.
        agent = types.SimpleNamespace(
            attributes=[],
            errors=0,
            add_custom_attribute=lambda k, v: agent.attributes.append((k, v)),
            notice_error=lambda: setattr(agent, "errors", agent.errors + 1),
        )
        app_module.verify_sheets_access = self._raise(BrokenPipeError(32, "Broken pipe"))

        with mock.patch.object(app_module, "_newrelic_agent", agent):
            response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertIn(("health.dependency", "sheets"), agent.attributes)
        self.assertEqual(agent.errors, 1)

    def test_healthy_probe_reports_nothing(self) -> None:
        agent = types.SimpleNamespace(
            attributes=[],
            errors=0,
            add_custom_attribute=lambda k, v: agent.attributes.append((k, v)),
            notice_error=lambda: setattr(agent, "errors", agent.errors + 1),
        )

        with mock.patch.object(app_module, "_newrelic_agent", agent):
            self.assertEqual(self._get().status_code, 200)

        self.assertEqual(agent.attributes, [])
        self.assertEqual(agent.errors, 0)

    def test_probe_survives_a_broken_agent(self) -> None:
        # Monitoring may never be the thing that breaks the health check.
        def explode(*args, **kwargs):
            raise RuntimeError("agent is unwell")

        agent = types.SimpleNamespace(add_custom_attribute=explode, notice_error=explode)
        app_module.verify_smtp_credentials = self._raise(OSError("connection refused"))

        with mock.patch.object(app_module, "_newrelic_agent", agent):
            response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["smtp"], "fail")

    def test_probe_works_without_the_agent_installed(self) -> None:
        app_module.verify_sheets_access = self._raise(OSError("connection refused"))

        with mock.patch.object(app_module, "_newrelic_agent", None):
            response = self._get()

        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.get_json()["sheets"], "fail")

    def test_shallow_health_is_unchanged(self) -> None:
        # The deploy pipeline curls /health. It must not gain a dependency on
        # SMTP, or a mail-server blip fails deploys.
        app_module.verify_smtp_credentials = self._raise(OSError("connection refused"))
        app_module.verify_sheets_access = self._raise(OSError("connection refused"))

        response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["status"], "ok")


class EdgeTokenTests(unittest.TestCase):
    """The edge trust boundary (ADR-0020).

    Distinct from the origin check: this asks whether the request came through
    Cloudflare at all, not which page sent it.
    """

    TOKEN = "edgetoken123"

    def setUp(self) -> None:
        self.client = app_module.app.test_client()

    def _configured(self, token: str = TOKEN, enforced: bool = True, log_window: float = 0.0):
        # The warning throttle is module state that would otherwise leak: with a
        # real window, whichever test logged first silences every test after it.
        # A zero window logs every refusal; the throttle is exercised on purpose
        # in its own tests below.
        return mock.patch.multiple(
            app_module,
            _EDGE_TOKEN=token,
            _EDGE_TOKEN_ENFORCED=enforced,
            _EDGE_LOG_WINDOW_SECONDS=log_window,
            _EDGE_LOG_STATE={"next_at": 0.0, "suppressed": 0},
        )

    def test_an_unconfigured_token_is_a_no_op(self) -> None:
        # Local runs, CI and any app whose cPanel entry was never added. The
        # check must not be able to refuse anything it has no secret for.
        #
        # Both header states, because an empty secret compares EQUAL to an
        # absent header: testing only that case passes whether or not the
        # unconfigured guard exists, and an app with no token would still refuse
        # a caller who happened to send one. Found by the deletion ritual.
        with self._configured(token="", enforced=True):
            for headers in ({}, {app_module._EDGE_TOKEN_HEADER: "anything"}):
                with self.subTest(headers=headers):
                    response = self.client.get("/health", headers=headers)
                    self.assertEqual(response.status_code, 200)

    def test_the_configured_token_passes(self) -> None:
        with self._configured():
            response = self.client.get(
                "/health", headers={app_module._EDGE_TOKEN_HEADER: self.TOKEN}
            )

        self.assertEqual(response.status_code, 200)

    def test_a_missing_token_is_logged_but_served_when_unenforced(self) -> None:
        # The state between creating the Transform Rule and arming the check:
        # it must report what it would have refused without refusing it.
        with (
            self._configured(enforced=False),
            self.assertLogs(app_module.logger, level="WARNING") as logs,
        ):
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 200)
        self.assertIn(app_module._EDGE_TOKEN_HEADER, logs.output[0])

    def test_a_missing_token_is_refused_when_enforced(self) -> None:
        with self._configured():
            response = self.client.get("/health")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], app_module._UNPROXIED_MESSAGE)

    def test_a_wrong_token_is_refused(self) -> None:
        # Values from the shared corpus rather than ones invented here, per the
        # blind-spot rule in api/test_text_corpus.py. Restricted to what an HTTP
        # header can actually carry: werkzeug encodes header values as latin-1.
        hostile = [
            "",
            "   ",
            "A" * 500,
            "12345",
            "!!!",
            "https://evil.example",
            self.TOKEN + "x",
            self.TOKEN[:-1],
            self.TOKEN.upper(),
            # Non-ASCII: `hmac.compare_digest` raises TypeError on a str holding
            # any of these, which turned a refusal into a 500 with a traceback.
            # The first list here was all-ASCII despite a comment claiming the
            # constraint was considered -- the blind spot test_text_corpus.py
            # exists for. Latin-1 is the ceiling: werkzeug decodes header bytes
            # that way, so these are what can actually arrive.
            "café",
            "ÿþ",
            "évilévilévil",
        ]
        with self._configured():
            for value in hostile:
                with self.subTest(value=value[:32]):
                    response = self.client.get(
                        "/health", headers={app_module._EDGE_TOKEN_HEADER: value}
                    )
                    self.assertEqual(response.status_code, 403)

    def test_a_hostile_token_never_produces_a_500(self) -> None:
        # The refusal path must be total: any byte a header can carry has to end
        # in a 403, not an exception. A 500 here would also be an uncapped way
        # to fill the error log from off-edge, where no rate limit applies.
        with self._configured():
            for value in ("café", "\x80\xff", "ÿ" * 300, "tokén123"):
                with self.subTest(value=value[:16]):
                    response = self.client.get(
                        "/health", headers={app_module._EDGE_TOKEN_HEADER: value}
                    )
                    self.assertEqual(response.status_code, 403)

    def test_a_path_matching_no_route_is_refused(self) -> None:
        # A scanner sweeping the origin address gets the same answer everywhere,
        # rather than a 404 that confirms the host is ours.
        with self._configured():
            response = self.client.get("/wp-login.php")

        self.assertEqual(response.status_code, 403)

    def test_every_route_refuses_an_unproxied_caller(self) -> None:
        # The check ADR-0018 did not make: name every entry point sharing the
        # property, and assert each one rather than the one in front of us.
        # Enumerated from the url_map so a route added later is included here
        # without anyone remembering to add it.
        rules = [r for r in app_module.app.url_map.iter_rules() if r.endpoint != "static"]

        self.assertGreaterEqual(len(rules), 4, "url_map lookup found no routes to check")
        self.assertEqual(
            [r.rule for r in rules if r.arguments],
            [],
            "a parameterised route needs a concrete URL adding to this test",
        )

        with self._configured():
            for rule in rules:
                for method in sorted(rule.methods - {"HEAD"}):
                    with self.subTest(rule=rule.rule, method=method):
                        response = self.client.open(rule.rule, method=method)
                        self.assertEqual(response.status_code, 403)

    def test_the_refusal_never_echoes_the_token(self) -> None:
        # The 403 goes to whoever probed the origin, and the log is read over
        # SSH by a human. Neither may carry the secret.
        with (
            self._configured(),
            self.assertLogs(app_module.logger, level="WARNING") as logs,
        ):
            response = self.client.get("/health", headers={app_module._EDGE_TOKEN_HEADER: "wrong"})

        self.assertNotIn(self.TOKEN, response.get_data(as_text=True))
        self.assertNotIn(self.TOKEN, "\n".join(logs.output))

    def test_a_proxied_submission_reaches_the_pipeline(self) -> None:
        # Every other pass-path assertion in this class is `GET /health`. The
        # endpoints that carry the traffic worth protecting are the two POSTs,
        # and a `before_request` that refused those while serving `/health`
        # would satisfy the whole class -- while taking every form on the site
        # down. The refusal path is asserted for every route; the pass path has
        # to name the routes that matter too.
        sent = []
        email_config = EmailConfig(
            smtp_server="mail.example.com",
            smtp_port=465,
            smtp_security="ssl",
            email_address="info@example.com",
            email_password="placeholder-value",
            recipients=["team@example.com"],
            plain_text_confirmation_only=False,
        )
        sheets_config = SheetsConfig(
            spreadsheet_id="",
            worksheet="Sheet1",
            service_account_file="",
            service_account_json="",
        )

        payloads = {
            "/send-email": {"firstName": "Julia", "email": "julia@example.com"},
            "/yard-sign": {
                "firstName": "Sam",
                "email": "sam@example.com",
                "address": "123 Riverfront Dr, Mankato, MN 56001",
            },
        }

        for path, payload in payloads.items():
            with self.subTest(path=path):
                sent.clear()
                with (
                    self._configured(),
                    mock.patch.multiple(
                        app_module,
                        _RATE_LIMIT_BUCKETS={},
                        load_email_config=lambda *_a, **_kw: email_config,
                        load_sheets_config=lambda *_a, **_kw: sheets_config,
                        send_submission_email=lambda _config, submission: sent.append(submission),
                        send_confirmation_email=lambda *_a, **_kw: None,
                        send_yard_sign_request_email=lambda _config, submission: sent.append(
                            submission
                        ),
                        send_yard_sign_confirmation_email=lambda *_a, **_kw: None,
                        append_row=lambda *_a, **_kw: None,
                    ),
                ):
                    response = self.client.post(
                        path,
                        json=payload,
                        headers={app_module._EDGE_TOKEN_HEADER: self.TOKEN},
                    )

                self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
                self.assertEqual(len(sent), 1)

    def test_the_unproxied_warning_is_throttled_without_losing_the_count(self) -> None:
        # A caller refused here never reached the edge's rate limiting, so
        # nothing else bounds how fast it can retry: one WARNING per refusal
        # makes the log the cheapest thing on the origin to attack. One line per
        # window is the fix, and the count is what keeps it a signal -- a
        # throttle that dropped it would make a flood read like one request.
        with (
            self._configured(log_window=300.0),
            self.assertLogs(app_module.logger, level="WARNING") as logs,
        ):
            for _ in range(50):
                self.assertEqual(self.client.get("/health").status_code, 403)

            self.assertEqual(len(logs.output), 1, logs.output)

            # Expire the window rather than waiting 300 seconds for it. The 49
            # refusals above are reported on the next line written, not the one
            # that opened the window.
            app_module._EDGE_LOG_STATE["next_at"] = 0.0
            self.client.get("/health")
            app_module._EDGE_LOG_STATE["next_at"] = 0.0
            self.client.get("/health")

        self.assertEqual(len(logs.output), 3, logs.output)
        self.assertIn("0 more suppressed", logs.output[0])
        self.assertIn("49 more suppressed", logs.output[1])
        self.assertIn("0 more suppressed", logs.output[2])

    def test_a_hostile_path_is_truncated_in_the_log(self) -> None:
        with (
            self._configured(enforced=False),
            self.assertLogs(app_module.logger, level="WARNING") as logs,
        ):
            self.client.get("/" + "A" * 5000)

        self.assertLess(len(logs.output[0]), 1000)


if __name__ == "__main__":
    unittest.main()

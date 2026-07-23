import unittest
from collections import deque
from time import monotonic

import api.app as app_module
from api.config import EmailConfig, SheetsConfig
from api.models import MAX_MESSAGE_LENGTH


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
            "/api/send-email",
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
        self.assertEqual(response.headers.get("Access-Control-Allow-Headers"), "Content-Type")

    def test_preflight_omits_cors_headers_for_disallowed_origin(self) -> None:
        response = self.client.options(
            "/api/send-email",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
            },
        )

        self.assertEqual(response.status_code, 204)
        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))


class AppRateLimitTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_rate_limit_window_seconds = app_module._RATE_LIMIT_WINDOW_SECONDS
        self._orig_rate_limit_max_requests = app_module._RATE_LIMIT_MAX_REQUESTS
        self._orig_rate_limit_buckets = app_module._RATE_LIMIT_BUCKETS
        self._orig_load_email_config = app_module.load_email_config
        self._orig_load_sheets_config = app_module.load_sheets_config
        self._orig_send_submission_email = app_module.send_submission_email
        self._orig_send_confirmation_email = app_module.send_confirmation_email
        self._orig_append_row = app_module.append_row

        app_module._RATE_LIMIT_WINDOW_SECONDS = 60
        app_module._RATE_LIMIT_MAX_REQUESTS = 1
        app_module._RATE_LIMIT_BUCKETS = {}

        self.sent_submissions = []
        self.confirmation_submissions = []
        self.sheet_rows = []

        app_module.load_email_config = lambda: EmailConfig(
            smtp_server="mail.example.com",
            smtp_port=465,
            smtp_security="ssl",
            email_address="info@example.com",
            email_password="placeholder-value",
            recipients=["team@example.com"],
            plain_text_confirmation_only=False,
        )
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

        first_response = self.client.post("/api/send-email", json=payload)
        second_response = self.client.post("/api/send-email", json=payload)

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)
        self.assertEqual(second_response.headers.get("Retry-After"), "59")
        self.assertEqual(
            second_response.get_json(),
            {"error": "Too many requests. Please try again later."},
        )
        self.assertEqual(len(self.sent_submissions), 1)
        self.assertEqual(len(self.confirmation_submissions), 1)
        self.assertEqual(len(self.sheet_rows), 1)

    def test_rate_limit_ignores_spoofed_first_x_forwarded_for_hop(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
        }

        first_response = self.client.post(
            "/api/send-email",
            json=payload,
            headers={"X-Forwarded-For": "spoofed-one, 203.0.113.5"},
        )
        second_response = self.client.post(
            "/api/send-email",
            json=payload,
            headers={"X-Forwarded-For": "spoofed-two, 203.0.113.5"},
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)

    def test_rate_limit_prefers_cf_connecting_ip_over_x_forwarded_for(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
        }

        first_response = self.client.post(
            "/api/send-email",
            json=payload,
            headers={
                "CF-Connecting-IP": "203.0.113.7",
                "X-Forwarded-For": "198.51.100.30",
            },
        )
        second_response = self.client.post(
            "/api/send-email",
            json=payload,
            headers={
                "CF-Connecting-IP": "203.0.113.7",
                "X-Forwarded-For": "198.51.100.31",
            },
        )

        self.assertEqual(first_response.status_code, 200)
        self.assertEqual(second_response.status_code, 429)

    def test_rate_limit_evicts_stale_buckets(self) -> None:
        stale_key = "send-email:198.51.100.99"
        app_module._RATE_LIMIT_BUCKETS[stale_key] = deque(
            [monotonic() - app_module._RATE_LIMIT_WINDOW_SECONDS - 1]
        )

        response = self.client.post(
            "/api/send-email",
            json={"firstName": "Julia", "email": "julia@example.com"},
            headers={"X-Forwarded-For": "198.51.100.40"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(stale_key, app_module._RATE_LIMIT_BUCKETS)

    def test_send_email_returns_json_error_when_email_config_is_invalid(self) -> None:
        def raise_config_error():
            raise ValueError("SMTP_SECURITY must be one of: auto, ssl, starttls")

        app_module.load_email_config = raise_config_error

        response = self.client.post(
            "/api/send-email",
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
            "/api/send-email",
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
            "/api/send-email",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.11"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"error": f"Message must be {MAX_MESSAGE_LENGTH} characters or fewer."},
        )
        self.assertEqual(len(self.sent_submissions), 0)

    def test_send_email_logs_request_body_even_when_submission_fails(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "not-an-email",
        }

        with self.assertLogs(app_module.logger, level="INFO") as captured:
            response = self.client.post(
                "/api/send-email",
                json=payload,
                headers={"X-Forwarded-For": "198.51.100.12"},
            )

        self.assertEqual(response.status_code, 400)
        body_logs = [line for line in captured.output if "request body" in line]
        self.assertEqual(len(body_logs), 1)
        self.assertIn("/send-email", body_logs[0])
        self.assertIn("not-an-email", body_logs[0])

    def test_send_email_truncates_oversized_request_body_in_logs(self) -> None:
        oversized = "x" * (app_module._MAX_LOGGED_BODY_CHARS + 100)

        with self.assertLogs(app_module.logger, level="INFO") as captured:
            self.client.post(
                "/api/send-email",
                json={"firstName": "Julia", "message": oversized},
                headers={"X-Forwarded-For": "198.51.100.13"},
            )

        body_logs = [line for line in captured.output if "request body" in line]
        self.assertEqual(len(body_logs), 1)
        self.assertIn("…[truncated]", body_logs[0])
        self.assertNotIn(oversized, body_logs[0])


class AppYardSignTests(unittest.TestCase):
    def setUp(self) -> None:
        self._orig_rate_limit_window_seconds = app_module._RATE_LIMIT_WINDOW_SECONDS
        self._orig_rate_limit_max_requests = app_module._RATE_LIMIT_MAX_REQUESTS
        self._orig_rate_limit_buckets = app_module._RATE_LIMIT_BUCKETS
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

        app_module.load_email_config = lambda: EmailConfig(
            smtp_server="mail.example.com",
            smtp_port=465,
            smtp_security="ssl",
            email_address="info@example.com",
            email_password="placeholder-value",
            recipients=["team@example.com"],
            plain_text_confirmation_only=False,
        )

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
            "/api/yard-sign",
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

    def test_yard_sign_requires_address(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
        }

        response = self.client.post(
            "/api/yard-sign",
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
            "/api/yard-sign",
            json=payload,
            headers={"X-Forwarded-For": "198.51.100.22"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.get_json(),
            {"error": "First name contains invalid characters."},
        )
        self.assertEqual(len(self.sent_requests), 0)


if __name__ == "__main__":
    unittest.main()

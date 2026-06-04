import unittest

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


if __name__ == "__main__":
    unittest.main()

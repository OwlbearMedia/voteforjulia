import unittest

import api.app as app_module


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


if __name__ == "__main__":
    unittest.main()

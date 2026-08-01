import os
import subprocess
import sys
import unittest
from unittest import mock

import api.app as app_module
from api.config import (
    DEFAULT_RECIPIENT_EMAIL,
    DEFAULT_SHEETS_TIMEOUT_SECONDS,
    DEFAULT_SMTP_TIMEOUT_SECONDS,
    env_positive_number,
    load_email_config,
    load_sheets_config,
)


class LoadEmailConfigRecipientTests(unittest.TestCase):
    def test_defaults_to_recipient_email(self) -> None:
        with mock.patch.dict(os.environ, {"RECIPIENT_EMAIL": "team@example.com"}, clear=False):
            config = load_email_config()

        self.assertEqual(config.recipients, ["team@example.com"])

    def test_uses_form_specific_recipient_env_when_set(self) -> None:
        env = {
            "RECIPIENT_EMAIL": "team@example.com",
            "RECIPIENT_EMAIL_SIGNS": "signs@example.com",
        }
        with mock.patch.dict(os.environ, env, clear=False):
            config = load_email_config("RECIPIENT_EMAIL_SIGNS")

        self.assertEqual(config.recipients, ["signs@example.com"])

    def test_falls_back_to_recipient_email_when_form_specific_env_unset(self) -> None:
        env = {"RECIPIENT_EMAIL": "team@example.com", "RECIPIENT_EMAIL_SIGNS": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            config = load_email_config("RECIPIENT_EMAIL_SIGNS")

        self.assertEqual(config.recipients, ["team@example.com"])

    def test_falls_back_to_default_when_no_recipient_env_set(self) -> None:
        env = {"RECIPIENT_EMAIL": "", "RECIPIENT_EMAIL_SIGNS": ""}
        with mock.patch.dict(os.environ, env, clear=False):
            config = load_email_config("RECIPIENT_EMAIL_SIGNS")

        self.assertEqual(config.recipients, [DEFAULT_RECIPIENT_EMAIL])


class EnvPositiveNumberTests(unittest.TestCase):
    def test_returns_the_default_when_unset(self) -> None:
        with mock.patch.dict(os.environ, {"SOME_TIMEOUT": ""}, clear=False):
            self.assertEqual(env_positive_number("SOME_TIMEOUT", 10.0), 10.0)

    def test_reads_an_override(self) -> None:
        with mock.patch.dict(os.environ, {"SOME_TIMEOUT": "2.5"}, clear=False):
            self.assertEqual(env_positive_number("SOME_TIMEOUT", 10.0), 2.5)

    def test_rejects_an_unparseable_value(self) -> None:
        # Deliberately not a silent fallback to the default: a timeout typo'd
        # to "1O" would then quietly restore the unbounded wait the setting
        # exists to prevent, and nothing would say so. load_email_config raises
        # ValueError, which app.py already renders as a JSON 500.
        with (
            mock.patch.dict(os.environ, {"SOME_TIMEOUT": "1O"}, clear=False),
            self.assertRaises(ValueError) as raised,
        ):
            env_positive_number("SOME_TIMEOUT", 10.0)

        self.assertIn("SOME_TIMEOUT", str(raised.exception))

    def test_rejects_a_non_positive_value(self) -> None:
        # Zero and negatives are the dangerous ones: socket APIs read 0 as
        # "non-blocking" and None as "wait forever", so neither is a timeout.
        for value in ("0", "-1"):
            with (
                self.subTest(value=value),
                mock.patch.dict(os.environ, {"SOME_TIMEOUT": value}, clear=False),
                self.assertRaises(ValueError),
            ):
                env_positive_number("SOME_TIMEOUT", 10.0)


class IntSettingTests(unittest.TestCase):
    """Import-time settings degrade to defaults instead of failing module import."""

    def test_reads_a_valid_override(self) -> None:
        with mock.patch.dict(os.environ, {"SOME_LIMIT": "25"}, clear=False):
            self.assertEqual(app_module._int_setting("SOME_LIMIT", 5), 25)

    def test_falls_back_and_logs_on_an_unparseable_value(self) -> None:
        # These are read at import, and this module is the API's entry point --
        # raising would fail module import and take every form on the site down
        # over a cPanel typo. Falling back keeps the limiter working at its
        # defaults; the log line is what makes the misconfiguration findable.
        with (
            mock.patch.dict(os.environ, {"SOME_LIMIT": "abc"}, clear=False),
            self.assertLogs("api.app", level="ERROR") as logs,
        ):
            value = app_module._int_setting("SOME_LIMIT", 5)

        self.assertEqual(value, 5)
        self.assertIn("SOME_LIMIT", logs.output[0])

    def test_falls_back_on_a_non_positive_value(self) -> None:
        # A limit of 0 previously clamped silently to 1, which is neither what
        # was asked for nor obviously wrong from the outside.
        for raw in ("0", "-5"):
            with (
                self.subTest(raw=raw),
                mock.patch.dict(os.environ, {"SOME_LIMIT": raw}, clear=False),
                self.assertLogs("api.app", level="ERROR"),
            ):
                self.assertEqual(app_module._int_setting("SOME_LIMIT", 5), 5)

    def test_importing_the_app_survives_a_bad_value(self) -> None:
        # The property that actually matters, checked end to end in a fresh
        # interpreter: a typo'd limit must not be able to take the API down.
        env = dict(
            os.environ,
            EMAIL_ADDRESS="a@b.com",
            EMAIL_PASSWORD="x",
            RATE_LIMIT_MAX_REQUESTS="abc",
            RATE_LIMIT_WINDOW_SECONDS="-1",
            MAX_REQUEST_BYTES="not-a-number",
        )
        result = subprocess.run(
            [sys.executable, "-c", "import api.app as m; print(m._RATE_LIMIT_MAX_REQUESTS)"],
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "5")


class TimeoutConfigTests(unittest.TestCase):
    """Both network clients must come out of config with a bounded wait."""

    def test_smtp_timeout_defaults_and_overrides(self) -> None:
        with mock.patch.dict(os.environ, {"SMTP_TIMEOUT_SECONDS": ""}, clear=False):
            self.assertEqual(load_email_config().timeout_seconds, DEFAULT_SMTP_TIMEOUT_SECONDS)

        with mock.patch.dict(os.environ, {"SMTP_TIMEOUT_SECONDS": "3"}, clear=False):
            self.assertEqual(load_email_config().timeout_seconds, 3.0)

    def test_sheets_timeout_defaults_and_overrides(self) -> None:
        with mock.patch.dict(os.environ, {"SHEETS_TIMEOUT_SECONDS": ""}, clear=False):
            self.assertEqual(load_sheets_config().timeout_seconds, DEFAULT_SHEETS_TIMEOUT_SECONDS)

        with mock.patch.dict(os.environ, {"SHEETS_TIMEOUT_SECONDS": "4"}, clear=False):
            self.assertEqual(load_sheets_config().timeout_seconds, 4.0)

    def test_the_two_timeouts_are_independent(self) -> None:
        # The negative half: one env var feeding both configs would pass every
        # assertion above, and the Sheets budget is deliberately the larger of
        # the two because it runs after the emails are already away.
        env = {"SMTP_TIMEOUT_SECONDS": "3", "SHEETS_TIMEOUT_SECONDS": "9"}
        with mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(load_email_config().timeout_seconds, 3.0)
            self.assertEqual(load_sheets_config().timeout_seconds, 9.0)


if __name__ == "__main__":
    unittest.main()

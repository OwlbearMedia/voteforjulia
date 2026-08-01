import os
import unittest
from unittest import mock

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

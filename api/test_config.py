import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
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

    def test_falls_back_on_a_fractional_value(self) -> None:
        # These settings are counts and byte limits, so a fraction is a typo,
        # not a request. Parsing through a float previously truncated it
        # silently -- "2.5" became 2 -- which is the one misconfiguration that
        # changed behaviour without saying so.
        with (
            mock.patch.dict(os.environ, {"SOME_LIMIT": "2.5"}, clear=False),
            self.assertLogs("api.app", level="ERROR") as logs,
        ):
            value = app_module._int_setting("SOME_LIMIT", 5)

        self.assertEqual(value, 5)
        self.assertIn("'2.5'", logs.output[0])

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


class EdgeTokenSettingTests(unittest.TestCase):
    """The API validates the edge token the way the deploy does. See ADR-0020."""

    VALID = "a" * 32

    def test_reads_a_valid_token(self) -> None:
        # The positive case, without which every assertion below passes on a
        # function that returns "" unconditionally.
        with mock.patch.dict(os.environ, {"EDGE_SHARED_TOKEN": self.VALID}, clear=False):
            self.assertEqual(app_module._edge_token_setting(), self.VALID)

    def test_an_unset_token_is_empty_and_silent(self) -> None:
        # Local runs and CI. Not a misconfiguration, so it must not log one.
        with (
            mock.patch.dict(os.environ, {"EDGE_SHARED_TOKEN": ""}, clear=False),
            self.assertNoLogs("api.app", level="ERROR"),
        ):
            self.assertEqual(app_module._edge_token_setting(), "")

    def test_a_token_under_the_length_floor_is_refused(self) -> None:
        # The realistic failure ADR-0020 names: a memorable value, not a short
        # one chosen on purpose. Refused here rather than trusted, because the
        # deploy's check never sees the copy typed into cPanel.
        for raw in ("short", "a" * 31):
            with (
                self.subTest(raw=raw),
                mock.patch.dict(os.environ, {"EDGE_SHARED_TOKEN": raw}, clear=False),
                self.assertLogs("api.app", level="ERROR") as logs,
            ):
                self.assertEqual(app_module._edge_token_setting(), "")

            # Never the value: this is a secret on its way to a log file.
            self.assertNotIn(raw, logs.output[0])
            self.assertIn("at least 32 characters", logs.output[0])

    def test_a_non_ascii_alphanumeric_token_is_refused(self) -> None:
        # `isalnum` alone accepts the last two: non-ASCII digits and letters
        # that the deploy's [A-Za-z0-9] rejects. All four are long enough, so
        # the message is asserted -- otherwise the length guard could be the
        # one firing and this would still pass.
        interior_space = "a" * 16 + " " + "a" * 16
        for raw in ("a" * 31 + "-", interior_space, "a" * 31 + "\u00e9", "a" * 31 + "\u0663"):
            with (
                self.subTest(raw=raw),
                mock.patch.dict(os.environ, {"EDGE_SHARED_TOKEN": raw}, clear=False),
                self.assertLogs("api.app", level="ERROR") as logs,
            ):
                self.assertEqual(app_module._edge_token_setting(), "")

            self.assertNotIn(raw, logs.output[0])
            self.assertIn("ASCII alphanumeric", logs.output[0])

    def test_the_length_floor_agrees_with_the_deploy(self) -> None:
        # Two implementations of one rule, in two languages, reading the same
        # secret from different places. Nothing else would notice them parting.
        script = Path(__file__).resolve().parent.parent / "scripts" / "arm-edge-gate.sh"
        match = re.search(r"^readonly MIN_TOKEN_LENGTH=(\d+)$", script.read_text(), re.MULTILINE)

        self.assertIsNotNone(match, "MIN_TOKEN_LENGTH not found in arm-edge-gate.sh")
        self.assertEqual(int(match.group(1)), app_module._EDGE_TOKEN_MIN_LENGTH)

    def test_a_weak_token_cannot_arm_the_gate(self) -> None:
        # The property that matters, end to end in a fresh interpreter: the
        # module-level token a bad value produces is the unset one, so the
        # `before_request` hook refuses nothing rather than guarding the origin
        # with a guessable secret.
        env = dict(
            os.environ,
            EMAIL_ADDRESS="a@b.com",
            EMAIL_PASSWORD="x",
            EDGE_SHARED_TOKEN="letmein",
            EDGE_TOKEN_ENFORCED="true",
        )
        result = subprocess.run(
            [sys.executable, "-c", "import api.app as m; print(repr(m._EDGE_TOKEN))"],
            env=env,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "''")


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

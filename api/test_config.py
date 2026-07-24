import os
import unittest
from unittest import mock

from api.config import DEFAULT_RECIPIENT_EMAIL, load_email_config


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


if __name__ == "__main__":
    unittest.main()

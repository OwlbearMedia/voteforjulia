import unittest
from email import message_from_string
from email.message import Message
from unittest.mock import patch

from api.config import EmailConfig
from api.models import Submission, YardSignRequest
from api.services.email_service import (
    send_confirmation_email,
    send_submission_email,
    send_yard_sign_confirmation_email,
    send_yard_sign_request_email,
)


def _decode_payload(part: Message) -> str:
    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")


class FakeSmtpServer:
    instances: list["FakeSmtpServer"] = []

    def __init__(self, smtp_server: str, smtp_port: int) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.login_args: tuple[str, str] | None = None
        self.sent_messages: list[tuple[str, list[str], str]] = []
        self.ehlo_calls = 0
        self.starttls_calls = 0
        self.quit_calls = 0
        FakeSmtpServer.instances.append(self)

    def __enter__(self) -> "FakeSmtpServer":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def sendmail(self, from_address: str, recipients: list[str], message: str) -> dict:
        self.sent_messages.append((from_address, recipients, message))
        return {}

    def ehlo(self) -> None:
        self.ehlo_calls += 1

    def starttls(self) -> None:
        self.starttls_calls += 1

    def quit(self) -> None:
        self.quit_calls += 1


class EmailServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSmtpServer.instances.clear()
        password_parts = ["placeholder", "value"]
        password_placeholder = "-".join(password_parts)
        self.config = EmailConfig(
            smtp_server="mail.example.com",
            smtp_port=465,
            smtp_security="ssl",
            email_address="info@example.com",
            email_password=password_placeholder,
            recipients=["team@example.com"],
            plain_text_confirmation_only=False,
        )
        self.submission = Submission(
            first_name="Julia",
            last_name="Hamann",
            name="Julia Hamann",
            email="supporter@example.com",
            phone="555-555-5555",
            message="I would like to volunteer.",
            help_ways=["Door Knocking", "Other details: Host a house party"],
        )

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_submission_email_sends_to_campaign_recipients(self) -> None:
        refused = send_submission_email(self.config, self.submission)

        self.assertEqual(refused, {})
        self.assertEqual(len(FakeSmtpServer.instances), 1)
        server = FakeSmtpServer.instances[0]
        self.assertEqual(server.login_args, ("info@example.com", "placeholder-value"))
        self.assertEqual(len(server.sent_messages), 1)

        from_address, recipients, raw_message = server.sent_messages[0]
        parsed = message_from_string(raw_message)

        self.assertEqual(from_address, "info@example.com")
        self.assertEqual(recipients, ["team@example.com"])
        self.assertEqual(parsed["To"], "team@example.com")
        self.assertEqual(parsed["Reply-To"], "supporter@example.com")
        self.assertEqual(parsed["Subject"], "New message from Julia Hamann")
        self.assertRegex(parsed["Message-ID"], r"^<[0-9a-f]{32}@example\.com>$")

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_submission_email_uses_distinct_high_entropy_message_ids(self) -> None:
        send_submission_email(self.config, self.submission)
        send_submission_email(self.config, self.submission)

        first_message_id = message_from_string(FakeSmtpServer.instances[0].sent_messages[0][2])[
            "Message-ID"
        ]
        second_message_id = message_from_string(FakeSmtpServer.instances[1].sent_messages[0][2])[
            "Message-ID"
        ]

        self.assertNotEqual(first_message_id, second_message_id)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_submission_email_encodes_non_ascii_body_as_utf8(self) -> None:
        submission = Submission(
            first_name="José",
            last_name="Muñoz",
            name="José Muñoz",
            email="jose@example.com",
            phone="",
            message="héllo — thanks! 😀",
            help_ways=[],
        )

        refused = send_submission_email(self.config, submission)

        self.assertEqual(refused, {})
        _, _, raw_message = FakeSmtpServer.instances[0].sent_messages[0]
        # Mirrors what smtplib.sendmail does internally for a str message: it
        # must be fully ASCII-transport-safe even though the content is UTF-8.
        raw_message.encode("ascii")

        parsed = message_from_string(raw_message)
        body_part = parsed.get_payload()[0]
        self.assertEqual(body_part.get_content_charset(), "utf-8")
        self.assertIn("héllo — thanks! 😀", _decode_payload(body_part))

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_confirmation_email_sends_to_submitter(self) -> None:
        refused = send_confirmation_email(self.config, self.submission)

        self.assertEqual(refused, {})
        self.assertEqual(len(FakeSmtpServer.instances), 1)
        server = FakeSmtpServer.instances[0]
        self.assertEqual(server.login_args, ("info@example.com", "placeholder-value"))
        self.assertEqual(len(server.sent_messages), 1)

        from_address, recipients, raw_message = server.sent_messages[0]
        parsed = message_from_string(raw_message)
        plain_text_payload = _decode_payload(parsed.get_payload()[0])
        html_payload = _decode_payload(parsed.get_payload()[1])

        self.assertEqual(from_address, "info@example.com")
        self.assertEqual(recipients, ["supporter@example.com"])
        self.assertEqual(parsed["To"], "supporter@example.com")
        self.assertEqual(parsed["Subject"], "Thanks for reaching out to Julia Hamann for Mayor")
        self.assertEqual(parsed.get_content_subtype(), "alternative")
        self.assertIn("Hi Julia!", plain_text_payload)
        self.assertIn("Thank you so much for reaching out to help promote my campaign", plain_text_payload)
        self.assertIn("All my best,", plain_text_payload)
        self.assertIn("Julia", plain_text_payload)
        self.assertIn("Hi Julia!", html_payload)
        self.assertIn("Thank you so much for reaching out to help promote my campaign", html_payload)
        self.assertIn("Paid for by Julia Hamann for Mankato Mayor", html_payload)
        self.assertIn("https://voteforjulia.com/julia-hamann-for-mankato-mayor.png", html_payload)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_confirmation_email_uses_there_when_name_missing(self) -> None:
        nameless_submission = Submission(
            first_name="",
            last_name="",
            name="",
            email="supporter@example.com",
            phone="",
            message="",
            help_ways=[],
        )

        refused = send_confirmation_email(self.config, nameless_submission)

        self.assertEqual(refused, {})
        self.assertEqual(len(FakeSmtpServer.instances), 1)
        server = FakeSmtpServer.instances[0]
        self.assertEqual(server.login_args, ("info@example.com", "placeholder-value"))
        self.assertEqual(len(server.sent_messages), 1)

        _, _, raw_message = server.sent_messages[0]
        parsed = message_from_string(raw_message)
        plain_text_payload = _decode_payload(parsed.get_payload()[0])
        html_payload = _decode_payload(parsed.get_payload()[1])

        self.assertIn("Hi there!", plain_text_payload)
        self.assertIn("Hi there!", html_payload)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_confirmation_email_can_send_plain_text_only(self) -> None:
        config = EmailConfig(
            smtp_server="mail.example.com",
            smtp_port=465,
            smtp_security="ssl",
            email_address="info@example.com",
            email_password="placeholder-value",
            recipients=["team@example.com"],
            plain_text_confirmation_only=True,
        )

        refused = send_confirmation_email(config, self.submission)

        self.assertEqual(refused, {})
        self.assertEqual(len(FakeSmtpServer.instances), 1)
        server = FakeSmtpServer.instances[0]
        self.assertEqual(len(server.sent_messages), 1)

        _, recipients, raw_message = server.sent_messages[0]
        parsed = message_from_string(raw_message)

        self.assertEqual(recipients, ["supporter@example.com"])
        self.assertEqual(parsed.get_content_type(), "text/plain")
        plain_text_payload = _decode_payload(parsed)
        self.assertIn("Hi Julia!", plain_text_payload)
        self.assertIn("Paid for by Julia Hamann for Mankato Mayor", plain_text_payload)

    @patch("api.services.email_service.smtplib.SMTP", new=FakeSmtpServer)
    def test_send_submission_email_uses_starttls_when_configured(self) -> None:
        config = EmailConfig(
            smtp_server="mail.example.com",
            smtp_port=587,
            smtp_security="starttls",
            email_address="info@example.com",
            email_password="placeholder-value",
            recipients=["team@example.com"],
            plain_text_confirmation_only=False,
        )

        refused = send_submission_email(config, self.submission)

        self.assertEqual(refused, {})
        self.assertEqual(len(FakeSmtpServer.instances), 1)
        server = FakeSmtpServer.instances[0]
        self.assertEqual(server.ehlo_calls, 2)
        self.assertEqual(server.starttls_calls, 1)
        self.assertEqual(server.login_args, ("info@example.com", "placeholder-value"))
        self.assertEqual(server.quit_calls, 1)


class YardSignEmailServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeSmtpServer.instances.clear()
        self.config = EmailConfig(
            smtp_server="mail.example.com",
            smtp_port=465,
            smtp_security="ssl",
            email_address="info@example.com",
            email_password="placeholder-value",
            recipients=["team@example.com"],
            plain_text_confirmation_only=False,
        )
        self.yard_sign_request = YardSignRequest(
            first_name="Julia",
            last_name="Hamann",
            name="Julia Hamann",
            email="supporter@example.com",
            phone="555-555-5555",
            address="123 Main St, Mankato, MN 56001",
            preferred_payment=["Online", "Cash"],
        )

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_yard_sign_request_email_sends_to_campaign_recipients(self) -> None:
        refused = send_yard_sign_request_email(self.config, self.yard_sign_request)

        self.assertEqual(refused, {})
        self.assertEqual(len(FakeSmtpServer.instances), 1)
        server = FakeSmtpServer.instances[0]
        self.assertEqual(len(server.sent_messages), 1)

        from_address, recipients, raw_message = server.sent_messages[0]
        parsed = message_from_string(raw_message)

        self.assertEqual(from_address, "info@example.com")
        self.assertEqual(recipients, ["team@example.com"])
        self.assertEqual(parsed["Reply-To"], "supporter@example.com")
        self.assertEqual(parsed["Subject"], "New yard sign request from Julia Hamann")
        request_body = _decode_payload(parsed.get_payload()[0])
        self.assertIn("Address: 123 Main St, Mankato, MN 56001", request_body)
        self.assertIn("Preferred payment: Online, Cash", request_body)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_yard_sign_confirmation_email_sends_to_submitter(self) -> None:
        refused = send_yard_sign_confirmation_email(self.config, self.yard_sign_request)

        self.assertEqual(refused, {})
        self.assertEqual(len(FakeSmtpServer.instances), 1)
        server = FakeSmtpServer.instances[0]
        self.assertEqual(len(server.sent_messages), 1)

        _, recipients, raw_message = server.sent_messages[0]
        parsed = message_from_string(raw_message)
        plain_text_payload = _decode_payload(parsed.get_payload()[0])
        html_payload = _decode_payload(parsed.get_payload()[1])

        self.assertEqual(recipients, ["supporter@example.com"])
        self.assertEqual(
            parsed["Subject"], "Thanks for requesting a yard sign for Julia Hamann for Mayor"
        )
        self.assertIn("Thanks so much for your support, Julia!", plain_text_payload)
        self.assertIn("requesting a yard sign", plain_text_payload)
        self.assertIn("Check your inbox to coordinate sign delivery", plain_text_payload)
        self.assertIn("make a donation", plain_text_payload)
        self.assertIn("Thanks so much for your support, Julia!", html_payload)
        self.assertIn("requesting a yard sign", html_payload)
        self.assertIn("Check your inbox to coordinate sign delivery", html_payload)
        self.assertIn("make a donation", html_payload)
        self.assertIn("Paid for by Julia Hamann for Mankato Mayor", html_payload)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_yard_sign_confirmation_email_uses_friend_when_name_missing(self) -> None:
        nameless_request = YardSignRequest(
            first_name="",
            last_name="",
            name="",
            email="supporter@example.com",
            phone="",
            address="123 Main St, Mankato, MN 56001",
            preferred_payment=[],
        )

        refused = send_yard_sign_confirmation_email(self.config, nameless_request)

        self.assertEqual(refused, {})
        _, _, raw_message = FakeSmtpServer.instances[0].sent_messages[0]
        parsed = message_from_string(raw_message)
        plain_text_payload = _decode_payload(parsed.get_payload()[0])

        self.assertIn("Thanks so much for your support, friend!", plain_text_payload)


if __name__ == "__main__":
    unittest.main()

import smtplib
import unicodedata
import unittest
from email import message_from_string
from email.message import Message
from unittest.mock import patch

from api.config import EmailConfig
from api.models import Submission, YardSignRequest
from api.services.email_service import (
    _safe_greeting,
    send_confirmation_email,
    send_submission_email,
    send_yard_sign_confirmation_email,
    send_yard_sign_request_email,
    verify_smtp_credentials,
)


def _decode_payload(part: Message) -> str:
    return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")


class FakeSmtpServer:
    instances: list["FakeSmtpServer"] = []

    def __init__(self, smtp_server: str, smtp_port: int, timeout: float | None = None) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.timeout = timeout
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


class RejectingLoginSmtpServer(FakeSmtpServer):
    """Reproduces the `$`-in-password incident: reachable server, refused LOGIN."""

    def login(self, username: str, password: str) -> None:
        raise smtplib.SMTPAuthenticationError(535, b"Incorrect authentication data")


def _config(**overrides) -> EmailConfig:
    defaults = {
        "smtp_server": "mail.example.com",
        "smtp_port": 465,
        "smtp_security": "ssl",
        "email_address": "info@example.com",
        "email_password": "placeholder-value",
        "recipients": ["team@example.com"],
        "plain_text_confirmation_only": False,
        # Deliberately not DEFAULT_SMTP_TIMEOUT_SECONDS: the timeout tests below
        # assert this exact value reaches the constructor, so hardcoding the
        # default in email_service.py instead of reading it from the config
        # would fail rather than pass by coincidence.
        "timeout_seconds": 12.5,
    }
    return EmailConfig(**{**defaults, **overrides})


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
        self.assertIn(
            "Thank you so much for reaching out to help promote my campaign", plain_text_payload
        )
        self.assertIn("All my best,", plain_text_payload)
        self.assertIn("Julia", plain_text_payload)
        self.assertIn("Hi Julia!", html_payload)
        self.assertIn(
            "Thank you so much for reaching out to help promote my campaign", html_payload
        )
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

    # The next two are a pair, and only mean something together. Both patch
    # SMTP and SMTP_SSL with the same fake, so neither can pass by accident of
    # which class was patched -- the assertion is on whether STARTTLS was
    # negotiated. "auto" is the shipped default (config.DEFAULT_SMTP_SECURITY),
    # so this is the branch production actually takes.
    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    @patch("api.services.email_service.smtplib.SMTP", new=FakeSmtpServer)
    def test_auto_security_negotiates_starttls_on_port_587(self) -> None:
        refused = send_submission_email(
            _config(smtp_port=587, smtp_security="auto"), self.submission
        )

        self.assertEqual(refused, {})
        server = FakeSmtpServer.instances[0]
        self.assertEqual(server.starttls_calls, 1)
        self.assertEqual(server.ehlo_calls, 2)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    @patch("api.services.email_service.smtplib.SMTP", new=FakeSmtpServer)
    def test_auto_security_stays_implicit_ssl_on_port_465(self) -> None:
        refused = send_submission_email(
            _config(smtp_port=465, smtp_security="auto"), self.submission
        )

        self.assertEqual(refused, {})
        server = FakeSmtpServer.instances[0]
        self.assertEqual(server.starttls_calls, 0)
        self.assertEqual(server.ehlo_calls, 0)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_explicit_ssl_ignores_the_starttls_port(self) -> None:
        # Port 587 with smtp_security="ssl" must still take the implicit-TLS
        # path: the explicit setting wins over the port heuristic.
        refused = send_submission_email(
            _config(smtp_port=587, smtp_security="ssl"), self.submission
        )

        self.assertEqual(refused, {})
        self.assertEqual(FakeSmtpServer.instances[0].starttls_calls, 0)

    # The next two are a pair for the same reason as the auto-security ones:
    # the timeout has to reach *both* constructors, and a test that only
    # exercised the SSL branch would stay green with the STARTTLS one left
    # unbounded. Without it smtplib inherits socket.getdefaulttimeout() -- None
    # -- and a mail server that accepts the connection then stalls holds the
    # worker open indefinitely.
    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_ssl_connection_is_given_a_timeout(self) -> None:
        send_submission_email(_config(smtp_port=465, smtp_security="ssl"), self.submission)

        self.assertEqual(FakeSmtpServer.instances[0].timeout, 12.5)

    @patch("api.services.email_service.smtplib.SMTP", new=FakeSmtpServer)
    def test_starttls_connection_is_given_a_timeout(self) -> None:
        send_submission_email(_config(smtp_port=587, smtp_security="starttls"), self.submission)

        self.assertEqual(FakeSmtpServer.instances[0].timeout, 12.5)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_each_message_gets_its_own_connection(self) -> None:
        # The mail server drops every message after the first on a shared
        # connection, so the notification and the confirmation must never be
        # consolidated onto one. Asserting the connection count is what would
        # catch that refactor.
        send_submission_email(self.config, self.submission)
        send_confirmation_email(self.config, self.submission)

        self.assertEqual(len(FakeSmtpServer.instances), 2)
        self.assertEqual([len(server.sent_messages) for server in FakeSmtpServer.instances], [1, 1])


class VerifySmtpCredentialsTests(unittest.TestCase):
    """The deep health check's SMTP probe (api/app.py's /health/deep)."""

    def setUp(self) -> None:
        FakeSmtpServer.instances.clear()

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_authenticates_without_sending_anything(self) -> None:
        # Sending a message here would burn the connection's one-message
        # allowance and put mail in the campaign's inbox on every health poll.
        verify_smtp_credentials(_config())

        self.assertEqual(len(FakeSmtpServer.instances), 1)
        server = FakeSmtpServer.instances[0]
        self.assertEqual(server.login_args, ("info@example.com", "placeholder-value"))
        self.assertEqual(server.sent_messages, [])

    @patch("api.services.email_service.smtplib.SMTP", new=FakeSmtpServer)
    def test_closes_the_starttls_connection(self) -> None:
        verify_smtp_credentials(_config(smtp_port=587, smtp_security="starttls"))

        server = FakeSmtpServer.instances[0]
        self.assertEqual(server.starttls_calls, 1)
        self.assertEqual(server.sent_messages, [])
        self.assertEqual(server.quit_calls, 1)

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=RejectingLoginSmtpServer)
    def test_propagates_authentication_failure(self) -> None:
        # The probe is only useful if a refused LOGIN raises: /health/deep
        # reports "fail" by catching this. Swallowing it would make the check
        # green during exactly the outage it exists to catch.
        with self.assertRaises(smtplib.SMTPAuthenticationError):
            verify_smtp_credentials(_config())

    @patch("api.services.email_service.smtplib.SMTP", new=RejectingLoginSmtpServer)
    def test_closes_the_connection_when_login_is_refused(self) -> None:
        with self.assertRaises(smtplib.SMTPAuthenticationError):
            verify_smtp_credentials(_config(smtp_port=587, smtp_security="starttls"))

        self.assertEqual(FakeSmtpServer.instances[0].quit_calls, 1)


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

    @patch("api.services.email_service.smtplib.SMTP_SSL", new=FakeSmtpServer)
    def test_send_yard_sign_confirmation_email_can_send_plain_text_only(self) -> None:
        refused = send_yard_sign_confirmation_email(
            _config(plain_text_confirmation_only=True), self.yard_sign_request
        )

        self.assertEqual(refused, {})
        _, recipients, raw_message = FakeSmtpServer.instances[0].sent_messages[0]
        parsed = message_from_string(raw_message)

        self.assertEqual(recipients, ["supporter@example.com"])
        self.assertEqual(parsed.get_content_type(), "text/plain")
        self.assertEqual(
            parsed["Subject"], "Thanks for requesting a yard sign for Julia Hamann for Mayor"
        )
        plain_text_payload = _decode_payload(parsed)
        self.assertIn("Thanks so much for your support, Julia!", plain_text_payload)
        self.assertIn("Paid for by Julia Hamann for Mankato Mayor", plain_text_payload)


if __name__ == "__main__":
    unittest.main()


class SafeGreetingTests(unittest.TestCase):
    """The confirmation greeting, ADR-0018.

    It is the one piece of caller-supplied text in a message the campaign's
    domain signs and sends to an address the caller also chose.
    """

    def test_real_names_are_untouched(self) -> None:
        # The case that matters most: this runs on every genuine submission,
        # and a filter that mangles names is worse than the problem it solves.
        for name in ("Alex", "José", "Mary-Anne", "O'Brien", "李雷", "Ngozi Adichie"):
            with self.subTest(name=name):
                self.assertEqual(_safe_greeting(name, "there"), name)

    def test_names_carrying_combining_marks_are_untouched(self) -> None:
        """The case the first version of this got wrong, caught by Copilot.

        A combining mark is category `M`, and `str.isalpha()` is false for it,
        so a letters-only filter deletes it. That is invisible for composed
        Latin text and catastrophic elsewhere: in Indic scripts the marks are
        the vowels, so "अनुराधा" came out as "अनरध". Composed "José" passed the
        original test purely because Python source is NFC by default.
        """
        for name in (
            unicodedata.normalize("NFD", "José"),
            unicodedata.normalize("NFD", "Ólafsdóttir"),
            "अनुराधा",
            "সুমিত",
            "பிரியா",
            "مُحَمَّد",
        ):
            with self.subTest(name=name):
                # NFC on both sides: the greeting normalises, so a decomposed
                # name comes back composed rather than changed.
                self.assertEqual(_safe_greeting(name, "there"), unicodedata.normalize("NFC", name))

    def test_bare_combining_marks_do_not_count_as_a_name(self) -> None:
        # Marks are kept, so something has to stop a string of nothing else
        # from being greeted -- it renders as stray glyphs on a stray letter.
        self.assertEqual(_safe_greeting("\u0301\u0301\u0301", "there"), "there")

    def test_a_phone_number_cannot_reach_the_greeting(self) -> None:
        self.assertNotIn("555", _safe_greeting("CALL 555-0142 NOW", "there"))

    def test_a_domain_cannot_reach_the_greeting(self) -> None:
        # The dot is the character that makes a domain a domain, and some mail
        # clients turn one into a link.
        self.assertNotIn(".", _safe_greeting("https://evil.example", "there"))

    def test_a_long_name_is_truncated(self) -> None:
        self.assertEqual(len(_safe_greeting("A" * 200, "there")), 30)

    def test_nothing_usable_falls_back(self) -> None:
        for empty in ("", "   ", "12345", "!!!"):
            with self.subTest(value=empty):
                self.assertEqual(_safe_greeting(empty, "there"), "there")

    def test_the_campaign_still_sees_what_was_submitted(self) -> None:
        """Only the greeting is sanitised, never the record.

        A volunteer following up needs the name as typed, so the notification
        email and the sheet row keep it verbatim. Sanitising those instead would
        quietly corrupt the campaign's own data to solve an email problem.
        """
        hostile = "CALL 555-0142"
        submission = Submission(
            first_name=hostile,
            last_name="",
            name=hostile,
            email="supporter@example.com",
            phone="",
            message="",
            help_ways=[],
        )

        self.assertIn(hostile, submission.to_email_body())
        self.assertIn(hostile, submission.to_sheet_row())

import unittest
from unittest.mock import patch

from api import models
from api.models import Submission, validate_submission


class FakeFormData:
    def __init__(self, pairs: list[tuple[str, str]]) -> None:
        self._pairs = pairs

    def get(self, key: str):
        values = [value for item_key, value in self._pairs if item_key == key]
        return values[-1] if values else None

    def getlist(self, key: str) -> list[str]:
        return [value for item_key, value in self._pairs if item_key == key]


class SubmissionParsingTests(unittest.TestCase):
    def test_from_json_composes_name_from_first_and_last(self) -> None:
        payload = {
            "firstName": "Julia",
            "lastName": "Hamann",
            "email": "julia@example.com",
            "helpWays": ["Door Knocking"],
        }

        submission = Submission.from_json(payload)

        self.assertEqual(submission.first_name, "Julia")
        self.assertEqual(submission.last_name, "Hamann")
        self.assertEqual(submission.name, "Julia Hamann")
        self.assertEqual(submission.help_ways, ["Door Knocking"])

    def test_from_json_uses_helpways_array_values(self) -> None:
        payload = {
            "firstName": "Julia",
            "email": "julia@example.com",
            "helpWays": ["Phone Banking", "Host a neighborhood event"],
        }

        submission = Submission.from_json(payload)

        self.assertEqual(
            submission.help_ways,
            ["Phone Banking", "Host a neighborhood event"],
        )

    def test_from_json_ignores_legacy_helpwaysother_field(self) -> None:
        payload = {
            "name": "Julia Hamann",
            "email": "julia@example.com",
            "helpWays": ["Other"],
            "helpWaysOther": "Translate campaign materials",
        }

        submission = Submission.from_json(payload)

        self.assertEqual(
            submission.help_ways,
            ["Other"],
        )

    def test_from_form_supports_helpways_without_brackets(self) -> None:
        form_data = FakeFormData(
            [
                ("firstName", "Julia"),
                ("lastName", "Hamann"),
                ("email", "julia@example.com"),
                ("helpWays", "Phone Banking"),
                ("helpWays", "Canvassing"),
            ]
        )

        submission = Submission.from_form(form_data)

        self.assertEqual(submission.first_name, "Julia")
        self.assertEqual(submission.last_name, "Hamann")
        self.assertEqual(submission.name, "Julia Hamann")
        self.assertEqual(submission.help_ways, ["Phone Banking", "Canvassing"])

    def test_from_form_uses_helpways_array_values(self) -> None:
        form_data = FakeFormData(
            [
                ("firstName", "Julia"),
                ("email", "julia@example.com"),
                ("helpWays[]", "Door Knocking"),
                ("helpWays[]", "Design social posts"),
            ]
        )

        submission = Submission.from_form(form_data)

        self.assertEqual(
            submission.help_ways,
            ["Door Knocking", "Design social posts"],
        )

    def test_to_sheet_row_uses_timestamp_first_and_last_name(self) -> None:
        submission = Submission(
            first_name="Julia",
            last_name="Hamann",
            name="Julia Hamann",
            email="julia@example.com",
            phone="555-555-5555",
            message="Ready to help.",
            help_ways=["Door Knocking", "Phone Banking"],
        )

        mocked_timestamp = "2026-05-29T12:00:00+00:00"
        with patch("api.models.datetime") as mock_datetime:
            mock_datetime.now.return_value.isoformat.return_value = mocked_timestamp
            row = submission.to_sheet_row()

        self.assertEqual(
            row,
            [
                mocked_timestamp,
                "Julia",
                "Hamann",
                "julia@example.com",
                "555-555-5555",
                "Door Knocking, Phone Banking",
                "Ready to help.",
            ],
        )


class SubmissionValidationTests(unittest.TestCase):
    def test_looks_like_email_rejects_control_characters(self) -> None:
        self.assertFalse(models.looks_like_email("julia@example.com\r\nBCC:evil@example.com"))

    def test_validate_submission_rejects_header_control_characters(self) -> None:
        submission = Submission(
            first_name="Julia\n",
            last_name="Hamann",
            name="Julia Hamann",
            email="julia@example.com",
            phone="555-555-5555",
            message="Ready to help.",
            help_ways=["Door Knocking"],
        )

        self.assertEqual(
            validate_submission(submission),
            "First name contains invalid characters.",
        )

    def test_validate_submission_rejects_oversized_message(self) -> None:
        submission = Submission(
            first_name="Julia",
            last_name="Hamann",
            name="Julia Hamann",
            email="julia@example.com",
            phone="555-555-5555",
            message="x" * (models.MAX_MESSAGE_LENGTH + 1),
            help_ways=["Door Knocking"],
        )

        self.assertEqual(
            validate_submission(submission),
            f"Message must be {models.MAX_MESSAGE_LENGTH} characters or fewer.",
        )


if __name__ == "__main__":
    unittest.main()

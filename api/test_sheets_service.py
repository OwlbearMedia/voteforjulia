import unittest
from unittest.mock import MagicMock, patch

from api.config import SheetsConfig
from api.services.sheets_service import append_row, reset_sheets_service_cache


def _fake_service(sheets: list[dict]) -> MagicMock:
    service = MagicMock()
    service.spreadsheets.return_value.get.return_value.execute.return_value = {
        "sheets": sheets
    }
    return service


class AppendRowTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_sheets_service_cache()
        self.config = SheetsConfig(
            spreadsheet_id="sheet-123",
            worksheet="2083435320",
            service_account_file="",
            service_account_json='{"type": "service_account"}',
        )

    def tearDown(self) -> None:
        reset_sheets_service_cache()

    def test_noop_when_spreadsheet_id_missing(self) -> None:
        config = SheetsConfig(
            spreadsheet_id="",
            worksheet="Sheet1",
            service_account_file="",
            service_account_json="",
        )

        with patch("googleapiclient.discovery.build") as build:
            append_row(config, ["a"])

        build.assert_not_called()

    def test_resolves_gid_to_sheet_title(self) -> None:
        service = _fake_service(
            [{"properties": {"sheetId": 2083435320, "title": "Yard Signs"}}]
        )

        with patch("google.oauth2.service_account.Credentials.from_service_account_info"), patch(
            "googleapiclient.discovery.build", return_value=service
        ):
            append_row(self.config, ["2026-01-01", "Jane", "Doe"])

        update_call = service.spreadsheets.return_value.values.return_value.update
        update_call.assert_called_once()
        self.assertEqual(update_call.call_args.kwargs["range"], "'Yard Signs'!A2")
        self.assertEqual(
            update_call.call_args.kwargs["body"], {"values": [["2026-01-01", "Jane", "Doe"]]}
        )

    def test_writes_after_last_non_empty_row_in_column_a(self) -> None:
        # Regression test: other columns (e.g. checkboxes defaulting every
        # cell to FALSE) must not influence where the row lands -- only
        # column A's actual values determine the next open row.
        config = SheetsConfig(
            spreadsheet_id="sheet-123",
            worksheet="Sheet1",
            service_account_file="",
            service_account_json='{"type": "service_account"}',
        )
        service = _fake_service([])
        service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [["2026-01-01"], ["2026-01-02"], ["2026-01-03"]]
        }

        with patch("google.oauth2.service_account.Credentials.from_service_account_info"), patch(
            "googleapiclient.discovery.build", return_value=service
        ):
            append_row(config, ["2026-01-04", "Jane", "Doe"])

        update_call = service.spreadsheets.return_value.values.return_value.update
        self.assertEqual(update_call.call_args.kwargs["range"], "Sheet1!A5")

    def test_raises_when_gid_not_found(self) -> None:
        service = _fake_service([{"properties": {"sheetId": 999, "title": "Sheet1"}}])

        with patch("google.oauth2.service_account.Credentials.from_service_account_info"), patch(
            "googleapiclient.discovery.build", return_value=service
        ):
            with self.assertRaises(ValueError):
                append_row(self.config, ["row"])

    def test_plain_worksheet_name_is_used_without_lookup(self) -> None:
        config = SheetsConfig(
            spreadsheet_id="sheet-123",
            worksheet="Sheet1",
            service_account_file="",
            service_account_json='{"type": "service_account"}',
        )
        service = _fake_service([])

        with patch("google.oauth2.service_account.Credentials.from_service_account_info"), patch(
            "googleapiclient.discovery.build", return_value=service
        ):
            append_row(config, ["row"])

        service.spreadsheets.return_value.get.assert_not_called()
        update_call = service.spreadsheets.return_value.values.return_value.update
        self.assertEqual(update_call.call_args.kwargs["range"], "Sheet1!A2")


if __name__ == "__main__":
    unittest.main()

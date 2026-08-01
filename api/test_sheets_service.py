import unittest
from unittest.mock import MagicMock, patch

from api.config import SheetsConfig
from api.services.sheets_service import (
    append_row,
    reset_sheets_service_cache,
    verify_sheets_access,
)


def _fake_service(sheets: list[dict]) -> MagicMock:
    service = MagicMock()
    service.spreadsheets.return_value.get.return_value.execute.return_value = {"sheets": sheets}
    return service


def _config(**overrides) -> SheetsConfig:
    defaults = {
        "spreadsheet_id": "sheet-123",
        "worksheet": "Sheet1",
        "service_account_file": "",
        "service_account_json": '{"type": "service_account"}',
    }
    return SheetsConfig(**{**defaults, **overrides})


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
        service = _fake_service([{"properties": {"sheetId": 2083435320, "title": "Yard Signs"}}])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(self.config, ["2026-01-01", "Jane", "Doe"])

        update_call = service.spreadsheets.return_value.values.return_value.update
        update_call.assert_called_once()
        self.assertEqual(update_call.call_args.kwargs["range"], "'Yard Signs'!A2")
        self.assertEqual(
            update_call.call_args.kwargs["body"], {"values": [["2026-01-01", "Jane", "Doe"]]}
        )

    def test_writes_after_last_non_empty_row(self) -> None:
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

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(config, ["2026-01-04", "Jane", "Doe"])

        get_call = service.spreadsheets.return_value.values.return_value.get
        self.assertEqual(get_call.call_args.kwargs["range"], "Sheet1!A2:C")
        update_call = service.spreadsheets.return_value.values.return_value.update
        self.assertEqual(update_call.call_args.kwargs["range"], "Sheet1!A5")

    def test_skips_manual_rows_missing_column_a(self) -> None:
        # Regression test: a manually entered row may have no timestamp in
        # column A but still hold data in other columns. It must not be
        # overwritten -- any occupied cell in the written columns marks the
        # row as taken.
        config = SheetsConfig(
            spreadsheet_id="sheet-123",
            worksheet="Sheet1",
            service_account_file="",
            service_account_json='{"type": "service_account"}',
        )
        service = _fake_service([])
        service.spreadsheets.return_value.values.return_value.get.return_value.execute.return_value = {
            "values": [
                ["2026-01-01"],
                [],
                ["", "Jane", "Doe", "", "555-1234"],
            ]
        }

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(config, ["2026-01-04", "John", "Smith", "j@example.com", "555-5678"])

        update_call = service.spreadsheets.return_value.values.return_value.update
        self.assertEqual(update_call.call_args.kwargs["range"], "Sheet1!A5")

    def test_raises_when_gid_not_found(self) -> None:
        service = _fake_service([{"properties": {"sheetId": 999, "title": "Sheet1"}}])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
            self.assertRaises(ValueError),
        ):
            append_row(self.config, ["row"])

    def test_plain_worksheet_name_is_used_without_lookup(self) -> None:
        config = SheetsConfig(
            spreadsheet_id="sheet-123",
            worksheet="Sheet1",
            service_account_file="",
            service_account_json='{"type": "service_account"}',
        )
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(config, ["row"])

        service.spreadsheets.return_value.get.assert_not_called()
        update_call = service.spreadsheets.return_value.values.return_value.update
        self.assertEqual(update_call.call_args.kwargs["range"], "Sheet1!A2")

    def test_escapes_apostrophes_in_worksheet_title(self) -> None:
        # A1 notation quotes a title containing spaces or punctuation with
        # single quotes, and an apostrophe inside it must be doubled -- an
        # unescaped one closes the quoted title early and the API rejects the
        # range.
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(worksheet="Julia's Signs"), ["row"])

        update_call = service.spreadsheets.return_value.values.return_value.update
        self.assertEqual(update_call.call_args.kwargs["range"], "'Julia''s Signs'!A2")

    def test_column_letters_continue_past_z(self) -> None:
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(), [f"value-{index}" for index in range(27)])

        get_call = service.spreadsheets.return_value.values.return_value.get
        self.assertEqual(get_call.call_args.kwargs["range"], "Sheet1!A2:AA")


class SheetsCredentialTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_sheets_service_cache()

    def tearDown(self) -> None:
        reset_sheets_service_cache()

    def test_uses_service_account_file_when_configured(self) -> None:
        service = _fake_service([])

        with (
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as from_file,
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(
                _config(service_account_file="/keys/sa.json", service_account_json=""), ["a"]
            )

        from_file.assert_called_once()
        self.assertEqual(from_file.call_args.args[0], "/keys/sa.json")
        self.assertEqual(
            from_file.call_args.kwargs["scopes"],
            ["https://www.googleapis.com/auth/spreadsheets"],
        )

    def test_file_takes_precedence_over_inline_json(self) -> None:
        service = _fake_service([])

        with (
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_file"
            ) as from_file,
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_info"
            ) as from_info,
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(service_account_file="/keys/sa.json"), ["a"])

        from_file.assert_called_once()
        from_info.assert_not_called()

    def test_parses_inline_json_credentials(self) -> None:
        service = _fake_service([])

        with (
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_info"
            ) as from_info,
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(service_account_json='{"type": "service_account"}'), ["a"])

        from_info.assert_called_once()
        self.assertEqual(from_info.call_args.args[0], {"type": "service_account"})

    def test_raises_when_no_credentials_are_configured(self) -> None:
        # A configured spreadsheet with no credentials is a misconfiguration,
        # not a no-op: append_row's early return only covers a missing
        # spreadsheet ID, so this must surface rather than silently drop rows.
        with self.assertRaises(ValueError) as raised:
            append_row(_config(service_account_file="", service_account_json=""), ["a"])

        self.assertIn("credentials are not configured", str(raised.exception))


class ServiceCacheTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_sheets_service_cache()

    def tearDown(self) -> None:
        reset_sheets_service_cache()

    def test_reuses_one_service_across_submissions(self) -> None:
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service) as build,
        ):
            append_row(_config(), ["first"])
            append_row(_config(), ["second"])

        self.assertEqual(build.call_count, 1)

    def test_different_credentials_get_their_own_service(self) -> None:
        # The negative half of the test above: without it, that assertion would
        # still pass if the cache ignored the credentials entirely and handed
        # every caller the same client.
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service) as build,
        ):
            append_row(_config(service_account_json='{"client_email": "one@example.com"}'), ["a"])
            append_row(_config(service_account_json='{"client_email": "two@example.com"}'), ["b"])

        self.assertEqual(build.call_count, 2)

    def test_reset_forces_a_fresh_service(self) -> None:
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service) as build,
        ):
            append_row(_config(), ["first"])
            reset_sheets_service_cache()
            append_row(_config(), ["second"])

        self.assertEqual(build.call_count, 2)


class WorksheetResolutionTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_sheets_service_cache()

    def tearDown(self) -> None:
        reset_sheets_service_cache()

    def test_gid_lookup_happens_once_per_spreadsheet(self) -> None:
        service = _fake_service([{"properties": {"sheetId": 2083435320, "title": "Yard Signs"}}])
        config = _config(worksheet="2083435320")

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(config, ["first"])
            append_row(config, ["second"])

        self.assertEqual(service.spreadsheets.return_value.get.call_count, 1)

    def test_gid_cache_is_keyed_by_spreadsheet(self) -> None:
        # The negative half: the same gid in a different spreadsheet is a
        # different worksheet, so a cache keyed on the gid alone would return
        # the wrong title and write rows into the wrong tab.
        service = _fake_service([{"properties": {"sheetId": 2083435320, "title": "Yard Signs"}}])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(spreadsheet_id="sheet-123", worksheet="2083435320"), ["a"])
            append_row(_config(spreadsheet_id="sheet-456", worksheet="2083435320"), ["b"])

        self.assertEqual(service.spreadsheets.return_value.get.call_count, 2)

    def test_all_digit_title_wins_over_a_matching_gid(self) -> None:
        # A tab literally titled "2026" is a valid title, so it must be
        # preferred over the unrelated sheet whose gid happens to be 2026.
        service = _fake_service(
            [
                {"properties": {"sheetId": 999, "title": "2026"}},
                {"properties": {"sheetId": 2026, "title": "Archive"}},
            ]
        )

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(worksheet="2026"), ["row"])

        update_call = service.spreadsheets.return_value.values.return_value.update
        self.assertEqual(update_call.call_args.kwargs["range"], "2026!A2")

    def test_all_digit_title_is_cached_as_itself(self) -> None:
        service = _fake_service([{"properties": {"sheetId": 999, "title": "2026"}}])
        config = _config(worksheet="2026")

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(config, ["first"])
            append_row(config, ["second"])

        self.assertEqual(service.spreadsheets.return_value.get.call_count, 1)
        update_call = service.spreadsheets.return_value.values.return_value.update
        self.assertEqual(update_call.call_args.kwargs["range"], "2026!A2")


class VerifySheetsAccessTests(unittest.TestCase):
    """The deep health check's Sheets probe (api/app.py's /health/deep)."""

    def setUp(self) -> None:
        reset_sheets_service_cache()

    def tearDown(self) -> None:
        reset_sheets_service_cache()

    def test_raises_when_spreadsheet_id_is_missing(self) -> None:
        with (
            patch("googleapiclient.discovery.build") as build,
            self.assertRaises(ValueError) as raised,
        ):
            verify_sheets_access(_config(spreadsheet_id=""))

        self.assertIn("GOOGLE_SHEETS_SPREADSHEET_ID", str(raised.exception))
        build.assert_not_called()

    def test_reads_metadata_even_for_a_plain_worksheet_name(self) -> None:
        # The point of the probe: `_resolve_worksheet_title` returns
        # immediately for a non-numeric worksheet, so reusing it would verify
        # nothing for the common "Sheet1" / "Yard Signs" configs. This must
        # issue its own request and actually reach the API.
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            verify_sheets_access(_config(worksheet="Sheet1"))

        get_call = service.spreadsheets.return_value.get
        get_call.assert_called_once()
        self.assertEqual(get_call.call_args.kwargs["spreadsheetId"], "sheet-123")
        self.assertEqual(get_call.call_args.kwargs["fields"], "spreadsheetId")
        get_call.return_value.execute.assert_called_once()
        service.spreadsheets.return_value.values.assert_not_called()

    def test_propagates_api_failures(self) -> None:
        # /health/deep reports "fail" by catching whatever this raises;
        # swallowing an error here would make the probe permanently green.
        service = _fake_service([])
        service.spreadsheets.return_value.get.return_value.execute.side_effect = OSError(
            "connection refused"
        )

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
            self.assertRaises(OSError),
        ):
            verify_sheets_access(_config())

    def test_propagates_missing_credentials(self) -> None:
        with self.assertRaises(ValueError) as raised:
            verify_sheets_access(_config(service_account_file="", service_account_json=""))

        self.assertIn("credentials are not configured", str(raised.exception))


if __name__ == "__main__":
    unittest.main()

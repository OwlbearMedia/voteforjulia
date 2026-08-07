import http.client
import ssl
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

        append_call = service.spreadsheets.return_value.values.return_value.append
        append_call.assert_called_once()
        self.assertEqual(append_call.call_args.kwargs["range"], "'Yard Signs'!A:C")
        self.assertEqual(
            append_call.call_args.kwargs["body"], {"values": [["2026-01-01", "Jane", "Doe"]]}
        )

    def test_row_placement_is_resolved_server_side_in_the_write_call(self) -> None:
        # Regression test for silent overwrites. Placement used to be chosen by
        # a values.get and then written with a values.update, which left a
        # window where two concurrent submissions picked the same row and the
        # second destroyed the first -- invisibly, since both requests returned
        # 200 and both submitters got a confirmation email. Passenger runs
        # several worker processes, so no in-process lock could close it.
        #
        # Asserting the *absence* of a preceding read is the point: it is what
        # proves there is no check whose result could go stale before the write.
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(), ["2026-01-04", "Jane", "Doe"])

        values = service.spreadsheets.return_value.values.return_value
        values.get.assert_not_called()
        values.update.assert_not_called()
        values.append.assert_called_once()

    def test_append_inserts_rather_than_overwriting(self) -> None:
        # The other half of the guarantee above, and what now protects the
        # manually entered rows the old row search handled by hand (a row with
        # no column A timestamp but data in other columns). INSERT_ROWS makes
        # the API open a new row instead of writing over whatever occupies the
        # target cells, so even if table detection lands somewhere unexpected
        # the worst case is a row in an odd position, never a row destroyed.
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(), ["2026-01-04", "Jane", "Doe"])

        append_call = service.spreadsheets.return_value.values.return_value.append
        self.assertEqual(append_call.call_args.kwargs["insertDataOption"], "INSERT_ROWS")
        # RAW keeps a leading "=" stored as text instead of evaluated, so a
        # submitted field cannot become a live formula in the volunteers' sheet.
        self.assertEqual(append_call.call_args.kwargs["valueInputOption"], "RAW")

    def test_logs_where_the_row_actually_landed(self) -> None:
        # The failure this exists for looks exactly like a healthy append from
        # the outside: HTTP 200, a confirmation email sent, and a log line
        # saying the row went to `A:G`. `values.append` places the row after the
        # last row of the table it detects, and that detection is not limited to
        # the columns in the range — so a stray value in column H at row 900
        # sends the row to 901 while every signal still reads "success".
        #
        # The response is the only thing that can tell those apart, so the
        # assertion is on the landing spot appearing in the log, not on the call
        # arguments (which are the same either way and would restate the diff).
        service = _fake_service([])
        service.spreadsheets.return_value.values.return_value.append.return_value.execute.return_value = {
            "tableRange": "'Yard Signs'!A1:H900",
            "updates": {"updatedRange": "'Yard Signs'!A901:G901"},
        }

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
            self.assertLogs("api.services.sheets_service", level="INFO") as captured,
        ):
            append_row(_config(worksheet="Yard Signs"), ["2026-01-04", "Jane", "Doe"])

        self.assertIn("'Yard Signs'!A901:G901", captured.output[-1])
        self.assertIn("'Yard Signs'!A1:H900", captured.output[-1])

    def test_append_logging_survives_a_response_without_placement(self) -> None:
        # A MagicMock response, or a future API version that drops the field,
        # must not turn a successful write into an exception in the logging.
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
            self.assertLogs("api.services.sheets_service", level="INFO") as captured,
        ):
            append_row(_config(), ["2026-01-04", "Jane", "Doe"])

        self.assertIn("unknown", captured.output[-1])

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
        append_call = service.spreadsheets.return_value.values.return_value.append
        self.assertEqual(append_call.call_args.kwargs["range"], "Sheet1!A:A")

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

        append_call = service.spreadsheets.return_value.values.return_value.append
        self.assertEqual(append_call.call_args.kwargs["range"], "'Julia''s Signs'!A:A")

    def test_column_letters_continue_past_z(self) -> None:
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(), [f"value-{index}" for index in range(27)])

        append_call = service.spreadsheets.return_value.values.return_value.append
        self.assertEqual(append_call.call_args.kwargs["range"], "Sheet1!A:AA")


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

    def test_transport_is_built_with_the_configured_timeout(self) -> None:
        # `build(credentials=...)` makes its own httplib2.Http whose timeout is
        # None, which is the unbounded wait this replaces -- and the Sheets call
        # runs after both emails are away, so a stall there holds a worker on a
        # request that has already had its user-visible effect. There is no
        # timeout argument on build(), so the transport is constructed here and
        # passed in; this asserts the value survives that hand-off.
        service = _fake_service([])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("httplib2.Http") as http,
            patch("googleapiclient.discovery.build", return_value=service),
        ):
            append_row(_config(timeout_seconds=7.5), ["a"])

        http.assert_called_once_with(timeout=7.5)

    def test_transport_is_authorized_with_the_credentials(self) -> None:
        # The negative half of the test above. `http` and `credentials` are
        # mutually exclusive on build(), so supplying a transport to carry the
        # timeout means authorizing it here instead -- and handing build() a
        # bare Http would send every request unauthenticated while still
        # passing the timeout assertion.
        service = _fake_service([])

        with (
            patch(
                "google.oauth2.service_account.Credentials.from_service_account_info"
            ) as from_info,
            patch("google_auth_httplib2.AuthorizedHttp") as authorized_http,
            patch("googleapiclient.discovery.build", return_value=service) as build,
        ):
            append_row(_config(), ["a"])

        self.assertEqual(authorized_http.call_args.args[0], from_info.return_value)
        self.assertIs(build.call_args.kwargs["http"], authorized_http.return_value)
        self.assertNotIn("credentials", build.call_args.kwargs)

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

        append_call = service.spreadsheets.return_value.values.return_value.append
        self.assertEqual(append_call.call_args.kwargs["range"], "2026!A:A")

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
        append_call = service.spreadsheets.return_value.values.return_value.append
        self.assertEqual(append_call.call_args.kwargs["range"], "2026!A:A")


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


class StaleConnectionTests(unittest.TestCase):
    """A cached client whose keep-alive socket the far end already closed.

    Seen in production as nine `BrokenPipeError` failures from `/health/deep`
    in a day. Reads recover by rebuilding the client; the write deliberately
    does not, because a retry could duplicate a supporter's row.
    """

    def setUp(self) -> None:
        reset_sheets_service_cache()

    def tearDown(self) -> None:
        reset_sheets_service_cache()

    @staticmethod
    def _reader(execute_side_effect) -> MagicMock:
        service = MagicMock()
        service.spreadsheets.return_value.get.return_value.execute.side_effect = execute_side_effect
        return service

    @staticmethod
    def _writer(execute_side_effect=None) -> MagicMock:
        service = MagicMock()
        append = service.spreadsheets.return_value.values.return_value.append
        if execute_side_effect is not None:
            append.return_value.execute.side_effect = execute_side_effect
        return service

    def test_read_rebuilds_the_client_and_retries_once(self) -> None:
        dead = self._reader(BrokenPipeError(32, "Broken pipe"))
        fresh = self._reader([{"spreadsheetId": "sheet-123"}])

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", side_effect=[dead, fresh]) as build,
        ):
            verify_sheets_access(_config())

        # Two clients built: the poisoned one was discarded, not reused.
        self.assertEqual(build.call_count, 2)
        fresh.spreadsheets.return_value.get.return_value.execute.assert_called_once()

    def test_read_gives_up_after_one_retry(self) -> None:
        dead = self._reader(BrokenPipeError(32, "Broken pipe"))
        also_dead = self._reader(BrokenPipeError(32, "Broken pipe"))

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", side_effect=[dead, also_dead]) as build,
            self.assertRaises(BrokenPipeError),
        ):
            verify_sheets_access(_config())

        self.assertEqual(build.call_count, 2)

    def test_read_does_not_retry_a_real_api_refusal(self) -> None:
        # A 403 or a missing sheet is the API answering. Rebuilding the client
        # cannot change the answer, and retrying doubles the latency.
        from googleapiclient.errors import HttpError

        refused = self._reader(HttpError(MagicMock(status=403), b"forbidden"))

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", side_effect=[refused]) as build,
            self.assertRaises(HttpError),
        ):
            verify_sheets_access(_config())

        self.assertEqual(build.call_count, 1)

    def test_append_does_not_retry(self) -> None:
        # The critical one. A connection error surfaces while reading the
        # response, so the server may already have inserted the row — retrying
        # would silently duplicate a supporter's submission.
        dead = self._writer(BrokenPipeError(32, "Broken pipe"))

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", side_effect=[dead]) as build,
            self.assertRaises(BrokenPipeError),
        ):
            append_row(_config(), ["a", "b"])

        self.assertEqual(build.call_count, 1)
        dead.spreadsheets.return_value.values.return_value.append.assert_called_once()

    def test_append_discards_the_poisoned_client(self) -> None:
        # Without this the same dead socket fails every submission until the
        # Passenger worker recycles.
        dead = self._writer(BrokenPipeError(32, "Broken pipe"))
        fresh = self._writer()

        with (
            patch("google.oauth2.service_account.Credentials.from_service_account_info"),
            patch("googleapiclient.discovery.build", side_effect=[dead, fresh]),
        ):
            with self.assertRaises(BrokenPipeError):
                append_row(_config(), ["a", "b"])

            # The next submission gets a new client rather than the dead one.
            append_row(_config(), ["c", "d"])

        fresh.spreadsheets.return_value.values.return_value.append.assert_called_once()

    def test_ssl_and_protocol_errors_count_as_stale(self) -> None:
        for error in (
            ssl.SSLEOFError("EOF occurred in violation of protocol"),
            http.client.RemoteDisconnected("Remote end closed connection"),
        ):
            with self.subTest(error=type(error).__name__):
                reset_sheets_service_cache()
                dead = self._reader(error)
                fresh = self._reader([{"spreadsheetId": "sheet-123"}])

                with (
                    patch("google.oauth2.service_account.Credentials.from_service_account_info"),
                    patch("googleapiclient.discovery.build", side_effect=[dead, fresh]) as build,
                ):
                    verify_sheets_access(_config())

                self.assertEqual(build.call_count, 2)


if __name__ == "__main__":
    unittest.main()

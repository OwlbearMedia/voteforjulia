from __future__ import annotations

import http.client
import json
import logging
import re
import ssl

from api.config import SheetsConfig

logger = logging.getLogger(__name__)

# Raised when the cached client writes into a keep-alive socket the far end has
# already closed. Observed in production as `BrokenPipeError: [Errno 32]` from
# nine `/health/deep` probes in a day, always on the SSL response read.
#
# googleapiclient's `HttpError` is deliberately absent: a 403, 404 or quota
# refusal is the API answering, and rebuilding the client would not change it.
# `TimeoutError` is absent too — a timeout means the server is slow, not that
# the socket is dead, and retrying only doubles a wait `timeout_seconds` exists
# to bound.
_STALE_CONNECTION_ERRORS = (ConnectionError, ssl.SSLError, http.client.HTTPException)

# Keyed by (service_account_file, service_account_json, timeout_seconds), which
# together identify the client. The first two identify the credentials; the
# timeout is part of the key because it is baked into the cached transport, so
# a client built under one timeout must not be handed to a caller asking for
# another. Building a service client involves parsing the service account key
# and constructing the API resource; the underlying google-auth credentials
# object refreshes its own access token as needed, so it's safe to reuse across
# requests in this long-lived process instead of rebuilding it per submission.
_service_cache: dict[tuple[str, str, float], object] = {}
_worksheet_title_cache: dict[tuple[str, str, str], str] = {}


def reset_sheets_service_cache() -> None:
    _service_cache.clear()
    _worksheet_title_cache.clear()


def _get_sheets_credentials(config: SheetsConfig):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    from google.oauth2.service_account import Credentials

    if config.service_account_file:
        return Credentials.from_service_account_file(config.service_account_file, scopes=scopes)

    if config.service_account_json:
        info = json.loads(config.service_account_json)
        return Credentials.from_service_account_info(info, scopes=scopes)

    raise ValueError("Google Sheets credentials are not configured.")


def _get_sheets_service(config: SheetsConfig):
    cache_key = (config.service_account_file, config.service_account_json, config.timeout_seconds)
    cached = _service_cache.get(cache_key)
    if cached is not None:
        return cached

    credentials = _get_sheets_credentials(config)

    # `build(credentials=...)` constructs its own httplib2.Http, whose `timeout`
    # defaults to None -- the same unbounded wait the SMTP client had. There is
    # no argument for it, so the transport has to be supplied ready-made. That
    # means authorizing it here too: `http` and `credentials` are mutually
    # exclusive, and passing a bare Http would send the requests unauthenticated.
    #
    # This matters more than the SMTP timeout, not less: the Sheets write runs
    # *after* both emails are away, so a stall here holds a worker open on a
    # request whose user-visible side effects have already happened.
    import google_auth_httplib2
    import httplib2
    from googleapiclient.discovery import build

    authorized_http = google_auth_httplib2.AuthorizedHttp(
        credentials, http=httplib2.Http(timeout=config.timeout_seconds)
    )
    service = build("sheets", "v4", http=authorized_http, cache_discovery=False)
    _service_cache[cache_key] = service
    return service


def _read_with_reconnect(config: SheetsConfig, build_request):
    """Run a **read** against the cached client, rebuilding it once if the socket is dead.

    Only safe for reads. A connection error surfaces while reading the
    response, which cannot be told apart from a request the server already
    applied — so retrying a write risks a duplicate row. See `append_row`.
    """
    try:
        return build_request(_get_sheets_service(config)).execute()
    except _STALE_CONNECTION_ERRORS:
        logger.warning("Sheets client had a dead connection; rebuilding and retrying the read once")
        reset_sheets_service_cache()
        return build_request(_get_sheets_service(config)).execute()


def verify_sheets_access(config: SheetsConfig) -> None:
    """Check the service account can actually read the spreadsheet. Raises on failure.

    Deliberately its own metadata read rather than a call to
    `_resolve_worksheet_title`: that helper returns immediately for a
    non-numeric worksheet (the common case — "Sheet1", "Yard Signs"), so it
    would verify nothing. Requesting only `spreadsheetId` keeps the response
    small while still proving credentials parse, the token refreshes, and the
    sheet is shared with the service account.
    """
    if not config.spreadsheet_id:
        raise ValueError("Google Sheets is not configured: missing GOOGLE_SHEETS_SPREADSHEET_ID")

    _read_with_reconnect(
        config,
        lambda service: service.spreadsheets().get(
            spreadsheetId=config.spreadsheet_id, fields="spreadsheetId"
        ),
    )


def _quote_sheet_title(title: str) -> str:
    if re.fullmatch(r"[A-Za-z0-9_]+", title):
        return title

    return "'" + title.replace("'", "''") + "'"


def _resolve_worksheet_title(service, spreadsheet_id: str, worksheet: str) -> str:
    # A1 ranges address sheets by title, but a sheet's gid (visible in its URL as
    # #gid=...) is a separate, more stable identifier some configs store instead.
    # Resolve a gid to its current title before building the range. A worksheet
    # value that happens to be all digits (e.g. a tab literally titled "2026")
    # is still a valid literal title, so check for a title match before
    # falling back to gid resolution.
    if not worksheet.isdigit():
        return worksheet

    cache_key = (spreadsheet_id, worksheet)
    cached_title = _worksheet_title_cache.get(cache_key)
    if cached_title is not None:
        return cached_title

    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
        .execute()
    )
    sheets = metadata.get("sheets", [])

    for sheet in sheets:
        properties = sheet.get("properties", {})
        if properties.get("title") == worksheet:
            _worksheet_title_cache[cache_key] = worksheet
            return worksheet

    gid = int(worksheet)
    for sheet in sheets:
        properties = sheet.get("properties", {})
        if properties.get("sheetId") == gid:
            title = properties.get("title", worksheet)
            _worksheet_title_cache[cache_key] = title
            return title

    raise ValueError(
        f"No worksheet found with title or gid {worksheet} in spreadsheet {spreadsheet_id}"
    )


def _column_letter(index: int) -> str:
    letters = ""
    while index > 0:
        index, remainder = divmod(index - 1, 26)
        letters = chr(ord("A") + remainder) + letters
    return letters


def append_row(config: SheetsConfig, row: list[str]) -> None:
    if not config.spreadsheet_id:
        return

    service = _get_sheets_service(config)
    worksheet_title = _resolve_worksheet_title(service, config.spreadsheet_id, config.worksheet)

    # The range is scoped to exactly the columns this submission writes, which
    # is what the previous hand-rolled row search was really for: append()'s
    # table detection was "thrown off" by unrelated columns holding values in
    # rows with no real submission (a checkbox column defaults every cell to
    # FALSE rather than truly empty). Bounding the range excludes those columns
    # from detection without taking the placement decision away from the API.
    end_column = _column_letter(max(len(row), 1))
    range_name = f"{_quote_sheet_title(worksheet_title)}!A:{end_column}"

    # Read-then-write is what this replaces. Choosing the row with a values.get
    # and then writing to it with a values.update is a time-of-check/
    # time-of-use gap: two submissions in flight pick the same row and the
    # second update overwrites the first, silently -- both submitters got their
    # confirmation email and both requests returned 200. Passenger runs several
    # worker processes, so no in-process lock could have closed it.
    #
    # append() resolves the insertion point server-side in the same call that
    # writes, so there is no gap. INSERT_ROWS is the other half: it inserts a
    # new row rather than writing over whatever occupies the target cells, so
    # even if table detection lands somewhere unexpected the failure mode is a
    # row in an odd position, never a row destroyed. That is also what now
    # protects manually entered rows that have no column A timestamp.
    # Not retried, unlike the reads in `_read_with_reconnect`. A dead keep-alive
    # socket surfaces while reading the *response*, which is indistinguishable
    # from a request the server already applied — so a retry can duplicate a
    # supporter's row, silently, in the sheet that is half the system of record
    # ([ADR-0004](../../docs/adr/0004-no-database.md)). Failing is the better
    # error: the caller returns a 502 and logs the raw body, which is the
    # designed recovery path.
    #
    # The cache is still cleared, so the poisoned client dies with this request
    # instead of failing every submission until the worker recycles. In
    # practice /health/deep exercises the same cached client every 5 minutes and
    # discards a stale one long before a submission — rare traffic riding on a
    # frequent probe's connection hygiene.
    try:
        service.spreadsheets().values().append(
            spreadsheetId=config.spreadsheet_id,
            range=range_name,
            valueInputOption="RAW",
            insertDataOption="INSERT_ROWS",
            body={"values": [row]},
        ).execute()
    except _STALE_CONNECTION_ERRORS:
        logger.warning("Sheets client had a dead connection during append; discarding it")
        reset_sheets_service_cache()
        raise

    logger.info("Appended row to %s in spreadsheet %s", range_name, config.spreadsheet_id)

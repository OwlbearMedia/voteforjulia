from __future__ import annotations

import json
import re

from api.config import SheetsConfig


def _get_sheets_credentials(config: SheetsConfig):
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    from google.oauth2.service_account import Credentials

    if config.service_account_file:
        return Credentials.from_service_account_file(config.service_account_file, scopes=scopes)

    if config.service_account_json:
        info = json.loads(config.service_account_json)
        return Credentials.from_service_account_info(info, scopes=scopes)

    raise ValueError("Google Sheets credentials are not configured.")


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

    metadata = (
        service.spreadsheets()
        .get(spreadsheetId=spreadsheet_id, fields="sheets.properties")
        .execute()
    )
    sheets = metadata.get("sheets", [])

    for sheet in sheets:
        properties = sheet.get("properties", {})
        if properties.get("title") == worksheet:
            return worksheet

    gid = int(worksheet)
    for sheet in sheets:
        properties = sheet.get("properties", {})
        if properties.get("sheetId") == gid:
            return properties.get("title", worksheet)

    raise ValueError(
        f"No worksheet found with title or gid {worksheet} in spreadsheet {spreadsheet_id}"
    )


def append_row(config: SheetsConfig, row: list[str]) -> None:
    if not config.spreadsheet_id:
        return

    credentials = _get_sheets_credentials(config)
    from googleapiclient.discovery import build

    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    worksheet_title = _resolve_worksheet_title(service, config.spreadsheet_id, config.worksheet)
    range_name = f"{_quote_sheet_title(worksheet_title)}!A:A"

    service.spreadsheets().values().append(
        spreadsheetId=config.spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

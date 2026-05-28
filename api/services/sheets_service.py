import json

from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build

from api.config import SheetsConfig


def _get_sheets_credentials(config: SheetsConfig) -> Credentials:
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]

    if config.service_account_file:
        return Credentials.from_service_account_file(config.service_account_file, scopes=scopes)

    if config.service_account_json:
        info = json.loads(config.service_account_json)
        return Credentials.from_service_account_info(info, scopes=scopes)

    raise ValueError("Google Sheets credentials are not configured.")


def append_row(config: SheetsConfig, row: list[str]) -> None:
    if not config.spreadsheet_id:
        return

    credentials = _get_sheets_credentials(config)
    service = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    range_name = f"{config.worksheet}!A:A"

    service.spreadsheets().values().append(
        spreadsheetId=config.spreadsheet_id,
        range=range_name,
        valueInputOption="RAW",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()

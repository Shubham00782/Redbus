import logging
import os

import gspread
from google.oauth2.service_account import Credentials
from gspread.exceptions import WorksheetNotFound

logger = logging.getLogger(__name__)

SHEET_HEADERS = [
    "Scraped At",
    "Journey Date",
    "From",
    "To",
    "Buses Found",
    "Number Plate",
    "Travels Name",
    "Make",
    "Rating",
    "Boarding Time",
    "Dropping Time",
    "Total Seats",
    "Booked Seats",
    "Occupancy Percentage",
    "Min Price",
    "Max Price",
]

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
_HISTORY_ROWS = 5000


class GoogleSheetConfigError(Exception):
    """Raised when the sheet id or service-account file is not configured."""


class GoogleSheetWriter:
    """Append occupancy rows to the existing worksheet.

    Each run adds rows under the same header. The worksheet is created only
    when that tab is missing, so three months of daily runs stay in one report.
    """

    def __init__(self, spreadsheet_id: str, worksheet_name: str, credentials_path: str):
        spreadsheet_id = (spreadsheet_id or "").strip()
        if not spreadsheet_id:
            raise GoogleSheetConfigError(
                "Set spreadsheet_id under [GoogleSheets] in config/config.ini, "
                "and share that sheet with the service account email as Editor."
            )
        credentials_path = _resolve_path(credentials_path)
        if not os.path.isfile(credentials_path):
            raise GoogleSheetConfigError(
                f"Google service account file not found at {credentials_path}. "
                "Download the JSON key and save it at that path."
            )

        credentials = Credentials.from_service_account_file(credentials_path, scopes=_SCOPES)
        client = gspread.authorize(credentials)
        try:
            spreadsheet = client.open_by_key(spreadsheet_id)
        except PermissionError as exc:
            account = getattr(credentials, "service_account_email", "the service account")
            raise GoogleSheetConfigError(
                f"The service account {account} cannot open spreadsheet {spreadsheet_id}. "
                "In Google Sheets, click Share and add that email as Editor."
            ) from exc
        self.worksheet = _open_or_create_worksheet(spreadsheet, worksheet_name)
        self._ensure_headers()
        self._format_report()

    def append_rows(self, rows: list):
        if not rows:
            logger.info("No occupancy rows to append")
            return
        logger.info("Appending %s rows to worksheet '%s'", len(rows), self.worksheet.title)
        self.worksheet.append_rows(rows, value_input_option="USER_ENTERED")

    def _ensure_headers(self):
        existing = self.worksheet.get_all_values()
        if not existing:
            logger.info("Writing header row to empty worksheet '%s'", self.worksheet.title)
            self.worksheet.append_row(SHEET_HEADERS, value_input_option="USER_ENTERED")
            return
        header = existing[0]
        if "Total Seats" not in header and "Booked Seats" in header:
            column = header.index("Booked Seats") + 1
            logger.info("Inserting Total Seats column at position %s", column)
            self.worksheet.insert_cols([["Total Seats"]], col=column)
            header = self.worksheet.row_values(1)
        if "Occupancy Percentage" not in header and "Booked Seats" in header:
            column = header.index("Booked Seats") + 2
            logger.info("Inserting Occupancy Percentage column at position %s", column)
            self.worksheet.insert_cols([["Occupancy Percentage"]], col=column)
            header = self.worksheet.row_values(1)
        if header != SHEET_HEADERS:
            logger.info("Updating header row on worksheet '%s'", self.worksheet.title)
            self.worksheet.update([SHEET_HEADERS], "A1", value_input_option="USER_ENTERED")

    def _format_report(self):
        """Freeze and label the header so months of appended rows stay readable."""
        end_column = _column_letter(len(SHEET_HEADERS))
        if self.worksheet.row_count < _HISTORY_ROWS or self.worksheet.col_count < len(SHEET_HEADERS):
            self.worksheet.resize(
                rows=max(self.worksheet.row_count, _HISTORY_ROWS),
                cols=max(self.worksheet.col_count, len(SHEET_HEADERS)),
            )
        self.worksheet.freeze(rows=1)
        self.worksheet.format(
            f"A1:{end_column}1",
            {
                "backgroundColor": {"red": 0.12, "green": 0.31, "blue": 0.47},
                "horizontalAlignment": "CENTER",
                "verticalAlignment": "MIDDLE",
                "textFormat": {
                    "bold": True,
                    "foregroundColor": {"red": 1, "green": 1, "blue": 1},
                },
            },
        )
        self.worksheet.format("E2:E5000", {"numberFormat": {"type": "NUMBER", "pattern": "0"}})
        self.worksheet.format("L2:M5000", {"numberFormat": {"type": "NUMBER", "pattern": "0"}})
        self.worksheet.format("N2:N5000", {"numberFormat": {"type": "NUMBER", "pattern": "0.0"}})
        self.worksheet.format("O2:P5000", {"numberFormat": {"type": "NUMBER", "pattern": "0"}})
        self.worksheet.set_basic_filter(f"A1:{end_column}{_HISTORY_ROWS}")


def _column_letter(index: int) -> str:
    """1-based column index to a sheet letter. 15 -> O."""
    letters = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def _project_root() -> str:
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _resolve_path(path: str) -> str:
    path = (path or "").strip()
    if not path:
        path = "config/service_account.json"
    if os.path.isabs(path):
        return path
    return os.path.join(_project_root(), path)


def _open_or_create_worksheet(spreadsheet, worksheet_name: str):
    try:
        return spreadsheet.worksheet(worksheet_name)
    except WorksheetNotFound:
        logger.info("Creating worksheet '%s'", worksheet_name)
        return spreadsheet.add_worksheet(
            title=worksheet_name,
            rows=1000,
            cols=len(SHEET_HEADERS),
        )

import time

import gspread
from oauth2client.service_account import ServiceAccountCredentials

from config import CREDS_FILE, SCOPE, SPREADSHEET_NAME

MAX_RETRIES = 5


def open_spreadsheet():
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDS_FILE, SCOPE)
    gc = gspread.authorize(creds)
    return gc.open(SPREADSHEET_NAME)


class HeaderMismatch(Exception):
    """Raised when a worksheet's header row doesn't match what's expected
    and isn't a safe, purely-additive extension of it. This never auto-wipes
    the sheet -- a structural header change (columns removed/reordered) has
    to be handled deliberately (e.g. via a one-off migration script), never
    as a side effect of running the regular pipeline.
    """


def ensure_headers(ws, headers):
    """Make sure row 1 matches `headers`, without ever wiping existing data.

    Only two cases are handled automatically:
    - The sheet has no header row yet -> write `headers`.
    - `headers` is `headers` is a strict extension of the current header
      row (same prefix, new trailing columns) -> fill in just the new
      header cells.
    Anything else (columns removed, reordered, or renamed) raises
    HeaderMismatch instead of guessing.
    """
    current_headers = ws.row_values(1) if ws.get_all_values() else []

    if current_headers == headers:
        return

    if not current_headers:
        ws.append_row(headers)
    elif len(headers) > len(current_headers) and headers[:len(current_headers)] == current_headers:
        # Purely additive change: only fill in the missing header cells,
        # never clear existing data.
        new_cols = headers[len(current_headers):]
        start_col = len(current_headers) + 1
        end_col = len(headers)
        range_name = gspread.utils.rowcol_to_a1(1, start_col) + ":" + gspread.utils.rowcol_to_a1(1, end_col)
        ws.update([new_cols], range_name)
    else:
        raise HeaderMismatch(
            f"Worksheet {ws.title!r} header {current_headers!r} does not match "
            f"expected {headers!r} and isn't a simple additive extension. "
            "Resolve this with a deliberate migration, not an automatic write."
        )


def setup_worksheet(ss, name, headers, rows=10000):
    try:
        ws = ss.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = ss.add_worksheet(title=name, rows=rows, cols=len(headers))

    ensure_headers(ws, headers)
    return ws


def chunked(items, size):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def write_batch(ws, batch_data):
    """batch_update with retries on transient Sheets API errors (e.g. 503)."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            ws.batch_update(batch_data)
            return
        except gspread.exceptions.APIError as e:
            if attempt == MAX_RETRIES:
                raise
            wait = 2 ** attempt
            print(f"    write failed ({e}); retrying in {wait}s "
                  f"(attempt {attempt}/{MAX_RETRIES})...")
            time.sleep(wait)

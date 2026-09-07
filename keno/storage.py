"""Read/write the Keno draw archive from a Google Sheet.

Auth is a Google Cloud service account, configured via Streamlit secrets
(`.streamlit/secrets.toml` locally, or the app's Secrets settings on
Community Cloud). `st.secrets` reads that file whether or not a Streamlit
server is actually running, so this works from both the CLI and the app.
See README.md for how to set up the service account and share the sheet.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from functools import lru_cache

import gspread
import pandas as pd
import streamlit as st
from google.oauth2.service_account import Credentials

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
WORKSHEET_TITLE = "draws"
HEADERS = ["id", "drawTime", "win", "bulls_eye"]


@lru_cache(maxsize=1)
def _worksheet() -> gspread.Worksheet:
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]), scopes=SCOPES
    )
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(st.secrets["gsheets"]["spreadsheet_id"])

    try:
        ws = spreadsheet.worksheet(WORKSHEET_TITLE)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=WORKSHEET_TITLE, rows=1000, cols=len(HEADERS))
        ws.append_row(HEADERS)

    if not ws.get_all_values():
        ws.append_row(HEADERS)

    return ws


def location_label() -> str:
    """Human-readable description of where the archive lives, for messages."""
    return f"Google Sheet '{st.secrets['gsheets']['spreadsheet_id']}' (worksheet '{WORKSHEET_TITLE}')"


def _read_all() -> pd.DataFrame:
    records = _worksheet().get_all_records()
    return pd.DataFrame(records, columns=HEADERS) if records else pd.DataFrame(columns=HEADERS)


def save_draws(new_df: pd.DataFrame) -> pd.DataFrame:
    """Append any rows in new_df not already present (by id) to the sheet."""
    existing = _read_all()
    existing_ids_set = set(existing["id"].astype(str)) if not existing.empty else set()

    to_add = new_df.copy()
    to_add["id"] = to_add["id"].astype(str)
    to_add = to_add[~to_add["id"].isin(existing_ids_set)]

    if not to_add.empty:
        _worksheet().append_rows(to_add[HEADERS].values.tolist(), value_input_option="RAW")

    return pd.concat([existing, to_add], ignore_index=True) if not existing.empty else to_add


def load_draws() -> pd.DataFrame:
    """Load the archive with the win column parsed back into lists of ints."""
    df = _read_all()
    if not df.empty:
        df["win"] = df["win"].apply(json.loads)
    return df


def collected_days() -> set[date]:
    """Which calendar days already have at least one draw archived."""
    df = _read_all()
    if df.empty:
        return set()
    return {datetime.fromisoformat(dt).date() for dt in df["drawTime"].dropna()}


def existing_ids(day: date) -> set[str]:
    """Run ids already archived for a given calendar day."""
    df = _read_all()
    if df.empty:
        return set()
    on_day = df["drawTime"].apply(lambda dt: datetime.fromisoformat(dt).date() == day)
    return set(df.loc[on_day, "id"].astype(str))

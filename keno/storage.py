"""Read/write the local Keno draw archive as a single deduplicated CSV."""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

import pandas as pd

DEFAULT_PATH = Path("data/draws.csv")


def save_draws(new_df: pd.DataFrame, path: Path = DEFAULT_PATH) -> pd.DataFrame:
    """Merge new_df into the archive at path, deduplicating by draw id."""
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = pd.read_csv(path)
        combined = pd.concat([existing, new_df], ignore_index=True)
    else:
        combined = new_df

    combined["id"] = combined["id"].astype(str)
    combined.drop_duplicates(subset=["id"], keep="last", inplace=True)
    combined.sort_values("drawTime", inplace=True)
    combined.to_csv(path, index=False)
    return combined


def load_draws(path: Path = DEFAULT_PATH) -> pd.DataFrame:
    """Load the archive with the win column parsed back into lists of ints."""
    df = pd.read_csv(path)
    df["win"] = df["win"].apply(json.loads)
    return df


def collected_days(path: Path = DEFAULT_PATH) -> set[date]:
    """Which calendar days already have at least one draw archived."""
    if not path.exists():
        return set()
    df = pd.read_csv(path, usecols=["drawTime"])
    if df.empty:
        return set()
    return {datetime.fromisoformat(dt).date() for dt in df["drawTime"].dropna()}


def existing_ids(day: date, path: Path = DEFAULT_PATH) -> set[str]:
    """Run ids already archived for a given calendar day."""
    if not path.exists():
        return set()
    df = pd.read_csv(path, usecols=["id", "drawTime"])
    if df.empty:
        return set()
    on_day = df["drawTime"].apply(lambda dt: datetime.fromisoformat(dt).date() == day)
    return set(df.loc[on_day, "id"].astype(str))

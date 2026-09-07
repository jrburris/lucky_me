"""Fetch historical Georgia Lottery Keno draws directly from their JSON API.

This replaces the older Selenium/BeautifulSoup scrapers used in earlier
prototypes: the Georgia Lottery site exposes the same draw data through a
plain JSON endpoint, so no browser automation is needed.
"""
from __future__ import annotations

import json
from datetime import date, datetime

import pandas as pd
import requests

GAME_NAME = "KENO!"  # esaGameName used by galottery.com's own search UI
DRAWS_URL = "https://www.galottery.com/api/v2/draw-games/draws/page"
SECONDS_PER_DAY = 86_400
PAGE_SIZE = 100
USER_AGENT = "Mozilla/5.0"


def _day_bounds_ms(day: date) -> tuple[int, int]:
    start = datetime(day.year, day.month, day.day)
    epoch_start = int(start.timestamp() * 1000)
    epoch_end = epoch_start + (SECONDS_PER_DAY * 1000 - 1000)
    return epoch_start, epoch_end


def _parse_primary(primary: list[str]) -> tuple[list[int], int | None]:
    """Split a draw's primary array into the 20 win numbers and the bullseye.

    The API mixes plain numbers with tagged entries like "M-01" (multiplier)
    and "BE-56" (bullseye) in the same list.
    """
    win = [int(n) for n in primary if n.isdigit()]
    bulls_eye = next(
        (int(n.split("-", 1)[1]) for n in primary if n.startswith("BE-")), None
    )
    return win, bulls_eye


def _fetch_day(session: requests.Session, day: date) -> list[dict]:
    epoch_start, epoch_end = _day_bounds_ms(day)
    rows = []
    page = 0

    while True:
        params = {
            "game-names": GAME_NAME,
            "date-from": epoch_start,
            "date-to": epoch_end,
            "status": "CLOSED",
            "order": "desc",
            "size": PAGE_SIZE,
            "page": page,
        }
        resp = session.get(DRAWS_URL, params=params, headers={"User-Agent": USER_AGENT})
        resp.raise_for_status()
        payload = json.loads(resp.text)
        draws = payload.get("draws", [])

        for draw in draws:
            results = draw.get("results") or []
            if not results:
                continue
            primary = results[0].get("primary") or []
            win, bulls_eye = _parse_primary(primary)
            if not win:
                continue
            draw_time_ms = draw.get("drawTime")
            rows.append(
                {
                    "id": draw["id"],
                    "drawTime": datetime.fromtimestamp(draw_time_ms / 1000).isoformat()
                    if draw_time_ms
                    else None,
                    "win": win,
                    "bulls_eye": bulls_eye,
                }
            )

        if len(draws) < PAGE_SIZE or payload.get("nextItems", 0) == 0:
            break
        page += 1

    return rows


def fetch_day(day: date) -> pd.DataFrame:
    """Fetch all Keno draws for a single calendar day."""
    with requests.Session() as session:
        rows = _fetch_day(session, day)

    df = pd.DataFrame(rows, columns=["id", "drawTime", "win", "bulls_eye"])
    df["win"] = df["win"].apply(json.dumps)
    return df

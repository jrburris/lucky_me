"""Frequency analysis and pick backtesting over a Keno draw archive."""
from __future__ import annotations

import math
from collections import Counter
from datetime import datetime
from itertools import combinations

import pandas as pd

from keno import payouts

NUMBER_RANGE = range(1, 81)


def number_frequency(df: pd.DataFrame) -> pd.Series:
    """Count how often each number 1-80 appeared across all draws in df."""
    counts = Counter()
    for win in df["win"]:
        counts.update(win)
    return pd.Series({n: counts.get(n, 0) for n in NUMBER_RANGE}, name="count")


def bullseye_frequency(df: pd.DataFrame) -> pd.Series:
    """Count how often each number 1-80 was the bullseye across all draws in df."""
    bulls_eye = df["bulls_eye"].dropna().astype(int)
    counts = bulls_eye.value_counts()
    return pd.Series({n: int(counts.get(n, 0)) for n in NUMBER_RANGE}, name="count")


def most_frequent(freq: pd.Series, n: int = 6) -> list[int]:
    return freq.sort_values(ascending=False).head(n).index.tolist()


def least_frequent(freq: pd.Series, n: int = 6) -> list[int]:
    return freq.sort_values(ascending=True).head(n).index.tolist()


def numbers_missing(df: pd.DataFrame, lookback: int = 10) -> list[int]:
    """Numbers that have not appeared in the most recent `lookback` draws."""
    recent = df.sort_values("drawTime").tail(lookback)
    freq = number_frequency(recent)
    return freq[freq == 0].index.tolist()


def number_zscores(freq: pd.Series, picks_per_draw: int = 20) -> pd.Series:
    """Per-number z-score against the count expected from pure random draws.

    `picks_per_draw` is how many of the 80 numbers each draw selects (20 for
    the main numbers, 1 for the bullseye) — it's the only thing that differs
    between the two, since expected count per number is always
    freq.sum() / 80 regardless of picks_per_draw.
    """
    total = freq.sum()
    expected = total / 80
    p = picks_per_draw / 80
    variance = expected * (1 - p)
    std = math.sqrt(variance) if variance > 0 else 1.0
    return (freq - expected) / std


def frequency_significance(freq: pd.Series, picks_per_draw: int = 20) -> dict:
    """Chi-square goodness-of-fit against uniform random draws, in plain terms.

    Rather than pull in scipy for a single test, this uses the standard
    large-df normal approximation for the chi-square distribution
    (mean = dof, std = sqrt(2*dof)) to give a rough verdict: a chi-square
    statistic within about 2 standard deviations of its expected value (the
    degrees of freedom) is what pure randomness looks like.
    """
    expected = freq.sum() / 80
    dof = len(freq) - 1
    chi2 = float(((freq - expected) ** 2 / expected).sum())
    std = math.sqrt(2 * dof)
    z = (chi2 - dof) / std
    verdict = "notably non-uniform" if z > 2 else "consistent with random draws"
    return {"chi2": chi2, "dof": dof, "expected_per_number": expected, "z": z, "verdict": verdict}


def hourly_draw_counts(df: pd.DataFrame) -> pd.Series:
    """Number of draws by hour of day (0-23) across all days in df."""
    hours = pd.to_datetime(df["drawTime"]).dt.hour
    return hours.value_counts().reindex(range(24), fill_value=0).sort_index()


def filter_since(df: pd.DataFrame, cutoff: datetime | None) -> pd.DataFrame:
    """Restrict to draws at or after cutoff. Returns df unchanged if cutoff is None."""
    if cutoff is None:
        return df
    return df[pd.to_datetime(df["drawTime"]) >= cutoff]


def common_combinations(
    df: pd.DataFrame, size: int, top_n: int = 10
) -> list[tuple[tuple[int, ...], int, str, float]]:
    """Which groups of `size` numbers appeared together in the same draw most often.

    Returns (combo, count, last_seen, hours_since_seen) tuples, sorted by
    count descending and then hours_since_seen descending. last_seen is the
    drawTime of the most recent draw containing that combo and
    hours_since_seen is how long ago that was relative to now.

    Cost grows combinatorially with both `size` and the number of draws
    (each draw contributes C(20, size) combinations), so this can get slow
    for large archives at size=7 or above.
    """
    counts: Counter[tuple[int, ...]] = Counter()
    last_seen: dict[tuple[int, ...], str] = {}

    ordered = df.sort_values("drawTime")
    for win, draw_time in zip(ordered["win"], ordered["drawTime"]):
        for combo in combinations(sorted(win), size):
            counts[combo] += 1
            last_seen[combo] = draw_time

    now = datetime.now()
    rows = [
        (
            combo,
            count,
            last_seen[combo],
            round((now - datetime.fromisoformat(last_seen[combo])).total_seconds() / 3600, 1),
        )
        for combo, count in counts.items()
    ]
    rows.sort(key=lambda row: (row[1], row[3]), reverse=True)
    return rows[:top_n]


def backtest_pick(
    df: pd.DataFrame,
    picks: list[int],
    wager: float = 1.0,
    payout_table: dict | None = None,
) -> dict:
    """Replay every draw in df as if `picks` had been played each time.

    Returns match-count distribution, total payout, and net result assuming
    a flat `wager` per game.
    """
    pick_set = set(picks)
    match_counts: Counter[int] = Counter()
    total_payout = 0.0

    for win in df["win"]:
        matches = len(pick_set & set(win))
        match_counts[matches] += 1
        total_payout += payouts.payout(len(pick_set), matches, payout_table) * wager

    games = len(df)
    total_cost = games * wager

    return {
        "picks": sorted(pick_set),
        "games": games,
        "match_distribution": dict(sorted(match_counts.items())),
        "total_wagered": total_cost,
        "total_payout": total_payout,
        "net": total_payout - total_cost,
    }

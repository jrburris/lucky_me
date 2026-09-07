"""Frequency analysis and pick backtesting over a Keno draw archive."""
from __future__ import annotations

from collections import Counter
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


def most_frequent(freq: pd.Series, n: int = 6) -> list[int]:
    return freq.sort_values(ascending=False).head(n).index.tolist()


def least_frequent(freq: pd.Series, n: int = 6) -> list[int]:
    return freq.sort_values(ascending=True).head(n).index.tolist()


def numbers_missing(df: pd.DataFrame, lookback: int = 10) -> list[int]:
    """Numbers that have not appeared in the most recent `lookback` draws."""
    recent = df.sort_values("drawTime").tail(lookback)
    freq = number_frequency(recent)
    return freq[freq == 0].index.tolist()


def common_combinations(df: pd.DataFrame, size: int, top_n: int = 10) -> list[tuple[tuple[int, ...], int]]:
    """Which groups of `size` numbers appeared together in the same draw most often.

    Cost grows combinatorially with both `size` and the number of draws
    (each draw contributes C(20, size) combinations), so this can get slow
    for large archives at size=7 or above.
    """
    counts: Counter[tuple[int, ...]] = Counter()
    for win in df["win"]:
        counts.update(combinations(sorted(win), size))
    return counts.most_common(top_n)


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

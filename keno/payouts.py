"""Keno payout tables.

DEFAULT_TABLE below is carried over from an earlier prototype's Massachusetts
Keno rates for $1 wagers. Georgia Lottery's actual payout table was never
captured in any prior version of this project - swap in the correct table
for your game before relying on payout() for real numbers.
"""
from __future__ import annotations

# {spots_picked: {matches: payout}}
DEFAULT_TABLE: dict[int, dict[int, float]] = {
    1: {1: 2.5},
    2: {1: 1.0, 2: 5.0},
    3: {2: 2.5, 3: 25.0},
    4: {2: 1.0, 3: 4.0, 4: 100.0},
    5: {3: 2.0, 4: 20.0, 5: 450.0},
}


def payout(spots: int, matches: int, table: dict | None = None) -> float:
    table = table or DEFAULT_TABLE
    return table.get(spots, {}).get(matches, 0.0)

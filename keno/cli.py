"""Command-line entry point: fetch, analyze, and backtest Georgia Keno draws.

Examples:
    python -m keno.cli fetch --date 2026-08-01
    python -m keno.cli analyze --top 6 --lookback 10
    python -m keno.cli backtest --picks 7 23 41 55 68
"""
from __future__ import annotations

import argparse
from datetime import datetime

from keno import analysis, collector, storage


def _date(value: str) -> datetime.date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def cmd_fetch(args: argparse.Namespace) -> None:
    already_have = storage.existing_ids(args.date)
    if already_have:
        print(f"{args.date.isoformat()} already has {len(already_have)} run(s) archived — skipping.")
    else:
        df = collector.fetch_day(args.date)
        if df.empty:
            print(f"No draws returned for {args.date.isoformat()}.")
        else:
            combined = storage.save_draws(df)
            print(
                f"Added {len(df)} run(s) for {args.date.isoformat()}. "
                f"Archive now has {len(combined)} draws saved to {storage.location_label()}"
            )

    pruned = storage.prune_older_than()
    if pruned:
        print(f"Pruned {pruned} draw(s) older than {storage.DEFAULT_RETENTION_DAYS} days.")


def cmd_analyze(args: argparse.Namespace) -> None:
    df = storage.load_draws()
    freq = analysis.number_frequency(df)

    print(f"Loaded {len(df)} draws")
    print(f"Most frequent {args.top}: {analysis.most_frequent(freq, args.top)}")
    print(f"Least frequent {args.top}: {analysis.least_frequent(freq, args.top)}")
    print(
        f"Not drawn in last {args.lookback} draws: "
        f"{analysis.numbers_missing(df, args.lookback)}"
    )

    if args.combos:
        for size in (4, 7):
            print(f"\nComputing most common {size}-number combinations "
                  f"(this can take a while for large archives)...")
            for combo, count, last_seen, hours_since in analysis.common_combinations(df, size, args.top):
                print(f"  {combo}: {count} (last seen {last_seen}, {hours_since}h ago)")


def cmd_backtest(args: argparse.Namespace) -> None:
    df = storage.load_draws()
    result = analysis.backtest_pick(df, args.picks, wager=args.wager)
    for key, value in result.items():
        print(f"{key}: {value}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    fetch_parser = subparsers.add_parser("fetch", help="Collect a day of draws from the Georgia Lottery API")
    fetch_parser.add_argument("--date", type=_date, required=True, help="YYYY-MM-DD")
    fetch_parser.set_defaults(func=cmd_fetch)

    analyze_parser = subparsers.add_parser("analyze", help="Summarize frequency across the archive")
    analyze_parser.add_argument("--top", type=int, default=6)
    analyze_parser.add_argument("--lookback", type=int, default=10)
    analyze_parser.add_argument(
        "--no-combos", dest="combos", action="store_false",
        help="Skip the 4- and 7-number combination breakdown (slow on large archives)",
    )
    analyze_parser.set_defaults(func=cmd_analyze, combos=True)

    backtest_parser = subparsers.add_parser("backtest", help="Replay a fixed pick against the archive")
    backtest_parser.add_argument("--picks", type=int, nargs="+", required=True)
    backtest_parser.add_argument("--wager", type=float, default=1.0)
    backtest_parser.set_defaults(func=cmd_backtest)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

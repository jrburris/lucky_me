"""Streamlit UI for the keno toolkit: view collected draws and run the
fetch / analyze / backtest functions from the keno package."""
from __future__ import annotations

import json
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from keno import analysis, collector, payouts, storage

st.set_page_config(page_title="Keno", layout="wide")
st.title("Keno")

if "gcp_service_account" not in st.secrets or "gsheets" not in st.secrets:
    st.error(
        "Google Sheets credentials are not configured. This app needs "
        "`[gcp_service_account]` and `[gsheets]` sections in its secrets — "
        "locally that's `.streamlit/secrets.toml`; on Streamlit Community "
        "Cloud it's the app's **Settings → Secrets** panel. See README.md "
        "for the exact format."
    )
    st.stop()


@st.cache_data
def _load_draws():
    df = storage.load_draws()
    return df if not df.empty else None


@st.cache_data
def _common_combinations(size: int, top_n: int):
    return analysis.common_combinations(_load_draws(), size, top_n)


def _refresh():
    st.cache_data.clear()


def _fetch_and_save(day: date) -> tuple[int, int]:
    """Fetch a single day and save only the runs (by id) not already archived.

    A fully-collected day adds nothing; a partial day tops up just the
    missing ids. Returns (added, already_had).
    """
    already_have = storage.existing_ids(day)
    new_df = collector.fetch_day(day)
    missing = new_df[~new_df["id"].isin(already_have)]
    if not missing.empty:
        storage.save_draws(new_df)
    return len(missing), len(already_have)


with st.sidebar:
    st.header("Archive")
    _sidebar_df = _load_draws()
    if _sidebar_df is None:
        st.caption("No draws collected yet.")
    else:
        days = sorted(storage.collected_days())
        st.metric("Total draws", len(_sidebar_df))
        st.metric("Days collected", len(days))
        if days:
            st.caption(f"{days[0].isoformat()} → {days[-1].isoformat()}")


tab_data, tab_analyze, tab_backtest = st.tabs(["Data", "Analyze", "Backtest"])

with tab_data:
    st.subheader("Fetch")
    st.caption(
        f"Pulls draws from the Georgia Lottery API into the Google Sheet archive. "
        f"Only runs (by id) not already archived are added — a fully-collected day "
        f"makes no changes, a partial day tops up just what's missing. Data older "
        f"than {storage.DEFAULT_RETENTION_DAYS} days is purged after every fetch."
    )
    mode = st.radio("Fetch", ["Today", "Date range"], horizontal=True, label_visibility="collapsed")

    if mode == "Today":
        today = date.today()
        already_have = storage.existing_ids(today)
        if already_have:
            st.info(f"{len(already_have)} run(s) already archived for {today.isoformat()}.")

        if st.button("Fetch today's draws", type="primary"):
            with st.spinner(f"Fetching {today.isoformat()}..."):
                try:
                    added, had = _fetch_and_save(today)
                    if added == 0 and had:
                        st.success(f"{today.isoformat()} is already fully collected — nothing to fetch.")
                    else:
                        st.success(f"Added {added} run(s) for {today.isoformat()}.")

                    pruned = storage.prune_older_than()
                    if pruned:
                        st.info(f"Pruned {pruned} draw(s) older than {storage.DEFAULT_RETENTION_DAYS} days.")

                    _refresh()
                except Exception as exc:
                    st.error(f"Fetch failed: {exc}")

    else:
        c1, c2 = st.columns(2)
        start = c1.date_input("Start date", value=date.today())
        end = c2.date_input("End date", value=date.today())
        st.caption("Fetches one day at a time — a wide range can take a while.")

        if st.button("Fetch range", type="primary", disabled=start > end):
            if start > end:
                st.error("Start date must be on or before end date.")
            else:
                days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
                progress = st.progress(0.0)
                total_added = 0
                try:
                    for i, day in enumerate(days, start=1):
                        progress.progress(i / len(days), text=f"Fetching {day.isoformat()} ({i}/{len(days)})...")
                        added, _ = _fetch_and_save(day)
                        total_added += added
                    progress.empty()
                    st.success(f"Added {total_added} new run(s) across {len(days)} day(s).")

                    pruned = storage.prune_older_than()
                    if pruned:
                        st.info(f"Pruned {pruned} draw(s) older than {storage.DEFAULT_RETENTION_DAYS} days.")

                    _refresh()
                except Exception as exc:
                    st.error(f"Fetch failed: {exc}")

    st.divider()

    df = _load_draws()
    if df is None:
        st.info("No draws collected yet — use Fetch above.")
    else:
        col1, col2, col3 = st.columns([1, 1, 1])
        col1.metric("Draws", len(df))
        col2.metric("Date range", f"{df['drawTime'].min()} — {df['drawTime'].max()}")
        export_df = df.assign(win=df["win"].apply(json.dumps))
        col3.download_button(
            "Download archive CSV", export_df.to_csv(index=False), file_name="draws.csv", mime="text/csv"
        )

        summary = (
            df.assign(day=df["drawTime"].str.slice(0, 10))
            .groupby("day")
            .size()
            .reset_index(name="draws")
            .sort_values("day", ascending=False)
            .reset_index(drop=True)
        )
        st.dataframe(summary, use_container_width=True)

with tab_analyze:
    df = _load_draws()
    if df is None:
        st.info("No draws collected yet. Use the Fetch section on the Data tab to pull some.")
    else:
        c1, c2 = st.columns(2)
        top_n = c1.slider("Top N", min_value=1, max_value=20, value=6)
        if len(df) < 2:
            lookback = len(df)
            c2.caption(f"Lookback draws: {lookback} (need at least 2 draws for a slider)")
        else:
            lookback = c2.slider(
                "Lookback draws", min_value=1, max_value=min(50, len(df)), value=min(10, len(df))
            )

        freq = analysis.number_frequency(df)

        st.subheader("Number frequency")
        st.bar_chart(freq)

        st.caption("Positional heatmap (1-80, left to right, top to bottom)")
        grid = pd.DataFrame(
            freq.values.reshape(8, 10),
            index=[f"{r * 10 + 1}-{r * 10 + 10}" for r in range(8)],
            columns=[str(c + 1) for c in range(10)],
        )
        st.dataframe(
            grid.style.background_gradient(cmap="YlOrRd", axis=None),
            use_container_width=True,
        )

        c1, c2, c3 = st.columns(3)
        c1.write("**Most frequent**")
        c1.write(analysis.most_frequent(freq, top_n))
        c2.write("**Least frequent**")
        c2.write(analysis.least_frequent(freq, top_n))
        c3.write(f"**Not drawn in last {lookback}**")
        c3.write(analysis.numbers_missing(df, lookback))

        st.subheader("Common combinations")
        st.caption(
            "Groups of numbers that appeared together in the same draw most often. "
            "The 7-number search is combinatorially heavier and can take a while on "
            "large archives."
        )
        combo_top_n = st.slider("Combos to show", min_value=1, max_value=20, value=10)

        if st.button("Find common combinations"):
            c1, c2 = st.columns(2)
            with st.spinner("Counting 4-number combinations..."):
                combos4 = _common_combinations(4, combo_top_n)
            c1.write("**Most common 4-number combos**")
            c1.table(pd.DataFrame(combos4, columns=["numbers", "count", "last seen", "hours ago"]))

            with st.spinner("Counting 7-number combinations (slower)..."):
                combos7 = _common_combinations(7, combo_top_n)
            c2.write("**Most common 7-number combos**")
            c2.table(pd.DataFrame(combos7, columns=["numbers", "count", "last seen", "hours ago"]))

with tab_backtest:
    df = _load_draws()
    if df is None:
        st.info("No draws collected yet. Use the Fetch section on the Data tab to pull some.")
    else:
        picks = st.multiselect(
            "Numbers to play (1-80)", options=list(range(1, 81)), max_selections=10
        )
        wager = st.number_input("Wager per game ($)", min_value=0.0, value=1.0, step=0.5)

        st.caption(
            "Payout table is a placeholder carried over from an earlier prototype "
            "(Massachusetts rates) — swap in Georgia's real table in keno/payouts.py "
            "before trusting dollar figures."
        )

        if st.button("Run backtest", type="primary", disabled=not picks):
            result = analysis.backtest_pick(df, picks, wager=wager)

            c1, c2, c3 = st.columns(3)
            c1.metric("Games", result["games"])
            c2.metric("Total wagered", f"${result['total_wagered']:.2f}")
            c3.metric("Net", f"${result['net']:.2f}", delta=f"{result['net']:.2f}")

            st.write("**Match distribution**")
            st.bar_chart(result["match_distribution"])

"""Streamlit UI for the keno toolkit: view collected draws and run the
fetch / analyze / backtest functions from the keno package."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from keno import analysis, collector, payouts, storage

st.set_page_config(page_title="Keno", layout="wide")
st.title("Keno")


@st.cache_data
def _load_draws():
    if not storage.DEFAULT_PATH.exists():
        return None
    df = storage.load_draws()
    return df if not df.empty else None


@st.cache_data
def _common_combinations(size: int, top_n: int):
    return analysis.common_combinations(_load_draws(), size, top_n)


def _refresh():
    st.cache_data.clear()


tab_data, tab_fetch, tab_analyze, tab_backtest = st.tabs(
    ["Data", "Fetch", "Analyze", "Backtest"]
)

with tab_data:
    df = _load_draws()
    if df is None:
        st.info("No draws collected yet. Use the Fetch tab to pull some.")
    else:
        col1, col2 = st.columns(2)
        col1.metric("Draws", len(df))
        col2.metric("Date range", f"{df['drawTime'].min()} — {df['drawTime'].max()}")
        st.dataframe(df, use_container_width=True, height=500)

with tab_fetch:
    st.write("Pull a day of draws from the Georgia Lottery API and add them to the local archive.")
    day = st.date_input("Date")
    already_have = storage.existing_ids(day)

    if already_have:
        st.info(f"{len(already_have)} run(s) already archived for {day.isoformat()}.")

    if st.button("Fetch draws", type="primary"):
        with st.spinner(f"Fetching {day.isoformat()}..."):
            try:
                new_df = collector.fetch_day(day)
                missing = new_df[~new_df["id"].isin(already_have)]

                if already_have and missing.empty:
                    st.success(f"{day.isoformat()} is already fully collected — nothing to fetch.")
                else:
                    combined = storage.save_draws(new_df)
                    _refresh()
                    st.success(
                        f"Added {len(missing)} new run(s). Archive now has {len(combined)} draws."
                    )
            except Exception as exc:
                st.error(f"Fetch failed: {exc}")

with tab_analyze:
    df = _load_draws()
    if df is None:
        st.info("No draws collected yet. Use the Fetch tab to pull some.")
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
        st.info("No draws collected yet. Use the Fetch tab to pull some.")
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

# lucky_me

Georgia Lottery Keno data collection and analysis.

DISCLAIMER: this project does not promote gambling of any kind. It's a study
project looking at Keno draw frequency and payout math — the odds are against
the player by design, and nothing here changes that.

## Origin

This consolidates four earlier prototype projects (`Keno-Analyzer`,
`keno`, `pi_keno`, and assorted notebooks) into one package:

- **Data collection** (`keno/collector.py`) uses the Georgia Lottery's
  internal JSON API directly, rather than driving a browser with Selenium
  as the older prototypes did. It's faster and doesn't break when the page
  markup changes.
- **Storage** (`keno/storage.py`) maintains a single deduplicated CSV
  archive of draws instead of one file per day.
- **Analysis** (`keno/analysis.py`) carries forward the frequency-counting
  and pick-backtesting logic from the old `analyzeKenoData.py` /
  `keno_nb.py` scripts, cleaned up and made reusable.
- **Payouts** (`keno/payouts.py`) carries forward the payout-table structure
  from the old `betCalculator.py`. The actual table values are from a
  Massachusetts Keno prototype and are a placeholder — swap in Georgia's
  real payout table before trusting any dollar figures.

## Setup

```
pip install -r requirements.txt
```

## Usage

### CLI

```
# Collect one day of draws into data/draws.csv (skipped if already collected)
python -m keno.cli fetch --date 2026-08-01

# Summarize frequency across the archive
python -m keno.cli analyze --top 6 --lookback 10

# Replay a fixed pick against every draw collected so far
python -m keno.cli backtest --picks 7 23 41 55 68
```

### Web UI

```
streamlit run app.py
```

Opens a browser tab with tabs for viewing the collected archive, fetching a
day of draws at a time (already-collected days are skipped), running
frequency analysis, and backtesting a pick — all driven by the same `keno`
package functions the CLI uses.

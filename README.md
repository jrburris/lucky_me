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
- **Storage** (`keno/storage.py`) keeps a single deduplicated archive of
  draws in a Google Sheet, so the data survives redeploys on Streamlit
  Community Cloud's ephemeral filesystem instead of one file per day.
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

The draw archive lives in a Google Sheet, so before running anything you
need a Google Cloud service account and a sheet it can write to:

1. In the [Google Cloud Console](https://console.cloud.google.com/), create
   (or reuse) a project and enable the **Google Sheets API** for it.
2. Under **IAM & Admin → Service Accounts**, create a service account, then
   add a JSON key for it and download it. This is the credential the app
   authenticates with — treat it like a password.
3. Create a Google Sheet (any name) to hold the archive, and share it with
   the service account's email address (looks like
   `something@your-project.iam.gserviceaccount.com`, found in the JSON key
   or the service account's details page) with **Editor** access. The app
   creates a `draws` worksheet inside it automatically on first use.
4. Copy the sheet's ID out of its URL — the long string between `/d/` and
   `/edit` in `https://docs.google.com/spreadsheets/d/<ID>/edit`.
5. Create `.streamlit/secrets.toml` (gitignored — never commit this file)
   with the service account JSON fields and the sheet ID:

   ```toml
   [gcp_service_account]
   type = "service_account"
   project_id = "..."
   private_key_id = "..."
   private_key = "-----BEGIN PRIVATE KEY-----\n...\n-----END PRIVATE KEY-----\n"
   client_email = "...@....iam.gserviceaccount.com"
   client_id = "..."
   auth_uri = "https://accounts.google.com/o/oauth2/auth"
   token_uri = "https://oauth2.googleapis.com/token"
   auth_provider_x509_cert_url = "https://www.googleapis.com/oauth2/v1/certs"
   client_x509_cert_url = "..."

   [gsheets]
   spreadsheet_id = "your-sheet-id-here"
   ```

   Every field above (except `spreadsheet_id`) is copied directly from the
   downloaded JSON key. This same file is read by both `streamlit run app.py`
   and the CLI — no separate config needed for each.

## Usage

### CLI

```
# Collect one day of draws into the Google Sheet (skipped if already collected)
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

## Deploying to Streamlit Community Cloud

The repo is already set up to deploy as-is: `app.py` at the root and
`requirements.txt` listing everything it needs.

### First deploy

1. Push the branch you want live to GitHub (`origin` is
   `github.com/jrburris/lucky_me`).
2. Go to [share.streamlit.io](https://share.streamlit.io) and sign in with
   GitHub.
3. Click **New app**, pick the `lucky_me` repo and branch, and set the main
   file path to `app.py`.
4. Before or after creating the app, open its **Settings → Secrets** and
   paste in the same content as your local `.streamlit/secrets.toml` (see
   Setup above). Community Cloud injects it as `st.secrets`, same as locally.
5. Click **Deploy**. Streamlit installs `requirements.txt` and starts the app.

### Redeploying

- **Push to the deployed branch** — Community Cloud watches it and
  auto-redeploys on every push. No manual step needed for code changes.
- **Force a redeploy without a code change** (e.g. to pick up a dependency
  bump or clear a stuck cache) — open the app on share.streamlit.io, use the
  **⋮** menu → **Reboot app**.
- **Changed `requirements.txt`** — a reboot (or the next push-triggered
  redeploy) reinstalls dependencies automatically.

### Data persistence

Community Cloud's local filesystem is ephemeral and wipes on every reboot
or redeploy, but that no longer matters here: the archive lives in the
Google Sheet configured via secrets, not on disk, so it survives reboots,
redeploys, and even switching which machine is running the app.

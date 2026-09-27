# NSE Candlestick Pattern Detector

Educational tool: detects candlestick patterns on Indian stocks using rule-based
logic (not LLM guessing), shows them on an interactive chart, and optionally
explains the pattern in plain English using Gemini.

## Setup

```bash
pip install -r requirements.txt
```

Optional (for AI explanations): get a free key from https://aistudio.google.com/
and set it as an environment variable:

```bash
export GEMINI_API_KEY=your_key_here      # Mac/Linux
setx GEMINI_API_KEY "your_key_here"      # Windows
```

## Run the UI

```bash
streamlit run app.py
```

This opens a browser window. Enter an NSE symbol like `RELIANCE.NS`, `TCS.NS`,
`INFY.NS`, `SBIN.NS` (NSE symbols always need the `.NS` suffix; BSE uses `.BO`).

## Run the console demo (no internet/API key needed)

```bash
python3 test_console_demo.py
```

This runs the pattern detection on generated sample data so you can see the
output format without needing live data or an API key.

## How it works

1. `fetcher/get_ohlc.py` — pulls real OHLC data via yfinance
2. `patterns/detect.py` — rule-based candlestick pattern detection (pure pandas)
3. `indicators/confirm.py` — RSI, volume, and trend confirmation scoring
4. `llm/explain.py` — sends the *already detected* pattern to Gemini for a
   plain-English explanation (Gemini never decides the pattern itself)
5. `app.py` — Streamlit UI tying it all together with an interactive chart

## Hosting on GitHub

**Important:** GitHub Actions cannot host the live Streamlit UI — it only runs
temporary automated jobs. Use both pieces below for the full setup.

### 1. Live interactive UI → Streamlit Community Cloud (free)

1. Push this whole folder to a new GitHub repo (public or private)
2. Go to https://share.streamlit.io and sign in with GitHub
3. Click "New app", pick your repo, and set the main file to `app.py`
4. Add your `GEMINI_API_KEY` under the app's "Secrets" settings (same format as `.env`)
5. Deploy — you get a live URL you can open anytime, no server to manage

### 2. Automated daily watchlist scan → GitHub Actions

This repo already includes `.github/workflows/daily-scan.yml`. Once pushed to
GitHub, it will:
- Run automatically every weekday at 4:30 PM IST (just after NSE market close)
- Scan the symbols in `scan_watchlist.py`'s `WATCHLIST` list
- Write results to `reports/latest.md` and commit them back to the repo

To trigger it manually: go to your repo's **Actions** tab → "Daily Candlestick
Pattern Scan" → **Run workflow**.

To change which stocks it checks, edit the `WATCHLIST` list at the top of
`scan_watchlist.py`.

No API key is needed for this scan (it's rule-based pattern detection only,
no Gemini call) — so it works for free with just the GitHub Actions default
setup.

## Disclaimer

This is a learning tool. Nothing it outputs is financial advice or a trading
signal. Always confirm with your own study and risk management.

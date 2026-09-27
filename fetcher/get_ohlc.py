"""
Fetches OHLC data for Indian stocks via yfinance.
NSE symbols need a '.NS' suffix, BSE symbols need '.BO'.
Examples: RELIANCE.NS, TCS.NS, INFY.NS, SBIN.NS
"""
import yfinance as yf
import pandas as pd
import time
import logging

logger = logging.getLogger(__name__)


def fetch_ohlc(symbol: str, period: str = "3mo", interval: str = "1d", retries: int = 3) -> pd.DataFrame:
    """
    period: '1mo','3mo','6mo','1y','2y' etc.
    interval: '1d','1h','15m' (intraday intervals only work for shorter periods)
    retries: number of retry attempts on transient failures
    """
    last_err = None
    for attempt in range(1, retries + 1):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period, interval=interval)
            break
        except Exception as e:
            last_err = e
            logger.warning("Attempt %d/%d for %s failed: %s", attempt, retries, symbol, e)
            if attempt < retries:
                time.sleep(2 * attempt)  # simple exponential backoff
    else:
        raise ConnectionError(f"Failed to fetch {symbol} after {retries} attempts: {last_err}")

    if df.empty:
        raise ValueError(f"No data returned for {symbol}. Check the symbol (needs .NS or .BO suffix).")

    df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
    df.index.name = "Date"

    # Normalize timezone — yfinance returns tz-aware datetimes for intraday
    # but tz-naive for daily. Stripping tz prevents downstream mismatches.
    if df.index.tz is not None:
        df.index = df.index.tz_localize(None)

    return df

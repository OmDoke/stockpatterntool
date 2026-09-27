"""
Confirmation indicators used to score how meaningful a detected pattern is.
"""
import pandas as pd
import numpy as np


def rsi(df, period=14):
    """
    Wilder's RSI using exponential moving average (standard method).
    Uses ewm with alpha=1/period for proper Wilder smoothing.
    """
    delta = df["Close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / period, min_periods=period).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def volume_ratio(df, period=20):
    """Current volume vs its rolling average -> >1 means above-average volume."""
    avg_vol = df["Volume"].rolling(period).mean()
    return df["Volume"] / avg_vol.replace(0, np.nan)


def trend(df, period=20):
    """Simple trend label from slope of the moving average."""
    ma = df["Close"].rolling(period).mean()
    slope = ma.diff()
    direction = np.where(slope > 0, "uptrend", np.where(slope < 0, "downtrend", "flat"))
    return pd.Series(direction, index=df.index)


def score_pattern(df, pattern_row, rsi_series, vol_ratio_series, trend_series):
    """
    Combines pattern bias with RSI/volume/trend context into a plain confidence note.
    This is rule-based, not an LLM guess.

    Returns (score, note) where score is 0-3:
      - 0: no confirmation signals align
      - 1: one indicator confirms
      - 2: two indicators confirm
      - 3: all three indicators confirm (strongest signal)
    """
    d = pattern_row["date"]
    bias = pattern_row["bias"]
    notes = []
    score = 0

    # RSI confirmation
    try:
        r = rsi_series.at[d] if d in rsi_series.index else np.nan
    except KeyError:
        r = np.nan
    if bias == "bullish" and pd.notna(r) and r < 35:
        notes.append(f"RSI {r:.0f} (oversold) supports bullish reversal")
        score += 1
    elif bias == "bearish" and pd.notna(r) and r > 65:
        notes.append(f"RSI {r:.0f} (overbought) supports bearish reversal")
        score += 1

    # Volume confirmation
    try:
        v = vol_ratio_series.at[d] if d in vol_ratio_series.index else np.nan
    except KeyError:
        v = np.nan
    if pd.notna(v) and v > 1.3:
        notes.append(f"Volume {v:.1f}x average — pattern has weight")
        score += 1

    # Trend confirmation
    try:
        t = trend_series.at[d] if d in trend_series.index else None
    except KeyError:
        t = None
    if bias == "bullish" and t == "downtrend":
        notes.append("Forms at end of downtrend — classic reversal setup")
        score += 1
    elif bias == "bearish" and t == "uptrend":
        notes.append("Forms at end of uptrend — classic reversal setup")
        score += 1

    if not notes:
        notes.append("No strong confirmation from RSI/volume/trend — weaker signal")

    return score, "; ".join(notes)

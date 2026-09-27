"""
Candlestick pattern detection using pure pandas (no TA-Lib dependency).
Each function returns a boolean Series aligned to the DataFrame index.
Patterns implemented: Doji, Hammer, Inverted Hammer, Shooting Star,
Bullish Engulfing, Bearish Engulfing, Morning Star, Evening Star.
"""
import pandas as pd
import numpy as np

# Minimum candle range as a fraction of the closing price.
# Filters out tiny candles on low-volume days that produce false positives.
MIN_RANGE_PCT = 0.001


def _body(df):
    return (df["Close"] - df["Open"]).abs()


def _candle_range(df):
    return (df["High"] - df["Low"]).replace(0, np.nan)


def _upper_wick(df):
    return df["High"] - df[["Close", "Open"]].max(axis=1)


def _lower_wick(df):
    return df[["Close", "Open"]].min(axis=1) - df["Low"]


def _significant(df):
    """Filter: only consider candles whose range is large enough to be meaningful."""
    return _candle_range(df) > df["Close"] * MIN_RANGE_PCT


def doji(df, body_pct=0.1):
    """Body is very small relative to the candle's range -> indecision."""
    return (_body(df) <= body_pct * _candle_range(df)) & _significant(df)


def hammer(df):
    """Small body near top, long lower wick, little/no upper wick -> bullish reversal at bottom of downtrend."""
    body = _body(df)
    lower = _lower_wick(df)
    upper = _upper_wick(df)
    safe_body = body.replace(0, np.nan)
    return (lower >= 2 * body) & (upper <= 0.3 * safe_body) & _significant(df)


def inverted_hammer(df):
    """Small body near bottom, long upper wick, little/no lower wick -> bullish reversal at bottom of downtrend.
    Differs from shooting star only by context (downtrend vs uptrend), but the candle shape is detected here."""
    body = _body(df)
    lower = _lower_wick(df)
    upper = _upper_wick(df)
    safe_body = body.replace(0, np.nan)
    return (upper >= 2 * body) & (lower <= 0.3 * safe_body) & _significant(df)


def shooting_star(df):
    """Small body near bottom, long upper wick, little/no lower wick -> bearish reversal at top of uptrend."""
    body = _body(df)
    lower = _lower_wick(df)
    upper = _upper_wick(df)
    safe_body = body.replace(0, np.nan)
    return (upper >= 2 * body) & (lower <= 0.3 * safe_body) & _significant(df)


def bullish_engulfing(df):
    """Prior candle bearish (red), current candle bullish (green) and fully engulfs prior body."""
    prev_open = df["Open"].shift(1)
    prev_close = df["Close"].shift(1)
    prev_bearish = prev_close < prev_open
    curr_bullish = df["Close"] > df["Open"]
    engulfs = (df["Open"] <= prev_close) & (df["Close"] >= prev_open)
    return prev_bearish & curr_bullish & engulfs & _significant(df)


def bearish_engulfing(df):
    """Prior candle bullish (green), current candle bearish (red) and fully engulfs prior body."""
    prev_open = df["Open"].shift(1)
    prev_close = df["Close"].shift(1)
    prev_bullish = prev_close > prev_open
    curr_bearish = df["Close"] < df["Open"]
    engulfs = (df["Open"] >= prev_close) & (df["Close"] <= prev_open)
    return prev_bullish & curr_bearish & engulfs & _significant(df)


def morning_star(df):
    """3-candle bullish reversal: long red, small indecisive candle, long green closing into first candle's body."""
    c1_open, c1_close = df["Open"].shift(2), df["Close"].shift(2)
    c2_body = _body(df).shift(1)
    c3_open, c3_close = df["Open"], df["Close"]
    c1_bearish = c1_close < c1_open
    c1_body = (c1_open - c1_close)
    small_middle = c2_body <= 0.4 * c1_body.replace(0, np.nan)
    c3_bullish = c3_close > c3_open
    closes_into_c1 = c3_close >= (c1_open + c1_close) / 2
    return c1_bearish & small_middle & c3_bullish & closes_into_c1 & _significant(df)


def evening_star(df):
    """3-candle bearish reversal: long green, small indecisive candle, long red closing into first candle's body."""
    c1_open, c1_close = df["Open"].shift(2), df["Close"].shift(2)
    c2_body = _body(df).shift(1)
    c3_open, c3_close = df["Open"], df["Close"]
    c1_bullish = c1_close > c1_open
    c1_body = (c1_close - c1_open)
    small_middle = c2_body <= 0.4 * c1_body.replace(0, np.nan)
    c3_bearish = c3_close < c3_open
    closes_into_c1 = c3_close <= (c1_open + c1_close) / 2
    return c1_bullish & small_middle & c3_bearish & closes_into_c1 & _significant(df)


PATTERN_FUNCS = {
    "Doji": (doji, "neutral"),
    "Hammer": (hammer, "bullish"),
    "Inverted Hammer": (inverted_hammer, "bullish"),
    "Shooting Star": (shooting_star, "bearish"),
    "Bullish Engulfing": (bullish_engulfing, "bullish"),
    "Bearish Engulfing": (bearish_engulfing, "bearish"),
    "Morning Star": (morning_star, "bullish"),
    "Evening Star": (evening_star, "bearish"),
}


def scan_patterns(df):
    """
    Runs all pattern functions on the OHLC DataFrame.
    Returns a DataFrame with one row per (date, pattern) match found.
    """
    results = []
    for name, (func, bias) in PATTERN_FUNCS.items():
        mask = func(df)
        matched_dates = df.index[mask.fillna(False)]
        for d in matched_dates:
            results.append({"date": d, "pattern": name, "bias": bias})
    if not results:
        return pd.DataFrame(columns=["date", "pattern", "bias"])
    return pd.DataFrame(results).sort_values("date").reset_index(drop=True)

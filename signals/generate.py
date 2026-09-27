"""
Generates actionable next-day trade signals from detected patterns + confirmation.
Calculates entry price, stop-loss, and target based on the pattern candle's price action.

This is rule-based logic (not prediction). The signals are educational suggestions
derived from classical candlestick trading rules.
"""
import pandas as pd
import numpy as np


# Minimum confidence score to generate an actionable signal
MIN_SCORE_FOR_SIGNAL = 1

# Risk-reward ratio for target calculation (1:2 means target is 2x the stop-loss distance)
RISK_REWARD_RATIO = 2.0


def generate_signal(df, pattern_row, score, note):
    """
    Given a detected pattern and its confirmation score, generate a next-day
    trade signal with entry, stop-loss, and target prices.

    Returns a dict with:
        action: 'BUY' | 'SELL' | 'WAIT' | 'WATCH'
        entry: suggested entry price (next day open area)
        stop_loss: price to exit if trade goes wrong
        target: price target based on risk-reward ratio
        risk_reward: the R:R ratio used
        reason: human-readable explanation
    """
    d = pattern_row["date"]
    bias = pattern_row["bias"]
    pattern = pattern_row["pattern"]

    # Get the pattern candle's OHLC data
    try:
        candle = df.loc[d]
    except KeyError:
        return _wait_signal("Could not find candle data for this date")

    candle_high = float(candle["High"])
    candle_low = float(candle["Low"])
    candle_close = float(candle["Close"])
    candle_open = float(candle["Open"])

    # Neutral patterns (Doji) — always WATCH, never act
    if bias == "neutral":
        return {
            "action": "WATCH",
            "emoji": "👀",
            "entry": None,
            "stop_loss": None,
            "target": None,
            "risk_reward": None,
            "reason": f"{pattern} shows indecision. Wait for next candle to confirm direction.",
        }

    # Weak signals — WAIT
    if score < MIN_SCORE_FOR_SIGNAL:
        return {
            "action": "WAIT",
            "emoji": "⏸️",
            "entry": None,
            "stop_loss": None,
            "target": None,
            "risk_reward": None,
            "reason": f"{pattern} detected but confirmation is weak ({score}/3). Skip this trade.",
        }

    # --- BULLISH signals → BUY ---
    if bias == "bullish":
        # Entry: near the close of the pattern candle (or next day open)
        entry = round(candle_close, 2)

        # Stop-loss: below the low of the pattern candle (with small buffer)
        buffer = (candle_high - candle_low) * 0.05  # 5% of candle range as buffer
        stop_loss = round(candle_low - buffer, 2)

        # Target: based on risk-reward ratio
        risk = entry - stop_loss
        target = round(entry + (risk * RISK_REWARD_RATIO), 2)

        # Calculate risk percentage
        risk_pct = round((risk / entry) * 100, 2)

        strength = "Strong" if score >= 2 else "Moderate"

        return {
            "action": "BUY",
            "emoji": "📗",
            "entry": entry,
            "stop_loss": stop_loss,
            "target": target,
            "risk_reward": f"1:{RISK_REWARD_RATIO:.0f}",
            "risk_pct": risk_pct,
            "reason": (
                f"{strength} BUY signal. {pattern} ({score}/3 confirmation). "
                f"Enter near {entry}, stop-loss at {stop_loss} ({risk_pct}% risk), "
                f"target {target}. {note}"
            ),
        }

    # --- BEARISH signals → SELL / EXIT ---
    if bias == "bearish":
        # Entry: near the close of the pattern candle
        entry = round(candle_close, 2)

        # Stop-loss: above the high of the pattern candle (with small buffer)
        buffer = (candle_high - candle_low) * 0.05
        stop_loss = round(candle_high + buffer, 2)

        # Target: below entry based on risk-reward ratio
        risk = stop_loss - entry
        target = round(entry - (risk * RISK_REWARD_RATIO), 2)

        risk_pct = round((risk / entry) * 100, 2)

        strength = "Strong" if score >= 2 else "Moderate"

        return {
            "action": "SELL",
            "emoji": "📕",
            "entry": entry,
            "stop_loss": stop_loss,
            "target": target,
            "risk_reward": f"1:{RISK_REWARD_RATIO:.0f}",
            "risk_pct": risk_pct,
            "reason": (
                f"{strength} SELL/EXIT signal. {pattern} ({score}/3 confirmation). "
                f"Exit/short near {entry}, stop-loss at {stop_loss} ({risk_pct}% risk), "
                f"target {target}. {note}"
            ),
        }

    return _wait_signal(f"Unknown bias: {bias}")


def _wait_signal(reason):
    return {
        "action": "WAIT",
        "emoji": "⏸️",
        "entry": None,
        "stop_loss": None,
        "target": None,
        "risk_reward": None,
        "reason": reason,
    }


def generate_signals_for_watchlist(results_with_scores):
    """
    Takes a list of dicts (each with pattern_row, df, score, note) and
    returns them enriched with trade signals.
    """
    signals = []
    for item in results_with_scores:
        signal = generate_signal(
            item["df"], item["pattern_row"], item["score"], item["note"]
        )
        item["signal"] = signal
        signals.append(item)
    return signals

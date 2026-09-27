"""
LIVE INTRADAY OPTIONS SCANNER
==============================
Run this during market hours (9:15 AM - 3:30 PM IST) to get real-time
NIFTY and BANKNIFTY options signals.

Usage:
    python live_options_scan.py              # Scan both NIFTY + BANKNIFTY
    python live_options_scan.py NIFTY        # Scan NIFTY only
    python live_options_scan.py BANKNIFTY    # Scan BANKNIFTY only

Checks 5m, 15m, 30m, and 1h charts for pattern confluence.
If multiple timeframes agree → stronger signal.
"""
import sys
import os
import datetime
import logging

from fetcher.get_ohlc import fetch_ohlc
from patterns.detect import scan_patterns
from indicators.confirm import rsi, volume_ratio, trend, score_pattern
from signals.options import generate_option_signal, INDEX_NAMES, STRIKE_GAPS, get_atm_strike

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
logger = logging.getLogger(__name__)

# Index symbols
INDICES = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK",
}

# Timeframes to scan (short to long)
TIMEFRAMES = [
    {"interval": "5m",  "period": "5d",  "label": "5 min",  "weight": 1},
    {"interval": "15m", "period": "1mo", "label": "15 min", "weight": 2},
    {"interval": "30m", "period": "1mo", "label": "30 min", "weight": 2},
    {"interval": "1h",  "period": "1mo", "label": "1 hour", "weight": 3},
]


def scan_timeframe(symbol, interval, period):
    """Scan a single timeframe. Returns result dict or None."""
    try:
        df = fetch_ohlc(symbol, period=period, interval=interval)
        if len(df) < 10:
            return None

        patterns_found = scan_patterns(df)
        if patterns_found.empty:
            return None

        rsi_s = rsi(df)
        vol_s = volume_ratio(df)
        trend_s = trend(df)

        # Get the most recent pattern
        best = patterns_found.sort_values("date", ascending=False).iloc[0]
        score, note = score_pattern(df, best, rsi_s, vol_s, trend_s)

        current_price = float(df["Close"].iloc[-1])
        current_rsi = float(rsi_s.iloc[-1]) if len(rsi_s) > 0 and not rsi_s.iloc[-1] != rsi_s.iloc[-1] else None
        current_trend = trend_s.iloc[-1] if len(trend_s) > 0 else None

        return {
            "pattern": best["pattern"],
            "bias": best["bias"],
            "date": best["date"],
            "score": score,
            "note": note,
            "current_price": current_price,
            "current_rsi": current_rsi,
            "current_trend": current_trend,
        }
    except Exception as e:
        logger.warning("  %s scan failed: %s", interval, e)
        return None


def compute_confluence(results, symbol):
    """
    Analyze results across all timeframes to compute a confluence score.
    More timeframes agreeing = stronger signal.

    Returns a dict with the final recommendation.
    """
    bullish_weight = 0
    bearish_weight = 0
    total_weight = 0
    details = []

    current_price = None

    for tf, result in results.items():
        weight = next(t["weight"] for t in TIMEFRAMES if t["interval"] == tf)
        total_weight += weight

        if result is None:
            details.append({"tf": tf, "bias": "none", "pattern": "-", "score": 0})
            continue

        current_price = result["current_price"]

        if result["bias"] == "bullish":
            bullish_weight += weight * (1 + result["score"] * 0.5)
        elif result["bias"] == "bearish":
            bearish_weight += weight * (1 + result["score"] * 0.5)

        details.append({
            "tf": tf,
            "bias": result["bias"],
            "pattern": result["pattern"],
            "score": result["score"],
            "note": result["note"],
            "rsi": result["current_rsi"],
            "trend": result["current_trend"],
        })

    if current_price is None:
        return None

    # Determine overall bias
    total_signal = bullish_weight + bearish_weight
    if total_signal == 0:
        overall_bias = "neutral"
        confidence = 0
    elif bullish_weight > bearish_weight:
        overall_bias = "bullish"
        confidence = bullish_weight / (bullish_weight + bearish_weight)
    elif bearish_weight > bullish_weight:
        overall_bias = "bearish"
        confidence = bearish_weight / (bullish_weight + bearish_weight)
    else:
        overall_bias = "conflicting"
        confidence = 0

    # Count how many timeframes agree
    agreeing_tfs = sum(1 for d in details if d["bias"] == overall_bias)
    total_tfs = sum(1 for d in details if d["bias"] != "none")

    # Generate final signal
    strike_gap = STRIKE_GAPS.get(symbol, 50)
    atm_strike = get_atm_strike(current_price, strike_gap)
    index_name = INDEX_NAMES.get(symbol, symbol)

    if overall_bias == "neutral" or overall_bias == "conflicting" or confidence < 0.55:
        action = "NO TRADE"
        option_type = None
        suggested_strike = None
        otm_strike = None
        strength = "AVOID"
        reason = "Timeframes are conflicting or neutral. No clear direction. Stay out."
    elif overall_bias == "bullish":
        action = "BUY CE"
        option_type = "CE"
        if confidence > 0.75 and agreeing_tfs >= 3:
            suggested_strike = atm_strike
            otm_strike = atm_strike + strike_gap
            strength = "STRONG"
        elif confidence > 0.6 and agreeing_tfs >= 2:
            suggested_strike = atm_strike + strike_gap
            otm_strike = atm_strike + (2 * strike_gap)
            strength = "MODERATE"
        else:
            suggested_strike = atm_strike + (2 * strike_gap)
            otm_strike = atm_strike + (3 * strike_gap)
            strength = "WEAK"

        risk_points = current_price * 0.004
        sl = round(current_price - risk_points, 2)
        target = round(current_price + (risk_points * 2), 2)
        reason = (
            f"{strength} bullish confluence ({agreeing_tfs}/{total_tfs} timeframes agree). "
            f"Buy {index_name} {suggested_strike} CE. "
            f"Index SL: {sl}, Target: {target}."
        )
    else:  # bearish
        action = "BUY PE"
        option_type = "PE"
        if confidence > 0.75 and agreeing_tfs >= 3:
            suggested_strike = atm_strike
            otm_strike = atm_strike - strike_gap
            strength = "STRONG"
        elif confidence > 0.6 and agreeing_tfs >= 2:
            suggested_strike = atm_strike - strike_gap
            otm_strike = atm_strike - (2 * strike_gap)
            strength = "MODERATE"
        else:
            suggested_strike = atm_strike - (2 * strike_gap)
            otm_strike = atm_strike - (3 * strike_gap)
            strength = "WEAK"

        risk_points = current_price * 0.004
        sl = round(current_price + risk_points, 2)
        target = round(current_price - (risk_points * 2), 2)
        reason = (
            f"{strength} bearish confluence ({agreeing_tfs}/{total_tfs} timeframes agree). "
            f"Buy {index_name} {suggested_strike} PE. "
            f"Index SL: {sl}, Target: {target}."
        )

    return {
        "index_name": index_name,
        "symbol": symbol,
        "current_price": current_price,
        "atm_strike": atm_strike,
        "action": action,
        "strength": strength,
        "option_type": option_type,
        "suggested_strike": suggested_strike,
        "otm_strike": otm_strike,
        "confidence": confidence,
        "agreeing_tfs": agreeing_tfs,
        "total_tfs": total_tfs,
        "overall_bias": overall_bias,
        "reason": reason,
        "details": details,
        "sl": sl if overall_bias in ["bullish", "bearish"] and confidence >= 0.55 else None,
        "target": target if overall_bias in ["bullish", "bearish"] and confidence >= 0.55 else None,
    }


def print_separator(char="=", width=80):
    print(char * width)


def print_center(text, width=80):
    print(text.center(width))


def display_result(result):
    """Print a formatted result to the console."""
    if result is None:
        print("  Could not fetch data for this index.")
        return

    idx = result["index_name"]
    price = result["current_price"]
    atm = result["atm_strike"]

    print()
    print_separator("=")
    print_center(f"{idx}  |  Level: {price:.2f}  |  ATM: {atm}")
    print_separator("=")
    print()

    # Timeframe breakdown table
    print(f"  {'Timeframe':<12} {'Pattern':<22} {'Bias':<12} {'Score':<10} {'Trend':<12} {'RSI':<8}")
    print(f"  {'-'*10:<12} {'-'*20:<22} {'-'*10:<12} {'-'*8:<10} {'-'*10:<12} {'-'*6:<8}")

    for d in result["details"]:
        tf_label = next((t["label"] for t in TIMEFRAMES if t["interval"] == d["tf"]), d["tf"])
        pattern = d.get("pattern", "-")
        bias = d.get("bias", "-")
        score_str = ("*" * d["score"] + "." * (3 - d["score"])) if d["score"] > 0 else "-"
        trend_str = d.get("trend", "-") if d.get("trend") else "-"
        rsi_str = f"{d['rsi']:.0f}" if d.get("rsi") is not None else "-"
        print(f"  {tf_label:<12} {pattern:<22} {bias:<12} {score_str:<10} {trend_str:<12} {rsi_str:<8}")

    print()
    print_separator("-")

    # Final recommendation
    action = result["action"]
    strength = result["strength"]

    if action == "NO TRADE":
        print(f"  RECOMMENDATION:  NO TRADE (timeframes conflicting)")
        print(f"  Stay out. Wait for clarity.")
    else:
        print(f"  RECOMMENDATION:  {action}")
        print(f"  Strength:        {strength} ({result['agreeing_tfs']}/{result['total_tfs']} timeframes agree)")
        print(f"  Confidence:      {result['confidence']:.0%}")
        print()
        print(f"  Option to Buy:   {idx} {result['suggested_strike']} {result['option_type']}")
        print(f"  Cheaper Option:  {idx} {result['otm_strike']} {result['option_type']} (OTM)")
        print()
        print(f"  Index SL:        {result['sl']}")
        print(f"  Index Target:    {result['target']}")

    print()
    print(f"  Reason: {result['reason']}")
    print_separator("=")
    print()


def main():
    now = datetime.datetime.now()
    print()
    print_separator("*")
    print_center("LIVE INTRADAY OPTIONS SCANNER")
    print_center(f"Scan Time: {now.strftime('%Y-%m-%d %I:%M %p IST')}")
    print_separator("*")

    # Check market hours (optional warning)
    hour = now.hour
    minute = now.minute
    if hour < 9 or (hour == 9 and minute < 15):
        print("\n  WARNING: Market hasn't opened yet (opens 9:15 AM IST).")
        print("  Data may be from previous session.\n")
    elif hour >= 15 and minute >= 30:
        print("\n  NOTE: Market is closed (closed 3:30 PM IST).")
        print("  Showing end-of-day data.\n")

    # Determine which indices to scan
    args = [a.upper() for a in sys.argv[1:]]
    if args:
        indices_to_scan = {name: sym for name, sym in INDICES.items() if name in args}
        if not indices_to_scan:
            print(f"  Unknown index. Use: {', '.join(INDICES.keys())}")
            sys.exit(1)
    else:
        indices_to_scan = INDICES

    for name, symbol in indices_to_scan.items():
        print(f"\n  Scanning {name} across {len(TIMEFRAMES)} timeframes...")

        results = {}
        for tf in TIMEFRAMES:
            logger.info("  Scanning %s %s...", name, tf["label"])
            result = scan_timeframe(symbol, tf["interval"], tf["period"])
            results[tf["interval"]] = result

            if result:
                logger.info("    -> %s (%s) | Score: %d/3", result["pattern"], result["bias"], result["score"])
            else:
                logger.info("    -> No pattern found")

        # Compute multi-timeframe confluence
        confluence = compute_confluence(results, symbol)
        display_result(confluence)

    # Summary
    print_separator("*")
    print_center("QUICK SUMMARY")
    print_separator("*")
    print()
    print(f"  {'Index':<14} {'Action':<14} {'Strength':<12} {'Option':<24} {'SL':<12} {'Target':<12}")
    print(f"  {'-'*12:<14} {'-'*12:<14} {'-'*10:<12} {'-'*22:<24} {'-'*10:<12} {'-'*10:<12}")

    for name, symbol in indices_to_scan.items():
        results = {}
        for tf in TIMEFRAMES:
            results[tf["interval"]] = scan_timeframe(symbol, tf["interval"], tf["period"])
        confluence = compute_confluence(results, symbol)
        if confluence:
            opt = f"{name} {confluence['suggested_strike']} {confluence['option_type']}" if confluence['suggested_strike'] else "-"
            sl = str(confluence.get('sl', '-')) if confluence.get('sl') else "-"
            tgt = str(confluence.get('target', '-')) if confluence.get('target') else "-"
            print(f"  {name:<14} {confluence['action']:<14} {confluence['strength']:<12} {opt:<24} {sl:<12} {tgt:<12}")

    print()
    print("  NOTE: Run this every 30-60 minutes during market hours for updated signals.")
    print("  Stronger signals = more timeframes agreeing in the same direction.")
    print()
    print_separator("-")
    print_center("Educational tool only - not financial advice")
    print_separator("-")
    print()


if __name__ == "__main__":
    main()

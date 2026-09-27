"""
Scans a watchlist of NSE symbols for candlestick patterns and writes a
markdown report to reports/latest.md with actionable next-day trade signals.
Meant to be run by the GitHub Actions workflow on a schedule (e.g. daily after market close).
"""
import sys
import os
import logging
import datetime
from fetcher.get_ohlc import fetch_ohlc
from patterns.detect import scan_patterns
from indicators.confirm import rsi, volume_ratio, trend, score_pattern
from signals.generate import generate_signal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Edit this list, or set the WATCHLIST environment variable (comma-separated)
DEFAULT_WATCHLIST = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "HDFCBANK.NS"]


def get_watchlist():
    """Read watchlist from env var (comma-separated) or fall back to default."""
    env_val = os.environ.get("WATCHLIST", "")
    if env_val.strip():
        return [s.strip().upper() for s in env_val.split(",") if s.strip()]
    return DEFAULT_WATCHLIST


def scan_symbol(symbol):
    df = fetch_ohlc(symbol, period="3mo", interval="1d")
    patterns_found = scan_patterns(df)
    if patterns_found.empty:
        return None

    rsi_s = rsi(df)
    vol_s = volume_ratio(df)
    trend_s = trend(df)

    best = patterns_found.sort_values("date", ascending=False).iloc[0]
    score, note = score_pattern(df, best, rsi_s, vol_s, trend_s)

    # Generate trade signal
    signal = generate_signal(df, best, score, note)

    return {
        "symbol": symbol,
        "date": best["date"].strftime("%Y-%m-%d"),
        "pattern": best["pattern"],
        "bias": best["bias"],
        "score": score,
        "note": note,
        "signal": signal,
        "close": float(df["Close"].iloc[-1]),
    }


def main():
    watchlist = get_watchlist()
    logger.info("Scanning %d symbols: %s", len(watchlist), ", ".join(watchlist))

    os.makedirs("reports", exist_ok=True)
    today = datetime.date.today().isoformat()

    lines = [
        f"# Daily Pattern Scan & Trade Signals - {today}\n",
        "> Educational tool only - not financial advice. Always do your own research.\n",
        "---\n",
        "## Quick Summary\n",
        "| Stock | Pattern | Action | Entry | Stop-Loss | Target | Risk |",
        "|-------|---------|--------|-------|-----------|--------|------|",
    ]

    # Collect results for summary table
    all_results = []
    failures = 0

    for symbol in watchlist:
        try:
            result = scan_symbol(symbol)
        except Exception as e:
            logger.error("Failed to scan %s: %s", symbol, e)
            failures += 1
            all_results.append({"symbol": symbol, "error": str(e)})
            continue

        if result is None:
            all_results.append({"symbol": symbol, "no_pattern": True})
            continue

        all_results.append(result)

    # Build summary table
    for r in all_results:
        sym = r["symbol"].replace(".NS", "")
        if "error" in r:
            lines.append(f"| {sym} | - | ERROR | - | - | - | - |")
        elif r.get("no_pattern"):
            lines.append(f"| {sym} | - | No signal | - | - | - | - |")
        else:
            sig = r["signal"]
            action = f"{sig['emoji']} **{sig['action']}**"
            entry = f"{sig['entry']}" if sig['entry'] else "-"
            sl = f"{sig['stop_loss']}" if sig['stop_loss'] else "-"
            tgt = f"{sig['target']}" if sig['target'] else "-"
            risk = f"{sig.get('risk_pct', '-')}%" if sig.get('risk_pct') else "-"
            lines.append(f"| {sym} | {r['pattern']} | {action} | {entry} | {sl} | {tgt} | {risk} |")

    lines.append("")
    lines.append("---\n")

    # Detailed sections per stock
    lines.append("## Detailed Analysis\n")

    for r in all_results:
        sym = r["symbol"]
        if "error" in r:
            lines.append(f"### {sym}\nError fetching data: {r['error']}\n")
            continue
        if r.get("no_pattern"):
            logger.info("%s: no patterns detected", sym)
            lines.append(f"### {sym}\nNo pattern detected in the last 3 months.\n")
            continue

        logger.info("%s: %s (%s) on %s -> %s",
                     sym, r["pattern"], r["bias"], r["date"], r["signal"]["action"])

        sig = r["signal"]
        stars = "*" * r["score"] + "." * (3 - r["score"])

        section = [
            f"### {sig['emoji']} {sym} - {sig['action']}\n",
            f"- **Pattern:** {r['pattern']} ({r['bias']})",
            f"- **Detected on:** {r['date']}",
            f"- **Current Price:** {r['close']:.2f}",
            f"- **Confidence:** {stars} ({r['score']}/3)",
            f"- **Why:** {r['note']}",
            "",
        ]

        if sig["entry"]:
            section.extend([
                "**Trade Plan:**",
                f"- Entry: **{sig['entry']}**",
                f"- Stop-Loss: **{sig['stop_loss']}** ({sig.get('risk_pct', '?')}% risk)",
                f"- Target: **{sig['target']}** (Risk-Reward {sig['risk_reward']})",
                "",
            ])

        section.extend([
            f"> {sig['reason']}",
            "",
        ])

        lines.append("\n".join(section))

    # Footer
    lines.extend([
        "---\n",
        "## How to Use This Report\n",
        "1. **BUY signals** - Consider buying at next morning's market open near the entry price",
        "2. **SELL signals** - Consider exiting/shorting at next morning's market open",
        "3. **WAIT** - Signal too weak, skip this trade",
        "4. **WATCH** - Market undecided (Doji), wait for next candle\n",
        "**Risk Management Rules:**",
        "- Never risk more than 2% of your capital on a single trade",
        "- Always place a stop-loss order immediately after entry",
        "- If the stock gaps up/down significantly at open, skip the trade",
        "- Strong signals (2-3 stars) are safer than weak ones (0-1 stars)\n",
        "> *This is an educational tool. Past patterns do not guarantee future results. "
        "Always do your own research before trading.*\n",
    ])

    report = "\n".join(lines)

    with open("reports/latest.md", "w", encoding="utf-8") as f:
        f.write(report)

    # also keep a dated copy
    with open(f"reports/{today}.md", "w", encoding="utf-8") as f:
        f.write(report)

    print(report)

    # Exit with error if ALL symbols failed (so GitHub Actions shows failure)
    if failures == len(watchlist):
        logger.error("All %d symbols failed!", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()

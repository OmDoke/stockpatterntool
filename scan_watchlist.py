"""
Scans a watchlist of NSE symbols + indices for candlestick patterns and writes a
markdown report to reports/latest.md with actionable next-day trade signals.
Supports: stocks (daily), indices (daily + intraday), and options suggestions.
Meant to be run by the GitHub Actions workflow or manually.
"""
import sys
import os
import logging
import datetime
from fetcher.get_ohlc import fetch_ohlc
from patterns.detect import scan_patterns
from indicators.confirm import rsi, volume_ratio, trend, score_pattern
from signals.generate import generate_signal
from signals.options import generate_option_signal, INDEX_NAMES

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Edit these lists, or set environment variables (comma-separated)
DEFAULT_STOCKS = ["RELIANCE.NS", "TCS.NS", "INFY.NS", "SBIN.NS", "HDFCBANK.NS"]
DEFAULT_INDICES = ["^NSEI", "^NSEBANK"]

# Intraday intervals to scan for indices
INTRADAY_INTERVALS = ["1h", "15m"]


def get_watchlist(env_var, default):
    """Read watchlist from env var (comma-separated) or fall back to default."""
    env_val = os.environ.get(env_var, "")
    if env_val.strip():
        return [s.strip() for s in env_val.split(",") if s.strip()]
    return default


def scan_symbol(symbol, period="3mo", interval="1d"):
    """Scan a single symbol for patterns. Returns result dict or None."""
    df = fetch_ohlc(symbol, period=period, interval=interval)
    patterns_found = scan_patterns(df)
    if patterns_found.empty:
        return None

    rsi_s = rsi(df)
    vol_s = volume_ratio(df)
    trend_s = trend(df)

    best = patterns_found.sort_values("date", ascending=False).iloc[0]
    score, note = score_pattern(df, best, rsi_s, vol_s, trend_s)

    # Generate stock trade signal
    signal = generate_signal(df, best, score, note)

    return {
        "symbol": symbol,
        "date": best["date"].strftime("%Y-%m-%d %H:%M") if interval != "1d" else best["date"].strftime("%Y-%m-%d"),
        "pattern": best["pattern"],
        "bias": best["bias"],
        "score": score,
        "note": note,
        "signal": signal,
        "close": float(df["Close"].iloc[-1]),
        "interval": interval,
    }


def scan_index_with_options(symbol, period="3mo", interval="1d"):
    """Scan an index and generate options signals."""
    df = fetch_ohlc(symbol, period=period, interval=interval)
    patterns_found = scan_patterns(df)
    if patterns_found.empty:
        return None

    rsi_s = rsi(df)
    vol_s = volume_ratio(df)
    trend_s = trend(df)

    best = patterns_found.sort_values("date", ascending=False).iloc[0]
    score, note = score_pattern(df, best, rsi_s, vol_s, trend_s)

    current_price = float(df["Close"].iloc[-1])

    # Generate options signal
    option_signal = generate_option_signal(
        symbol, current_price, best["pattern"], best["bias"], score, note
    )

    return {
        "symbol": symbol,
        "index_name": INDEX_NAMES.get(symbol, symbol),
        "date": best["date"].strftime("%Y-%m-%d %H:%M") if interval != "1d" else best["date"].strftime("%Y-%m-%d"),
        "pattern": best["pattern"],
        "bias": best["bias"],
        "score": score,
        "note": note,
        "option_signal": option_signal,
        "close": current_price,
        "interval": interval,
    }


def main():
    stocks = get_watchlist("WATCHLIST", DEFAULT_STOCKS)
    indices = get_watchlist("INDICES", DEFAULT_INDICES)

    logger.info("Scanning %d stocks: %s", len(stocks), ", ".join(stocks))
    logger.info("Scanning %d indices: %s", len(indices), ", ".join(indices))

    os.makedirs("reports", exist_ok=True)
    today = datetime.date.today().isoformat()

    lines = [
        f"# Daily Pattern Scan & Trade Signals - {today}\n",
        "> Educational tool only - not financial advice. Always do your own research.\n",
    ]

    failures = 0

    # ═══════════════════════════════════════════════════════════
    # SECTION 1: INDEX OPTIONS SIGNALS (Nifty 50, Bank Nifty)
    # ═══════════════════════════════════════════════════════════
    lines.extend([
        "---\n",
        "## INDEX OPTIONS SIGNALS\n",
        "| Index | Interval | Pattern | Action | Strike | OTM Strike | Index SL | Index Target |",
        "|-------|----------|---------|--------|--------|------------|----------|--------------|",
    ])

    index_details = []

    for symbol in indices:
        # Daily scan
        for interval in ["1d"] + INTRADAY_INTERVALS:
            # Intraday needs shorter period
            period = "1mo" if interval in ["15m", "1h"] else "3mo"
            try:
                result = scan_index_with_options(symbol, period=period, interval=interval)
            except Exception as e:
                logger.error("Failed to scan %s (%s): %s", symbol, interval, e)
                failures += 1
                idx_name = INDEX_NAMES.get(symbol, symbol)
                lines.append(f"| {idx_name} | {interval} | - | ERROR | - | - | - | - |")
                continue

            if result is None:
                idx_name = INDEX_NAMES.get(symbol, symbol)
                lines.append(f"| {idx_name} | {interval} | - | No signal | - | - | - | - |")
                continue

            sig = result["option_signal"]
            idx_name = result["index_name"]
            logger.info("%s (%s): %s (%s) -> %s", idx_name, interval, result["pattern"], result["bias"], sig["action"])

            strike = f"{idx_name} {sig['suggested_strike']} {sig['option_type']}" if sig["suggested_strike"] else "-"
            otm = f"{idx_name} {sig['otm_strike']} {sig['option_type']}" if sig["otm_strike"] else "-"
            sl = f"{sig['stop_loss_index']}" if sig["stop_loss_index"] else "-"
            tgt = f"{sig['target_index']}" if sig["target_index"] else "-"

            lines.append(f"| {idx_name} | {interval} | {result['pattern']} | {sig['emoji']} **{sig['action']}** | {strike} | {otm} | {sl} | {tgt} |")
            index_details.append(result)

    lines.append("")

    # Detailed index sections
    if index_details:
        lines.append("### Index Details\n")
        for r in index_details:
            sig = r["option_signal"]
            stars = "*" * r["score"] + "." * (3 - r["score"])
            section = [
                f"#### {sig['emoji']} {r['index_name']} ({r['interval']}) - {sig['action']}\n",
                f"- **Pattern:** {r['pattern']} ({r['bias']})",
                f"- **Detected on:** {r['date']}",
                f"- **Current Level:** {r['close']:.2f}",
                f"- **ATM Strike:** {sig['atm_strike']}",
                f"- **Confidence:** {stars} ({r['score']}/3)",
                "",
            ]

            if sig["suggested_strike"]:
                section.extend([
                    "**Options Trade Plan:**",
                    f"- Buy: **{r['index_name']} {sig['suggested_strike']} {sig['option_type']}**",
                    f"- Cheaper alternative: **{r['index_name']} {sig['otm_strike']} {sig['option_type']}** (OTM, lower premium)",
                    f"- Index Stop-Loss: **{sig['stop_loss_index']}**",
                    f"- Index Target: **{sig['target_index']}**",
                    "",
                ])

            section.extend([f"> {sig['reason']}", ""])
            lines.append("\n".join(section))

    # ═══════════════════════════════════════════════════════════
    # SECTION 2: STOCK SIGNALS
    # ═══════════════════════════════════════════════════════════
    lines.extend([
        "---\n",
        "## STOCK SIGNALS\n",
        "| Stock | Pattern | Action | Entry | Stop-Loss | Target | Risk |",
        "|-------|---------|--------|-------|-----------|--------|------|",
    ])

    stock_details = []

    for symbol in stocks:
        try:
            result = scan_symbol(symbol)
        except Exception as e:
            logger.error("Failed to scan %s: %s", symbol, e)
            failures += 1
            sym = symbol.replace(".NS", "").replace(".BO", "")
            lines.append(f"| {sym} | - | ERROR | - | - | - | - |")
            continue

        if result is None:
            sym = symbol.replace(".NS", "").replace(".BO", "")
            lines.append(f"| {sym} | - | No signal | - | - | - | - |")
            continue

        stock_details.append(result)
        sig = result["signal"]
        sym = result["symbol"].replace(".NS", "").replace(".BO", "")
        logger.info("%s: %s (%s) -> %s", sym, result["pattern"], result["bias"], sig["action"])

        entry = f"{sig['entry']}" if sig['entry'] else "-"
        sl = f"{sig['stop_loss']}" if sig['stop_loss'] else "-"
        tgt = f"{sig['target']}" if sig['target'] else "-"
        risk = f"{sig.get('risk_pct', '-')}%" if sig.get('risk_pct') else "-"
        lines.append(f"| {sym} | {result['pattern']} | {sig['emoji']} **{sig['action']}** | {entry} | {sl} | {tgt} | {risk} |")

    lines.append("")

    # Detailed stock sections
    if stock_details:
        lines.append("### Stock Details\n")
        for r in stock_details:
            sig = r["signal"]
            sym = r["symbol"]
            stars = "*" * r["score"] + "." * (3 - r["score"])

            section = [
                f"#### {sig['emoji']} {sym} - {sig['action']}\n",
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

            section.extend([f"> {sig['reason']}", ""])
            lines.append("\n".join(section))

    # ═══════════════════════════════════════════════════════════
    # FOOTER
    # ═══════════════════════════════════════════════════════════
    lines.extend([
        "---\n",
        "## How to Use This Report\n",
        "### Stock Signals",
        "- **BUY** - Buy the stock at next morning's open near entry price",
        "- **SELL** - Exit/short the stock at next morning's open\n",
        "### Options Signals",
        "- **BUY CE** - Buy Call option at the suggested strike (bullish view)",
        "- **BUY PE** - Buy Put option at the suggested strike (bearish view)",
        "- Use the **OTM strike** for lower premium (higher risk, higher reward)",
        "- Use the **ATM strike** for safer trades (higher premium, lower risk)\n",
        "### Common Rules",
        "- **WAIT** - Signal too weak, skip this trade",
        "- **WATCH** - Market undecided (Doji), wait for next candle\n",
        "### Intraday vs Daily",
        "- **1d** (Daily) = Swing trade (hold 1-5 days)",
        "- **1h** (Hourly) = Intraday/short-term (hold hours to 1 day)",
        "- **15m** (15-min) = Scalping/quick intraday (hold minutes to hours)\n",
        "**Risk Management:**",
        "- Never risk more than 2% of your capital on a single trade",
        "- Always place a stop-loss immediately after entry",
        "- For options: your max loss is the premium paid",
        "- If index gaps significantly at open, skip the trade\n",
        "> *This is an educational tool. Past patterns do not guarantee future results. "
        "Always do your own research before trading.*\n",
    ])

    report = "\n".join(lines)

    with open("reports/latest.md", "w", encoding="utf-8") as f:
        f.write(report)

    with open(f"reports/{today}.md", "w", encoding="utf-8") as f:
        f.write(report)

    # Print to console — replace emojis with '?' on Windows (cp1252 can't render them)
    import sys as _sys
    _sys.stdout.buffer.write(report.encode(_sys.stdout.encoding or "utf-8", errors="replace"))
    _sys.stdout.buffer.write(b"\n")

    # Exit with error if ALL symbols failed
    total = len(stocks) + len(indices) * (1 + len(INTRADAY_INTERVALS))
    if failures >= total:
        logger.error("All %d scans failed!", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()

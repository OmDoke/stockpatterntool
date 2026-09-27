"""
Generates a styled HTML report from scan results.
The HTML report looks professional and can be opened in any browser.
"""


def generate_html_report(today, index_results, stock_results):
    """Generate a complete styled HTML report string."""

    # Build index options table rows
    index_rows = ""
    for r in index_results:
        if "error" in r:
            idx_name = r.get("index_name", r["symbol"])
            index_rows += f'<tr><td>{idx_name}</td><td>{r.get("interval","1d")}</td><td>-</td><td class="wait">ERROR</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>'
        elif r.get("no_pattern"):
            idx_name = r.get("index_name", r["symbol"])
            index_rows += f'<tr><td>{idx_name}</td><td>{r.get("interval","1d")}</td><td>-</td><td class="wait">No signal</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>'
        else:
            sig = r["option_signal"]
            idx_name = r["index_name"]
            action_class = "buy" if "CE" in sig["action"] else ("sell" if "PE" in sig["action"] else "wait")
            strike = f'{idx_name} {sig["suggested_strike"]} {sig["option_type"]}' if sig["suggested_strike"] else "-"
            otm = f'{idx_name} {sig["otm_strike"]} {sig["option_type"]}' if sig["otm_strike"] else "-"
            sl = f'{sig["stop_loss_index"]}' if sig["stop_loss_index"] else "-"
            tgt = f'{sig["target_index"]}' if sig["target_index"] else "-"
            index_rows += f'<tr><td>{idx_name}</td><td>{r["interval"]}</td><td>{r["pattern"]}</td><td class="{action_class}">{sig["action"]}</td><td>{strike}</td><td>{otm}</td><td>{sl}</td><td>{tgt}</td></tr>'

    # Build index detail cards
    index_cards = ""
    for r in index_results:
        if "error" in r or r.get("no_pattern"):
            continue
        sig = r["option_signal"]
        stars_html = '<span class="star filled">&#9733;</span>' * r["score"] + '<span class="star">&#9733;</span>' * (3 - r["score"])
        action_class = "buy" if "CE" in sig["action"] else ("sell" if "PE" in sig["action"] else "wait")

        trade_plan = ""
        if sig["suggested_strike"]:
            trade_plan = f"""
            <div class="trade-plan">
                <h4>Options Trade Plan</h4>
                <div class="metrics">
                    <div class="metric"><span class="label">Buy</span><span class="value">{r["index_name"]} {sig["suggested_strike"]} {sig["option_type"]}</span></div>
                    <div class="metric"><span class="label">Alternative (OTM)</span><span class="value">{r["index_name"]} {sig["otm_strike"]} {sig["option_type"]}</span></div>
                    <div class="metric"><span class="label">Index SL</span><span class="value sl">{sig["stop_loss_index"]}</span></div>
                    <div class="metric"><span class="label">Index Target</span><span class="value target">{sig["target_index"]}</span></div>
                </div>
            </div>"""

        index_cards += f"""
        <div class="card {action_class}-card">
            <div class="card-header">
                <span class="badge {action_class}">{sig["action"]}</span>
                <span class="symbol">{r["index_name"]} ({r["interval"]})</span>
            </div>
            <div class="card-body">
                <div class="info-row"><span>Pattern:</span> <strong>{r["pattern"]}</strong> ({r["bias"]})</div>
                <div class="info-row"><span>Detected:</span> {r["date"]}</div>
                <div class="info-row"><span>Current Level:</span> {r["close"]:.2f}</div>
                <div class="info-row"><span>Confidence:</span> {stars_html}</div>
                {trade_plan}
                <div class="reason">{sig["reason"]}</div>
            </div>
        </div>"""

    # Build stock table rows
    stock_rows = ""
    for r in stock_results:
        if "error" in r:
            sym = r["symbol"].replace(".NS", "").replace(".BO", "")
            stock_rows += f'<tr><td>{sym}</td><td>-</td><td class="wait">ERROR</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>'
        elif r.get("no_pattern"):
            sym = r["symbol"].replace(".NS", "").replace(".BO", "")
            stock_rows += f'<tr><td>{sym}</td><td>-</td><td class="wait">No signal</td><td>-</td><td>-</td><td>-</td><td>-</td></tr>'
        else:
            sig = r["signal"]
            sym = r["symbol"].replace(".NS", "").replace(".BO", "")
            action_class = "buy" if sig["action"] == "BUY" else ("sell" if sig["action"] == "SELL" else "wait")
            entry = f'{sig["entry"]}' if sig["entry"] else "-"
            sl = f'{sig["stop_loss"]}' if sig["stop_loss"] else "-"
            tgt = f'{sig["target"]}' if sig["target"] else "-"
            risk = f'{sig.get("risk_pct", "-")}%' if sig.get("risk_pct") else "-"
            stock_rows += f'<tr><td>{sym}</td><td>{r["pattern"]}</td><td class="{action_class}">{sig["action"]}</td><td>{entry}</td><td>{sl}</td><td>{tgt}</td><td>{risk}</td></tr>'

    # Build stock detail cards
    stock_cards = ""
    for r in stock_results:
        if "error" in r or r.get("no_pattern"):
            continue
        sig = r["signal"]
        stars_html = '<span class="star filled">&#9733;</span>' * r["score"] + '<span class="star">&#9733;</span>' * (3 - r["score"])
        action_class = "buy" if sig["action"] == "BUY" else ("sell" if sig["action"] == "SELL" else "wait")

        trade_plan = ""
        if sig["entry"]:
            trade_plan = f"""
            <div class="trade-plan">
                <h4>Trade Plan</h4>
                <div class="metrics">
                    <div class="metric"><span class="label">Entry</span><span class="value">Rs. {sig["entry"]}</span></div>
                    <div class="metric"><span class="label">Stop-Loss</span><span class="value sl">Rs. {sig["stop_loss"]}</span></div>
                    <div class="metric"><span class="label">Target</span><span class="value target">Rs. {sig["target"]}</span></div>
                    <div class="metric"><span class="label">Risk</span><span class="value">{sig.get("risk_pct", "?")}% (R:R {sig["risk_reward"]})</span></div>
                </div>
            </div>"""

        stock_cards += f"""
        <div class="card {action_class}-card">
            <div class="card-header">
                <span class="badge {action_class}">{sig["action"]}</span>
                <span class="symbol">{r["symbol"]}</span>
            </div>
            <div class="card-body">
                <div class="info-row"><span>Pattern:</span> <strong>{r["pattern"]}</strong> ({r["bias"]})</div>
                <div class="info-row"><span>Detected:</span> {r["date"]}</div>
                <div class="info-row"><span>Current Price:</span> Rs. {r["close"]:.2f}</div>
                <div class="info-row"><span>Confidence:</span> {stars_html}</div>
                {trade_plan}
                <div class="reason">{sig["reason"]}</div>
            </div>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stock Pattern Scan - {today}</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
            background: #0f0f1a;
            color: #e0e0e0;
            padding: 20px;
            min-height: 100vh;
        }}
        .container {{ max-width: 1200px; margin: 0 auto; }}

        /* Header */
        .header {{
            text-align: center;
            padding: 30px 0;
            border-bottom: 1px solid #2a2a4a;
            margin-bottom: 30px;
        }}
        .header h1 {{
            font-size: 2rem;
            background: linear-gradient(135deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 8px;
        }}
        .header .date {{ color: #888; font-size: 0.95rem; }}
        .header .disclaimer {{
            color: #666;
            font-size: 0.8rem;
            margin-top: 8px;
            padding: 6px 16px;
            background: #1a1a2e;
            border-radius: 20px;
            display: inline-block;
        }}

        /* Section titles */
        .section-title {{
            font-size: 1.4rem;
            color: #fff;
            margin: 30px 0 16px;
            padding-bottom: 8px;
            border-bottom: 2px solid #2a2a4a;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-title .icon {{ font-size: 1.6rem; }}

        /* Tables */
        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 24px;
            background: #16162a;
            border-radius: 12px;
            overflow: hidden;
        }}
        th {{
            background: #1e1e3a;
            color: #aaa;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 0.75rem;
            letter-spacing: 0.5px;
            padding: 12px 16px;
            text-align: left;
        }}
        td {{
            padding: 10px 16px;
            border-bottom: 1px solid #1e1e3a;
            font-size: 0.9rem;
        }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background: #1a1a35; }}

        /* Action badges in table */
        td.buy {{ color: #4ade80; font-weight: 700; }}
        td.sell {{ color: #f87171; font-weight: 700; }}
        td.wait {{ color: #888; font-weight: 600; }}

        /* Cards */
        .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(360px, 1fr)); gap: 16px; margin-bottom: 30px; }}
        .card {{
            background: #16162a;
            border-radius: 12px;
            overflow: hidden;
            border: 1px solid #2a2a4a;
            transition: transform 0.2s, box-shadow 0.2s;
        }}
        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0,0,0,0.3);
        }}
        .buy-card {{ border-left: 4px solid #4ade80; }}
        .sell-card {{ border-left: 4px solid #f87171; }}
        .wait-card {{ border-left: 4px solid #666; }}

        .card-header {{
            padding: 14px 16px;
            display: flex;
            align-items: center;
            gap: 12px;
            background: #1a1a35;
        }}
        .badge {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 0.75rem;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .badge.buy {{ background: #064e3b; color: #4ade80; }}
        .badge.sell {{ background: #450a0a; color: #f87171; }}
        .badge.wait {{ background: #333; color: #aaa; }}
        .symbol {{ font-weight: 700; font-size: 1.1rem; color: #fff; }}

        .card-body {{ padding: 16px; }}
        .info-row {{ display: flex; justify-content: space-between; padding: 4px 0; font-size: 0.88rem; }}
        .info-row span:first-child {{ color: #888; }}

        .trade-plan {{
            background: #1a1a35;
            border-radius: 8px;
            padding: 12px;
            margin: 12px 0;
        }}
        .trade-plan h4 {{ color: #aaa; font-size: 0.8rem; text-transform: uppercase; margin-bottom: 10px; }}
        .metrics {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; }}
        .metric {{ display: flex; flex-direction: column; }}
        .metric .label {{ font-size: 0.7rem; color: #666; text-transform: uppercase; }}
        .metric .value {{ font-size: 0.95rem; font-weight: 600; color: #e0e0e0; }}
        .metric .value.sl {{ color: #f87171; }}
        .metric .value.target {{ color: #4ade80; }}

        .reason {{
            margin-top: 12px;
            padding: 10px;
            background: #1a1a35;
            border-radius: 6px;
            font-size: 0.82rem;
            color: #999;
            line-height: 1.5;
            border-left: 3px solid #2a2a4a;
        }}

        /* Stars */
        .star {{ color: #333; font-size: 1.1rem; }}
        .star.filled {{ color: #fbbf24; }}

        /* Guide section */
        .guide {{
            background: #16162a;
            border-radius: 12px;
            padding: 24px;
            margin-top: 30px;
        }}
        .guide h3 {{ color: #fff; margin-bottom: 16px; }}
        .guide h4 {{ color: #aaa; margin: 14px 0 6px; font-size: 0.9rem; }}
        .guide ul {{ padding-left: 20px; }}
        .guide li {{ color: #999; font-size: 0.85rem; padding: 3px 0; }}
        .guide li strong {{ color: #e0e0e0; }}

        .footer {{
            text-align: center;
            color: #555;
            font-size: 0.75rem;
            padding: 30px 0 10px;
            border-top: 1px solid #1e1e3a;
            margin-top: 30px;
        }}

        @media (max-width: 768px) {{
            .cards {{ grid-template-columns: 1fr; }}
            .metrics {{ grid-template-columns: 1fr; }}
            body {{ padding: 10px; }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Stock & Index Pattern Scanner</h1>
            <div class="date">Daily Scan Report - {today}</div>
            <div class="disclaimer">Educational tool only - not financial advice</div>
        </div>

        <!-- INDEX OPTIONS SIGNALS -->
        <div class="section-title"><span class="icon">📈</span> Index Options Signals</div>
        <table>
            <thead>
                <tr>
                    <th>Index</th><th>Interval</th><th>Pattern</th><th>Action</th>
                    <th>Strike</th><th>OTM Strike</th><th>Index SL</th><th>Index Target</th>
                </tr>
            </thead>
            <tbody>{index_rows}</tbody>
        </table>

        <div class="cards">{index_cards}</div>

        <!-- STOCK SIGNALS -->
        <div class="section-title"><span class="icon">📊</span> Stock Signals</div>
        <table>
            <thead>
                <tr>
                    <th>Stock</th><th>Pattern</th><th>Action</th>
                    <th>Entry</th><th>Stop-Loss</th><th>Target</th><th>Risk</th>
                </tr>
            </thead>
            <tbody>{stock_rows}</tbody>
        </table>

        <div class="cards">{stock_cards}</div>

        <!-- GUIDE -->
        <div class="guide">
            <h3>How to Use This Report</h3>
            <h4>Options Signals</h4>
            <ul>
                <li><strong>BUY CE</strong> - Buy Call option (bullish view)</li>
                <li><strong>BUY PE</strong> - Buy Put option (bearish view)</li>
                <li>Use <strong>OTM strike</strong> for cheaper premium, <strong>ATM</strong> for safer trades</li>
            </ul>
            <h4>Stock Signals</h4>
            <ul>
                <li><strong>BUY</strong> - Buy at next morning's open near entry price</li>
                <li><strong>SELL</strong> - Exit/short at next morning's open</li>
            </ul>
            <h4>Timeframes</h4>
            <ul>
                <li><strong>1d</strong> = Swing trade (1-5 days)</li>
                <li><strong>1h</strong> = Intraday (hours to 1 day)</li>
                <li><strong>15m</strong> = Scalping (minutes to hours)</li>
            </ul>
            <h4>Risk Management</h4>
            <ul>
                <li>Never risk more than 2% of capital on a single trade</li>
                <li>Always place stop-loss immediately after entry</li>
                <li>For options: max loss = premium paid</li>
                <li>Skip the trade if index gaps significantly at open</li>
            </ul>
        </div>

        <div class="footer">
            This is an educational tool. Past patterns do not guarantee future results. Always do your own research before trading.
        </div>
    </div>
</body>
</html>"""

    return html

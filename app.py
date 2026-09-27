"""
Streamlit UI for the Indian stock & index candlestick pattern detector.
Supports stocks, Nifty 50, Bank Nifty with options CE/PE suggestions.
Run with:  streamlit run app.py
"""
import streamlit as st
import plotly.graph_objects as go

from fetcher.get_ohlc import fetch_ohlc
from patterns.detect import scan_patterns
from indicators.confirm import rsi, volume_ratio, trend, score_pattern
from signals.generate import generate_signal
from signals.options import generate_option_signal, INDEX_NAMES
from llm.explain import explain_pattern

st.set_page_config(page_title="NSE Pattern Detector & Options Signals", layout="wide")
st.title("📊 Indian Stock & Index Pattern Detector")
st.caption("Educational tool only — not financial advice.")

# --- Input Section ---
col1, col2, col3, col4 = st.columns([2, 1, 1, 1])

PRESET_SYMBOLS = {
    "Custom": "",
    "RELIANCE.NS": "RELIANCE.NS",
    "TCS.NS": "TCS.NS",
    "INFY.NS": "INFY.NS",
    "SBIN.NS": "SBIN.NS",
    "HDFCBANK.NS": "HDFCBANK.NS",
    "NIFTY 50 (^NSEI)": "^NSEI",
    "BANK NIFTY (^NSEBANK)": "^NSEBANK",
}

preset = col1.selectbox("Select Stock / Index", list(PRESET_SYMBOLS.keys()), index=0)
if preset == "Custom":
    symbol = col1.text_input("Enter symbol", "RELIANCE.NS").strip().upper()
else:
    symbol = PRESET_SYMBOLS[preset]

period = col2.selectbox("Period", ["1mo", "3mo", "6mo", "1y"], index=1)
interval = col3.selectbox("Interval", ["1d", "1h", "15m"], index=0)

# Detect if this is an index symbol
is_index = symbol in INDEX_NAMES

# Validate symbol format
if symbol and not is_index and not (symbol.endswith(".NS") or symbol.endswith(".BO")):
    st.warning("⚠️ Symbol should end with `.NS` (NSE) or `.BO` (BSE), or use ^NSEI / ^NSEBANK for indices.")

if st.button("Analyze", type="primary"):
    if not symbol:
        st.error("Please enter a stock symbol.")
    else:
        try:
            # Intraday needs shorter period
            effective_period = period
            if interval in ["15m", "1h"] and period in ["6mo", "1y"]:
                effective_period = "1mo"
                st.info(f"Note: Using 1mo period for {interval} interval (yfinance limitation).")

            with st.spinner("Fetching data..."):
                df = fetch_ohlc(symbol, period=effective_period, interval=interval)

            patterns_found = scan_patterns(df)
            rsi_s = rsi(df)
            vol_s = volume_ratio(df)
            trend_s = trend(df)

            # Persist results in session state
            st.session_state["analysis"] = {
                "df": df,
                "patterns_found": patterns_found,
                "rsi_s": rsi_s,
                "vol_s": vol_s,
                "trend_s": trend_s,
                "symbol": symbol,
                "is_index": is_index,
                "interval": interval,
            }

        except Exception as e:
            st.error(f"Error: {e}")

# --- Render results from session state ---
if "analysis" in st.session_state:
    data = st.session_state["analysis"]
    df = data["df"]
    patterns_found = data["patterns_found"]
    rsi_s = data["rsi_s"]
    vol_s = data["vol_s"]
    trend_s = data["trend_s"]
    sym = data["symbol"]
    is_idx = data["is_index"]
    intv = data["interval"]

    display_name = INDEX_NAMES.get(sym, sym)

    # --- Candlestick chart ---
    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=display_name
    )])

    if not patterns_found.empty:
        for bias, color in [("bullish", "green"), ("bearish", "red"), ("neutral", "orange")]:
            subset = patterns_found[patterns_found["bias"] == bias]
            if subset.empty:
                continue
            marker_highs = df["High"].reindex(subset["date"]).values * 1.02
            fig.add_trace(go.Scatter(
                x=subset["date"],
                y=marker_highs,
                mode="markers",
                marker=dict(symbol="triangle-down" if bias == "bearish" else "triangle-up", size=10, color=color),
                name=f"{bias} pattern",
                text=subset["pattern"],
                hovertemplate="%{text}<extra></extra>",
            ))

    fig.update_layout(height=500, xaxis_rangeslider_visible=False, margin=dict(t=30, b=10))
    st.plotly_chart(fig, use_container_width=True)

    # --- Pattern table ---
    st.subheader("Detected Patterns")
    if patterns_found.empty:
        st.info("No patterns detected in this window.")
    else:
        rows = []
        for _, row in patterns_found.sort_values("date", ascending=False).head(15).iterrows():
            score, note = score_pattern(df, row, rsi_s, vol_s, trend_s)
            rows.append({
                "Date": row["date"].strftime("%Y-%m-%d %H:%M") if intv != "1d" else row["date"].strftime("%Y-%m-%d"),
                "Pattern": row["pattern"],
                "Bias": row["bias"],
                "Confidence": "★" * score + "☆" * (3 - score),
                "Why": note,
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

        best = patterns_found.sort_values("date", ascending=False).iloc[0]
        score, note = score_pattern(df, best, rsi_s, vol_s, trend_s)

        st.subheader(f"Most Recent Pattern: {best['pattern']} ({best['bias']})")
        st.write(note)

        # --- Trade Signal Section ---
        st.markdown("---")

        if is_idx:
            # OPTIONS SIGNAL for indices
            current_price = float(df["Close"].iloc[-1])
            option_signal = generate_option_signal(
                sym, current_price, best["pattern"], best["bias"], score, note
            )

            st.subheader(f"{option_signal['emoji']} Options Signal: {option_signal['action']}")

            if option_signal["suggested_strike"]:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric(f"{display_name} Level", f"₹{current_price:.2f}")
                m2.metric("Buy Option", f"{display_name} {option_signal['suggested_strike']} {option_signal['option_type']}")
                m3.metric("Index Stop-Loss", f"₹{option_signal['stop_loss_index']}")
                m4.metric("Index Target", f"₹{option_signal['target_index']}")

                st.caption(f"Cheaper alternative: {display_name} {option_signal['otm_strike']} {option_signal['option_type']} (OTM, lower premium)")

            if option_signal["action"] == "BUY CE":
                st.success(option_signal["reason"])
            elif option_signal["action"] == "BUY PE":
                st.error(option_signal["reason"])
            elif option_signal["action"] == "WATCH":
                st.warning(option_signal["reason"])
            else:
                st.info(option_signal["reason"])

        else:
            # STOCK SIGNAL
            signal = generate_signal(df, best, score, note)

            st.subheader(f"{signal['emoji']} Next-Day Trade Signal: {signal['action']}")

            if signal["entry"]:
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Entry Price", f"₹{signal['entry']}")
                m2.metric("Stop-Loss", f"₹{signal['stop_loss']}")
                m3.metric("Target", f"₹{signal['target']}")
                m4.metric("Risk", f"{signal.get('risk_pct', '?')}%", delta=f"R:R {signal['risk_reward']}")

            if signal["action"] == "BUY":
                st.success(signal["reason"])
            elif signal["action"] == "SELL":
                st.error(signal["reason"])
            elif signal["action"] == "WATCH":
                st.warning(signal["reason"])
            else:
                st.info(signal["reason"])

        # Explain with AI
        if st.button("Explain with AI"):
            with st.spinner("Asking Gemini..."):
                explanation = explain_pattern(sym, best["pattern"], best["bias"], note)
            st.info(explanation)

st.markdown("---")
st.caption("Patterns are detected with rule-based logic (pandas), not by an LLM reading the chart image — this keeps detection accurate. The AI is used only to explain the result in plain language.")

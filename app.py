"""
Streamlit UI for the Indian stock candlestick pattern detector.
Run with:  streamlit run app.py
"""
import streamlit as st
import plotly.graph_objects as go

from fetcher.get_ohlc import fetch_ohlc
from patterns.detect import scan_patterns
from indicators.confirm import rsi, volume_ratio, trend, score_pattern
from llm.explain import explain_pattern

st.set_page_config(page_title="NSE Candlestick Pattern Detector", layout="wide")
st.title("📊 Indian Stock Candlestick Pattern Detector")
st.caption("Educational tool only — not financial advice.")

col1, col2, col3 = st.columns([2, 1, 1])
symbol = col1.text_input("NSE Symbol (e.g. RELIANCE.NS, TCS.NS, INFY.NS)", "RELIANCE.NS").strip().upper()
period = col2.selectbox("Period", ["1mo", "3mo", "6mo", "1y"], index=1)
interval = col3.selectbox("Interval", ["1d", "1h"], index=0)

# Validate symbol format
if symbol and not (symbol.endswith(".NS") or symbol.endswith(".BO")):
    st.warning("⚠️ Symbol should end with `.NS` (NSE) or `.BO` (BSE). Example: `RELIANCE.NS`")

if st.button("Analyze", type="primary"):
    if not symbol:
        st.error("Please enter a stock symbol.")
    else:
        try:
            with st.spinner("Fetching data..."):
                df = fetch_ohlc(symbol, period=period, interval=interval)

            patterns_found = scan_patterns(df)
            rsi_s = rsi(df)
            vol_s = volume_ratio(df)
            trend_s = trend(df)

            # Persist results in session state so the "Explain with AI" button works
            st.session_state["analysis"] = {
                "df": df,
                "patterns_found": patterns_found,
                "rsi_s": rsi_s,
                "vol_s": vol_s,
                "trend_s": trend_s,
                "symbol": symbol,
            }

        except Exception as e:
            st.error(f"Error: {e}")

# --- Render results from session state (persists across re-runs) ---
if "analysis" in st.session_state:
    data = st.session_state["analysis"]
    df = data["df"]
    patterns_found = data["patterns_found"]
    rsi_s = data["rsi_s"]
    vol_s = data["vol_s"]
    trend_s = data["trend_s"]
    sym = data["symbol"]

    # --- Candlestick chart with pattern markers ---
    fig = go.Figure(data=[go.Candlestick(
        x=df.index, open=df["Open"], high=df["High"],
        low=df["Low"], close=df["Close"], name=sym
    )])

    if not patterns_found.empty:
        for bias, color in [("bullish", "green"), ("bearish", "red"), ("neutral", "orange")]:
            subset = patterns_found[patterns_found["bias"] == bias]
            if subset.empty:
                continue
            # Use reindex to safely align pattern dates with the price data
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
                "Date": row["date"].strftime("%Y-%m-%d"),
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
        from signals.generate import generate_signal
        signal = generate_signal(df, best, score, note)

        st.markdown("---")
        st.subheader(f"{signal['emoji']} Next-Day Trade Signal: {signal['action']}")

        if signal["entry"]:
            # Show entry, stop-loss, target as metrics
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

        # "Explain with AI" button — now works because it's NOT nested inside
        # another button. Results are read from st.session_state instead.
        if st.button("Explain with AI"):
            with st.spinner("Asking Gemini..."):
                explanation = explain_pattern(sym, best["pattern"], best["bias"], note)
            st.info(explanation)

st.markdown("---")
st.caption("Patterns are detected with rule-based logic (pandas), not by an LLM reading the chart image — this keeps detection accurate. The AI is used only to explain the result in plain language.")


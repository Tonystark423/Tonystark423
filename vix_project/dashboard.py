"""
dashboard.py — Stark Financial Sentiment Dashboard
Combines live VIX, Finnhub headlines, VADER scoring, and gauge UI.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from news_fetcher import fetch_market_news, fetch_company_news, fetch_vix
from sentiment_engine import calculate_greed_score, score_to_label
from ledger_sync import append_snapshot, read_ledger

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="Stark Financial — Sentinel Dashboard",
    layout="wide",
)

st.title("Stark Financial Holdings LLC")
st.subheader("Sentinel Dashboard — VIX & Market Sentiment")

# ---------------------------------------------------------------------------
# Gauge helper
# ---------------------------------------------------------------------------

def build_gauge(score: float) -> go.Figure:
    display_value = (score + 1) * 50
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=display_value,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Market Sentiment Index", "font": {"size": 22}},
        gauge={
            "axis": {"range": [0, 100], "tickwidth": 1, "tickcolor": "darkblue"},
            "bar": {"color": "black"},
            "bgcolor": "white",
            "borderwidth": 2,
            "bordercolor": "gray",
            "steps": [
                {"range": [0, 30],   "color": "red"},
                {"range": [30, 45],  "color": "orange"},
                {"range": [45, 55],  "color": "yellow"},
                {"range": [55, 70],  "color": "lightgreen"},
                {"range": [70, 100], "color": "green"},
            ],
            "threshold": {
                "line": {"color": "red", "width": 4},
                "thickness": 0.75,
                "value": (40 + 1) * 50 / 100 * 100,  # VIX=40 equivalent marker
            },
        },
    ))
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig

# ---------------------------------------------------------------------------
# Sidebar controls
# ---------------------------------------------------------------------------
st.sidebar.header("Controls")
news_category = st.sidebar.selectbox("News Category", ["general", "forex", "crypto", "merger"])
headline_limit = st.sidebar.slider("Max Headlines", 10, 100, 30)
ticker_input = st.sidebar.text_input("Company Ticker (optional)", placeholder="e.g. AAPL")
auto_log = st.sidebar.checkbox("Auto-log snapshot to ledger", value=True)

# ---------------------------------------------------------------------------
# Main panel
# ---------------------------------------------------------------------------
col_gauge, col_vix = st.columns([2, 1])

if st.button("Refresh Sentinel"):
    with st.spinner("Fetching live data..."):
        try:
            # Fetch data
            if ticker_input.strip():
                headlines = fetch_company_news(ticker_input.strip(), limit=headline_limit)
            else:
                headlines = fetch_market_news(category=news_category, limit=headline_limit)

            vix = fetch_vix()
            score = calculate_greed_score(headlines)
            label, color = score_to_label(score)

            # Gauge
            with col_gauge:
                st.plotly_chart(build_gauge(score), use_container_width=True)

            # VIX indicator
            with col_vix:
                st.metric("VIX", f"{vix:.2f}" if vix else "N/A",
                          delta="ALERT" if vix and vix >= 40 else None,
                          delta_color="inverse")
                st.metric("Sentiment Score", f"{score:+.4f}")
                st.markdown(f"**Status:** :{color}[{label}]")
                st.caption(f"Headlines analyzed: {len(headlines)}")

            # Alert banner
            if vix and vix >= 40:
                st.error(f"SENTINEL ALERT: VIX = {vix:.2f} — threshold of 40 breached!")
            if score < -0.2:
                st.warning(f"SENTINEL ALERT: Sentiment in {label} territory ({score:+.4f})")

            # Ledger logging
            if auto_log:
                append_snapshot(vix, score, label, len(headlines))
                st.success("Snapshot logged to ledger.")

            # Headlines preview
            with st.expander("Headlines Used"):
                for h in headlines:
                    st.write(f"- {h}")

        except Exception as exc:
            st.error(f"Error fetching data: {exc}")

# ---------------------------------------------------------------------------
# Ledger history table
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Ledger Snapshot History")

history = read_ledger(tail=20)
if history:
    df = pd.DataFrame(history)
    st.dataframe(df, use_container_width=True)
else:
    st.info("No snapshots logged yet. Click 'Refresh Sentinel' to record the first entry.")

"""
dashboard.py — Stark Financial Sentiment Dashboard
Combines live VIX, Finnhub headlines, VADER scoring, and gauge UI.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from news_fetcher import fetch_market_news, fetch_company_news, fetch_vix
from sentiment_engine import calculate_greed_score, score_to_label
from ledger_sync import append_snapshot, read_ledger, process_derisking_sale

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
# Profit Taker Calculator
# ---------------------------------------------------------------------------
st.markdown("---")
st.subheader("Profit Taker Calculator")
st.caption("Calculates how many shares to sell to fully recover your initial principal, leaving the remainder as a zero-cost position.")

pt_col1, pt_col2 = st.columns(2)

with pt_col1:
    pt_ticker = st.text_input("Ticker / Position Label", value="VIXY", help="Must match an entry in holdings.csv to log the sale.")
    pt_shares = st.number_input("Shares Owned", min_value=0.01, value=100.0, step=1.0)
    pt_cost_basis = st.number_input("Avg Cost Basis ($ per share)", min_value=0.01, value=20.00, step=0.01, format="%.2f")

with pt_col2:
    pt_current_price = st.number_input("Current Price ($ per share)", min_value=0.01, value=31.15, step=0.01, format="%.2f")
    pt_mmf_yield = st.number_input("MMF Reinvestment Yield (%)", min_value=0.0, value=3.58, step=0.01, format="%.2f",
                                    help="e.g. VMFXX current yield. Used to estimate annual income on parked proceeds.")

if st.button("Calculate"):
    total_cost        = pt_shares * pt_cost_basis
    total_value       = pt_shares * pt_current_price
    unrealized_gain   = total_value - total_cost
    gain_pct          = (unrealized_gain / total_cost) * 100

    shares_to_sell    = total_cost / pt_current_price          # recover exactly what you paid
    shares_to_sell    = min(shares_to_sell, pt_shares)         # can't sell more than you own
    proceeds          = shares_to_sell * pt_current_price
    remaining_shares  = pt_shares - shares_to_sell
    remaining_value   = remaining_shares * pt_current_price
    annual_mmf_income = proceeds * (pt_mmf_yield / 100)

    # Signal: High VIX + Low Sentiment = contrarian buy signal
    buy_signal = False
    buy_signal_note = ""
    try:
        last = read_ledger(tail=1)
        if last:
            last_vix   = float(last[-1]["vix"]) if last[-1]["vix"] != "N/A" else 0.0
            last_score = float(last[-1]["sentiment_score"])
            if last_vix >= 30 and last_score < -0.1:
                buy_signal = True
                buy_signal_note = f"VIX={last_vix:.1f}, Sentiment={last_score:+.4f} — contrarian buy conditions present."
    except Exception:
        pass

    r1, r2, r3 = st.columns(3)
    r1.metric("Total Cost Basis",   f"${total_cost:,.2f}")
    r1.metric("Total Market Value", f"${total_value:,.2f}")
    r2.metric("Unrealized Gain",    f"${unrealized_gain:,.2f}", delta=f"{gain_pct:.1f}%")
    r2.metric("Shares to Sell",     f"{shares_to_sell:.4f}", help="Sells just enough to recover your full principal.")
    r3.metric("Sale Proceeds",      f"${proceeds:,.2f}")
    r3.metric("Remaining Shares",   f"{remaining_shares:.4f}", help="These shares cost you nothing — pure upside.")

    st.markdown("---")
    mmf_col, reinvest_col = st.columns(2)
    with mmf_col:
        st.markdown("**Yield Arbitrage (MMF Park)**")
        st.write(f"Park **${proceeds:,.2f}** in MMF at **{pt_mmf_yield:.2f}%**")
        st.write(f"Estimated annual income: **${annual_mmf_income:,.2f}**")
    with reinvest_col:
        st.markdown("**Contrarian Equity Signal**")
        if buy_signal:
            st.success(f"BUY SIGNAL active — {buy_signal_note}")
            voo_shares = proceeds / pt_current_price
            st.write(f"Proceeds could buy ~**{voo_shares:.2f} shares** of an index fund at current price.")
        else:
            st.info("No active buy signal from last sentinel snapshot. Run 'Refresh Sentinel' first.")

    st.markdown("---")
    st.markdown("**Log Partial Sale to Ledger**")
    st.caption(f"Will sell {shares_to_sell:.4f} shares of **{pt_ticker}** @ ${pt_current_price:.2f} and zero the remaining cost basis.")
    if st.button("Log De-Risking Sale to Holdings"):
        try:
            msg = process_derisking_sale(pt_ticker, shares_to_sell, pt_current_price)
            st.success(msg)
        except ValueError as e:
            st.error(str(e))

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

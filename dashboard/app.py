import streamlit as st
from sentiment import calculate_greed_score
from gauge import display_sentiment_gauge

st.set_page_config(page_title="Stark Financial — Sentiment Dashboard", layout="centered")

st.title("Stark Financial Holdings LLC")
st.subheader("Market Sentiment Dashboard")

st.markdown("### Enter Headlines")
raw_input = st.text_area(
    "Paste one headline per line:",
    height=180,
    placeholder="Market plunges as inflation fears grip Wall Street\nTech stocks surge on strong earnings...",
)

if st.button("Analyze"):
    headlines = [line.strip() for line in raw_input.splitlines() if line.strip()]

    if not headlines:
        st.warning("Please enter at least one headline.")
    else:
        score = calculate_greed_score(headlines)

        st.plotly_chart(display_sentiment_gauge(score), use_container_width=True)

        col1, col2 = st.columns(2)
        col1.metric("Compound Score", f"{score:+.4f}", help="VADER compound: -1.0 = Extreme Fear, +1.0 = Extreme Greed")

        if score < -0.2:
            status, color = "EXTREME FEAR", "red"
        elif score < 0.0:
            status, color = "FEAR", "orange"
        elif score <= 0.2:
            status, color = "NEUTRAL", "gray"
        elif score <= 0.5:
            status, color = "GREED", "green"
        else:
            status, color = "EXTREME GREED", "darkgreen"

        col2.markdown(f"**Market Status:** :{color}[{status}]")

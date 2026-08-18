import plotly.graph_objects as go


def display_sentiment_gauge(score: float) -> go.Figure:
    """
    Renders a Plotly gauge for a VADER compound score in [-1.0, +1.0].
    Mapped to 0-100 scale: display_value = (score + 1) * 50

    Color bands:
        0  - 30  : Extreme Fear  (red)
        30 - 45  : Fear          (orange)
        45 - 55  : Neutral       (yellow)
        55 - 70  : Greed         (light green)
        70 - 100 : Extreme Greed (green)
    """
    display_value = (score + 1) * 50

    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=display_value,
        domain={"x": [0, 1], "y": [0, 1]},
        title={"text": "Market Sentiment Index", "font": {"size": 24}},
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
                "value": 90,
            },
        },
    ))

    fig.update_layout(height=300, margin=dict(l=20, r=20, t=50, b=20))
    return fig

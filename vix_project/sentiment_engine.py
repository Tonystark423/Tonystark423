"""
sentiment_engine.py — VADER Sentiment Logic
Scores a list of headlines and returns a compound greed/fear score.
"""

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

_analyzer = SentimentIntensityAnalyzer()


def calculate_greed_score(headlines: list[str]) -> float:
    """
    Analyze headlines and return an aggregated VADER compound score.

    Returns:
        float in [-1.0, +1.0]
        -1.0 = Extreme Fear | 0.0 = Neutral | +1.0 = Extreme Greed
    """
    if not headlines:
        return 0.0

    scores = [_analyzer.polarity_scores(h)["compound"] for h in headlines]
    return round(sum(scores) / len(scores), 4)


def score_to_label(score: float) -> tuple[str, str]:
    """
    Map a compound score to a (label, color) pair for UI display.

    Returns:
        Tuple of (status_label, css_color_name)
    """
    if score < -0.2:
        return "EXTREME FEAR", "red"
    elif score < 0.0:
        return "FEAR", "orange"
    elif score <= 0.2:
        return "NEUTRAL", "gray"
    elif score <= 0.5:
        return "GREED", "green"
    else:
        return "EXTREME GREED", "darkgreen"

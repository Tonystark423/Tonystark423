from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import pandas as pd


def calculate_greed_score(headlines):
    """
    Analyzes a list of headlines and returns an aggregated sentiment score.
    -1.0 = Extreme Fear | 0.0 = Neutral | +1.0 = Extreme Greed
    """
    analyzer = SentimentIntensityAnalyzer()
    scores = []

    if not headlines:
        return 0.0

    for text in headlines:
        # VADER returns a dict: {'neg', 'neu', 'pos', 'compound'}
        # We want the 'compound' score as our primary metric
        vs = analyzer.polarity_scores(text)
        scores.append(vs['compound'])

    avg_score = sum(scores) / len(scores)
    return round(avg_score, 4)


# --- Quick Test ---
if __name__ == "__main__":
    sample_news = [
        "Market plunges as inflation fears grip Wall Street",
        "Tech stocks see massive sell-off amid rate hike concerns",
        "Vanguard reports record inflows as investors stay bullish",
        "Analysts predict explosive growth for semiconductor sector",
    ]

    score = calculate_greed_score(sample_news)
    print(f"Current Sentiment Score: {score}")

    if score < -0.2:
        print("Status: Market is in FEAR")
    elif score > 0.2:
        print("Status: Market is in GREED")
    else:
        print("Status: Market is NEUTRAL")

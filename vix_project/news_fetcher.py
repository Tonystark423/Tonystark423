"""
news_fetcher.py — Finnhub API Logic
Fetches recent market news headlines for sentiment analysis.
"""

import os
import requests
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
BASE_URL = "https://finnhub.io/api/v1"


def _headers() -> dict:
    return {"X-Finnhub-Token": FINNHUB_API_KEY}


def fetch_market_news(category: str = "general", limit: int = 50) -> list[str]:
    """
    Fetch recent market news headlines from Finnhub.

    Args:
        category: "general" | "forex" | "crypto" | "merger"
        limit:    Max number of headlines to return.

    Returns:
        List of headline strings.
    """
    url = f"{BASE_URL}/news"
    params = {"category": category}
    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    resp.raise_for_status()

    articles = resp.json()
    headlines = [a["headline"] for a in articles if a.get("headline")]
    return headlines[:limit]


def fetch_company_news(ticker: str, days_back: int = 7, limit: int = 30) -> list[str]:
    """
    Fetch recent news headlines for a specific ticker.

    Args:
        ticker:    Stock symbol (e.g. "AAPL").
        days_back: How many calendar days of news to pull.
        limit:     Max headlines to return.

    Returns:
        List of headline strings.
    """
    today = datetime.today()
    from_date = (today - timedelta(days=days_back)).strftime("%Y-%m-%d")
    to_date = today.strftime("%Y-%m-%d")

    url = f"{BASE_URL}/company-news"
    params = {"symbol": ticker, "from": from_date, "to": to_date}
    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    resp.raise_for_status()

    articles = resp.json()
    headlines = [a["headline"] for a in articles if a.get("headline")]
    return headlines[:limit]


def fetch_vix(symbol: str = "VIX") -> float | None:
    """
    Fetch the current VIX (or any index quote) from Finnhub.

    Args:
        symbol: Finnhub symbol for VIX. Try "VIX" or "CBOE:VIX".

    Returns:
        Current price as float, or None on failure.
    """
    url = f"{BASE_URL}/quote"
    params = {"symbol": symbol}
    resp = requests.get(url, headers=_headers(), params=params, timeout=10)
    resp.raise_for_status()

    data = resp.json()
    return data.get("c")  # 'c' = current price

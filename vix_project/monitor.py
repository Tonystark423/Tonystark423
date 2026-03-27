"""
monitor.py — VIX Sentinel
Polls VIX at a set interval and triggers alerts when thresholds are breached.
"""

import time
import logging
from datetime import datetime
from news_fetcher import fetch_vix
from sentiment_engine import calculate_greed_score, score_to_label
from news_fetcher import fetch_market_news

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# --- Alert thresholds ---
VIX_ALERT_THRESHOLD = 40.0       # Trigger alert if VIX crosses this level
SENTIMENT_FEAR_THRESHOLD = -0.2  # Trigger alert if sentiment drops below this
POLL_INTERVAL_SECONDS = 300      # Check every 5 minutes


def check_vix_alert(vix: float) -> bool:
    if vix is not None and vix >= VIX_ALERT_THRESHOLD:
        log.warning("SENTINEL ALERT: VIX = %.2f — crossed threshold of %.1f", vix, VIX_ALERT_THRESHOLD)
        return True
    return False


def check_sentiment_alert(score: float) -> bool:
    if score <= SENTIMENT_FEAR_THRESHOLD:
        label, _ = score_to_label(score)
        log.warning("SENTINEL ALERT: Sentiment = %+.4f (%s)", score, label)
        return True
    return False


def run_sentinel(poll_interval: int = POLL_INTERVAL_SECONDS):
    """
    Main sentinel loop. Polls VIX and sentiment continuously.
    Press Ctrl+C to stop.
    """
    log.info("VIX Sentinel started. Poll interval: %ds. VIX threshold: %.1f", poll_interval, VIX_ALERT_THRESHOLD)

    while True:
        try:
            vix = fetch_vix()
            headlines = fetch_market_news(limit=30)
            score = calculate_greed_score(headlines)
            label, _ = score_to_label(score)

            log.info("VIX=%.2f | Sentiment=%+.4f (%s) | Headlines=%d", vix or 0.0, score, label, len(headlines))

            check_vix_alert(vix or 0.0)
            check_sentiment_alert(score)

        except Exception as exc:
            log.error("Sentinel poll failed: %s", exc)

        time.sleep(poll_interval)


if __name__ == "__main__":
    run_sentinel()

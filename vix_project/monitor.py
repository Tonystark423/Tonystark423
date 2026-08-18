"""
monitor.py — VIX Sentinel
Polls VIX at a set interval and triggers alerts when thresholds are breached.

Alerts fired via Telegram. Requires in .env:
    TELEGRAM_BOT_TOKEN=<your bot token>
    TELEGRAM_CHAT_ID=<your chat id>
"""

import os
import time
import logging
import requests
from dotenv import load_dotenv
from news_fetcher import fetch_vix, fetch_market_news
from sentiment_engine import calculate_greed_score, score_to_label

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
VIX_HIGH_THRESHOLD   = 40.0   # Spike alert — extreme fear
LOW_VIX_THRESHOLD    = 19.0   # Re-entry alert — market calm
VIX_RESET_BUFFER     = 2.0    # VIX must climb back above LOW + buffer to re-arm
SENTIMENT_FEAR_THRESHOLD = -0.2
POLL_INTERVAL_SECONDS    = 300  # 5 minutes

# ---------------------------------------------------------------------------
# Telegram
# ---------------------------------------------------------------------------
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID   = os.getenv("TELEGRAM_CHAT_ID")


def send_telegram(message: str) -> None:
    """Send a message via Telegram bot. Logs a warning if credentials are missing."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log.warning("Telegram credentials not set — message not sent: %s", message)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)
        resp.raise_for_status()
        log.info("Telegram alert sent.")
    except Exception as exc:
        log.error("Telegram send failed: %s", exc)

# ---------------------------------------------------------------------------
# Alert checks
# ---------------------------------------------------------------------------

def check_vix_spike(vix: float) -> bool:
    """Alert when VIX crosses above the high threshold."""
    if vix >= VIX_HIGH_THRESHOLD:
        msg = (
            f"*SENTINEL ALERT — VIX SPIKE*\n"
            f"Current VIX: `{vix:.2f}`\n"
            f"Threshold: `{VIX_HIGH_THRESHOLD}`\n"
            f"Extreme fear conditions detected."
        )
        log.warning("SENTINEL ALERT: VIX = %.2f — spike threshold breached.", vix)
        send_telegram(msg)
        return True
    return False


def check_sentiment_alert(score: float) -> bool:
    """Alert when sentiment drops into fear territory."""
    if score <= SENTIMENT_FEAR_THRESHOLD:
        label, _ = score_to_label(score)
        msg = (
            f"*SENTINEL ALERT — SENTIMENT*\n"
            f"Score: `{score:+.4f}` ({label})\n"
            f"Market sentiment has entered fear territory."
        )
        log.warning("SENTINEL ALERT: Sentiment = %+.4f (%s)", score, label)
        send_telegram(msg)
        return True
    return False


def check_reentry(vix: float, state: dict) -> None:
    """
    Fire a one-shot re-entry alert when VIX drops below LOW_VIX_THRESHOLD.
    Resets once VIX climbs back above LOW_VIX_THRESHOLD + VIX_RESET_BUFFER.

    Args:
        vix:   Current VIX level.
        state: Mutable dict carrying {'sent_reentry_alert': bool} across calls.
    """
    if vix < LOW_VIX_THRESHOLD and not state["sent_reentry_alert"]:
        msg = (
            f"*VIX RE-ENTRY ALERT*\n"
            f"Current VIX: `{vix:.2f}`\n"
            f"Market has stabilized. Consider reloading the 'Fear' hedge "
            f"with your VOO/VMFXX profits."
        )
        log.info("RE-ENTRY ALERT: VIX = %.2f — below calm threshold of %.1f", vix, LOW_VIX_THRESHOLD)
        send_telegram(msg)
        state["sent_reentry_alert"] = True

    elif vix > (LOW_VIX_THRESHOLD + VIX_RESET_BUFFER):
        # Re-arm once VIX climbs back up
        if state["sent_reentry_alert"]:
            log.info("Re-entry alert re-armed (VIX = %.2f).", vix)
        state["sent_reentry_alert"] = False

# ---------------------------------------------------------------------------
# Main sentinel loop
# ---------------------------------------------------------------------------

def run_sentinel(poll_interval: int = POLL_INTERVAL_SECONDS) -> None:
    """
    Polls VIX and sentiment on a fixed interval.
    Press Ctrl+C to stop.
    """
    log.info(
        "VIX Sentinel started. Poll interval: %ds | High threshold: %.1f | Re-entry threshold: %.1f",
        poll_interval, VIX_HIGH_THRESHOLD, LOW_VIX_THRESHOLD,
    )

    reentry_state = {"sent_reentry_alert": False}

    while True:
        try:
            vix       = fetch_vix() or 0.0
            headlines = fetch_market_news(limit=30)
            score     = calculate_greed_score(headlines)
            label, _  = score_to_label(score)

            log.info(
                "VIX=%.2f | Sentiment=%+.4f (%s) | Headlines=%d",
                vix, score, label, len(headlines),
            )

            check_vix_spike(vix)
            check_sentiment_alert(score)
            check_reentry(vix, reentry_state)

        except Exception as exc:
            log.error("Sentinel poll failed: %s", exc)

        time.sleep(poll_interval)


if __name__ == "__main__":
    run_sentinel()

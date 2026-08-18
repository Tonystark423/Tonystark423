"""
status_check.py — Aggregated status report for the Telegram bot.
Returns a Markdown-formatted string covering VIX, sentiment, and holdings.
"""

from datetime import datetime, timezone
from news_fetcher import fetch_vix, fetch_market_news
from sentiment_engine import calculate_greed_score, score_to_label
from ledger_sync import read_holdings, read_ledger


def get_status() -> str:
    """
    Build a full Markdown status report.
    Called by the Telegram bot's /status command.

    Returns:
        Markdown string safe for Telegram parse_mode='Markdown'.
    """
    lines = [f"*Stark Financial — Sentinel Report*", f"_{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_", ""]

    # --- VIX ---
    try:
        vix = fetch_vix()
        if vix is not None:
            vix_flag = " ⚠️ SPIKE" if vix >= 40 else (" ✅ CALM" if vix < 19 else "")
            lines.append(f"*VIX:* `{vix:.2f}`{vix_flag}")
        else:
            lines.append("*VIX:* `unavailable`")
    except Exception as exc:
        lines.append(f"*VIX:* error — {exc}")

    # --- Sentiment ---
    try:
        headlines = fetch_market_news(limit=30)
        score = calculate_greed_score(headlines)
        label, _ = score_to_label(score)
        lines.append(f"*Sentiment:* `{score:+.4f}` ({label})")
        lines.append(f"*Headlines analyzed:* {len(headlines)}")
    except Exception as exc:
        lines.append(f"*Sentiment:* error — {exc}")

    lines.append("")

    # --- Holdings ---
    holdings = read_holdings()
    if holdings:
        lines.append("*Holdings:*")
        for row in holdings:
            cost = float(row["Avg_Price"])
            cost_str = "HOUSE MONEY" if cost == 0.0 else f"${cost:.2f}"
            lines.append(f"  • `{row['Ticker']}` — {float(row['Shares']):.4f} shares @ {cost_str}")
    else:
        lines.append("*Holdings:* none recorded")

    lines.append("")

    # --- Last ledger snapshot ---
    last = read_ledger(tail=1)
    if last and last[-1].get("sentiment_label") != "SALE":
        snap = last[-1]
        lines.append(f"*Last snapshot:* {snap['timestamp'][:16]}")
    else:
        lines.append("*Last snapshot:* none")

    return "\n".join(lines)

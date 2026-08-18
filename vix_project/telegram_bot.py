"""
telegram_bot.py — Stark Financial Telegram Bot
Commands:
  /status  — Full VIX + sentiment + holdings report
  /vix     — Current VIX price only
"""

import os
import telebot  # pip install pyTelegramBotAPI
import yfinance as yf
from dotenv import load_dotenv
from status_check import get_status

load_dotenv()

TOKEN       = os.getenv("TELEGRAM_BOT_TOKEN")
ALLOWED_ID  = os.getenv("TELEGRAM_CHAT_ID")

bot = telebot.TeleBot(TOKEN)


def _authorized(message) -> bool:
    """Return True only if the message comes from the configured chat ID."""
    return str(message.chat.id) == ALLOWED_ID


@bot.message_handler(commands=["status"])
def send_status(message):
    if not _authorized(message):
        bot.reply_to(message, "Unauthorized.")
        return
    try:
        report = get_status()
        bot.reply_to(message, report, parse_mode="Markdown")
    except Exception as exc:
        bot.reply_to(message, f"Error generating report: {exc}")


@bot.message_handler(commands=["vix"])
def send_vix(message):
    if not _authorized(message):
        bot.reply_to(message, "Unauthorized.")
        return
    try:
        price = yf.Ticker("^VIX").fast_info["last_price"]
        bot.reply_to(message, f"Current VIX: `{price:.2f}`", parse_mode="Markdown")
    except Exception as exc:
        bot.reply_to(message, f"Error fetching VIX: {exc}")


if __name__ == "__main__":
    print("Bot is online and listening...")
    bot.infinity_polling()

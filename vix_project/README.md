# Stark Financial Holdings LLC — VIX Sentinel System

A automated market monitoring and position management toolkit.
Runs headless, pushes Telegram alerts, and tracks holdings in CSV ledgers.

---

## Architecture

```
vix_project/
├── news_fetcher.py     Finnhub API — VIX quote, market/company headlines
├── sentiment_engine.py VADER sentiment scorer (-1.0 fear → +1.0 greed)
├── monitor.py          Headless sentinel loop — polls every 5 min, fires alerts
├── dashboard.py        Streamlit UI — gauge, profit taker, ledger history
├── ledger_sync.py      holdings.csv + ledger_snapshots.csv writer/reader
├── status_check.py     Aggregates VIX + sentiment + holdings → Markdown report
├── telegram_bot.py     Telegram bot — /status, /vix commands
├── .env.example        Environment variable template
└── requirements.txt    Python dependencies
```

### Data files (git-ignored, created on first run)
```
holdings.csv            Current positions: Ticker, Shares, Avg_Price, Notes
ledger_snapshots.csv    Timestamped audit log: VIX, sentiment, sales
```

---

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
```

Edit `.env`:
```
FINNHUB_API_KEY=...       # finnhub.io → Dashboard → API Key
TELEGRAM_BOT_TOKEN=...    # @BotFather on Telegram → /newbot
TELEGRAM_CHAT_ID=...      # @userinfobot on Telegram → your ID
```

### 3. Seed your first position (one-time)
```python
from ledger_sync import add_holding
add_holding("VIXY", shares=100.0, avg_price=20.00)
```

---

## Running the system

### Streamlit Dashboard (interactive)
```bash
streamlit run dashboard.py
```
Opens at `http://localhost:8501`. Features:
- Live sentiment gauge (VADER + Finnhub headlines)
- VIX metric with spike alert banner
- **Profit Taker Calculator** — computes exact shares to sell to recover principal
- **Log De-Risking Sale** button — zeroes remaining cost basis in `holdings.csv`
- Ledger snapshot history table

### Headless Sentinel (background monitor)
```bash
python monitor.py
```
Polls every 5 minutes. Sends Telegram alerts for:

| Condition | Threshold | Alert type |
|---|---|---|
| VIX spike | ≥ 40 | Push immediately |
| Sentiment fear | ≤ -0.2 | Push immediately |
| VIX re-entry | < 19.0 | Push once; re-arms when VIX > 21.0 |

### Telegram Bot (interactive queries)
```bash
python telegram_bot.py
```

| Command | Response |
|---|---|
| `/status` | Full report: VIX, sentiment, holdings, last snapshot |
| `/vix` | Current VIX price only |

To run as a systemd service (so it survives reboots):
```bash
sudo systemctl start bot_control
sudo journalctl -u bot_control -f   # live log
```

---

## Key concepts

### Profit Taker formula
```
shares_to_sell = total_cost_basis / current_price
```
Selling exactly this many shares returns 100% of your initial capital.
The remaining shares have a $0.00 cost basis — "House Money."

### Sentiment score
VADER compound score averaged across the latest 30 market headlines.
Mapped to a 0–100 gauge for display:
```
display_value = (compound_score + 1) * 50
```

| Score range | Label | Gauge color |
|---|---|---|
| < -0.2 | Extreme Fear | Red |
| -0.2 – 0.0 | Fear | Orange |
| 0.0 – 0.2 | Neutral | Yellow |
| 0.2 – 0.5 | Greed | Light green |
| > 0.5 | Extreme Greed | Green |

### Contrarian buy signal
Triggered in the dashboard when the last sentinel snapshot shows:
- VIX ≥ 30 **and** sentiment < -0.1

High fear + elevated volatility historically precedes mean reversion.

---

## Ledger files

### `holdings.csv`
| Column | Description |
|---|---|
| Ticker | Position label (e.g. VIXY, VOO) |
| Shares | Current share count |
| Avg_Price | Cost basis per share (`0.00` = House Money) |
| Notes | Auto-stamped on de-risking sale |

### `ledger_snapshots.csv`
| Column | Description |
|---|---|
| timestamp | UTC ISO-8601 |
| vix | VIX at time of snapshot |
| sentiment_score | VADER compound |
| sentiment_label | FEAR / NEUTRAL / GREED / SALE |
| headline_count | Number of headlines scored |
| notes | Free text; sale entries include full trade detail |

---

## Security notes
- The Telegram bot rejects all messages not from `TELEGRAM_CHAT_ID`
- `.env` is gitignored — credentials never touch the repository
- `holdings.csv` and `ledger_snapshots.csv` are gitignored — positions stay local
- Never store SSNs, EINs, or full account numbers in any file here

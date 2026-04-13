"""CoinStats API integration — live crypto price feed.

Fetches current prices from the CoinStats OpenAPI and updates
estimated_value for all Cryptocurrency assets in the ledger.

Configuration (.env):
    COINSTATS_API_KEY=<your-key>   # required
    COINSTATS_CURRENCY=USD          # optional, default USD

Usage:
    from coinstats import refresh_crypto_prices, fetch_prices
    prices  = fetch_prices()                   # {symbol: price_float}
    updated = refresh_crypto_prices(conn)      # list of update dicts
"""

import json
import os
import urllib.error
import urllib.request
from decimal import Decimal, ROUND_HALF_UP

COINSTATS_API_KEY = os.getenv("COINSTATS_API_KEY", "")
COINSTATS_BASE    = "https://openapiv1.coinstats.app"
COINSTATS_CURRENCY = os.getenv("COINSTATS_CURRENCY", "USD")

# ---------------------------------------------------------------------------
# CoinStats coin ID → ledger subcategory symbol
# CoinStats uses its own coin IDs; symbols are unreliable across APIs.
# ---------------------------------------------------------------------------
COIN_ID_TO_SYMBOL: dict[str, str] = {
    "bitcoin":       "BTC",
    "ethereum":      "ETH",
    "solana":        "SOL",
    "ripple":        "XRP",
    "binancecoin":   "BNB",
    "avalanche-2":   "AVAX",
    "chainlink":     "LINK",
    "dogecoin":      "DOGE",
    "arbitrum":      "ARB",
    "uniswap":       "UNI",
    "aave":          "AAVE",
    "staked-ether":  "stETH",
}

# Reverse lookup: symbol → CoinStats ID (used to build query)
SYMBOL_TO_ID: dict[str, str] = {v: k for k, v in COIN_ID_TO_SYMBOL.items()}

# All symbols we care about
TRACKED_SYMBOLS = set(SYMBOL_TO_ID.keys())


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _get(path: str, params: dict | None = None) -> dict | list:
    """Make a GET request to the CoinStats API; return parsed JSON."""
    if not COINSTATS_API_KEY:
        raise RuntimeError(
            "COINSTATS_API_KEY is not set. "
            "Add it to .env: COINSTATS_API_KEY=<your-key>"
        )

    url = f"{COINSTATS_BASE}{path}"
    if params:
        qs = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{qs}"

    req = urllib.request.Request(
        url,
        headers={
            "X-API-KEY": COINSTATS_API_KEY,
            "accept":    "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"CoinStats API error {exc.code}: {body[:200]}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"CoinStats network error: {exc.reason}") from exc


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def fetch_prices(symbols: set[str] | None = None) -> dict[str, float]:
    """Return {symbol: usd_price} for all tracked (or specified) symbols.

    CoinStats v1 /coins endpoint returns a paginated list of coins.
    We fetch up to 500 coins in one call; all our tracked coins are
    in the top 500 by market cap.
    """
    symbols = symbols or TRACKED_SYMBOLS
    raw = _get("/coins", {
        "currency": COINSTATS_CURRENCY,
        "limit":    500,
        "skip":     0,
    })

    # Response shape: {"result": [...]} or directly a list
    coins = raw.get("result") if isinstance(raw, dict) else raw

    prices: dict[str, float] = {}
    for coin in coins:
        coin_id = coin.get("id", "")
        sym = COIN_ID_TO_SYMBOL.get(coin_id)
        if sym and sym in symbols:
            price = coin.get("price")
            if price is not None:
                prices[sym] = float(price)

    return prices


def refresh_crypto_prices(conn) -> list[dict]:
    """Fetch live prices and update estimated_value for all Cryptocurrency assets.

    For each asset:
        estimated_value = ROUND(quantity * live_price, 4)

    Returns a list of dicts describing each updated asset:
        [{asset_name, subcategory, quantity, old_value, new_value, price}, ...]
    """
    prices = fetch_prices()
    if not prices:
        return []

    rows = conn.execute(
        "SELECT id, asset_name, subcategory, quantity, estimated_value "
        "FROM assets WHERE category = 'Cryptocurrency'"
    ).fetchall()

    updated = []
    for row in rows:
        sym = (row["subcategory"] or "").strip()
        if sym not in prices:
            continue

        price = Decimal(str(prices[sym]))
        try:
            qty = Decimal(str(row["quantity"])) if row["quantity"] else Decimal("0")
        except Exception:
            continue

        new_value = (qty * price).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
        old_value = row["estimated_value"] or "0.0000"

        conn.execute(
            "UPDATE assets SET estimated_value = ?, updated_at = datetime('now') "
            "WHERE id = ?",
            (str(new_value), row["id"]),
        )
        updated.append({
            "id":           row["id"],
            "asset_name":   row["asset_name"],
            "symbol":       sym,
            "quantity":     str(qty),
            "price_usd":    f"{price:.4f}",
            "old_value":    old_value,
            "new_value":    str(new_value),
        })

    conn.commit()
    return updated


def get_portfolio_snapshot(conn) -> dict:
    """Return current crypto portfolio with live prices overlaid (no DB write).

    Useful for a read-only price check without modifying stored values.
    """
    prices = fetch_prices()

    rows = conn.execute(
        "SELECT id, asset_name, subcategory, quantity, estimated_value "
        "FROM assets WHERE category = 'Cryptocurrency' ORDER BY "
        "CAST(estimated_value AS REAL) DESC"
    ).fetchall()

    positions = []
    total_live   = Decimal("0")
    total_stored = Decimal("0")

    for row in rows:
        sym   = (row["subcategory"] or "").strip()
        price = prices.get(sym)
        try:
            qty = Decimal(str(row["quantity"])) if row["quantity"] else Decimal("0")
        except Exception:
            qty = Decimal("0")

        stored = Decimal(row["estimated_value"] or "0")
        live   = (qty * Decimal(str(price))).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ) if price else None

        total_stored += stored
        if live is not None:
            total_live += live

        positions.append({
            "asset_name":      row["asset_name"],
            "symbol":          sym,
            "quantity":        str(qty),
            "price_usd":       f"{price:.4f}" if price else None,
            "live_value_usd":  str(live) if live is not None else None,
            "stored_value_usd": str(stored),
        })

    return {
        "positions":           positions,
        "total_live_usd":      str(total_live),
        "total_stored_usd":    str(total_stored),
        "pnl_vs_stored":       str(total_live - total_stored),
        "currency":            COINSTATS_CURRENCY,
        "coins_with_price":    len(prices),
    }

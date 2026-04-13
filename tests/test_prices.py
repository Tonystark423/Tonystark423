"""Tests for live price endpoints (/api/prices, /api/prices/refresh).

CoinStats API calls are not made during tests — endpoints return 502
when COINSTATS_API_KEY is empty, which is the expected test-env behaviour.
Success-path tests mock the coinstats module so no real HTTP call is made.
"""
import os
import sys
import types
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import app as app_module


@pytest.fixture(scope="module", autouse=True)
def set_env():
    os.environ["LEDGER_USER"] = "testuser"
    os.environ["LEDGER_PASS"] = "testpass"
    # Ensure no API key is set so endpoints return predictable 502
    os.environ.pop("COINSTATS_API_KEY", None)


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    return (app_module.LEDGER_USER, app_module.LEDGER_PASS)


class TestPricesAuth:
    def test_get_prices_requires_auth(self, client):
        assert client.get("/api/prices").status_code == 401

    def test_refresh_prices_requires_auth(self, client):
        assert client.post("/api/prices/refresh").status_code == 401


class TestPricesNoKey:
    """When COINSTATS_API_KEY is absent, endpoints return 502 with error message."""

    def test_get_prices_returns_502_without_key(self, client, auth):
        resp = client.get("/api/prices", auth=auth)
        assert resp.status_code == 502
        data = resp.get_json()
        assert "error" in data
        assert "COINSTATS_API_KEY" in data["error"]

    def test_refresh_prices_returns_502_without_key(self, client, auth):
        resp = client.post("/api/prices/refresh", auth=auth)
        assert resp.status_code == 502
        data = resp.get_json()
        assert "error" in data
        assert "COINSTATS_API_KEY" in data["error"]

    def test_get_prices_error_is_string(self, client, auth):
        resp = client.get("/api/prices", auth=auth)
        assert isinstance(resp.get_json()["error"], str)

    def test_refresh_prices_error_is_string(self, client, auth):
        resp = client.post("/api/prices/refresh", auth=auth)
        assert isinstance(resp.get_json()["error"], str)


class TestPricesWithMock:
    """Mock coinstats module to exercise success paths without real HTTP calls."""

    SNAPSHOT = {
        "positions": [
            {
                "asset_name": "Bitcoin (BTC)",
                "symbol": "BTC",
                "quantity": "42",
                "price_usd": "70000.0000",
                "live_value_usd": "2940000.00",
                "stored_value_usd": "3073141.44",
            }
        ],
        "total_live_usd": "2940000.00",
        "total_stored_usd": "3073141.44",
        "pnl_vs_stored": "-133141.44",
        "currency": "USD",
        "coins_with_price": 1,
    }

    UPDATED = [
        {
            "id": 1,
            "asset_name": "Bitcoin (BTC)",
            "symbol": "BTC",
            "quantity": "42",
            "price_usd": "70000.0000",
            "old_value": "3073141.44",
            "new_value": "2940000.0000",
        }
    ]

    @pytest.fixture(autouse=True)
    def inject_mock(self, monkeypatch):
        """Replace coinstats in sys.modules with a mock."""
        mock = types.ModuleType("coinstats")
        mock.get_portfolio_snapshot = lambda conn: self.SNAPSHOT
        mock.refresh_crypto_prices  = lambda conn: self.UPDATED
        monkeypatch.setitem(sys.modules, "coinstats", mock)

    def test_get_prices_returns_200(self, client, auth):
        resp = client.get("/api/prices", auth=auth)
        assert resp.status_code == 200

    def test_get_prices_has_positions(self, client, auth):
        data = client.get("/api/prices", auth=auth).get_json()
        assert "positions" in data
        assert isinstance(data["positions"], list)

    def test_get_prices_has_totals(self, client, auth):
        data = client.get("/api/prices", auth=auth).get_json()
        assert "total_live_usd" in data
        assert "total_stored_usd" in data
        assert "pnl_vs_stored" in data

    def test_get_prices_currency(self, client, auth):
        data = client.get("/api/prices", auth=auth).get_json()
        assert data["currency"] == "USD"

    def test_refresh_prices_returns_200(self, client, auth):
        resp = client.post("/api/prices/refresh", auth=auth)
        assert resp.status_code == 200

    def test_refresh_prices_has_count(self, client, auth):
        data = client.post("/api/prices/refresh", auth=auth).get_json()
        assert "count" in data
        assert data["count"] == 1

    def test_refresh_prices_has_updated_list(self, client, auth):
        data = client.post("/api/prices/refresh", auth=auth).get_json()
        assert "updated" in data
        assert isinstance(data["updated"], list)
        assert data["updated"][0]["symbol"] == "BTC"

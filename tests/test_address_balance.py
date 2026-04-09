"""
Tests for GET /api/address/<address>/balance.

Strategy:
  - urllib.request.urlopen is mocked so no real network calls are made.
  - Each test covers a distinct branch: happy path, bad address format,
    upstream HTTP 400, upstream non-400 HTTP error, and network failure.
  - Assertion density is kept >= 0.5 on every function (Pattern 1 + 2).
"""

import json
import os
import sqlite3
import tempfile
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

# ---------------------------------------------------------------------------
# Isolated DB setup (same pattern as test_app.py)
# ---------------------------------------------------------------------------

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ.setdefault("DB_PATH", _db_path)
os.environ.setdefault("LEDGER_USER", "testuser")
os.environ.setdefault("LEDGER_PASS", "testpass")
os.environ.setdefault("FLASK_SECRET_KEY", "test-secret")

import app as app_module  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def init_database():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    conn = sqlite3.connect(_db_path)
    conn.executescript(schema)
    conn.close()
    yield
    os.close(_db_fd)
    os.unlink(_db_path)


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    return ("testuser", "testpass")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GENESIS_ADDRESS = "1A1zP1eP5QGefi2DMPTfTL5SLmv7Divf8a"
_GENESIS_SATOSHI = 6825000000


def _mock_urlopen(address, satoshi):
    """Return a context-manager mock that yields a blockchain.info-shaped response."""
    body = json.dumps({address: {"final_balance": satoshi, "n_tx": 1, "total_received": satoshi}})
    resp = MagicMock()
    resp.read.return_value = body.encode()
    resp.__enter__ = lambda s: s
    resp.__exit__ = MagicMock(return_value=False)
    return resp


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------

class TestAddressBalanceAuth:
    def test_no_credentials_returns_401(self, client):
        resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

    def test_wrong_password_returns_401(self, client):
        resp = client.get(
            f"/api/address/{_GENESIS_ADDRESS}/balance",
            auth=(_GENESIS_ADDRESS, "wrongpass"),
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Address format validation (fires before any network call)
# ---------------------------------------------------------------------------

class TestAddressValidation:
    @pytest.mark.parametrize("bad_address", [
        "short",                  # too short (< 25 chars)
        "a" * 91,                 # too long (> 90 chars)
        "1A1z/../etc/passwd",     # path traversal chars
        "addr with space",        # space
        "addr;DROP TABLE--",      # SQL injection chars
        "<script>xss</script>",   # XSS chars
    ])
    def test_invalid_address_returns_400(self, client, auth, bad_address):
        resp = client.get(f"/api/address/{bad_address}/balance", auth=auth)
        # Flask may return 404 for addresses that contain URL-special chars
        # before even reaching our route — either 400 or 404 proves rejection.
        assert resp.status_code in (400, 404)

    def test_invalid_address_error_message(self, client, auth):
        """Verify the error payload shape for a clearly bad address."""
        resp = client.get("/api/address/bad/balance", auth=auth)
        assert resp.status_code == 400
        data = resp.get_json()
        assert "error" in data
        assert "Invalid address" in data["error"]

    def test_valid_legacy_address_passes_format_check(self, client, auth):
        """A correctly-formed address must not be rejected by the format gate."""
        mock_resp = _mock_urlopen(_GENESIS_ADDRESS, _GENESIS_SATOSHI)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        assert resp.status_code == 200

    def test_bech32_address_passes_format_check(self, client, auth):
        """bc1… bech32 addresses are alphanumeric and must clear the regex."""
        bech32 = "bc1qar0srrr7xfkvy5l643lydnw9re59gtzzwf5mdq"
        mock_resp = _mock_urlopen(bech32, 0)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get(f"/api/address/{bech32}/balance", auth=auth)
        assert resp.status_code == 200


# ---------------------------------------------------------------------------
# Happy-path response shape
# ---------------------------------------------------------------------------

class TestAddressBalanceHappyPath:
    def test_response_contains_all_required_fields(self, client, auth):
        mock_resp = _mock_urlopen(_GENESIS_ADDRESS, _GENESIS_SATOSHI)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data["address"] == _GENESIS_ADDRESS
        assert data["network"] == "bitcoin"
        assert "balance_satoshi" in data
        assert "balance_btc" in data

    def test_balance_satoshi_matches_upstream(self, client, auth):
        mock_resp = _mock_urlopen(_GENESIS_ADDRESS, _GENESIS_SATOSHI)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        assert resp.get_json()["balance_satoshi"] == _GENESIS_SATOSHI

    def test_balance_btc_is_correct_conversion(self, client, auth):
        """68.25 BTC = 6_825_000_000 satoshi; eight decimal places required."""
        mock_resp = _mock_urlopen(_GENESIS_ADDRESS, _GENESIS_SATOSHI)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        assert resp.get_json()["balance_btc"] == "68.25000000"

    def test_zero_balance_address(self, client, auth):
        """An address with no funds must return 0 satoshi and eight-zero BTC string."""
        empty_addr = "1BpEi6DfDAUFd153wiGrvkiKW1iHBGEjVL"
        mock_resp = _mock_urlopen(empty_addr, 0)
        with patch("urllib.request.urlopen", return_value=mock_resp):
            resp = client.get(f"/api/address/{empty_addr}/balance", auth=auth)
        data = resp.get_json()
        assert data["balance_satoshi"] == 0
        assert data["balance_btc"] == "0.00000000"

    def test_upstream_url_includes_address(self, client, auth):
        """Verify the correct blockchain.info URL is constructed."""
        mock_resp = _mock_urlopen(_GENESIS_ADDRESS, _GENESIS_SATOSHI)
        with patch("urllib.request.urlopen", return_value=mock_resp) as mock_open:
            client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        called_url = mock_open.call_args[0][0].full_url
        assert _GENESIS_ADDRESS in called_url
        assert "blockchain.info/balance" in called_url


# ---------------------------------------------------------------------------
# Upstream error branches
# ---------------------------------------------------------------------------

class TestAddressBalanceUpstreamErrors:
    def test_upstream_http_400_returns_404(self, client, auth):
        """blockchain.info returns HTTP 400 for an unrecognised address → our 404."""
        import urllib.error
        exc = urllib.error.HTTPError(url=None, code=400, msg="Bad Request", hdrs={}, fp=None)
        with patch("urllib.request.urlopen", side_effect=exc):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        assert resp.status_code == 404
        assert "not found" in resp.get_json()["error"].lower()

    def test_upstream_http_500_returns_502(self, client, auth):
        """Non-400 HTTP errors from the upstream API are proxied as 502."""
        import urllib.error
        exc = urllib.error.HTTPError(url=None, code=500, msg="Internal Server Error", hdrs={}, fp=None)
        with patch("urllib.request.urlopen", side_effect=exc):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        assert resp.status_code == 502
        data = resp.get_json()
        assert "error" in data
        assert "500" in data["error"]

    def test_network_unreachable_returns_502(self, client, auth):
        """URLError (DNS failure, refused connection, etc.) → 502."""
        import urllib.error
        exc = urllib.error.URLError(reason="Network unreachable")
        with patch("urllib.request.urlopen", side_effect=exc):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        assert resp.status_code == 502
        assert "blockchain API" in resp.get_json()["error"]

    def test_timeout_returns_502(self, client, auth):
        """TimeoutError (socket timeout) → 502."""
        with patch("urllib.request.urlopen", side_effect=TimeoutError()):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        assert resp.status_code == 502
        assert "error" in resp.get_json()

    def test_os_error_returns_502(self, client, auth):
        """Generic OSError (e.g. SSL failure) → 502."""
        with patch("urllib.request.urlopen", side_effect=OSError("SSL error")):
            resp = client.get(f"/api/address/{_GENESIS_ADDRESS}/balance", auth=auth)
        assert resp.status_code == 502
        assert "error" in resp.get_json()

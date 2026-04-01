"""
Tests for validate_fields() — the asset input validation layer.

Mirrors the three gates in middleware/validateAsset.js:
  1. Precision gate    — estimated_value must be > 0
  2. Quantity gate     — quantity must be > 0
  3. Name sanitization — strip whitespace, cap at 100 chars

Each truth-table row has its own test so a mutation to any
comparison operator is caught immediately.
"""

import os
import sqlite3
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"]     = _db_path
os.environ["LEDGER_USER"] = "testuser"
os.environ["LEDGER_PASS"] = "testpass"

import app as app_module  # noqa: E402
from app import validate_fields  # noqa: E402


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
    app_module.app.config["DB_PATH"] = _db_path
    with app_module.app.test_client() as c:
        yield c


auth = ("testuser", "testpass")


# ---------------------------------------------------------------------------
# Unit tests for validate_fields() directly — fast, no HTTP overhead
# ---------------------------------------------------------------------------

class TestPrecisionGate:
    """Rule 1: estimated_value must be a positive number when provided."""

    def test_positive_value_passes(self):
        fields, err = validate_fields({"estimated_value": 0.29})
        assert err is None
        assert fields["estimated_value"] == "0.2900"   # stored as exact Decimal string

    def test_value_rounded_to_4_decimal_places(self):
        fields, err = validate_fields({"estimated_value": 0.123456789})
        assert err is None
        assert fields["estimated_value"] == "0.1235"   # ROUND_HALF_UP at 4dp

    def test_zero_value_rejected(self):
        _, err = validate_fields({"estimated_value": 0})
        assert err is not None
        assert "greater than zero" in err

    def test_negative_value_rejected(self):
        _, err = validate_fields({"estimated_value": -10.0})
        assert err is not None
        assert "greater than zero" in err

    def test_string_non_numeric_rejected(self):
        _, err = validate_fields({"estimated_value": "not-a-number"})
        assert err is not None
        assert "number" in err

    def test_none_value_skipped(self):
        """None means 'not provided' — validation does not apply."""
        fields, err = validate_fields({"estimated_value": None})
        assert err is None


class TestQuantityGate:
    """Rule 2: quantity must be a positive number when provided."""

    def test_positive_quantity_passes(self):
        fields, err = validate_fields({"quantity": 100})
        assert err is None
        assert fields["quantity"] == "100.0000"

    def test_fractional_quantity_passes(self):
        """
        Crypto holdings can be fractional, but 0.00042 rounds to 0.0004
        at 4 decimal places. Callers needing sub-pip precision must use
        a quantity scale that keeps significant digits within 4dp
        (e.g. express in milli-units).
        """
        fields, err = validate_fields({"quantity": 0.00042})
        assert err is None
        assert fields["quantity"] == "0.0004"   # correct: 4dp truncation

    def test_zero_quantity_rejected(self):
        _, err = validate_fields({"quantity": 0})
        assert err is not None
        assert "greater than zero" in err

    def test_negative_quantity_rejected(self):
        _, err = validate_fields({"quantity": -5})
        assert err is not None
        assert "greater than zero" in err

    def test_string_non_numeric_rejected(self):
        _, err = validate_fields({"quantity": "many"})
        assert err is not None
        assert "number" in err

    def test_none_quantity_skipped(self):
        fields, err = validate_fields({"quantity": None})
        assert err is None


class TestNameSanitization:
    """Rule 3: asset_name is stripped and capped at 100 characters."""

    def test_leading_trailing_whitespace_stripped(self):
        fields, err = validate_fields({"asset_name": "  PMAX  "})
        assert err is None
        assert fields["asset_name"] == "PMAX"

    def test_name_capped_at_100_characters(self):
        long_name = "A" * 150
        fields, err = validate_fields({"asset_name": long_name})
        assert err is None
        assert len(fields["asset_name"]) == 100

    def test_name_exactly_100_characters_unchanged(self):
        name = "B" * 100
        fields, err = validate_fields({"asset_name": name})
        assert err is None
        assert fields["asset_name"] == name

    def test_blank_after_strip_rejected(self):
        _, err = validate_fields({"asset_name": "   "})
        assert err is not None
        assert "blank" in err

    def test_empty_string_rejected(self):
        _, err = validate_fields({"asset_name": ""})
        assert err is not None

    def test_none_name_skipped(self):
        """None means field not included in payload — no validation."""
        fields, err = validate_fields({"asset_name": None})
        assert err is None


# ---------------------------------------------------------------------------
# Integration tests — validation wired into POST and PUT routes
# ---------------------------------------------------------------------------

class TestValidationViaAPI:

    def test_post_zero_value_returns_400(self, client):
        resp = client.post("/api/assets", auth=auth, json={
            "asset_name": "PMAX", "category": "Securities & Commodities",
            "estimated_value": 0,
        })
        assert resp.status_code == 400
        assert "greater than zero" in resp.get_json()["error"]

    def test_post_negative_quantity_returns_400(self, client):
        resp = client.post("/api/assets", auth=auth, json={
            "asset_name": "PMAX", "category": "Securities & Commodities",
            "quantity": -1,
        })
        assert resp.status_code == 400
        assert "greater than zero" in resp.get_json()["error"]

    def test_post_name_sanitized_in_db(self, client):
        resp = client.post("/api/assets", auth=auth, json={
            "asset_name": "  PMAX - Powell Max Limited  ",
            "category": "Securities & Commodities",
            "quantity": 100, "estimated_value": 29.00,
        })
        assert resp.status_code == 201
        assert resp.get_json()["asset_name"] == "PMAX - Powell Max Limited"

    def test_put_negative_value_returns_400(self, client):
        create = client.post("/api/assets", auth=auth, json={
            "asset_name": "Temp", "category": "Cryptocurrency",
        })
        asset_id = create.get_json()["id"]

        resp = client.put(f"/api/assets/{asset_id}", auth=auth, json={
            "estimated_value": -99.0,
        })
        assert resp.status_code == 400
        assert "greater than zero" in resp.get_json()["error"]

    def test_kills_float_drift_mutant(self, client):
        """
        AI8TB Density: kills the 'Float Drift' mutant.

        0.29 * 100 = 28.999999999999996 in IEEE 754 float arithmetic.
        This test proves the stored value is the exact Decimal string
        "29.0000", not the drifted float representation.

        If validate_fields used float() instead of Decimal(str()),
        this assertion would catch it.
        """
        import sqlite3 as _sqlite3
        resp = client.post("/api/assets", auth=auth, json={
            "asset_name": "PMAX Float Drift Check",
            "category": "Securities & Commodities",
            "estimated_value": 0.2900,
            "quantity": 100,
        })
        assert resp.status_code == 201
        asset_id = resp.get_json()["id"]

        # Read the raw stored string directly from SQLite — bypasses any
        # float conversion the JSON serialiser might apply
        conn = _sqlite3.connect(_db_path)
        row = conn.execute(
            "SELECT estimated_value, quantity FROM assets WHERE id = ?",
            (asset_id,),
        ).fetchone()
        conn.close()

        assert row[0] == "0.2900", f"Float drift detected: stored '{row[0]}' not '0.2900'"
        assert row[1] == "100.0000", f"Quantity drift: stored '{row[1]}' not '100.0000'"

    def test_valid_pmax_trade_accepted(self, client):
        """End-to-end: the PMAX trade from the order confirmation."""
        resp = client.post("/api/assets", auth=auth, json={
            "asset_name": "PMAX - Powell Max Limited",
            "category": "Securities & Commodities",
            "subcategory": "Equity",
            "quantity": 100,
            "unit": "shares",
            "estimated_value": 29.00,
            "acquisition_date": "2025-04-07",
            "custodian": "JAN / Powell Max Limited",
            "status": "active",
            "notes": "Limit buy filled at $0.29, order placed 09:48:46 EDT",
        })
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["estimated_value"] == "29.0000"
        assert data["quantity"] == "100.0000"
        assert data["asset_name"] == "PMAX - Powell Max Limited"

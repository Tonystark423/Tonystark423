"""
Tests for the tax engine (tax_engine.py) and tax API endpoints.

Unit tests cover pure functions directly.
Integration tests use the same Flask test-client pattern as test_app.py.

NOTE: All test modules in this suite share the same app.py module instance
(Python module caching). test_app.py is imported first alphabetically and
fixes LEDGER_USER="testuser"/LEDGER_PASS="testpass", so all modules must
use those credentials.
"""

import json
import os
import sqlite3
import tempfile
from datetime import date, timedelta

import pytest

# These env settings only take effect if this module is imported first.
# When run as part of the full suite, test_app.py has already imported app.py
# with testuser/testpass. We set the same values here for isolation runs.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"] = _db_path
os.environ["LEDGER_USER"] = "testuser"
os.environ["LEDGER_PASS"] = "testpass"
os.environ["FLASK_SECRET_KEY"] = "test-secret"

import app as app_module  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def init_database():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    conn = sqlite3.connect(app_module.DB_PATH)
    conn.executescript(schema)
    conn.close()
    yield
    os.close(_db_fd)
    try:
        os.unlink(_db_path)
    except FileNotFoundError:
        pass


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    # Match the credentials that app_module.LEDGER_USER/PASS were set to
    # at first import (always testuser/testpass when running the full suite).
    return (app_module.LEDGER_USER, app_module.LEDGER_PASS)


@pytest.fixture()
def seed_sold_security(client, auth):
    """Insert a sold Security asset acquired > 1 year ago (long-term gains)."""
    acq_date = (date.today() - timedelta(days=400)).isoformat()
    payload = {
        "asset_name": "NVDA Stock Tax Test",
        "category": "Securities & Commodities",
        "estimated_value": 50000.0,
        "acquisition_date": acq_date,
        "status": "sold",
    }
    resp = client.post(
        "/api/assets",
        data=json.dumps(payload),
        content_type="application/json",
        auth=auth,
    )
    assert resp.status_code == 201
    return resp.get_json()


@pytest.fixture()
def seed_computer_resource(client, auth):
    """Insert an active Computer Resources asset (Section 179 eligible)."""
    payload = {
        "asset_name": "AI GPU Cluster Tax Test",
        "category": "Computer Resources",
        "estimated_value": 200000.0,
        "acquisition_date": "2025-01-10",
        "status": "active",
    }
    resp = client.post(
        "/api/assets",
        data=json.dumps(payload),
        content_type="application/json",
        auth=auth,
    )
    assert resp.status_code == 201
    return resp.get_json()


# ---------------------------------------------------------------------------
# Unit tests — tax_engine pure functions
# ---------------------------------------------------------------------------

class TestTaxEngineUnit:
    def _make_conn(self):
        conn = sqlite3.connect(":memory:")
        schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
        with open(schema_path) as f:
            conn.executescript(f.read())
        conn.row_factory = sqlite3.Row
        return conn

    def test_get_capital_gains_empty_db(self):
        """No sold assets → empty gains list."""
        from tax_engine import get_capital_gains
        conn = self._make_conn()
        gains = get_capital_gains(conn)
        assert gains == []
        conn.close()

    def test_get_capital_gains_long_term(self):
        """Asset held > 365 days classified as long_term."""
        from tax_engine import get_capital_gains
        conn = self._make_conn()
        acq = (date.today() - timedelta(days=400)).isoformat()
        conn.execute(
            "INSERT INTO assets (asset_name, category, estimated_value, acquisition_date, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("NVDA", "Securities & Commodities", "50000.0000", acq, "sold"),
        )
        conn.commit()
        gains = get_capital_gains(conn)
        assert len(gains) == 1
        assert gains[0]["gain_type"] == "long_term"
        conn.close()

    def test_get_capital_gains_short_term(self):
        """Asset held < 365 days classified as short_term."""
        from tax_engine import get_capital_gains
        conn = self._make_conn()
        acq = (date.today() - timedelta(days=100)).isoformat()
        conn.execute(
            "INSERT INTO assets (asset_name, category, estimated_value, acquisition_date, status) "
            "VALUES (?, ?, ?, ?, ?)",
            ("BTC-Short", "Cryptocurrency", "10000.0000", acq, "sold"),
        )
        conn.commit()
        gains = get_capital_gains(conn)
        assert len(gains) == 1
        assert gains[0]["gain_type"] == "short_term"
        conn.close()

    def test_get_capital_gains_missing_date_defaults_short_term(self):
        """Missing acquisition_date → conservative short_term classification."""
        from tax_engine import get_capital_gains
        conn = self._make_conn()
        conn.execute(
            "INSERT INTO assets (asset_name, category, estimated_value, status) "
            "VALUES (?, ?, ?, ?)",
            ("NoDateAsset", "Cryptocurrency", "5000.0000", "sold"),
        )
        conn.commit()
        gains = get_capital_gains(conn)
        assert any(g["gain_type"] == "short_term" for g in gains)
        conn.close()

    def test_get_deductions_section179_eligible(self):
        """Computer Resources assets qualify for Section 179."""
        from tax_engine import get_deductions
        conn = self._make_conn()
        conn.execute(
            "INSERT INTO assets (asset_name, category, estimated_value, status) "
            "VALUES (?, ?, ?, ?)",
            ("GPU Cluster", "Computer Resources", "100000.0000", "active"),
        )
        conn.commit()
        deductions = get_deductions(conn)
        assert len(deductions) == 1
        assert deductions[0]["deduction_type"] == "Section 179"
        conn.close()

    def test_get_deductions_non_eligible_category(self):
        """Money Market Funds are not eligible for Section 179."""
        from tax_engine import get_deductions
        conn = self._make_conn()
        conn.execute(
            "INSERT INTO assets (asset_name, category, estimated_value, status) "
            "VALUES (?, ?, ?, ?)",
            ("SPAXX", "Money Market Funds", "50000.0000", "active"),
        )
        conn.commit()
        deductions = get_deductions(conn)
        assert deductions == []
        conn.close()

    def test_apply_tax_hacks_returns_hacks_list(self):
        """apply_tax_hacks returns a dict with hacks list and savings."""
        from tax_engine import apply_tax_hacks
        gains = [{"proceeds": "10000", "gain_type": "short_term", "estimated_tax": "3700"}]
        deductions = [{"deductible_amount": "5000", "deduction_type": "Section 179"}]
        result = apply_tax_hacks(gains, deductions)
        assert "hacks" in result
        assert "total_estimated_savings" in result
        assert isinstance(result["hacks"], list)
        assert len(result["hacks"]) > 0

    def test_apply_tax_hacks_short_term_flag(self):
        """Short-term gains trigger a hold-for-long-term recommendation."""
        from tax_engine import apply_tax_hacks
        gains = [{"proceeds": "20000", "gain_type": "short_term", "estimated_tax": "7400"}]
        result = apply_tax_hacks(gains, [])
        hack_names = [h["hack"] for h in result["hacks"]]
        assert any("Long-Term" in name or "Hold" in name for name in hack_names)

    def test_generate_tax_report_required_keys(self):
        """generate_tax_report returns all required top-level keys."""
        from tax_engine import generate_tax_report
        conn = self._make_conn()
        report = generate_tax_report(conn, tax_year=2025)
        for key in ("tax_year", "generated_at", "disclaimer", "capital_gains",
                    "deductions", "hacks", "summary"):
            assert key in report, f"Missing key: {key}"
        conn.close()

    def test_generate_tax_report_summary_keys(self):
        """Summary block has all expected financial keys."""
        from tax_engine import generate_tax_report
        conn = self._make_conn()
        report = generate_tax_report(conn, tax_year=2025)
        for key in ("total_proceeds", "estimated_tax_before_deductions",
                    "total_deductions", "estimated_net_liability"):
            assert key in report["summary"], f"Missing summary key: {key}"
        conn.close()

    def test_generate_tax_report_empty_db_zeros(self):
        """Empty DB → zero proceeds and zero liability."""
        from tax_engine import generate_tax_report
        conn = self._make_conn()
        report = generate_tax_report(conn, tax_year=2025)
        assert report["summary"]["total_proceeds"] == "0.00"
        assert report["summary"]["estimated_net_liability"] == "0"
        conn.close()

    def test_export_tax_excel_returns_bytes(self):
        """export_tax_excel produces non-empty bytes output."""
        from tax_engine import generate_tax_report, export_tax_excel
        conn = self._make_conn()
        report = generate_tax_report(conn, tax_year=2025)
        result = export_tax_excel(report)
        assert isinstance(result, bytes)
        assert len(result) > 0
        conn.close()


# ---------------------------------------------------------------------------
# Integration tests — /api/tax/* endpoints
# ---------------------------------------------------------------------------

class TestTaxSummaryEndpoint:
    def test_requires_auth(self, client):
        resp = client.get("/api/tax/summary")
        assert resp.status_code == 401

    def test_returns_200(self, client, auth):
        """Tax summary endpoint always returns 200 (even with empty data)."""
        resp = client.get("/api/tax/summary", auth=auth)
        assert resp.status_code == 200

    def test_response_has_required_structure(self, client, auth):
        resp = client.get("/api/tax/summary", auth=auth)
        data = resp.get_json()
        for key in ("tax_year", "generated_at", "disclaimer",
                    "capital_gains", "deductions", "hacks", "summary"):
            assert key in data, f"Missing key: {key}"

    def test_summary_block_has_financial_fields(self, client, auth):
        resp = client.get("/api/tax/summary", auth=auth)
        summary = resp.get_json()["summary"]
        for key in ("total_proceeds", "estimated_tax_before_deductions",
                    "total_deductions", "estimated_net_liability"):
            assert key in summary

    def test_with_sold_securities_returns_gains(self, client, auth, seed_sold_security):
        resp = client.get("/api/tax/summary", auth=auth)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["capital_gains"]) >= 1
        assert float(data["summary"]["total_proceeds"]) > 0

    def test_with_computer_resources_returns_deductions(self, client, auth, seed_computer_resource):
        resp = client.get("/api/tax/summary", auth=auth)
        assert resp.status_code == 200
        data = resp.get_json()
        assert len(data["deductions"]) >= 1

    def test_summary_has_disclaimer(self, client, auth):
        resp = client.get("/api/tax/summary", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json()["disclaimer"]

    def test_summary_has_hacks_list(self, client, auth, seed_sold_security, seed_computer_resource):
        resp = client.get("/api/tax/summary", auth=auth)
        assert resp.status_code == 200
        assert isinstance(resp.get_json()["hacks"], list)

    def test_year_param_reflected_in_response(self, client, auth):
        resp = client.get("/api/tax/summary?year=2024", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json()["tax_year"] == 2024


class TestTaxFileEndpoint:
    def test_requires_auth(self, client):
        resp = client.post("/api/tax/file", content_type="application/json",
                           data=json.dumps({}))
        assert resp.status_code == 401

    def test_returns_excel_attachment(self, client, auth):
        resp = client.post("/api/tax/file", content_type="application/json",
                           data=json.dumps({}), auth=auth)
        assert resp.status_code == 200
        assert "spreadsheetml" in resp.content_type
        cd = resp.headers.get("Content-Disposition", "")
        assert "attachment" in cd

    def test_response_is_valid_xlsx(self, client, auth):
        """Response body starts with PK magic bytes (ZIP / XLSX container)."""
        resp = client.post("/api/tax/file", content_type="application/json",
                           data=json.dumps({}), auth=auth)
        assert resp.status_code == 200
        # XLSX files are ZIP archives; first two bytes are always b'PK'
        assert resp.data[:2] == b"PK"

    def test_entity_name_accepted_without_error(self, client, auth):
        """Passing entity_name in the body must not cause a server error."""
        resp = client.post("/api/tax/file", content_type="application/json",
                           data=json.dumps({"entity_name": "Stark Holdings"}), auth=auth)
        assert resp.status_code == 200

    def test_filename_includes_year(self, client, auth):
        resp = client.post("/api/tax/file", content_type="application/json",
                           data=json.dumps({"year": 2024}), auth=auth)
        assert resp.status_code == 200
        cd = resp.headers.get("Content-Disposition", "")
        assert "2024" in cd
        assert ".xlsx" in cd

    def test_preparer_param_accepted_without_error(self, client, auth):
        """Passing preparer in the body must not cause a server error."""
        resp = client.post("/api/tax/file", content_type="application/json",
                           data=json.dumps({"preparer": "Tony Stark"}), auth=auth)
        assert resp.status_code == 200

import io
import os
import sqlite3
import tempfile
from unittest.mock import patch

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"] = _db_path
os.environ["LEDGER_USER"] = "testuser"
os.environ["LEDGER_PASS"] = "testpass"

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


@pytest.fixture(autouse=True)
def clear_assets():
    conn = sqlite3.connect(_db_path)
    conn.execute("DELETE FROM assets")
    conn.commit()
    conn.close()
    yield
    conn = sqlite3.connect(_db_path)
    conn.execute("DELETE FROM assets")
    conn.commit()
    conn.close()


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    app_module.app.config["DB_PATH"] = _db_path
    app_module.app.config["LEDGER_USER"] = "testuser"
    app_module.app.config["LEDGER_PASS"] = "testpass"
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    return ("testuser", "testpass")


def seed_asset():
    conn = sqlite3.connect(_db_path)
    conn.execute(
        """
        INSERT INTO assets (
            asset_name, category, subcategory, description,
            estimated_value, quantity, unit, acquisition_date, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "Expense Seed",
            "Securities & Commodities",
            "debit",
            "cloud hosting",
            "125.5000",
            "1.0000",
            "USD",
            "2024-06-15",
            "active",
        ),
    )
    conn.commit()
    conn.close()


class TestOptionalRoutes:
    def test_authenticated_index_renders_dashboard(self, client, auth):
        resp = client.get("/", auth=auth)
        assert resp.status_code == 200
        assert b"Asset Ledger" in resp.data

    def test_import_csv_requires_file(self, client, auth):
        resp = client.post("/api/import/csv", auth=auth)
        assert resp.status_code == 400
        assert "No file field" in resp.get_json()["error"]

    def test_import_csv_rejects_non_csv_extension(self, client, auth):
        resp = client.post(
            "/api/import/csv",
            data={"file": (io.BytesIO(b"name\nx\n"), "ledger.txt")},
            content_type="multipart/form-data",
            auth=auth,
        )
        assert resp.status_code == 400
        assert ".csv" in resp.get_json()["error"]

    def test_import_csv_success_returns_200(self, client, auth):
        result = {"processed": 1, "inserted": 1, "skipped": 0, "errors": []}
        with patch("ledger_processor.process_csv", return_value=result) as mock_process:
            resp = client.post(
                "/api/import/csv?beneficial_owner=Pepper&custodian=Fidelity",
                data={"file": (io.BytesIO(b"asset_name,category\nPMAX,Cryptocurrency\n"), "ledger.csv")},
                content_type="multipart/form-data",
                auth=auth,
            )
        assert resp.status_code == 200
        assert resp.get_json() == result
        _, args, kwargs = mock_process.mock_calls[0]
        assert args[2:] == ()
        assert kwargs["default_beneficial_owner"] == "Pepper"
        assert kwargs["default_custodian"] == "Fidelity"

    def test_import_csv_partial_success_returns_207(self, client, auth):
        result = {"processed": 2, "inserted": 1, "skipped": 0, "errors": ["bad row"]}
        with patch("ledger_processor.process_csv", return_value=result):
            resp = client.post(
                "/api/import/csv",
                data={"file": (io.BytesIO(b"asset_name,category\nPMAX,Cryptocurrency\n"), "ledger.csv")},
                content_type="multipart/form-data",
                auth=auth,
            )
        assert resp.status_code == 207
        assert resp.get_json()["errors"] == ["bad row"]

    def test_report_expenses_no_data_returns_404(self, client, auth):
        resp = client.get("/api/reports/expenses", auth=auth)
        assert resp.status_code == 404
        assert "No data" in resp.get_json()["error"]

    def test_report_expenses_returns_png(self, client, auth):
        seed_asset()

        def fake_create_visuals(df, output_path, **_kwargs):
            with open(output_path, "wb") as fh:
                fh.write(b"png-bytes")

        with patch("ledger_processor.create_visuals", side_effect=fake_create_visuals):
            resp = client.get(
                "/api/reports/expenses?after=2024-01-01&before=2024-12-31",
                auth=auth,
            )
        assert resp.status_code == 200
        assert resp.mimetype == "image/png"
        assert resp.data == b"png-bytes"

    def test_export_excel_no_data_returns_404(self, client, auth):
        resp = client.get("/api/export/excel", auth=auth)
        assert resp.status_code == 404
        assert "No data" in resp.get_json()["error"]

    def test_export_excel_returns_workbook(self, client, auth):
        seed_asset()

        def fake_export_excel(df, output_path, **_kwargs):
            with open(output_path, "wb") as fh:
                fh.write(b"xlsx-bytes")

        with patch("ledger_processor.export_excel", side_effect=fake_export_excel):
            resp = client.get(
                "/api/export/excel?after=2024-01-01&before=2024-12-31",
                auth=auth,
            )
        assert resp.status_code == 200
        assert resp.mimetype == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        assert resp.data == b"xlsx-bytes"

    def test_report_budget_empty_returns_zero_summary(self, client, auth):
        resp = client.get("/api/reports/budget", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json() == {
            "summary": {"over": 0, "warning": 0, "ok": 0},
            "items": [],
        }

    def test_report_budget_returns_summary(self, client, auth):
        seed_asset()
        items = [
            {"category": "Technology", "limit": 100.0, "actual": 125.5, "variance": -25.5, "status": "over"},
            {"category": "Travel", "limit": 200.0, "actual": 50.0, "variance": 150.0, "status": "ok"},
        ]
        with patch("ledger_processor.check_budgets", return_value=items):
            resp = client.get(
                "/api/reports/budget?after=2024-01-01&before=2024-12-31",
                auth=auth,
            )
        assert resp.status_code == 200
        assert resp.get_json()["summary"] == {"over": 1, "warning": 0, "ok": 1}
        assert resp.get_json()["items"] == items

    def test_sync_starkbank_missing_env_returns_503(self, client, auth, monkeypatch):
        monkeypatch.delenv("STARKBANK_ENVIRONMENT", raising=False)
        monkeypatch.delenv("STARKBANK_PROJECT_ID", raising=False)
        monkeypatch.delenv("STARKBANK_PRIVATE_KEY", raising=False)
        resp = client.post("/api/sync/starkbank", auth=auth)
        assert resp.status_code == 503
        assert "Missing env vars" in resp.get_json()["error"]

    def test_sync_starkbank_returns_counts(self, client, auth, monkeypatch):
        monkeypatch.setenv("STARKBANK_ENVIRONMENT", "sandbox")
        monkeypatch.setenv("STARKBANK_PROJECT_ID", "123")
        monkeypatch.setenv("STARKBANK_PRIVATE_KEY", "pem")
        with patch("starkbank_sync.sync_transactions", return_value=(3, 1)) as mock_sync:
            resp = client.post(
                "/api/sync/starkbank",
                json={"limit": 50, "after": "2024-01-01", "before": "2024-12-31"},
                auth=auth,
            )
        assert resp.status_code == 200
        assert resp.get_json() == {"inserted": 3, "skipped": 1}
        _, args, kwargs = mock_sync.mock_calls[0]
        assert kwargs == {"limit": 50, "after": "2024-01-01", "before": "2024-12-31"}
        assert args

    def test_sync_starkbank_handles_upstream_error(self, client, auth, monkeypatch):
        monkeypatch.setenv("STARKBANK_ENVIRONMENT", "sandbox")
        monkeypatch.setenv("STARKBANK_PROJECT_ID", "123")
        monkeypatch.setenv("STARKBANK_PRIVATE_KEY", "pem")
        with patch("starkbank_sync.sync_transactions", side_effect=Exception("boom")):
            resp = client.post("/api/sync/starkbank", json={}, auth=auth)
        assert resp.status_code == 502
        assert resp.get_json()["error"] == "boom"

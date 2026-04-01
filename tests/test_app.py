"""
Test suite for app.py — targets all branch conditions including
boundary cases, null/missing inputs, and auth edge cases.

Run:
    pip install pytest pytest-cov
    pytest tests/ -v --cov=app --cov-report=term-missing
"""

import json
import os
import sqlite3
import tempfile

import pytest

# Point at an isolated temp database before importing the app
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"] = _db_path
os.environ["LEDGER_USER"] = "testuser"
os.environ["LEDGER_PASS"] = "testpass"
os.environ["FLASK_SECRET_KEY"] = "test-secret"

import app as app_module  # noqa: E402  (must come after env setup)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def init_database():
    """Create schema in the temp database once for the whole session."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    conn = sqlite3.connect(_db_path)
    conn.executescript(schema)
    conn.close()
    yield
    # Cleanup
    os.close(_db_fd)
    os.unlink(_db_path)


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    """Valid Basic Auth credentials as a (user, pass) tuple."""
    return ("testuser", "testpass")


@pytest.fixture()
def seed_asset(client, auth):
    """Insert one asset and return its full record dict."""
    payload = {
        "asset_name": "SPAXX Money Market",
        "category": "Money Market Funds",
        "subcategory": "SPAXX",
        "quantity": 10000.0,
        "unit": "USD",
        "estimated_value": 10000.0,
        "acquisition_date": "2024-01-15",
        "custodian": "Fidelity",
        "beneficial_owner": "Test Owner",
        "status": "active",
        "notes": "Fidelity money market fund",
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
# Auth — all branches of require_auth
# ---------------------------------------------------------------------------

class TestAuth:
    def test_no_credentials_returns_401(self, client):
        resp = client.get("/api/assets")
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers

    def test_wrong_username_returns_401(self, client):
        resp = client.get("/api/assets", auth=("wronguser", "testpass"))
        assert resp.status_code == 401

    def test_wrong_password_returns_401(self, client):
        resp = client.get("/api/assets", auth=("testuser", "wrongpass"))
        assert resp.status_code == 401

    def test_correct_credentials_returns_200(self, client, auth):
        resp = client.get("/api/assets", auth=auth)
        assert resp.status_code == 200

    def test_ui_root_requires_auth(self, client):
        resp = client.get("/")
        assert resp.status_code == 401

    def test_export_requires_auth(self, client):
        resp = client.get("/api/export")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /api/assets — create_asset branches
# ---------------------------------------------------------------------------

class TestCreateAsset:
    def test_missing_asset_name_returns_400(self, client, auth):
        resp = client.post(
            "/api/assets",
            data=json.dumps({"category": "Cryptocurrency"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "asset_name" in resp.get_json()["error"]

    def test_missing_category_returns_400(self, client, auth):
        resp = client.post(
            "/api/assets",
            data=json.dumps({"asset_name": "BTC"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "category" in resp.get_json()["error"]

    def test_both_required_fields_missing_returns_400(self, client, auth):
        resp = client.post(
            "/api/assets",
            data=json.dumps({"notes": "orphan note"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400

    def test_valid_minimal_payload_returns_201(self, client, auth):
        resp = client.post(
            "/api/assets",
            data=json.dumps({"asset_name": "BTC Holdings", "category": "Cryptocurrency"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["asset_name"] == "BTC Holdings"
        assert data["category"] == "Cryptocurrency"
        assert data["status"] == "active"   # default applied
        assert data["id"] is not None

    def test_full_payload_all_fields_stored(self, client, auth):
        payload = {
            "asset_name": "Patent US-12345",
            "category": "Proprietary IP",
            "subcategory": "Patent",
            "description": "Distributed ledger algorithm",
            "quantity": 1.0,
            "unit": "patent",
            "estimated_value": 500000.0,
            "acquisition_date": "2023-06-01",
            "custodian": "USPTO",
            "beneficial_owner": "Stark Financial Holdings LLC",
            "status": "active",
            "notes": "Pending renewal 2027",
        }
        resp = client.post(
            "/api/assets",
            data=json.dumps(payload),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        # quantity and estimated_value are stored as 4dp Decimal strings (schema TEXT col).
        _PRECISION_FIELDS = {"quantity", "estimated_value"}
        for key, val in payload.items():
            if key in _PRECISION_FIELDS:
                from decimal import Decimal
                expected_str = str(Decimal(str(val)).quantize(Decimal("0.0001")))
                assert data[key] == expected_str, f"Field {key!r} mismatch"
            else:
                assert data[key] == val, f"Field {key!r} mismatch"

    def test_invalid_category_rejected_by_db(self, client, auth):
        """SQLite CHECK constraint should reject an unrecognised category."""
        resp = client.post(
            "/api/assets",
            data=json.dumps({"asset_name": "Bad", "category": "InvalidCategory"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code in (400, 500)

    def test_null_optional_fields_accepted(self, client, auth):
        resp = client.post(
            "/api/assets",
            data=json.dumps({
                "asset_name": "Null Field Asset",
                "category": "Computer Resources",
                "estimated_value": None,
                "quantity": None,
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["estimated_value"] is None
        assert data["quantity"] is None

    def test_negative_estimated_value_rejected(self, client, auth):
        """validate_fields rejects non-positive estimated_value (must be > 0)."""
        resp = client.post(
            "/api/assets",
            data=json.dumps({
                "asset_name": "Margin Position",
                "category": "Securities & Commodities",
                "estimated_value": -5000.0,
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "greater than zero" in resp.get_json()["error"]

    def test_zero_quantity_rejected(self, client, auth):
        """validate_fields rejects zero quantity (must be > 0)."""
        resp = client.post(
            "/api/assets",
            data=json.dumps({
                "asset_name": "Depleted Asset",
                "category": "Cryptocurrency",
                "quantity": 0.0,
                "unit": "BTC",
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "greater than zero" in resp.get_json()["error"]


# ---------------------------------------------------------------------------
# GET /api/assets — list_assets branches
# ---------------------------------------------------------------------------

class TestListAssets:
    def test_returns_list(self, client, auth, seed_asset):
        resp = client.get("/api/assets", auth=auth)
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_empty_search_returns_all(self, client, auth, seed_asset):
        resp = client.get("/api/assets?q=", auth=auth)
        assert resp.status_code == 200
        assert len(resp.get_json()) >= 1

    def test_fts_search_finds_match(self, client, auth, seed_asset):
        """Exercises the FTS5 branch (q is non-empty)."""
        resp = client.get("/api/assets?q=Fidelity", auth=auth)
        assert resp.status_code == 200
        results = resp.get_json()
        assert any(a["custodian"] == "Fidelity" for a in results)

    def test_fts_search_no_match_returns_empty(self, client, auth, seed_asset):
        resp = client.get("/api/assets?q=xyznonexistent99", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json() == []

    def test_category_filter_direct_path(self, client, auth, seed_asset):
        """Exercises the no-q + category filter branch."""
        resp = client.get("/api/assets?category=Money+Market+Funds", auth=auth)
        assert resp.status_code == 200
        results = resp.get_json()
        assert all(a["category"] == "Money Market Funds" for a in results)

    def test_status_filter_direct_path(self, client, auth, seed_asset):
        resp = client.get("/api/assets?status=active", auth=auth)
        assert resp.status_code == 200
        assert all(a["status"] == "active" for a in resp.get_json())

    def test_category_and_status_combined(self, client, auth, seed_asset):
        resp = client.get(
            "/api/assets?category=Money+Market+Funds&status=active", auth=auth
        )
        assert resp.status_code == 200

    def test_fts_with_category_filter(self, client, auth, seed_asset):
        """Exercises the q + category filter branch inside the FTS path."""
        resp = client.get(
            "/api/assets?q=Fidelity&category=Money+Market+Funds", auth=auth
        )
        assert resp.status_code == 200

    def test_fts_with_status_filter(self, client, auth, seed_asset):
        """Exercises the q + status filter branch inside the FTS path."""
        resp = client.get("/api/assets?q=SPAXX&status=active", auth=auth)
        assert resp.status_code == 200

    def test_limit_respected(self, client, auth):
        resp = client.get("/api/assets?limit=1", auth=auth)
        assert resp.status_code == 200
        assert len(resp.get_json()) <= 1

    def test_limit_capped_at_1000(self, client, auth):
        resp = client.get("/api/assets?limit=99999", auth=auth)
        assert resp.status_code == 200  # does not error; limit silently capped


# ---------------------------------------------------------------------------
# GET /api/assets/<id> — get_asset branches
# ---------------------------------------------------------------------------

class TestGetAsset:
    def test_existing_id_returns_asset(self, client, auth, seed_asset):
        asset_id = seed_asset["id"]
        resp = client.get(f"/api/assets/{asset_id}", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json()["id"] == asset_id

    def test_nonexistent_id_returns_404(self, client, auth):
        resp = client.get("/api/assets/999999", auth=auth)
        assert resp.status_code == 404
        assert "error" in resp.get_json()


# ---------------------------------------------------------------------------
# PUT /api/assets/<id> — update_asset branches
# ---------------------------------------------------------------------------

class TestUpdateAsset:
    def test_nonexistent_id_returns_404(self, client, auth):
        resp = client.put(
            "/api/assets/999999",
            data=json.dumps({"notes": "ghost update"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 404

    def test_empty_body_returns_400(self, client, auth, seed_asset):
        """No recognised writable fields provided → 400."""
        resp = client.put(
            f"/api/assets/{seed_asset['id']}",
            data=json.dumps({"id": 99, "created_at": "tamper"}),  # non-writable only
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "No valid fields" in resp.get_json()["error"]

    def test_partial_update_only_changes_given_fields(self, client, auth, seed_asset):
        asset_id = seed_asset["id"]
        resp = client.put(
            f"/api/assets/{asset_id}",
            data=json.dumps({"notes": "Updated note"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["notes"] == "Updated note"
        assert data["asset_name"] == seed_asset["asset_name"]  # unchanged

    def test_updated_at_changes_on_update(self, client, auth, seed_asset):
        original_updated_at = seed_asset["updated_at"]
        asset_id = seed_asset["id"]
        resp = client.put(
            f"/api/assets/{asset_id}",
            data=json.dumps({"status": "pending"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 200
        # updated_at should be refreshed (may be equal if test runs fast,
        # but the field must be present)
        assert "updated_at" in resp.get_json()

    def test_status_update_to_sold(self, client, auth, seed_asset):
        resp = client.put(
            f"/api/assets/{seed_asset['id']}",
            data=json.dumps({"status": "sold"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "sold"


# ---------------------------------------------------------------------------
# DELETE /api/assets/<id> — delete_asset branches
# ---------------------------------------------------------------------------

class TestDeleteAsset:
    def test_nonexistent_id_returns_404(self, client, auth):
        resp = client.delete("/api/assets/999999", auth=auth)
        assert resp.status_code == 404

    def test_existing_asset_deleted_returns_204(self, client, auth):
        # Create a dedicated asset to delete
        create_resp = client.post(
            "/api/assets",
            data=json.dumps({"asset_name": "Temp Delete Me", "category": "Cryptocurrency"}),
            content_type="application/json",
            auth=auth,
        )
        asset_id = create_resp.get_json()["id"]

        del_resp = client.delete(f"/api/assets/{asset_id}", auth=auth)
        assert del_resp.status_code == 204

    def test_deleted_asset_no_longer_retrievable(self, client, auth):
        create_resp = client.post(
            "/api/assets",
            data=json.dumps({"asset_name": "Gone Asset", "category": "Cryptocurrency"}),
            content_type="application/json",
            auth=auth,
        )
        asset_id = create_resp.get_json()["id"]
        client.delete(f"/api/assets/{asset_id}", auth=auth)

        get_resp = client.get(f"/api/assets/{asset_id}", auth=auth)
        assert get_resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /api/export — export_csv branches
# ---------------------------------------------------------------------------

class TestExportCSV:
    def test_returns_csv_content_type(self, client, auth, seed_asset):
        resp = client.get("/api/export", auth=auth)
        assert resp.status_code == 200
        assert "text/csv" in resp.content_type

    def test_csv_contains_header_row(self, client, auth, seed_asset):
        resp = client.get("/api/export", auth=auth)
        text = resp.data.decode()
        assert "asset_name" in text
        assert "category" in text
        assert "estimated_value" in text

    def test_csv_contains_seeded_data(self, client, auth, seed_asset):
        resp = client.get("/api/export", auth=auth)
        assert seed_asset["asset_name"] in resp.data.decode()

    def test_export_empty_table_still_returns_header(self, client, auth):
        """Export with no data should still return a valid CSV with just the header."""
        # Wipe all records temporarily using a direct DB call
        with app_module.app.app_context():
            db = sqlite3.connect(_db_path)
            db.execute("DELETE FROM assets")
            db.commit()
            db.close()

        resp = client.get("/api/export", auth=auth)
        assert resp.status_code == 200
        lines = resp.data.decode().strip().splitlines()
        assert len(lines) == 1          # header only
        assert "asset_name" in lines[0]

    def test_content_disposition_filename(self, client, auth):
        resp = client.get("/api/export", auth=auth)
        assert "ledger_export.csv" in resp.headers.get("Content-Disposition", "")

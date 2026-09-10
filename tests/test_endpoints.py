"""
Tests for the uncovered app.py endpoint blocks — claims, signings,
portfolio summary, CSV import, budget report, tax summary, and the
starkbank sync endpoint's missing-env path.

Follows TESTING_STANDARDS.md:
  - Pattern 1 (Value over Existence): assert business rules, not status only.
  - Pattern 2 (Inner Gate): test rejections inside-out (404 before 400).
  - Pattern 3 (Decision Matrix): filter branches covered with control records.
  - Pattern 4 (State Verification): read the DB after mutations.

Claims use the bankruptcy_claims table; signings use batch_signings.
Both tables are created by schema.sql (applied by conftest._init_database).
"""

import io

import pytest

import app as app_module  # noqa: E402
from conftest import direct_db  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers — seed a claim / signing directly into the DB for known IDs
# ---------------------------------------------------------------------------

def _seed_claim(db, claimant="Evan Burke", status="identified",
                source="PACER", claim_type="Cash", claimed_value="10000"):
    cur = db.execute(
        """INSERT INTO bankruptcy_claims
           (claimant_name, status, source, claim_type, claimed_value)
           VALUES (?, ?, ?, ?, ?)""",
        (claimant, status, source, claim_type, claimed_value),
    )
    db.commit()
    return cur.lastrowid


def _seed_signing(db, batch_ref="BATCH-001", status="pending",
                  asset_category="Cryptocurrency", signer="A. Stark",
                  num_items=3, total_value="5000"):
    cur = db.execute(
        """INSERT INTO batch_signings
           (batch_ref, status, asset_category, signer, num_items, total_value)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (batch_ref, status, asset_category, signer, num_items, total_value),
    )
    db.commit()
    return cur.lastrowid


# ===========================================================================
# Bankruptcy claims — CRUD + filters + summary
# ===========================================================================

class TestCreateClaim:
    def test_missing_claimant_name_returns_400(self, client, auth):
        resp = client.post("/api/claims", json={"case_number": "24-10042"}, auth=auth)
        assert resp.status_code == 400
        assert "claimant_name" in resp.get_json()["error"]

    def test_negative_claimed_value_rejected(self, client, auth):
        resp = client.post("/api/claims", json={"claimant_name": "Bad Claim", "claimed_value": -500}, auth=auth)
        assert resp.status_code == 400
        assert "cannot be negative" in resp.get_json()["error"]
        assert direct_db().execute("SELECT id FROM bankruptcy_claims WHERE claimant_name = 'Bad Claim'").fetchone() is None

    def test_claim_created_and_persisted(self, client, auth):
        resp = client.post("/api/claims", json={"claimant_name": "Acme Claimant",
            "case_number": "24-10042", "source": "PACER", "claim_type": "Securities",
            "claimed_value": 25000, "status": "identified"}, auth=auth)
        assert resp.status_code == 201
        claim_id = resp.get_json()["id"]
        row = direct_db().execute(
            "SELECT claimant_name, claimed_value, status, source FROM bankruptcy_claims WHERE id = ?",
            (claim_id,)).fetchone()
        assert row["claimant_name"] == "Acme Claimant"
        assert row["claimed_value"] == "25000.0000"
        assert row["status"] == "identified"
        assert row["source"] == "PACER"

    def test_blank_claimant_name_rejected(self, client, auth):
        resp = client.post("/api/claims", json={"claimant_name": "   "}, auth=auth)
        assert resp.status_code == 400
        assert "blank" in resp.get_json()["error"]


class TestGetClaim:
    def test_existing_claim_returns_200(self, client, auth, db_conn):
        cid = _seed_claim(db_conn)
        resp = client.get(f"/api/claims/{cid}", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json()["id"] == cid
        assert resp.get_json()["claimant_name"] == "Evan Burke"

    def test_nonexistent_returns_404(self, client, auth):
        resp = client.get("/api/claims/999999", auth=auth)
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Not found"


class TestUpdateClaim:
    def test_nonexistent_returns_404(self, client, auth):
        resp = client.put("/api/claims/999999", json={"status": "filed"}, auth=auth)
        assert resp.status_code == 404

    def test_empty_fields_returns_400(self, client, auth, db_conn):
        cid = _seed_claim(db_conn)
        resp = client.put(f"/api/claims/{cid}", json={"id": 99}, auth=auth)
        assert resp.status_code == 400
        assert "No valid fields" in resp.get_json()["error"]

    def test_status_advance_persists(self, client, auth, db_conn):
        cid = _seed_claim(db_conn, status="identified")
        resp = client.put(f"/api/claims/{cid}", json={"status": "recovered",
            "recovered_value": "7500", "recovery_date": "2025-04-09"}, auth=auth)
        assert resp.status_code == 200
        row = direct_db().execute(
            "SELECT status, recovered_value FROM bankruptcy_claims WHERE id = ?", (cid,)
        ).fetchone()
        assert row["status"] == "recovered"
        assert row["recovered_value"] == "7500.0000"

    def test_negative_recovered_value_rejected(self, client, auth, db_conn):
        cid = _seed_claim(db_conn)
        resp = client.put(f"/api/claims/{cid}", json={"recovered_value": -1}, auth=auth)
        assert resp.status_code == 400
        assert "cannot be negative" in resp.get_json()["error"]


class TestListClaims:
    def test_filters_by_status(self, client, auth, db_conn):
        _seed_claim(db_conn, claimant="Alpha", status="identified")
        _seed_claim(db_conn, claimant="Beta", status="recovered")
        resp = client.get("/api/claims?status=recovered", auth=auth)
        assert resp.status_code == 200
        results = resp.get_json()
        assert all(r["status"] == "recovered" for r in results)
        assert any(r["claimant_name"] == "Beta" for r in results)
        assert all(r["claimant_name"] != "Alpha" for r in results)
        assert all(r["status"] != "identified" for r in results)

    def test_filters_by_claimant_partial(self, client, auth, db_conn):
        _seed_claim(db_conn, claimant="Evan Burke")
        _seed_claim(db_conn, claimant="Other Party")
        resp = client.get("/api/claims?claimant=evan", auth=auth)
        results = resp.get_json()
        assert resp.status_code == 200
        assert any("Evan Burke" == r["claimant_name"] for r in results)
        assert all("Other Party" != r["claimant_name"] for r in results)

    def test_limit_capped(self, client, auth):
        resp = client.get("/api/claims?limit=99999", auth=auth)
        assert resp.status_code == 200


class TestClaimsSummary:
    def test_returns_list(self, client, auth, db_conn):
        _seed_claim(db_conn, claimant="Sum Test")
        resp = client.get("/api/claims/summary", auth=auth)
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)


# ===========================================================================
# Batch signings — CRUD + filters
# ===========================================================================

class TestCreateSigning:
    def test_missing_batch_ref_returns_400(self, client, auth):
        resp = client.post("/api/signings", json={"signer": "X"}, auth=auth)
        assert resp.status_code == 400
        assert "batch_ref" in resp.get_json()["error"]

    def test_zero_total_value_rejected(self, client, auth):
        resp = client.post("/api/signings", json={"batch_ref": "B-Z", "total_value": 0}, auth=auth)
        assert resp.status_code == 400
        assert "greater than zero" in resp.get_json()["error"]
        assert direct_db().execute("SELECT id FROM batch_signings WHERE batch_ref = 'B-Z'").fetchone() is None

    def test_negative_num_items_rejected(self, client, auth):
        resp = client.post("/api/signings", json={"batch_ref": "B-N", "num_items": -2}, auth=auth)
        assert resp.status_code == 400
        assert "negative" in resp.get_json()["error"]
        assert direct_db().execute("SELECT id FROM batch_signings WHERE batch_ref = 'B-N'").fetchone() is None

    def test_signing_created_and_persisted(self, client, auth):
        resp = client.post("/api/signings", json={"batch_ref": "BATCH-OK",
            "asset_category": "Cryptocurrency", "signer": "A. Stark",
            "num_items": 5, "total_value": 12000, "status": "pending"}, auth=auth)
        assert resp.status_code == 201
        sid = resp.get_json()["id"]
        row = direct_db().execute(
            "SELECT batch_ref, total_value, num_items, signer FROM batch_signings WHERE id = ?",
            (sid,)).fetchone()
        assert row["batch_ref"] == "BATCH-OK"
        assert row["total_value"] == "12000.0000"
        assert row["num_items"] == 5
        assert row["signer"] == "A. Stark"


class TestGetSigning:
    def test_nonexistent_returns_404(self, client, auth):
        resp = client.get("/api/signings/999999", auth=auth)
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Not found"

    def test_existing_returns_record(self, client, auth, db_conn):
        sid = _seed_signing(db_conn)
        resp = client.get(f"/api/signings/{sid}", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json()["id"] == sid


class TestUpdateSigning:
    def test_nonexistent_returns_404(self, client, auth):
        resp = client.put("/api/signings/999999", json={"status": "signed"}, auth=auth)
        assert resp.status_code == 404

    def test_empty_fields_returns_400(self, client, auth, db_conn):
        sid = _seed_signing(db_conn)
        resp = client.put(f"/api/signings/{sid}", json={"id": 1}, auth=auth)
        assert resp.status_code == 400
        assert "No valid fields" in resp.get_json()["error"]

    def test_status_advance_to_signed_persists(self, client, auth, db_conn):
        sid = _seed_signing(db_conn, status="pending")
        resp = client.put(f"/api/signings/{sid}", json={"status": "signed"}, auth=auth)
        assert resp.status_code == 200
        row = direct_db().execute(
            "SELECT status, updated_at FROM batch_signings WHERE id = ?", (sid,)
        ).fetchone()
        assert row["status"] == "signed"
        assert row["updated_at"] is not None


class TestListSignings:
    def test_filters_by_status(self, client, auth, db_conn):
        _seed_signing(db_conn, batch_ref="P-1", status="pending")
        _seed_signing(db_conn, batch_ref="S-1", status="signed")
        resp = client.get("/api/signings?status=signed", auth=auth)
        assert resp.status_code == 200
        results = resp.get_json()
        assert all(r["status"] == "signed" for r in results)
        assert any(r["batch_ref"] == "S-1" for r in results)
        assert all(r["batch_ref"] != "P-1" for r in results)

    def test_filters_by_category(self, client, auth, db_conn):
        _seed_signing(db_conn, batch_ref="C-1", asset_category="Cryptocurrency")
        _seed_signing(db_conn, batch_ref="S-1", asset_category="Securities & Commodities")
        resp = client.get("/api/signings?asset_category=Cryptocurrency", auth=auth)
        assert resp.status_code == 200
        results = resp.get_json()
        assert all(r["asset_category"] == "Cryptocurrency" for r in results)
        assert all(r["asset_category"] != "Securities & Commodities" for r in results)
        assert any(r["batch_ref"] == "C-1" for r in results)


# ===========================================================================
# Portfolio summary
# ===========================================================================

class TestPortfolioSummary:
    def test_returns_list(self, client, auth, db_conn):
        db_conn.execute("INSERT INTO assets (asset_name, category, beneficial_owner, status, estimated_value, unit) VALUES (?, ?, ?, ?, ?, ?)",
            ("BTC Test", "Cryptocurrency", "All-Star Financial Holdings", "active", "50000", "BTC"))
        db_conn.commit()
        resp = client.get("/api/portfolio/summary", auth=auth)
        assert resp.status_code == 200
        data = resp.get_json()
        assert isinstance(data, list)
        assert any(r["category"] == "Cryptocurrency" and r["asset_count"] >= 1 for r in data)

    def test_filter_by_owner_excludes_others(self, client, auth, db_conn):
        db_conn.execute("INSERT INTO assets (asset_name, category, beneficial_owner, status, estimated_value) VALUES (?, ?, ?, ?, ?)",
            ("Own1", "Cryptocurrency", "OwnerX", "active", "100"))
        db_conn.execute("INSERT INTO assets (asset_name, category, beneficial_owner, status, estimated_value) VALUES (?, ?, ?, ?, ?)",
            ("Own2", "Cryptocurrency", "OwnerY", "active", "100"))
        db_conn.commit()
        resp = client.get("/api/portfolio/summary?owner=OwnerX", auth=auth)
        assert resp.status_code == 200
        results = resp.get_json()
        assert all(r["beneficial_owner"] == "OwnerX" for r in results)
        assert all(r["beneficial_owner"] != "OwnerY" for r in results)


# ===========================================================================
# Tax summary endpoint
# ===========================================================================

class TestTaxSummary:
    def test_returns_report_json(self, client, auth):
        resp = client.get("/api/tax/summary", auth=auth)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "tax_year" in data
        assert "summary" in data
        assert "capital_gains" in data

    def test_year_param_accepted(self, client, auth):
        resp = client.get("/api/tax/summary?year=2024", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json()["tax_year"] == 2024


# ===========================================================================
# Stark Bank sync endpoint — missing env vars path (no network)
# ===========================================================================

class TestStarkbankSyncEndpoint:
    def test_missing_env_returns_503(self, client, auth, monkeypatch):
        for v in ("STARKBANK_ENVIRONMENT", "STARKBANK_PROJECT_ID", "STARKBANK_PRIVATE_KEY"):
            monkeypatch.delenv(v, raising=False)
        resp = client.post("/api/sync/starkbank", auth=auth)
        assert resp.status_code == 503
        assert "Missing env vars" in resp.get_json()["error"]
        assert "STARKBANK_ENVIRONMENT" in resp.get_json()["error"]


# ===========================================================================
# Budget report endpoint
# ===========================================================================

class TestBudgetReport:
    def test_date_filter_with_no_rows_returns_zero_summary(self, client, auth):
        # Scope to a future date window with no rows -> exercises the after/before
        # filter branch AND the empty-rows early return (zero summary + items).
        resp = client.get("/api/reports/budget?after=2999-01-01&before=2999-12-31", auth=auth)
        assert resp.status_code == 200
        data = resp.get_json()
        assert set(data.keys()) == {"summary", "items"}
        assert data["summary"] == {"over": 0, "warning": 0, "ok": 0}
        assert data["items"] == []

    def test_with_expense_data(self, client, auth, db_conn):
        db_conn.execute("INSERT INTO assets (asset_name, category, description, subcategory, estimated_value, status) VALUES (?, ?, ?, ?, ?, ?)",
            ("AWS Cloud", "Computer Resources", "AWS cloud invoice", "Debit/Expense", "6000", "active"))
        db_conn.commit()
        resp = client.get("/api/reports/budget", auth=auth)
        assert resp.status_code == 200
        items = resp.get_json()["items"]
        tech = next((i for i in items if i["category"] == "Technology"), None)
        assert tech is not None
        assert tech["actual"] == 6000.0
        assert tech["status"] == "over"
        assert tech["variance"] == round(5000.0 - 6000.0, 2)


# ===========================================================================
# CSV import endpoint
# ===========================================================================

class TestCsvImport:
    def test_no_file_field_returns_400(self, client, auth):
        resp = client.post("/api/import/csv", auth=auth)
        assert resp.status_code == 400
        assert "file" in resp.get_json()["error"]

    def test_non_csv_extension_rejected(self, client, auth):
        resp = client.post("/api/import/csv", auth=auth, data={"file": (io.BytesIO(b"data"), "report.xlsx")})
        assert resp.status_code == 400
        assert ".csv" in resp.get_json()["error"]
        assert direct_db().execute("SELECT id FROM assets WHERE asset_name = 'data'").fetchone() is None

    def test_imports_valid_csv(self, client, auth):
        csv_bytes = b"asset_name,category,estimated_value\nImpAsset,Cryptocurrency,1000\n"
        resp = client.post("/api/import/csv", auth=auth, data={
            "file": (io.BytesIO(csv_bytes), "ledger.csv")})
        assert resp.status_code == 200
        result = resp.get_json()
        assert result["inserted"] == 1
        assert result["errors"] == []
        row = direct_db().execute(
            "SELECT category, estimated_value FROM assets WHERE asset_name = 'ImpAsset'"
        ).fetchone()
        assert row["category"] == "Cryptocurrency"
        assert row["estimated_value"] == "1000.0000"

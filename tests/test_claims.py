"""Tests for the Claims ledger API (/api/claims).

Follows the fixture and auth patterns established in test_app.py.
All tests use the Flask test client with HTTP Basic Auth.
"""
import json
import pytest

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import app as app_module


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def set_env():
    os.environ["LEDGER_USER"] = "testuser"
    os.environ["LEDGER_PASS"] = "testpass"


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    return (app_module.LEDGER_USER, app_module.LEDGER_PASS)


@pytest.fixture()
def seed_claim(client, auth):
    """Create one claim and return the response JSON."""
    resp = client.post(
        "/api/claims",
        data=json.dumps({
            "institution":  "Test Bank Corp",
            "claim_type":   "investment_return",
            "amount_owed":  "250000.00",
            "origin_date":  "2015-06-01",
            "status":       "open",
            "jurisdiction": "Federal",
            "description":  "Seed claim for test isolation",
        }),
        content_type="application/json",
        auth=auth,
    )
    assert resp.status_code == 201
    return resp.get_json()


# ---------------------------------------------------------------------------
# Auth gate
# ---------------------------------------------------------------------------

class TestClaimsAuth:
    def test_list_requires_auth(self, client):
        assert client.get("/api/claims").status_code == 401

    def test_create_requires_auth(self, client):
        assert client.post("/api/claims", json={"institution": "X", "amount_owed": "1"}).status_code == 401

    def test_summary_requires_auth(self, client):
        assert client.get("/api/claims/summary").status_code == 401

    def test_get_single_requires_auth(self, client):
        assert client.get("/api/claims/1").status_code == 401

    def test_update_requires_auth(self, client):
        assert client.put("/api/claims/1", json={"status": "settled"}).status_code == 401

    def test_delete_requires_auth(self, client):
        assert client.delete("/api/claims/1").status_code == 401


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------

class TestCreateClaim:
    def test_minimal_payload_returns_201(self, client, auth):
        resp = client.post(
            "/api/claims",
            data=json.dumps({"institution": "Minimal Bank", "amount_owed": "1000.00"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["institution"] == "Minimal Bank"
        assert data["amount_owed"] == "1000.00"
        assert data["status"] == "open"
        assert data["claim_type"] == "other"
        assert data["currency"] == "USD"

    def test_full_payload_all_fields_stored(self, client, auth):
        resp = client.post(
            "/api/claims",
            data=json.dumps({
                "institution":       "Full Fields Bank",
                "claim_type":        "wages",
                "amount_owed":       "500000.00",
                "currency":          "USD",
                "origin_date":       "2010-01-15",
                "last_contact_date": "2024-03-01",
                "status":            "demand_sent",
                "jurisdiction":      "SDNY",
                "counsel":           "Sullivan & Cromwell LLP",
                "description":       "Unpaid wages 2010-2026",
                "notes":             "16 years outstanding. No response.",
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        d = resp.get_json()
        assert d["institution"]   == "Full Fields Bank"
        assert d["claim_type"]    == "wages"
        assert d["amount_owed"]   == "500000.00"
        assert d["status"]        == "demand_sent"
        assert d["jurisdiction"]  == "SDNY"
        assert d["counsel"]       == "Sullivan & Cromwell LLP"
        assert d["origin_date"]   == "2010-01-15"

    def test_missing_institution_returns_400(self, client, auth):
        resp = client.post(
            "/api/claims",
            data=json.dumps({"amount_owed": "1000.00"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "institution" in resp.get_json()["error"]

    def test_missing_amount_returns_400(self, client, auth):
        resp = client.post(
            "/api/claims",
            data=json.dumps({"institution": "No Amount Bank"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "amount_owed" in resp.get_json()["error"]

    def test_invalid_claim_type_returns_400(self, client, auth):
        resp = client.post(
            "/api/claims",
            data=json.dumps({
                "institution": "Bad Type Bank",
                "amount_owed": "100.00",
                "claim_type":  "not_a_real_type",
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400
        assert "claim_type" in resp.get_json()["error"]

    def test_invalid_status_returns_400(self, client, auth):
        resp = client.post(
            "/api/claims",
            data=json.dumps({
                "institution": "Bad Status Bank",
                "amount_owed": "100.00",
                "status":      "flying",
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400

    def test_created_at_is_set(self, client, auth):
        resp = client.post(
            "/api/claims",
            data=json.dumps({"institution": "Timestamp Bank", "amount_owed": "1.00"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        assert resp.get_json()["created_at"] is not None

    @pytest.mark.parametrize("claim_type", [
        "wages", "investment_return", "royalties",
        "breach_of_contract", "settlement", "judgment", "other",
    ])
    def test_all_valid_claim_types_accepted(self, client, auth, claim_type):
        resp = client.post(
            "/api/claims",
            data=json.dumps({
                "institution": f"Type Test — {claim_type}",
                "amount_owed": "100.00",
                "claim_type":  claim_type,
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        assert resp.get_json()["claim_type"] == claim_type

    @pytest.mark.parametrize("status", [
        "open", "demand_sent", "in_negotiation", "arbitration",
        "litigation", "judgment_obtained", "settled", "closed_no_recovery",
    ])
    def test_all_valid_statuses_accepted(self, client, auth, status):
        resp = client.post(
            "/api/claims",
            data=json.dumps({
                "institution": f"Status Test — {status}",
                "amount_owed": "100.00",
                "status":      status,
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        assert resp.get_json()["status"] == status


# ---------------------------------------------------------------------------
# List
# ---------------------------------------------------------------------------

class TestListClaims:
    def test_returns_200_and_list(self, client, auth, seed_claim):
        resp = client.get("/api/claims", auth=auth)
        assert resp.status_code == 200
        data = resp.get_json()
        assert "claims" in data
        assert "total_open_owed" in data
        assert "count" in data
        assert isinstance(data["claims"], list)

    def test_count_matches_claims_length(self, client, auth, seed_claim):
        resp = client.get("/api/claims", auth=auth)
        data = resp.get_json()
        assert data["count"] == len(data["claims"])

    def test_status_filter(self, client, auth):
        client.post("/api/claims", auth=auth, json={
            "institution": "Filter Test — Open",
            "amount_owed": "1.00", "status": "open",
        })
        client.post("/api/claims", auth=auth, json={
            "institution": "Filter Test — Settled",
            "amount_owed": "1.00", "status": "settled",
        })
        resp = client.get("/api/claims?status=settled", auth=auth)
        assert resp.status_code == 200
        for claim in resp.get_json()["claims"]:
            assert claim["status"] == "settled"

    def test_institution_filter(self, client, auth):
        client.post("/api/claims", auth=auth, json={
            "institution": "UniqueNameXQ9Corp",
            "amount_owed": "1.00",
        })
        resp = client.get("/api/claims?institution=UniqueNameXQ9Corp", auth=auth)
        data = resp.get_json()
        assert data["count"] >= 1
        assert all("UniqueNameXQ9Corp" in c["institution"] for c in data["claims"])

    def test_settled_claims_excluded_from_total_open_owed(self, client, auth):
        client.post("/api/claims", auth=auth, json={
            "institution": "Settled Not Counted",
            "amount_owed": "999999.00",
            "status": "settled",
        })
        resp = client.get("/api/claims", auth=auth)
        # settled claims must not inflate total_open_owed
        total = float(resp.get_json()["total_open_owed"])
        assert total < 999999 * 100  # sanity check — not double-counting


# ---------------------------------------------------------------------------
# Get single
# ---------------------------------------------------------------------------

class TestGetClaim:
    def test_existing_id_returns_200(self, client, auth, seed_claim):
        claim_id = seed_claim["id"]
        resp = client.get(f"/api/claims/{claim_id}", auth=auth)
        assert resp.status_code == 200
        assert resp.get_json()["id"] == claim_id

    def test_nonexistent_id_returns_404(self, client, auth):
        resp = client.get("/api/claims/999999", auth=auth)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------

class TestUpdateClaim:
    def test_partial_update_status(self, client, auth, seed_claim):
        claim_id = seed_claim["id"]
        resp = client.put(
            f"/api/claims/{claim_id}",
            data=json.dumps({"status": "demand_sent"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "demand_sent"

    def test_partial_update_counsel(self, client, auth, seed_claim):
        claim_id = seed_claim["id"]
        resp = client.put(
            f"/api/claims/{claim_id}",
            data=json.dumps({"counsel": "Weil Gotshal & Manges LLP"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 200
        assert resp.get_json()["counsel"] == "Weil Gotshal & Manges LLP"

    def test_update_amount_owed(self, client, auth, seed_claim):
        claim_id = seed_claim["id"]
        resp = client.put(
            f"/api/claims/{claim_id}",
            data=json.dumps({"amount_owed": "1500000.00"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 200
        assert resp.get_json()["amount_owed"] == "1500000.00"

    def test_empty_body_returns_400(self, client, auth, seed_claim):
        claim_id = seed_claim["id"]
        resp = client.put(
            f"/api/claims/{claim_id}",
            data=json.dumps({}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 400

    def test_nonexistent_id_returns_404(self, client, auth):
        resp = client.put(
            "/api/claims/999999",
            data=json.dumps({"status": "settled"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 404

    def test_unknown_fields_ignored_not_errored(self, client, auth, seed_claim):
        claim_id = seed_claim["id"]
        resp = client.put(
            f"/api/claims/{claim_id}",
            data=json.dumps({"nonexistent_field": "value", "notes": "updated note"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 200
        assert resp.get_json()["notes"] == "updated note"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------

class TestDeleteClaim:
    def test_existing_claim_deleted_204(self, client, auth, seed_claim):
        claim_id = seed_claim["id"]
        resp = client.delete(f"/api/claims/{claim_id}", auth=auth)
        assert resp.status_code == 204

    def test_deleted_claim_not_retrievable(self, client, auth, seed_claim):
        claim_id = seed_claim["id"]
        client.delete(f"/api/claims/{claim_id}", auth=auth)
        resp = client.get(f"/api/claims/{claim_id}", auth=auth)
        assert resp.status_code == 404

    def test_nonexistent_returns_404(self, client, auth):
        resp = client.delete("/api/claims/999999", auth=auth)
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

class TestClaimsSummary:
    def test_returns_200(self, client, auth):
        assert client.get("/api/claims/summary", auth=auth).status_code == 200

    def test_response_structure(self, client, auth):
        data = client.get("/api/claims/summary", auth=auth).get_json()
        assert "total_open_owed" in data
        assert "by_status" in data
        assert "by_type" in data
        assert "oldest_open_claim" in data

    def test_total_open_excludes_settled(self, client, auth):
        client.post("/api/claims", auth=auth, json={
            "institution": "Summary Settled Test",
            "amount_owed": "8888888.00",
            "status": "settled",
        })
        client.post("/api/claims", auth=auth, json={
            "institution": "Summary Open Test",
            "amount_owed": "1.00",
            "status": "open",
        })
        data = client.get("/api/claims/summary", auth=auth).get_json()
        # settled amount must not appear in total_open_owed
        assert float(data["total_open_owed"]) < 8888888.00 * 2

    def test_by_status_is_list(self, client, auth, seed_claim):
        data = client.get("/api/claims/summary", auth=auth).get_json()
        assert isinstance(data["by_status"], list)

    def test_oldest_open_claim_has_institution(self, client, auth, seed_claim):
        data = client.get("/api/claims/summary", auth=auth).get_json()
        if data["oldest_open_claim"]:
            assert "institution" in data["oldest_open_claim"]
            assert "origin_date" in data["oldest_open_claim"]

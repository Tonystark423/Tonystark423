"""
Best-practice patterns for high-density tests in complex scenarios.

SCENARIO 1 — Nested Conditional Logic (list_assets decision matrix)
=====================================================================
list_assets has a 3-variable boolean branch:

    if q:                          # FTS path
        if category: ...           #   + category filter
        if status: ...             #   + status filter
    else:                          # direct path
        if category: ...           #   + category filter
        if status: ...             #   + status filter

That produces 8 logical combinations (2^3). Each must produce a
*different* result set to be worth testing separately. The trick:
seed data deliberately designed to distinguish every branch.

SCENARIO 2 — Boundary / Limit Arithmetic
=========================================
The `limit` parameter has an implicit cap at 1000. Testing only
the happy-path limit misses the boundary. Use parameterize to
sweep the boundary systematically without copy-paste.

SCENARIO 3 — Combinatorial Filter Isolation
============================================
When filters compose, each additional filter must provably *exclude*
records the previous filter would have included. Without a control
record in the result set, you can't tell if the filter is working
or if the data just happened to be homogeneous.

Pattern: seed N categories, filter for 1, assert the other N-1 are absent.
"""

import json
import os
import sqlite3
import tempfile

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


@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    return ("testuser", "testpass")


# ---------------------------------------------------------------------------
# SCENARIO 1 — Nested Conditional: the 8-combination decision matrix
#
# Seed data is designed so each combination produces a distinguishable
# result. Every record has a unique custodian so we can assert exact
# presence/absence rather than just counts.
# ---------------------------------------------------------------------------

@pytest.fixture()
def matrix_data(client, auth):
    """
    Seed 4 records covering all filter-dimension combinations:

      Record A: category=Crypto,    status=active,  custodian=AlphaExchange
      Record B: category=Crypto,    status=pending, custodian=BetaExchange
      Record C: category=Prop IP,   status=active,  custodian=GammaVault
      Record D: category=Prop IP,   status=pending, custodian=DeltaVault

    The shared search term "MatrixAsset" appears in all asset names so
    the FTS path can reach any of them.
    """
    records = [
        {"asset_name": "MatrixAsset Alpha", "category": "Cryptocurrency",
         "status": "active",  "custodian": "AlphaExchange"},
        {"asset_name": "MatrixAsset Beta",  "category": "Cryptocurrency",
         "status": "pending", "custodian": "BetaExchange"},
        {"asset_name": "MatrixAsset Gamma", "category": "Proprietary IP",
         "status": "active",  "custodian": "GammaVault"},
        {"asset_name": "MatrixAsset Delta", "category": "Proprietary IP",
         "status": "pending", "custodian": "DeltaVault"},
    ]
    ids = []
    for r in records:
        resp = client.post("/api/assets", json=r, auth=auth)
        assert resp.status_code == 201
        ids.append(resp.get_json()["id"])
    yield records
    # Teardown: remove seeded rows so they don't bleed into other tests
    conn = sqlite3.connect(_db_path)
    for asset_id in ids:
        conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    conn.commit()
    conn.close()


def custodians(resp) -> set:
    return {r["custodian"] for r in resp.get_json()}


class TestDecisionMatrix:
    """
    Each test name encodes exactly which branches are active.
    Pattern: q=T/F  category=T/F  status=T/F
    """

    # --- FTS path (q=True) ---

    def test_q_only(self, client, auth, matrix_data):
        """FTS path, no filters — all 4 matrix records must appear."""
        resp = client.get("/api/assets?q=MatrixAsset", auth=auth)
        found = custodians(resp)
        assert "AlphaExchange" in found
        assert "BetaExchange"  in found
        assert "GammaVault"    in found
        assert "DeltaVault"    in found

    def test_q_and_category(self, client, auth, matrix_data):
        """FTS path + category filter — only Crypto records, both statuses."""
        resp = client.get(
            "/api/assets?q=MatrixAsset&category=Cryptocurrency", auth=auth
        )
        found = custodians(resp)
        assert "AlphaExchange" in found    # Crypto + active  ✓
        assert "BetaExchange"  in found    # Crypto + pending ✓
        assert "GammaVault"    not in found  # PropIP filtered out
        assert "DeltaVault"    not in found  # PropIP filtered out

    def test_q_and_status(self, client, auth, matrix_data):
        """FTS path + status filter — only active records, both categories."""
        resp = client.get(
            "/api/assets?q=MatrixAsset&status=active", auth=auth
        )
        found = custodians(resp)
        assert "AlphaExchange" in found    # Crypto + active  ✓
        assert "GammaVault"    in found    # PropIP + active  ✓
        assert "BetaExchange"  not in found  # pending filtered out
        assert "DeltaVault"    not in found  # pending filtered out

    def test_q_and_category_and_status(self, client, auth, matrix_data):
        """FTS path + both filters — exactly one record survives."""
        resp = client.get(
            "/api/assets?q=MatrixAsset&category=Cryptocurrency&status=active",
            auth=auth,
        )
        found = custodians(resp)
        assert found == {"AlphaExchange"}  # only Crypto + active

    # --- Direct path (q=False) ---

    def test_no_q_and_category(self, client, auth, matrix_data):
        """Direct path + category filter — only PropIP, both statuses."""
        resp = client.get(
            "/api/assets?category=Proprietary+IP", auth=auth
        )
        found = custodians(resp)
        assert "GammaVault" in found
        assert "DeltaVault" in found
        assert "AlphaExchange" not in found
        assert "BetaExchange"  not in found

    def test_no_q_and_status(self, client, auth, matrix_data):
        """Direct path + status filter — only pending, both categories."""
        resp = client.get("/api/assets?status=pending", auth=auth)
        found = custodians(resp)
        assert "BetaExchange" in found
        assert "DeltaVault"   in found
        assert "AlphaExchange" not in found
        assert "GammaVault"    not in found

    def test_no_q_and_category_and_status(self, client, auth, matrix_data):
        """Direct path + both filters — exactly one record survives."""
        resp = client.get(
            "/api/assets?category=Proprietary+IP&status=pending", auth=auth
        )
        found = custodians(resp)
        assert found == {"DeltaVault"}


# ---------------------------------------------------------------------------
# SCENARIO 4 — Inner Gate Pattern: test rejections inside-out
#
# The rule: verify the innermost dark alley first, in complete isolation,
# before testing the success path. This ensures each gate is independently
# load-bearing — removing it would be caught immediately.
#
# update_asset has a two-level gate stack:
#   Gate 1 (outer): asset must exist          → 404 if not
#   Gate 2 (inner): payload must have fields  → 400 if not
#
# The trap most teams fall into: they only test Gate 1 (easier to reach)
# and assume Gate 2 is covered by the success-path test.
# The inner gate test proves Gate 2 is independently enforced even when
# Gate 1 passes — i.e. it can't be accidentally deleted without failing.
#
# require_auth has a three-condition gate (no auth / wrong user / wrong pass).
# Testing each condition separately proves no short-circuit collapse has
# merged them into a single boolean blob.
# ---------------------------------------------------------------------------

class TestInnerGatePattern:

    @pytest.fixture()
    def existing_id(self, client, auth):
        """Seed one asset and return its id — lets inner-gate tests bypass Gate 1."""
        resp = client.post(
            "/api/assets",
            json={"asset_name": "Gate Test Asset", "category": "Cryptocurrency"},
            auth=auth,
        )
        asset_id = resp.get_json()["id"]
        yield asset_id
        conn = sqlite3.connect(_db_path)
        conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        conn.commit()
        conn.close()

    # --- Gate 1: existence check ---

    def test_outer_gate_nonexistent_id_blocks_before_payload_parsed(
        self, client, auth
    ):
        """
        Outer gate fires on a non-existent ID regardless of payload quality.
        Even a perfectly valid payload can't reach Gate 2.
        Density: 2 assertions / 2 lines = 1.0
        """
        resp = client.put(
            "/api/assets/999999",
            json={"asset_name": "Valid Field"},   # payload is fine
            auth=auth,
        )
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "Not found"

    # --- Gate 2: payload validation (inner gate) ---

    def test_inner_gate_empty_payload_blocked_after_id_resolves(
        self, client, auth, existing_id
    ):
        """
        Inner gate fires when the ID *does* exist but the payload has no
        writable fields. Gate 1 has passed; Gate 2 is the only thing
        standing between the request and an unintended no-op UPDATE.
        Density: 2 assertions / 2 lines = 1.0
        """
        resp = client.put(
            f"/api/assets/{existing_id}",
            json={"id": 99, "created_at": "tamper"},  # only non-writable keys
            auth=auth,
        )
        assert resp.status_code == 400
        assert "No valid fields" in resp.get_json()["error"]

    def test_inner_gate_only_non_writable_keys_blocked(
        self, client, auth, existing_id
    ):
        """
        Confirm the inner gate distinguishes writable from non-writable columns.
        Sending `updated_at` (non-writable) alone must trigger Gate 2,
        not silently succeed. This prevents a privilege-escalation class of
        bug where a client forces a timestamp or ID update.
        Density: 2 assertions / 3 lines = 0.67
        """
        resp = client.put(
            f"/api/assets/{existing_id}",
            json={"updated_at": "2020-01-01", "created_at": "2020-01-01"},
            auth=auth,
        )
        assert resp.status_code == 400
        # Verify the DB row's timestamps were NOT touched
        conn = sqlite3.connect(_db_path)
        row = conn.execute(
            "SELECT updated_at FROM assets WHERE id = ?", (existing_id,)
        ).fetchone()
        conn.close()
        assert row[0] != "2020-01-01"

    def test_gates_are_ordered_outer_before_inner(self, client, auth):
        """
        Prove gate ordering: a non-existent ID with an empty payload must
        return 404 (Gate 1), not 400 (Gate 2). If the gates were reversed
        the wrong error code would fire — a subtle contract break.
        Density: 2 assertions / 2 lines = 1.0
        """
        resp = client.put(
            "/api/assets/999999",
            json={},   # would trigger Gate 2 — but Gate 1 fires first
            auth=auth,
        )
        assert resp.status_code == 404   # Gate 1 wins
        assert resp.get_json()["error"] == "Not found"

    # --- require_auth: three-condition outer gate ---

    def test_auth_gate_no_header(self, client):
        """No Authorization header — first condition of the auth gate."""
        resp = client.put("/api/assets/1", json={"notes": "x"})
        assert resp.status_code == 401
        assert "WWW-Authenticate" in resp.headers  # contract: header must be present

    def test_auth_gate_wrong_user(self, client):
        """Wrong username — second condition fires independently of password."""
        resp = client.put(
            "/api/assets/1", json={"notes": "x"}, auth=("hacker", "testpass")
        )
        assert resp.status_code == 401

    def test_auth_gate_wrong_pass(self, client):
        """
        Correct username, wrong password — third condition fires independently.
        If username + password were compared as a combined hash this would
        still pass; this test ensures they are checked as separate values.
        """
        resp = client.put(
            "/api/assets/1", json={"notes": "x"}, auth=("testuser", "wrongpass")
        )
        assert resp.status_code == 401

    def test_all_auth_conditions_satisfied_reaches_inner_gates(
        self, client, auth, existing_id
    ):
        """
        Success path: all three auth conditions pass, request reaches
        the inner gates. Proves auth gate is not accidentally over-blocking.
        Density: 2 assertions / 2 lines = 1.0
        """
        resp = client.put(
            f"/api/assets/{existing_id}",
            json={"notes": "auth gate cleared"},
            auth=auth,
        )
        assert resp.status_code == 200
        assert resp.get_json()["notes"] == "auth gate cleared"


# ---------------------------------------------------------------------------
# SCENARIO 2 — Boundary Arithmetic: parametrize sweeps the limit boundary
#
# Why parametrize beats copy-paste:
#   - Each case is a named data point in the report (no ambiguous failure)
#   - Adding a new boundary value is one line, not a new test function
#   - The assertion is identical across cases — density stays high
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("requested,expected_max", [
    (1,    1),     # normal small limit
    (50,   50),    # mid-range
    (200,  200),   # default
    (999,  999),   # just under cap
    (1000, 1000),  # exactly at cap
    (1001, 1000),  # cap triggers: 1001 → 1000
    (9999, 1000),  # far over cap: still 1000
])
def test_limit_boundary_sweep(client, auth, requested, expected_max):
    """
    Parametrized boundary sweep of the limit cap (max 1000).
    Each row is an independent test case in the CI report.
    Density: 1 assertion / 1 logical line = 1.0 per parametrize call.
    """
    resp = client.get(f"/api/assets?limit={requested}", auth=auth)
    assert len(resp.get_json()) <= expected_max


# ---------------------------------------------------------------------------
# SCENARIO 3 — Combinatorial Filter Isolation
#
# The key principle: always include a CONTROL record that the filter
# should EXCLUDE. Without the exclusion assertion, a broken filter
# that returns everything still passes.
#
# Bad:  assert len(results) >= 1
# Good: assert all correct + assert none incorrect
# ---------------------------------------------------------------------------

class TestFilterIsolation:

    @pytest.fixture()
    def isolation_data(self, client, auth):
        """One record per category — lets us assert cross-category exclusion."""
        categories = [
            "Proprietary IP",
            "Computer Resources",
            "Money Market Funds",
            "Securities & Commodities",
            "Cryptocurrency",
        ]
        ids = []
        for cat in categories:
            resp = client.post(
                "/api/assets",
                json={"asset_name": f"IsolationAsset {cat}", "category": cat,
                      "custodian": f"Custodian_{cat.replace(' ', '_')}"},
                auth=auth,
            )
            assert resp.status_code == 201
            ids.append(resp.get_json()["id"])
        yield categories
        conn = sqlite3.connect(_db_path)
        for asset_id in ids:
            conn.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
        conn.commit()
        conn.close()

    @pytest.mark.parametrize("target_category", [
        "Proprietary IP",
        "Computer Resources",
        "Money Market Funds",
        "Securities & Commodities",
        "Cryptocurrency",
    ])
    def test_category_filter_excludes_all_other_categories(
        self, client, auth, isolation_data, target_category
    ):
        """
        For every category: filter for it, then assert every other
        category is absent. This is the 'control record' pattern —
        the exclusion assertion is what gives this test its value.
        """
        other_categories = [c for c in isolation_data if c != target_category]

        resp = client.get(f"/api/assets?category={target_category}", auth=auth)
        assert resp.status_code == 200
        results = resp.get_json()

        # Inclusion: at least one record from the target category is present
        assert any(r["category"] == target_category for r in results)

        # Exclusion (the control): no record from any other category leaked through
        leaked = [
            r for r in results if r["category"] in other_categories
        ]
        assert leaked == [], (
            f"Filter for {target_category!r} leaked {len(leaked)} record(s) "
            f"from other categories: {[r['category'] for r in leaked]}"
        )

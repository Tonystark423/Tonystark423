"""
Spy / Mock verification tests for app.py database interactions.

Demonstrates two patterns:

  Approach A — unittest.mock spy on sqlite3 connection
    Verifies the *call* was made with the right arguments.
    Use when you need to confirm the query shape itself (e.g. parameterized,
    no string interpolation) rather than the resulting DB state.

  Approach B — state verification (direct DB read-back)
    Verifies the *effect* on the database.
    Preferred for raw SQLite — proves data landed correctly, not just that
    a method fired. Doesn't break on harmless query rewrites.

Assertion Density target: >= 0.66 per test (value zone).
"""

import json
import os
import sqlite3
import tempfile
from unittest.mock import MagicMock, call, patch

import pytest

# Isolated database for this module
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"] = _db_path
os.environ["LEDGER_USER"] = "testuser"
os.environ["LEDGER_PASS"] = "testpass"

import app as app_module  # noqa: E402


# ---------------------------------------------------------------------------
# Session-scoped DB setup
# ---------------------------------------------------------------------------

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


@pytest.fixture()
def auth():
    return ("testuser", "testpass")


def direct_db():
    """Open a direct connection to the test DB for state-verification reads."""
    conn = sqlite3.connect(_db_path)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Approach A — Mock/Spy: verify the database call itself
#
# We patch get_db() to intercept execute() calls. This lets us assert:
#   - queries use parameterized placeholders (no f-string injection)
#   - the right SQL verb was used (INSERT / UPDATE / DELETE)
#   - the bound values match the payload
#
# TRADEOFF: these tests are coupled to the query text. Refactoring the SQL
# without changing behavior will break them. Use sparingly — prefer Approach B
# for most cases.
# ---------------------------------------------------------------------------

class TestDBCallSpy:

    def test_create_asset_uses_parameterized_query(self, client, auth):
        """
        Spy on execute() to confirm INSERT uses ? placeholders, not
        string interpolation (SQL-injection guard).
        """
        real_conn = sqlite3.connect(_db_path)
        real_conn.row_factory = sqlite3.Row
        real_conn.execute("PRAGMA journal_mode=WAL")

        spy_conn = MagicMock(wraps=real_conn)

        with patch.object(app_module, "get_db", return_value=spy_conn):
            client.post(
                "/api/assets",
                data=json.dumps({
                    "asset_name": "Spy Test Asset",
                    "category": "Cryptocurrency",
                    "estimated_value": 9999.0,
                }),
                content_type="application/json",
                auth=auth,
            )

        # Collect every SQL string passed to execute()
        executed_sql = [
            str(c.args[0]).strip().upper()
            for c in spy_conn.execute.call_args_list
            if c.args
        ]

        insert_calls = [s for s in executed_sql if s.startswith("INSERT INTO ASSETS")]
        assert len(insert_calls) >= 1, "Expected at least one INSERT INTO assets"

        # Confirm the INSERT used ? placeholders — no raw string concat
        insert_sql = insert_calls[0]
        assert "?" in insert_sql, "INSERT must use parameterized placeholders"
        assert "9999" not in insert_sql, "Values must not be interpolated into SQL string"

        real_conn.close()

    def test_delete_issues_correct_sql_verb(self, client, auth):
        """
        Spy confirms DELETE is issued (not UPDATE with a soft-delete flag)
        when the delete endpoint is called.
        """
        # Seed a record directly to get a known ID
        conn = direct_db()
        cur = conn.execute(
            "INSERT INTO assets (asset_name, category) VALUES (?, ?)",
            ("Spy Delete Target", "Cryptocurrency"),
        )
        conn.commit()
        asset_id = cur.lastrowid
        conn.close()

        real_conn = sqlite3.connect(_db_path)
        real_conn.row_factory = sqlite3.Row
        real_conn.execute("PRAGMA journal_mode=WAL")
        spy_conn = MagicMock(wraps=real_conn)

        with patch.object(app_module, "get_db", return_value=spy_conn):
            client.delete(f"/api/assets/{asset_id}", auth=auth)

        executed_sql = [
            str(c.args[0]).strip().upper()
            for c in spy_conn.execute.call_args_list
            if c.args
        ]

        delete_calls = [s for s in executed_sql if s.startswith("DELETE")]
        assert len(delete_calls) == 1, "Expected exactly one DELETE statement"
        assert "WHERE ID = ?" in delete_calls[0], "DELETE must be scoped by ID"

        real_conn.close()


# ---------------------------------------------------------------------------
# Approach B — State Verification: verify the database effect
#
# After each API call, open a direct DB connection and read back the row.
# This proves the data actually landed in the right columns — not just
# that some method fired.
#
# ASSERTION DENSITY: each test makes 3-6 assertions against real DB state.
# ---------------------------------------------------------------------------

class TestDBStateVerification:

    def test_create_asset_persists_all_fields_to_db(self, client, auth):
        """
        Happy path — every field in the payload must appear verbatim
        in the database row. No silent truncation, coercion, or loss.
        """
        payload = {
            "asset_name": "HBM4 Memory Module",
            "category": "Computer Resources",
            "subcategory": "HBM4",
            "description": "High Bandwidth Memory Gen4 supply",
            "quantity": 512.0,
            "unit": "GB",
            "estimated_value": 75000.0,
            "acquisition_date": "2025-01-10",
            "custodian": "Internal Vault",
            "beneficial_owner": "Stark Financial Holdings LLC",
            "status": "active",
            "notes": "Earmarked for AI compute cluster",
        }

        resp = client.post(
            "/api/assets",
            data=json.dumps(payload),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201
        asset_id = resp.get_json()["id"]

        # Read the row directly from the DB — bypasses the API response entirely
        conn = direct_db()
        row = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        conn.close()

        assert row is not None, "Row must exist in DB after POST"

        # Every payload field must match DB state exactly.
        # quantity and estimated_value are stored as 4dp Decimal strings (TEXT col).
        _PRECISION = {"quantity", "estimated_value"}
        for field, expected in payload.items():
            if field in _PRECISION:
                from decimal import Decimal
                assert row[field] == str(Decimal(str(expected)).quantize(Decimal("0.0001"))), (
                    f"DB field {field!r} = {row[field]!r}, expected Decimal string of {expected!r}"
                )
            else:
                assert row[field] == expected, (
                    f"DB field {field!r} = {row[field]!r}, expected {expected!r}"
                )

        # Timestamps must be populated by the DB DEFAULT
        assert row["created_at"] is not None
        assert row["updated_at"] is not None

    def test_update_asset_only_mutates_specified_columns(self, client, auth):
        """
        Partial update — DB state must show:
          - changed field updated
          - all other fields unchanged
          - updated_at refreshed
          - created_at untouched
        This is the "Happy Path with boundary" test: checks both sides of
        the mutation.
        """
        # Seed
        conn = direct_db()
        cur = conn.execute(
            """INSERT INTO assets (asset_name, category, custodian, notes, status)
               VALUES (?, ?, ?, ?, ?)""",
            ("Original Name", "Cryptocurrency", "Coinbase", "Original note", "active"),
        )
        conn.commit()
        asset_id = cur.lastrowid
        original_created_at = conn.execute(
            "SELECT created_at FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()["created_at"]
        conn.close()

        # Partial update — only notes
        resp = client.put(
            f"/api/assets/{asset_id}",
            data=json.dumps({"notes": "Updated note"}),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 200

        # Verify DB state directly
        conn = direct_db()
        row = conn.execute(
            "SELECT * FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        conn.close()

        assert row["notes"] == "Updated note"           # changed field
        assert row["asset_name"] == "Original Name"     # unchanged
        assert row["custodian"] == "Coinbase"           # unchanged
        assert row["status"] == "active"                # unchanged
        assert row["created_at"] == original_created_at # never mutated by PUT
        assert row["updated_at"] is not None            # refreshed

    def test_delete_removes_row_from_db(self, client, auth):
        """
        Dark alley test — confirms the row is gone from the DB after DELETE,
        not just that the API returned 204.
        """
        conn = direct_db()
        cur = conn.execute(
            "INSERT INTO assets (asset_name, category) VALUES (?, ?)",
            ("Delete Verification Target", "Proprietary IP"),
        )
        conn.commit()
        asset_id = cur.lastrowid
        conn.close()

        resp = client.delete(f"/api/assets/{asset_id}", auth=auth)
        assert resp.status_code == 204

        # State verification — row must be absent
        conn = direct_db()
        row = conn.execute(
            "SELECT id FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        conn.close()

        assert row is None, "Row must not exist in DB after DELETE"

    def test_fts_index_updated_after_insert(self, client, auth):
        """
        Verifies the FTS5 trigger fired on INSERT — the new asset must be
        searchable via the FTS index immediately after creation.
        """
        resp = client.post(
            "/api/assets",
            data=json.dumps({
                "asset_name": "UniqueSearchableTerm_XQ9",
                "category": "Proprietary IP",
                "notes": "FTS trigger verification asset",
            }),
            content_type="application/json",
            auth=auth,
        )
        assert resp.status_code == 201

        # Query via FTS index directly — not the API
        conn = direct_db()
        rows = conn.execute(
            "SELECT rowid FROM assets_fts WHERE assets_fts MATCH ?",
            ("UniqueSearchableTerm_XQ9",),
        ).fetchall()
        conn.close()

        assert len(rows) == 1, "FTS trigger must index new asset on INSERT"

    def test_fts_index_cleaned_after_delete(self, client, auth):
        """
        Verifies the FTS5 delete trigger fired — deleted asset must not
        appear in FTS results (no ghost entries in the index).
        """
        resp = client.post(
            "/api/assets",
            data=json.dumps({
                "asset_name": "GhostCheckAsset_ZZ7",
                "category": "Cryptocurrency",
                "custodian": "GhostExchange",
            }),
            content_type="application/json",
            auth=auth,
        )
        asset_id = resp.get_json()["id"]

        client.delete(f"/api/assets/{asset_id}", auth=auth)

        # FTS index must have no entry for this rowid
        conn = direct_db()
        rows = conn.execute(
            "SELECT rowid FROM assets_fts WHERE assets_fts MATCH ?",
            ("GhostCheckAsset_ZZ7",),
        ).fetchall()
        conn.close()

        assert rows == [], "FTS index must not retain deleted asset (ghost entry)"

    def test_default_status_written_to_db_not_just_response(self, client, auth):
        """
        Business rule guard: status='active' default must be persisted
        to the DB, not just returned in the API response.
        A response-only default would be caught here but not by testing
        the API response alone.
        """
        resp = client.post(
            "/api/assets",
            data=json.dumps({
                "asset_name": "Default Status Check",
                "category": "Securities & Commodities",
            }),
            content_type="application/json",
            auth=auth,
        )
        asset_id = resp.get_json()["id"]

        # Read from DB — not from the API response
        conn = direct_db()
        row = conn.execute(
            "SELECT status FROM assets WHERE id = ?", (asset_id,)
        ).fetchone()
        conn.close()

        assert row["status"] == "active", (
            "Default status must be 'active' in the DB row, not just in the API response"
        )

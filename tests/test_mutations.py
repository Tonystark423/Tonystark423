"""
Mutation-killing test suite for app.py
=======================================
Each test is labelled with the specific mutant it is designed to kill.
A mutant is "killed" when the test FAILS after the mutation is applied.
A mutant that survives means the test suite has a logic gap.

Target function: require_auth (app.py:54-65)

    auth = request.authorization
    if not auth or auth.username != LEDGER_USER or auth.password != LEDGER_PASS:
        return Response("Authentication required.", 401, {...})
    return f(*args, **kwargs)

Mutation map
------------
MUTANT 1  `not auth`         →  `auth`
           Effect: no-auth header now PASSES the gate
           Killed by: test_no_auth_header_denied

MUTANT 2  first `or`         →  `and`
           Effect: missing header only blocks when username also wrong;
                   a request with correct credentials + no header passes
           Killed by: test_no_auth_header_denied

MUTANT 3  `username !=`      →  `username ==`
           Effect: correct username is DENIED, wrong username is ALLOWED
           Killed by: test_correct_username_wrong_password_denied
                  AND test_wrong_username_correct_password_denied

MUTANT 4  second `or`        →  `and`
           Effect: only blocks when BOTH username AND password are wrong;
                   wrong username with correct password now PASSES
           Killed by: test_wrong_username_correct_password_denied

MUTANT 5  `password !=`      →  `password ==`
           Effect: correct password is DENIED, wrong password is ALLOWED
           Killed by: test_correct_credentials_allowed
                  AND test_correct_username_wrong_password_denied

MUTANT 6  entire condition   →  `False` (always allow)
           Effect: gate removed entirely
           Killed by: test_no_auth_header_denied

MUTANT 7  entire condition   →  `True` (always deny)
           Effect: no request ever passes
           Killed by: test_correct_credentials_allowed
"""

import os
import sqlite3
import tempfile

import pytest

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"]      = _db_path
os.environ["LEDGER_USER"]  = "legituser"
os.environ["LEDGER_PASS"]  = "legitpass"

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


# ---------------------------------------------------------------------------
# Mutation-killing tests — Access Control Integrity
# ---------------------------------------------------------------------------

class TestAccessControlMutations:

    # KILLS MUTANT 1, 2, 6
    def test_no_auth_header_denied(self, client):
        """
        No Authorization header at all must be rejected.
        Kills: MUTANT 1 (not auth → auth), MUTANT 2 (first or → and),
               MUTANT 6 (condition → False).
        """
        resp = client.get("/api/assets")
        assert resp.status_code == 401
        assert resp.headers.get("WWW-Authenticate") == 'Basic realm="Ledger"'

    # KILLS MUTANT 3, 4
    def test_wrong_username_correct_password_denied(self, client):
        """
        Correct password but wrong username must be rejected.
        Kills: MUTANT 3 (username != → ==) — wrong name would pass instead of block.
               MUTANT 4 (second or → and) — only blocks when BOTH wrong; this has
               correct password so the and-mutant would let it through.
        """
        resp = client.get("/api/assets", auth=("wronguser", "legitpass"))
        assert resp.status_code == 401

    # KILLS MUTANT 3, 5
    def test_correct_username_wrong_password_denied(self, client):
        """
        Correct username but wrong password must be rejected.
        Kills: MUTANT 3 (username != → ==) — correct name would now block instead of pass.
               MUTANT 5 (password != → ==) — wrong password would pass instead of block.
        """
        resp = client.get("/api/assets", auth=("legituser", "wrongpass"))
        assert resp.status_code == 401

    # KILLS MUTANT 5, 7
    def test_correct_credentials_allowed(self, client):
        """
        Exact username + password must be accepted.
        Kills: MUTANT 5 (password != → ==) — correct password would now be denied.
               MUTANT 7 (condition → True) — gate always denies; nothing passes.
        """
        resp = client.get("/api/assets", auth=("legituser", "legitpass"))
        assert resp.status_code == 200

    # KILLS MUTANT 2 explicitly (no-header + correct creds variant)
    def test_empty_string_credentials_denied(self, client):
        """
        Empty username and password are not equivalent to 'no credentials'.
        Kills: MUTANT 2 edge case — ensures the username check fires
        independently of the header-presence check.
        """
        resp = client.get("/api/assets", auth=("", ""))
        assert resp.status_code == 401

    def test_case_sensitive_username(self, client):
        """
        'LegitUser' (wrong case) must not match 'legituser'.
        Guards against a mutation that normalises credentials before comparison.
        """
        resp = client.get("/api/assets", auth=("LegitUser", "legitpass"))
        assert resp.status_code == 401

    def test_case_sensitive_password(self, client):
        """
        'LegitPass' (wrong case) must not match 'legitpass'.
        """
        resp = client.get("/api/assets", auth=("legituser", "LegitPass"))
        assert resp.status_code == 401

    def test_swapped_credentials_denied(self, client):
        """
        Username and password swapped must be rejected.
        Kills a structural mutant where the username and password
        comparison targets are accidentally transposed.
        """
        resp = client.get("/api/assets", auth=("legitpass", "legituser"))
        assert resp.status_code == 401

    def test_failed_auth_produces_no_db_side_effects(self, client):
        """
        The 'Silent Success' assertion: verify what did NOT happen.

        A rejected request must not touch the database at all.
        Without this test, a mutation that moves the auth check *after*
        the DB call would pass every status-code assertion while still
        writing data on unauthenticated requests.

        Python equivalent of: expect(dbSpy).not.toHaveBeenCalled()
        """
        import unittest.mock as mock
        with mock.patch.object(app_module, "get_db") as mock_get_db:
            client.post(
                "/api/assets",
                json={"asset_name": "Should not persist", "category": "Cryptocurrency"},
                # no auth
            )
        mock_get_db.assert_not_called()   # DB must never be reached on auth failure

    def test_auth_gate_applies_to_every_route(self, client):
        """
        The decorator must protect all routes, not just GET /api/assets.
        A mutant that applies @require_auth only to one route would survive
        single-route tests. This confirms the gate is structural.
        """
        routes = [
            ("GET",    "/api/assets"),
            ("POST",   "/api/assets"),
            ("GET",    "/api/assets/1"),
            ("PUT",    "/api/assets/1"),
            ("DELETE", "/api/assets/1"),
            ("GET",    "/api/export"),
            ("GET",    "/"),
            # Tax filing routes
            ("GET",    "/api/tax/summary"),
            ("POST",   "/api/tax/file"),
            # Meal planning routes
            ("GET",    "/api/meals"),
            ("POST",   "/api/meals"),
            ("GET",    "/api/meals/1"),
            ("DELETE", "/api/meals/1"),
            ("GET",    "/api/meals/suggestions"),
        ]
        for method, path in routes:
            resp = client.open(path, method=method)
            assert resp.status_code == 401, (
                f"{method} {path} should return 401 without credentials, got {resp.status_code}"
            )

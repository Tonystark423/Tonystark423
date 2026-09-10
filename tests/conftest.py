"""
Shared pytest configuration and fixtures for the Stark Financial Holdings
asset ledger test suite.

This module is the single source of truth for test isolation. It sets the
environment variables BEFORE any test module imports ``app``, so
``app_module.DB_PATH`` / ``LEDGER_USER`` / ``LEDGER_PASS`` are fixed for the
whole session. Every test module then reuses these fixtures instead of
defining its own tempfile + env + schema setup, which previously froze the
app to whichever module was imported first and left later modules reading
a different database (the root cause of the order-dependent failures).

The application uses a single, process-wide SQLite database (``app_module.DB_PATH``).
Tests that need a clean slate (e.g. CSV import, mutation sweeps) operate on
an in-memory database instead; see ``make_db`` / ``memory_db``.
"""

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Environment must be set BEFORE the first import of `app`.
# pytest imports conftest.py before collecting any test module, so this runs
# first and freezes app_module.DB_PATH / LEDGER_USER / LEDGER_PASS once.
# ---------------------------------------------------------------------------
# Ensure the repository root (where app.py, tax_engine.py, ledger_processor.py
# and starkbank_sync.py live) is importable. pytest's rootdir auto-discovery
# does not always prepend it to sys.path (depends on invocation / config),
# so add it explicitly to keep `import app` robust in CI.
_REPO_ROOT = str(Path(__file__).resolve().parent.parent)
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DB_PATH"] = _db_path
os.environ["LEDGER_USER"] = "testuser"
os.environ["LEDGER_PASS"] = "testpass"
os.environ["FLASK_SECRET_KEY"] = "test-secret"

import app as app_module  # noqa: E402

# Credentials tests may flip these env vars; restore them per-test if needed.
LEDGER_USER = os.environ["LEDGER_USER"]
LEDGER_PASS = os.environ["LEDGER_PASS"]


# ---------------------------------------------------------------------------
# Session-scoped schema + cleanup
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session", autouse=True)
def _init_database():
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        schema = f.read()
    conn = sqlite3.connect(_db_path)
    conn.executescript(schema)
    conn.close()
    yield
    os.close(_db_fd)
    try:
        os.unlink(_db_path)
    except FileNotFoundError:
        pass


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def client():
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def auth():
    """Valid Basic Auth credentials as a (user, pass) tuple."""
    return (LEDGER_USER, LEDGER_PASS)


def direct_db():
    """Open a direct connection to the application's test DB for
    state-verification reads (Pattern 4). Always uses app_module.DB_PATH so
    it never reads a stale module-local tempfile."""
    conn = sqlite3.connect(app_module.DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture()
def db_conn():
    """A direct DB connection for state-verification reads, closed after the test."""
    conn = direct_db()
    yield conn
    conn.close()


@pytest.fixture()
def make_db():
    """Factory returning a fresh in-memory SQLite DB with the full schema applied.
    Use for component tests (ledger_processor, starkbank_sync) that want a clean
    database without touching the shared app DB."""
    schema_path = os.path.join(os.path.dirname(__file__), "..", "schema.sql")
    with open(schema_path) as f:
        schema = f.read()

    def _make():
        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row
        conn.executescript(schema)
        return conn

    return _make

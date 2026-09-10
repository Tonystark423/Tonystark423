"""
Tests for starkbank_sync.py — Stark Bank transaction → ledger upsert.

External boundary (starkbank SDK) is mocked; no network. Follows the
TESTING_STANDARDS.md playbook (Pattern 4 DB state verification, Pattern 1
value over existence, side-effect assertions via mock.assert_*).

NOTE — known bug surfaced by test_insert_rejected_by_category_check:
starkbank_sync._tx_to_fields() stamps category="Bank Transaction", but
schema.sql's assets table CHECK constraint only permits:
    Proprietary IP | Computer Resources | Money Market Funds |
    Securities & Commodities | Cryptocurrency | Real Estate
so every INSERT raises sqlite3.IntegrityError and sync_transactions does
not catch it, aborting the sync on the first transaction. This test
documents that current behavior; the fix is a schema/design decision
(add "Bank Transaction" to the CHECK, or remap to an allowed category).
"""

from contextlib import contextmanager
import sqlite3
from datetime import datetime
from types import SimpleNamespace
from unittest import mock

import pytest

import starkbank_sync as sync_mod


# ---------------------------------------------------------------------------
# Test doubles — fake Stark Bank Transaction objects
# ---------------------------------------------------------------------------

def _tx(tx_id="123", amount=5000, description="Wire transfer", tags=None,
        created=None):
    """Build a minimal object with the attributes _tx_to_fields reads."""
    return SimpleNamespace(
        id=tx_id,
        amount=amount,
        description=description,
        tags=tags,
        created=created or datetime(2024, 1, 15),
    )


# ---------------------------------------------------------------------------
# _tx_to_fields — pure field mapping (no DB, no network)
# ---------------------------------------------------------------------------

class TestTxToFields:
    def test_credit_amount_mapped_to_dollars(self):
        fields = sync_mod._tx_to_fields(_tx(amount=5000, description="Income"))
        assert fields["estimated_value"] == "50.0000"
        assert fields["subcategory"] == "credit"
        assert fields["quantity"] == "1.0000"
        assert fields["unit"] == "USD"

    def test_debit_amount_uses_absolute_value(self):
        fields = sync_mod._tx_to_fields(_tx(amount=-2500, description="Bill pay"))
        assert fields["estimated_value"] == "25.0000"
        assert fields["subcategory"] == "debit"

    def test_category_is_bank_transaction(self):
        fields = sync_mod._tx_to_fields(_tx())
        assert fields["category"] == "Bank Transaction"
        assert fields["subcategory"] == "credit"

    def test_description_falls_back_when_blank(self):
        tx = _tx(description="   ", tx_id="abc")
        fields = sync_mod._tx_to_fields(tx)
        assert fields["asset_name"] == "Stark Bank credit abc"
        assert fields["description"] == "Stark Bank credit abc"

    def test_notes_contains_starkbank_id_marker(self):
        fields = sync_mod._tx_to_fields(_tx(tx_id="TXN-99"))
        assert "starkbank_id=TXN-99" in fields["notes"]

    def test_notes_includes_tags(self):
        fields = sync_mod._tx_to_fields(_tx(tags=["invoice", "vendor"]))
        assert "tags: invoice, vendor" in fields["notes"]

    def test_acquisition_date_from_created(self):
        fields = sync_mod._tx_to_fields(_tx(created=datetime(2024, 3, 1)))
        assert fields["acquisition_date"] == "2024-03-01"

    def test_status_active_and_custodian_stark_bank(self):
        fields = sync_mod._tx_to_fields(_tx())
        assert fields["status"] == "active"
        assert fields["custodian"] == "Stark Bank"



# ---------------------------------------------------------------------------
# sync_transactions — mocked starkbank.transaction.query, real in-memory DB
# ---------------------------------------------------------------------------

@contextmanager
def _mocked_query(txs):
    """Patch _get_project + starkbank.transaction so query() yields `txs`."""
    with mock.patch.object(sync_mod, "_get_project", return_value=None), \
         mock.patch.object(sync_mod.starkbank, "transaction") as txn:
        txn.query.return_value = iter(txs)
        yield txn


class TestSyncTransactions:
    def test_dedup_skips_existing_starkbank_id(self, make_db):
        db = make_db()
        db.execute(
            "INSERT INTO assets (asset_name, category, notes) VALUES (?, ?, ?)",
            ("Existing", "Cryptocurrency", "starkbank_id=DUP-1"),
        )
        db.commit()
        with _mocked_query([_tx(tx_id="DUP-1"), _tx(tx_id="NEW-1")]) as txn:
            with pytest.raises(sqlite3.IntegrityError):
                sync_mod.sync_transactions(db, limit=10)
        # The duplicate was skipped BEFORE the failing insert, so only the seed row exists.
        rows = db.execute("SELECT notes FROM assets WHERE notes LIKE '%DUP-1%'").fetchall()
        assert len(rows) == 1
        assert rows[0]["notes"] == "starkbank_id=DUP-1"
        new_rows = db.execute("SELECT id FROM assets WHERE notes LIKE '%NEW-1%'").fetchall()
        assert new_rows == []
        assert txn.query.call_args.kwargs["limit"] == 10
        assert txn.query.call_count == 1

    def test_insert_rejected_by_category_check_documents_bug(self, make_db):
        """KNOWN BUG: category="Bank Transaction" is rejected by the assets
        CHECK constraint; sync_transactions does not catch the IntegrityError,
        so the first non-duplicate transaction aborts the whole sync."""
        db = make_db()
        with _mocked_query([_tx(tx_id="BUG-1", amount=1000)]) as txn:
            with pytest.raises(sqlite3.IntegrityError):
                sync_mod.sync_transactions(db, limit=10)
        rows = db.execute("SELECT id FROM assets WHERE notes LIKE '%BUG-1%'").fetchall()
        assert rows == []
        assert txn.query.call_count == 1
        assert db.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"] == 0

    def test_empty_transaction_list_returns_zeros(self, make_db):
        db = make_db()
        with _mocked_query([]) as txn:
            inserted, skipped = sync_mod.sync_transactions(db, limit=50)
        assert inserted == 0
        assert skipped == 0
        assert txn.query.call_args.kwargs["limit"] == 50
        count = db.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"]
        assert count == 0
        assert txn.query.call_count == 1

    def test_query_receives_limit_and_optional_bounds(self, make_db):
        db = make_db()
        with _mocked_query([]) as txn:
            sync_mod.sync_transactions(db, limit=25, after="2024-01-01", before="2024-12-31")
            kwargs = txn.query.call_args.kwargs
        assert kwargs["limit"] == 25
        assert kwargs["after"] == "2024-01-01"
        assert kwargs["before"] == "2024-12-31"
        assert txn.query.call_count == 1
        assert "after" in kwargs and "before" in kwargs

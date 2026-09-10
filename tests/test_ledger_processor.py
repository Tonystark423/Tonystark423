"""
Tests for ledger_processor.py — the CSV ledger ingestion module.

Mirrors the alias-mapping, Decimal-coercion, upsert, and budget logic in
ledger_processor.py. Follows the TESTING_STANDARDS.md playbook:

  - Pattern 1 (Value over Existence): assert business rules, not just "ran".
  - Pattern 3 (Decision Matrix): every category/status mapping branch covered.
  - Pattern 4 (State Verification): read the in-memory DB after upsert.
  - Pattern 5 (Parametrize): boundary sweeps for Decimal coercion.

Component tier: these tests exercise ledger_processor against a fresh
in-memory SQLite DB (make_db fixture), independent of the shared app DB.
"""

import io

import pandas as pd
import pytest

import ledger_processor as lp


# ---------------------------------------------------------------------------
# _normalise_col — column name normalisation
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("raw,expected", [
    ("Asset Name", "asset_name"),
    ("Asset-Name", "asset_name"),
    ("  AssetName ", "assetname"),
    ("MARKET_VALUE", "market_value"),
    ("asset_class", "asset_class"),
])
def test_normalise_col(raw, expected):
    assert lp._normalise_col(raw) == expected


# ---------------------------------------------------------------------------
# _to_decimal_str — Decimal precision gate (Pattern 5 boundary sweep)
# ---------------------------------------------------------------------------

class TestToDecimalStr:
    def test_positive_value_quantized_to_4dp(self):
        assert lp._to_decimal_str(0.29) == "0.2900"

    def test_float_drift_prevented(self):
        # 0.29 stored as float drifts to 0.289999...; Decimal(str()) is exact.
        result = lp._to_decimal_str(0.29)
        assert result == "0.2900"
        assert "2899" not in result

    def test_large_value_kept(self):
        assert lp._to_decimal_str(1_000_000.5) == "1000000.5000"

    @pytest.mark.parametrize("invalid", [None, float("nan"), 0, -1, -0.01, "abc"])
    def test_invalid_or_nonpositive_returns_none(self, invalid):
        assert lp._to_decimal_str(invalid) is None


# ---------------------------------------------------------------------------
# _map_category — decision matrix across all branches (Pattern 3)
# ---------------------------------------------------------------------------

class TestMapCategory:
    @pytest.mark.parametrize("raw,expected", [
        ("Proprietary IP", "Proprietary IP"),
        ("Computer Resources", "Computer Resources"),
        ("Money Market Funds", "Money Market Funds"),
        ("Securities & Commodities", "Securities & Commodities"),
        ("Cryptocurrency", "Cryptocurrency"),
        ("Real Estate", "Real Estate"),
    ])
    def test_exact_match_passes(self, raw, expected):
        assert lp._map_category(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("cryptocurrency", "Cryptocurrency"),
        ("PROPRIETARY IP", "Proprietary IP"),
        ("real estate", "Real Estate"),
    ])
    def test_case_insensitive_match(self, raw, expected):
        assert lp._map_category(raw) == expected

    @pytest.mark.parametrize("raw,expected", [
        ("GPU cluster", "Computer Resources"),
        ("new patent application", "Proprietary IP"),
        ("SPAXX fidelity fund", "Money Market Funds"),
        ("bitcoin BTC holding", "Cryptocurrency"),
    ])
    def test_substring_heuristics(self, raw, expected):
        assert lp._map_category(raw) == expected

    @pytest.mark.parametrize("raw", ["", None, "nan", "none"])
    def test_empty_falls_back_to_securities(self, raw):
        assert lp._map_category(raw) == "Securities & Commodities"

    def test_unrecognised_falls_back_to_securities(self):
        # Avoid substring keywords (e.g. 'coin' in 'exotic' hits Cryptocurrency).
        assert lp._map_category("zzz unmatchable") == "Securities & Commodities"


# ---------------------------------------------------------------------------
# _map_status — status normalisation branches
# ---------------------------------------------------------------------------

class TestMapStatus:
    @pytest.mark.parametrize("raw,expected", [
        ("active", "active"), ("sold", "sold"), ("pending", "pending"),
        ("SOLD", "sold"), ("closed", "sold"), ("exit position", "sold"),
        ("pending settlement", "pending"), ("waiting", "pending"),
    ])
    def test_known_and_keyword_statuses(self, raw, expected):
        assert lp._map_status(raw) == expected

    @pytest.mark.parametrize("raw", ["", None, "nan", "none", "garbage"])
    def test_empty_or_unknown_defaults_active(self, raw):
        assert lp._map_status(raw) == "active"


# ---------------------------------------------------------------------------
# process_csv — end-to-end upsert against an in-memory DB (Pattern 4)
# ---------------------------------------------------------------------------

def _csv(text: str) -> io.StringIO:
    return io.StringIO(text)


class TestProcessCsv:
    def test_inserts_valid_rows_to_db(self, make_db):
        csv_text = (
            "asset_name,category,estimated_value,custodian\n"
            "NVDA,Securities & Commodities,50000,Fidelity\n"
            "BTC,Cryptocurrency,1000,Coinbase\n"
        )
        db = make_db()
        result = lp.process_csv(_csv(csv_text), db)
        assert result["inserted"] == 2
        assert result["skipped"] == 0
        assert result["processed"] == 2
        assert result["errors"] == []
        rows = db.execute(
            "SELECT asset_name, category, estimated_value, custodian "
            "FROM assets ORDER BY asset_name"
        ).fetchall()
        assert [r["asset_name"] for r in rows] == ["BTC", "NVDA"]
        assert rows[0]["category"] == "Cryptocurrency"
        assert rows[0]["estimated_value"] == "1000.0000"
        assert rows[0]["custodian"] == "Coinbase"
        assert rows[1]["custodian"] == "Fidelity"
        assert rows[1]["estimated_value"] == "50000.0000"

    def test_alias_columns_mapped_to_ledger_fields(self, make_db):
        csv_text = "name,asset_class,amount,broker\nAAPL,Stocks,250,Schwab\n"
        db = make_db()
        result = lp.process_csv(_csv(csv_text), db)
        assert result["inserted"] == 1
        assert result["errors"] == []
        row = db.execute(
            "SELECT asset_name, category, estimated_value, custodian, subcategory "
            "FROM assets"
        ).fetchone()
        assert row["asset_name"] == "AAPL"
        assert row["category"] == "Securities & Commodities"  # "Stocks" heuristics fallback
        assert row["estimated_value"] == "250.0000"
        assert row["custodian"] == "Schwab"
        assert row["subcategory"] == "Credit/Income"  # derived from positive amount

    def test_currency_cleaned_dollar_commas(self, make_db):
        csv_text = "asset_name,category,value\nNVDA,Securities & Commodities,\"$50,000.00\"\n"
        db = make_db()
        result = lp.process_csv(_csv(csv_text), db)
        assert result["inserted"] == 1
        assert result["errors"] == []
        row = db.execute("SELECT asset_name, estimated_value FROM assets").fetchone()
        assert row["estimated_value"] == "50000.0000"
        assert row["asset_name"] == "NVDA"

    def test_decimal_coercion_no_float_drift(self, make_db):
        csv_text = "asset_name,category,estimated_value\nDrift,Securities & Commodities,0.29\n"
        db = make_db()
        result = lp.process_csv(_csv(csv_text), db)
        assert result["inserted"] == 1
        row = db.execute("SELECT estimated_value FROM assets").fetchone()
        assert row["estimated_value"] == "0.2900"

    def test_duplicate_rows_skipped_not_inserted(self, make_db):
        row_text = "asset_name,category,estimated_value\nNVDA,Securities & Commodities,50000\n"
        db = make_db()
        first = lp.process_csv(_csv(row_text), db)
        result = lp.process_csv(_csv(row_text), db)
        assert first["inserted"] == 1
        assert result["inserted"] == 0
        assert result["skipped"] == 1
        assert result["errors"] == []
        count = db.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"]
        assert count == 1

    def test_empty_csv_returns_error(self, make_db):
        db = make_db()
        result = lp.process_csv(_csv("asset_name,category\n"), db)
        assert result["inserted"] == 0
        assert result["processed"] == 0
        assert len(result["errors"]) == 1
        assert "empty" in result["errors"][0].lower()

    def test_missing_asset_name_column_returns_error(self, make_db):
        csv_text = "category,estimated_value\nCryptocurrency,100\n"
        db = make_db()
        result = lp.process_csv(_csv(csv_text), db)
        assert result["inserted"] == 0
        assert len(result["errors"]) == 1
        assert "asset_name" in result["errors"][0]

    def test_nonexistent_file_path_returns_error(self, make_db):
        db = make_db()
        result = lp.process_csv("/no/such/file_xyz.csv", db)
        assert result["inserted"] == 0
        assert len(result["errors"]) == 1
        assert "not found" in result["errors"][0].lower()

    def test_blank_asset_name_rows_dropped(self, make_db):
        csv_text = "asset_name,category\n  ,Cryptocurrency\nRealAsset,Cryptocurrency\n"
        db = make_db()
        result = lp.process_csv(_csv(csv_text), db)
        assert result["inserted"] == 1
        assert result["errors"] == []
        count = db.execute("SELECT COUNT(*) AS n FROM assets").fetchone()["n"]
        assert count == 1
        name = db.execute("SELECT asset_name FROM assets").fetchone()["asset_name"]
        assert name == "RealAsset"

    def test_default_owner_and_custodian_stamped(self, make_db):
        csv_text = "asset_name,category\nBTC,Cryptocurrency\n"
        db = make_db()
        result = lp.process_csv(_csv(csv_text), db,
                       default_beneficial_owner="Stark Holdings",
                       default_custodian="Stark Bank")
        assert result["inserted"] == 1
        row = db.execute(
            "SELECT asset_name, custodian, beneficial_owner FROM assets"
        ).fetchone()
        assert row["asset_name"] == "BTC"
        assert row["custodian"] == "Stark Bank"
        assert row["beneficial_owner"] == "Stark Holdings"


# ---------------------------------------------------------------------------
# categorize_transaction — keyword categorisation
# ---------------------------------------------------------------------------

class TestCategorizeTransaction:
    @pytest.mark.parametrize("desc,expected", [
        ("Monthly payroll", "Payroll"),
        ("Office rent Q1", "Facilities"),
        ("AWS cloud invoice", "Technology"),
        ("Interest payment", "Revenue"),
        ("IRS tax deposit", "Tax"),
        ("Legal counsel fees", "Legal & Compliance"),
        ("Flight to NYC", "Travel"),
    ])
    def test_keyword_matches(self, desc, expected):
        assert lp.categorize_transaction(desc) == expected

    def test_no_match_defaults_general_operations(self):
        assert lp.categorize_transaction("random vendor purchase") == "General Operations"


# ---------------------------------------------------------------------------
# check_budgets — budget status logic
# ---------------------------------------------------------------------------

class TestCheckBudgets:
    def _df(self, rows):
        return pd.DataFrame(rows, columns=["Type", "Category", "Amount"])

    def test_over_budget_status(self):
        df = self._df([("Expense", "Technology", 6000)])
        results = lp.check_budgets(df)
        tech = next(r for r in results if r["category"] == "Technology")
        assert tech["status"] == "over"
        assert tech["actual"] == 6000.0
        assert tech["variance"] == round(5000.0 - 6000.0, 2)

    def test_warning_status_above_80pct(self):
        df = self._df([("Expense", "Technology", 4500)])  # 90% of 5000
        results = lp.check_budgets(df)
        tech = next(r for r in results if r["category"] == "Technology")
        assert tech["status"] == "warning"
        assert tech["limit"] == 5000.0
        assert tech["actual"] == 4500.0
        assert tech["variance"] == 500.0

    def test_ok_status_below_threshold(self):
        df = self._df([("Expense", "Technology", 1000)])
        results = lp.check_budgets(df)
        tech = next(r for r in results if r["category"] == "Technology")
        assert tech["status"] == "ok"
        assert tech["actual"] == 1000.0
        assert tech["variance"] == 4000.0

    def test_custom_limits_override_defaults(self):
        df = self._df([("Expense", "Technology", 6000)])
        results = lp.check_budgets(df, custom_limits={"Technology": 10000})
        tech = next(r for r in results if r["category"] == "Technology")
        assert tech["status"] == "ok"
        assert tech["limit"] == 10000.0
        assert tech["actual"] == 6000.0
        assert tech["variance"] == 4000.0

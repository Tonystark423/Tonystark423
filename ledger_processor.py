"""Stark Financial Holdings — CSV Ledger Processor.

Reads a CSV export (brokerage, bank, or manual), cleans it, maps columns
to the assets schema, applies Decimal precision, and upserts into SQLite.

Supported column aliases (case-insensitive, whitespace-stripped):
  asset_name       : asset_name, name, description, asset, symbol, ticker
  category         : category, asset_class, type, asset_type
  subcategory      : subcategory, sub_category, subtype
  estimated_value  : estimated_value, amount, balance, credit, value,
                     market_value, current_value, price
  quantity         : quantity, shares, units, qty
  unit             : unit, currency, denomination
  acquisition_date : acquisition_date, date, trade_date, purchase_date
  custodian        : custodian, broker, institution, account
  beneficial_owner : beneficial_owner, owner, holder
  status           : status, state
  notes            : notes, memo, remarks, comment

Usage:
  from ledger_processor import process_csv
  result = process_csv("stark_holdings_ledger.csv", db_conn)
  print(result)   # {"processed": 42, "inserted": 38, "skipped": 4, "errors": [...]}
"""

from __future__ import annotations

import io
import os
import sqlite3
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Union

import pandas as pd

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

VALID_CATEGORIES = {
    "Proprietary IP",
    "Computer Resources",
    "Money Market Funds",
    "Securities & Commodities",
    "Cryptocurrency",
}

VALID_STATUSES = {"active", "sold", "pending"}

ASSET_NAME_MAX = 100

# ---------------------------------------------------------------------------
# Budget limits (USD, per spend category)
# Override at runtime by mutating this dict or passing custom_limits to
# check_budgets(). Stored here so the API endpoint and CLI share one source.
# ---------------------------------------------------------------------------

BUDGET_LIMITS: dict[str, float] = {
    "Payroll":            50_000.00,
    "Facilities":         10_000.00,
    "Technology":          5_000.00,
    "Tax":                 8_000.00,
    "Legal & Compliance":  3_000.00,
    "Travel":              2_500.00,
    "General Operations":  2_000.00,
    # Revenue is income — no spending cap
}

# Maps normalised CSV column names → ledger field names
_ALIASES: dict[str, str] = {
    "asset_name":       "asset_name",
    "name":             "asset_name",
    "description":      "asset_name",
    "asset":            "asset_name",
    "symbol":           "asset_name",
    "ticker":           "asset_name",

    "category":         "category",
    "asset_class":      "category",
    "type":             "category",
    "asset_type":       "category",

    "subcategory":      "subcategory",
    "sub_category":     "subcategory",
    "subtype":          "subcategory",

    "estimated_value":  "estimated_value",
    "amount":           "estimated_value",
    "balance":          "estimated_value",
    "credit":           "estimated_value",
    "value":            "estimated_value",
    "market_value":     "estimated_value",
    "current_value":    "estimated_value",
    "price":            "estimated_value",

    "quantity":         "quantity",
    "shares":           "quantity",
    "units":            "quantity",
    "qty":              "quantity",

    "unit":             "unit",
    "currency":         "unit",
    "denomination":     "unit",

    "acquisition_date": "acquisition_date",
    "date":             "acquisition_date",
    "trade_date":       "acquisition_date",
    "purchase_date":    "acquisition_date",

    "custodian":        "custodian",
    "broker":           "custodian",
    "institution":      "custodian",
    "account":          "custodian",

    "beneficial_owner": "beneficial_owner",
    "owner":            "beneficial_owner",
    "holder":           "beneficial_owner",

    "status":           "status",
    "state":            "status",

    "notes":            "notes",
    "memo":             "notes",
    "remarks":          "notes",
    "comment":          "notes",
}

_CURRENCY_COLS = {"estimated_value", "amount", "balance", "credit", "value",
                  "market_value", "current_value", "price"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _normalise_col(col: str) -> str:
    return col.strip().lower().replace(" ", "_").replace("-", "_")


def _clean_currency(series: pd.Series) -> pd.Series:
    """Strip $, commas, parentheses; convert to numeric."""
    return pd.to_numeric(
        series.astype(str).str.replace(r"[\$,\(\)\s]", "", regex=True),
        errors="coerce",
    )


def _to_decimal_str(raw) -> str | None:
    """Convert a raw value to 4dp Decimal string, or None if invalid/zero."""
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return None
    try:
        d = Decimal(str(raw))
    except InvalidOperation:
        return None
    if d <= 0:
        return None
    return str(d.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))


def _map_category(raw: str) -> str:
    """Best-effort match to allowed category values; falls back to 'Securities & Commodities'."""
    if not raw or str(raw).strip().lower() in ("nan", "none", ""):
        return "Securities & Commodities"
    cleaned = str(raw).strip()
    # Exact match first
    if cleaned in VALID_CATEGORIES:
        return cleaned
    # Case-insensitive
    lower = cleaned.lower()
    for v in VALID_CATEGORIES:
        if v.lower() == lower:
            return v
    # Substring heuristics
    if any(k in lower for k in ("ip", "patent", "algorithm", "software", "license")):
        return "Proprietary IP"
    if any(k in lower for k in ("gpu", "cpu", "server", "compute", "memory", "hbm")):
        return "Computer Resources"
    if any(k in lower for k in ("money market", "mmf", "spaxx", "fidelity", "fund")):
        return "Money Market Funds"
    if any(k in lower for k in ("crypto", "bitcoin", "btc", "eth", "coin", "token")):
        return "Cryptocurrency"
    return "Securities & Commodities"


def _map_status(raw: str) -> str:
    if not raw or str(raw).strip().lower() in ("nan", "none", ""):
        return "active"
    cleaned = str(raw).strip().lower()
    if cleaned in VALID_STATUSES:
        return cleaned
    if any(k in cleaned for k in ("sell", "sold", "closed", "exit")):
        return "sold"
    if any(k in cleaned for k in ("pend", "wait", "settl")):
        return "pending"
    return "active"


# ---------------------------------------------------------------------------
# Core processor
# ---------------------------------------------------------------------------

def process_csv(
    source: Union[str, io.IOBase],
    db: sqlite3.Connection,
    default_beneficial_owner: str = "",
    default_custodian: str = "",
) -> dict:
    """Load, clean, and upsert a CSV into the assets table.

    Args:
        source: file path string or file-like object.
        db: open sqlite3.Connection (caller manages lifecycle).
        default_beneficial_owner: stamped on rows that have no owner column.
        default_custodian: stamped on rows that have no custodian column.

    Returns:
        {"processed": N, "inserted": N, "skipped": N, "errors": [...]}
    """
    # 1. Load
    if isinstance(source, str):
        if not os.path.exists(source):
            return {"processed": 0, "inserted": 0, "skipped": 0,
                    "errors": [f"File not found: {source}"]}
        df = pd.read_csv(source, encoding="utf-8")
    else:
        df = pd.read_csv(source, encoding="utf-8")

    if df.empty:
        return {"processed": 0, "inserted": 0, "skipped": 0, "errors": ["CSV is empty"]}

    # 2. Normalise column names
    df.columns = [_normalise_col(c) for c in df.columns]

    # 3. Clean currency columns before alias mapping
    for col in df.columns:
        if col in _CURRENCY_COLS:
            df[col] = _clean_currency(df[col])

    # 4. Clean date columns
    for col in df.columns:
        if "date" in col:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # 5. Rename to ledger field names (first alias wins per target)
    rename_map: dict[str, str] = {}
    seen_targets: set[str] = set()
    for raw_col in df.columns:
        target = _ALIASES.get(raw_col)
        if target and target not in seen_targets:
            rename_map[raw_col] = target
            seen_targets.add(target)
    df = df.rename(columns=rename_map)

    # 6. Drop rows with no usable asset_name
    if "asset_name" not in df.columns:
        return {"processed": 0, "inserted": 0, "skipped": 0,
                "errors": ["No column maps to asset_name. Provide 'name', 'symbol', or 'asset_name'."]}

    df = df.dropna(subset=["asset_name"])
    df = df[df["asset_name"].astype(str).str.strip() != ""]

    # 7. Derive Transaction Type for rows with Amount (mirrors user's original logic)
    if "estimated_value" in df.columns and "subcategory" not in df.columns:
        df["subcategory"] = df["estimated_value"].apply(
            lambda x: "Credit/Income" if (not pd.isna(x) and x > 0) else "Debit/Expense"
        )

    # 8. Upsert loop
    inserted = 0
    skipped  = 0
    errors: list[str] = []

    for idx, row in df.iterrows():
        try:
            fields = _build_fields(row, default_beneficial_owner, default_custodian)
        except Exception as exc:
            errors.append(f"Row {idx}: build error — {exc}")
            skipped += 1
            continue

        # Dedup: asset_name + acquisition_date + estimated_value
        existing = db.execute(
            """SELECT id FROM assets
               WHERE asset_name = ?
                 AND COALESCE(acquisition_date,'') = COALESCE(?,'')
                 AND COALESCE(estimated_value,'') = COALESCE(?,'')""",
            (fields["asset_name"], fields.get("acquisition_date"), fields.get("estimated_value")),
        ).fetchone()

        if existing:
            skipped += 1
            continue

        cols         = ", ".join(fields.keys())
        placeholders = ", ".join("?" for _ in fields)
        try:
            db.execute(
                f"INSERT INTO assets ({cols}) VALUES ({placeholders})",
                list(fields.values()),
            )
            inserted += 1
        except sqlite3.IntegrityError as exc:
            errors.append(f"Row {idx}: integrity error — {exc}")
            skipped += 1

    db.commit()

    processed = inserted + skipped
    return {"processed": processed, "inserted": inserted, "skipped": skipped, "errors": errors}


def _build_fields(row: pd.Series, default_owner: str, default_custodian: str) -> dict:
    fields: dict = {}

    # asset_name — required, max 100 chars
    fields["asset_name"] = str(row["asset_name"]).strip()[:ASSET_NAME_MAX]

    # category — validate/map
    raw_cat = row.get("category", "")
    fields["category"] = _map_category(raw_cat)

    # subcategory
    raw_sub = row.get("subcategory", "")
    if raw_sub and str(raw_sub).strip().lower() not in ("nan", "none", ""):
        fields["subcategory"] = str(raw_sub).strip()

    # description
    raw_desc = row.get("description", "")
    if raw_desc and str(raw_desc).strip().lower() not in ("nan", "none", ""):
        fields["description"] = str(raw_desc).strip()

    # estimated_value — Decimal precision
    raw_val = row.get("estimated_value")
    decimal_val = _to_decimal_str(raw_val)
    if decimal_val is not None:
        fields["estimated_value"] = decimal_val

    # quantity
    raw_qty = row.get("quantity")
    decimal_qty = _to_decimal_str(raw_qty)
    if decimal_qty is not None:
        fields["quantity"] = decimal_qty

    # unit
    raw_unit = row.get("unit", "")
    if raw_unit and str(raw_unit).strip().lower() not in ("nan", "none", ""):
        fields["unit"] = str(raw_unit).strip()

    # acquisition_date
    raw_date = row.get("acquisition_date")
    if raw_date is not None and not (isinstance(raw_date, float) and pd.isna(raw_date)):
        try:
            fields["acquisition_date"] = pd.Timestamp(raw_date).strftime("%Y-%m-%d")
        except Exception:
            pass

    # custodian
    raw_cust = row.get("custodian", "") or default_custodian
    if raw_cust and str(raw_cust).strip().lower() not in ("nan", "none", ""):
        fields["custodian"] = str(raw_cust).strip()

    # beneficial_owner
    raw_owner = row.get("beneficial_owner", "") or default_owner
    if raw_owner and str(raw_owner).strip().lower() not in ("nan", "none", ""):
        fields["beneficial_owner"] = str(raw_owner).strip()

    # status
    raw_status = row.get("status", "")
    fields["status"] = _map_status(raw_status)

    # notes
    raw_notes = row.get("notes", "")
    if raw_notes and str(raw_notes).strip().lower() not in ("nan", "none", ""):
        fields["notes"] = str(raw_notes).strip()

    return fields


# ---------------------------------------------------------------------------
# Categorization
# ---------------------------------------------------------------------------

#: Keyword → spend category map (evaluated in order; first match wins)
_CATEGORY_RULES: list[tuple[list[str], str]] = [
    (["salary", "payroll", "wage"],                          "Payroll"),
    (["rent", "lease", "office"],                            "Facilities"),
    (["cloud", "aws", "azure", "gcp", "software", "saas",
      "license", "subscription"],                            "Technology"),
    (["interest", "dividend", "sale", "payment from",
      "proceeds", "distribution"],                           "Revenue"),
    (["tax", "irs", "nj division"],                          "Tax"),
    (["legal", "counsel", "attorney", "compliance"],         "Legal & Compliance"),
    (["travel", "flight", "hotel", "lodging"],               "Travel"),
]
_CATEGORY_DEFAULT = "General Operations"


def categorize_transaction(description: str) -> str:
    """Keyword-based categorization of a transaction description.

    Evaluated in _CATEGORY_RULES order; first keyword match wins.
    Returns _CATEGORY_DEFAULT when no rule matches.
    """
    desc = str(description).lower()
    for keywords, label in _CATEGORY_RULES:
        if any(kw in desc for kw in keywords):
            return label
    return _CATEGORY_DEFAULT


# ---------------------------------------------------------------------------
# Budget checking
# ---------------------------------------------------------------------------

def check_budgets(
    df: pd.DataFrame,
    custom_limits: dict[str, float] | None = None,
    type_col: str = "Type",
    category_col: str = "Category",
    amount_col: str = "Amount",
) -> list[dict]:
    """Compare actual spend vs. budget limits per category.

    Args:
        df: DataFrame with Type, Category, Amount columns.
        custom_limits: override BUDGET_LIMITS for this call only.
        type_col / category_col / amount_col: column name overrides.

    Returns:
        List of dicts, one per budgeted category, e.g.:
        [
          {"category": "Technology", "limit": 5000.0, "actual": 6200.0,
           "variance": -1200.0, "status": "over"},
          {"category": "Payroll",    "limit": 50000.0, "actual": 32000.0,
           "variance": 18000.0, "status": "ok"},
          ...
        ]
        Status values: "over" | "warning" (>80% of limit) | "ok"
    """
    limits = custom_limits if custom_limits is not None else BUDGET_LIMITS

    expenses = df[
        df[type_col].str.lower().str.contains("expense|debit", na=False)
    ].groupby(category_col)[amount_col].sum().abs()

    results: list[dict] = []
    for category, limit in sorted(limits.items()):
        actual   = float(expenses.get(category, 0.0))
        variance = round(limit - actual, 2)
        if actual > limit:
            status = "over"
        elif actual > limit * 0.80:
            status = "warning"
        else:
            status = "ok"
        results.append({
            "category": category,
            "limit":    round(limit, 2),
            "actual":   round(actual, 2),
            "variance": variance,
            "status":   status,
        })

    return results


# ---------------------------------------------------------------------------
# Visualization
# ---------------------------------------------------------------------------

def create_visuals(
    df: pd.DataFrame,
    output_path: str = "stark_expense_chart.png",
    type_col: str = "Type",
    category_col: str = "Category",
    amount_col: str = "Amount",
    budget_limits: dict[str, float] | None = None,
) -> str:
    """Generate a bar chart of expenses by category and save as PNG.

    Bars are coloured by budget status:
      steelblue  — within budget
      orange     — within budget but >80% consumed (warning)
      crimson    — over budget

    When budget_limits is provided (defaults to BUDGET_LIMITS), a dashed
    horizontal marker is drawn at the limit value for each bar.

    Args:
        df: DataFrame with at minimum Type, Category, and Amount columns.
        output_path: where to write the PNG file.
        type_col / category_col / amount_col: column name overrides.
        budget_limits: per-category USD caps; None uses BUDGET_LIMITS.

    Returns:
        Absolute path of the saved chart file.
    """
    import matplotlib
    matplotlib.use("Agg")  # non-interactive backend — safe for servers
    import matplotlib.pyplot as plt

    limits = budget_limits if budget_limits is not None else BUDGET_LIMITS

    expenses = df[df[type_col].str.lower().str.contains("expense|debit", na=False)]
    if expenses.empty:
        raise ValueError("No expense rows found — check the Type column values.")

    category_totals = (
        expenses.groupby(category_col)[amount_col]
        .sum()
        .abs()
        .sort_values(ascending=False)
    )

    # Colour each bar by status
    def _bar_colour(cat: str, actual: float) -> str:
        limit = limits.get(cat)
        if limit is None:
            return "steelblue"
        if actual > limit:
            return "crimson"
        if actual > limit * 0.80:
            return "darkorange"
        return "steelblue"

    colours = [_bar_colour(cat, val) for cat, val in category_totals.items()]

    fig, ax = plt.subplots(figsize=(11, 6))
    bars = ax.bar(range(len(category_totals)), category_totals.values, color=colours)
    ax.set_xticks(range(len(category_totals)))
    ax.set_xticklabels(category_totals.index, rotation=40, ha="right")

    # Budget threshold markers
    for i, (cat, actual) in enumerate(category_totals.items()):
        limit = limits.get(cat)
        if limit is not None:
            ax.plot([i - 0.4, i + 0.4], [limit, limit],
                    color="black", linewidth=1.5, linestyle="--", zorder=5)

    ax.set_title("Stark Financial Holdings: Expenses by Category",
                 fontsize=14, fontweight="bold")
    ax.set_ylabel("Total Amount (USD)")
    ax.set_xlabel("Category")
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda x, _: f"${x:,.2f}"))

    # Legend
    from matplotlib.patches import Patch
    from matplotlib.lines import Line2D
    legend_elements = [
        Patch(facecolor="steelblue",  label="Within budget"),
        Patch(facecolor="darkorange", label="Warning (>80%)"),
        Patch(facecolor="crimson",    label="Over budget"),
        Line2D([0], [0], color="black", linewidth=1.5,
               linestyle="--", label="Budget limit"),
    ]
    ax.legend(handles=legend_elements, loc="upper right", fontsize=9)

    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return os.path.abspath(output_path)


# ---------------------------------------------------------------------------
# CLI convenience
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import json
    from dotenv import load_dotenv

    load_dotenv()

    if len(sys.argv) < 2:
        print("Usage: python ledger_processor.py <path/to/file.csv>")
        sys.exit(1)

    csv_path = sys.argv[1]
    db_path  = os.getenv("DB_PATH", "ledger.db")
    owner    = os.getenv("LEDGER_BENEFICIAL_OWNER", "")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    result = process_csv(csv_path, conn, default_beneficial_owner=owner)
    conn.close()

    print(json.dumps(result, indent=2))

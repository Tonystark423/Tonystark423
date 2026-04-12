"""Stark Financial Holdings LLC — Asset Ledger."""

import csv
import io
import os
import sqlite3
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from functools import wraps

from dotenv import load_dotenv
from flask import Flask, Response, g, jsonify, render_template, request

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "changeme")

DB_PATH = os.getenv("DB_PATH", "ledger.db")
LEDGER_USER = os.getenv("LEDGER_USER", "admin")
LEDGER_PASS = os.getenv("LEDGER_PASS", "changeme")

COLUMNS = [
    "id", "asset_name", "category", "subcategory", "description",
    "quantity", "unit", "estimated_value", "acquisition_date",
    "custodian", "beneficial_owner", "status", "notes",
    "created_at", "updated_at",
]

WRITABLE_COLUMNS = [c for c in COLUMNS if c not in ("id", "created_at", "updated_at")]

ASSET_NAME_MAX_LENGTH = 100


def validate_fields(fields: dict) -> tuple[dict, str | None]:
    """
    Validate and sanitize writable asset fields.
    Returns (sanitized_fields, error_message_or_None).

    Rules:
      1. Precision gate: estimated_value must be > 0 when provided
      2. Quantity integrity: quantity must be > 0 when provided
      3. Name sanitization: strip whitespace, cap at ASSET_NAME_MAX_LENGTH
    """
    if "estimated_value" in fields and fields["estimated_value"] is not None:
        try:
            # Use Decimal(str(...)) not Decimal(float) — Decimal(0.29) inherits
            # the float representation error; Decimal("0.29") is exact.
            val = Decimal(str(fields["estimated_value"]))
        except InvalidOperation:
            return fields, "estimated_value must be a number"
        if val <= 0:
            return fields, "estimated_value must be greater than zero"
        # Quantize to 4 decimal places before storing — prevents drift at
        # the boundary. Store as str so SQLite TEXT affinity preserves exact
        # representation; the JSON response converts back via float().
        fields["estimated_value"] = str(val.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    if "quantity" in fields and fields["quantity"] is not None:
        try:
            qty = Decimal(str(fields["quantity"]))
        except InvalidOperation:
            return fields, "quantity must be a number"
        if qty <= 0:
            return fields, "quantity must be greater than zero"
        fields["quantity"] = str(qty.quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))

    if "asset_name" in fields and fields["asset_name"] is not None:
        fields["asset_name"] = str(fields["asset_name"]).strip()[:ASSET_NAME_MAX_LENGTH]
        if not fields["asset_name"]:
            return fields, "asset_name cannot be blank"

    return fields, None


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def require_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or auth.username != LEDGER_USER or auth.password != LEDGER_PASS:
            return Response(
                "Authentication required.",
                401,
                {"WWW-Authenticate": 'Basic realm="Ledger"'},
            )
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
@require_auth
def index():
    return render_template("index.html")


@app.route("/api/assets", methods=["GET"])
@require_auth
def list_assets():
    db = get_db()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    limit = min(int(request.args.get("limit", 200)), 1000)
    offset = int(request.args.get("offset", 0))

    params = []

    if q:
        sql = """
            SELECT a.*
            FROM assets a
            JOIN assets_fts f ON a.id = f.rowid
            WHERE assets_fts MATCH ?
        """
        params.append(q + "*")
        if category:
            sql += " AND a.category = ?"
            params.append(category)
        if status:
            sql += " AND a.status = ?"
            params.append(status)
        sql += " ORDER BY rank LIMIT ? OFFSET ?"
    else:
        sql = "SELECT * FROM assets WHERE 1=1"
        if category:
            sql += " AND category = ?"
            params.append(category)
        if status:
            sql += " AND status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT ? OFFSET ?"

    params += [limit, offset]
    rows = db.execute(sql, params).fetchall()
    return jsonify([dict(r) for r in rows])


@app.route("/api/assets", methods=["POST"])
@require_auth
def create_asset():
    data = request.get_json(force=True)
    fields = {k: data[k] for k in WRITABLE_COLUMNS if k in data}
    if "asset_name" not in fields or "category" not in fields:
        return jsonify({"error": "asset_name and category are required"}), 400
    fields, err = validate_fields(fields)
    if err:
        return jsonify({"error": err}), 400

    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    db = get_db()
    try:
        cur = db.execute(
            f"INSERT INTO assets ({cols}) VALUES ({placeholders})",
            list(fields.values()),
        )
    except sqlite3.IntegrityError as e:
        return jsonify({"error": str(e)}), 400
    db.commit()
    row = db.execute("SELECT * FROM assets WHERE id = ?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201


@app.route("/api/assets/<int:asset_id>", methods=["GET"])
@require_auth
def get_asset(asset_id):
    row = get_db().execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    if row is None:
        return jsonify({"error": "Not found"}), 404
    return jsonify(dict(row))


@app.route("/api/assets/<int:asset_id>", methods=["PUT"])
@require_auth
def update_asset(asset_id):
    db = get_db()
    if db.execute("SELECT id FROM assets WHERE id = ?", (asset_id,)).fetchone() is None:
        return jsonify({"error": "Not found"}), 404

    data = request.get_json(force=True)
    fields = {k: data[k] for k in WRITABLE_COLUMNS if k in data}
    if not fields:
        return jsonify({"error": "No valid fields provided"}), 400
    fields, err = validate_fields(fields)
    if err:
        return jsonify({"error": err}), 400

    set_clause = ", ".join(f"{k} = ?" for k in fields)
    set_clause += ", updated_at = datetime('now')"
    db.execute(
        f"UPDATE assets SET {set_clause} WHERE id = ?",
        list(fields.values()) + [asset_id],
    )
    db.commit()
    row = db.execute("SELECT * FROM assets WHERE id = ?", (asset_id,)).fetchone()
    return jsonify(dict(row))


@app.route("/api/assets/<int:asset_id>", methods=["DELETE"])
@require_auth
def delete_asset(asset_id):
    db = get_db()
    if db.execute("SELECT id FROM assets WHERE id = ?", (asset_id,)).fetchone() is None:
        return jsonify({"error": "Not found"}), 404
    db.execute("DELETE FROM assets WHERE id = ?", (asset_id,))
    db.commit()
    return "", 204


@app.route("/api/export", methods=["GET"])
@require_auth
def export_csv():
    db = get_db()
    rows = db.execute("SELECT * FROM assets ORDER BY category, asset_name").fetchall()

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS)
    writer.writeheader()
    for row in rows:
        writer.writerow(dict(row))

    return Response(
        buf.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=ledger_export.csv"},
    )


@app.route("/api/import/csv", methods=["POST"])
@require_auth
def import_csv():
    """Upload a CSV file and upsert rows into the ledger.

    Multipart form field: file (the CSV)
    Optional query params:
      beneficial_owner  stamped on rows with no owner column
      custodian         stamped on rows with no custodian column

    Returns:
      { "processed": N, "inserted": N, "skipped": N, "errors": [...] }
    """
    if "file" not in request.files:
        return jsonify({"error": "No file field in request"}), 400

    upload = request.files["file"]
    if not upload.filename or not upload.filename.lower().endswith(".csv"):
        return jsonify({"error": "File must be a .csv"}), 400

    try:
        from ledger_processor import process_csv  # lazy import — optional dependency
    except ImportError:
        return jsonify({"error": "pandas not installed. Run: pip install pandas"}), 503

    owner    = request.args.get("beneficial_owner", os.getenv("LEDGER_BENEFICIAL_OWNER", ""))
    custodian = request.args.get("custodian", "")

    stream = upload.stream
    result = process_csv(stream, get_db(), default_beneficial_owner=owner,
                         default_custodian=custodian)

    status_code = 200 if not result["errors"] else 207  # 207 Multi-Status = partial success
    return jsonify(result), status_code


@app.route("/api/reports/expenses", methods=["GET"])
@require_auth
def report_expenses():
    """Return a PNG bar chart of expenses by spend category.

    Query params:
      after   ISO date — only rows with acquisition_date >= after
      before  ISO date — only rows with acquisition_date <= before

    The chart groups assets where subcategory contains 'debit' or 'expense'
    and applies keyword categorization to the description field.
    """
    try:
        from ledger_processor import categorize_transaction, create_visuals
    except ImportError:
        return jsonify({"error": "pandas/matplotlib not installed"}), 503

    db = get_db()
    sql = "SELECT description, estimated_value, subcategory, acquisition_date FROM assets WHERE 1=1"
    params: list = []

    after  = request.args.get("after", "")
    before = request.args.get("before", "")
    if after:
        sql += " AND acquisition_date >= ?"
        params.append(after)
    if before:
        sql += " AND acquisition_date <= ?"
        params.append(before)

    rows = db.execute(sql, params).fetchall()
    if not rows:
        return jsonify({"error": "No data in ledger"}), 404

    import tempfile
    import pandas as _pd

    df = _pd.DataFrame([dict(r) for r in rows])
    df["Amount"]   = _pd.to_numeric(df["estimated_value"], errors="coerce").fillna(0.0)
    df["Type"]     = df["subcategory"].fillna("").apply(
        lambda s: "Expense" if any(k in s.lower() for k in ("debit", "expense")) else "Income"
    )
    df["Category"] = df["description"].fillna("").apply(categorize_transaction)

    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
        tmp_path = tmp.name

    from ledger_processor import BUDGET_LIMITS
    try:
        create_visuals(df, output_path=tmp_path,
                       type_col="Type", category_col="Category", amount_col="Amount",
                       budget_limits=BUDGET_LIMITS)
        with open(tmp_path, "rb") as fh:
            png_bytes = fh.read()
    finally:
        os.unlink(tmp_path)

    return Response(png_bytes, mimetype="image/png",
                    headers={"Content-Disposition": "inline; filename=expense_report.png"})


@app.route("/api/export/excel", methods=["GET"])
@require_auth
def export_excel():
    """Download a multi-sheet Excel workbook of the full ledger.

    Sheets:
      Raw Data       — every asset row
      Monthly Pivot  — Income / Expense / Net by calendar month (.unstack())
      Budget Check   — actual spend vs. limits per category
      Category Rollup— total spend per keyword category

    Query params:
      after   ISO date — restrict rows included
      before  ISO date — restrict rows included
    """
    try:
        from ledger_processor import categorize_transaction, export_excel as _export_excel, BUDGET_LIMITS
    except ImportError:
        return jsonify({"error": "pandas/openpyxl not installed"}), 503

    import tempfile
    import pandas as _pd

    db = get_db()
    sql = "SELECT * FROM assets WHERE 1=1"
    params: list = []

    after  = request.args.get("after", "")
    before = request.args.get("before", "")
    if after:
        sql += " AND acquisition_date >= ?"
        params.append(after)
    if before:
        sql += " AND acquisition_date <= ?"
        params.append(before)

    rows = db.execute(sql, params).fetchall()
    if not rows:
        return jsonify({"error": "No data in ledger"}), 404

    df = _pd.DataFrame([dict(r) for r in rows])
    df["Amount"]   = _pd.to_numeric(df["estimated_value"], errors="coerce").fillna(0.0)
    df["Type"]     = df["subcategory"].fillna("").apply(
        lambda s: "Expense" if any(k in s.lower() for k in ("debit", "expense")) else "Income"
    )
    df["Category"] = df["description"].fillna("").apply(categorize_transaction)

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        _export_excel(df, output_path=tmp_path, budget_limits=BUDGET_LIMITS)
        with open(tmp_path, "rb") as fh:
            xlsx_bytes = fh.read()
    finally:
        os.unlink(tmp_path)

    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=stark_financial_report.xlsx"},
    )


@app.route("/api/reports/budget", methods=["GET"])
@require_auth
def report_budget():
    """Return a JSON budget check — actual spend vs. limits per category.

    Query params:
      after   ISO date — restrict to rows with acquisition_date >= after
      before  ISO date — restrict to rows with acquisition_date <= before

    Response (200):
      {
        "summary": {"over": 1, "warning": 0, "ok": 6},
        "items": [
          {"category": "Technology", "limit": 5000.0, "actual": 6200.0,
           "variance": -1200.0, "status": "over"},
          ...
        ]
      }
    """
    try:
        from ledger_processor import categorize_transaction, check_budgets
    except ImportError:
        return jsonify({"error": "pandas not installed"}), 503

    import pandas as _pd

    db = get_db()
    sql = "SELECT description, estimated_value, subcategory FROM assets WHERE 1=1"
    params: list = []

    after  = request.args.get("after", "")
    before = request.args.get("before", "")
    if after:
        sql += " AND acquisition_date >= ?"
        params.append(after)
    if before:
        sql += " AND acquisition_date <= ?"
        params.append(before)

    rows = db.execute(sql, params).fetchall()
    if not rows:
        return jsonify({"summary": {"over": 0, "warning": 0, "ok": 0}, "items": []})

    df = _pd.DataFrame([dict(r) for r in rows])
    df["Amount"]   = _pd.to_numeric(df["estimated_value"], errors="coerce").fillna(0.0)
    df["Type"]     = df["subcategory"].fillna("").apply(
        lambda s: "Expense" if any(k in s.lower() for k in ("debit", "expense")) else "Income"
    )
    df["Category"] = df["description"].fillna("").apply(categorize_transaction)

    items = check_budgets(df, type_col="Type", category_col="Category", amount_col="Amount")
    summary = {
        "over":    sum(1 for i in items if i["status"] == "over"),
        "warning": sum(1 for i in items if i["status"] == "warning"),
        "ok":      sum(1 for i in items if i["status"] == "ok"),
    }
    return jsonify({"summary": summary, "items": items})


# ---------------------------------------------------------------------------
# Tax Filing — "Tax Hack"
# ---------------------------------------------------------------------------

@app.route("/api/tax/summary", methods=["GET"])
@require_auth
def tax_summary():
    """Return a JSON tax summary computed from existing assets.

    Query params:
      year  int — tax year label (default: current calendar year)

    Response 200:
      {
        "tax_year": 2025,
        "generated_at": "...",
        "disclaimer": "...",
        "capital_gains": [...],
        "deductions": [...],
        "hacks": [...],
        "summary": { ... }
      }
    """
    try:
        from tax_engine import generate_tax_report
    except ImportError:
        return jsonify({"error": "tax_engine module not available"}), 503

    import datetime as _dt
    year = int(request.args.get("year", _dt.date.today().year))
    report = generate_tax_report(get_db(), tax_year=year)
    return jsonify(report)


@app.route("/api/tax/file", methods=["POST"])
@require_auth
def tax_file():
    """Generate and download a tax filing workbook (Excel).

    Optional JSON body:
      { "year": 2025, "entity_name": "...", "preparer": "..." }

    Response 200: .xlsx attachment with four sheets:
      Summary, Capital Gains, Deductions, Tax Hacks
    """
    try:
        from tax_engine import generate_tax_report, export_tax_excel
    except ImportError:
        return jsonify({"error": "tax_engine module not available"}), 503

    import datetime as _dt

    data = request.get_json(silent=True) or {}
    year        = int(data.get("year", _dt.date.today().year))
    entity_name = data.get("entity_name", "Stark Financial Holdings LLC")
    preparer    = data.get("preparer", "")

    report = generate_tax_report(get_db(), tax_year=year)
    report["filing_metadata"] = {
        "entity_name": entity_name,
        "preparer":    preparer,
        "filed_at":    _dt.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "status":      "draft",
    }

    xlsx_bytes = export_tax_excel(report)
    filename   = f"stark_tax_filing_{year}.xlsx"
    return Response(
        xlsx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.route("/api/sync/starkbank", methods=["POST"])
@require_auth
def sync_starkbank():
    """Pull live transactions from Stark Bank and upsert into the ledger.

    Optional JSON body:
      { "limit": 50, "after": "2024-01-01", "before": "2024-12-31" }

    Returns:
      { "inserted": N, "skipped": N }
    """
    missing = [v for v in ("STARKBANK_ENVIRONMENT", "STARKBANK_PROJECT_ID", "STARKBANK_PRIVATE_KEY")
               if not os.getenv(v)]
    if missing:
        return jsonify({"error": f"Missing env vars: {', '.join(missing)}"}), 503

    try:
        from starkbank_sync import sync_transactions  # lazy import — optional dependency
    except ImportError:
        return jsonify({"error": "starkbank package not installed. Run: pip install starkbank"}), 503

    data    = request.get_json(silent=True) or {}
    limit   = min(int(data.get("limit", 100)), 1000)
    after   = data.get("after")
    before  = data.get("before")

    try:
        inserted, skipped = sync_transactions(get_db(), limit=limit, after=after, before=before)
    except Exception as exc:  # noqa: BLE001
        return jsonify({"error": str(exc)}), 502

    return jsonify({"inserted": inserted, "skipped": skipped})


if __name__ == "__main__":
    app.run(debug=False)

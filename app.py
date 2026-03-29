"""Stark Financial Holdings LLC — Asset Ledger."""

import csv
import io
import os
import sqlite3
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

    cols = ", ".join(fields.keys())
    placeholders = ", ".join("?" for _ in fields)
    db = get_db()
    cur = db.execute(
        f"INSERT INTO assets ({cols}) VALUES ({placeholders})",
        list(fields.values()),
    )
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


if __name__ == "__main__":
    app.run(debug=False)

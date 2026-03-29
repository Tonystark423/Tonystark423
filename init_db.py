#!/usr/bin/env python3
"""Initialize the ledger SQLite database from schema.sql."""

import os
import sqlite3
import sys

from dotenv import load_dotenv

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "ledger.db")
SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")


def init_db():
    if not os.path.exists(SCHEMA_PATH):
        print(f"Error: schema.sql not found at {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(1)

    with open(SCHEMA_PATH, "r") as f:
        schema = f.read()

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.commit()
        print(f"Database initialized successfully: {DB_PATH}")
    except sqlite3.Error as e:
        print(f"Error initializing database: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()

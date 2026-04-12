CREATE TABLE IF NOT EXISTS assets (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name       TEXT    NOT NULL,
    category         TEXT    NOT NULL CHECK(category IN (
                         'Proprietary IP',
                         'Computer Resources',
                         'Money Market Funds',
                         'Securities & Commodities',
                         'Cryptocurrency'
                     )),
    subcategory      TEXT,
    description      TEXT,
    quantity         TEXT,   -- stored as Decimal string ("0.0001" precision) to avoid IEEE 754 drift
    unit             TEXT,
    estimated_value  TEXT,   -- stored as Decimal string; use DECIMAL(19,4) if migrating to PostgreSQL
    acquisition_date TEXT,
    custodian        TEXT,
    beneficial_owner TEXT,
    status           TEXT    NOT NULL DEFAULT 'active'
                             CHECK(status IN ('active', 'sold', 'pending')),
    notes            TEXT,
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- FTS5 virtual table for full-text search (content table — no data duplication)
CREATE VIRTUAL TABLE IF NOT EXISTS assets_fts
    USING fts5(
        asset_name,
        description,
        notes,
        custodian,
        content='assets',
        content_rowid='id'
    );

-- Keep FTS index in sync with the assets table
CREATE TRIGGER IF NOT EXISTS assets_ai AFTER INSERT ON assets BEGIN
    INSERT INTO assets_fts(rowid, asset_name, description, notes, custodian)
    VALUES (new.id, new.asset_name, new.description, new.notes, new.custodian);
END;

CREATE TRIGGER IF NOT EXISTS assets_ad AFTER DELETE ON assets BEGIN
    INSERT INTO assets_fts(assets_fts, rowid, asset_name, description, notes, custodian)
    VALUES ('delete', old.id, old.asset_name, old.description, old.notes, old.custodian);
END;

CREATE TRIGGER IF NOT EXISTS assets_au AFTER UPDATE ON assets BEGIN
    INSERT INTO assets_fts(assets_fts, rowid, asset_name, description, notes, custodian)
    VALUES ('delete', old.id, old.asset_name, old.description, old.notes, old.custodian);
    INSERT INTO assets_fts(rowid, asset_name, description, notes, custodian)
    VALUES (new.id, new.asset_name, new.description, new.notes, new.custodian);
END;


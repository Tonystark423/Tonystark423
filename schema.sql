CREATE TABLE IF NOT EXISTS assets (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_name       TEXT    NOT NULL,
    category         TEXT    NOT NULL CHECK(category IN (
                         'Proprietary IP',
                         'Computer Resources',
                         'Money Market Funds',
                         'Securities & Commodities',
                         'Cryptocurrency',
                         'Real Estate'
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


-- ---------------------------------------------------------------------------
-- Claims Ledger — unpaid obligations owed TO Stark Financial Holdings LLC
-- ---------------------------------------------------------------------------
-- Each row is a distinct claim against an institution or counterparty.
-- Creates a timestamped, auditable paper trail for demand letters,
-- arbitration filings, and forensic accounting reconstruction.
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS claims (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    institution       TEXT    NOT NULL,
    claim_type        TEXT    NOT NULL DEFAULT 'other'
                              CHECK(claim_type IN (
                                  'wages',
                                  'investment_return',
                                  'royalties',
                                  'breach_of_contract',
                                  'settlement',
                                  'judgment',
                                  'other'
                              )),
    amount_owed       TEXT    NOT NULL DEFAULT '0.0000',
    currency          TEXT    NOT NULL DEFAULT 'USD',
    origin_date       TEXT,
    last_contact_date TEXT,
    status            TEXT    NOT NULL DEFAULT 'open'
                              CHECK(status IN (
                                  'open',
                                  'demand_sent',
                                  'in_negotiation',
                                  'arbitration',
                                  'litigation',
                                  'judgment_obtained',
                                  'settled',
                                  'closed_no_recovery'
                              )),
    jurisdiction      TEXT,
    counsel           TEXT,
    description       TEXT,
    notes             TEXT,
    created_at        TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at        TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TRIGGER IF NOT EXISTS claims_au AFTER UPDATE ON claims BEGIN
    UPDATE claims SET updated_at = datetime('now') WHERE id = old.id;
END;

-- ---------------------------------------------------------------------------
-- Portfolio: Cryptocurrency, US Equities, and other holdings
-- ---------------------------------------------------------------------------
-- Existing 'assets' table covers Cryptocurrency and Securities & Commodities.
-- Use beneficial_owner = 'All-Star Financial Holdings' to tag those holdings.
-- Use subcategory for ticker / coin symbol (e.g. 'BTC', 'AAPL').
-- Use custodian for exchange or wallet provider (e.g. 'Coinbase', 'NYSE').
-- ---------------------------------------------------------------------------

-- Batch Signing Log — records each signing event for crypto transactions,
-- Stark Bank payment batches, or equity trade authorizations.
CREATE TABLE IF NOT EXISTS batch_signings (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_ref       TEXT    NOT NULL,   -- internal reference / txn batch ID
    asset_category  TEXT    CHECK(asset_category IN (
                        'Cryptocurrency',
                        'Securities & Commodities',
                        'Money Market Funds',
                        'Other'
                    )),
    signer          TEXT,               -- individual or system that signed
    num_items       INTEGER DEFAULT 0,  -- number of transactions in batch
    total_value     TEXT,               -- Decimal string, same convention as assets
    currency        TEXT    DEFAULT 'USD',
    status          TEXT    NOT NULL DEFAULT 'pending'
                            CHECK(status IN ('pending', 'signed', 'failed', 'cancelled')),
    notes           TEXT,
    signed_at       TEXT,               -- ISO datetime when signing completed
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Portfolio summary view — total holdings by category, status, and owner
CREATE VIEW IF NOT EXISTS portfolio_summary AS
SELECT
    category,
    subcategory,
    status,
    beneficial_owner,
    COUNT(*)                              AS asset_count,
    SUM(CAST(estimated_value AS REAL))    AS total_value_usd,
    unit
FROM assets
GROUP BY category, subcategory, status, beneficial_owner, unit;

-- ---------------------------------------------------------------------------
-- Bankruptcy Claims — track cases, trustees, and recovered assets
-- ---------------------------------------------------------------------------
-- Workflow:
--   1. Create a claim record with the PACER case number and trustee info.
--   2. As assets are recovered, insert them into the assets table and link
--      them here via recovered_asset_id.
--   3. Advance status through: identified → filed → pending_recovery → recovered → closed
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS bankruptcy_claims (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    claimant_name       TEXT    NOT NULL,           -- name searched (e.g. "Evan Jacob Burke")
    case_number         TEXT,                       -- PACER case number (e.g. "24-10042")
    court               TEXT,                       -- e.g. "D.N.H." (District of New Hampshire)
    trustee_name        TEXT,
    trustee_contact     TEXT,
    source              TEXT    CHECK(source IN (
                            'PACER',
                            'State Unclaimed Property',
                            'Bankruptcy Court',
                            'Trustee Direct',
                            'Other'
                        )),
    claim_type          TEXT    CHECK(claim_type IN (
                            'Cash',
                            'Securities',
                            'Cryptocurrency',
                            'Real Property',
                            'Personal Property',
                            'Other'
                        )),
    claimed_value       TEXT,                       -- Decimal string, estimated value of claim
    recovered_value     TEXT,                       -- Decimal string, actual recovered amount
    currency            TEXT    DEFAULT 'USD',
    status              TEXT    NOT NULL DEFAULT 'identified'
                                CHECK(status IN (
                                    'identified',       -- found in search
                                    'filed',            -- claim formally filed
                                    'pending_recovery', -- approved, awaiting disbursement
                                    'recovered',        -- funds/assets received
                                    'closed'            -- resolved / no recovery
                                )),
    recovered_asset_id  INTEGER REFERENCES assets(id),  -- linked ledger asset once recovered
    filing_date         TEXT,                       -- ISO date claim was filed
    recovery_date       TEXT,                       -- ISO date asset was received
    notes               TEXT,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Summary view: total claimed vs recovered by status and claimant
CREATE VIEW IF NOT EXISTS bankruptcy_summary AS
SELECT
    claimant_name,
    status,
    source,
    COUNT(*)                                   AS claim_count,
    SUM(CAST(claimed_value   AS REAL))         AS total_claimed_usd,
    SUM(CAST(recovered_value AS REAL))         AS total_recovered_usd
FROM bankruptcy_claims
GROUP BY claimant_name, status, source;

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


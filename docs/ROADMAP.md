# Stark Financial Holdings LLC — Asset Ledger Roadmap

This roadmap tracks the evolution of the Asset Ledger: a private, searchable
Flask application backed by SQLite that records all company holdings
(cryptocurrency, securities & commodities, money market funds, computer
resources, proprietary IP) plus the supporting tax, claims, and signing
workflows.

Milestones are ordered by dependency and risk. Each milestone lists its scope,
the concrete deliverables already in the repository that anchor it, and the
acceptance criteria that mark it complete. Dates are relative quarters (Q+1,
Q+2, …) so the plan stays valid as the calendar moves.

## Current State (Baseline)

What ships today, confirmed against the working tree:

- **Application core** — `app.py`, 24 routes: asset CRUD + full-text search,
  CSV import (`/api/import/csv`), CSV + multi-sheet Excel export
  (`/api/export`, `/api/export/excel`), portfolio and budget/expense reports.
- **Storage** — SQLite via `schema.sql` (`assets`, `batch_signings`,
  `portfolio_summary` view); `init_db.py` bootstraps it. `ledger.db` and `.env`
  are gitignored and never committed.
- **Tax engine** — `tax_engine.py` computes realized gains/losses, applies
  Section 179 + 100% bonus depreciation, and folds in OBBBA (H.R. 1, 2025)
  provisions; surfaced through `/api/tax/summary` and `/api/tax/file`.
- **Integrations** — `ledger_processor.py` (CSV ingest with column aliasing and
  Decimal precision) and `starkbank_sync.py` (optional Stark Bank pull via
  `/api/sync/starkbank`, sandbox by default).
- **Workflows** — claims management (`/api/claims*`) and batch signing log
  (`/api/signings*`) for crypto transactions, Stark Bank batches, and equity
  trade authorizations.
- **Client tooling** — `StreamDeckController/` (C# controller + ledger client)
  and `seed_assets.py` for initial portfolio seeding.
- **Quality** — `tests/` (6 suites: app, db spy, mutations, nested logic, tax,
  validation), `scripts/check_assertion_density.py` + `weekly_quality_report.py`,
  ADR-001 assertion-density gate, weekly quality-report CI workflow.
- **Docs** — `README.md`, `TESTING_STANDARDS.md`, `docs/adr/`, corporate banking
  resolution materials under `docs/`.

Open gaps observed: HTTP Basic Auth only (no sessions, no rate limiting, no
audit trail); no schema migration tooling; tax engine is a single in-process
module with no persisted filing history; Stark Bank sync is manual and
sandbox-only; deployment story is local `flask run` behind optional nginx.

---

## Milestone 1 — Security & Auth Hardening (Q+1)

Raise the access-control baseline above HTTP Basic Auth and make every
state-changing action attributable.

Scope:
- Replace plaintext Basic Auth with session-based auth (`LEDGER_USER` /
  `LEDGER_PASS` retained for the single-operator case) and a logout path.
- Add rate limiting on auth and write endpoints; keep the `require_auth`
  decorator but extend it to record the actor.
- Introduce an append-only `audit_log` table recording actor, route, method,
  target id, and timestamp for all `POST`/`PUT`/`DELETE` and sync calls.
- Centralize secret loading; fail fast if `FLASK_SECRET_KEY` is the
  `changeme` default in non-debug runs.
- Add a `SECURITY.md` summarizing the threat model and the existing
  gitignore/PII guarantees from `README.md`.

Acceptance criteria:
- Every write route writes exactly one `audit_log` row; tests assert the row
  exists and its actor field is correct.
- `check_assertion_density.py` passes on the new auth/audit tests (no ghost
  coverage — see ADR-001).
- Default-secret startup guard has a dedicated failing-fast test.

## Milestone 2 — Schema Lifecycle & Data Integrity (Q+1)

Make the SQLite schema versioned and migratable instead of recreated by hand.

Scope:
- Add a `schema_version` table and a lightweight migration runner
  (`migrations/NNN_*.sql`) invoked by `init_db.py`; existing `schema.sql`
  becomes migration `001`.
- Add CHECK constraints and foreign keys where the schema currently relies on
  application-layer validation (status enums, `batch_signings.asset_category`,
  signed/created/updated ordering).
- Harden `validate_fields` in `app.py` so the API and the CSV processor share
  one validation path; today `ledger_processor.py` re-implements category
  checks.
- Persist tax filings: a `tax_filings` table backing `/api/tax/file` so past
  filings are queryable rather than regenerated.

Acceptance criteria:
- A fresh `python init_db.py` and an upgrade from the prior version both
  converge to head schema with no data loss, covered by a migration test.
- `VALID_CATEGORIES` is defined once and consumed by both `app.py` and
  `ledger_processor.py`.
- `/api/tax/file` records and `/api/tax/summary` reads back a prior filing.

## Milestone 3 — Reporting, Tax & Analytics (Q+2)

Deepen the reporting surface that the homepage dashboard and tax engine began.

Scope:
- Extend the homepage traffic-analytics dashboard (`/`) to compose portfolio
  summary, budget, and expense signals into a single real-time view.
- Add multi-year and comparison-period tax reports; refactor `tax_engine.py`
  constants (OBBBA limits, rates, holding-day threshold) into a versioned
  tax-rule module so prior-year filings are reproducible.
- Add a holdings-history (cost-basis vs. current) feed to support
  unrealized-gain views alongside the existing realized-gain path.
- Expand Excel export (`/api/export/excel`) with a tax and an audit worksheet.

Acceptance criteria:
- A report test asserts reproducibility: the same inputs produce identical
  outputs across runs and across Python versions in the support matrix.
- Comparison-period report returns correct deltas for a seeded portfolio.
- Export workbook opens in Excel and openpyxl with the new sheets present.

## Milestone 4 — Integrations & Automation (Q+2)

Move Stark Bank sync and CSV ingest from manual triggers toward reliable
automation.

Scope:
- Promote Stark Bank from sandbox-only: support `STARKBANK_ENVIRONMENT=production`
  with explicit opt-in and a dry-run mode that previews rows before upsert.
- Add a scheduled sync path (cron/systemd timer or GitHub Actions) with
  idempotent upserts keyed on `batch_ref` / transaction id to avoid duplicates.
- Add webhook-style endpoints (no inbound network exposure required) so the
  StreamDeckController and external systems can pull deltas, not full state.
- Add a connector-agnostic import interface so future custodians map through
  the same `ledger_processor` alias layer.

Acceptance criteria:
- Sync run is idempotent: running twice on the same upstream batch inserts
  zero duplicate rows (covered by `test_db_spy.py`-style spy tests).
- Dry-run returns the planned upsert set without writing.
- Production environment requires an explicit env flag and is refused in
  tests by default.

## Milestone 5 — Operations, Observability & Deployment (Q+3)

Make the single-operator deployment reproducible and observable.

Scope:
- Add structured request logging and a `/healthz` endpoint; surface the
  `audit_log` (M1) and sync history (M4) for the operator.
- Define an official deployment path beyond local `flask run`: container build
  and a one-command `gunicorn`/reverse-proxy setup; document HTTPS via the
  existing nginx + Let's Encrypt note.
- Add automated SQLite backup/restore for `ledger.db` with rotation, since
  the DB is the source of truth and is never committed.
- Document the runbook (restore, rotate keys, rotate `FLASK_SECRET_KEY`)
  alongside `SECURITY.md`.

Acceptance criteria:
- `docker build` produces a working image; smoke test hits `/healthz` and an
  authenticated route.
- Backup + restore round-trips a populated `ledger.db` and verifies row counts.
- Runbook covers key rotation with no data loss and no dropped auth sessions.

## Milestone 6 — Quality, Mutation Testing & Docs (Q+3, ongoing)

Lock in the quality baseline the assertion-density gate established.

Scope:
- Wire `scripts/demo_surviving_mutant.py` into CI on a fixed corpus so
  mutation-testing results are tracked over time, not only generated locally.
- Keep the `--cov-fail-under=80` gate and add a branch-coverage companion;
  enforce the assertion-density gate as a hard CI failure (it is currently a
  report).
- Add ADRs for any architectural decisions introduced in M1–M5, following the
  format of `docs/adr/001-assertion-density-quality-gate.md`.
- Keep `ROADMAP.md` updated each milestone with a "shipped" marker and a link
  to the closing PR.

Acceptance criteria:
- CI fails on a surviving mutant in the security- or tax-critical modules.
- Branch coverage and assertion density both gate the build.
- Every completed milestone has a merged ADR or a roadmap note explaining why
  one was not needed.

---

## Tracking

Status legend: 🔵 planned · 🟡 in progress · 🟢 shipped

| Milestone | Quarter | Status |
|---|---|---|
| M1 — Security & Auth Hardening | Q+1 | 🔵 |
| M2 — Schema Lifecycle & Data Integrity | Q+1 | 🔵 |
| M3 — Reporting, Tax & Analytics | Q+2 | 🔵 |
| M4 — Integrations & Automation | Q+2 | 🔵 |
| M5 — Operations, Observability & Deployment | Q+3 | 🔵 |
| M6 — Quality, Mutation Testing & Docs | ongoing | 🔵 |

This roadmap is a living document. Update the table and append a short
"shipped" note (with the merging PR) at the end of each milestone rather than
rewriting history.

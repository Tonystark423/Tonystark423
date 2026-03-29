# Testing Standards

Three-tiered quality system for this codebase.

---

## The Enforcer — CI Quality Gates (`blank.yml`)

Every PR to `main` must pass all three checks:

| Gate | Tool | Threshold | Blocks on |
|---|---|---|---|
| Workflow lint | `actionlint` | — | Invalid YAML syntax, deprecated commands |
| Branch coverage | `pytest --cov` | 80% minimum | Coverage drop below floor |
| Assertion density | `scripts/check_assertion_density.py` | 0.08 minimum | Any test with 0 assertions; file density below floor |

Run locally before pushing:
```bash
pytest tests/ -v --cov=app --cov-report=term-missing --cov-fail-under=80
python scripts/check_assertion_density.py tests/
```

---

## Assertion Density

**Formula:** `assertions / lines_in_function`

| Range | Label | Meaning |
|---|---|---|
| 0.0 | Danger | Vanity test — code is touched, nothing is verified |
| < 0.5 | Below threshold | Thin — likely missing control/exclusion assertions |
| 0.5–0.65 | Acceptable | Adequate for setup-heavy integration tests |
| ≥ 0.66 | Healthy | Target for unit and focused integration tests |
| 1.0 | High integrity | Single-purpose test, every line asserts |

> Integration tests naturally score lower than unit tests because setup code
> (seeding, HTTP calls, fixture wiring) inflates the denominator. The hard
> rule is **zero vanity tests** (0 assertions). The 0.08 CI floor catches
> files that have drifted entirely into vanity territory.

---

## The Playbook — Four Patterns

### Pattern 1 — Value over Existence

Always assert the *business rule*, not just that code ran.

```python
# Vanity — density 0.0: proves nothing except "no exception"
def test_create_asset_vanity(client, auth):
    resp = client.post("/api/assets", json={...}, auth=auth)
    assert resp.status_code == 201

# Value — density 0.67: proves the business rule held
def test_create_asset_default_status_is_active(client, auth):
    resp = client.post("/api/assets",
                       json={"asset_name": "X", "category": "Cryptocurrency"},
                       auth=auth)
    assert resp.status_code == 201
    assert resp.get_json()["status"] == "active"   # business rule
```

**Reference:** `tests/test_app.py` — `TestCreateAsset`

---

### Pattern 2 — Inner Gate: test rejections inside-out

When a function has nested gates, test the innermost one first in complete
isolation. This proves each gate is independently load-bearing — removing
any single gate would be caught immediately.

```
require_auth (outer gate)
  └─ no header / wrong user / wrong pass  → 401
  └─ pass ──► update_asset
                └─ ID not found           → 404  (outer inner gate)
                └─ no valid fields        → 400  (inner inner gate)
                └─ pass ──► UPDATE + 200
```

```python
# Inner gate in isolation — ID exists, payload is the only variable
def test_inner_gate_empty_payload_blocked(client, auth, existing_id):
    resp = client.put(f"/api/assets/{existing_id}",
                      json={"id": 99},   # non-writable key only
                      auth=auth)
    assert resp.status_code == 400
    assert "No valid fields" in resp.get_json()["error"]

# Gate ordering — proves Gate 1 fires before Gate 2
def test_gates_are_ordered_outer_before_inner(client, auth):
    resp = client.put("/api/assets/999999",
                      json={},           # would trigger Gate 2 if reached
                      auth=auth)
    assert resp.status_code == 404       # Gate 1 wins
    assert resp.get_json()["error"] == "Not found"
```

**Reference:** `tests/test_nested_logic.py` — `TestInnerGatePattern`

---

### Pattern 3 — Decision Matrix: cover all branch combinations

When a function has N boolean variables, map every combination and give
each its own test. Use seed data designed to make each combination produce
a *distinct* result set.

For `list_assets` (`q` × `category` × `status` = 8 combinations):

```python
# Every test has inclusion AND exclusion assertions.
# The exclusion assert is what gives it value — without it,
# a broken filter that returns everything still passes.

def test_q_and_category(client, auth, matrix_data):
    resp = client.get("/api/assets?q=MatrixAsset&category=Cryptocurrency", auth=auth)
    found = {r["custodian"] for r in resp.get_json()}
    assert "AlphaExchange" in found      # ✓ included
    assert "BetaExchange"  in found      # ✓ included
    assert "GammaVault"    not in found  # ✗ excluded (wrong category)
    assert "DeltaVault"    not in found  # ✗ excluded (wrong category)
```

**Reference:** `tests/test_nested_logic.py` — `TestDecisionMatrix`

---

### Pattern 4 — State Verification: read the DB, not the response

After a mutation, open a direct DB connection and verify the row. This
catches a class of bug where the API response is hardcoded correctly but
the data was never actually written (or was written to the wrong column).

```python
# Bad: trusts the API response
def test_create_trusts_response(client, auth):
    resp = client.post("/api/assets", json={...}, auth=auth)
    assert resp.get_json()["status"] == "active"   # response could be faked

# Good: reads the DB directly
def test_create_verifies_db_state(client, auth):
    resp = client.post("/api/assets", json={...}, auth=auth)
    asset_id = resp.get_json()["id"]

    conn = sqlite3.connect(DB_PATH)
    row = conn.execute("SELECT status FROM assets WHERE id = ?", (asset_id,)).fetchone()
    conn.close()

    assert row[0] == "active"   # proved in the DB, not in the response
```

**Reference:** `tests/test_db_spy.py` — `TestDBStateVerification`

---

### Pattern 5 — Parametrize boundary sweeps

Use `@pytest.mark.parametrize` for boundary arithmetic. Each case becomes
a named data point in the CI report. Adding a new boundary is one line,
not a new test function.

```python
@pytest.mark.parametrize("requested,expected_max", [
    (1,    1),
    (1000, 1000),   # exactly at cap
    (1001, 1000),   # cap triggers
    (9999, 1000),   # far over cap
])
def test_limit_boundary_sweep(client, auth, requested, expected_max):
    resp = client.get(f"/api/assets?limit={requested}", auth=auth)
    assert len(resp.get_json()) <= expected_max
```

**Reference:** `tests/test_nested_logic.py` — `test_limit_boundary_sweep`

---

## Test File Reference

| File | Patterns covered |
|---|---|
| `tests/test_app.py` | Auth branches, CRUD edge cases, boundary values (null/negative/zero), filter paths |
| `tests/test_db_spy.py` | SQL injection guard (spy), state verification, FTS trigger verification |
| `tests/test_nested_logic.py` | Decision matrix (8 combinations), inner gate ordering, parametrized boundary sweep, filter isolation with control records |
| `scripts/check_assertion_density.py` | AST-based density gate — run in CI and locally |

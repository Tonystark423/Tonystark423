# ADR-001: Assertion Density Quality Gate

**Status:** Accepted
**Date:** 2026-03-29
**Deciders:** Engineering team

---

## Context

Standard line/branch coverage metrics report which code was *executed* during
tests, but say nothing about whether the tests *verified* anything. A test
suite can achieve 100% line coverage while containing zero meaningful
assertions — a condition known as "ghost coverage."

Concrete example from this codebase: the `require_auth` decorator contains
the condition:

```python
if not auth or auth.username != LEDGER_USER or auth.password != LEDGER_PASS:
```

Changing the first `or` to `and` (a single-character mutation) causes all
requests without an `Authorization` header to bypass authentication. A test
suite with only a "happy path" test for authenticated requests would still
report 100% line coverage after this mutation — the mutant survives.

This class of bug is not hypothetical. Boolean operator errors in access
control are a recurring source of security vulnerabilities.

## Decision

We adopt a three-tiered quality gate enforced in CI on every PR:

### Tier 1 — Branch Coverage Floor (existing)
`pytest --cov=app --cov-fail-under=80`
Ensures code paths are *reached*. Necessary but not sufficient.

### Tier 2 — Assertion Density Gate (new)
`scripts/check_assertion_density.py --diff-only --min-density 0.5`

- Uses AST analysis to count `assert` statements per test function
- Only checks functions whose lines overlap the PR diff (Boy Scout Rule)
- Hard-fails on any test function with 0 assertions (vanity tests)
- Hard-fails if touched functions average below 0.5 density

Density formula: `assertions / source_lines_in_function`

| Range | Label | Policy |
|---|---|---|
| 0.0 | Vanity | Hard block — must be fixed before merge |
| < 0.5 | Thin | Hard block on new/modified code |
| 0.5–0.65 | Acceptable | Passes gate |
| ≥ 0.66 | Healthy | Target |

### Tier 3 — Mutation-Killing Tests (new practice)
For security-critical logic (auth, access control, financial calculations),
test functions are written to explicitly target named mutants:

```python
def test_wrong_username_correct_password_denied(self, client):
    """Kills: MUTANT 3 (username != → ==), MUTANT 4 (second or → and)"""
    resp = client.get("/api/assets", auth=("wronguser", "legitpass"))
    assert resp.status_code == 401
```

Each boolean operator in a security boundary requires at least one test
that would fail if that operator were mutated.

## Consequences

### Positive
- Mutations to boolean operators in `require_auth` are caught before merge
- The CI gate distinguishes "code was run" from "code was verified"
- New contributors receive immediate, specific feedback ("0 assertions in
  this function — what is it proving?") rather than a vague coverage number
- The weekly density report surfaces quality trends before they become
  technical debt

### Negative / Mitigations
- **Integration test density is structurally lower** than unit test density
  because setup code inflates the denominator. Mitigated by the 0.08 floor
  for integration suites vs 0.5 for the diff gate, and by documenting the
  distinction in `TESTING_STANDARDS.md`.
- **Generated/mock files skew the metric.** Mitigated by `--exclude` patterns
  in `weekly_quality_report.py` and documented in `TESTING_STANDARDS.md`.
- **Legacy code is not retroactively penalised.** The `--diff-only` flag
  means only touched functions are checked. Legacy debt is addressed via
  the Boy Scout Rule: leave any function you modify with higher density
  than you found it.
- **Grace period for rollout.** Set `continue-on-error: true` on the density
  gate step in `blank.yml` for the first sprint to let the team observe
  scores without being blocked. Remove it once the team stabilises above
  the floor.

## Alternatives Considered

**Full mutation testing with `mutmut` or `cosmic-ray`**
Would catch all surviving mutants automatically. Rejected for initial
adoption because mutation test runs are slow (minutes to hours on large
codebases) and require significant CI time budget. Planned for V2 once
the team has internalised assertion density.

**Property-based testing with `hypothesis`**
Valuable for boundary arithmetic (the limit-cap logic in `list_assets` is
a natural fit). Rejected for initial adoption for the same ramp-up reason.
The parametrized boundary sweep in `tests/test_nested_logic.py` is a
manual approximation until `hypothesis` is introduced.

**Raising the coverage floor to 95%+**
Does not solve ghost coverage. A developer can satisfy 95% coverage with
assertions that always pass regardless of the code under test. Density
addresses the root cause; coverage floor does not.

## References

- `TESTING_STANDARDS.md` — patterns and examples
- `scripts/check_assertion_density.py` — gate implementation
- `scripts/demo_surviving_mutant.py` — live demo of ghost coverage
- `tests/test_mutations.py` — mutation-killing suite for `require_auth`
- `.github/workflows/blank.yml` — CI gate configuration

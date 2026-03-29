#!/usr/bin/env python3
"""
Live Demo: Surviving Mutant — Ghost Coverage in Action
=======================================================
Designed for use in engineering presentations.

What it does (in order):
  1. Runs the test suite — confirms everything is green
  2. Applies a single-character mutation to require_auth in app.py:
       changes the first `or` to `and`
     This means: a request with no Authorization header only gets blocked
     if the username check *also* fails — i.e. no-header requests from
     a client that somehow passes the username check slip through.
  3. Runs the test suite again — shows which tests survive vs are killed
  4. Reverts the mutation unconditionally (even if tests crash)
  5. Prints a summary: survived mutants expose ghost coverage

Usage:
    python scripts/demo_surviving_mutant.py

    # Run against a specific test file only (faster for live demo):
    python scripts/demo_surviving_mutant.py --tests tests/test_app.py

    # Show the mutation-killing suite killing the mutant:
    python scripts/demo_surviving_mutant.py --tests tests/test_mutations.py
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path

APP_PATH = Path(__file__).parent.parent / "app.py"

# The exact string to mutate and what to replace it with
MUTATION = {
    "description": "require_auth: first `or` → `and`",
    "original":    "if not auth or auth.username != LEDGER_USER or auth.password != LEDGER_PASS:",
    "mutant":      "if not auth and auth.username != LEDGER_USER or auth.password != LEDGER_PASS:",
    "effect": (
        "A request with no Authorization header is only blocked when the "
        "username check also fails. Clients that omit the header but somehow "
        "satisfy the username condition bypass authentication entirely."
    ),
}

DIVIDER = "=" * 64


def run_tests(test_paths: list[str]) -> tuple[int, str]:
    result = subprocess.run(
        ["python", "-m", "pytest"] + test_paths + ["-v", "--tb=no", "-q"],
        capture_output=True, text=True,
    )
    return result.returncode, result.stdout + result.stderr


def apply_mutation(source: str) -> str:
    if MUTATION["original"] not in source:
        raise ValueError(
            f"Mutation target not found in {APP_PATH}.\n"
            f"Expected: {MUTATION['original']!r}"
        )
    return source.replace(MUTATION["original"], MUTATION["mutant"], 1)


def revert_mutation(source: str) -> str:
    return source.replace(MUTATION["mutant"], MUTATION["original"], 1)


def print_section(title: str) -> None:
    print(f"\n{DIVIDER}")
    print(f"  {title}")
    print(DIVIDER)


def summarise_results(label: str, returncode: int, output: str) -> None:
    passed = output.count(" PASSED")
    failed = output.count(" FAILED")
    errors = output.count(" ERROR")
    status = "ALL PASSED" if returncode == 0 else f"{failed} FAILED, {errors} ERRORS"
    print(f"\n  [{label}] {status}  ({passed} passed, {failed} failed)")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Live demo: surviving mutant")
    parser.add_argument(
        "--tests", nargs="*",
        default=["tests/"],
        help="Test paths to run (default: tests/)",
    )
    args = parser.parse_args(argv)

    original_source = APP_PATH.read_text(encoding="utf-8")

    # ------------------------------------------------------------------
    # Step 1: Baseline — everything green
    # ------------------------------------------------------------------
    print_section("STEP 1 — Baseline: run the test suite (expect: all green)")
    baseline_rc, baseline_out = run_tests(args.tests)
    summarise_results("BASELINE", baseline_rc, baseline_out)
    if baseline_rc != 0:
        print("\n  ⚠ Baseline is already failing. Fix tests before running demo.")
        return 1

    # ------------------------------------------------------------------
    # Step 2: Apply mutation
    # ------------------------------------------------------------------
    print_section("STEP 2 — Apply mutation to app.py")
    print(f"\n  Mutation : {MUTATION['description']}")
    print(f"\n  Before   : {MUTATION['original']}")
    print(f"  After    : {MUTATION['mutant']}")
    print(f"\n  Effect   : {MUTATION['effect']}")

    try:
        mutant_source = apply_mutation(original_source)
        APP_PATH.write_text(mutant_source, encoding="utf-8")
        print("\n  Mutation applied.")

        # ------------------------------------------------------------------
        # Step 3: Run tests against the mutant
        # ------------------------------------------------------------------
        print_section("STEP 3 — Run tests against the mutant")
        mutant_rc, mutant_out = run_tests(args.tests)
        summarise_results("MUTANT", mutant_rc, mutant_out)

        # Count surviving vs killed
        passed_lines = [l for l in mutant_out.splitlines() if "PASSED" in l]
        failed_lines = [l for l in mutant_out.splitlines() if "FAILED" in l]

        print_section("STEP 4 — Verdict")
        if mutant_rc == 0:
            print(f"\n  🚨 MUTANT SURVIVED — {len(passed_lines)} test(s) still pass")
            print("\n  This is Ghost Coverage. The mutation is undetected.")
            print("  These tests executed the mutated code but verified nothing:")
            for line in passed_lines[:10]:
                print(f"    {line.strip()}")
            outcome = "SURVIVED"
        else:
            print(f"\n  ✅ MUTANT KILLED — {len(failed_lines)} test(s) caught the mutation")
            print("\n  These tests detected the logic change:")
            for line in failed_lines[:10]:
                print(f"    {line.strip()}")
            outcome = "KILLED"

    finally:
        # ------------------------------------------------------------------
        # Step 4 (always): Revert — even if tests crashed
        # ------------------------------------------------------------------
        APP_PATH.write_text(original_source, encoding="utf-8")
        print(f"\n{DIVIDER}")
        print("  app.py reverted to original. Repository is clean.")
        print(DIVIDER)

    print(f"\n  Demo complete. Mutant: {outcome}")
    print(
        "\n  Next step: run with --tests tests/test_mutations.py to show"
        "\n  the mutation-killing suite killing the same mutant.\n"
    )
    return 0 if outcome == "KILLED" else 0  # demo always exits 0


if __name__ == "__main__":
    sys.exit(main())

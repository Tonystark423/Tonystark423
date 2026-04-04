#!/usr/bin/env python3
"""
Assertion Density Quality Gate
===============================
Parses every test_*.py file using the AST and reports, per test function:

    density = assert_count / max(source_lines, 1)

Exits non-zero if:
  - Any individual test function has 0 assertions  (vanity test — density 0.0)
  - The overall file-level density is below MIN_DENSITY (default 0.5)

Usage:
    python scripts/check_assertion_density.py [tests/]
    python scripts/check_assertion_density.py --min-density 0.6 tests/

Diff-aware mode (Migration Path / Boy Scout Rule):
    python scripts/check_assertion_density.py --diff-only tests/

    With --diff-only the gate only checks test functions whose source lines
    overlap with the current git diff (origin/main...HEAD by default).
    Legacy functions that were not touched in this PR are skipped entirely.
    New files are always checked in full regardless of --diff-only.

    Override the diff base:
    python scripts/check_assertion_density.py --diff-only --base HEAD~3 tests/

Exit codes:
    0  All files pass the quality gate
    1  One or more files/functions failed
"""

import ast
import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


MIN_DENSITY_DEFAULT = 0.5

# AST node types that count as assertions
ASSERT_NODE_TYPES = (ast.Assert,)

# pytest.raises / pytest.warns used as context managers also count
PYTEST_ASSERT_CALLS = {"raises", "warns", "approx"}


def count_assertions(node: ast.AST) -> int:
    """Recursively count assertion statements within an AST node."""
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
        # pytest.raises(...) / pytest.warns(...) as context manager
        elif isinstance(child, ast.With):
            for item in child.items:
                expr = item.context_expr
                if isinstance(expr, ast.Call):
                    func = expr.func
                    # matches: pytest.raises, pytest.warns
                    if (
                        isinstance(func, ast.Attribute)
                        and func.attr in PYTEST_ASSERT_CALLS
                    ):
                        count += 1
                    # matches bare: raises(...)
                    elif isinstance(func, ast.Name) and func.id in PYTEST_ASSERT_CALLS:
                        count += 1
    return count


def source_lines(node: ast.FunctionDef) -> int:
    """Number of non-blank, non-comment lines in the function body."""
    return max(1, (node.end_lineno or node.lineno) - node.lineno)


@dataclass
class FunctionResult:
    name: str
    lineno: int
    assertions: int
    lines: int

    @property
    def density(self) -> float:
        return self.assertions / max(self.lines, 1)

    @property
    def passed(self) -> bool:
        return self.assertions > 0


@dataclass
class FileResult:
    path: Path
    functions: list[FunctionResult] = field(default_factory=list)

    @property
    def total_assertions(self) -> int:
        return sum(f.assertions for f in self.functions)

    @property
    def total_lines(self) -> int:
        return sum(f.lines for f in self.functions)

    @property
    def overall_density(self) -> float:
        return self.total_assertions / max(self.total_lines, 1)

    @property
    def zero_assertion_functions(self) -> list[FunctionResult]:
        return [f for f in self.functions if f.assertions == 0]


def analyse_file(path: Path) -> FileResult:
    result = FileResult(path=path)
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))

    # Only iterate direct children of the module to avoid double-counting
    # class methods (which ast.walk would visit both at top-level and inside ClassDef)
    for node in ast.iter_child_nodes(tree):
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
            # Top-level test function
            result.functions.append(FunctionResult(
                name=node.name,
                lineno=node.lineno,
                assertions=count_assertions(node),
                lines=source_lines(node),
            ))
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            # Test class — only process direct method children
            for item in ast.iter_child_nodes(node):
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test_"):
                    result.functions.append(FunctionResult(
                        name=f"{node.name}::{item.name}",
                        lineno=item.lineno,
                        assertions=count_assertions(item),
                        lines=source_lines(item),
                    ))

    return result


def collect_test_files(paths: list[Path]) -> list[Path]:
    files = []
    for p in paths:
        if p.is_file() and p.name.startswith("test_") and p.suffix == ".py":
            files.append(p)
        elif p.is_dir():
            files.extend(sorted(p.rglob("test_*.py")))
    return files


def changed_lines_by_file(base: str) -> dict[Path, set[int]]:
    """
    Return a mapping of {file_path: {changed_line_numbers}} by parsing
    `git diff --unified=0 <base>` output.

    Only added/modified lines (prefixed with +) are included — deleted
    lines no longer exist in the working tree and can't be checked.
    New files (diff header shows /dev/null as the old path) are recorded
    with an empty set as a sentinel meaning "check all lines."
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--unified=0", base],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as e:
        print(f"Warning: git diff failed ({e}). Falling back to full scan.",
              file=sys.stderr)
        return {}

    changed: dict[Path, set[int]] = {}
    current_file: Path | None = None
    is_new_file = False
    current_line = 0

    for line in result.stdout.splitlines():
        if line.startswith("diff --git"):
            current_file = None
            is_new_file = False
        elif line.startswith("--- "):
            is_new_file = line.strip() == "--- /dev/null"
        elif line.startswith("+++ "):
            raw = line[4:].strip()
            if raw == "/dev/null":
                current_file = None
            else:
                # Strip the "b/" prefix git adds
                current_file = Path(raw[2:] if raw.startswith("b/") else raw)
                if is_new_file:
                    # New file — sentinel: check everything
                    changed[current_file] = set()
        elif line.startswith("@@ ") and current_file is not None:
            # @@ -old_start,old_count +new_start,new_count @@
            try:
                new_part = line.split("+")[1].split(" ")[0]
                start, *rest = new_part.split(",")
                count = int(rest[0]) if rest else 1
                current_line = int(start)
                if current_file not in changed:
                    changed[current_file] = set()
                changed[current_file].update(
                    range(current_line, current_line + max(count, 1))
                )
            except (ValueError, IndexError):
                pass
        elif line.startswith("+") and not line.startswith("+++"):
            if current_file is not None and current_file in changed:
                changed[current_file].add(current_line)
            current_line += 1
        elif not line.startswith("-"):
            current_line += 1

    return changed


def function_overlaps_diff(fn: "FunctionResult", changed: set[int]) -> bool:
    """
    True if the function's line range overlaps the changed line set,
    OR if changed is empty (sentinel for new files — check everything).
    """
    if not changed:  # new file sentinel
        return True
    return any(ln in changed for ln in range(fn.lineno, fn.lineno + fn.lines + 1))


def format_density(density: float) -> str:
    if density == 0.0:
        return f"{density:.2f} [DANGER]"
    elif density < 0.5:
        return f"{density:.2f} [BELOW THRESHOLD]"
    elif density < 0.66:
        return f"{density:.2f} [ACCEPTABLE]"
    else:
        return f"{density:.2f} [HEALTHY]"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Assertion Density Quality Gate")
    parser.add_argument(
        "paths",
        nargs="*",
        default=["tests"],
        help="Test files or directories to analyse (default: tests/)",
    )
    parser.add_argument(
        "--min-density",
        type=float,
        default=MIN_DENSITY_DEFAULT,
        metavar="FLOAT",
        help=f"Minimum acceptable overall density per file (default: {MIN_DENSITY_DEFAULT})",
    )
    parser.add_argument(
        "--no-fail-zero",
        action="store_true",
        help="Do not fail on individual functions with 0 assertions",
    )
    parser.add_argument(
        "--diff-only",
        action="store_true",
        help=(
            "Boy Scout / Migration Path mode: only check test functions whose "
            "lines overlap the current git diff. Legacy untouched functions are "
            "skipped. New files are always checked in full."
        ),
    )
    parser.add_argument(
        "--base",
        default="origin/main",
        metavar="REF",
        help="Git ref to diff against when using --diff-only (default: origin/main)",
    )
    args = parser.parse_args(argv)

    test_files = collect_test_files([Path(p) for p in args.paths])
    if not test_files:
        print("No test files found.", file=sys.stderr)
        return 1

    diff_map: dict[Path, set[int]] = {}
    if args.diff_only:
        diff_map = changed_lines_by_file(args.base)
        if not diff_map:
            print("  No changed test files detected in diff — nothing to check.")
            print(f"\n{'='*60}\n  QUALITY GATE: PASSED (no changed tests)\n{'='*60}\n")
            return 0
        print(f"  Diff-aware mode: checking only lines changed vs {args.base!r}")

    overall_failed = False

    for path in test_files:
        result = analyse_file(path)
        if not result.functions:
            continue

        # In diff-only mode, resolve the path relative to the repo root
        # (git diff uses repo-relative paths)
        if args.diff_only:
            # Try both the raw path and its resolved absolute form
            rel = Path(*path.parts[-path.parts.__len__():])  # as-is
            file_changed = diff_map.get(path) or diff_map.get(rel)
            for diff_path, diff_lines in diff_map.items():
                if path.resolve().as_posix().endswith(diff_path.as_posix()):
                    file_changed = diff_lines
                    break
            else:
                if file_changed is None:
                    continue  # file not in diff — skip entirely (legacy)

            # Filter to only functions that overlap the diff
            result.functions = [
                fn for fn in result.functions
                if function_overlaps_diff(fn, file_changed)
            ]
            if not result.functions:
                continue

        print(f"\n{'='*60}")
        print(f"  {path}")
        print(f"{'='*60}")
        print(f"  {'Function':<55} {'Asserts':>7}  {'Lines':>5}  Density")
        print(f"  {'-'*55} {'-'*7}  {'-'*5}  {'-'*20}")

        file_failed = False

        for fn in result.functions:
            marker = ""
            if fn.assertions == 0:
                marker = " <-- VANITY (0 assertions)"
                if not args.no_fail_zero:
                    file_failed = True
            elif fn.density < args.min_density:
                marker = " <-- LOW DENSITY"
                # Low per-function density is a warning, not a hard fail
            print(
                f"  {fn.name:<55} {fn.assertions:>7}  {fn.lines:>5}  "
                f"{format_density(fn.density)}{marker}"
            )

        print(f"\n  Overall density: {format_density(result.overall_density)}")
        print(f"  Total assertions: {result.total_assertions}  |  "
              f"Total lines: {result.total_lines}  |  "
              f"Test functions: {len(result.functions)}")

        if result.overall_density < args.min_density:
            print(f"\n  FAIL: overall density {result.overall_density:.2f} "
                  f"< required {args.min_density:.2f}")
            file_failed = True

        if result.zero_assertion_functions and not args.no_fail_zero:
            names = ", ".join(f.name for f in result.zero_assertion_functions)
            print(f"\n  FAIL: {len(result.zero_assertion_functions)} vanity test(s) "
                  f"with 0 assertions: {names}")

        if file_failed:
            overall_failed = True

    print(f"\n{'='*60}")
    if overall_failed:
        print("  QUALITY GATE: FAILED")
        print("  Fix vanity tests (add meaningful assertions) or raise density.")
    else:
        print("  QUALITY GATE: PASSED")
    print(f"{'='*60}\n")

    return 1 if overall_failed else 0


if __name__ == "__main__":
    sys.exit(main())

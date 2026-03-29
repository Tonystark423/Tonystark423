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

Exit codes:
    0  All files pass the quality gate
    1  One or more files/functions failed
"""

import ast
import argparse
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
    args = parser.parse_args(argv)

    test_files = collect_test_files([Path(p) for p in args.paths])
    if not test_files:
        print("No test files found.", file=sys.stderr)
        return 1

    overall_failed = False

    for path in test_files:
        result = analyse_file(path)
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

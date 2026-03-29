#!/usr/bin/env python3
"""
Weekly Assertion Density Quality Report
========================================
Produces a per-contributor density summary for the last N days by:
  1. Finding commits in the window via git log
  2. Extracting which test functions each author added or modified
     (using the same AST parser as check_assertion_density.py)
  3. Reporting density, badge, and trend per contributor

Usage:
    python scripts/weekly_quality_report.py
    python scripts/weekly_quality_report.py --days 14
    python scripts/weekly_quality_report.py --since 2025-01-01
    python scripts/weekly_quality_report.py --format markdown   # default
    python scripts/weekly_quality_report.py --format csv

Why Python instead of bash:
  - The bash version counts raw diff lines as the denominator, which
    inflates the count with blank lines, comments, and imports.
  - This version uses AST-level function analysis — the same measure
    the CI gate uses — so the numbers are directly comparable.
"""

import argparse
import csv
import io
import json
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Reuse the AST analysis from check_assertion_density.py
sys.path.insert(0, str(Path(__file__).parent))
from check_assertion_density import analyse_file, FunctionResult  # noqa: E402


# ---------------------------------------------------------------------------
# Badge thresholds
# ---------------------------------------------------------------------------

def badge(density: float) -> str:
    if density >= 1.0:  return "Diamond"
    if density >= 0.66: return "Gold"
    if density >= 0.5:  return "Silver"
    if density > 0.0:   return "Thin"
    return "Vanity"


def badge_emoji(b: str) -> str:
    return {
        "Diamond": "💎 Diamond",
        "Gold":    "✅ Gold",
        "Silver":  "🔵 Silver",
        "Thin":    "⚠️  Thin",
        "Vanity":  "🚨 Vanity",
    }.get(b, b)


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------

def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"git error: {result.stderr.strip()}", file=sys.stderr)
        return ""
    return result.stdout


def commits_in_window(since: str) -> list[dict]:
    """Return list of {hash, author, date} for commits since the given date."""
    out = run([
        "git", "log",
        f"--since={since}",
        "--format=%H\t%aN\t%aI",   # hash, author name, ISO date
    ])
    commits = []
    for line in out.strip().splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) == 3:
            commits.append({"hash": parts[0], "author": parts[1], "date": parts[2]})
    return commits


def test_files_changed_in_commit(commit_hash: str) -> list[Path]:
    """Return test_*.py files that were added or modified in this commit."""
    out = run(["git", "diff-tree", "--no-commit-id", "-r", "--name-only", commit_hash])
    return [
        Path(p) for p in out.strip().splitlines()
        if p and Path(p).name.startswith("test_") and p.endswith(".py")
    ]


def changed_line_numbers_in_commit(commit_hash: str, file_path: Path) -> set[int]:
    """
    Return the set of line numbers that were added (+) in this commit
    for the given file, by parsing the unified diff.
    """
    out = run([
        "git", "diff", "--unified=0",
        f"{commit_hash}^", commit_hash, "--", str(file_path),
    ])
    changed: set[int] = set()
    current_new_line = 0

    for line in out.splitlines():
        if line.startswith("@@ "):
            try:
                new_part = line.split("+")[1].split(" ")[0]
                start, *rest = new_part.split(",")
                current_new_line = int(start)
            except (ValueError, IndexError):
                pass
        elif line.startswith("+") and not line.startswith("+++"):
            changed.add(current_new_line)
            current_new_line += 1
        elif not line.startswith("-"):
            current_new_line += 1

    return changed


def file_at_commit(commit_hash: str, file_path: Path) -> str | None:
    """Return the content of a file at a specific commit, or None if absent."""
    result = subprocess.run(
        ["git", "show", f"{commit_hash}:{file_path}"],
        capture_output=True, text=True,
    )
    return result.stdout if result.returncode == 0 else None


# ---------------------------------------------------------------------------
# Per-author analysis
# ---------------------------------------------------------------------------

@dataclass
class AuthorStats:
    author: str
    functions_checked: int = 0
    total_assertions: int = 0
    total_lines: int = 0
    vanity_count: int = 0       # functions with 0 assertions
    commits_analysed: int = 0
    example_functions: list[str] = field(default_factory=list)

    @property
    def density(self) -> float:
        return self.total_assertions / max(self.total_lines, 1)

    @property
    def has_data(self) -> bool:
        return self.functions_checked > 0


def analyse_author_commit(
    commit_hash: str,
    file_path: Path,
    stats: AuthorStats,
) -> None:
    """
    Analyse a single (commit, file) pair and accumulate results into stats.
    Only functions whose lines overlap the commit's diff are counted.
    """
    # Get the file content at this commit
    content = file_at_commit(commit_hash, file_path)
    if content is None:
        return

    # Write to a temp path for analyse_file (it needs a real Path)
    import tempfile, os
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".py", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        file_result = analyse_file(tmp_path)
    finally:
        os.unlink(tmp_path)

    if not file_result.functions:
        return

    changed_lines = changed_line_numbers_in_commit(commit_hash, file_path)
    if not changed_lines:
        return  # nothing added in this file in this commit

    stats.commits_analysed += 1
    for fn in file_result.functions:
        fn_lines = set(range(fn.lineno, fn.lineno + fn.lines + 1))
        if not fn_lines & changed_lines:
            continue  # function wasn't touched in this commit

        stats.functions_checked += 1
        stats.total_assertions += fn.assertions
        stats.total_lines += max(fn.lines, 1)
        if fn.assertions == 0:
            stats.vanity_count += 1
        if len(stats.example_functions) < 3:
            stats.example_functions.append(fn.name)


# ---------------------------------------------------------------------------
# Report rendering
# ---------------------------------------------------------------------------

def render_markdown(rows: list[AuthorStats], window: str) -> str:
    lines = [
        f"## Weekly Quality Report — last {window}",
        f"_Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}_",
        "",
        "| Contributor | Density | Badge | Functions | Vanity Tests | Commits |",
        "| :--- | :---: | :--- | :---: | :---: | :---: |",
    ]
    for s in rows:
        if not s.has_data:
            continue
        lines.append(
            f"| {s.author} "
            f"| {s.density:.2f} "
            f"| {badge_emoji(badge(s.density))} "
            f"| {s.functions_checked} "
            f"| {s.vanity_count} "
            f"| {s.commits_analysed} |"
        )

    if not any(s.has_data for s in rows):
        lines.append("| _(no test changes in window)_ | — | — | — | — | — |")

    team_assertions = sum(s.total_assertions for s in rows if s.has_data)
    team_lines      = sum(s.total_lines      for s in rows if s.has_data)
    team_density    = team_assertions / max(team_lines, 1)
    team_vanity     = sum(s.vanity_count for s in rows if s.has_data)

    lines += [
        "",
        f"**Team average density:** `{team_density:.2f}` "
        f"({badge_emoji(badge(team_density))})  ",
        f"**Total vanity tests added:** `{team_vanity}`  ",
        f"**Target:** `0.5` minimum · `0.66` healthy · `1.0` high integrity",
    ]
    return "\n".join(lines)


def render_csv(rows: list[AuthorStats]) -> str:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=[
        "author", "density", "badge", "functions_checked",
        "vanity_count", "commits_analysed",
    ])
    writer.writeheader()
    for s in rows:
        if not s.has_data:
            continue
        writer.writerow({
            "author":            s.author,
            "density":           f"{s.density:.2f}",
            "badge":             badge(s.density),
            "functions_checked": s.functions_checked,
            "vanity_count":      s.vanity_count,
            "commits_analysed":  s.commits_analysed,
        })
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Weekly assertion density report")
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--days", type=int, default=7, metavar="N",
        help="Report window in days (default: 7)",
    )
    group.add_argument(
        "--since", metavar="DATE",
        help="ISO date to start from, e.g. 2025-01-01 (overrides --days)",
    )
    parser.add_argument(
        "--format", choices=["markdown", "csv"], default="markdown",
        help="Output format (default: markdown)",
    )
    parser.add_argument(
        "--min-commits", type=int, default=1, metavar="N",
        help="Minimum commits to appear in report (default: 1)",
    )
    args = parser.parse_args(argv)

    if args.since:
        since = args.since
        window_label = f"since {since}"
    else:
        since = (
            datetime.now(timezone.utc) - timedelta(days=args.days)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        window_label = f"{args.days} days"

    commits = commits_in_window(since)
    if not commits:
        print(f"No commits found since {since}.")
        return 0

    # Accumulate stats per author
    author_stats: dict[str, AuthorStats] = {}
    for commit in commits:
        author = commit["author"]
        if author not in author_stats:
            author_stats[author] = AuthorStats(author=author)

        for test_file in test_files_changed_in_commit(commit["hash"]):
            analyse_author_commit(commit["hash"], test_file, author_stats[author])

    # Filter and sort
    rows = sorted(
        [s for s in author_stats.values() if s.commits_analysed >= args.min_commits],
        key=lambda s: s.density,
        reverse=True,
    )

    if args.format == "csv":
        print(render_csv(rows))
    else:
        print(render_markdown(rows, window_label))

    # Exit non-zero if any contributor has vanity tests in the window
    total_vanity = sum(s.vanity_count for s in rows)
    return 1 if total_vanity > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

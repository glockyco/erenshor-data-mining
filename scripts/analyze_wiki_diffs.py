#!/usr/bin/env python3
"""
Analyze diffs between fetched and generated wiki pages.
Provides comprehensive statistics and identifies potential issues.

Usage:
    python scripts/analyze_wiki_diffs.py [--variant VARIANT]

Examples:
    python scripts/analyze_wiki_diffs.py
    python scripts/analyze_wiki_diffs.py --variant playtest
"""

import os
import difflib
from pathlib import Path
import argparse


def get_file_stats(filepath):
    """Get basic statistics about a file."""
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        return {"size": len(content), "lines": len(lines), "content": content}
    except Exception as e:
        return None


def analyze_diff(fetched_file, generated_file):
    """Analyze diff between two files."""
    fetched_stats = get_file_stats(fetched_file)
    generated_stats = get_file_stats(generated_file)

    if not fetched_stats or not generated_stats:
        return None

    # Calculate unified diff
    diff = list(
        difflib.unified_diff(
            fetched_stats["content"].splitlines(keepends=True),
            generated_stats["content"].splitlines(keepends=True),
            lineterm="",
            n=0,  # No context lines
        )
    )

    # Count changes
    additions = sum(1 for line in diff if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in diff if line.startswith("-") and not line.startswith("---"))

    # Calculate size changes
    size_change = generated_stats["size"] - fetched_stats["size"]
    size_change_pct = (size_change / fetched_stats["size"] * 100) if fetched_stats["size"] > 0 else 0

    line_change = generated_stats["lines"] - fetched_stats["lines"]

    return {
        "additions": additions,
        "deletions": deletions,
        "total_changes": additions + deletions,
        "size_change": size_change,
        "size_change_pct": size_change_pct,
        "line_change": line_change,
        "fetched_size": fetched_stats["size"],
        "generated_size": generated_stats["size"],
        "fetched_lines": fetched_stats["lines"],
        "generated_lines": generated_stats["lines"],
        "diff_lines": len(diff),
    }


def main():
    parser = argparse.ArgumentParser(description="Analyze wiki page diffs")
    parser.add_argument("--variant", default="playtest", help="Variant to analyze (default: playtest)")
    args = parser.parse_args()

    # Paths
    FETCHED_DIR = Path(f"variants/{args.variant}/wiki/fetched")
    GENERATED_DIR = Path(f"variants/{args.variant}/wiki/generated")

    if not FETCHED_DIR.exists():
        print(f"Error: Fetched directory not found: {FETCHED_DIR}")
        return 1

    if not GENERATED_DIR.exists():
        print(f"Error: Generated directory not found: {GENERATED_DIR}")
        return 1

    print("=" * 80)
    print("WIKI PAGE DIFF ANALYSIS")
    print("=" * 80)
    print(f"Variant: {args.variant}")
    print()

    # Find all fetched files
    fetched_files = set()
    for root, dirs, files in os.walk(FETCHED_DIR):
        for file in files:
            if file.endswith(".txt"):
                rel_path = Path(root).relative_to(FETCHED_DIR) / file
                fetched_files.add(str(rel_path))

    # Find all generated files
    generated_files = set()
    for root, dirs, files in os.walk(GENERATED_DIR):
        for file in files:
            if file.endswith(".txt"):
                rel_path = Path(root).relative_to(GENERATED_DIR) / file
                generated_files.add(str(rel_path))

    # Pages in both (can compare)
    common_pages = fetched_files & generated_files
    new_pages = generated_files - fetched_files
    deleted_pages = fetched_files - generated_files

    print(f"Total fetched pages:   {len(fetched_files)}")
    print(f"Total generated pages: {len(generated_files)}")
    print(f"Pages to compare:      {len(common_pages)}")
    print(f"New pages:             {len(new_pages)}")
    print(f"Deleted pages:         {len(deleted_pages)}")
    print()

    # Analyze diffs for common pages
    print("Analyzing diffs...")
    results = []

    for i, rel_path in enumerate(sorted(common_pages), 1):
        if i % 100 == 0:
            print(f"  Processed {i}/{len(common_pages)} pages...")

        fetched_file = FETCHED_DIR / rel_path
        generated_file = GENERATED_DIR / rel_path

        diff_stats = analyze_diff(fetched_file, generated_file)
        if diff_stats:
            results.append({"path": rel_path, "name": Path(rel_path).stem, **diff_stats})

    print(f"  Completed {len(results)} comparisons")
    print()

    # Statistics
    print("=" * 80)
    print("DIFF STATISTICS")
    print("=" * 80)
    print()

    # Pages with no changes
    no_changes = [r for r in results if r["total_changes"] == 0]
    print(f"Pages with NO changes: {len(no_changes)}")

    # Pages with changes
    with_changes = [r for r in results if r["total_changes"] > 0]
    print(f"Pages WITH changes:    {len(with_changes)}")
    print()

    if with_changes:
        # Distribution of change sizes
        changes = [r["total_changes"] for r in with_changes]
        print(f"Change distribution:")
        print(f"  Min changes:     {min(changes)}")
        print(f"  Max changes:     {max(changes)}")
        print(f"  Median changes:  {sorted(changes)[len(changes) // 2]}")
        print(f"  Mean changes:    {sum(changes) / len(changes):.1f}")
        print()

        # Size change distribution
        size_changes_pct = [r["size_change_pct"] for r in with_changes]
        print(f"Size change distribution:")
        print(f"  Min:     {min(size_changes_pct):+.1f}%")
        print(f"  Max:     {max(size_changes_pct):+.1f}%")
        print(f"  Median:  {sorted(size_changes_pct)[len(size_changes_pct) // 2]:+.1f}%")
        print(f"  Mean:    {sum(size_changes_pct) / len(size_changes_pct):+.1f}%")
        print()

    # Large changes (potential issues)
    print("=" * 80)
    print("POTENTIAL ISSUES")
    print("=" * 80)
    print()

    # Pages with very large diffs (>500 lines changed)
    large_diffs = sorted(
        [r for r in with_changes if r["total_changes"] > 500], key=lambda x: x["total_changes"], reverse=True
    )
    print(f"Pages with >500 line changes: {len(large_diffs)}")
    if large_diffs:
        print("\nTop 10 largest diffs:")
        for r in large_diffs[:10]:
            print(
                f"  {r['total_changes']:4d} changes | {r['size_change']:+6d} bytes ({r['size_change_pct']:+6.1f}%) | {r['name']}"
            )
    print()

    # Pages with massive size changes (>100% or <-50%)
    huge_growth = sorted(
        [r for r in with_changes if r["size_change_pct"] > 100], key=lambda x: x["size_change_pct"], reverse=True
    )
    huge_shrink = sorted([r for r in with_changes if r["size_change_pct"] < -50], key=lambda x: x["size_change_pct"])

    print(f"Pages with >100% size increase: {len(huge_growth)}")
    if huge_growth:
        print("\nTop 10 size increases:")
        for r in huge_growth[:10]:
            print(
                f"  {r['size_change_pct']:+7.1f}% | {r['fetched_size']:5d} -> {r['generated_size']:5d} bytes | {r['name']}"
            )
    print()

    print(f"Pages with >50% size decrease: {len(huge_shrink)}")
    if huge_shrink:
        print("\nTop 10 size decreases:")
        for r in huge_shrink[:10]:
            print(
                f"  {r['size_change_pct']:+7.1f}% | {r['fetched_size']:5d} -> {r['generated_size']:5d} bytes | {r['name']}"
            )
    print()

    # Very small pages (might be broken)
    tiny_pages = sorted([r for r in results if r["generated_size"] < 100], key=lambda x: x["generated_size"])
    print(f"Generated pages <100 bytes (might be broken): {len(tiny_pages)}")
    if tiny_pages:
        print("\nSmallest generated pages:")
        for r in tiny_pages[:10]:
            print(f"  {r['generated_size']:3d} bytes | {r['name']}")
    print()

    # Top 20 pages by total changes
    print("=" * 80)
    print("TOP 20 PAGES BY TOTAL CHANGES")
    print("=" * 80)
    print()

    top_changes = sorted(with_changes, key=lambda x: x["total_changes"], reverse=True)[:20]
    for i, r in enumerate(top_changes, 1):
        print(
            f"{i:2d}. {r['total_changes']:4d} changes (+{r['additions']:-4d}/-{r['deletions']:4d}) | "
            f"{r['size_change']:+6d}b ({r['size_change_pct']:+6.1f}%) | {r['name']}"
        )
    print()

    print("=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)

    return 0


if __name__ == "__main__":
    exit(main())

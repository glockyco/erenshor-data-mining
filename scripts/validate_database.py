#!/usr/bin/env python3
"""Validate Erenshor database for data quality issues.

This script checks for:
- Duplicate IDs across Items, Spells, Skills, Characters, and Quests
- Missing required fields
- Data consistency issues

Usage:
    python scripts/validate_database.py main
    python scripts/validate_database.py playtest
    python scripts/validate_database.py --all
"""

import argparse
import sqlite3
import sys
from pathlib import Path


def get_db_path(variant: str) -> Path:
    """Get the database path for a variant."""
    repo_root = Path(__file__).parent.parent
    return repo_root / "variants" / variant / f"erenshor-{variant}.sqlite"


def check_duplicate_ids(db_path: Path, variant: str) -> list[dict]:
    """Check for duplicate IDs in Items, Spells, Skills, Characters, and Quests."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    issues = []

    # Check Items
    cursor.execute("""
        SELECT Id, COUNT(*) as Count, GROUP_CONCAT(ResourceName, ', ') as Resources
        FROM Items
        WHERE Id IS NOT NULL AND Id != ''
        GROUP BY Id
        HAVING COUNT(*) > 1
        ORDER BY Count DESC, Id
    """)
    for row in cursor.fetchall():
        issues.append({
            "variant": variant,
            "type": "Items",
            "severity": "ERROR",
            "id": row[0],
            "count": row[1],
            "resources": row[2],
            "message": f"Duplicate Item ID {row[0]} found in {row[1]} items: {row[2]}",
        })

    # Check Spells
    cursor.execute("""
        SELECT Id, COUNT(*) as Count, GROUP_CONCAT(ResourceName, ', ') as Resources
        FROM Spells
        WHERE Id IS NOT NULL AND Id != ''
        GROUP BY Id
        HAVING COUNT(*) > 1
        ORDER BY Count DESC, Id
    """)
    for row in cursor.fetchall():
        issues.append({
            "variant": variant,
            "type": "Spells",
            "severity": "ERROR",
            "id": row[0],
            "count": row[1],
            "resources": row[2],
            "message": f"Duplicate Spell ID {row[0]} found in {row[1]} spells: {row[2]}",
        })

    # Check Skills
    cursor.execute("""
        SELECT Id, COUNT(*) as Count, GROUP_CONCAT(ResourceName, ', ') as Resources
        FROM Skills
        WHERE Id IS NOT NULL AND Id != ''
        GROUP BY Id
        HAVING COUNT(*) > 1
        ORDER BY Count DESC, Id
    """)
    for row in cursor.fetchall():
        issues.append({
            "variant": variant,
            "type": "Skills",
            "severity": "ERROR",
            "id": row[0],
            "count": row[1],
            "resources": row[2],
            "message": f"Duplicate Skill ID {row[0]} found in {row[1]} skills: {row[2]}",
        })

    # Check Characters (by Id, not Guid)
    cursor.execute("""
        SELECT Id, COUNT(*) as Count, GROUP_CONCAT(ObjectName, ', ') as Objects
        FROM Characters
        WHERE Id IS NOT NULL AND Id != ''
        GROUP BY Id
        HAVING COUNT(*) > 1
        ORDER BY Count DESC, Id
        LIMIT 10
    """)
    for row in cursor.fetchall():
        issues.append({
            "variant": variant,
            "type": "Characters",
            "severity": "WARNING",
            "id": row[0],
            "count": row[1],
            "resources": row[2],
            "message": f"Duplicate Character ID {row[0]} found in {row[1]} characters: {row[2]}",
        })

    # Check Quests
    cursor.execute("""
        SELECT QuestDBIndex, COUNT(*) as Count, GROUP_CONCAT(QuestName, ', ') as Names
        FROM Quests
        WHERE QuestDBIndex IS NOT NULL
        GROUP BY QuestDBIndex
        HAVING COUNT(*) > 1
        ORDER BY Count DESC, QuestDBIndex
        LIMIT 10
    """)
    for row in cursor.fetchall():
        issues.append({
            "variant": variant,
            "type": "Quests",
            "severity": "ERROR",
            "id": row[0],
            "count": row[1],
            "resources": row[2],
            "message": f"Duplicate Quest ID {row[0]} found in {row[1]} quests: {row[2]}",
        })

    conn.close()
    return issues


def check_missing_resource_names(db_path: Path, variant: str) -> list[dict]:
    """Check for missing ResourceName fields."""
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()

    issues = []

    # Check Items
    cursor.execute("""
        SELECT COUNT(*) FROM Items WHERE ResourceName IS NULL OR ResourceName = ''
    """)
    count = cursor.fetchone()[0]
    if count > 0:
        issues.append({
            "variant": variant,
            "type": "Items",
            "severity": "WARNING",
            "message": f"{count} items have missing ResourceName",
        })

    # Check Spells
    cursor.execute("""
        SELECT COUNT(*) FROM Spells WHERE ResourceName IS NULL OR ResourceName = ''
    """)
    count = cursor.fetchone()[0]
    if count > 0:
        issues.append({
            "variant": variant,
            "type": "Spells",
            "severity": "WARNING",
            "message": f"{count} spells have missing ResourceName",
        })

    # Check Skills
    cursor.execute("""
        SELECT COUNT(*) FROM Skills WHERE ResourceName IS NULL OR ResourceName = ''
    """)
    count = cursor.fetchone()[0]
    if count > 0:
        issues.append({
            "variant": variant,
            "type": "Skills",
            "severity": "WARNING",
            "message": f"{count} skills have missing ResourceName",
        })

    conn.close()
    return issues


def validate_variant(variant: str) -> tuple[list[dict], bool]:
    """Validate a single variant database."""
    db_path = get_db_path(variant)

    if not db_path.exists():
        print(f"Error: Database not found: {db_path}", file=sys.stderr)
        return [], False

    print(f"\nValidating {variant} variant...")
    print(f"Database: {db_path}")
    print("-" * 60)

    issues = []
    issues.extend(check_duplicate_ids(db_path, variant))
    issues.extend(check_missing_resource_names(db_path, variant))

    if not issues:
        print("✅ No issues found!")
        return issues, True

    # Group by severity
    errors = [i for i in issues if i["severity"] == "ERROR"]
    warnings = [i for i in issues if i["severity"] == "WARNING"]

    if errors:
        print(f"\n❌ Found {len(errors)} ERROR(s):")
        for issue in errors:
            print(f"  - [{issue['type']}] {issue['message']}")

    if warnings:
        print(f"\n⚠️  Found {len(warnings)} WARNING(s):")
        for issue in warnings:
            print(f"  - [{issue['type']}] {issue['message']}")

    return issues, len(errors) == 0


def generate_report(all_issues: dict[str, list[dict]], output_path: Path | None = None) -> str:
    """Generate a markdown report of all validation issues."""
    report = []
    report.append("# Database Validation Report\n\n")

    total_errors = sum(len([i for i in issues if i["severity"] == "ERROR"]) for issues in all_issues.values())
    total_warnings = sum(len([i for i in issues if i["severity"] == "WARNING"]) for issues in all_issues.values())

    report.append(f"**Total Issues**: {total_errors} errors, {total_warnings} warnings\n\n")

    for variant, issues in all_issues.items():
        if not issues:
            continue

        report.append(f"## {variant.title()} Variant\n\n")

        errors = [i for i in issues if i["severity"] == "ERROR"]
        if errors:
            report.append("### Errors\n\n")
            for issue in errors:
                report.append(f"- **[{issue['type']}]** {issue['message']}\n")
            report.append("\n")

        warnings = [i for i in issues if i["severity"] == "WARNING"]
        if warnings:
            report.append("### Warnings\n\n")
            for issue in warnings:
                report.append(f"- **[{issue['type']}]** {issue['message']}\n")
            report.append("\n")

    report_text = "".join(report)

    if output_path:
        output_path.write_text(report_text)
        print(f"\nReport written to: {output_path}")

    return report_text


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Validate Erenshor database for data quality issues.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "variant",
        nargs="?",
        choices=["main", "playtest", "demo"],
        help="Variant to validate",
    )

    parser.add_argument(
        "--all",
        action="store_true",
        help="Validate all variants",
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="Output report to file",
    )

    args = parser.parse_args()

    if not args.variant and not args.all:
        parser.error("Either specify a variant or use --all")

    # Determine which variants to validate
    variants = ["main", "playtest", "demo"] if args.all else [args.variant]

    all_issues = {}
    all_passed = True

    for variant in variants:
        issues, passed = validate_variant(variant)
        all_issues[variant] = issues
        if not passed:
            all_passed = False

    # Generate report if requested
    if args.output:
        generate_report(all_issues, args.output)

    # Exit with error code if any errors found
    if not all_passed:
        print("\n❌ Validation failed with errors")
        sys.exit(1)
    else:
        print("\n✅ All validations passed!")
        sys.exit(0)


if __name__ == "__main__":
    main()

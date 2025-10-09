"""Overview page validator.

Validates overview wiki pages (Weapons, Armor) for structural correctness.
"""

from __future__ import annotations

from erenshor.domain.validation.base import ValidationResult, Violation
from erenshor.registry.core import WikiPage
from erenshor.shared.wiki_parser import parse as mw_parse

__all__ = ["OverviewValidator"]


class OverviewValidator:
    """Validate overview page structure.

    Checks:
    - Exactly one wikitable present
    - Table has datatable class
    - Table has expected column headers
    """

    def validate(self, page: WikiPage, content: str) -> ValidationResult:
        """Validate overview page content.

        Args:
            page: Wiki page metadata
            content: Rendered wiki page text

        Returns:
            ValidationResult with pass/fail status and violations
        """
        violations: list[Violation] = []

        try:
            mw_parse(content)
        except Exception as e:
            violations.append(Violation("structure", f"Parse failed: {e}", "error"))
            return ValidationResult(passed=False, violations=violations)

        # Check for exactly one wikitable
        table_count = content.count('{| class="wikitable')
        if table_count == 0:
            violations.append(Violation("table", "No wikitable found", "error"))
        elif table_count > 1:
            violations.append(
                Violation(
                    "table",
                    f"Expected exactly one wikitable, found {table_count}",
                    "warning",
                )
            )

        # Check for datatable class
        if '{| class="wikitable datatable' not in content:
            violations.append(
                Violation(
                    "datatable",
                    "Wikitable missing 'datatable' class",
                    "warning",
                )
            )

        # Check for expected column headers based on page title
        page_title = page.title
        if page_title == "Weapons":
            expected_headers = ["!Weapon", "!Slot", "!Type", "![[Classes]]"]
        elif page_title == "Armor":
            expected_headers = ["!Armor", "!Slot", "![[Classes]]"]
        else:
            expected_headers = []

        for header in expected_headers:
            if header not in content:
                violations.append(
                    Violation(
                        "headers",
                        f"Missing expected header: {header}",
                        "error",
                    )
                )

        passed = all(v.severity != "error" for v in violations)
        return ValidationResult(passed=passed, violations=violations)

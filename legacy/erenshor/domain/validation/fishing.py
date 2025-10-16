"""Fishing page validator.

Validates the Fishing wiki page for structural correctness and completeness.
"""

from __future__ import annotations

from erenshor.domain.validation.base import ValidationResult, Violation
from erenshor.registry.core import WikiPage
from erenshor.shared.wiki_parser import (
    parse as mw_parse,
)

__all__ = ["FishingValidator"]


class FishingValidator:
    """Validate Fishing page structure.

    Checks:
    - Required header '=List of Fishing Locations=' is present
    - At least one zone section exists
    - All zone sections have wikitable structure
    """

    def validate(self, page: WikiPage, content: str) -> ValidationResult:
        """Validate Fishing page content.

        Args:
            page: Wiki page metadata
            content: Rendered wiki page text

        Returns:
            ValidationResult with pass/fail status and violations
        """
        import re

        violations: list[Violation] = []

        try:
            mw_parse(content)
        except Exception as e:
            violations.append(Violation("structure", f"Parse failed: {e}", "error"))
            return ValidationResult(passed=False, violations=violations)

        # Check for required header
        if "=List of Fishing Locations=" not in content:
            violations.append(
                Violation(
                    "header",
                    "Missing required header '=List of Fishing Locations='",
                    "error",
                )
            )

        # Check for at least one zone section header: "==Zone Name Fishing Loot=="
        zone_sections = re.findall(r"^==(.+?) Fishing Loot==$", content, re.MULTILINE)
        if not zone_sections:
            violations.append(
                Violation(
                    "zones",
                    "No fishing zone sections found",
                    "error",
                )
            )

        # Check that each zone has a wikitable
        zone_count = len(zone_sections)
        table_count = content.count('{| class="wikitable"')

        if table_count < zone_count:
            violations.append(
                Violation(
                    "tables",
                    f"Expected {zone_count} wikitables for zones, found {table_count}",
                    "warning",
                )
            )

        passed = all(v.severity != "error" for v in violations)
        return ValidationResult(passed=passed, violations=violations)

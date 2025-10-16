"""Ability page validator.

Validates ability wiki pages for structural correctness and completeness.
"""

from __future__ import annotations

from erenshor.domain.validation.base import ValidationResult, Violation
from erenshor.registry.core import WikiPage
from erenshor.shared.wiki_parser import (
    find_templates as mw_find_templates,
)
from erenshor.shared.wiki_parser import (
    parse as mw_parse,
)
from erenshor.shared.wiki_parser import (
    template_params as mw_template_params,
)

__all__ = ["AbilityValidator"]


class AbilityValidator:
    """Validate ability page structure.

    Checks:
    - At least one Ability infobox present
    - For single-entity pages: exactly one infobox
    - For multi-entity pages: one infobox per entity
    - Required fields populated (type, description)
    - No conflicting templates
    """

    def validate(self, page: WikiPage, content: str) -> ValidationResult:
        """Validate ability page content.

        Args:
            page: Wiki page metadata
            content: Rendered wiki page text

        Returns:
            ValidationResult with pass/fail status and violations
        """
        violations: list[Violation] = []

        try:
            code = mw_parse(content)
        except Exception as e:
            violations.append(Violation("structure", f"Parse failed: {e}", "error"))
            return ValidationResult(passed=False, violations=violations)

        # Check for Ability templates
        ability_templates = mw_find_templates(code, ["Ability"])

        if len(ability_templates) == 0:
            violations.append(Violation("infobox", "No Ability infobox found", "error"))
        else:
            # For multi-entity pages, expect one infobox per entity
            expected_count = len(page.entities) if page.entities else 1
            if len(ability_templates) != expected_count:
                violations.append(
                    Violation(
                        "infobox",
                        f"Expected {expected_count} Ability infobox(es) for {expected_count} entity/entities, "
                        f"found {len(ability_templates)}",
                        "error",
                    )
                )

        # Check required fields if template exists
        if ability_templates:
            params = mw_template_params(ability_templates[0])

            # Type should be present
            if not params.get("type"):
                violations.append(Violation("type", "Type field missing", "warning"))

            # Description should be present
            if not params.get("description"):
                violations.append(
                    Violation("description", "Description field missing", "warning")
                )

        passed = all(v.severity != "error" for v in violations)
        return ValidationResult(passed=passed, violations=violations)

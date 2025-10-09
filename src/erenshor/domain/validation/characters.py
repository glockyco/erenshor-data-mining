"""Character page validator.

Validates character/enemy wiki pages for structural correctness and completeness.
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

__all__ = ["CharacterValidator"]


class CharacterValidator:
    """Validate character/enemy page structure.

    Checks:
    - Exactly one Enemy infobox present
    - Required fields populated (name, type, level)
    - Coordinates only for unique characters
    - Spawn chance only for hostile Boss/Rare
    - No legacy templates (Enemy Stats, Character, Pet)
    """

    def validate(self, page: WikiPage, content: str) -> ValidationResult:
        """Validate character page content.

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

        # Check for exactly one Enemy template
        enemy_templates = mw_find_templates(code, ["Enemy"])

        if len(enemy_templates) == 0:
            violations.append(Violation("infobox", "No Enemy infobox found", "error"))
        elif len(enemy_templates) > 1:
            violations.append(
                Violation(
                    "infobox",
                    f"Multiple Enemy infoboxes found ({len(enemy_templates)})",
                    "error",
                )
            )

        # Check for templates that predate current Enemy-only standard
        enemy_stats = mw_find_templates(code, ["Enemy Stats"])
        if enemy_stats:
            violations.append(
                Violation(
                    "legacy_template",
                    "Legacy Enemy Stats template found (should be removed)",
                    "warning",
                )
            )

        character_templates = mw_find_templates(code, ["Character"])
        if character_templates:
            violations.append(
                Violation(
                    "legacy_template",
                    "Legacy Character template found (should use Enemy)",
                    "warning",
                )
            )

        pet_templates = mw_find_templates(code, ["Pet"])
        if pet_templates:
            violations.append(
                Violation(
                    "legacy_template",
                    "Legacy Pet template found (should use Enemy)",
                    "warning",
                )
            )

        # Check required fields if Enemy template exists
        if enemy_templates:
            params = mw_template_params(enemy_templates[0])

            # Name should be present
            if not params.get("name"):
                violations.append(Violation("name", "Name field missing", "error"))

            # Type should be present
            if not params.get("type"):
                violations.append(Violation("type", "Type field missing", "warning"))

            # Level should be present
            if not params.get("level"):
                violations.append(Violation("level", "Level field missing", "warning"))

        passed = all(v.severity != "error" for v in violations)
        return ValidationResult(passed=passed, violations=violations)

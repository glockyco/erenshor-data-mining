"""Item page validator.

Validates item wiki pages for structural correctness and completeness.
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

__all__ = ["ItemValidator"]


class ItemValidator:
    """Validate item page structure.

    Checks:
    - Exactly one item infobox present
    - Required fields populated (sell value)
    - Weapon/armor has Fancy table with 3 tiers
    - No conflicting templates
    """

    def validate(self, page: WikiPage, content: str) -> ValidationResult:
        """Validate item page content.

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

        infobox_names = [
            "Item",
            "Weapon",
            "Armor",
            "Auras",
            "Ability Books",
            "Ability_Books",
            "Consumable",
            "Mold",
        ]
        infoboxes = mw_find_templates(code, infobox_names)

        if len(infoboxes) == 0:
            violations.append(Violation("infobox", "No infobox found", "error"))
        elif len(infoboxes) > 1:
            violations.append(
                Violation(
                    "infobox", f"Multiple infoboxes found ({len(infoboxes)})", "error"
                )
            )

        if infoboxes:
            params = mw_template_params(infoboxes[0])
            if not params.get("sell"):
                violations.append(Violation("sell", "Sell value missing", "warning"))

        weapon_fancy = mw_find_templates(code, ["Fancy-weapon"])
        armor_fancy = mw_find_templates(code, ["Fancy-armor"])

        if weapon_fancy:
            if len(weapon_fancy) not in (0, 3):
                violations.append(
                    Violation(
                        "fancy_table",
                        f"Weapon should have exactly 3 Fancy-weapon templates, found {len(weapon_fancy)}",
                        "error",
                    )
                )

        if armor_fancy:
            if len(armor_fancy) not in (0, 3):
                violations.append(
                    Violation(
                        "fancy_table",
                        f"Armor should have exactly 3 Fancy-armor templates, found {len(armor_fancy)}",
                        "error",
                    )
                )

        passed = all(v.severity != "error" for v in violations)
        return ValidationResult(passed=passed, violations=violations)

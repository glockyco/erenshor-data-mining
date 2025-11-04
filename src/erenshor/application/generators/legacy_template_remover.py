"""Legacy MediaWiki template removal system.

This module handles migration of legacy MediaWiki templates to their current
active equivalents on existing wiki pages.

Background:
-----------
Over time, the Erenshor wiki has evolved its template system. Legacy templates
like {{Consumable}}, {{Character}}, {{Pet}}, etc. need to be replaced with
their modern equivalents ({{Item}}, {{Enemy}}, etc.).

This system handles template name replacement while preserving template parameters,
ensuring wiki pages migrate smoothly to the new template system.

Features:
---------
- Replace legacy template names with active template names
- Preserve all template parameters during migration
- Handle multiple templates per page
- Remove deprecated templates entirely
- Preserve page content and structure
- Log all transformations for auditability

Example:
--------
    >>> remover = LegacyTemplateRemover()
    >>> old_wikitext = "{{Consumable|name=Health Potion|type=Food}}"
    >>> new_wikitext = remover.remove_legacy_templates(old_wikitext)
    >>> print(new_wikitext)
    {{Item|name=Health Potion|type=Food}}

Template Mappings:
------------------
Legacy -> Active:
- {{Character}} -> {{Enemy}}
- {{Pet}} -> {{Enemy}}
- {{Consumable}} -> {{Item}}
- {{Weapon}} -> {{Item}}  (non-stat info)
- {{Armor}} -> {{Item}}   (non-stat info)
- {{Auras}} -> {{Item}}

Removed Entirely:
- {{Enemy Stats}} - Now included within {{Enemy}} template (consolidated)

Not Migrated (Active Templates):
- {{Item}}
- {{Fancy-weapon}}
- {{Fancy-armor}}
- {{Fancy-charm}}
- {{Enemy}}
- {{Ability}}
- {{Mold}}
- {{Ability Books}}
"""

from collections.abc import Sequence
from typing import ClassVar

from loguru import logger

from erenshor.infrastructure.wiki.template_parser import TemplateParser


class LegacyTemplateRemover:
    """Removes or replaces legacy MediaWiki templates with active equivalents.

    This class handles the migration of wiki pages from legacy template names
    to the current active template system. It preserves all template parameters
    while updating template names.

    Attributes:
        LEGACY_MAPPINGS: Dictionary mapping legacy template names to active names.
        TEMPLATES_TO_REMOVE: List of template names to remove entirely.
        parser: TemplateParser instance for manipulating wikitext.

    Example:
        >>> remover = LegacyTemplateRemover()
        >>> wikitext = "{{Character|name=Goblin|level=5}}"
        >>> result = remover.remove_legacy_templates(wikitext)
        >>> print(result)
        {{Enemy|name=Goblin|level=5}}
    """

    # Legacy template name -> Active template name mappings
    #
    # These templates exist on old wiki pages but should be replaced with
    # their modern equivalents.
    LEGACY_MAPPINGS: ClassVar[dict[str, str]] = {
        # Character templates -> Enemy
        "Character": "Enemy",
        "Pet": "Enemy",
        # Item type templates -> Item
        "Consumable": "Item",
        "Weapon": "Item",  # Non-stat info (source, vendors, etc.)
        "Armor": "Item",  # Non-stat info (source, vendors, etc.)
        "Auras": "Item",
        # Note: {{Mold}} and {{Ability Books}} should eventually
        # be replaced # by {{Item}} as well but need some changes
        # in the wiki templates # before they can be migrated.
    }

    # Templates to remove entirely (no replacement)
    #
    # These templates are deprecated and should be removed from wiki pages.
    TEMPLATES_TO_REMOVE: ClassVar[Sequence[str]] = [
        "Enemy Stats",
    ]

    def __init__(self) -> None:
        """Initialize legacy template remover."""
        self.parser = TemplateParser()
        logger.debug("LegacyTemplateRemover initialized")

    def remove_legacy_templates(self, wikitext: str) -> str:
        """Remove or replace all legacy templates in wikitext.

        This method processes wikitext and:
        1. Replaces legacy template names with active equivalents
        2. Removes deprecated templates entirely
        3. Preserves all template parameters
        4. Leaves active templates unchanged

        Args:
            wikitext: MediaWiki wikitext to process.

        Returns:
            Updated wikitext with legacy templates removed/replaced.

        Example:
            >>> remover = LegacyTemplateRemover()
            >>> # Multiple templates on same page
            >>> wikitext = "{{Character|name=Goblin}} and {{Consumable|name=Potion}}"
            >>> result = remover.remove_legacy_templates(wikitext)
            >>> print(result)
            {{Enemy|name=Goblin}} and {{Item|name=Potion}}

            >>> # Template to remove
            >>> wikitext = "{{Enemy Stats|hp=100}}"
            >>> result = remover.remove_legacy_templates(wikitext)
            >>> print(result)
            <empty>
        """
        if not wikitext or not wikitext.strip():
            logger.debug("Empty wikitext, nothing to process")
            return wikitext

        logger.info("Processing wikitext for legacy templates")

        # Parse wikitext into AST
        code = self.parser.parse(wikitext)

        # Track transformations for logging
        replacements_count = 0
        removals_count = 0

        # Process templates to remove first (before replacements)
        if self.TEMPLATES_TO_REMOVE:
            templates_to_remove = self.parser.find_templates(code, list(self.TEMPLATES_TO_REMOVE))
            for template in templates_to_remove:
                logger.info(f"Removing deprecated template: {{{{{str(template.name).strip()}}}}}")
                self.parser.remove_template(code, template)
                removals_count += 1

        # Process legacy template replacements
        for legacy_name, active_name in self.LEGACY_MAPPINGS.items():
            # Find all instances of this legacy template
            legacy_templates = self.parser.find_templates(code, [legacy_name])

            if not legacy_templates:
                continue

            logger.info(f"Found {len(legacy_templates)} instances of legacy template {{{{{legacy_name}}}}}")

            for template in legacy_templates:
                # Get all parameters
                params = self.parser.get_params(template)

                # Generate new template with same parameters
                new_template_str = self.parser.generate_template(active_name, params)

                # Replace old template with new one
                self.parser.replace_template(code, template, new_template_str)

                logger.debug(f"Replaced {{{{{legacy_name}}}}} -> {{{{{active_name}}}}}")
                replacements_count += 1

        # Render back to wikitext
        result = self.parser.render(code)

        # Log summary
        if replacements_count > 0 or removals_count > 0:
            logger.info(f"Legacy template migration complete: {replacements_count} replaced, {removals_count} removed")
        else:
            logger.debug("No legacy templates found")

        return result

    def has_legacy_templates(self, wikitext: str) -> bool:
        """Check if wikitext contains any legacy templates.

        This method is useful for determining if a page needs migration
        before performing the actual replacement.

        Args:
            wikitext: MediaWiki wikitext to check.

        Returns:
            True if wikitext contains legacy templates, False otherwise.

        Example:
            >>> remover = LegacyTemplateRemover()
            >>> wikitext = "{{Character|name=Goblin}}"
            >>> remover.has_legacy_templates(wikitext)
            True

            >>> wikitext = "{{Enemy|name=Goblin}}"
            >>> remover.has_legacy_templates(wikitext)
            False
        """
        if not wikitext or not wikitext.strip():
            return False

        code = self.parser.parse(wikitext)

        # Check for templates to remove
        if self.TEMPLATES_TO_REMOVE:
            templates_to_remove = self.parser.find_templates(code, list(self.TEMPLATES_TO_REMOVE))
            if templates_to_remove:
                return True

        # Check for legacy template mappings
        for legacy_name in self.LEGACY_MAPPINGS:
            legacy_templates = self.parser.find_templates(code, [legacy_name])
            if legacy_templates:
                return True

        return False

    def get_legacy_template_summary(self, wikitext: str) -> dict[str, int]:
        """Get summary of legacy templates found in wikitext.

        Returns a dictionary mapping template names to counts, useful for
        reporting and diagnostics.

        Args:
            wikitext: MediaWiki wikitext to analyze.

        Returns:
            Dictionary mapping template names to occurrence counts.

        Example:
            >>> remover = LegacyTemplateRemover()
            >>> wikitext = "{{Character|name=Goblin}} {{Consumable|name=Potion}}"
            >>> summary = remover.get_legacy_template_summary(wikitext)
            >>> print(summary)
            {'Character': 1, 'Consumable': 1}
        """
        if not wikitext or not wikitext.strip():
            return {}

        code = self.parser.parse(wikitext)
        summary: dict[str, int] = {}

        # Count templates to remove
        if self.TEMPLATES_TO_REMOVE:
            for template_name in self.TEMPLATES_TO_REMOVE:
                templates = self.parser.find_templates(code, [template_name])
                if templates:
                    summary[template_name] = len(templates)

        # Count legacy template mappings
        for legacy_name in self.LEGACY_MAPPINGS:
            legacy_templates = self.parser.find_templates(code, [legacy_name])
            if legacy_templates:
                summary[legacy_name] = len(legacy_templates)

        return summary

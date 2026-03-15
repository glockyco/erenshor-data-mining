"""Field preservation system for wiki template regeneration.

This module provides a system to preserve manually-edited fields when regenerating
wiki pages from database content. It allows selective field preservation based on
template-specific rules.

Core concept: When regenerating wiki pages, some template fields should keep their
existing values rather than being overwritten with fresh database values.

Design principles (from Phase 3 feedback):
- Keep it simple: 5 handlers (override, preserve, prefer_manual, prefer_database, custom)
- Template-specific rules
- Default behavior is override (always use new database value)
- Configuration via Python dict (easy to migrate to TOML later)

Handlers:
- override: Always use new database value (default)
- preserve: Always keep existing wiki value
- prefer_manual: Use wiki value if non-empty, else database value
- prefer_database: Use database value if non-empty, else wiki value
- custom: Register your own handler function

Example:
    >>> config = FieldPreservationConfig()
    >>> handler = FieldPreservationHandler(config)
    >>>
    >>> # Old page has manual description, new page has database description
    >>> old_fields = {"description": "Custom lore text", "damage": "10"}
    >>> new_fields = {"description": "Generic item", "damage": "15"}
    >>>
    >>> # Apply preservation rules
    >>> result = handler.apply_preservation("Item", old_fields, new_fields)
    >>> print(result)
    {'description': 'Custom lore text', 'damage': '15'}  # description preserved, damage updated

Usage in page generators:
    >>> parser = TemplateParser()
    >>> handler = FieldPreservationHandler()
    >>>
    >>> # Generate new page content
    >>> new_wikitext = generate_item_page(item)
    >>>
    >>> # If old page exists, preserve fields
    >>> if old_wikitext:
    >>>     preserved = handler.merge_templates(
    >>>         old_wikitext=old_wikitext,
    >>>         new_wikitext=new_wikitext,
    >>>         template_names=["Item"]
    >>>     )
    >>>     final_wikitext = preserved
    >>> else:
    >>>     final_wikitext = new_wikitext
"""

from collections.abc import Callable, Mapping
from typing import Any

from loguru import logger

from erenshor.infrastructure.wiki.template_parser import TemplateParser

# Type alias for handler functions
# Signature: (old_value: str, new_value: str, context: dict[str, Any]) -> str
PreservationHandler = Callable[[str, str, dict[str, Any]], str]


class FieldPreservationError(Exception):
    """Base exception for field preservation errors."""

    pass


class HandlerNotFoundError(FieldPreservationError):
    """Raised when a handler name is not registered."""

    pass


class InvalidRuleError(FieldPreservationError):
    """Raised when preservation rule is invalid."""

    pass


# Built-in handlers
def override_handler(old_value: str, new_value: str, context: dict[str, Any]) -> str:
    """Always use new database value (default behavior).

    Args:
        old_value: Existing wiki field value (ignored)
        new_value: New database value
        context: Additional context (unused)

    Returns:
        New value
    """
    return new_value


def preserve_handler(old_value: str, new_value: str, context: dict[str, Any]) -> str:
    """Always keep existing wiki value.

    Args:
        old_value: Existing wiki field value
        new_value: New database value (ignored)
        context: Additional context (unused)

    Returns:
        Old value
    """
    return old_value


def prefer_manual_handler(old_value: str, new_value: str, context: dict[str, Any]) -> str:
    """Keep wiki value if non-empty, else use database value.

    This is useful for fields that editors might add manually but that
    also have default values from the database.

    Args:
        old_value: Existing wiki field value
        new_value: New database value
        context: Additional context (unused)

    Returns:
        Old value if non-empty, else new value
    """
    return old_value if old_value and old_value.strip() else new_value


def prefer_database_handler(old_value: str, new_value: str, context: dict[str, Any]) -> str:
    """Use database value if non-empty, else keep wiki value.

    This is the inverse of prefer_manual. It's useful for fields that should
    normally be generated from the database, but if database doesn't have data,
    we should preserve whatever is in the wiki (could be manual or from previous export).

    Args:
        old_value: Existing wiki field value
        new_value: New database value
        context: Additional context (unused)

    Returns:
        New value if non-empty, else old value
    """
    return new_value if new_value and new_value.strip() else old_value


def merge_handler(old_value: str, new_value: str, context: dict[str, Any]) -> str:
    """Merge old and new values, combining both.

    Useful for fields where both manual wiki content and database content should coexist.
    For <br>-separated lists, deduplicates entries while preserving order.
    For comma-separated lists, merges and deduplicates.

    Args:
        old_value: Existing wiki field value
        new_value: New database value
        context: Additional context (unused)

    Returns:
        Merged value with deduplicated entries
    """
    if not old_value or not old_value.strip():
        return new_value
    if not new_value or not new_value.strip():
        return old_value

    # Determine separator to use:
    # - Use <br> if either value has <br>
    # - Use comma only if BOTH values have commas AND neither has <br> AND we don't detect {{!}} (QuestLink pipe)
    # - The {{!}} pattern indicates a QuestLink with display name override, which may contain commas
    has_br = "<br>" in old_value or "<br>" in new_value
    has_comma_in_old = "," in old_value
    has_comma_in_new = "," in new_value
    # Check if this looks like a QuestLink with display name (which may contain commas internally)
    has_questlink_pipe = "{{!}}" in old_value or "{{!}}" in new_value

    # Choose separator
    if has_br:
        # If either has <br>, use <br>
        separator = "<br>"
        old_items = (
            [item.strip() for item in old_value.split("<br>") if item.strip()]
            if "<br>" in old_value
            else ([old_value.strip()] if old_value.strip() else [])
        )
        new_items = (
            [item.strip() for item in new_value.split("<br>") if item.strip()]
            if "<br>" in new_value
            else ([new_value.strip()] if new_value.strip() else [])
        )
    elif (has_comma_in_old or has_comma_in_new) and not has_questlink_pipe:
        # At least one has commas and no QuestLink pipes - likely comma-separated list like type field
        # Use comma separator and split both on comma (treating single items as 1-item lists)
        separator = ", "
        old_items = (
            [item.strip() for item in old_value.split(",") if item.strip()]
            if "," in old_value
            else ([old_value.strip()] if old_value.strip() else [])
        )
        new_items = (
            [item.strip() for item in new_value.split(",") if item.strip()]
            if "," in new_value
            else ([new_value.strip()] if new_value.strip() else [])
        )
    else:
        # Default to <br> (single values or QuestLink with comma in display name)
        separator = "<br>"
        old_items = [old_value.strip()] if old_value.strip() else []
        new_items = [new_value.strip()] if new_value.strip() else []

    # Deduplicate while preserving order (old items first, then new items not in old)
    seen = set()
    merged = []
    for item in old_items + new_items:
        if item not in seen:
            seen.add(item)
            merged.append(item)

    return separator.join(merged)


# Default preservation rules per template
DEFAULT_PRESERVATION_RULES: dict[str, dict[str, str]] = {
    "Item": {
        # Manual content that editors add
        "image": "prefer_manual",  # Custom images
        "imagecaption": "prefer_manual",  # Custom captions
        "othersource": "preserve",  # Manually-added sources that don't fit other categories
        # Fields that benefit from merging manual and database values
        "type": "merge",  # Combine manual types with database types
        "questsource": "merge",  # Combine manual quest sources with database quest sources
        "relatedquest": "merge",  # Combine manual related quests with database related quests
        # All other fields (including vendorsource, source, etc.) use "override" (default)
        # Most source fields are auto-generated from database, not manually researched
    },
    # Fancy-* templates: All fields use default "override" behavior
    # No manual content - everything comes from database
    "Fancy-weapon": {},
    "Fancy-armor": {},
    "Fancy-charm": {},
    "Character": {
        # Manual edit fields only
        "imagecaption": "preserve",  # Custom image captions
        "type": "prefer_manual",  # NPC/Enemy/Boss classification (some manual, some DB)
        # Location fields - prefer database but fallback to wiki if DB has no data
        "zones": "prefer_database",  # From coordinate (non-prefab), spawn point (prefab) or manual (fallback)
        "coordinates": "prefer_database",  # From coordinate (non-prefab), spawn point (prefab) or manual (fallback)
        "respawn": "prefer_database",  # From spawn point (prefab) or manual (fallback)
        # All other fields implicitly use "override" (default)
    },
    "Ability": {
        "image": "prefer_manual",  # Custom ability icons
    },
    "Zone": {
        # Manually uploaded assets
        "image": "prefer_manual",
        "imagecaption": "prefer_manual",
        # Filled once by editors, intentionally blank in generated output
        "level": "prefer_manual",
        # type, maplink, connects → default "override" (generated from DB)
    },
}


class FieldPreservationConfig:
    """Configuration for field preservation rules.

    Manages template-specific preservation rules and handler registry.
    Provides lookup and validation for preservation rules.

    Example:
        >>> config = FieldPreservationConfig()
        >>> rule = config.get_rule("Item", "description")
        >>> print(rule)
        'preserve'
    """

    def __init__(
        self,
        rules: dict[str, dict[str, str]] | None = None,
        handlers: dict[str, PreservationHandler] | None = None,
    ) -> None:
        """Initialize field preservation configuration.

        Args:
            rules: Template-specific preservation rules (defaults to DEFAULT_PRESERVATION_RULES)
            handlers: Custom handler registry (defaults to built-in handlers only)
        """
        self._rules = rules if rules is not None else DEFAULT_PRESERVATION_RULES.copy()
        self._handlers: dict[str, PreservationHandler] = {
            "override": override_handler,
            "preserve": preserve_handler,
            "prefer_manual": prefer_manual_handler,
            "prefer_database": prefer_database_handler,
            "merge": merge_handler,
        }
        if handlers:
            self._handlers.update(handlers)

        logger.debug(f"Initialized preservation config with {len(self._rules)} template rules")

    def get_rule(self, template_name: str, field_name: str) -> str:
        """Get preservation rule for a specific template field.

        Args:
            template_name: Template name (e.g., "Item", "Fancy-weapon")
            field_name: Field name (e.g., "description", "damage")

        Returns:
            Handler name (e.g., "preserve", "override", "prefer_manual")
            Defaults to "override" if no specific rule exists.
        """
        template_rules = self._rules.get(template_name, {})
        rule = template_rules.get(field_name, "override")
        logger.debug(f"Rule for {template_name}.{field_name}: {rule}")
        return rule

    def get_handler(self, handler_name: str) -> PreservationHandler:
        """Get handler function by name.

        Args:
            handler_name: Handler name (e.g., "preserve", "override")

        Returns:
            Handler function

        Raises:
            HandlerNotFoundError: If handler name is not registered
        """
        if handler_name not in self._handlers:
            raise HandlerNotFoundError(
                f"Handler not found: {handler_name}. Available handlers: {', '.join(self._handlers.keys())}"
            )
        return self._handlers[handler_name]

    def register_handler(self, name: str, handler: PreservationHandler) -> None:
        """Register a custom handler function.

        Args:
            name: Handler name for use in rules
            handler: Handler function with signature (old, new, context) -> str

        Example:
            >>> def custom_handler(old, new, ctx):
            ...     return f"{old} + {new}"
            >>> config.register_handler("concat", custom_handler)
        """
        self._handlers[name] = handler
        logger.debug(f"Registered custom handler: {name}")

    def add_rule(self, template_name: str, field_name: str, handler_name: str) -> None:
        """Add or update a preservation rule.

        Args:
            template_name: Template name
            field_name: Field name
            handler_name: Handler name

        Raises:
            HandlerNotFoundError: If handler name is not registered
        """
        # Validate handler exists
        self.get_handler(handler_name)

        if template_name not in self._rules:
            self._rules[template_name] = {}

        self._rules[template_name][field_name] = handler_name
        logger.debug(f"Added rule: {template_name}.{field_name} = {handler_name}")

    def get_template_rules(self, template_name: str) -> dict[str, str]:
        """Get all preservation rules for a template.

        Args:
            template_name: Template name

        Returns:
            Dictionary mapping field names to handler names
        """
        return self._rules.get(template_name, {}).copy()


class FieldPreservationHandler:
    """Handler for applying field preservation rules to templates.

    Uses FieldPreservationConfig to determine which fields to preserve when
    merging old wiki content with new database content.

    Example:
        >>> handler = FieldPreservationHandler()
        >>> old = {"description": "Manual text", "damage": "10"}
        >>> new = {"description": "Database text", "damage": "15"}
        >>> result = handler.apply_preservation("Item", old, new)
        >>> print(result)
        {'description': 'Manual text', 'damage': '15'}
    """

    def __init__(self, config: FieldPreservationConfig | None = None) -> None:
        """Initialize field preservation handler.

        Args:
            config: Preservation configuration (defaults to new instance with default rules)
        """
        self._config = config if config is not None else FieldPreservationConfig()
        self._parser = TemplateParser()
        logger.debug("Initialized field preservation handler")

    def apply_preservation(
        self,
        template_name: str,
        old_fields: Mapping[str, str],
        new_fields: Mapping[str, str],
        context: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        """Apply preservation rules to merge old and new field values.

        Args:
            template_name: Template name (e.g., "Item", "Fancy-weapon")
            old_fields: Existing wiki field values
            new_fields: New database field values
            context: Additional context passed to handlers

        Returns:
            Merged field dictionary with preservation rules applied

        Example:
            >>> handler = FieldPreservationHandler()
            >>> old = {"description": "Custom", "damage": "10"}
            >>> new = {"description": "Default", "damage": "15", "level": "5"}
            >>> result = handler.apply_preservation("Item", old, new)
            >>> # description preserved, damage updated, level added
            >>> print(result)
            {'description': 'Custom', 'damage': '15', 'level': '5'}
        """
        ctx = context if context is not None else {}
        ctx["template_name"] = template_name

        result: dict[str, str] = {}

        # Get all field names from both old and new
        all_fields = set(old_fields.keys()) | set(new_fields.keys())

        logger.debug(f"Applying preservation for {template_name}: {len(all_fields)} fields")

        for field_name in all_fields:
            old_value = old_fields.get(field_name, "")
            new_value = new_fields.get(field_name, "")

            # Get preservation rule for this field
            rule_name = self._config.get_rule(template_name, field_name)
            handler = self._config.get_handler(rule_name)

            # Apply handler
            result[field_name] = handler(old_value, new_value, ctx)

            if old_value != result[field_name]:
                logger.debug(f"  {field_name}: '{old_value}' -> '{result[field_name]}' (rule: {rule_name})")

        return result

    def merge_templates(
        self,
        old_wikitext: str,
        new_wikitext: str,
        template_names: list[str],
        context: dict[str, Any] | None = None,
    ) -> str:
        """Merge new templates into existing page, preserving all manual content.

        This method starts with old_wikitext (which has templates + manual content) and
        updates only the specified templates in place. Everything else (manual sections,
        categories, etc.) is preserved.

        Args:
            old_wikitext: Existing wiki page (templates + manual content)
            new_wikitext: Freshly generated templates (just templates, no manual content)
            template_names: List of template names to merge (e.g., ["Item"])
            context: Additional context passed to handlers

        Returns:
            Old wikitext with templates updated, all manual content preserved

        Example:
            >>> handler = FieldPreservationHandler()
            >>> old = "{{Item|description=Manual|damage=10}}\\n\\n== Notes ==\\nManual content."
            >>> new = "{{Item|description=Auto|damage=15|level=5}}"
            >>> result = handler.merge_templates(old, new, ["Item"])
            >>> # Result: Updated Item template + preserved Notes section
        """
        logger.debug(f"Merging {len(template_names)} templates into existing page")

        # Parse old page (contains everything: templates + manual content)
        old_code = self._parser.parse(old_wikitext)

        # Parse new templates to extract their content
        new_code = self._parser.parse(new_wikitext)
        new_templates_found = self._parser.find_templates(new_code, template_names)

        if not new_templates_found:
            logger.debug("No new templates found, returning old wikitext as-is")
            return old_wikitext

        # Build list of new templates grouped by template name
        new_template_map: dict[str, list[Any]] = {}
        for tmpl in new_templates_found:
            tmpl_name = str(tmpl.name).strip()
            if tmpl_name in template_names:
                if tmpl_name not in new_template_map:
                    new_template_map[tmpl_name] = []
                new_template_map[tmpl_name].append(tmpl)

        # For each template type, merge fields
        for template_name in template_names:
            # Find templates in old page
            old_templates = self._parser.find_templates(old_code, [template_name])

            # Get new templates for this name
            new_tmpls = new_template_map.get(template_name, [])
            if not new_tmpls:
                logger.debug(f"No new templates for {template_name}, skipping")
                continue

            if not old_templates:
                # Templates don't exist in old page, append all to end
                logger.debug(
                    f"Template {template_name} not found in old page, appending {len(new_tmpls)} new templates"
                )

                for new_tmpl in new_tmpls:
                    # Extract fields from new template
                    new_fields = self._parser.get_params(new_tmpl)

                    # Generate formatted template
                    formatted_template = self._parser.generate_template(
                        template_name,
                        new_fields,
                        inline=False,
                    )

                    old_code.append(f"\n\n{formatted_template}")
                continue

            # Match old and new templates by position (order in which they appear)
            # Process pairs in order: (old[0], new[0]), (old[1], new[1]), etc.
            for i, new_tmpl in enumerate(new_tmpls):
                new_fields = self._parser.get_params(new_tmpl)

                if i < len(old_templates):
                    # Have matching old template at same position, merge fields
                    old_tmpl = old_templates[i]
                    old_fields = self._parser.get_params(old_tmpl)

                    # Apply preservation rules
                    preserved_fields = self.apply_preservation(template_name, old_fields, new_fields, context)

                    # Preserve field order from new template (from Jinja2 template order)
                    ordered_preserved = {k: preserved_fields[k] for k in new_fields if k in preserved_fields}

                    # Generate properly formatted template from merged fields
                    formatted_template = self._parser.generate_template(
                        template_name,
                        ordered_preserved,
                        inline=False,  # Multi-line format
                    )

                    # Replace template in old_code (preserving everything else)
                    self._parser.replace_template(old_code, old_tmpl, formatted_template)
                else:
                    # More new templates than old, append extras to end
                    logger.debug(f"Extra new template {template_name} at position {i}, appending")
                    formatted_template = self._parser.generate_template(
                        template_name,
                        new_fields,
                        inline=False,
                    )
                    old_code.append(f"\n\n{formatted_template}")

        # Render modified old page (templates updated, manual content preserved)
        result = self._parser.render(old_code)
        logger.debug(f"Merged templates into existing page successfully ({len(result)} characters)")
        return result

    def get_config(self) -> FieldPreservationConfig:
        """Get the preservation configuration.

        Returns:
            Current FieldPreservationConfig instance
        """
        return self._config

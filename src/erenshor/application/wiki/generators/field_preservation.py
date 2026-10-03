"""Field preservation for wiki template regeneration.

Regeneration merges freshly generated template fields into the live page. Each
template field has a rule that decides between the live value and the generated
value. Fields without a rule take the generated value.

Handlers:
- override: use the generated value (default)
- preserve: keep the live value
- prefer_manual: keep the live value when it is not blank, else use the generated value
- prefer_database: use the generated value when it is not blank, else keep the live value
- merge: merge a list field by link target (see :class:`LinkListMerge`)

Example:
    >>> handler = FieldPreservationHandler()
    >>> old_fields = {"imagecaption": "Custom caption", "level": "10"}
    >>> new_fields = {"imagecaption": "", "level": "15"}
    >>> handler.apply_preservation("Character", old_fields, new_fields)
    {'imagecaption': 'Custom caption', 'level': '15'}
"""

from collections.abc import Callable, Mapping
from types import MappingProxyType
from typing import Any

import mwparserfromhell
from loguru import logger
from mwparserfromhell.nodes import Tag, Text

from erenshor.application.wiki_deploy.link_audit import LinkTargets
from erenshor.infrastructure.wiki.template_parser import TemplateParser

# Type alias for handler functions
# Signature: (old_value: str, new_value: str, context: dict[str, Any]) -> str
PreservationHandler = Callable[[str, str, dict[str, Any]], str]

# Separator of each list field that the merge rule handles. A comma list also
# splits at top-level commas, so that live values in either style merge.
LIST_SEPARATORS: Mapping[str, str] = MappingProxyType(
    {
        "type": ", ",
        "questsource": "<br>",
        "relatedquest": "<br>",
    }
)


class FieldPreservationError(Exception):
    """Base exception for field preservation errors."""

    pass


class HandlerNotFoundError(FieldPreservationError):
    """Raised when a handler name is not registered."""

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


def list_entries(value: str, separator: str) -> list[str]:
    """Split a list field into its entries.

    Entries are separated by top-level ``<br>`` tags. A comma list also splits
    at top-level commas. Separators inside templates and links do not split.
    """
    split_at_commas = separator == ", "
    entries: list[str] = []
    current: list[str] = []
    for node in mwparserfromhell.parse(value).nodes:
        if isinstance(node, Tag) and str(node.tag).strip().casefold() == "br":
            entries.append("".join(current))
            current = []
        elif split_at_commas and isinstance(node, Text) and "," in node.value:
            head, *tail = node.value.split(",")
            current.append(head)
            for part in tail:
                entries.append("".join(current))
                current = [part]
        else:
            current.append(str(node))
    entries.append("".join(current))
    return [entry.strip() for entry in entries if entry.strip()]


class LinkListMerge:
    """Merge a live list field with its generated value by link target.

    Each entry is identified by the page that it links, or by its text when it
    is not a link. The result keeps the live order. The generated entries that
    link a page take the place of the first live entry that links the same page,
    and later live entries for that page are dropped. Live entries for other
    pages and live text stay. Generated entries without a live counterpart
    follow at the end. The result uses the separator of the field.
    """

    def __init__(self, link_targets: LinkTargets) -> None:
        self._link_targets = link_targets

    def identity(self, entry: str) -> tuple[str, str]:
        """Return the page that ``entry`` links, or its whitespace-normalized text."""
        target = self._link_targets.target(entry)
        return ("link", target) if target is not None else ("text", " ".join(entry.split()))

    def __call__(self, old_value: str, new_value: str, context: dict[str, Any]) -> str:
        if not old_value.strip():
            return new_value
        if not new_value.strip():
            return old_value
        separator = LIST_SEPARATORS[context["field_name"]]
        generated: dict[tuple[str, str], list[str]] = {}
        for entry in list_entries(new_value, separator):
            group = generated.setdefault(self.identity(entry), [])
            if entry not in group:
                group.append(entry)
        merged: list[str] = []
        placed: set[tuple[str, str]] = set()
        for entry in list_entries(old_value, separator):
            identity = self.identity(entry)
            if identity in generated:
                if identity not in placed:
                    merged.extend(generated[identity])
                    placed.add(identity)
            elif entry not in merged:
                merged.append(entry)
        for identity, group in generated.items():
            if identity not in placed:
                merged.extend(group)
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
        "type": "override",  # Classification comes from the clean database
        # Location fields - prefer database but fallback to wiki if DB has no data
        "zones": "prefer_database",  # From coordinate (non-prefab), spawn point (prefab) or manual (fallback)
        "coordinates": "prefer_database",  # From coordinate (non-prefab), spawn point (prefab) or manual (fallback)
        "location": "preserve",  # Editor-written landmark description, never sourced from the export
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
        # prefer_manual: the wiki's Dungeon/Zone classification is kept;
        # wikilink values are normalised to plain text before merge reaches here.
        "type": "prefer_manual",
        # maplink, connects → default "override" (generated from DB)
    },
}


class FieldPreservationConfig:
    """Configuration for field preservation rules.

    Manages template-specific preservation rules and handler registry.
    Provides lookup and validation for preservation rules.

    Example:
        >>> config = FieldPreservationConfig()
        >>> config.get_rule("Item", "othersource")
        'preserve'
    """

    def __init__(
        self,
        rules: dict[str, dict[str, str]] | None = None,
        handlers: dict[str, PreservationHandler] | None = None,
        *,
        link_targets: LinkTargets | None = None,
    ) -> None:
        """Initialize field preservation configuration.

        Args:
            rules: Template-specific preservation rules (defaults to DEFAULT_PRESERVATION_RULES)
            handlers: Custom handler registry (defaults to built-in handlers only)
            link_targets: Link catalog resolver. The ``merge`` rule exists only with it,
                because list entries merge by the page that they link.
        """
        self._rules = rules if rules is not None else DEFAULT_PRESERVATION_RULES.copy()
        self._handlers: dict[str, PreservationHandler] = {
            "override": override_handler,
            "preserve": preserve_handler,
            "prefer_manual": prefer_manual_handler,
            "prefer_database": prefer_database_handler,
        }
        if link_targets is not None:
            self._handlers["merge"] = LinkListMerge(link_targets)
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
            if handler_name == "merge":
                raise HandlerNotFoundError("The merge handler needs link targets: pass link_targets to the config")
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
        >>> old = {"othersource": "Manual text", "buy": "10"}
        >>> new = {"othersource": "", "buy": "15"}
        >>> handler.apply_preservation("Item", old, new)
        {'othersource': 'Manual text', 'buy': '15'}
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
            context: Additional context passed to handlers. Each handler also
                receives ``template_name`` and ``field_name``.

        Returns:
            Merged field dictionary with preservation rules applied, in the
            order of the new fields followed by fields only the old template has

        Example:
            >>> handler = FieldPreservationHandler()
            >>> old = {"othersource": "Custom", "buy": "10"}
            >>> new = {"othersource": "", "buy": "15", "sell": "5"}
            >>> handler.apply_preservation("Item", old, new)
            {'othersource': 'Custom', 'buy': '15', 'sell': '5'}
        """
        ctx = context if context is not None else {}
        ctx["template_name"] = template_name

        result: dict[str, str] = {}
        all_fields = [*new_fields, *(field for field in old_fields if field not in new_fields)]

        logger.debug(f"Applying preservation for {template_name}: {len(all_fields)} fields")

        for field_name in all_fields:
            old_value = old_fields.get(field_name, "")
            new_value = new_fields.get(field_name, "")

            rule_name = self._config.get_rule(template_name, field_name)
            handler = self._config.get_handler(rule_name)
            ctx["field_name"] = field_name
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

            # Generated templates have authoritative cardinality. If entities
            # split or disappear, retaining unmatched old templates silently
            # keeps stale generated records on the page.
            for stale_tmpl in old_templates[len(new_tmpls) :]:
                logger.debug(f"Removing stale {template_name} template")
                self._parser.remove_template(old_code, stale_tmpl)

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

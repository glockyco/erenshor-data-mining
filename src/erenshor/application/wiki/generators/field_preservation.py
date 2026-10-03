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

import math
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from itertools import permutations
from types import MappingProxyType
from typing import Any

import mwparserfromhell
from loguru import logger
from mwparserfromhell.nodes import Node, Tag, Template, Text
from mwparserfromhell.wikicode import Wikicode

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

# Field that names the entity of each root template. Live roots without a
# stable key match generated roots by this name.
ROOT_NAME_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        "Item": "title",
        "Character": "name",
        "Ability": "title",
        "Stance": "title",
        "Zone": "title",
    }
)


class FieldPreservationError(Exception):
    """Base exception for field preservation errors."""


class HandlerNotFoundError(FieldPreservationError):
    """Raised when a handler name is not registered."""


class AmbiguousRootsError(FieldPreservationError):
    """Raised when live root templates cannot be matched to generated roots safely."""


@dataclass(frozen=True)
class TemplateMerge:
    """A live page with generated root templates merged into it.

    Attributes:
        text: The merged page text.
        kept_roots: Live roots that match no generated root, as
            ``"<template>: <name>"``. They stay unchanged for a human to review.
    """

    text: str
    kept_roots: tuple[str, ...]


# Companion templates that belong to the root before them. Generation owns
# them: a merged root takes the companions of its generated root.
ROOT_COMPANIONS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "Item": frozenset(
            {
                "ItemTooltip",
                "Item/Aura",
                "Item/Charm",
                "Item/Consumable",
                "Item/General",
                "Item/Mold",
                "Item/SkillBook",
                "Item/SpellScroll",
            }
        ),
        "Character": frozenset(),
        "Ability": frozenset({"SpellTooltip", "SkillTooltip"}),
        "Stance": frozenset({"StanceTooltip"}),
        "Zone": frozenset(),
    }
)


@dataclass(frozen=True)
class _RootBlock:
    """A top-level root template and the companions that follow it."""

    root: Template
    companions: tuple[Template, ...]


def _root_blocks(code: Wikicode, template_name: str) -> list[_RootBlock]:
    """Return the top-level roots of one template with their companions.

    A companion belongs to the nearest root of its template before it, even
    when prose stands between them or editor markup such as a table holds the
    companion. Companions before the first root belong to no block.
    """
    companion_names = ROOT_COMPANIONS[template_name]
    top_level = {id(node) for node in code.nodes}
    roots: list[Template] = []
    companions: dict[int, list[Template]] = {}
    for template in code.filter_templates():
        name = str(template.name).strip()
        if name == template_name and id(template) in top_level:
            roots.append(template)
            companions[id(template)] = []
        elif name in companion_names and roots:
            companions[id(roots[-1])].append(template)
    return [_RootBlock(root, tuple(companions[id(root)])) for root in roots]


def _block_end(code: Wikicode, block: _RootBlock) -> Node:
    """Return the top-level node that ends a block: its last companion, or the markup that holds it."""
    if not block.companions:
        return block.root
    last = block.companions[-1]
    return last if any(node is last for node in code.nodes) else code.get_ancestors(last)[0]


def _companions_text(block: _RootBlock) -> str:
    """Return the companions of a block as text that follows its root, or an empty string."""
    return "".join(f"\n{companion}" for companion in block.companions)


def _param(template: Template, name: str) -> str | None:
    """Return the stripped value of a template parameter, or None when it is blank or absent."""
    if not template.has(name):
        return None
    value = str(template.get(name).value).strip()
    return value or None


def _root_label(template: Template, template_name: str) -> str:
    """Return the entity name that a root template shows, for messages."""
    return _param(template, ROOT_NAME_FIELDS[template_name]) or "(unnamed)"


def _root_name_key(template: Template, template_name: str) -> str:
    """Return the name of a root template, normalized for matching."""
    return " ".join((_param(template, ROOT_NAME_FIELDS[template_name]) or "").split()).casefold()


# Same-name roots pair by trying every pairing. Groups that need more pairings
# than this fail and need stable keys by hand.
_MAX_SAME_NAME_PAIRINGS = 40_320


def _agreeing_fields(old_fields: Mapping[str, str], new_fields: Mapping[str, str]) -> int:
    """Count the generated fields whose live value is the same and not blank."""
    return sum(
        1
        for field, value in new_fields.items()
        if (normalized := " ".join(value.split())) and normalized == " ".join(old_fields.get(field, "").split())
    )


def _largest_pairings(olds: int, news: int) -> Iterator[tuple[tuple[int, int], ...]]:
    """Yield every pairing of ``min(olds, news)`` roots as ``(old index, new index)`` tuples.

    The pairing by position comes first.
    """
    if olds <= news:
        for chosen in permutations(range(news), olds):
            yield tuple(zip(range(olds), chosen, strict=True))
    else:
        for chosen in permutations(range(olds), news):
            yield tuple(zip(chosen, range(news), strict=True))


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
    "Stance": {
        "image": "prefer_manual",  # Custom stance icons
        "imagecaption": "preserve",  # Custom image captions
    },
    "Zone": {
        # Every field but the title belongs to editors once it has a value.
        # Generated values fill new pages and blank fields only. Editors
        # upload images, fill levels, and refine the type to Raid. They also
        # correct the data: they remove zone lines that players cannot reach,
        # add access by teleport, and link the map of each scene of a page.
        "image": "prefer_manual",
        "imagecaption": "prefer_manual",
        "level": "prefer_manual",
        "type": "prefer_manual",
        "maplink": "prefer_manual",
        "connects": "prefer_manual",
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
            template_name: Template name (e.g., "Item", "Character")
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
            template_name: Template name (e.g., "Item", "Character")
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
    ) -> TemplateMerge:
        """Merge generated root templates and their companions into the live page.

        Each generated root replaces the live root of the same entity, with the
        preservation rules applied to their fields. A live root is the same
        entity when it carries the same ``stablekey``. A live root without a key
        is the same entity when its name is the same, because live pages
        predate the keys. Several roots with one name pair so that the most
        field values agree. When several pairings agree equally well and merge
        to different pages, the page fails, because a live value could reach
        the wrong entity.

        A merged root takes the companions of its generated root: they replace
        its first live companion, or follow the root when it has none, and its
        other live companions go. A generated root without a live root follows
        the last live root of its template and that root's companions, or the
        end of the page. A live root that matches no generated root stays
        unchanged with its companions and is reported in ``kept_roots``. Text
        outside roots and companions stays unchanged.

        Raises:
            AmbiguousRootsError: Live roots cannot be matched safely.
        """
        old_code = self._parser.parse(old_wikitext)
        new_code = self._parser.parse(new_wikitext)
        kept_roots: list[str] = []

        for template_name in template_names:
            old_blocks = _root_blocks(old_code, template_name)
            new_blocks = _root_blocks(new_code, template_name)
            pairs = self.match_roots(
                template_name,
                [block.root for block in old_blocks],
                [block.root for block in new_blocks],
                context,
            )
            old_by_root = {id(block.root): block for block in old_blocks}
            new_by_root = {id(block.root): block for block in new_blocks}
            paired_old = {id(old_root) for old_root, _ in pairs}
            paired_new = {id(new_root) for _, new_root in pairs}

            # Insert first: the anchor node may be replaced below.
            added = "".join(
                f"\n\n{self._format_root(template_name, block.root)}{_companions_text(block)}"
                for block in new_blocks
                if id(block.root) not in paired_new
            )
            if added and old_blocks:
                old_code.insert(old_code.index(_block_end(old_code, old_blocks[-1])) + 1, added)
            elif added:
                old_code.append(added)

            for old_root, new_root in pairs:
                old_block, new_block = old_by_root[id(old_root)], new_by_root[id(new_root)]
                merged_root = self._parser.generate_template(
                    template_name,
                    self._merged_fields(
                        template_name,
                        self._parser.get_params(old_root),
                        self._parser.get_params(new_root),
                        context,
                    ),
                    inline=False,
                )
                if old_block.companions:
                    first, *stale = old_block.companions
                    for companion in stale:
                        old_code.replace(companion, "")
                    old_code.replace(first, _companions_text(new_block).removeprefix("\n"))
                    old_code.replace(old_root, merged_root)
                else:
                    old_code.replace(old_root, merged_root + _companions_text(new_block))

            kept_roots.extend(
                f"{template_name}: {_root_label(block.root, template_name)}"
                for block in old_blocks
                if id(block.root) not in paired_old
            )

        return TemplateMerge(text=self._parser.render(old_code), kept_roots=tuple(kept_roots))

    def _format_root(self, template_name: str, root: Template) -> str:
        return self._parser.generate_template(template_name, self._parser.get_params(root), inline=False)

    def _merged_fields(
        self,
        template_name: str,
        old_fields: Mapping[str, str],
        new_fields: Mapping[str, str],
        context: dict[str, Any] | None,
    ) -> dict[str, str]:
        """Return the fields of a merged root: the generated fields after the preservation rules."""
        preserved = self.apply_preservation(template_name, old_fields, new_fields, context)
        return {field: preserved[field] for field in new_fields}

    def match_roots(
        self,
        template_name: str,
        old_roots: Sequence[Template],
        new_roots: Sequence[Template],
        context: dict[str, Any] | None = None,
    ) -> list[tuple[Template, Template]]:
        """Pair live roots with generated roots of one template.

        A live root with a ``stablekey`` pairs with the generated root of that
        key. Live roots without a key pair with generated roots of the same
        name. When several roots share a name, they pair so that the most
        field values agree, because a live root holds the data that an earlier
        generation wrote for its entity.

        Raises:
            AmbiguousRootsError: Two live roots carry one key, or several
                pairings of same-name roots agree equally well and merge to
                different pages.
        """
        old_by_key: dict[str, Template] = {}
        for old_root in old_roots:
            key = _param(old_root, "stablekey")
            if key is None:
                continue
            if key in old_by_key:
                raise AmbiguousRootsError(f"Two live {template_name} roots carry the stable key {key!r}")
            old_by_key[key] = old_root

        pairs: list[tuple[Template, Template]] = []
        unmatched_new: dict[str, list[Template]] = {}
        for new_root in new_roots:
            key = _param(new_root, "stablekey")
            if key is not None and key in old_by_key:
                pairs.append((old_by_key.pop(key), new_root))
            else:
                unmatched_new.setdefault(_root_name_key(new_root, template_name), []).append(new_root)

        unkeyed_old: dict[str, list[Template]] = {}
        for old_root in old_roots:
            if _param(old_root, "stablekey") is None:
                unkeyed_old.setdefault(_root_name_key(old_root, template_name), []).append(old_root)

        for name, news in unmatched_new.items():
            pairs.extend(self._pair_same_name(template_name, unkeyed_old.get(name, []), news, context))
        return pairs

    def _pair_same_name(
        self,
        template_name: str,
        olds: Sequence[Template],
        news: Sequence[Template],
        context: dict[str, Any] | None,
    ) -> list[tuple[Template, Template]]:
        """Pair same-name live and generated roots so that the most field values agree.

        Every pairing of the largest possible size is scored by the number of
        fields whose live and generated values are equal and not blank. When
        several pairings reach the best score, they must merge to the same page.
        """
        if not olds or not news:
            return []
        if len(olds) == 1 and len(news) == 1:
            return [(olds[0], news[0])]
        if math.perm(max(len(olds), len(news)), min(len(olds), len(news))) > _MAX_SAME_NAME_PAIRINGS:
            raise self._ambiguous(template_name, news, "are too many to pair")

        old_fields = [self._parser.get_params(old_root) for old_root in olds]
        new_fields = [self._parser.get_params(new_root) for new_root in news]
        agreement = [[_agreeing_fields(old, new) for new in new_fields] for old in old_fields]
        best_score = -1
        best: list[tuple[tuple[int, int], ...]] = []
        for pairing in _largest_pairings(len(olds), len(news)):
            score = sum(agreement[old][new] for old, new in pairing)
            if score > best_score:
                best_score, best = score, [pairing]
            elif score == best_score:
                best.append(pairing)

        def page(pairing: tuple[tuple[int, int], ...]) -> tuple[object, ...]:
            partner = {new: old for old, new in pairing}
            merged = tuple(
                tuple(self._merged_fields(template_name, old_fields[partner[new]], fields, context).items())
                if new in partner
                else tuple(fields.items())
                for new, fields in enumerate(new_fields)
            )
            kept = tuple(sorted(str(olds[old]) for old in range(len(olds)) if old not in partner.values()))
            return (merged, kept)

        if len({page(pairing) for pairing in best}) > 1:
            raise self._ambiguous(template_name, news, "agree equally well with several entities")
        return [(olds[old], news[new]) for old, new in best[0]]

    @staticmethod
    def _ambiguous(template_name: str, news: Sequence[Template], reason: str) -> AmbiguousRootsError:
        keys = ", ".join(_param(new_root, "stablekey") or "(no key)" for new_root in news)
        return AmbiguousRootsError(
            f"The unkeyed {template_name} roots named {_root_label(news[0], template_name)!r} {reason}. "
            f"Add the right stable key to each live root by hand: {keys}"
        )

    def get_config(self) -> FieldPreservationConfig:
        """Get the preservation configuration.

        Returns:
            Current FieldPreservationConfig instance
        """
        return self._config

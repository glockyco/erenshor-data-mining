"""Item section generator for wiki content.

This module generates MediaWiki template wikitext for individual items including
weapons, armor, consumables, and other item types.

This section generator produces templates for single items. Multi-entity page
assembly is handled by PageGenerator classes.

Template structure:
- General items: {{Item}} template + category tags
- Weapons: {{Item}} + 3x {{Fancy-weapon}} (Normal/Blessed/Godly) + category tags
- Armor: {{Item}} + 3x {{Fancy-armor}} (Normal/Blessed/Godly) + category tags
- Charms: {{Item}} + {{Fancy-charm}} + category tags

Note: This initial implementation generates fresh content without source enrichment
(vendors, drops, quests, crafting). Source enrichment will be added in future tasks.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.formatting import format_description, safe_str
from erenshor.application.wiki.generators.item_type_display import build_item_types
from erenshor.application.wiki.generators.sections.base import SectionGeneratorBase
from erenshor.registry.item_classifier import ItemKind, classify_item_kind
from erenshor.shared.game_constants import LONG_NAME_FONT_SIZE, LONG_NAME_THRESHOLD

if TYPE_CHECKING:
    from erenshor.domain.enriched_data.item import EnrichedItemData
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.item_stats import ItemStats
    from erenshor.registry.resolver import RegistryResolver


class ItemSectionGenerator(SectionGeneratorBase):
    """Generator for item wiki sections.

    Generates template wikitext for a SINGLE item entity with appropriate templates
    and category tags based on item classification.

    Multi-entity page assembly is handled by PageGenerator classes, not here.

    Example:
        >>> resolver = RegistryResolver(...)
        >>> category_generator = CategoryGenerator(resolver)
        >>> generator = ItemSectionGenerator(resolver, category_generator)
        >>> item = Item(...)  # From repository
        >>> wikitext = generator.generate_template(item, page_title="Sword of Truth")
    """

    def __init__(self, resolver: RegistryResolver) -> None:
        """Initialize item section generator.

        Args:
            resolver: Registry resolver for links and display names
        """
        super().__init__()
        self._resolver = resolver

    def generate_template(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate template wikitext for a single item.

        Args:
            enriched: Enriched item data with stats and related data
            page_title: Wiki page title (from registry)

        Returns:
            Template wikitext for single item (infobox + categories)

        Example:
            >>> enriched = item_enricher.enrich(item)
            >>> wikitext = generator.generate_template(enriched, "Sword")
        """
        item = enriched.item

        logger.debug(f"Generating template for item: {item.item_name} (kind: {self._classify(item)})")

        # Classify item to determine templates
        kind = self._classify(item)

        # Generate appropriate templates based on kind
        if kind == ItemKind.WEAPON:
            template_wikitext = self._generate_weapon_page(enriched, page_title)
        elif kind == ItemKind.ARMOR:
            template_wikitext = self._generate_armor_page(enriched, page_title)
        elif kind == ItemKind.CHARM:
            template_wikitext = self._generate_charm_page(enriched, page_title)
        elif kind in (ItemKind.AURA, ItemKind.ABILITY_BOOK, ItemKind.CONSUMABLE, ItemKind.MOLD, ItemKind.GENERAL):
            # All non-weapon/armor/charm items use general template for now
            template_wikitext = self._generate_general_item_page(enriched, page_title)
        else:
            # Fallback (should never reach here due to exhaustive ItemKind)
            template_wikitext = self._generate_general_item_page(enriched, page_title)

        return self.normalize_wikitext(template_wikitext)

    def _classify(self, item: Item) -> ItemKind:
        """Classify item kind.

        Args:
            item: Item entity

        Returns:
            ItemKind classification
        """
        return classify_item_kind(
            required_slot=item.required_slot,
            teach_spell=item.teach_spell_stable_key,
            teach_skill=item.teach_skill_stable_key,
            template_flag=item.template,
            click_effect=item.item_effect_on_click_stable_key,
            disposable=bool(item.disposable),
        )

    def _generate_general_item_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for general items (consumables, molds, ability books, etc).

        Args:
            enriched: Enriched item data
            page_title: Wiki page title
            resolver: Registry resolver for links and overrides

        Returns:
            Wikitext with {{Item}} template
        """
        context = self._build_item_template_context(enriched, page_title)
        return self.render_template("item.jinja2", context)

    def _generate_weapon_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for weapons.

        Generates {{Item}} template for general info plus 3x {{Fancy-weapon}} templates
        (one for each quality tier: Normal/Blessed/Godly) in a wiki table.

        Args:
            enriched: Enriched item data with stats
            page_title: Wiki page title
            resolver: Registry resolver for links and overrides

        Returns:
            Wikitext with {{Item}} template + {{Fancy-weapon}} table

        Raises:
            ValueError: If stats is empty (all weapons must have stats)
        """
        item = enriched.item
        stats = enriched.stats
        if not stats:
            raise ValueError(
                f"Weapon '{item.item_name}' ({item.stable_key}) has no ItemStats - this should NEVER happen!"
            )

        # Generate {{Item}} template (SOURCE FIELDS ONLY for weapons)
        item_context = self._build_weapon_armor_item_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Fancy-weapon}} templates (one per quality tier)
        fancy_templates = [self._build_fancy_weapon(enriched, page_title, stat) for stat in stats]
        fancy_table = self._format_fancy_table(fancy_templates)

        return f"{item_template}\n\n{fancy_table}"

    def _generate_armor_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for armor.

        Generates {{Item}} template for general info plus 3x {{Fancy-armor}} templates
        (one for each quality tier: Normal/Blessed/Godly) in a wiki table.

        Args:
            enriched: Enriched item data with stats
            page_title: Wiki page title
            resolver: Registry resolver for links and overrides

        Returns:
            Wikitext with {{Item}} template + {{Fancy-armor}} table

        Raises:
            ValueError: If stats is empty (all armor must have stats)
        """
        item = enriched.item
        stats = enriched.stats

        if not stats:
            raise ValueError(
                f"Armor '{item.item_name}' ({item.stable_key}) has no ItemStats - this should NEVER happen!"
            )

        # Generate {{Item}} template (SOURCE FIELDS ONLY for armor)
        item_context = self._build_weapon_armor_item_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Fancy-armor}} templates (one per quality tier)
        fancy_templates = [self._build_fancy_armor(enriched, page_title, stat) for stat in stats]
        fancy_table = self._format_fancy_table(fancy_templates)

        return f"{item_template}\n\n{fancy_table}"

    def _generate_charm_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for charms.

        Generates {{Item}} template for source fields plus {{Fancy-charm}} template
        for stat scaling display.

        Args:
            enriched: Enriched item data with stats
            page_title: Wiki page title
            resolver: Registry resolver for links and overrides

        Returns:
            Wikitext with {{Item}} + {{Fancy-charm}} templates
        """
        stats = enriched.stats

        item_context = self._build_weapon_armor_item_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        if stats:
            charm_stat = stats[0]
            charm_context = self._build_fancy_charm(enriched, page_title, charm_stat)
            charm_template = self.render_template("fancy-charm.jinja2", charm_context)
            return f"{item_template}\n\n{charm_template}"
        return item_template

    def _format_item_name_for_fancy_template(self, display_name: str) -> str:
        """Format item name for fancy templates, wrapping long names with font-size span.

        Args:
            display_name: Display name from registry to show

        Returns:
            Display name wrapped in span if name exceeds LONG_NAME_THRESHOLD, otherwise plain display name
        """
        if len(display_name) > LONG_NAME_THRESHOLD:
            return f'<span style="font-size:{LONG_NAME_FONT_SIZE}">{display_name}</span>'
        return display_name

    def _weapon_type_display(self, required_slot: str | None, this_weapon_type: str | None) -> str:
        """Convert weapon slot and type to display format for Fancy templates.

        Args:
            required_slot: Item required slot (e.g., "Primary", "PrimaryOrSecondary", "Secondary")
            this_weapon_type: Weapon type (e.g., "TwoHandMelee", "TwoHandStaff")

        Returns:
            Display string for weapon type (e.g., "Primary", "Primary or Secondary", "Primary - 2-Handed")
        """
        slot = (required_slot if required_slot is not None else "").strip()

        # Convert PrimaryOrSecondary to "Primary or Secondary"
        if slot == "PrimaryOrSecondary":
            slot = "Primary or Secondary"

        # Add 2-Handed suffix for two-handed weapons
        weapon_kind = (this_weapon_type if this_weapon_type is not None else "").strip()
        two_handed = weapon_kind in ("TwoHandMelee", "TwoHandStaff", "TwoHandBow")
        if two_handed:
            slot += " - 2-Handed"

        return slot

    def _build_weapon_armor_item_context(self, enriched: EnrichedItemData, page_title: str) -> dict[str, str]:
        """Build context for {{Item}} template for weapons/armor (SOURCE FIELDS ONLY).

        For weapons and armor, the {{Item}} template should ONLY contain source-related
        fields (vendors, drops, quests, crafting). All stat fields (damage, delay, classes,
        relic, description, etc.) are shown in the {{Fancy-weapon}}/{{Fancy-armor}} templates
        instead, so they should be empty strings in the {{Item}} template.

        This matches the legacy implementation behavior to avoid duplicate information.

        Args:
            enriched: Enriched item data with sources
            page_title: Wiki page title

        Returns:
            Template context dict with ONLY source fields populated
        """
        item = enriched.item

        # Get display name from registry (no styling for {{Item}} template)
        display_name = self._resolver.resolve_display_name(item.stable_key)

        # Format source fields
        vendor_sources = self._format_vendor_sources(enriched)
        drop_sources = self._format_drop_sources(enriched)
        quest_rewards_str, quest_requirements_str = self._format_quest_sources(enriched)
        craft_sources, component_for = self._format_crafting_sources(enriched)
        crafting_results, recipe_ingredients = self._format_recipe_info(enriched)

        # Build context with SOURCE FIELDS ONLY
        # All stat/class/relic/description fields are EMPTY for weapons/armor
        context: dict[str, str] = {
            "title": display_name,
            "image": "",  # Image shown in fancy templates, not here
            "imagecaption": "",
            "type": "",  # No type for weapons/armor
            "vendorsource": vendor_sources,
            "source": drop_sources,
            "othersource": "",  # Primarily manual content
            "questsource": quest_rewards_str,
            "relatedquest": quest_requirements_str,
            "craftsource": craft_sources,
            "componentfor": component_for,
            "relic": "",  # Shown in fancy templates, not here
            "classes": "",  # Shown in fancy templates, not here
            "effects": "",
            "damage": "",  # Shown in fancy templates, not here
            "delay": "",  # Shown in fancy templates, not here
            "dps": "",
            "casttime": "",
            "duration": "",
            "cooldown": "",
            "description": "",  # Shown in fancy templates, not here
            "buy": safe_str(item.item_value) if item.item_value else "",
            "sell": safe_str(item.sell_value) if item.sell_value else "",
            "crafting": crafting_results,
            "recipe": recipe_ingredients,
        }

        return context

    def _build_item_template_context(self, enriched: EnrichedItemData, page_title: str) -> dict[str, str]:
        """Build context for {{Item}} template for general items.

        For general items (consumables, molds, ability books, etc), the {{Item}} template
        contains ALL fields including stats, classes, description, etc.

        Converts Item entity to template context dict. Handles None values,
        formats booleans, and provides empty strings for fields without data.

        Args:
            enriched: Enriched item data
            page_title: Wiki page title

        Returns:
            Template context dict
        """
        item = enriched.item

        # Classify item to determine type
        kind = self._classify(item)

        # Build item type display (Consumable, Quest Item, Crafting, Summoning Item)
        quest_requirements: list[str] = []
        component_for: list[str] = []

        # Use enriched quest sources
        # Only quest requirements (not rewards) make an item a "Quest Item"
        if enriched.sources:
            quest_requirements = enriched.sources.quest_requirements

        # Use enriched crafting sources for component usage
        if enriched.sources:
            component_for = enriched.sources.component_for

        item_type = build_item_types(
            item=item,
            item_kind=kind,
            quest_requirements=quest_requirements,
            component_for=component_for,
        )

        # Get display name from registry (may differ from page title for disambiguation)
        display_name = self._resolver.resolve_display_name(item.stable_key)

        # Format class restrictions (comma-separated with wiki links)
        classes = ", ".join(f"[[{cls}]]" for cls in enriched.classes) if enriched.classes else ""

        # Extract effects (ItemEffectOnClick, WornEffect, etc)
        effects = ""
        if enriched.proc:
            effects = self._resolver.ability_link(enriched.proc.stable_key)

        # Format source fields
        vendor_sources = self._format_vendor_sources(enriched)
        drop_sources = self._format_drop_sources(enriched)
        quest_rewards_str, quest_requirements_str = self._format_quest_sources(enriched)
        craft_sources_str, component_for_str = self._format_crafting_sources(enriched)
        crafting_results, recipe_ingredients = self._format_recipe_info(enriched)

        # Get image name from registry (resolve stable key to image filename)
        image_name = self._resolver.resolve_image_name(item.stable_key)
        image_field = f"[[File:{image_name}.png]]" if image_name else ""

        # Build context with all {{Item}} template fields
        context: dict[str, str] = {
            "title": display_name,
            "image": image_field,
            "imagecaption": "",
            "type": item_type,
            "vendorsource": vendor_sources,
            "source": drop_sources,
            "othersource": "",  # Primarily manual content
            "questsource": quest_rewards_str,
            "relatedquest": quest_requirements_str,
            "craftsource": craft_sources_str,
            "componentfor": component_for_str,
            "relic": "True" if item.relic else "",
            "classes": classes,
            "effects": effects,
            "damage": "",  # Not used for general items
            "delay": "",  # Not used for general items
            "dps": "",  # Not used for general items
            "casttime": "",  # Not used for general items
            "duration": "",  # Not used for general items
            "cooldown": "",  # Not used for general items
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "buy": safe_str(item.item_value) if item.item_value else "",
            "sell": safe_str(item.sell_value) if item.sell_value else "",
            "crafting": crafting_results,
            "recipe": recipe_ingredients,
        }

        return context

    def _build_fancy_weapon(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> str:
        """Build a single {{Fancy-weapon}} template for one quality tier.

        Args:
            enriched: Enriched item data with classes and proc info
            page_title: Wiki page title
            stat: ItemStats for this quality tier

        Returns:
            Rendered {{Fancy-weapon}} template wikitext
        """
        item = enriched.item

        # Determine tier number (0=Normal, 1=Blessed, 2=Godly)
        tier = {"Normal": 0, "Blessed": 1, "Godly": 2}.get(stat.quality, 0)

        # Get weapon type display
        weapon_type = self._weapon_type_display(item.required_slot, item.this_weapon_type)

        # Class obtainability
        class_flags = {
            "arcanist": "True" if "Arcanist" in enriched.classes else "",
            "duelist": "True" if "Duelist" in enriched.classes else "",
            "druid": "True" if "Druid" in enriched.classes else "",
            "paladin": "True" if "Paladin" in enriched.classes else "",
            "stormcaller": "True" if "Stormcaller" in enriched.classes else "",
        }

        # Extract proc info using resolver
        proc_name = ""
        proc_desc = ""
        proc_chance = ""
        proc_style = ""
        if enriched.proc:
            proc = enriched.proc
            proc_name = self._resolver.ability_link(proc.stable_key)
            proc_desc = proc.description
            proc_chance = proc.proc_chance
            proc_style = proc.proc_style

        # Get display name from registry (may differ from page title for disambiguation)
        display_name = self._resolver.resolve_display_name(item.stable_key)

        context = {
            "image": f"[[File:{page_title}.png|80px]]",
            "name": self._format_item_name_for_fancy_template(display_name),
            "type": weapon_type,
            "relic": "True" if item.relic else "",
            "str": safe_str(stat.str_),
            "end": safe_str(stat.end_),
            "dex": safe_str(stat.dex),
            "agi": safe_str(stat.agi),
            "int": safe_str(stat.int_),
            "wis": safe_str(stat.wis),
            "cha": safe_str(stat.cha),
            "res": safe_str(stat.res),
            "damage": safe_str(stat.weapon_dmg) if stat.weapon_dmg else "",
            "delay": safe_str(item.weapon_dly) if item.weapon_dly else "",
            "health": safe_str(stat.hp),
            "mana": safe_str(stat.mana),
            "armor": safe_str(stat.ac),
            "magic": safe_str(stat.mr),
            "poison": safe_str(stat.pr),
            "elemental": safe_str(stat.er),
            "void": safe_str(stat.vr),
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            **class_flags,
            "proc_name": proc_name,
            "proc_desc": proc_desc,
            "proc_chance": proc_chance,
            "proc_style": proc_style,
            "tier": str(tier),
        }

        return self.render_template("weapon.jinja2", context)

    def _build_fancy_armor(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> str:
        """Build a single {{Fancy-armor}} template for one quality tier.

        Args:
            enriched: Enriched item data with classes and proc info
            page_title: Wiki page title
            stat: ItemStats for this quality tier

        Returns:
            Rendered {{Fancy-armor}} template wikitext
        """
        item = enriched.item

        # Determine tier number (0=Normal, 1=Blessed, 2=Godly)
        tier = {"Normal": 0, "Blessed": 1, "Godly": 2}.get(stat.quality, 0)

        # TODO: Get armor slot from item.required_slot
        slot = safe_str(item.required_slot)

        # Class obtainability
        class_flags = {
            "arcanist": "True" if "Arcanist" in enriched.classes else "",
            "duelist": "True" if "Duelist" in enriched.classes else "",
            "druid": "True" if "Druid" in enriched.classes else "",
            "paladin": "True" if "Paladin" in enriched.classes else "",
            "stormcaller": "True" if "Stormcaller" in enriched.classes else "",
        }

        # Extract proc info using resolver
        proc_name = ""
        proc_desc = ""
        proc_chance = ""
        proc_style = ""
        if enriched.proc:
            proc = enriched.proc
            proc_name = self._resolver.ability_link(proc.stable_key)
            proc_desc = proc.description
            proc_chance = proc.proc_chance
            proc_style = proc.proc_style

        # Get display name from registry (may differ from page title for disambiguation)
        display_name = self._resolver.resolve_display_name(item.stable_key)

        context = {
            "image": f"[[File:{page_title}.png|80px]]",
            "name": self._format_item_name_for_fancy_template(display_name),
            "type": "",  # Armor doesn't use "type" field
            "slot": slot,
            "relic": "True" if item.relic else "",
            "str": safe_str(stat.str_),
            "end": safe_str(stat.end_),
            "dex": safe_str(stat.dex),
            "agi": safe_str(stat.agi),
            "int": safe_str(stat.int_),
            "wis": safe_str(stat.wis),
            "cha": safe_str(stat.cha),
            "res": safe_str(stat.res),
            "health": safe_str(stat.hp),
            "mana": safe_str(stat.mana),
            "armor": safe_str(stat.ac),
            "magic": safe_str(stat.mr),
            "poison": safe_str(stat.pr),
            "elemental": safe_str(stat.er),
            "void": safe_str(stat.vr),
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            **class_flags,
            "proc_name": proc_name,
            "proc_desc": proc_desc,
            "proc_chance": proc_chance,
            "proc_style": proc_style,
            "tier": str(tier),
        }

        return self.render_template("armor.jinja2", context)

    def _build_fancy_charm(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> dict[str, str]:
        """Build context for {{Fancy-charm}} template.

        Args:
            enriched: Enriched item data with classes
            page_title: Wiki page title
            stat: ItemStats (use first/Normal quality, scaling is same across all tiers)

        Returns:
            Template context dict for fancy-charm template
        """
        item = enriched.item

        def format_scaling(value: float | None) -> str:
            """Format scaling value - empty string if 0 or None, otherwise the value."""
            if value is None or value == 0.0:
                return ""
            return str(int(value)) if value == int(value) else str(value)

        class_flags = {
            "arcanist": "True" if "Arcanist" in enriched.classes else "",
            "duelist": "True" if "Duelist" in enriched.classes else "",
            "druid": "True" if "Druid" in enriched.classes else "",
            "paladin": "True" if "Paladin" in enriched.classes else "",
            "stormcaller": "True" if "Stormcaller" in enriched.classes else "",
        }

        # Get display name from registry (may differ from page title for disambiguation)
        display_name = self._resolver.resolve_display_name(item.stable_key)

        context = {
            "image_name": f"{page_title}.png",
            "name": self._format_item_name_for_fancy_template(display_name),
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "str_scaling": format_scaling(stat.str_scaling),
            "end_scaling": format_scaling(stat.end_scaling),
            "dex_scaling": format_scaling(stat.dex_scaling),
            "agi_scaling": format_scaling(stat.agi_scaling),
            "int_scaling": format_scaling(stat.int_scaling),
            "wis_scaling": format_scaling(stat.wis_scaling),
            "cha_scaling": format_scaling(stat.cha_scaling),
            **class_flags,
        }

        return context

    def _format_fancy_table(self, fancy_templates: list[str]) -> str:
        """Format fancy templates into a MediaWiki table.

        Takes 3 fancy templates (Normal/Blessed/Godly) and formats them
        into a wiki table with one column per quality tier.

        Args:
            fancy_templates: List of rendered fancy template strings (should have 3 entries)

        Returns:
            MediaWiki table wikitext
        """
        # Join templates with ! to create table columns
        columns = "\n!".join(fancy_templates)
        return f"{{|\n!{columns}\n|}}"

    def _format_vendor_sources(self, enriched: EnrichedItemData) -> str:
        """Format vendor sources as wiki links.

        Vendors are:
        - Filtered to exclude entities that don't have wiki pages
        - Deduplicated by link text
        - Sorted alphabetically by display name

        Args:
            enriched: Enriched item data with vendor sources
            resolver: Registry resolver for character links

        Returns:
            <br>-separated list of vendor links (e.g., "[[Vendor A]]<br>[[Vendor B]]")
        """
        if not enriched.sources or not enriched.sources.vendors:
            return ""

        # Resolve all vendor links, filter excluded entities, and deduplicate
        vendor_links = []
        seen = set()
        for stable_key in enriched.sources.vendors:
            # Skip excluded entities (those without wiki pages)
            if self._resolver.resolve_page_title(stable_key) is None:
                continue

            link = self._resolver.character_link(stable_key)
            if link not in seen:
                seen.add(link)
                vendor_links.append(link)

        # Sort alphabetically
        vendor_links.sort()

        return "<br>".join(vendor_links)

    def _format_drop_sources(self, enriched: EnrichedItemData) -> str:
        """Format drop sources as wiki links with drop probabilities.

        Drop sources are:
        - Filtered to exclude entities that don't have wiki pages
        - Sorted by drop probability (descending, highest first)
        - Deduplicated by resolved link text (same character, same drop %)

        Args:
            enriched: Enriched item data with drop sources
            resolver: Registry resolver for character links

        Returns:
            <br>-separated list of drop links with probabilities (e.g., "[[Enemy A]] (5.0%)<br>[[Enemy B]] (10.0%)")
        """
        if not enriched.sources or not enriched.sources.drops:
            return ""

        # Build list of (link, probability) tuples, filtering out excluded entities
        drop_data = []
        for stable_key, drop_probability in enriched.sources.drops:
            # Skip excluded entities (those without wiki pages)
            if self._resolver.resolve_page_title(stable_key) is None:
                continue

            link = self._resolver.character_link(stable_key)
            drop_data.append((link, drop_probability))

        # Sort by probability descending (highest first), then by link text ascending (for ties)
        drop_data.sort(key=lambda x: (-x[1], x[0]))

        # Deduplicate by link text (keeping first occurrence which has highest probability)
        seen = set()
        unique_drops = []
        for link, probability in drop_data:
            # Create unique key from link and probability
            key = (link, probability)
            if key not in seen:
                seen.add(key)
                unique_drops.append(f"{link} ({probability:.1f}%)")

        return "<br>".join(unique_drops)

    def _format_quest_sources(self, enriched: EnrichedItemData) -> tuple[str, str]:
        """Format quest reward and requirement sources as wiki links.

        Quests are:
        - Filtered to exclude entities that don't have wiki pages
        - Deduplicated by link text
        - Sorted alphabetically

        Args:
            enriched: Enriched item data with quest sources
            resolver: Registry resolver for quest links

        Returns:
            Tuple of (reward_links, requirement_links):
            - reward_links: <br>-separated quest reward links (sorted alphabetically)
            - requirement_links: <br>-separated quest requirement links (sorted alphabetically)
        """
        if not enriched.sources:
            return ("", "")

        # Format reward quests, filtering out excluded entities and deduplicating
        reward_links = []
        seen_rewards = set()
        for stable_key in enriched.sources.quest_rewards:
            if self._resolver.resolve_page_title(stable_key) is not None:
                link = self._resolver.quest_link(stable_key)
                if link not in seen_rewards:
                    seen_rewards.add(link)
                    reward_links.append(link)

        # Sort reward links alphabetically
        reward_links.sort()

        # Format requirement quests, filtering out excluded entities and deduplicating
        requirement_links = []
        seen_requirements = set()
        for stable_key in enriched.sources.quest_requirements:
            if self._resolver.resolve_page_title(stable_key) is not None:
                link = self._resolver.quest_link(stable_key)
                if link not in seen_requirements:
                    seen_requirements.add(link)
                    requirement_links.append(link)

        # Sort requirement links alphabetically
        requirement_links.sort()

        return ("<br>".join(reward_links), "<br>".join(requirement_links))

    def _format_crafting_sources(self, enriched: EnrichedItemData) -> tuple[str, str]:
        """Format crafting sources (how to craft this item) and component usage.

        Args:
            enriched: Enriched item data with crafting sources
            resolver: Registry resolver for item links

        Returns:
            Tuple of (craft_sources, component_for):
            - craft_sources: Full recipe to craft this item (mold + materials with quantities)
            - component_for: What items use this as a component
        """
        if not enriched.sources:
            return ("", "")

        # Format craft recipe (mold + all ingredients with quantities)
        craft_links = []
        for stable_key, quantity in enriched.sources.craft_recipe:
            link = self._resolver.item_link(stable_key)
            craft_links.append(f"{quantity}x {link}")

        # Format component usage (items that require this as a component)
        component_links = [self._resolver.item_link(stable_key) for stable_key in enriched.sources.component_for]

        return ("<br>".join(craft_links), "<br>".join(component_links))

    def _format_recipe_info(self, enriched: EnrichedItemData) -> tuple[str, str]:
        """Format recipe results and ingredients for mold items.

        Args:
            enriched: Enriched item data with crafting results and ingredients
            resolver: Registry resolver for item links

        Returns:
            Tuple of (crafting_results, recipe_ingredients):
            - crafting_results: What this mold produces (with quantities)
            - recipe_ingredients: What materials this mold needs (with quantities)
        """
        if not enriched.sources:
            return ("", "")

        # Format crafting results (what this mold produces)
        result_links = []
        for stable_key, quantity in enriched.sources.crafting_results:
            link = self._resolver.item_link(stable_key)
            result_links.append(f"{quantity}x {link}")

        # Format recipe ingredients (what this mold needs)
        ingredient_links = []
        for stable_key, quantity in enriched.sources.recipe_ingredients:
            link = self._resolver.item_link(stable_key)
            ingredient_links.append(f"{quantity}x {link}")

        return ("<br>".join(result_links), "<br>".join(ingredient_links))

"""Item section generator for wiki content.

This module generates MediaWiki template wikitext for individual items including
weapons, armor, consumables, and other item types.

This section generator produces templates for single items. Multi-entity page
assembly is handled by PageGenerator classes.

Template structure:
- General items: {{Item}} template + category tags
- Weapons: {{Item}} + 3x {{Item/Weapon}} (Normal/Blessed/Godly) + category tags
- Armor: {{Item}} + 3x {{Item/Armor}} (Normal/Blessed/Godly) + category tags
- Charms: {{Item}} + {{Item/Charm}} + category tags

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
    from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
    from erenshor.domain.enriched_data.item import EnrichedItemData
    from erenshor.domain.entities.item import Item
    from erenshor.domain.entities.item_stats import ItemStats
    from erenshor.domain.entities.spell import Spell
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

    def __init__(self, resolver: RegistryResolver, class_display: ClassDisplayNameService) -> None:
        """Initialize item section generator.

        Args:
            resolver: Registry resolver for links and display names
            class_display: Service for mapping class names to display names
        """
        super().__init__()
        self._resolver = resolver
        self._class_display = class_display

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
        elif kind == ItemKind.AURA:
            template_wikitext = self._generate_aura_page(enriched, page_title)
        elif kind == ItemKind.SPELL_SCROLL:
            template_wikitext = self._generate_spellscroll_page(enriched, page_title)
        elif kind == ItemKind.SKILL_BOOK:
            template_wikitext = self._generate_skillbook_page(enriched, page_title)
        elif kind == ItemKind.CONSUMABLE:
            template_wikitext = self._generate_consumable_page(enriched, page_title)
        elif kind == ItemKind.MOLD:
            template_wikitext = self._generate_mold_page(enriched, page_title)
        elif kind == ItemKind.GENERAL:
            template_wikitext = self._generate_general_page(enriched, page_title)
        else:
            # Fallback (should never reach here due to exhaustive ItemKind)
            template_wikitext = self._generate_general_page(enriched, page_title)

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

    def _generate_aura_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for aura items.

        Aura items provide passive spell effects when worn. Generates {{Item}} template
        for source fields plus {{Item/Aura}} template with full spell details.

        Args:
            enriched: Enriched item data with aura_spell
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} + {{Item/Aura}} templates
        """
        item = enriched.item

        # Generate {{Item}} template for sources
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Item/Aura}} template with spell details
        display_name = self._resolver.resolve_display_name(item.stable_key)
        image_name = self._resolver.resolve_image_name(item.stable_key)

        # Build spell details from aura spell
        spell_details = self._build_spell_details_context(enriched.aura_spell, prefix="aura")

        aura_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            **spell_details,
        }

        aura_template = self.render_template("aura.jinja2", aura_context)
        return f"{item_template}\n\n{aura_template}"

    def _generate_spellscroll_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for spell scroll items.

        Spell scrolls teach spells to the player. Generates {{Item}} template for sources
        plus {{Item/SpellScroll}} template with taught spell info.

        Level requirements are shown per-class: if a class can learn the spell, show the
        spell's required_level for that class. Empty string if the class cannot learn it.

        Args:
            enriched: Enriched item data with taught_spell
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} + {{Item/SpellScroll}} templates
        """
        item = enriched.item
        spell = enriched.taught_spell

        # Generate {{Item}} template for sources
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Item/SpellScroll}} template
        display_name = self._resolver.resolve_display_name(item.stable_key)
        image_name = self._resolver.resolve_image_name(item.stable_key)

        # Get classes that can use the taught spell and the required level
        spell_classes = enriched.taught_spell_classes
        required_level = str(spell.required_level) if spell and spell.required_level else ""

        # Build per-class level requirements: show level if class can learn, empty otherwise
        def class_level(class_name: str) -> str:
            return required_level if class_name in spell_classes else ""

        spellscroll_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "arcanist_level": class_level("Arcanist"),
            "druid_level": class_level("Druid"),
            "duelist_level": class_level("Duelist"),
            "paladin_level": class_level("Paladin"),
            "stormcaller_level": class_level("Stormcaller"),
            "reaver_level": class_level("Reaver"),
            "mana_cost": str(spell.mana_cost) if spell and spell.mana_cost else "",
            "spell_type": spell.type if spell and spell.type else "",
            "spell_desc": format_description(spell.spell_desc) if spell and spell.spell_desc else "",
        }

        spellscroll_template = self.render_template("spellscroll.jinja2", spellscroll_context)
        return f"{item_template}\n\n{spellscroll_template}"

    def _generate_skillbook_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for skill book items.

        Skill books teach skills to the player. Generates {{Item}} template for sources
        plus {{Item/SkillBook}} template with taught skill info including class levels.

        Args:
            enriched: Enriched item data with taught_skill
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} + {{Item/SkillBook}} templates
        """
        item = enriched.item
        skill = enriched.taught_skill

        # Generate {{Item}} template for sources
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Item/SkillBook}} template
        display_name = self._resolver.resolve_display_name(item.stable_key)
        image_name = self._resolver.resolve_image_name(item.stable_key)

        # Helper for class level formatting (empty if None or 0)
        def level_str(val: int | None) -> str:
            if val is None or val == 0:
                return ""
            return str(val)

        skillbook_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "duelist_level": level_str(skill.duelist_required_level) if skill else "",
            "druid_level": level_str(skill.druid_required_level) if skill else "",
            "arcanist_level": level_str(skill.arcanist_required_level) if skill else "",
            "paladin_level": level_str(skill.paladin_required_level) if skill else "",
            "stormcaller_level": level_str(skill.stormcaller_required_level) if skill else "",
            "reaver_level": level_str(skill.reaver_required_level) if skill else "",
            "skill_type": skill.type_of_skill if skill and skill.type_of_skill else "",
            "skill_desc": format_description(skill.skill_desc) if skill and skill.skill_desc else "",
            "simplayers_autolearn": "True" if skill and skill.sim_players_autolearn else "",
        }

        skillbook_template = self.render_template("skillbook.jinja2", skillbook_context)
        return f"{item_template}\n\n{skillbook_template}"

    def _generate_consumable_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for consumable items.

        Consumables are items that trigger a spell effect when used and may be consumed.
        Generates {{Item}} template for sources plus {{Item/Consumable}} with effect details.

        Args:
            enriched: Enriched item data with proc (effect)
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} + {{Item/Consumable}} templates
        """
        item = enriched.item

        # Generate {{Item}} template for sources
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Item/Consumable}} template with spell details
        display_name = self._resolver.resolve_display_name(item.stable_key)
        image_name = self._resolver.resolve_image_name(item.stable_key)

        # Get effect spell from proc info
        effect_spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(effect_spell, prefix="effect")

        consumable_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "disposable": "True" if item.disposable else "",
            **spell_details,
        }

        consumable_template = self.render_template("consumable.jinja2", consumable_context)
        return f"{item_template}\n\n{consumable_template}"

    def _generate_mold_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for mold/template items.

        Molds are crafting templates that define recipes. Generates {{Item}} template
        for sources plus {{Item/Mold}} with recipe details.

        Args:
            enriched: Enriched item data with recipe info in sources
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} + {{Item/Mold}} templates
        """
        item = enriched.item

        # Generate {{Item}} template for sources
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Item/Mold}} template
        display_name = self._resolver.resolve_display_name(item.stable_key)
        image_name = self._resolver.resolve_image_name(item.stable_key)

        # Format recipe ingredients and rewards from sources
        ingredients = ""
        rewards = ""
        if enriched.sources:
            # Format ingredients
            ingredient_links = []
            for stable_key, quantity in enriched.sources.recipe_ingredients:
                link = self._resolver.item_link(stable_key)
                ingredient_links.append(f"{quantity}x {link!s}")
            ingredients = "<br>".join(ingredient_links)

            # Format rewards (only show first result - game always produces one item)
            if enriched.sources.crafting_results:
                stable_key, _quantity = enriched.sources.crafting_results[0]
                rewards = str(self._resolver.item_link(stable_key))

        mold_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "ingredients": ingredients,
            "rewards": rewards,
            "station": "",  # Crafting station info not currently in database
        }

        mold_template = self.render_template("mold.jinja2", mold_context)
        return f"{item_template}\n\n{mold_template}"

    def _generate_general_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for general items (quest items, misc items, etc).

        General items are items that don't fit into other categories.
        Generates {{Item}} template plus {{Item/General}} for basic info.

        Args:
            enriched: Enriched item data
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} + {{Item/General}} templates
        """
        item = enriched.item

        # Generate {{Item}} template for sources
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Item/General}} template
        display_name = self._resolver.resolve_display_name(item.stable_key)
        image_name = self._resolver.resolve_image_name(item.stable_key)

        # Build spell details context from proc info (if available - for ItemEffectOnClick)
        spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(spell, prefix="effect")

        # Add proc trigger info (style and chance) from enriched.proc
        if enriched.proc:
            spell_details["effect_style"] = enriched.proc.proc_style
            spell_details["effect_chance"] = enriched.proc.proc_chance
        else:
            spell_details["effect_style"] = ""
            spell_details["effect_chance"] = ""

        general_context = {
            "image": f"{image_name}.png" if image_name else "",
            "name": display_name,
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            "value": safe_str(item.item_value) if item.item_value else "",
            "stack_size": "",  # Stack size info would need to be added
            "disposable": "True" if item.disposable else "",
            **spell_details,
        }

        general_template = self.render_template("general.jinja2", general_context)
        return f"{item_template}\n\n{general_template}"

    def _generate_general_item_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for general items (consumables, molds, ability books, etc).

        DEPRECATED: Use specific generator methods instead (_generate_aura_page, etc.)

        Args:
            enriched: Enriched item data
            page_title: Wiki page title
            resolver: Registry resolver for links and overrides

        Returns:
            Wikitext with {{Item}} template
        """
        context = self._build_item_infobox_context(enriched, page_title)
        return self.render_template("item.jinja2", context)

    def _generate_weapon_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for weapons.

        Generates {{Item}} template for general info plus 3x {{Item/Weapon}} templates
        (one for each quality tier: Normal/Blessed/Godly) in a wiki table.

        Args:
            enriched: Enriched item data with stats
            page_title: Wiki page title
            resolver: Registry resolver for links and overrides

        Returns:
            Wikitext with {{Item}} template + {{Item/Weapon}} table

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
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Item/Weapon}} templates (one per quality tier)
        fancy_templates = [self._build_fancy_weapon(enriched, page_title, stat) for stat in stats]
        fancy_table = self._format_fancy_table(fancy_templates)

        return f"{item_template}\n\n{fancy_table}"

    def _generate_armor_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for armor.

        Generates {{Item}} template for general info plus 3x {{Item/Armor}} templates
        (one for each quality tier: Normal/Blessed/Godly) in a wiki table.

        Args:
            enriched: Enriched item data with stats
            page_title: Wiki page title
            resolver: Registry resolver for links and overrides

        Returns:
            Wikitext with {{Item}} template + {{Item/Armor}} table

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
        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        # Generate {{Item/Armor}} templates (one per quality tier)
        fancy_templates = [self._build_fancy_armor(enriched, page_title, stat) for stat in stats]
        fancy_table = self._format_fancy_table(fancy_templates)

        return f"{item_template}\n\n{fancy_table}"

    def _generate_charm_page(self, enriched: EnrichedItemData, page_title: str) -> str:
        """Generate page for charms.

        Generates {{Item}} template for source fields plus {{Item/Charm}} template
        for stat scaling display.

        Args:
            enriched: Enriched item data with stats
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} + {{Item/Charm}} templates
        """
        stats = enriched.stats

        item_context = self._build_item_infobox_context(enriched, page_title)
        item_template = self.render_template("item.jinja2", item_context)

        if stats:
            charm_stat = stats[0]
            charm_context = self._build_charm_context(enriched, page_title, charm_stat)
            charm_template = self.render_template("charm.jinja2", charm_context)
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

    def _get_weapon_range(self, item: Item) -> str:
        """Get weapon range display value.

        Based on game logic in ItemInfoWindow.cs:
        - Wands use WandRange
        - Bows use BowRange
        - Melee weapons don't display range (implicitly 1)

        Args:
            item: Item entity

        Returns:
            Range value as string, or empty string for melee weapons
        """
        if item.is_wand and item.wand_range and item.wand_range > 0:
            return str(item.wand_range)
        if item.is_bow and item.bow_range and item.bow_range > 0:
            return str(item.bow_range)
        return ""

    def _build_item_infobox_context(self, enriched: EnrichedItemData, page_title: str) -> dict[str, str]:
        """Build context for {{Item}} infobox template.

        The {{Item}} template contains only source and acquisition information.
        All stats, descriptions, and item-specific data are shown in the Item/*
        tooltip templates instead to avoid duplication.

        Args:
            enriched: Enriched item data with sources
            page_title: Wiki page title

        Returns:
            Template context dict with infobox fields
        """
        item = enriched.item

        # Classify item to determine type
        kind = self._classify(item)

        # Build item type display (Consumable, Quest Item, Crafting, etc.)
        quest_requirements: list[str] = []
        component_for_list: list[str] = []

        if enriched.sources:
            quest_requirements = enriched.sources.quest_requirements
            component_for_list = enriched.sources.component_for

        item_type = build_item_types(
            item=item,
            item_kind=kind,
            quest_requirements=quest_requirements,
            component_for=component_for_list,
        )

        # Get display name from registry (no styling for {{Item}} template)
        display_name = self._resolver.resolve_display_name(item.stable_key)

        # Format source fields
        vendor_sources = self._format_vendor_sources(enriched)
        drop_sources = self._format_drop_sources(enriched)
        quest_rewards_str, quest_requirements_str = self._format_quest_sources(enriched)
        craft_sources, component_for_str = self._format_crafting_sources(enriched)

        # Spell Book: link to taught spell
        taughtspell = ""
        if item.teach_spell_stable_key:
            taughtspell = str(self._resolver.ability_link(item.teach_spell_stable_key))

        # Skill Book: link to taught skill
        taughtskill = ""
        if item.teach_skill_stable_key:
            taughtskill = str(self._resolver.ability_link(item.teach_skill_stable_key))

        # Format item drops (for consumables like fossils)
        guaranteed_drops = self._format_guaranteed_drops(enriched)
        drop_rates = self._format_drop_rates(enriched)

        # Build context with only fields needed by {{Item}} template
        context: dict[str, str] = {
            "title": display_name,
            "type": item_type,
            "vendorsource": vendor_sources,
            "source": drop_sources,
            "othersource": "",  # Primarily manual content
            "questsource": quest_rewards_str,
            "relatedquest": quest_requirements_str,
            "craftsource": craft_sources,
            "componentfor": component_for_str,
            "buy": safe_str(item.item_value) if item.item_value else "",
            "sell": safe_str(item.sell_value) if item.sell_value else "",
            "taughtspell": taughtspell,
            "taughtskill": taughtskill,
            "guaranteeddrops": guaranteed_drops,
            "droprates": drop_rates,
        }

        return context

    def _build_fancy_weapon(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> str:
        """Build a single {{Item/Weapon}} template for one quality tier.

        Args:
            enriched: Enriched item data with classes and proc info
            page_title: Wiki page title
            stat: ItemStats for this quality tier

        Returns:
            Rendered {{Item/Weapon}} template wikitext
        """
        item = enriched.item

        # Determine tier number (0=Normal, 1=Blessed, 2=Godly)
        tier = {"Normal": 0, "Blessed": 1, "Godly": 2}.get(stat.quality, 0)

        # Get weapon type display
        weapon_type = self._weapon_type_display(item.required_slot, item.this_weapon_type)

        # Class obtainability - map internal class names to display names
        class_flags = self._build_class_flags(enriched.classes)

        # Get display name from registry (may differ from page title for disambiguation)
        display_name = self._resolver.resolve_display_name(item.stable_key)

        # Build spell details context from proc info (if available)
        spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(spell, prefix="proc")

        # Add proc trigger info (style and chance) from enriched.proc
        if enriched.proc:
            spell_details["proc_style"] = enriched.proc.proc_style
            spell_details["proc_chance"] = enriched.proc.proc_chance
        else:
            spell_details["proc_style"] = ""
            spell_details["proc_chance"] = ""

        context = {
            "image": f"{page_title}.png",
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
            "range": self._get_weapon_range(item),
            "health": safe_str(stat.hp),
            "mana": safe_str(stat.mana),
            "armor": safe_str(stat.ac),
            "magic": safe_str(stat.mr),
            "poison": safe_str(stat.pr),
            "elemental": safe_str(stat.er),
            "void": safe_str(stat.vr),
            "description": format_description(safe_str(item.lore)) if item.lore else "",
            **class_flags,
            **spell_details,
            "tier": str(tier),
        }

        return self.render_template("weapon.jinja2", context)

    def _build_fancy_armor(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> str:
        """Build a single {{Item/Armor}} template for one quality tier.

        Args:
            enriched: Enriched item data with classes and proc info
            page_title: Wiki page title
            stat: ItemStats for this quality tier

        Returns:
            Rendered {{Item/Armor}} template wikitext
        """
        item = enriched.item

        # Determine tier number (0=Normal, 1=Blessed, 2=Godly)
        tier = {"Normal": 0, "Blessed": 1, "Godly": 2}.get(stat.quality, 0)

        # Get armor slot from item.required_slot
        slot = safe_str(item.required_slot)

        # Class obtainability - map internal class names to display names
        class_flags = self._build_class_flags(enriched.classes)

        # Get display name from registry (may differ from page title for disambiguation)
        display_name = self._resolver.resolve_display_name(item.stable_key)

        # Build spell details context from proc info (if available)
        spell = enriched.proc.spell if enriched.proc else None
        spell_details = self._build_spell_details_context(spell, prefix="proc")

        # Add proc trigger info (style and chance) from enriched.proc
        if enriched.proc:
            spell_details["proc_style"] = enriched.proc.proc_style
            spell_details["proc_chance"] = enriched.proc.proc_chance
        else:
            spell_details["proc_style"] = ""
            spell_details["proc_chance"] = ""

        context = {
            "image": f"{page_title}.png",
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
            **spell_details,
            "tier": str(tier),
        }

        return self.render_template("armor.jinja2", context)

    def _build_charm_context(self, enriched: EnrichedItemData, page_title: str, stat: ItemStats) -> dict[str, str]:
        """Build context for {{Item/Charm}} template.

        Args:
            enriched: Enriched item data with classes
            page_title: Wiki page title
            stat: ItemStats (use first/Normal quality, scaling is same across all tiers)

        Returns:
            Template context dict for charm template
        """
        item = enriched.item

        def format_scaling(value: float | None) -> str:
            """Format scaling value - empty string if 0 or None, otherwise rounded to int."""
            if value is None or value == 0.0:
                return ""
            return str(round(value))

        # Get display name and image from registry
        display_name = self._resolver.resolve_display_name(item.stable_key)
        image_name = self._resolver.resolve_image_name(item.stable_key)

        context = {
            "image": f"{image_name}.png" if image_name else f"{page_title}.png",
            "name": display_name,
            "tier": "0",  # Charms don't have tiers in the new system
            "strscaling": format_scaling(stat.str_scaling),
            "endscaling": format_scaling(stat.end_scaling),
            "dexscaling": format_scaling(stat.dex_scaling),
            "agiscaling": format_scaling(stat.agi_scaling),
            "intscaling": format_scaling(stat.int_scaling),
            "wisscaling": format_scaling(stat.wis_scaling),
            "chascaling": format_scaling(stat.cha_scaling),
            "resistscaling": format_scaling(stat.resist_scaling),
            "mitigationscaling": format_scaling(stat.mitigation_scaling),
            **self._build_class_flags(enriched.classes),
        }

        return context

    def _build_class_flags(self, class_names: list[str]) -> dict[str, str]:
        """Build class obtainability flags for item templates.

        Uses internal class names (e.g., "Duelist", "Reaver") as template
        parameter names, since the MediaWiki templates use internal names.

        Args:
            class_names: Internal class names from enriched.classes

        Returns:
            Dict like {"arcanist": "True", "duelist": "", "reaver": "True", ...}
        """
        class_set = set(class_names)
        known_classes = self._class_display.get_all_internal_names()
        return {name.lower(): "True" if name in class_set else "" for name in known_classes}

    def _build_spell_details_context(self, spell: Spell | None, prefix: str = "proc") -> dict[str, str]:
        """Build template context for spell details fields.

        Extracts all relevant spell fields and prefixes them appropriately
        for use in templates like {{Item/Weapon}}, {{Item/Armor}}, etc.

        Args:
            spell: Spell entity (can be None if no proc/effect)
            prefix: Field name prefix (e.g., "proc", "effect", "aura")

        Returns:
            Dict with prefixed spell fields, all empty strings if spell is None
        """
        # Define all the spell detail fields with their context keys
        empty_context: dict[str, str] = {
            f"{prefix}_spell_icon": "",
            f"{prefix}_spell_name": "",
            f"{prefix}_spell_level": "",
            f"{prefix}_spell_duration_ticks": "",
            f"{prefix}_spell_type": "",
            f"{prefix}_spell_line": "",
            f"{prefix}_target_damage": "",
            f"{prefix}_target_healing": "",
            f"{prefix}_shielding_amt": "",
            f"{prefix}_damage_type": "",
            f"{prefix}_cast_time": "",
            f"{prefix}_cooldown": "",
            f"{prefix}_spell_range": "",
            f"{prefix}_lifetap": "",
            f"{prefix}_group_effect": "",
            f"{prefix}_stun_target": "",
            f"{prefix}_charm_target": "",
            f"{prefix}_root_target": "",
            f"{prefix}_taunt_spell": "",
            f"{prefix}_aggro": "",
            f"{prefix}_status_effect_name": "",
            f"{prefix}_hp": "",
            f"{prefix}_ac": "",
            f"{prefix}_mana": "",
            f"{prefix}_str": "",
            f"{prefix}_dex": "",
            f"{prefix}_end": "",
            f"{prefix}_agi": "",
            f"{prefix}_wis": "",
            f"{prefix}_int": "",
            f"{prefix}_cha": "",
            f"{prefix}_mr": "",
            f"{prefix}_er": "",
            f"{prefix}_pr": "",
            f"{prefix}_vr": "",
            f"{prefix}_movement_speed": "",
            f"{prefix}_damage_shield": "",
            f"{prefix}_haste": "",
            f"{prefix}_percent_lifesteal": "",
            f"{prefix}_atk_roll_modifier": "",
            f"{prefix}_resonate_chance": "",
            f"{prefix}_add_proc_name": "",
            f"{prefix}_add_proc_chance": "",
            f"{prefix}_special_descriptor": "",
            f"{prefix}_xp_bonus": "",
        }

        if spell is None:
            return empty_context

        # Helper to convert boolean-like integers to display strings
        def bool_str(val: int | None) -> str:
            return "True" if val else ""

        # Helper to safely format numeric values (skip zeros)
        def num_str(val: int | float | None) -> str:
            if val is None or val == 0:
                return ""
            return str(val)

        # Build context from spell entity
        # Resolve add_proc name if present
        add_proc_name = ""
        if spell.add_proc_stable_key:
            add_proc_name = str(self._resolver.ability_link(spell.add_proc_stable_key))

        # Resolve status effect name if present
        status_effect_name = ""
        if spell.status_effect_to_apply_stable_key:
            stable_key = spell.status_effect_to_apply_stable_key
            page_title = self._resolver.resolve_page_title(stable_key)
            display_name = self._resolver.resolve_display_name(stable_key)
            if page_title:
                if display_name and display_name != page_title:
                    status_effect_name = f"<br>[[{page_title}|{display_name}]]"
                else:
                    status_effect_name = f"<br>[[{page_title}]]"
            else:
                # No wiki page, just show display name
                status_effect_name = f"<br>{display_name}" if display_name else ""

        # Resolve spell display name and icon from registry
        spell_display_name = self._resolver.resolve_display_name(spell.stable_key) or spell.spell_name or ""
        spell_icon_name = self._resolver.resolve_image_name(spell.stable_key)
        spell_icon = f"{spell_icon_name}.png" if spell_icon_name else ""

        # Generate wiki link for spell name: [[PageName|DisplayName]] or [[DisplayName]]
        spell_page_title = self._resolver.resolve_page_title(spell.stable_key)
        if spell_page_title:
            if spell_display_name != spell_page_title:
                spell_name_link = f"[[{spell_page_title}|{spell_display_name}]]"
            else:
                spell_name_link = f"[[{spell_display_name}]]"
        else:
            # Excluded spell - plain text
            spell_name_link = spell_display_name

        context: dict[str, str] = {
            f"{prefix}_spell_icon": spell_icon,
            f"{prefix}_spell_name": spell_name_link,
            f"{prefix}_spell_level": num_str(spell.required_level),
            f"{prefix}_spell_duration_ticks": num_str(spell.spell_duration_in_ticks),
            f"{prefix}_spell_type": spell.type or "",
            f"{prefix}_spell_line": spell.line or "",
            f"{prefix}_target_damage": num_str(spell.target_damage),
            f"{prefix}_target_healing": num_str(spell.target_healing),
            f"{prefix}_shielding_amt": num_str(spell.shielding_amt),
            f"{prefix}_damage_type": spell.damage_type or "",
            f"{prefix}_cast_time": f"{spell.spell_charge_time / 60.0:.1f}" if spell.spell_charge_time else "",
            f"{prefix}_cooldown": num_str(spell.cooldown),
            f"{prefix}_spell_range": num_str(spell.spell_range),
            f"{prefix}_lifetap": bool_str(spell.lifetap),
            f"{prefix}_group_effect": bool_str(spell.group_effect),
            f"{prefix}_stun_target": bool_str(spell.stun_target),
            f"{prefix}_charm_target": bool_str(spell.charm_target),
            f"{prefix}_root_target": bool_str(spell.root_target),
            f"{prefix}_taunt_spell": bool_str(spell.taunt_spell),
            f"{prefix}_aggro": num_str(spell.aggro),
            f"{prefix}_status_effect_name": status_effect_name,
            f"{prefix}_hp": num_str(spell.hp),
            f"{prefix}_ac": num_str(spell.ac),
            f"{prefix}_mana": num_str(spell.mana),
            f"{prefix}_str": num_str(spell.str_),
            f"{prefix}_dex": num_str(spell.dex),
            f"{prefix}_end": num_str(spell.end_),
            f"{prefix}_agi": num_str(spell.agi),
            f"{prefix}_wis": num_str(spell.wis),
            f"{prefix}_int": num_str(spell.int_),
            f"{prefix}_cha": num_str(spell.cha),
            f"{prefix}_mr": num_str(spell.mr),
            f"{prefix}_er": num_str(spell.er),
            f"{prefix}_pr": num_str(spell.pr),
            f"{prefix}_vr": num_str(spell.vr),
            f"{prefix}_movement_speed": num_str(spell.movement_speed),
            f"{prefix}_damage_shield": num_str(spell.damage_shield),
            f"{prefix}_haste": num_str(spell.haste),
            f"{prefix}_percent_lifesteal": num_str(spell.percent_lifesteal),
            f"{prefix}_atk_roll_modifier": num_str(spell.atk_roll_modifier),
            f"{prefix}_resonate_chance": num_str(spell.resonate_chance),
            f"{prefix}_add_proc_name": add_proc_name,
            f"{prefix}_add_proc_chance": num_str(spell.add_proc_chance),
            f"{prefix}_special_descriptor": spell.special_descriptor or "",
            f"{prefix}_xp_bonus": str(round(spell.xp_bonus * 100))
            if spell.xp_bonus and spell.line == "XPBonus"
            else "",
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

        # Sort alphabetically by display name
        vendor_links.sort()

        return "<br>".join(str(link) for link in vendor_links)

    def _format_drop_sources(self, enriched: EnrichedItemData) -> str:
        """Format drop sources as wiki links with drop probabilities.

        Drop sources include both characters and items (e.g., fossils) and are:
        - Filtered to exclude entities that don't have wiki pages
        - Sorted by drop probability (descending, highest first)
        - Deduplicated by resolved link text (same source, same drop %)

        Args:
            enriched: Enriched item data with drop sources

        Returns:
            <br>-separated list of drop links with probabilities (e.g., "[[Enemy A]] (5.0%)<br>[[Fossil]] (26.0%)")
        """
        if not enriched.sources or not enriched.sources.drops:
            return ""

        # Build list of (link, probability) tuples, filtering out excluded entities
        drop_data = []
        for stable_key, drop_probability in enriched.sources.drops:
            # Skip excluded entities (those without wiki pages)
            if self._resolver.resolve_page_title(stable_key) is None:
                continue

            # Use plain [[Name]] links for all drop sources (items and characters)
            link = self._resolver.standard_link(stable_key)
            drop_data.append((link, drop_probability))

        # Sort by probability descending (highest first), then by display name ascending (for ties)
        drop_data.sort(key=lambda x: (-x[1], x[0]))

        # Deduplicate by link text (keeping first occurrence which has highest probability)
        seen = set()
        unique_drops = []
        for link, probability in drop_data:
            # Create unique key from link and probability
            key = (link, probability)
            if key not in seen:
                seen.add(key)
                unique_drops.append(f"{link!s} ({probability:.1f}%)")

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

        # Sort reward links alphabetically by display name
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

        # Sort requirement links alphabetically by display name
        requirement_links.sort()

        return ("<br>".join(str(link) for link in reward_links), "<br>".join(str(link) for link in requirement_links))

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
            craft_links.append(f"{quantity}x {link!s}")

        # Format component usage (items that require this as a component)
        component_links = [self._resolver.item_link(stable_key) for stable_key in enriched.sources.component_for]

        return ("<br>".join(craft_links), "<br>".join(str(link) for link in component_links))

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
            result_links.append(f"{quantity}x {link!s}")

        # Format recipe ingredients (what this mold needs)
        ingredient_links = []
        for stable_key, quantity in enriched.sources.recipe_ingredients:
            link = self._resolver.item_link(stable_key)
            ingredient_links.append(f"{quantity}x {link!s}")

        return ("<br>".join(result_links), "<br>".join(ingredient_links))

    def _format_guaranteed_drops(self, enriched: EnrichedItemData) -> str:
        """Format guaranteed drop pool as wiki links (no percentages).

        For consumables like fossils that produce random items when used.
        All items in the pool are listed, sorted alphabetically by display name
        (consistent with character page guaranteed drops).

        Args:
            enriched: Enriched item data with item drops

        Returns:
            <br>-separated {{ItemLink}}s, or empty string if no drops
        """
        if not enriched.sources or not enriched.sources.item_drops:
            return ""

        # Collect items with display names for alphabetical sorting
        items_with_names: list[tuple[str, str]] = []  # (display_name_lower, link)
        for stable_key, _ in enriched.sources.item_drops:
            # Skip items without wiki pages
            if self._resolver.resolve_page_title(stable_key) is None:
                continue
            display_name = self._resolver.resolve_display_name(stable_key)
            link = self._resolver.item_link(stable_key)
            items_with_names.append((display_name.lower(), str(link)))

        # Sort alphabetically by display name
        items_with_names.sort(key=lambda x: x[0])

        return "<br>".join(link for _, link in items_with_names)

    def _format_drop_rates(self, enriched: EnrichedItemData) -> str:
        """Format drop rates as wiki links with percentages.

        For consumables like fossils that produce random items when used.
        Shows each item with its drop probability.

        Args:
            enriched: Enriched item data with item drops

        Returns:
            <br>-separated {{ItemLink}}s with (X%) suffix, or empty string if no drops
        """
        if not enriched.sources or not enriched.sources.item_drops:
            return ""

        # Items are already sorted by probability desc from the repository
        links = []
        for stable_key, probability in enriched.sources.item_drops:
            # Skip items without wiki pages
            if self._resolver.resolve_page_title(stable_key) is None:
                continue
            link = self._resolver.item_link(stable_key)
            # Use integer percentage (no decimals) per the example
            links.append(f"{link!s} ({probability:.0f}%)")

        return "<br>".join(links)

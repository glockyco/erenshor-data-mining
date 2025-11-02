"""Item template generator for wiki content.

This module generates MediaWiki template wikitext for individual items including
weapons, armor, consumables, and other item types.

Template generators handle SINGLE entities only. Multi-entity page assembly
is handled by WikiService.

Template structure:
- General items: {{Item}} template + category tags
- Weapons: {{Item}} + 3x {{Fancy-weapon}} (Normal/Blessed/Godly) + category tags
- Armor: {{Item}} + 3x {{Fancy-armor}} (Normal/Blessed/Godly) + category tags
- Charms: {{Item}} + {{Fancy-charm}} + category tags

Note: This initial implementation generates fresh content without source enrichment
(vendors, drops, quests, crafting). Source enrichment will be added in future tasks.
"""

from loguru import logger

from erenshor.application.generators.categories import CategoryGenerator
from erenshor.application.generators.formatting import safe_str
from erenshor.application.generators.template_generator_base import TemplateGeneratorBase
from erenshor.domain.entities.item import Item
from erenshor.registry.item_classifier import ItemKind, classify_item_kind


class ItemTemplateGenerator(TemplateGeneratorBase):
    """Generator for item wiki templates.

    Generates template wikitext for a SINGLE item entity with appropriate templates
    and category tags based on item classification.

    Multi-entity page assembly is handled by WikiService, not here.

    Example:
        >>> generator = ItemTemplateGenerator()
        >>> item = Item(...)  # From repository
        >>> wikitext = generator.generate_template(item, page_title="Sword of Truth")
    """

    def __init__(self) -> None:
        """Initialize item template generator."""
        super().__init__()
        self._category_generator = CategoryGenerator()

    def generate_template(self, item: Item, page_title: str) -> str:
        """Generate template wikitext for a single item.

        Args:
            item: Single Item entity from repository
            page_title: Wiki page title (from registry)

        Returns:
            Template wikitext for single item (infobox + categories)

        Example:
            >>> item = Item(id="1", resource_name="Sword", item_name="Sword")
            >>> wikitext = generator.generate_template(item, "Sword")
        """
        logger.debug(f"Generating template for item: {item.item_name} (kind: {self._classify(item)})")

        # Classify item to determine templates
        kind = self._classify(item)

        # Generate appropriate templates based on kind
        if kind == ItemKind.WEAPON:
            template_wikitext = self._generate_weapon_page(item, page_title)
        elif kind == ItemKind.ARMOR:
            template_wikitext = self._generate_armor_page(item, page_title)
        elif kind in (ItemKind.AURA, ItemKind.ABILITY_BOOK, ItemKind.CONSUMABLE, ItemKind.MOLD, ItemKind.GENERAL):
            # All non-weapon/armor items use general template for now
            template_wikitext = self._generate_general_item_page(item, page_title)
        else:
            # Fallback (should never reach here due to exhaustive ItemKind)
            template_wikitext = self._generate_general_item_page(item, page_title)

        # Generate category tags
        categories = self._category_generator.generate_item_categories(item)
        category_wikitext = self.format_category_tags(categories)

        # Combine templates and categories
        page_content = template_wikitext
        if category_wikitext:
            page_content += "\n" + category_wikitext

        return self.normalize_wikitext(page_content)

    def _classify(self, item: Item) -> ItemKind:
        """Classify item kind.

        Args:
            item: Item entity

        Returns:
            ItemKind classification
        """
        return classify_item_kind(
            required_slot=item.required_slot,
            teach_spell=item.teach_spell,
            teach_skill=item.teach_skill,
            template_flag=item.template,
            click_effect=item.item_effect_on_click,
            disposable=bool(item.disposable),
        )

    def _generate_general_item_page(self, item: Item, page_title: str) -> str:
        """Generate page for general items (consumables, molds, ability books, etc).

        Args:
            item: Item entity
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} template
        """
        context = self._build_item_template_context(item, page_title)
        return self.render_template("item.jinja2", context)

    def _generate_weapon_page(self, item: Item, page_title: str) -> str:
        """Generate page for weapons.

        Currently generates {{Item}} template only. Multi-tier {{Fancy-weapon}}
        templates will be added when ItemStats repository query is available.

        Args:
            item: Item entity
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} template (fancy templates deferred)
        """
        # TODO: Add {{Fancy-weapon}} templates when ItemStats query exists
        context = self._build_item_template_context(item, page_title)
        return self.render_template("item.jinja2", context)

    def _generate_armor_page(self, item: Item, page_title: str) -> str:
        """Generate page for armor.

        Currently generates {{Item}} template only. Multi-tier {{Fancy-armor}}
        templates will be added when ItemStats repository query is available.

        Args:
            item: Item entity
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} template (fancy templates deferred)
        """
        # TODO: Add {{Fancy-armor}} templates when ItemStats query exists
        context = self._build_item_template_context(item, page_title)
        return self.render_template("item.jinja2", context)

    def _generate_charm_page(self, item: Item, page_title: str) -> str:
        """Generate page for charms.

        Currently generates {{Item}} template only. {{Fancy-charm}} template
        will be added when charm stats data is available.

        Args:
            item: Item entity
            page_title: Wiki page title

        Returns:
            Wikitext with {{Item}} template (fancy template deferred)
        """
        # TODO: Add {{Fancy-charm}} template when charm stats data available
        context = self._build_item_template_context(item, page_title)
        return self.render_template("item.jinja2", context)

    def _build_item_template_context(self, item: Item, page_title: str) -> dict[str, str]:
        """Build context for {{Item}} template.

        Converts Item entity to template context dict. Handles None values,
        formats booleans, and provides empty strings for fields without data.

        Args:
            item: Item entity
            page_title: Wiki page title

        Returns:
            Template context dict
        """

        # Build context with all {{Item}} template fields
        context: dict[str, str] = {
            "title": page_title,
            "image": f"[[File:{item.resource_name}.png]]",  # TODO: Use registry for image name
            "imagecaption": "",
            "type": "",  # TODO: Build from item kind + quest/crafting flags
            "vendorsource": "",  # TODO: Source enrichment (future task)
            "source": "",  # TODO: Source enrichment (future task)
            "othersource": "",  # TODO: Source enrichment (future task)
            "questsource": "",  # TODO: Source enrichment (future task)
            "relatedquest": "",  # TODO: Source enrichment (future task)
            "craftsource": "",  # TODO: Source enrichment (future task)
            "componentfor": "",  # TODO: Source enrichment (future task)
            "relic": "True" if item.relic else "",
            "classes": safe_str(item.classes),
            "effects": "",  # TODO: Parse item_effect_on_click
            "damage": "",  # TODO: Extract from item or stats
            "delay": safe_str(item.weapon_dly) if item.weapon_dly else "",
            "dps": "",  # TODO: Calculate damage / delay
            "casttime": safe_str(item.spell_cast_time) if item.spell_cast_time else "",
            "duration": "",  # TODO: Extract from spell effect
            "cooldown": "",  # TODO: Extract from spell effect
            "description": safe_str(item.lore),
            "buy": safe_str(item.item_value) if item.item_value else "",
            "sell": safe_str(item.sell_value) if item.sell_value else "",
            "itemid": safe_str(item.id),
            "crafting": "",  # TODO: Crafting results (future task)
            "recipe": "",  # TODO: Recipe ingredients (future task)
        }

        return context

"""Ability book item generator.

Handles ability books (items that teach spells/skills).
"""

from __future__ import annotations

import logging

from sqlalchemy.engine import Engine

from erenshor.application.generators.items.base import ItemGeneratorBase
from erenshor.application.models import RenderedBlock
from erenshor.domain.entities import DbItem
from erenshor.domain.entities.spell import DbSkill, DbSpell
from erenshor.infrastructure.templates.contexts import AbilityBookInfoboxContext
from erenshor.infrastructure.templates.engine import render_template
from erenshor.registry.links import RegistryLinkResolver
from erenshor.shared.game_constants import WIKITEXT_LINE_SEPARATOR
from erenshor.shared.text import normalize_wikitext, parse_name_and_id

__all__ = ["AbilityBookGenerator"]


logger = logging.getLogger(__name__)


class AbilityBookGenerator(ItemGeneratorBase):
    """Generator for ability book items."""

    def __init__(self) -> None:
        """Initialize ability book generator."""
        super().__init__()
        self._spell_cache: dict[str, DbSpell] = {}
        self._skill_cache: dict[str, DbSkill] = {}

    def _get_spell_cached(self, engine: Engine, spell_id: str) -> DbSpell | None:
        """Get spell from cache or database.

        Args:
            engine: Database engine
            spell_id: Spell ID

        Returns:
            Spell object or None
        """
        from erenshor.infrastructure.database.repositories import get_spell_by_id

        if spell_id in self._spell_cache:
            return self._spell_cache[spell_id]
        sp = get_spell_by_id(engine, spell_id)
        if sp is not None:
            self._spell_cache[spell_id] = sp
        return sp

    def _get_skill_cached(self, engine: Engine, skill_id: str) -> DbSkill | None:
        """Get skill from cache or database.

        Args:
            engine: Database engine
            skill_id: Skill ID

        Returns:
            Skill object or None
        """
        from erenshor.infrastructure.database.repositories import get_skill_by_id

        if skill_id in self._skill_cache:
            return self._skill_cache[skill_id]
        sk = get_skill_by_id(engine, skill_id)
        if sk is not None:
            self._skill_cache[skill_id] = sk
        return sk

    def generate_ability_book_block(
        self,
        engine: Engine,
        item: DbItem,
        page_title: str,
        linker: RegistryLinkResolver,
        vendor_sources: list[str],
        drop_sources: list[str],
        quest_sources: list[str],
        related_quests: list[str],
        craft_sources: list[str],
        comp_for: list[str],
    ) -> RenderedBlock:
        """Generate ability book block.

        Args:
            engine: Database engine
            item: Database item
            page_title: Wiki page title
            linker: Link resolver
            vendor_sources: Vendor source links
            drop_sources: Drop source links
            quest_sources: Quest source links
            related_quests: Related quest links
            craft_sources: Crafting source links
            comp_for: Component usage links

        Returns:
            Rendered block for ability book
        """
        buy_value = str(item.ItemValue or "") if vendor_sources else ""

        # Check if this teaches a spell or a skill
        spell_id = None
        skill_id = None
        if item.TeachSpell and item.TeachSpell.strip():
            parsed = parse_name_and_id(item.TeachSpell)
            if parsed:
                _, spell_id = parsed
        elif item.TeachSkill and item.TeachSkill.strip():
            parsed = parse_name_and_id(item.TeachSkill)
            if parsed:
                _, skill_id = parsed

        spell = self._get_spell_cached(engine, spell_id) if spell_id else None
        skill = self._get_skill_cached(engine, skill_id) if skill_id else None

        # Build context fields based on whether it's a spell or skill
        if spell:
            description = spell.SpellDesc
            spelltype = spell.Type or ""
            classes = ", ".join(spell.Classes) if spell.Classes else ""
            effects = f"Learn Spell: [[{spell.SpellName}]]"
            manacost = str(spell.ManaCost)
        elif skill:
            description = skill.SkillDesc
            spelltype = skill.TypeOfSkill or ""
            # Build classes list for skills
            skill_classes_list = []
            class_levels = [
                ("Duelist", skill.DuelistRequiredLevel),
                ("Paladin", skill.PaladinRequiredLevel),
                ("Arcanist", skill.ArcanistRequiredLevel),
                ("Druid", skill.DruidRequiredLevel),
                ("Stormcaller", skill.StormcallerRequiredLevel),
            ]
            for class_name, level in class_levels:
                if level and level > 0:
                    skill_classes_list.append(f"[[{class_name}]] ({level})")
            classes = WIKITEXT_LINE_SEPARATOR.join(skill_classes_list)
            effects = f"Learn Skill: [[{skill.SkillName}]]"
            manacost = ""
        else:
            description = ""
            spelltype = ""
            classes = ""
            effects = ""
            manacost = ""

        # Get image name from registry
        from erenshor.domain.entities.page import EntityRef

        entity_ref = EntityRef.from_item(item)
        image_name = linker.registry.get_image_name(entity_ref)

        book_ctx = AbilityBookInfoboxContext(
            block_id=item.ResourceName,
            title=page_title,
            buy=buy_value,
            sell=str(item.SellValue or ""),
            vendorsource=WIKITEXT_LINE_SEPARATOR.join(vendor_sources)
            if vendor_sources
            else "",
            source=WIKITEXT_LINE_SEPARATOR.join(drop_sources) if drop_sources else "",
            description=description,
            questsource=WIKITEXT_LINE_SEPARATOR.join(quest_sources)
            if quest_sources
            else "",
            relatedquest=WIKITEXT_LINE_SEPARATOR.join(related_quests)
            if related_quests
            else "",
            craftsource=WIKITEXT_LINE_SEPARATOR.join(craft_sources)
            if craft_sources
            else "",
            componentfor=WIKITEXT_LINE_SEPARATOR.join(comp_for) if comp_for else "",
            itemid=item.Id if item.Id is not None else "",
            image=f"{image_name}.png",
            type="[[Ability Books]]",
            spelltype=spelltype,
            classes=classes,
            effects=effects,
            manacost=manacost,
        )

        book_rendered = normalize_wikitext(
            render_template("items/ability_book.j2", book_ctx)
        )
        return RenderedBlock(
            page_title=page_title,
            block_id=item.ResourceName,
            template_key="Infobox_item_ability_book",
            text=book_rendered,
        )

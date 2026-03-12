"""Entity page generator.

Generates wiki pages for all game entities (items, characters, spells, skills, stances).
Handles multi-entity pages where multiple entities share the same wiki_page_name.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.wiki.generators.base import GeneratedPage, PageGenerator, PageMetadata
from erenshor.application.wiki.generators.sections.categories import CategoryGenerator
from erenshor.application.wiki.generators.sections.character import CharacterSectionGenerator
from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator
from erenshor.application.wiki.generators.sections.skill import SkillSectionGenerator
from erenshor.application.wiki.generators.sections.spell import SpellSectionGenerator
from erenshor.application.wiki.generators.sections.stance import StanceSectionGenerator
from erenshor.domain.enriched_data.character import EnrichedCharacterData
from erenshor.domain.enriched_data.item import EnrichedItemData
from erenshor.domain.enriched_data.skill import EnrichedSkillData
from erenshor.domain.enriched_data.spell import EnrichedSpellData
from erenshor.domain.enriched_data.stance import EnrichedStanceData
from erenshor.domain.entities import Character, Item, Skill, Spell, Stance
from erenshor.domain.value_objects.proc_info import ProcInfo
from erenshor.domain.value_objects.source_info import SourceInfo
from erenshor.domain.value_objects.wiki_link import AbilityLink, ItemLink, WikiLink

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.context import GeneratorContext

AnyEnriched = EnrichedItemData | EnrichedCharacterData | EnrichedSpellData | EnrichedSkillData | EnrichedStanceData


class EntityPageGenerator(PageGenerator):
    """Generates wiki pages for all game entities.

    Groups entities by wiki_page_name and generates one page per unique title.
    Each page contains templates for ALL entities sharing that wiki_page_name.
    Data is assembled inline from direct repository calls — no enricher classes.
    """

    def __init__(self, context: GeneratorContext) -> None:
        self.item_generator = ItemSectionGenerator(context.class_display)
        self.character_generator = CharacterSectionGenerator()
        self.spell_generator = SpellSectionGenerator(context.class_display)
        self.skill_generator = SkillSectionGenerator(context.class_display)
        self.stance_generator = StanceSectionGenerator()
        self.category_generator = CategoryGenerator()
        super().__init__(context)

        self._cached_entities: list[Item | Character | Spell | Skill | Stance] | None = None

    def _load_entities(self) -> list[Item | Character | Spell | Skill | Stance]:
        if self._cached_entities is not None:
            return self._cached_entities

        all_entities: list[Item | Character | Spell | Skill | Stance] = []
        all_entities.extend(self.context.item_repo.get_items_for_wiki_generation())
        all_entities.extend(self.context.character_repo.get_characters_for_wiki_generation())
        all_entities.extend(self.context.spell_repo.get_spells_for_wiki_generation())
        all_entities.extend(self.context.skill_repo.get_skills_for_wiki_generation())
        all_entities.extend(self.context.stance_repo.get_all())

        self._cached_entities = all_entities
        return all_entities

    def get_pages_to_fetch(self) -> list[str]:
        all_entities = self._load_entities()

        page_titles = list({entity.wiki_page_name for entity in all_entities if entity.wiki_page_name is not None})

        items_count = sum(1 for e in all_entities if isinstance(e, Item))
        characters_count = sum(1 for e in all_entities if isinstance(e, Character))
        spells_count = sum(1 for e in all_entities if isinstance(e, Spell))
        skills_count = sum(1 for e in all_entities if isinstance(e, Skill))
        stances_count = sum(1 for e in all_entities if isinstance(e, Stance))

        logger.info(
            f"EntityPageGenerator: {len(page_titles)} unique pages from {len(all_entities)} entities "
            f"(items={items_count}, characters={characters_count}, spells={spells_count}, "
            f"skills={skills_count}, stances={stances_count})"
        )

        return page_titles

    def generate_pages(self) -> Iterator[GeneratedPage]:
        all_entities = self._load_entities()

        # Group entities by wiki_page_name (all entities in clean DB have one)
        page_groups: dict[str, list[Item | Character | Spell | Skill | Stance]] = {}
        for entity in all_entities:
            page_title = entity.wiki_page_name
            if page_title is None:
                logger.debug(f"Skipping entity with no wiki_page_name: {entity.stable_key}")
                continue
            if page_title not in page_groups:
                page_groups[page_title] = []
            page_groups[page_title].append(entity)

        logger.info(f"Generating {len(page_groups)} pages from {len(all_entities)} entities")

        for page_title, entities in page_groups.items():
            entities.sort(key=self._entity_sort_key)

            # Assemble enriched data inline for each entity
            enriched_entities: list[AnyEnriched] = []
            for entity in entities:
                if isinstance(entity, Item):
                    enriched_entities.append(self._assemble_item(entity))
                elif isinstance(entity, Character):
                    enriched_entities.append(self._assemble_character(entity))
                elif isinstance(entity, Spell):
                    enriched_entities.append(self._assemble_spell(entity))
                elif isinstance(entity, Skill):
                    enriched_entities.append(self._assemble_skill(entity))
                elif isinstance(entity, Stance):
                    enriched_entities.append(self._assemble_stance(entity))
                else:
                    logger.warning(f"Unknown entity type: {type(entity)}")

            # Generate templates for each enriched entity
            templates = []
            for enriched in enriched_entities:
                if isinstance(enriched, EnrichedItemData):
                    template = self.item_generator.generate_template(enriched, page_title)
                elif isinstance(enriched, EnrichedCharacterData):
                    template = self.character_generator.generate_template(enriched, page_title)
                elif isinstance(enriched, EnrichedSpellData):
                    template = self.spell_generator.generate_template(enriched, page_title)
                elif isinstance(enriched, EnrichedSkillData):
                    template = self.skill_generator.generate_template(enriched, page_title)
                elif isinstance(enriched, EnrichedStanceData):
                    template = self.stance_generator.generate_template(enriched, page_title)
                else:
                    continue
                templates.append(template)

            entity_content = (
                "\n\n----\n\n".join(templates) if len(templates) > 1 else (templates[0] if templates else "")
            )

            all_categories: list[str] = []
            for enriched in enriched_entities:
                all_categories.extend(self.category_generator.generate_categories(enriched))
            categories = list(dict.fromkeys(all_categories))
            category_wikitext = self.category_generator.format_category_tags(categories)

            full_content = f"{entity_content}\n\n{category_wikitext}".strip()

            stable_keys = [entity.stable_key for entity in entities]

            yield GeneratedPage(
                title=page_title,
                content=full_content,
                metadata=PageMetadata(
                    summary="Update entity data from game export",
                    minor=False,
                ),
                stable_keys=stable_keys,
            )

        logger.info(f"EntityPageGenerator: Generated {len(page_groups)} pages")

    def _entity_sort_key(self, entity: Item | Character | Spell | Skill | Stance) -> tuple[int, str, int, str]:
        """Sort key for ordering entities within a multi-entity page.

        Spells with class restrictions sort before those without (the
        player-castable version is the "primary" spell). Characters sort
        by zone then level descending. All ties break on stable_key.
        """
        if isinstance(entity, Spell):
            has_classes = 0 if self.context.spell_repo.get_spell_classes(entity.stable_key) else 1
            return (has_classes, "", 0, entity.stable_key)
        if isinstance(entity, Character):
            zone = entity.scene or ""
            level = -(entity.level or 0)
            return (0, zone, level, entity.stable_key)
        return (0, "", 0, entity.stable_key)

    # -------------------------------------------------------------------------
    # Inline assembly — replaces enricher classes
    # -------------------------------------------------------------------------

    def _assemble_character(self, character: Character) -> EnrichedCharacterData:
        spawn_infos = self.context.spawn_repo.get_spawn_info_for_character(character.stable_key)
        loot_drops = self.context.loot_repo.get_loot_for_character(character.stable_key)
        spells = self.context.spell_repo.get_spells_used_by_character(character.stable_key)
        return EnrichedCharacterData(
            character=character,
            spawn_infos=spawn_infos,
            loot_drops=loot_drops,
            spells=spells,
        )

    def _assemble_item(self, item: Item) -> EnrichedItemData:
        stats = self.context.item_repo.get_item_stats(item.stable_key)
        classes = self.context.item_repo.get_item_classes(item.stable_key)
        proc = self._extract_proc(item)
        sources = self._assemble_source_info(item)

        aura_spell = None
        if item.aura_stable_key:
            aura_spell = self.context.spell_repo.get_spell_by_stable_key(item.aura_stable_key)

        taught_spell = None
        taught_spell_classes: list[str] = []
        if item.teach_spell_stable_key:
            taught_spell = self.context.spell_repo.get_spell_by_stable_key(item.teach_spell_stable_key)
            taught_spell_classes = self.context.spell_repo.get_spell_classes(item.teach_spell_stable_key)

        taught_skill = None
        if item.teach_skill_stable_key:
            taught_skill = self.context.skill_repo.get_skill_by_stable_key(item.teach_skill_stable_key)

        return EnrichedItemData(
            item=item,
            stats=stats,
            classes=classes,
            proc=proc,
            sources=sources,
            aura_spell=aura_spell,
            taught_spell=taught_spell,
            taught_spell_classes=taught_spell_classes,
            taught_skill=taught_skill,
        )

    def _extract_proc(self, item: Item) -> ProcInfo | None:
        """Extract proc information from item fields, returning a ProcInfo with pre-built link."""
        is_weapon_slot = item.required_slot in ("Primary", "Secondary", "PrimaryOrSecondary")

        def _make_proc(stable_key: str, chance: str, style: str) -> ProcInfo | None:
            spell = self.context.spell_repo.get_spell_by_stable_key(stable_key)
            if spell is None:
                return None
            proc_link = AbilityLink(
                page_title=spell.wiki_page_name,
                display_name=spell.display_name or spell.spell_name or "",
                image_name=spell.image_name,
            )
            return ProcInfo(
                proc_link=proc_link,
                description=spell.spell_desc or "",
                proc_chance=chance,
                proc_style=style,
                spell=spell,
            )

        if item.weapon_proc_on_hit_stable_key and (item.weapon_proc_chance or 0) > 0:
            style = "Bash" if item.shield else "Attack" if is_weapon_slot else "Cast"
            chance = str(int(item.weapon_proc_chance)) if item.weapon_proc_chance is not None else "0"
            return _make_proc(item.weapon_proc_on_hit_stable_key, chance, style)

        if item.wand_effect_stable_key and (item.wand_proc_chance or 0) > 0:
            chance = str(int(item.wand_proc_chance)) if item.wand_proc_chance is not None else "0"
            return _make_proc(item.wand_effect_stable_key, chance, "Attack")

        if item.bow_effect_stable_key and (item.bow_proc_chance or 0) > 0:
            chance = str(int(item.bow_proc_chance)) if item.bow_proc_chance is not None else "0"
            return _make_proc(item.bow_effect_stable_key, chance, "Attack")

        if item.worn_effect_stable_key:
            return _make_proc(item.worn_effect_stable_key, "", "Worn")

        if item.item_effect_on_click_stable_key:
            return _make_proc(item.item_effect_on_click_stable_key, "", "Activatable")

        return None

    def _assemble_source_info(self, item: Item) -> SourceInfo:
        vendors = self.context.character_repo.get_vendors_selling_item(item.stable_key)

        char_drops = self.context.character_repo.get_characters_dropping_item(item.stable_key)
        item_sources = self.context.item_repo.get_item_sources(item.stable_key)
        drops: list[tuple[WikiLink, float]] = [*char_drops, *item_sources]

        quest_rewards = self.context.quest_repo.get_quests_rewarding_item(item.stable_key)
        quest_requirements = self.context.quest_repo.get_quests_requiring_item(item.stable_key)

        craft_sources_links = self.context.item_repo.get_items_producing_item(item.stable_key)
        component_for = self.context.item_repo.get_items_requiring_item(item.stable_key)

        # Build craft_recipe from the first mold's recipe.
        # Query the first mold's stable key directly from crafting_rewards.
        craft_recipe: list[tuple[ItemLink, int]] = []
        if craft_sources_links:
            first_mold_rows = self._execute_raw_direct(
                """
                SELECT cr.recipe_item_stable_key
                FROM crafting_rewards cr
                WHERE cr.reward_item_stable_key = ?
                LIMIT 1
                """,
                (item.stable_key,),
            )
            if first_mold_rows:
                mold_stable_key = str(first_mold_rows[0]["recipe_item_stable_key"])
                recipe = self.context.item_repo.get_crafting_recipe(mold_stable_key)
                if recipe:
                    # Mold itself (1x)
                    craft_recipe.append((craft_sources_links[0], 1))
                    craft_recipe.extend(recipe.materials)

        crafting_results: list[tuple[ItemLink, int]] = []
        recipe_ingredients: list[tuple[ItemLink, int]] = []
        own_recipe = self.context.item_repo.get_crafting_recipe(item.stable_key)
        if own_recipe:
            crafting_results = own_recipe.results
            recipe_ingredients = own_recipe.materials

        item_drops = self.context.item_repo.get_item_drops(item.stable_key)

        return SourceInfo(
            vendors=vendors,
            drops=drops,
            quest_rewards=quest_rewards,
            quest_requirements=quest_requirements,
            craft_sources=craft_sources_links,
            craft_recipe=craft_recipe,
            component_for=component_for,
            crafting_results=crafting_results,
            recipe_ingredients=recipe_ingredients,
            item_drops=item_drops,
        )

    def _execute_raw_direct(self, query: str, params: tuple) -> list:  # type: ignore[type-arg]
        """Execute a raw query via the item repository's connection (convenience helper)."""
        return self.context.item_repo._execute_raw(query, params)

    def _assemble_spell(self, spell: Spell) -> EnrichedSpellData:
        obtainable_teaching_items = self.context.item_repo.get_obtainable_items_that_teach_spell(spell.stable_key)

        classes: list[str] = []
        if obtainable_teaching_items:
            classes = self.context.spell_repo.get_spell_classes(spell.stable_key)

        items_with_effect = self.context.item_repo.get_items_with_spell_effect(spell.stable_key)
        used_by_characters = self.context.character_repo.get_characters_using_spell(spell.stable_key)

        pet_to_summon = None
        if spell.pet_to_summon_stable_key:
            pet_to_summon = self.context.character_repo.get_character_link(spell.pet_to_summon_stable_key)

        return EnrichedSpellData(
            spell=spell,
            classes=classes,
            items_with_effect=items_with_effect,
            teaching_items=obtainable_teaching_items,
            used_by_characters=used_by_characters,
            pet_to_summon=pet_to_summon,
        )

    def _assemble_skill(self, skill: Skill) -> EnrichedSkillData:
        obtainable_teaching_items = self.context.item_repo.get_obtainable_items_that_teach_skill(skill.stable_key)
        items_with_effect = self.context.item_repo.get_items_with_skill_effect(skill.stable_key)

        activated_stance: AbilityLink | None = None
        if skill.stance_to_use_stable_key:
            stance = self.context.stance_repo.get_by_stable_key(skill.stance_to_use_stable_key)
            if stance is not None:
                activated_stance = AbilityLink(
                    page_title=stance.wiki_page_name,
                    display_name=stance.display_name or "",
                    image_name=stance.image_name,
                )

        effect_to_apply: AbilityLink | None = None
        if skill.effect_to_apply_stable_key:
            spell = self.context.spell_repo.get_spell_by_stable_key(skill.effect_to_apply_stable_key)
            if spell is not None:
                effect_to_apply = AbilityLink(
                    page_title=spell.wiki_page_name,
                    display_name=spell.display_name or spell.spell_name or "",
                    image_name=spell.image_name,
                )

        cast_on_target: AbilityLink | None = None
        if skill.cast_on_target_stable_key:
            spell = self.context.spell_repo.get_spell_by_stable_key(skill.cast_on_target_stable_key)
            if spell is not None:
                cast_on_target = AbilityLink(
                    page_title=spell.wiki_page_name,
                    display_name=spell.display_name or spell.spell_name or "",
                    image_name=spell.image_name,
                )

        spawn_on_use = None
        if skill.spawn_on_use_stable_key:
            spawn_on_use = self.context.character_repo.get_character_link(skill.spawn_on_use_stable_key)

        return EnrichedSkillData(
            skill=skill,
            items_with_effect=items_with_effect,
            teaching_items=obtainable_teaching_items,
            activated_stance=activated_stance,
            effect_to_apply=effect_to_apply,
            cast_on_target=cast_on_target,
            spawn_on_use=spawn_on_use,
        )

    def _assemble_stance(self, stance: Stance) -> EnrichedStanceData:
        activated_by_skills = self.context.skill_repo.get_skills_using_stance(stance.stable_key)
        return EnrichedStanceData(
            stance=stance,
            activated_by_skills=activated_by_skills,
        )

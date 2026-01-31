"""Entity page generator.

Generates wiki pages for all game entities (items, characters, spells, skills).
Handles multi-entity pages where multiple entities share the same page title.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.enrichers.character_enricher import CharacterEnricher
from erenshor.application.enrichers.item_enricher import ItemEnricher
from erenshor.application.enrichers.skill_enricher import SkillEnricher
from erenshor.application.enrichers.spell_enricher import SpellEnricher
from erenshor.application.enrichers.stance_enricher import StanceEnricher
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

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.context import GeneratorContext


class EntityPageGenerator(PageGenerator):
    """Generates wiki pages for all game entities.

    This generator handles all entity types (items, characters, spells, skills, stances)
    and correctly handles multi-entity pages where multiple entities share
    the same page title.

    For example, a page might contain:
    - Multiple spell tiers (Fireball I, Fireball II, Fireball III)
    - Both a skill and spell (Aura: Blessing of Stone)
    - Multiple item variants

    The generator groups entities by page title and generates templates for
    ALL entities on each page.
    """

    def __init__(self, context: GeneratorContext) -> None:
        """Initialize entity page generator.

        Args:
            context: Shared context with repositories and resolver
        """
        super().__init__(context)

        # Initialize enrichers
        self.item_enricher = ItemEnricher(
            item_repo=context.item_repo,
            spell_repo=context.spell_repo,
            skill_repo=context.skill_repo,
            character_repo=context.character_repo,
            quest_repo=context.quest_repo,
        )
        self.character_enricher = CharacterEnricher(
            spawn_repo=context.spawn_repo,
            loot_repo=context.loot_repo,
            spell_repo=context.spell_repo,
        )
        self.spell_enricher = SpellEnricher(
            spell_repo=context.spell_repo,
            item_repo=context.item_repo,
            character_repo=context.character_repo,
        )
        self.skill_enricher = SkillEnricher(
            item_repo=context.item_repo,
            stance_repo=context.stance_repo,
        )
        self.stance_enricher = StanceEnricher(
            skill_repo=context.skill_repo,
        )

        # Initialize section generators
        self.item_generator = ItemSectionGenerator(context.resolver, context.class_display)
        self.character_generator = CharacterSectionGenerator(context.resolver)
        self.spell_generator = SpellSectionGenerator(context.resolver, context.class_display)
        self.skill_generator = SkillSectionGenerator(context.resolver, context.class_display)
        self.stance_generator = StanceSectionGenerator(context.resolver)
        self.category_generator = CategoryGenerator(context.resolver)

        # Cache for entities (populated by _load_entities, reused by both fetch and generate)
        self._cached_entities: list[Item | Character | Spell | Skill | Stance] | None = None

    def _load_entities(self) -> list[Item | Character | Spell | Skill | Stance]:
        """Load all entities from repositories.

        Returns:
            List of all entities for wiki generation
        """
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
        """Return all entity page titles to fetch from wiki.

        Fetches entities from all repositories and deduplicates page titles
        to handle multi-entity pages.

        Returns:
            Unique list of wiki page titles for all entities
        """
        all_entities = self._load_entities()

        # Resolve page titles and deduplicate (filter out None for excluded entities)
        page_titles = [
            title
            for title in {self.context.resolver.resolve_page_title(entity.stable_key) for entity in all_entities}
            if title is not None
        ]

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
        """Generate complete wiki pages for all entities.

        Groups entities by page title and generates one page per unique title.
        Each page contains templates for ALL entities sharing that page title.

        Yields:
            GeneratedPage objects with entity content and metadata
        """
        all_entities = self._load_entities()

        # Group entities by page title (filter out excluded entities where page_title is None)
        page_groups: dict[str, list[Item | Character | Spell | Skill | Stance]] = {}
        for entity in all_entities:
            page_title = self.context.resolver.resolve_page_title(entity.stable_key)
            if page_title is None:
                logger.debug(f"Skipping excluded entity: {entity.stable_key}")
                continue
            if page_title not in page_groups:
                page_groups[page_title] = []
            page_groups[page_title].append(entity)

        logger.info(f"Generating {len(page_groups)} pages from {len(all_entities)} entities")

        for page_title, entities in page_groups.items():
            # Enrich all entities first
            enriched_entities: list[
                EnrichedItemData | EnrichedCharacterData | EnrichedSpellData | EnrichedSkillData | EnrichedStanceData
            ] = []
            for entity in entities:
                if isinstance(entity, Item):
                    enriched_entities.append(self.item_enricher.enrich(entity))
                elif isinstance(entity, Character):
                    enriched_entities.append(self.character_enricher.enrich(entity))
                elif isinstance(entity, Spell):
                    enriched_entities.append(self.spell_enricher.enrich(entity))
                elif isinstance(entity, Skill):
                    enriched_entities.append(self.skill_enricher.enrich(entity))
                elif isinstance(entity, Stance):
                    enriched_entities.append(self.stance_enricher.enrich(entity))
                else:
                    logger.warning(f"Unknown entity type: {type(entity)}")

            enriched_entities = self._deduplicate_characters(enriched_entities)

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

            # Combine all entity templates (use horizontal rule separator for multi-entity pages)
            if len(templates) > 1:
                entity_content = "\n\n----\n\n".join(templates)
            else:
                entity_content = templates[0] if templates else ""

            # Generate category tags from first enriched entity
            categories = self.category_generator.generate_categories(enriched_entities[0])
            category_wikitext = self.category_generator.format_category_tags(categories)

            # Combine sections
            full_content = f"{entity_content}\n\n{category_wikitext}".strip()

            # Extract stable keys from all entities on this page
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

    @staticmethod
    def _build_character_dedup_key(
        enriched: EnrichedCharacterData,
        display_name: str,
    ) -> tuple[str, int | None, int | None, tuple[tuple[str | None, float], ...], tuple[str, ...]]:
        """Build a hashable key for deduplicating identical characters.

        Two characters are considered identical if they have the same display
        name, level, effective HP, loot table, and spell list. The display
        name comes from the registry resolver and determines the rendered
        infobox name — characters with different display names always produce
        different template output and must never be merged.

        Other stats (mana, AC, str, dex, etc.) are derived from level and
        guaranteed identical when level + HP match.

        Args:
            enriched: Enriched character data to build key from
            display_name: Registry-resolved display name for this character

        Returns:
            Hashable tuple suitable as a dict key
        """
        loot_key = tuple(sorted((d.item_stable_key, d.drop_probability) for d in enriched.loot_drops))
        spell_key = tuple(sorted(enriched.spells))
        return (
            display_name,
            enriched.character.level,
            enriched.character.effective_hp,
            loot_key,
            spell_key,
        )

    def _deduplicate_characters(
        self,
        enriched_entities: Sequence[
            EnrichedItemData | EnrichedCharacterData | EnrichedSpellData | EnrichedSkillData | EnrichedStanceData
        ],
    ) -> list[EnrichedItemData | EnrichedCharacterData | EnrichedSpellData | EnrichedSkillData | EnrichedStanceData]:
        """Remove duplicate character infoboxes, merging their spawn info.

        Multiple Character entities can share the same NPCName (prefab copies,
        placed instances, disabled variants). When they have identical stats,
        loot, and spells, only the first is kept and spawn_infos from all
        duplicates are merged into it.

        Non-character entities pass through unchanged.

        Args:
            enriched_entities: Mixed list of enriched entities for one page

        Returns:
            Filtered list with duplicate characters removed
        """
        result: list[
            EnrichedItemData | EnrichedCharacterData | EnrichedSpellData | EnrichedSkillData | EnrichedStanceData
        ] = []
        seen_characters: dict[
            tuple[str, int | None, int | None, tuple[tuple[str | None, float], ...], tuple[str, ...]],
            EnrichedCharacterData,
        ] = {}
        duplicate_count = 0

        for enriched in enriched_entities:
            if not isinstance(enriched, EnrichedCharacterData):
                result.append(enriched)
                continue

            display_name = self.context.resolver.resolve_display_name(enriched.character.stable_key)
            key = self._build_character_dedup_key(enriched, display_name)
            if key in seen_characters:
                seen_characters[key].spawn_infos.extend(enriched.spawn_infos)
                duplicate_count += 1
            else:
                seen_characters[key] = enriched
                result.append(enriched)

        if duplicate_count > 0:
            logger.debug(f"Deduplicated {duplicate_count} character entities")

        return result

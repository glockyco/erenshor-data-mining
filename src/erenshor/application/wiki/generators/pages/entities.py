"""Entity page generator.

Generates wiki pages for all game entities (items, characters, spells, skills).
Handles multi-entity pages where multiple entities share the same page title.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import TYPE_CHECKING

from loguru import logger

from erenshor.application.enrichers.character_enricher import CharacterEnricher
from erenshor.application.enrichers.item_enricher import ItemEnricher
from erenshor.application.enrichers.skill_enricher import SkillEnricher
from erenshor.application.enrichers.spell_enricher import SpellEnricher
from erenshor.application.wiki.generators.base import GeneratedPage, PageGenerator, PageMetadata
from erenshor.application.wiki.generators.sections.categories import CategoryGenerator
from erenshor.application.wiki.generators.sections.character import CharacterSectionGenerator
from erenshor.application.wiki.generators.sections.item import ItemSectionGenerator
from erenshor.application.wiki.generators.sections.skill import SkillSectionGenerator
from erenshor.application.wiki.generators.sections.spell import SpellSectionGenerator
from erenshor.domain.entities import Character, Item, Skill, Spell

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.context import GeneratorContext


class EntityPageGenerator(PageGenerator):
    """Generates wiki pages for all game entities.

    This generator handles all entity types (items, characters, spells, skills)
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
        )

        # Initialize section generators
        self.item_generator = ItemSectionGenerator(context.resolver)
        self.character_generator = CharacterSectionGenerator(context.resolver)
        self.spell_generator = SpellSectionGenerator(context.resolver)
        self.skill_generator = SkillSectionGenerator(context.resolver)
        self.category_generator = CategoryGenerator(context.resolver)

        # Cache for entities (populated by _load_entities, reused by both fetch and generate)
        self._cached_entities: list[Item | Character | Spell | Skill] | None = None

    def _load_entities(self) -> list[Item | Character | Spell | Skill]:
        """Load all entities from repositories.

        Returns:
            List of all entities for wiki generation
        """
        if self._cached_entities is not None:
            return self._cached_entities

        all_entities: list[Item | Character | Spell | Skill] = []
        all_entities.extend(self.context.item_repo.get_items_for_wiki_generation())
        all_entities.extend(self.context.character_repo.get_characters_for_wiki_generation())
        all_entities.extend(self.context.spell_repo.get_spells_for_wiki_generation())
        all_entities.extend(self.context.skill_repo.get_skills_for_wiki_generation())

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

        logger.info(
            f"EntityPageGenerator: {len(page_titles)} unique pages from {len(all_entities)} entities "
            f"(items={items_count}, characters={characters_count}, spells={spells_count}, skills={skills_count})"
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
        page_groups: dict[str, list[Item | Character | Spell | Skill]] = {}
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
                EnrichedItemData | EnrichedCharacterData | EnrichedSpellData | EnrichedSkillData
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
                else:
                    logger.warning(f"Unknown entity type: {type(entity)}")

            # Generate templates for each enriched entity
            templates = []
            for enriched in enriched_entities:
                from erenshor.domain.enriched_data.character import EnrichedCharacterData
                from erenshor.domain.enriched_data.item import EnrichedItemData
                from erenshor.domain.enriched_data.skill import EnrichedSkillData
                from erenshor.domain.enriched_data.spell import EnrichedSpellData

                if isinstance(enriched, EnrichedItemData):
                    template = self.item_generator.generate_template(enriched, page_title)
                elif isinstance(enriched, EnrichedCharacterData):
                    template = self.character_generator.generate_template(enriched, page_title)
                elif isinstance(enriched, EnrichedSpellData):
                    template = self.spell_generator.generate_template(enriched, page_title)
                elif isinstance(enriched, EnrichedSkillData):
                    template = self.skill_generator.generate_template(enriched, page_title)
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

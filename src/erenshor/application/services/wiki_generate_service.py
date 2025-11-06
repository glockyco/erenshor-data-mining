"""Wiki generate service for creating wiki pages locally.

This service handles generating wiki pages from database entities, merging with
fetched content, and preserving manual edits.
"""

from itertools import chain

from loguru import logger
from rich.console import Console
from rich.progress import track

from erenshor.application.generators.character_template_generator import CharacterTemplateGenerator
from erenshor.application.generators.field_preservation import FieldPreservationHandler
from erenshor.application.generators.item_template_generator import ItemTemplateGenerator
from erenshor.application.generators.legacy_template_remover import LegacyTemplateRemover
from erenshor.application.generators.page_normalizer import PageNormalizer
from erenshor.application.generators.skill_template_generator import SkillTemplateGenerator
from erenshor.application.generators.spell_template_generator import SpellTemplateGenerator
from erenshor.application.services.character_enricher import CharacterEnricher
from erenshor.application.services.wiki_helpers import display_operation_summary, group_entities_by_page_title
from erenshor.application.services.wiki_page import OperationResult, WikiPage
from erenshor.application.services.wiki_storage import WikiStorage
from erenshor.domain.entities import Character, Item, Skill, Spell
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.factions import FactionRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
from erenshor.infrastructure.database.repositories.skills import SkillRepository
from erenshor.infrastructure.database.repositories.spawn_points import SpawnPointRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository
from erenshor.registry.resolver import RegistryResolver


class WikiGenerateService:
    """Service for generating wiki pages locally."""

    def __init__(
        self,
        storage: WikiStorage,
        item_repo: ItemRepository,
        character_repo: CharacterRepository,
        spell_repo: SpellRepository,
        skill_repo: SkillRepository,
        faction_repo: FactionRepository,
        spawn_repo: SpawnPointRepository,
        loot_repo: LootTableRepository,
        registry_resolver: RegistryResolver,
        console: Console | None = None,
    ) -> None:
        """Initialize generate service.

        Args:
            storage: Storage for saving generated pages.
            item_repo: Repository for item entities.
            character_repo: Repository for character entities.
            spell_repo: Repository for spell entities.
            skill_repo: Repository for skill entities.
            faction_repo: Repository for faction data.
            spawn_repo: Repository for spawn point data.
            loot_repo: Repository for loot table data.
            registry_resolver: Resolver for page titles from registry.
            console: Rich console for output (optional).
        """
        self._storage = storage
        self._item_repo = item_repo
        self._character_repo = character_repo
        self._spell_repo = spell_repo
        self._skill_repo = skill_repo
        self._resolver = registry_resolver
        self._console = console or Console()

        # Initialize character enricher
        character_enricher = CharacterEnricher(
            faction_repo=faction_repo,
            spawn_repo=spawn_repo,
            loot_repo=loot_repo,
        )

        # Initialize generators and handlers
        self._item_generator = ItemTemplateGenerator()
        self._character_generator = CharacterTemplateGenerator()
        self._spell_generator = SpellTemplateGenerator()
        self._skill_generator = SkillTemplateGenerator()

        # Store enricher for service orchestration
        self._enricher = character_enricher
        self._preservation_handler = FieldPreservationHandler()
        self._legacy_remover = LegacyTemplateRemover()
        self._page_normalizer = PageNormalizer()

        logger.debug("WikiGenerateService initialized")

    def generate_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        page_titles: list[str] | None = None,
    ) -> OperationResult:
        """Generate wiki pages for all entities or specified page titles.

        Workflow:
        1. Load ALL entities from ALL repositories (or filter by page_titles)
        2. Resolve ALL page titles via registry
        3. Group entities by page title
        4. For each page, generate appropriate templates
        5. Assemble and save locally

        Args:
            dry_run: If True, generate content but don't save to storage.
            limit: Maximum number of pages to generate (for testing).
            page_titles: If specified, only generate these specific page titles. If None, generate all pages.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(
            f"Generating wiki pages (dry_run={dry_run}, limit={limit}, "
            f"page_titles={len(page_titles) if page_titles else 'all'})"
        )

        # Load ALL entities from ALL repositories
        items = self._item_repo.get_items_for_wiki_generation()
        characters = self._character_repo.get_characters_for_wiki_generation()
        spells = self._spell_repo.get_spells_for_wiki_generation()
        skills = self._skill_repo.get_skills_for_wiki_generation()

        all_entities: list[Item | Character | Spell | Skill] = list(chain(items, characters, spells, skills))

        # Group entities by page title
        pages = group_entities_by_page_title(all_entities, self._resolver)
        total_pages = len(pages)

        # Filter by requested page titles if specified
        if page_titles:
            page_titles_set = set(page_titles)
            pages = [p for p in pages if p.title in page_titles_set]
            logger.info(f"Filtered to {len(pages)} pages matching requested titles (out of {total_pages} total)")

        # Apply limit after filtering
        if limit:
            pages = pages[:limit]
            logger.info(f"Limited to {len(pages)} pages")

        # Generate each page
        return self._generate_pages_bulk(pages, dry_run)

    def _generate_pages_bulk(
        self,
        pages: list[WikiPage],
        dry_run: bool,
    ) -> OperationResult:
        """Generate pages using appropriate template generators.

        Args:
            pages: List of WikiPage objects to generate.
            dry_run: If True, skip saving to storage.

        Returns:
            OperationResult with statistics and warnings/errors.
        """
        total = len(pages)
        succeeded = 0
        failed = 0
        skipped = 0
        warnings: list[str] = []
        errors: list[str] = []

        self._console.print(f"\n[bold]Generating {total} wiki pages...[/bold]\n")

        if not pages:
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=["No pages to generate"],
                errors=[],
            )

        # Process each page with progress bar
        for page in track(
            pages,
            description="Processing pages",
            total=total,
        ):
            try:
                # Determine which generator to use and generate templates for each entity
                templates = []

                for entity in page.entities:
                    if isinstance(entity, Item):
                        template = self._item_generator.generate_template(entity, page.title)
                    elif isinstance(entity, Character):
                        enriched = self._enricher.enrich(entity)
                        template = self._character_generator.generate_template(enriched, page.title, self._resolver)
                    elif isinstance(entity, Spell):
                        template = self._spell_generator.generate_template(entity, page.title)
                    elif isinstance(entity, Skill):
                        template = self._skill_generator.generate_template(entity, page.title)
                    else:
                        logger.warning(f"Unknown entity type: {type(entity)}")
                        continue

                    templates.append(template)

                # Concatenate templates
                page_content = "\n\n".join(templates)

                # Fetch existing content for preservation
                existing = self._storage.read_fetched_by_title(page.title)

                # Apply preservation and legacy removal if page exists
                if existing:
                    # Remove legacy templates FIRST (before field preservation)
                    # This ensures {{Character}} → {{Enemy}} conversion happens before
                    # we try to merge Enemy fields, avoiding duplicate templates
                    if self._legacy_remover.has_legacy_templates(existing):
                        migrated_content = self._legacy_remover.remove_legacy_templates(existing)
                        logger.debug(f"Legacy templates migrated: {page.title}")
                    else:
                        migrated_content = existing

                    # Preserve manual edits (after legacy migration)
                    final_content = self._preservation_handler.merge_templates(
                        old_wikitext=migrated_content,
                        new_wikitext=page_content,
                        template_names=["Item", "Enemy", "Ability"],
                    )

                    # Normalize page: merge categories from old + new, move to top, clean spacing
                    final_content = self._page_normalizer.normalize(final_content, page_content)
                else:
                    # New page, just normalize
                    final_content = self._page_normalizer.normalize(page_content)

                # Save to storage (skip in dry-run)
                if not dry_run:
                    self._storage.save_generated_by_title(
                        page.title,
                        page.stable_keys,
                        final_content,
                    )

                succeeded += 1

            except Exception as e:
                error_msg = f"Error generating page {page.title}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        # Display summary
        display_operation_summary(
            console=self._console,
            operation="Generate",
            total=total,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            warnings=warnings,
            errors=errors,
            dry_run=dry_run,
        )

        return OperationResult(
            total=total,
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            warnings=warnings,
            errors=errors,
        )

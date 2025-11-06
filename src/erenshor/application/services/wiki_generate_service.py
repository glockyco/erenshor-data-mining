"""Wiki generate service for creating wiki pages locally.

This service handles generating wiki pages from database entities, merging with
fetched content, and preserving manual edits.
"""

from itertools import chain

from loguru import logger
from rich.console import Console
from rich.progress import track

from erenshor.application.generators.categories import CategoryGenerator
from erenshor.application.generators.character_template_generator import CharacterTemplateGenerator
from erenshor.application.generators.field_preservation import FieldPreservationHandler
from erenshor.application.generators.item_template_generator import ItemTemplateGenerator
from erenshor.application.generators.legacy_template_remover import LegacyTemplateRemover
from erenshor.application.generators.page_normalizer import PageNormalizer
from erenshor.application.generators.skill_template_generator import SkillTemplateGenerator
from erenshor.application.generators.spell_template_generator import SpellTemplateGenerator
from erenshor.application.services.character_enricher import CharacterEnricher
from erenshor.application.services.item_enricher import ItemEnricher
from erenshor.application.services.skill_enricher import SkillEnricher
from erenshor.application.services.spell_enricher import SpellEnricher
from erenshor.application.services.wiki_helpers import display_operation_summary, group_entities_by_page_title
from erenshor.application.services.wiki_page import OperationResult, WikiPage
from erenshor.application.services.wiki_storage import WikiStorage
from erenshor.domain.entities import Character, Item, Skill, Spell
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.factions import FactionRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
from erenshor.infrastructure.database.repositories.quests import QuestRepository
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
        quest_repo: QuestRepository,
        registry_resolver: RegistryResolver,
        console: Console | None = None,
    ) -> None:
        """Initialize generate service.

        Args:
            storage: Storage for saving generated pages.
            item_repo: Repository for item entities and related data.
            character_repo: Repository for character entities.
            spell_repo: Repository for spell entities.
            skill_repo: Repository for skill entities.
            faction_repo: Repository for faction data.
            spawn_repo: Repository for spawn point data.
            loot_repo: Repository for loot table data.
            quest_repo: Repository for quest data.
            registry_resolver: Resolver for page titles from registry.
            console: Rich console for output (optional).
        """
        self._storage = storage
        self._item_repo = item_repo
        self._character_repo = character_repo
        self._spell_repo = spell_repo
        self._skill_repo = skill_repo
        self._quest_repo = quest_repo
        self._resolver = registry_resolver
        self._console = console or Console()

        # Initialize enrichers
        self._item_enricher = ItemEnricher(
            item_repo=item_repo,
            spell_repo=spell_repo,
            character_repo=character_repo,
            quest_repo=quest_repo,
        )
        self._character_enricher = CharacterEnricher(
            spawn_repo=spawn_repo,
            loot_repo=loot_repo,
        )
        self._spell_enricher = SpellEnricher(
            spell_repo=spell_repo,
            item_repo=item_repo,
        )
        self._skill_enricher = SkillEnricher(
            item_repo=item_repo,
        )

        # Initialize generators and handlers
        category_generator = CategoryGenerator(registry_resolver)
        self._item_generator = ItemTemplateGenerator(registry_resolver, category_generator)
        self._character_generator = CharacterTemplateGenerator(registry_resolver, category_generator)
        self._spell_generator = SpellTemplateGenerator(registry_resolver)
        self._skill_generator = SkillTemplateGenerator(registry_resolver)

        # Store handlers
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
                        enriched = self._item_enricher.enrich(entity)
                        template = self._item_generator.generate_template(enriched, page.title)
                    elif isinstance(entity, Character):
                        enriched = self._character_enricher.enrich(entity)
                        template = self._character_generator.generate_template(enriched, page.title)
                    elif isinstance(entity, Spell):
                        enriched = self._spell_enricher.enrich(entity)
                        template = self._spell_generator.generate_template(enriched, page.title)
                    elif isinstance(entity, Skill):
                        enriched = self._skill_enricher.enrich(entity)
                        template = self._skill_generator.generate_template(enriched, page.title)
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

                    # Replace fancy tables (Fancy-weapon, Fancy-armor, Fancy-charm)
                    # These tables are 100% generated, no manual content
                    final_content = self._replace_fancy_tables(final_content, page_content)

                    # Normalize page: merge categories from old + new, move to top, clean formatting
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

    def _replace_fancy_tables(self, old_wikitext: str, new_wikitext: str) -> str:
        """Replace fancy content (tables or standalone templates) with freshly generated versions.

        Weapons/Armor: {| |- ||{{Fancy-weapon}}...||...||... |}  (table with 3 quality tiers)
        Charms: {{Fancy-charm\n...\n}}  (single template, charms don't upgrade)

        These contain no manual content and should be completely replaced to ensure
        consistent formatting.

        Args:
            old_wikitext: Existing page content (may have old fancy content)
            new_wikitext: New generated content (has new fancy content)

        Returns:
            Updated wikitext with fancy content replaced
        """
        from mwparserfromhell import parse

        # Parse old content only (we'll extract raw text from new_wikitext)
        old_code = parse(old_wikitext)

        # Find Fancy-* templates in new content (to determine type)
        new_code = parse(new_wikitext)
        fancy_template_names = ["Fancy-weapon", "Fancy-armor", "Fancy-charm"]
        new_fancy_templates = [t for t in new_code.filter_templates() if str(t.name).strip() in fancy_template_names]

        if not new_fancy_templates:
            # No fancy templates in new content
            return old_wikitext

        # Determine if we're dealing with a table or standalone template
        # Tables contain Fancy-weapon or Fancy-armor (3 tiers each)
        # Standalone is Fancy-charm (single template, no table)
        has_weapon_or_armor = any(str(t.name).strip() in ["Fancy-weapon", "Fancy-armor"] for t in new_fancy_templates)

        if has_weapon_or_armor:
            # Find and replace the wiki table containing Fancy-weapon/Fancy-armor
            return self._replace_wiki_table(old_code, new_wikitext, fancy_template_names)
        # Find and replace standalone Fancy-charm template
        return self._replace_fancy_charm_template(old_code, new_wikitext)

    def _replace_wiki_table(self, old_code, new_wikitext: str, fancy_names: list[str]) -> str:
        """Replace wiki table containing Fancy-* templates.

        Args:
            old_code: Parsed old wikitext
            new_wikitext: Raw new wikitext (not parsed, preserves formatting)
            fancy_names: List of fancy template names to look for

        Returns:
            Updated wikitext
        """
        from mwparserfromhell import parse

        # Parse new content to find the table node
        new_code = parse(new_wikitext)

        # Find the table in new content
        new_table_node = None
        for node in new_code.nodes:
            node_str = str(node)
            if node_str.startswith("{|") and any(name in node_str for name in fancy_names):
                new_table_node = node
                break

        if not new_table_node:
            return str(old_code)

        # Get the raw string representation (preserves original formatting from new_wikitext)
        # Find the exact position of this table in the original new_wikitext
        new_wikitext_str = str(new_code)
        table_str = str(new_table_node)

        # The table in new_wikitext should be identical to what we just found
        # So we can use the original from new_wikitext which has correct formatting
        table_start = new_wikitext.find("{|")
        table_end = new_wikitext.find("|}", table_start) + 2
        new_table_raw = new_wikitext[table_start:table_end]

        # Find and replace the table in old content
        for node in old_code.nodes:
            node_str = str(node)
            if node_str.startswith("{|") and any(name in node_str for name in fancy_names):
                old_code.replace(node, new_table_raw)
                logger.debug("Replaced fancy table with raw text")
                return str(old_code)

        # No old table found, insert after {{Item}}
        item_template = self._find_item_template(old_code)
        if item_template:
            # Insert after {{Item}}
            item_index = old_code.index(item_template)
            old_code.insert(item_index + 1, f"\n\n{new_table_raw}")
            logger.debug("Inserted fancy table after {{Item}}")
            return str(old_code)

        # Fallback: append
        old_code.append(f"\n\n{new_table_raw}")
        logger.debug("Appended fancy table")
        return str(old_code)

    def _replace_fancy_charm_template(self, old_code, new_wikitext: str) -> str:
        """Replace standalone Fancy-charm template.

        Args:
            old_code: Parsed old wikitext
            new_wikitext: Raw new wikitext (not parsed, preserves formatting)

        Returns:
            Updated wikitext
        """
        from mwparserfromhell import parse

        # Parse new content to find Fancy-charm template
        new_code = parse(new_wikitext)

        # Find Fancy-charm in new content
        new_charm_node = None
        for node in new_code.filter_templates():
            if str(node.name).strip() == "Fancy-charm":
                new_charm_node = node
                break

        if not new_charm_node:
            return str(old_code)

        # Find the template in the original new_wikitext to preserve formatting
        # Look for {{Fancy-charm at the start and }} at the end
        charm_start = new_wikitext.find("{{Fancy-charm")
        if charm_start == -1:
            return str(old_code)

        # Find the matching closing braces
        # Count opening {{ and closing }} to handle nested templates
        brace_count = 0
        i = charm_start
        while i < len(new_wikitext):
            if new_wikitext[i : i + 2] == "{{":
                brace_count += 1
                i += 2
            elif new_wikitext[i : i + 2] == "}}":
                brace_count -= 1
                if brace_count == 0:
                    new_charm_raw = new_wikitext[charm_start : i + 2]
                    break
                i += 2
            else:
                i += 1
        else:
            # Couldn't find closing braces
            return str(old_code)

        # Find and replace in old content
        for node in old_code.filter_templates():
            if str(node.name).strip() == "Fancy-charm":
                old_code.replace(node, new_charm_raw)
                logger.debug("Replaced {{Fancy-charm}} template with raw text")
                return str(old_code)

        # No old charm, insert after {{Item}}
        item_template = self._find_item_template(old_code)
        if item_template:
            item_index = old_code.index(item_template)
            old_code.insert(item_index + 1, f"\n\n{new_charm_raw}")
            logger.debug("Inserted {{Fancy-charm}} after {{Item}}")
            return str(old_code)

        # Fallback: append
        old_code.append(f"\n\n{new_charm_raw}")
        logger.debug("Appended {{Fancy-charm}}")
        return str(old_code)

    def _find_item_template(self, code):
        """Find {{Item}} template in parsed wikicode.

        Args:
            code: Parsed wikicode

        Returns:
            Item template node or None
        """
        for node in code.filter_templates():
            if str(node.name).strip() == "Item":
                return node
        return None

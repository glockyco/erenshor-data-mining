"""Wiki generate service for creating wiki pages locally.

This service handles generating wiki pages from database entities, merging with
fetched content, and preserving manual edits.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.progress import track

if TYPE_CHECKING:
    import mwparserfromhell
    import mwparserfromhell.nodes
    import mwparserfromhell.wikicode

    from erenshor.application.wiki.generators.base import GeneratedPage
    from erenshor.application.wiki.services.class_display_service import ClassDisplayNameService
    from erenshor.application.wiki.services.storage import WikiStorage
    from erenshor.infrastructure.database.repositories.characters import CharacterRepository
    from erenshor.infrastructure.database.repositories.factions import FactionRepository
    from erenshor.infrastructure.database.repositories.items import ItemRepository
    from erenshor.infrastructure.database.repositories.loot_tables import LootTableRepository
    from erenshor.infrastructure.database.repositories.quests import QuestRepository
    from erenshor.infrastructure.database.repositories.skills import SkillRepository
    from erenshor.infrastructure.database.repositories.spawn_points import SpawnPointRepository
    from erenshor.infrastructure.database.repositories.spells import SpellRepository
    from erenshor.infrastructure.database.repositories.stances import StanceRepository
    from erenshor.registry.resolver import RegistryResolver

from erenshor.application.wiki.generators.context import GeneratorContext
from erenshor.application.wiki.generators.field_preservation import FieldPreservationHandler
from erenshor.application.wiki.generators.legacy_template_remover import LegacyTemplateRemover
from erenshor.application.wiki.generators.page_normalizer import PageNormalizer
from erenshor.application.wiki.generators.registry import get_generators_by_name
from erenshor.application.wiki.services.page import OperationResult


class WikiGenerateService:
    """Service for generating wiki pages locally."""

    def __init__(
        self,
        storage: WikiStorage,
        item_repo: ItemRepository,
        character_repo: CharacterRepository,
        spell_repo: SpellRepository,
        skill_repo: SkillRepository,
        stance_repo: StanceRepository,
        faction_repo: FactionRepository,
        spawn_repo: SpawnPointRepository,
        loot_repo: LootTableRepository,
        quest_repo: QuestRepository,
        registry_resolver: RegistryResolver,
        class_display: ClassDisplayNameService,
        console: Console | None = None,
    ) -> None:
        """Initialize generate service.

        Args:
            storage: Storage for saving generated pages.
            item_repo: Repository for item entities and related data.
            character_repo: Repository for character entities.
            spell_repo: Repository for spell entities.
            skill_repo: Repository for skill entities.
            stance_repo: Repository for stance entities.
            faction_repo: Repository for faction data.
            spawn_repo: Repository for spawn point data.
            loot_repo: Repository for loot table data.
            quest_repo: Repository for quest data.
            registry_resolver: Resolver for page titles from registry.
            class_display: Service for mapping class names to display names.
            console: Rich console for output (optional).
        """
        self._storage = storage
        self._console = console or Console()

        # Create generator context with all dependencies
        self._context = GeneratorContext(
            item_repo=item_repo,
            character_repo=character_repo,
            spell_repo=spell_repo,
            skill_repo=skill_repo,
            stance_repo=stance_repo,
            faction_repo=faction_repo,
            spawn_repo=spawn_repo,
            loot_repo=loot_repo,
            quest_repo=quest_repo,
            resolver=registry_resolver,
            storage=storage,
            class_display=class_display,
        )

        # Handlers for preservation and normalization
        self._preservation_handler = FieldPreservationHandler()
        self._legacy_remover = LegacyTemplateRemover()
        self._page_normalizer = PageNormalizer()

        logger.debug("WikiGenerateService initialized")

    def generate_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        page_titles: list[str] | None = None,
        generator_names: list[str] | None = None,
    ) -> OperationResult:
        """Generate wiki pages using registered generators.

        Workflow:
        1. Instantiate generators from registry
        2. Each generator produces GeneratedPage objects
        3. Apply preservation and normalization
        4. Save to storage

        Args:
            dry_run: If True, generate content but don't save to storage.
            limit: Maximum number of pages to generate (for testing).
            page_titles: If specified, only generate these specific page titles. If None, generate all pages.
            generator_names: Optional list of generator names to use. If None, use all registered generators.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(
            f"Generating wiki pages (dry_run={dry_run}, limit={limit}, "
            f"page_titles={len(page_titles) if page_titles else 'all'}, "
            f"generators={generator_names or 'all'})"
        )

        # Get generators from registry
        generators = get_generators_by_name(self._context, generator_names)
        logger.debug(f"Using {len(generators)} generators")

        # Collect generated pages from all generators
        all_generated_pages = []
        for generator in generators:
            logger.debug(f"Running generator: {generator.__class__.__name__}")
            generated_pages = list(generator.generate_pages())
            all_generated_pages.extend(generated_pages)
            logger.debug(f"  Generated {len(generated_pages)} pages")

        logger.info(f"Total pages generated: {len(all_generated_pages)}")

        # Remove stale metadata/files when doing a full (unfiltered) generation.
        # Stale entries arise when page titles change (e.g., whitespace stripping)
        # and the old entries linger, causing overwrites on MediaWiki.
        if not page_titles and not limit and not generator_names:
            valid_titles = {p.title for p in all_generated_pages}
            removed = self._storage.remove_stale_pages(valid_titles)
            if removed:
                logger.info(f"Cleaned up {removed} stale pages")

        # Filter by requested page titles if specified
        if page_titles:
            page_titles_set = set(page_titles)
            filtered_pages = [p for p in all_generated_pages if p.title in page_titles_set]
            logger.info(
                f"Filtered to {len(filtered_pages)} pages matching requested titles "
                f"(out of {len(all_generated_pages)} total)"
            )
            all_generated_pages = filtered_pages

        # Apply limit after filtering
        if limit:
            all_generated_pages = all_generated_pages[:limit]
            logger.info(f"Limited to {len(all_generated_pages)} pages")

        # Process and save pages
        return self._process_generated_pages(all_generated_pages, dry_run)

    def _process_generated_pages(
        self,
        generated_pages: list[GeneratedPage],
        dry_run: bool,
    ) -> OperationResult:
        """Process generated pages with preservation and normalization.

        Args:
            generated_pages: List of GeneratedPage objects from generators.
            dry_run: If True, skip saving to storage.

        Returns:
            OperationResult with statistics and warnings/errors.
        """

        total = len(generated_pages)
        succeeded = 0
        failed = 0
        warnings: list[str] = []
        errors: list[str] = []

        self._console.print(f"\n[bold]Generating {total} wiki pages...[/bold]\n")

        if not generated_pages:
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=["No pages to generate"],
                errors=[],
            )

        # Process each generated page with progress bar
        for gen_page in track(
            generated_pages,
            description="Processing pages",
            total=total,
        ):
            try:
                # Get generated content
                page_content = gen_page.content

                # Fetch existing content for preservation
                existing = self._storage.read_fetched_by_title(gen_page.title)

                # Apply preservation and legacy removal if page exists
                if existing:
                    # Check if this is an overview page (Weapons, Armor)
                    # These pages need special handling: preserve intro, replace table
                    if gen_page.title in ["Weapons", "Armor"]:
                        final_content = self._replace_overview_table(existing, page_content)
                        # Normalize page
                        final_content = self._page_normalizer.normalize(final_content, page_content)
                    else:
                        # Standard entity page processing
                        # Remove legacy templates FIRST
                        if self._legacy_remover.has_legacy_templates(existing):
                            migrated_content = self._legacy_remover.remove_legacy_templates(existing)
                            logger.debug(f"Legacy templates migrated: {gen_page.title}")
                        else:
                            migrated_content = existing

                        # Preserve manual edits
                        final_content = self._preservation_handler.merge_templates(
                            old_wikitext=migrated_content,
                            new_wikitext=page_content,
                            template_names=["Item", "Enemy", "Ability"],
                        )

                        # Replace fancy tables (weapons, armor, charms)
                        final_content = self._replace_fancy_tables(final_content, page_content)

                        # Replace/insert item type templates (aura, spellscroll, skillbook, consumable, mold, general)
                        final_content = self._replace_item_type_templates(final_content, page_content)

                        # Normalize page
                        final_content = self._page_normalizer.normalize(final_content, page_content)
                else:
                    # New page, just normalize
                    final_content = self._page_normalizer.normalize(page_content)

                # Save to storage (skip in dry-run)
                if not dry_run:
                    self._storage.save_generated_by_title(
                        gen_page.title,
                        gen_page.stable_keys,
                        final_content,
                    )

                succeeded += 1

            except Exception as e:
                error_msg = f"Error generating page {gen_page.title}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        # Display summary
        from erenshor.application.wiki.services.helpers import display_operation_summary

        display_operation_summary(
            console=self._console,
            operation="Generate",
            total=total,
            succeeded=succeeded,
            failed=failed,
            skipped=0,
            warnings=warnings,
            errors=errors,
            dry_run=dry_run,
        )

        return OperationResult(
            total=total,
            succeeded=succeeded,
            failed=failed,
            skipped=0,
            warnings=warnings,
            errors=errors,
        )

    def _replace_overview_table(self, old_wikitext: str, new_wikitext: str) -> str:
        """Replace overview page wikitable while preserving intro text.

        Overview pages (Weapons, Armor) have:
        1. Manual intro paragraphs
        2. Large wikitable with game data

        We need to:
        - Preserve the manual intro text
        - Replace the entire wikitable with freshly generated content

        Args:
            old_wikitext: Existing page content (has manual intro + old table)
            new_wikitext: New generated content (has fresh table)

        Returns:
            Updated wikitext with preserved intro and new table
        """
        # Find where the wikitable starts in old content
        old_table_start = old_wikitext.find("{|")

        if old_table_start == -1:
            # No old table found, just return new content
            logger.debug("No wikitable found in old content, using new content")
            return new_wikitext

        # Extract intro text (everything before the table)
        intro_text = old_wikitext[:old_table_start].rstrip()

        # Find the wikitable in new content
        new_table_start = new_wikitext.find("{|")

        if new_table_start == -1:
            # No new table generated, keep old content
            logger.warning("No wikitable in new content, keeping old content")
            return old_wikitext

        # Extract new table (everything from {| onwards)
        new_table = new_wikitext[new_table_start:]

        # Combine: intro + new table
        result = f"{intro_text}\n\n{new_table}"

        logger.debug("Replaced overview wikitable while preserving intro text")
        return result

    def _replace_fancy_tables(self, old_wikitext: str, new_wikitext: str) -> str:
        """Replace item quality tables/templates with freshly generated versions.

        Weapons/Armor: {| |- ||{{Item/Weapon}}...||...||... |}  (table with 3 quality tiers)
        Charms: {{Item/Charm\n...\n}}  (single template, charms don't upgrade)

        Old pages may still have {{Fancy-weapon}}, {{Fancy-armor}}, {{Fancy-charm}}
        which need to be replaced with the new {{Item/Weapon}}, {{Item/Armor}}, {{Item/Charm}}.

        These contain no manual content and should be completely replaced to ensure
        consistent formatting.

        Args:
            old_wikitext: Existing page content (may have old or new templates)
            new_wikitext: New generated content (has new Item/* templates)

        Returns:
            Updated wikitext with item quality templates replaced
        """
        from mwparserfromhell import parse

        # Parse old content only (we'll extract raw text from new_wikitext)
        old_code = parse(old_wikitext)

        # New template names (what we generate now)
        new_template_names = ["Item/Weapon", "Item/Armor", "Item/Charm"]
        # Legacy template names (what old pages may have)
        legacy_template_names = ["Fancy-weapon", "Fancy-armor", "Fancy-charm"]
        # All possible names to look for in old content
        all_template_names = new_template_names + legacy_template_names

        # Find Item/* templates in new content (to determine type)
        new_code = parse(new_wikitext)
        new_item_templates = [t for t in new_code.filter_templates() if str(t.name).strip() in new_template_names]

        if not new_item_templates:
            # No item quality templates in new content
            return old_wikitext

        # Determine if we're dealing with a table or standalone template
        # Tables contain Item/Weapon or Item/Armor (3 tiers each)
        # Standalone is Item/Charm (single template, no table)
        has_weapon_or_armor = any(str(t.name).strip() in ["Item/Weapon", "Item/Armor"] for t in new_item_templates)

        if has_weapon_or_armor:
            # Find and replace the wiki table containing item quality templates
            return self._replace_wiki_table(old_code, new_wikitext, all_template_names)
        # Find and replace standalone charm template
        return self._replace_fancy_charm_template(old_code, new_wikitext)

    def _replace_wiki_table(
        self, old_code: mwparserfromhell.wikicode.Wikicode, new_wikitext: str, template_names: list[str]
    ) -> str:
        """Replace wiki table containing item quality templates.

        Args:
            old_code: Parsed old wikitext
            new_wikitext: Raw new wikitext (not parsed, preserves formatting)
            template_names: List of template names to look for (both new and legacy)

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
            if node_str.startswith("{|") and any(name in node_str for name in template_names):
                new_table_node = node
                break

        if not new_table_node:
            return str(old_code)

        # The table in new_wikitext should be identical to what we just found
        # So we can use the original from new_wikitext which has correct formatting
        table_start = new_wikitext.find("{|")
        table_end = new_wikitext.find("|}", table_start) + 2
        new_table_raw = new_wikitext[table_start:table_end]

        # Find and replace the table in old content (check for both old and new template names)
        for node in old_code.nodes:
            node_str = str(node)
            if node_str.startswith("{|") and any(name in node_str for name in template_names):
                old_code.replace(node, new_table_raw)
                logger.debug("Replaced item quality table with raw text")
                return str(old_code)

        # No old table found, insert after {{Item}}
        item_template = self._find_item_template(old_code)
        if item_template:
            # Insert after {{Item}}
            item_index = old_code.index(item_template)
            old_code.insert(item_index + 1, f"\n\n{new_table_raw}")
            logger.debug("Inserted item quality table after {{Item}}")
            return str(old_code)

        # If no {{Item}} template found, append table at the end
        old_code.append(f"\n\n{new_table_raw}")
        logger.debug("Appended item quality table")
        return str(old_code)

    def _replace_fancy_charm_template(self, old_code: mwparserfromhell.wikicode.Wikicode, new_wikitext: str) -> str:
        """Replace standalone charm template (Item/Charm or legacy Fancy-charm).

        Args:
            old_code: Parsed old wikitext
            new_wikitext: Raw new wikitext (not parsed, preserves formatting)

        Returns:
            Updated wikitext
        """
        from mwparserfromhell import parse

        # New and legacy charm template names
        new_charm_name = "Item/Charm"
        legacy_charm_name = "Fancy-charm"

        # Parse new content to find Item/Charm template
        new_code = parse(new_wikitext)

        # Find Item/Charm in new content
        new_charm_node = None
        for node in new_code.filter_templates():
            if str(node.name).strip() == new_charm_name:
                new_charm_node = node
                break

        if not new_charm_node:
            return str(old_code)

        # Find the template in the original new_wikitext to preserve formatting
        # Look for {{Item/Charm at the start and }} at the end
        charm_start = new_wikitext.find("{{Item/Charm")
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

        # Find and replace in old content (check for both new and legacy charm)
        for node in old_code.filter_templates():
            template_name = str(node.name).strip()
            if template_name in [new_charm_name, legacy_charm_name]:
                old_code.replace(node, new_charm_raw)
                logger.debug(f"Replaced {{{{{template_name}}}}} template with {{{{Item/Charm}}}}")
                return str(old_code)

        # No old charm, insert after {{Item}}
        item_template = self._find_item_template(old_code)
        if item_template:
            item_index = old_code.index(item_template)
            old_code.insert(item_index + 1, f"\n\n{new_charm_raw}")
            logger.debug("Inserted {{Item/Charm}} after {{Item}}")
            return str(old_code)

        # If no {{Item}} template found, append charm template at the end
        old_code.append(f"\n\n{new_charm_raw}")
        logger.debug("Appended {{Item/Charm}}")
        return str(old_code)

    def _find_item_template(self, code: mwparserfromhell.wikicode.Wikicode) -> mwparserfromhell.nodes.Template | None:
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

    def _replace_item_type_templates(self, old_wikitext: str, new_wikitext: str) -> str:
        """Replace or insert ALL item type tooltip templates.

        These are TOOLTIP templates ({{Item/Aura}}, {{Item/SpellScroll}}, etc.) that
        are generated alongside {{Item}} for non-weapon/armor/charm items.

        For multi-item pages (multiple items sharing the same wiki page), this handles
        multiple tooltips by matching them positionally - first new tooltip replaces
        first old tooltip, second new replaces second old, etc.

        Note: Legacy INFOBOX templates ({{Auras}}, {{Ability Books}}, {{Mold}}) are
        handled by LegacyTemplateRemover which converts them to {{Item}}.

        This method:
        1. Finds ALL tooltip templates in new content
        2. Finds ALL tooltip templates in old content
        3. Replaces by position (new[0] -> old[0], new[1] -> old[1], etc.)
        4. Inserts extras after the last {{Item}} if more new than old

        Args:
            old_wikitext: Existing page content (after legacy template removal)
            new_wikitext: New generated content

        Returns:
            Updated wikitext with ALL tooltip templates replaced/inserted
        """
        from mwparserfromhell import parse

        # Tooltip template names (what we generate)
        tooltip_templates = [
            "Item/Aura",
            "Item/SpellScroll",
            "Item/SkillBook",
            "Item/Consumable",
            "Item/Mold",
            "Item/General",
        ]

        # Find ALL tooltip templates in new content (in order)
        new_code = parse(new_wikitext)
        new_tooltip_names: list[str] = []
        for template in new_code.filter_templates():
            name = str(template.name).strip()
            if name in tooltip_templates:
                new_tooltip_names.append(name)

        if not new_tooltip_names:
            # No tooltip templates in new content, nothing to do
            return old_wikitext

        # Extract raw template text for each new tooltip
        # Track occurrence index for each template name to handle multiples of same type
        name_occurrence_count: dict[str, int] = {}
        new_tooltip_raw_list: list[str] = []

        for tooltip_name in new_tooltip_names:
            occurrence_index = name_occurrence_count.get(tooltip_name, 0)
            raw = self._extract_nth_template_raw(new_wikitext, tooltip_name, occurrence_index)
            if raw:
                new_tooltip_raw_list.append(raw)
                name_occurrence_count[tooltip_name] = occurrence_index + 1

        if not new_tooltip_raw_list:
            return old_wikitext

        # Parse old content
        old_code = parse(old_wikitext)

        # Find ALL existing tooltip templates in old content (in order)
        old_tooltip_templates: list[mwparserfromhell.nodes.Template] = []
        for template in old_code.filter_templates():
            name = str(template.name).strip()
            if name in tooltip_templates:
                old_tooltip_templates.append(template)

        # If old page has NO tooltip templates but we have multiple new ones,
        # this is a multi-item legacy page that needs proper structure.
        # Use the new content's structure which has proper interleaving and separators.
        if not old_tooltip_templates and len(new_tooltip_raw_list) > 1:
            logger.debug(f"Multi-item legacy page with {len(new_tooltip_raw_list)} tooltips - using new structure")
            return new_wikitext

        # Replace existing tooltips by position, collect extras to append
        extras_to_append: list[str] = []

        for i, new_raw in enumerate(new_tooltip_raw_list):
            if i < len(old_tooltip_templates):
                # Replace existing tooltip at position i
                old_template = old_tooltip_templates[i]
                old_name = str(old_template.name).strip()
                old_code.replace(old_template, new_raw)
                logger.debug(f"Replaced tooltip {i}: {{{{{old_name}}}}} with {{{{{new_tooltip_names[i]}}}}}")
            else:
                # No more old tooltips at this position, collect for appending
                extras_to_append.append(new_raw)
                logger.debug(f"Will append tooltip {i}: {{{{{new_tooltip_names[i]}}}}}")

        # Append all extra tooltips at the end (preserves order)
        for extra_raw in extras_to_append:
            old_code.append(f"\n\n{extra_raw}")

        return str(old_code)

    def _extract_template_raw(self, wikitext: str, template_name: str) -> str | None:
        """Extract raw template text from wikitext preserving formatting.

        Args:
            wikitext: Raw wikitext
            template_name: Template name to find (e.g., "Item/Aura")

        Returns:
            Raw template text including {{ and }}, or None if not found
        """
        return self._extract_nth_template_raw(wikitext, template_name, 0)

    def _extract_nth_template_raw(self, wikitext: str, template_name: str, n: int = 0) -> str | None:
        """Extract the Nth occurrence of a template from wikitext.

        Args:
            wikitext: Raw wikitext
            template_name: Template name to find (e.g., "Item/General")
            n: 0-based index of which occurrence to extract

        Returns:
            Raw template text including {{ and }}, or None if not found
        """
        search_str = "{{" + template_name
        start = 0
        occurrences_found = 0

        while start < len(wikitext):
            pos = wikitext.find(search_str, start)
            if pos == -1:
                return None

            if occurrences_found == n:
                # Found the Nth occurrence, extract it
                return self._extract_template_at_position(wikitext, pos)

            # Skip past this occurrence and continue searching
            occurrences_found += 1
            start = pos + len(search_str)

        return None

    def _extract_template_at_position(self, wikitext: str, start: int) -> str:
        """Extract template starting at given position.

        Args:
            wikitext: Raw wikitext
            start: Position where template starts (at the first '{')

        Returns:
            Raw template text including {{ and }}
        """
        brace_count = 0
        i = start
        while i < len(wikitext):
            if wikitext[i : i + 2] == "{{":
                brace_count += 1
                i += 2
            elif wikitext[i : i + 2] == "}}":
                brace_count -= 1
                i += 2
                if brace_count == 0:
                    return wikitext[start:i]
            else:
                i += 1
        return wikitext[start:]  # Unclosed template, return rest

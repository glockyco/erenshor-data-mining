"""Wiki service for orchestrating wiki page updates.

This module provides the WikiService class that orchestrates the complete wiki
page update workflow including:
- Fetching existing wiki pages
- Generating new content using page generators
- Preserving manually-edited fields
- Removing legacy templates
- Updating wiki pages via MediaWikiClient
- Push-style progress notifications

The service uses a "fail-soft" approach where individual page failures don't
stop the entire batch, allowing users to see all issues at once.

Example:
    >>> from erenshor.application.services.wiki_service import WikiService
    >>> from erenshor.infrastructure.wiki.client import MediaWikiClient
    >>>
    >>> # Initialize service with dependencies
    >>> wiki_client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php")
    >>> service = WikiService(
    ...     wiki_client=wiki_client,
    ...     item_repo=item_repo,
    ...     character_repo=character_repo,
    ...     spell_repo=spell_repo,
    ... )
    >>>
    >>> # Update item pages with progress display
    >>> result = service.update_item_pages(dry_run=False, limit=10)
    >>> print(f"Updated {result.updated} pages")
    >>> if result.warnings:
    ...     print(f"Warnings: {len(result.warnings)}")
"""

from dataclasses import dataclass
from typing import Any

from loguru import logger
from rich.console import Console
from rich.progress import track

from erenshor.application.generators.character_page_generator import CharacterPageGenerator
from erenshor.application.generators.field_preservation import FieldPreservationHandler
from erenshor.application.generators.item_page_generator import ItemPageGenerator
from erenshor.application.generators.legacy_template_remover import LegacyTemplateRemover
from erenshor.application.generators.spell_page_generator import SpellPageGenerator
from erenshor.domain.entities.character import Character
from erenshor.domain.entities.item import Item
from erenshor.domain.entities.spell import Spell
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository
from erenshor.infrastructure.wiki.client import MediaWikiAPIError, MediaWikiClient


class WikiServiceError(Exception):
    """Base exception for wiki service errors."""

    pass


@dataclass
class UpdateResult:
    """Result of a wiki update operation.

    Attributes:
        total: Total number of pages processed.
        updated: Number of pages successfully updated.
        skipped: Number of pages skipped (no changes needed).
        failed: Number of pages that failed to update.
        warnings: List of warning messages.
        errors: List of error messages.
    """

    total: int
    updated: int
    skipped: int
    failed: int
    warnings: list[str]
    errors: list[str]

    def has_warnings(self) -> bool:
        """Check if result has warnings."""
        return len(self.warnings) > 0

    def has_errors(self) -> bool:
        """Check if result has errors."""
        return len(self.errors) > 0


class WikiService:
    """Service for orchestrating wiki page updates.

    This service coordinates the wiki update workflow:
    1. Fetch entities from database
    2. Generate new wiki content
    3. Fetch existing wiki pages (batched)
    4. Preserve manual edits
    5. Remove legacy templates
    6. Update wiki pages (individual)
    7. Display progress and notifications inline

    The service uses dependency injection for testability and follows
    a "fail-soft" approach where individual failures don't stop the batch.

    Example:
        >>> service = WikiService(
        ...     wiki_client=wiki_client,
        ...     item_repo=item_repo,
        ...     character_repo=character_repo,
        ...     spell_repo=spell_repo,
        ... )
        >>> result = service.update_item_pages(dry_run=False)
        >>> print(f"Updated: {result.updated}, Failed: {result.failed}")
    """

    def __init__(
        self,
        wiki_client: MediaWikiClient,
        item_repo: ItemRepository,
        character_repo: CharacterRepository,
        spell_repo: SpellRepository,
    ) -> None:
        """Initialize wiki service.

        Args:
            wiki_client: MediaWiki API client for fetching/updating pages.
            item_repo: Repository for fetching items from database.
            character_repo: Repository for fetching characters from database.
            spell_repo: Repository for fetching spells from database.
        """
        self._wiki_client = wiki_client
        self._item_repo = item_repo
        self._character_repo = character_repo
        self._spell_repo = spell_repo

        # Initialize generators and handlers
        self._item_generator = ItemPageGenerator()
        self._character_generator = CharacterPageGenerator()
        self._spell_generator = SpellPageGenerator()
        self._preservation_handler = FieldPreservationHandler()
        self._legacy_remover = LegacyTemplateRemover()

        # Console for Rich output
        self._console = Console()

        logger.debug("WikiService initialized")

    def update_item_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> UpdateResult:
        """Update all item wiki pages.

        Generates fresh wiki content for all items and updates the wiki,
        preserving manually-edited fields and removing legacy templates.

        Args:
            dry_run: If True, generate content but don't update wiki.
            limit: Maximum number of items to process (for testing).

        Returns:
            UpdateResult with summary statistics and warnings/errors.

        Example:
            >>> result = service.update_item_pages(dry_run=False, limit=10)
            >>> print(f"Updated {result.updated}/{result.total} pages")
        """
        logger.info(f"Updating item pages (dry_run={dry_run}, limit={limit})")

        # Fetch items from database
        items = self._item_repo.get_items_for_wiki_generation()

        # Apply limit if specified
        if limit is not None:
            items = items[:limit]

        if not items:
            logger.warning("No items found for wiki generation")
            return UpdateResult(
                total=0,
                updated=0,
                skipped=0,
                failed=0,
                warnings=["No items found in database"],
                errors=[],
            )

        # Update items with progress tracking
        return self._update_pages(
            entities=items,
            entity_type="item",
            generator=self._item_generator,
            page_title_fn=lambda item: f"Item:{item.item_name}",
            template_names=["Item"],
            dry_run=dry_run,
        )

    def update_character_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> UpdateResult:
        """Update all character wiki pages.

        Generates fresh wiki content for all characters/enemies and updates
        the wiki, preserving manually-edited fields.

        Args:
            dry_run: If True, generate content but don't update wiki.
            limit: Maximum number of characters to process (for testing).

        Returns:
            UpdateResult with summary statistics and warnings/errors.

        Example:
            >>> result = service.update_character_pages(dry_run=False)
            >>> print(f"Updated {result.updated}/{result.total} pages")
        """
        logger.info(f"Updating character pages (dry_run={dry_run}, limit={limit})")

        # Fetch characters from database
        characters = self._character_repo.get_characters_for_wiki_generation()

        # Apply limit if specified
        if limit is not None:
            characters = characters[:limit]

        if not characters:
            logger.warning("No characters found for wiki generation")
            return UpdateResult(
                total=0,
                updated=0,
                skipped=0,
                failed=0,
                warnings=["No characters found in database"],
                errors=[],
            )

        # Update characters with progress tracking
        return self._update_pages(
            entities=characters,
            entity_type="character",
            generator=self._character_generator,
            page_title_fn=lambda char: f"Character:{char.npc_name}",
            template_names=["Character"],
            dry_run=dry_run,
        )

    def update_spell_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> UpdateResult:
        """Update all spell wiki pages.

        Generates fresh wiki content for all spells/abilities and updates
        the wiki, preserving manually-edited fields.

        Args:
            dry_run: If True, generate content but don't update wiki.
            limit: Maximum number of spells to process (for testing).

        Returns:
            UpdateResult with summary statistics and warnings/errors.

        Example:
            >>> result = service.update_spell_pages(dry_run=False)
            >>> print(f"Updated {result.updated}/{result.total} pages")
        """
        logger.info(f"Updating spell pages (dry_run={dry_run}, limit={limit})")

        # Fetch spells from database
        spells = self._spell_repo.get_spells_for_wiki_generation()

        # Apply limit if specified
        if limit is not None:
            spells = spells[:limit]

        if not spells:
            logger.warning("No spells found for wiki generation")
            return UpdateResult(
                total=0,
                updated=0,
                skipped=0,
                failed=0,
                warnings=["No spells found in database"],
                errors=[],
            )

        # Update spells with progress tracking
        return self._update_pages(
            entities=spells,
            entity_type="spell",
            generator=self._spell_generator,
            page_title_fn=lambda spell: f"Spell:{spell.spell_name}",
            template_names=["Ability"],
            dry_run=dry_run,
        )

    def _update_pages(
        self,
        entities: list[Item] | list[Character] | list[Spell],
        entity_type: str,
        generator: Any,
        page_title_fn: Any,
        template_names: list[str],
        dry_run: bool,
    ) -> UpdateResult:
        """Update wiki pages for a list of entities.

        This is the core update workflow that:
        1. Generates new content for all entities
        2. Fetches existing wiki pages in batches
        3. Preserves manual edits and removes legacy templates
        4. Updates wiki pages individually
        5. Shows progress and inline notifications

        Args:
            entities: List of entities to process.
            entity_type: Entity type name for display.
            generator: Page generator instance.
            page_title_fn: Function to get wiki page title from entity.
            template_names: Template names to preserve/merge.
            dry_run: If True, skip wiki API calls.

        Returns:
            UpdateResult with statistics and warnings/errors.
        """
        total = len(entities)
        updated = 0
        skipped = 0
        failed = 0
        warnings: list[str] = []
        errors: list[str] = []

        self._console.print(f"\n[bold]Updating {total} {entity_type} pages...[/bold]\n")

        # Build page title mapping
        page_titles = [page_title_fn(entity) for entity in entities]

        # Fetch existing wiki pages in batches (skip in dry-run)
        existing_pages: dict[str, str | None] = {}
        if not dry_run:
            try:
                self._console.print("[dim]Fetching existing pages...[/dim]")
                existing_pages = self._wiki_client.get_pages(page_titles)
                existing_count = sum(1 for content in existing_pages.values() if content)
                self._console.print(f"[dim]Found {existing_count} existing pages[/dim]\n")
            except MediaWikiAPIError as e:
                error_msg = f"Failed to fetch existing pages: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                # Continue with empty dict (treat all as new pages)
                existing_pages = {}

        # Process each entity with progress bar
        for entity, page_title in track(
            zip(entities, page_titles, strict=False),
            description=f"Processing {entity_type}s",
            total=total,
        ):
            try:
                # Generate new content
                new_content = generator.generate_page(entity, page_title)

                # Get existing content
                existing_content = existing_pages.get(page_title) if not dry_run else None

                # Apply preservation and legacy removal if page exists
                if existing_content:
                    # Preserve manual edits
                    preserved_content = self._preservation_handler.merge_templates(
                        old_wikitext=existing_content,
                        new_wikitext=new_content,
                        template_names=template_names,
                    )

                    # Check if preservation made changes (manual edits detected)
                    if preserved_content != new_content:
                        warning = f"Manual edits preserved: {page_title}"
                        warnings.append(warning)
                        self._console.print(f"[yellow]⚠[/yellow] {warning}")

                    # Remove legacy templates
                    if self._legacy_remover.has_legacy_templates(preserved_content):
                        final_content = self._legacy_remover.remove_legacy_templates(preserved_content)
                        warning = f"Legacy templates removed: {page_title}"
                        warnings.append(warning)
                        self._console.print(f"[blue]i[/blue] {warning}")
                    else:
                        final_content = preserved_content
                else:
                    # New page, no preservation needed
                    final_content = new_content

                # Update wiki (skip in dry-run)
                if not dry_run:
                    try:
                        self._wiki_client.edit_page(
                            title=page_title,
                            content=final_content,
                            summary=f"Automated {entity_type} page update from database",
                        )
                        updated += 1
                    except MediaWikiAPIError as e:
                        error_msg = f"Failed to update {page_title}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        self._console.print(f"[red]✗[/red] {error_msg}")
                        failed += 1
                else:
                    # In dry-run, count as updated (would have been updated)
                    updated += 1

            except Exception as e:
                error_msg = f"Error processing {page_title}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        # Display summary
        self._display_summary(
            entity_type=entity_type,
            total=total,
            updated=updated,
            skipped=skipped,
            failed=failed,
            warnings=warnings,
            errors=errors,
            dry_run=dry_run,
        )

        return UpdateResult(
            total=total,
            updated=updated,
            skipped=skipped,
            failed=failed,
            warnings=warnings,
            errors=errors,
        )

    def _display_summary(
        self,
        entity_type: str,
        total: int,
        updated: int,
        skipped: int,
        failed: int,
        warnings: list[str],
        errors: list[str],
        dry_run: bool,
    ) -> None:
        """Display update summary with Rich formatting.

        Args:
            entity_type: Entity type name for display.
            total: Total pages processed.
            updated: Pages successfully updated.
            skipped: Pages skipped.
            failed: Pages that failed.
            warnings: Warning messages.
            errors: Error messages.
            dry_run: Whether this was a dry-run.
        """
        self._console.print()
        self._console.print("[bold]Summary:[/bold]")
        self._console.print(f"  Total pages:   {total}")

        if dry_run:
            self._console.print(f"  [dim]Generated:    {updated}[/dim]")
        else:
            self._console.print(f"  [green]Updated:       {updated}[/green]")

        if skipped > 0:
            self._console.print(f"  [dim]Skipped:       {skipped}[/dim]")

        if failed > 0:
            self._console.print(f"  [red]Failed:        {failed}[/red]")

        if warnings:
            self._console.print(f"  [yellow]Warnings:      {len(warnings)}[/yellow]")

        if errors:
            self._console.print(f"  [red]Errors:        {len(errors)}[/red]")

        if dry_run:
            self._console.print("\n[dim]Dry-run mode: No pages were actually updated[/dim]")

        self._console.print()

"""Wiki service for orchestrating wiki page fetch/generate/deploy workflow.

This module provides the WikiService class that orchestrates the three-stage wiki
workflow:

1. Fetch: Download existing pages from MediaWiki and cache locally
2. Generate: Create new wiki pages from database, merge with fetched content,
   preserve manual edits, and save locally for review
3. Deploy: Upload generated pages to MediaWiki

The service uses local file storage (WikiStorage) to enable:
- Reviewing generated content before deployment
- Interrupting and resuming workflows
- Testing and validation without hitting the wiki
- Tracking what changed between versions

Example:
    >>> from erenshor.application.services.wiki_service import WikiService
    >>> from erenshor.infrastructure.wiki.client import MediaWikiClient
    >>> from pathlib import Path
    >>>
    >>> # Initialize service
    >>> wiki_client = MediaWikiClient(api_url="https://erenshor.wiki.gg/api.php")
    >>> storage = WikiStorage(Path("variants/main/wiki"))
    >>> service = WikiService(
    ...     wiki_client=wiki_client,
    ...     storage=storage,
    ...     item_repo=item_repo,
    ...     character_repo=character_repo,
    ...     spell_repo=spell_repo,
    ... )
    >>>
    >>> # Three-stage workflow
    >>> service.fetch_pages(entity_type="items")
    >>> service.generate_pages(entity_type="items")
    >>> # Review files in variants/main/wiki/generated/
    >>> service.deploy_pages(entity_type="items")
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
from erenshor.application.services.wiki_storage import WikiStorage
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
class OperationResult:
    """Result of a wiki operation (fetch/generate/deploy).

    Attributes:
        total: Total number of pages processed.
        succeeded: Number of pages successfully processed.
        failed: Number of pages that failed to process.
        skipped: Number of pages skipped (e.g., no changes needed).
        warnings: List of warning messages.
        errors: List of error messages.
    """

    total: int
    succeeded: int
    failed: int
    skipped: int
    warnings: list[str]
    errors: list[str]

    def has_warnings(self) -> bool:
        """Check if result has warnings."""
        return len(self.warnings) > 0

    def has_errors(self) -> bool:
        """Check if result has errors."""
        return len(self.errors) > 0


class WikiService:
    """Service for orchestrating wiki page fetch/generate/deploy workflow.

    This service coordinates the three-stage wiki workflow:
    1. Fetch: Download pages from MediaWiki → save to storage
    2. Generate: Create pages from DB, merge, preserve → save to storage
    3. Deploy: Upload pages from storage → MediaWiki

    The service uses dependency injection for testability and follows
    a "fail-soft" approach where individual failures don't stop the batch.

    Example:
        >>> service = WikiService(
        ...     wiki_client=wiki_client,
        ...     storage=storage,
        ...     item_repo=item_repo,
        ...     character_repo=character_repo,
        ...     spell_repo=spell_repo,
        ... )
        >>> service.fetch_pages(entity_type="items")
        >>> service.generate_pages(entity_type="items")
        >>> service.deploy_pages(entity_type="items")
    """

    def __init__(
        self,
        wiki_client: MediaWikiClient,
        storage: WikiStorage,
        item_repo: ItemRepository,
        character_repo: CharacterRepository,
        spell_repo: SpellRepository,
    ) -> None:
        """Initialize wiki service.

        Args:
            wiki_client: MediaWiki API client for fetching/updating pages.
            storage: Local file storage for wiki pages.
            item_repo: Repository for fetching items from database.
            character_repo: Repository for fetching characters from database.
            spell_repo: Repository for fetching spells from database.
        """
        self._wiki_client = wiki_client
        self._storage = storage
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

    def fetch_item_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Fetch item wiki pages from MediaWiki.

        Downloads existing wiki pages and saves them to local storage for later
        use during generation. Pages are cached using stable keys.

        Args:
            dry_run: If True, simulate fetch without actually downloading.
            limit: Maximum number of items to fetch (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Fetching item pages (dry_run={dry_run}, limit={limit})")

        # Fetch items from database to know which pages to fetch
        items = self._item_repo.get_items_for_wiki_generation()

        if limit is not None:
            items = items[:limit]

        return self._fetch_pages(
            entities=items,
            entity_type="item",
            page_title_fn=lambda item: f"Item:{item.item_name}",
            dry_run=dry_run,
        )

    def fetch_character_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Fetch character wiki pages from MediaWiki.

        Args:
            dry_run: If True, simulate fetch without actually downloading.
            limit: Maximum number of characters to fetch (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Fetching character pages (dry_run={dry_run}, limit={limit})")

        characters = self._character_repo.get_characters_for_wiki_generation()

        if limit is not None:
            characters = characters[:limit]

        return self._fetch_pages(
            entities=characters,
            entity_type="character",
            page_title_fn=lambda char: f"Character:{char.npc_name}",
            dry_run=dry_run,
        )

    def fetch_spell_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Fetch spell wiki pages from MediaWiki.

        Args:
            dry_run: If True, simulate fetch without actually downloading.
            limit: Maximum number of spells to fetch (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Fetching spell pages (dry_run={dry_run}, limit={limit})")

        spells = self._spell_repo.get_spells_for_wiki_generation()

        if limit is not None:
            spells = spells[:limit]

        return self._fetch_pages(
            entities=spells,
            entity_type="spell",
            page_title_fn=lambda spell: f"Spell:{spell.spell_name}",
            dry_run=dry_run,
        )

    def generate_item_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Generate item wiki pages locally.

        Generates fresh wiki content for items, merges with fetched content (if exists),
        preserves manual edits, removes legacy templates, and saves to local storage
        for review before deployment.

        Args:
            dry_run: If True, generate content but don't save to storage.
            limit: Maximum number of items to process (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Generating item pages (dry_run={dry_run}, limit={limit})")

        items = self._item_repo.get_items_for_wiki_generation()

        if limit is not None:
            items = items[:limit]

        return self._generate_pages(
            entities=items,
            entity_type="item",
            generator=self._item_generator,
            page_title_fn=lambda item: f"Item:{item.item_name}",
            template_names=["Item"],
            dry_run=dry_run,
        )

    def generate_character_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Generate character wiki pages locally.

        Args:
            dry_run: If True, generate content but don't save to storage.
            limit: Maximum number of characters to process (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Generating character pages (dry_run={dry_run}, limit={limit})")

        characters = self._character_repo.get_characters_for_wiki_generation()

        if limit is not None:
            characters = characters[:limit]

        return self._generate_pages(
            entities=characters,
            entity_type="character",
            generator=self._character_generator,
            page_title_fn=lambda char: f"Character:{char.npc_name}",
            template_names=["Character"],
            dry_run=dry_run,
        )

    def generate_spell_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Generate spell wiki pages locally.

        Args:
            dry_run: If True, generate content but don't save to storage.
            limit: Maximum number of spells to process (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Generating spell pages (dry_run={dry_run}, limit={limit})")

        spells = self._spell_repo.get_spells_for_wiki_generation()

        if limit is not None:
            spells = spells[:limit]

        return self._generate_pages(
            entities=spells,
            entity_type="spell",
            generator=self._spell_generator,
            page_title_fn=lambda spell: f"Spell:{spell.spell_name}",
            template_names=["Ability"],
            dry_run=dry_run,
        )

    def deploy_item_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Deploy generated item pages to MediaWiki.

        Uploads pages from local storage to the wiki. Only uploads pages that
        have been generated (exist in storage).

        Args:
            dry_run: If True, simulate deployment without actually uploading.
            limit: Maximum number of items to deploy (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Deploying item pages (dry_run={dry_run}, limit={limit})")

        # Get list of generated items from storage
        generated_keys = self._storage.list_generated()
        item_keys = [k for k in generated_keys if k.startswith("item:")]

        if limit is not None:
            item_keys = item_keys[:limit]

        return self._deploy_pages(
            stable_keys=item_keys,
            entity_type="item",
            dry_run=dry_run,
        )

    def deploy_character_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Deploy generated character pages to MediaWiki.

        Args:
            dry_run: If True, simulate deployment without actually uploading.
            limit: Maximum number of characters to deploy (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Deploying character pages (dry_run={dry_run}, limit={limit})")

        generated_keys = self._storage.list_generated()
        character_keys = [k for k in generated_keys if k.startswith("character:")]

        if limit is not None:
            character_keys = character_keys[:limit]

        return self._deploy_pages(
            stable_keys=character_keys,
            entity_type="character",
            dry_run=dry_run,
        )

    def deploy_spell_pages(
        self,
        dry_run: bool = False,
        limit: int | None = None,
    ) -> OperationResult:
        """Deploy generated spell pages to MediaWiki.

        Args:
            dry_run: If True, simulate deployment without actually uploading.
            limit: Maximum number of spells to deploy (for testing).

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(f"Deploying spell pages (dry_run={dry_run}, limit={limit})")

        generated_keys = self._storage.list_generated()
        spell_keys = [k for k in generated_keys if k.startswith("spell:")]

        if limit is not None:
            spell_keys = spell_keys[:limit]

        return self._deploy_pages(
            stable_keys=spell_keys,
            entity_type="spell",
            dry_run=dry_run,
        )

    def _fetch_pages(
        self,
        entities: list[Item] | list[Character] | list[Spell],
        entity_type: str,
        page_title_fn: Any,
        dry_run: bool,
    ) -> OperationResult:
        """Fetch wiki pages for a list of entities.

        Args:
            entities: List of entities to fetch pages for.
            entity_type: Entity type name for display.
            page_title_fn: Function to get wiki page title from entity.
            dry_run: If True, skip actual fetching.

        Returns:
            OperationResult with statistics and warnings/errors.
        """
        total = len(entities)
        succeeded = 0
        failed = 0
        skipped = 0
        warnings: list[str] = []
        errors: list[str] = []

        self._console.print(f"\n[bold]Fetching {total} {entity_type} pages...[/bold]\n")

        if not entities:
            logger.warning(f"No {entity_type} entities found")
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=[f"No {entity_type} entities found"],
                errors=[],
            )

        # Build page title mapping
        page_titles = [page_title_fn(entity) for entity in entities]

        # Fetch pages in batches from wiki
        if not dry_run:
            try:
                self._console.print("[dim]Fetching pages from MediaWiki...[/dim]")
                fetched_pages = self._wiki_client.get_pages(page_titles)
                self._console.print(f"[dim]Fetched {len(fetched_pages)} pages[/dim]\n")

                # Save fetched pages to storage
                for entity, page_title in track(
                    zip(entities, page_titles, strict=False),
                    description=f"Saving {entity_type}s",
                    total=total,
                ):
                    try:
                        stable_key = entity.stable_key
                        content = fetched_pages.get(page_title)

                        if content:
                            # Save fetched content
                            entity_name = getattr(entity, f"{entity_type}_name", str(entity))
                            self._storage.save_fetched(stable_key, page_title, content, entity_name)
                            succeeded += 1
                        else:
                            # Page doesn't exist yet - skip
                            skipped += 1

                    except Exception as e:
                        error_msg = f"Error saving {page_title}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        failed += 1

            except MediaWikiAPIError as e:
                error_msg = f"Failed to fetch pages from MediaWiki: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                return OperationResult(
                    total=total,
                    succeeded=0,
                    failed=total,
                    skipped=0,
                    warnings=warnings,
                    errors=[error_msg],
                )
        else:
            # Dry run - just count
            succeeded = total

        # Display summary
        self._display_summary(
            entity_type=entity_type,
            operation="Fetch",
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

    def _generate_pages(
        self,
        entities: list[Item] | list[Character] | list[Spell],
        entity_type: str,
        generator: Any,
        page_title_fn: Any,
        template_names: list[str],
        dry_run: bool,
    ) -> OperationResult:
        """Generate wiki pages for a list of entities.

        Args:
            entities: List of entities to generate pages for.
            entity_type: Entity type name for display.
            generator: Page generator instance.
            page_title_fn: Function to get wiki page title from entity.
            template_names: Template names to preserve/merge.
            dry_run: If True, skip saving to storage.

        Returns:
            OperationResult with statistics and warnings/errors.
        """
        total = len(entities)
        succeeded = 0
        failed = 0
        skipped = 0
        warnings: list[str] = []
        errors: list[str] = []

        self._console.print(f"\n[bold]Generating {total} {entity_type} pages...[/bold]\n")

        if not entities:
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=[f"No {entity_type} entities found"],
                errors=[],
            )

        # Process each entity with progress bar
        for entity in track(
            entities,
            description=f"Processing {entity_type}s",
            total=total,
        ):
            try:
                stable_key = entity.stable_key
                page_title = page_title_fn(entity)

                # Generate new content
                new_content = generator.generate_page(entity, page_title)

                # Try to get fetched content for merging
                existing_content = self._storage.read_fetched(stable_key)

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
                        info = f"Legacy templates removed: {page_title}"
                        warnings.append(info)
                        self._console.print(f"[blue]i[/blue] {info}")
                    else:
                        final_content = preserved_content
                else:
                    # New page, no preservation needed
                    final_content = new_content

                # Save to storage (skip in dry-run)
                if not dry_run:
                    self._storage.save_generated(stable_key, final_content)

                succeeded += 1

            except Exception as e:
                error_msg = f"Error generating page for {entity}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        # Display summary
        self._display_summary(
            entity_type=entity_type,
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

    def _deploy_pages(
        self,
        stable_keys: list[str],
        entity_type: str,
        dry_run: bool,
    ) -> OperationResult:
        """Deploy pages from storage to MediaWiki.

        Args:
            stable_keys: List of stable keys for pages to deploy.
            entity_type: Entity type name for display.
            dry_run: If True, skip actual upload.

        Returns:
            OperationResult with statistics and warnings/errors.
        """
        total = len(stable_keys)
        succeeded = 0
        failed = 0
        skipped = 0
        warnings: list[str] = []
        errors: list[str] = []

        self._console.print(f"\n[bold]Deploying {total} {entity_type} pages...[/bold]\n")

        if not stable_keys:
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=[f"No generated {entity_type} pages found"],
                errors=[],
            )

        # Deploy each page with progress bar
        for stable_key in track(
            stable_keys,
            description=f"Deploying {entity_type}s",
            total=total,
        ):
            try:
                # Read generated content
                content = self._storage.read_generated(stable_key)
                if not content:
                    warning = f"No generated content for {stable_key}"
                    warnings.append(warning)
                    skipped += 1
                    continue

                # Get wiki title from metadata
                wiki_title = self._storage.get_wiki_title(stable_key)
                if not wiki_title:
                    error_msg = f"No wiki title found for {stable_key}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    failed += 1
                    continue

                # Upload to wiki (skip in dry-run)
                if not dry_run:
                    try:
                        self._wiki_client.edit_page(
                            title=wiki_title,
                            content=content,
                            summary=f"Automated {entity_type} page update from database",
                        )
                        succeeded += 1
                    except MediaWikiAPIError as e:
                        error_msg = f"Failed to upload {wiki_title}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        self._console.print(f"[red]✗[/red] {error_msg}")
                        failed += 1
                else:
                    # In dry-run, count as succeeded
                    succeeded += 1

            except Exception as e:
                error_msg = f"Error deploying {stable_key}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        # Display summary
        self._display_summary(
            entity_type=entity_type,
            operation="Deploy",
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

    def _display_summary(
        self,
        entity_type: str,
        operation: str,
        total: int,
        succeeded: int,
        failed: int,
        skipped: int,
        warnings: list[str],
        errors: list[str],
        dry_run: bool,
    ) -> None:
        """Display operation summary with Rich formatting.

        Args:
            entity_type: Entity type name for display.
            operation: Operation name (Fetch/Generate/Deploy).
            total: Total pages processed.
            succeeded: Pages successfully processed.
            failed: Pages that failed.
            skipped: Pages skipped.
            warnings: Warning messages.
            errors: Error messages.
            dry_run: Whether this was a dry-run.
        """
        self._console.print()
        self._console.print(f"[bold]{operation} Summary:[/bold]")
        self._console.print(f"  Total pages:   {total}")

        if dry_run:
            self._console.print(f"  [dim]Simulated:    {succeeded}[/dim]")
        else:
            self._console.print(f"  [green]Succeeded:     {succeeded}[/green]")

        if skipped > 0:
            self._console.print(f"  [dim]Skipped:       {skipped}[/dim]")

        if failed > 0:
            self._console.print(f"  [red]Failed:        {failed}[/red]")

        if warnings:
            self._console.print(f"  [yellow]Warnings:      {len(warnings)}[/yellow]")

        if errors:
            self._console.print(f"  [red]Errors:        {len(errors)}[/red]")

        if dry_run:
            self._console.print(f"\n[dim]Dry-run mode: No actual {operation.lower()} performed[/dim]")

        self._console.print()

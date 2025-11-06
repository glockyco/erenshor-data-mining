"""Wiki fetch service for downloading pages from MediaWiki.

This service handles fetching wiki pages from MediaWiki with smart cache invalidation
based on recent changes timestamps.
"""

from itertools import chain

from loguru import logger
from rich.console import Console
from rich.progress import track

from erenshor.application.services.wiki_helpers import display_operation_summary, group_entities_by_page_title
from erenshor.application.services.wiki_page import OperationResult, WikiPage
from erenshor.application.services.wiki_storage import WikiStorage
from erenshor.domain.entities import Character, Item, Skill, Spell
from erenshor.infrastructure.database.repositories.characters import CharacterRepository
from erenshor.infrastructure.database.repositories.items import ItemRepository
from erenshor.infrastructure.database.repositories.skills import SkillRepository
from erenshor.infrastructure.database.repositories.spells import SpellRepository
from erenshor.infrastructure.wiki.client import MediaWikiAPIError, MediaWikiClient
from erenshor.registry.resolver import RegistryResolver


class WikiFetchService:
    """Service for fetching wiki pages from MediaWiki."""

    def __init__(
        self,
        wiki_client: MediaWikiClient,
        storage: WikiStorage,
        item_repo: ItemRepository,
        character_repo: CharacterRepository,
        spell_repo: SpellRepository,
        skill_repo: SkillRepository,
        registry_resolver: RegistryResolver,
        console: Console | None = None,
    ) -> None:
        """Initialize fetch service.

        Args:
            wiki_client: MediaWiki API client for fetching pages.
            storage: Storage for caching fetched pages.
            item_repo: Repository for item entities.
            character_repo: Repository for character entities.
            spell_repo: Repository for spell entities.
            skill_repo: Repository for skill entities.
            registry_resolver: Resolver for page titles from registry.
            console: Rich console for output (optional).
        """
        self._wiki_client = wiki_client
        self._storage = storage
        self._item_repo = item_repo
        self._character_repo = character_repo
        self._spell_repo = spell_repo
        self._skill_repo = skill_repo
        self._resolver = registry_resolver
        self._console = console or Console()

        logger.debug("WikiFetchService initialized")

    def fetch_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        force_refetch: bool = False,
        page_titles: list[str] | None = None,
    ) -> OperationResult:
        """Fetch wiki pages for all entities or specified page titles.

        Workflow:
        1. Load ALL entities from ALL repositories (or filter by page_titles)
        2. Resolve ALL page titles via registry
        3. Group entities by page title
        4. Fetch unique pages from MediaWiki

        Args:
            dry_run: If True, simulate fetch without actually downloading.
            limit: Maximum number of pages to fetch (for testing).
            force_refetch: If True, re-fetch pages even if already cached.
            page_titles: If specified, only fetch these specific page titles. If None, fetch all pages.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(
            f"Fetching wiki pages (dry_run={dry_run}, limit={limit}, "
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

        # Fetch unique pages
        return self._fetch_pages_bulk(pages, dry_run, force_refetch)

    def _fetch_pages_bulk(
        self,
        pages: list[WikiPage],
        dry_run: bool,
        force_refetch: bool = False,
    ) -> OperationResult:
        """Fetch pages from MediaWiki (bulk operation).

        Args:
            pages: List of WikiPage objects to fetch.
            dry_run: If True, skip actual fetching.
            force_refetch: If True, re-fetch even if already cached.

        Returns:
            OperationResult with statistics and warnings/errors.
        """
        total = len(pages)
        succeeded = 0
        failed = 0
        skipped = 0
        warnings: list[str] = []
        errors: list[str] = []

        self._console.print(f"\n[bold]Fetching {total} wiki pages...[/bold]\n")

        if not pages:
            logger.warning("No pages to fetch")
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=["No pages to fetch"],
                errors=[],
            )

        # Get recently changed pages with timestamps from wiki (if not force_refetch)
        recent_changes: dict[str, str] = {}
        if not force_refetch:
            try:
                logger.info("Checking for recently modified pages...")
                recent_changes = self._wiki_client.get_recent_changes(days=30)
                logger.info(f"Found {len(recent_changes)} recently modified pages")
            except Exception as e:
                logger.warning(f"Failed to get recent changes: {e}, fetching all uncached pages")

        # Filter out already-fetched pages using smart timestamp comparison
        pages_to_fetch = []
        for page in pages:
            metadata = self._storage.get_metadata_by_title(page.title)

            if force_refetch:
                # Force refetch: fetch everything
                pages_to_fetch.append(page)
            elif not metadata:
                # Page not cached: fetch it
                logger.debug(f"Fetching uncached page: {page.title}")
                pages_to_fetch.append(page)
            elif not metadata.fetched_at:
                # Page generated locally but never fetched from wiki: fetch it
                logger.debug(f"Fetching never-fetched page: {page.title}")
                pages_to_fetch.append(page)
            else:
                # Page has been fetched before: compare timestamps
                wiki_modified_at = recent_changes.get(page.title)

                if not wiki_modified_at:
                    # Page not in recent changes: definitely not modified recently, skip
                    logger.debug(f"Skipping unmodified page: {page.title}")
                    skipped += 1
                elif wiki_modified_at > metadata.fetched_at:
                    # Wiki version is newer than our cached version: re-fetch
                    logger.debug(
                        f"Re-fetching modified page: {page.title} "
                        f"(wiki: {wiki_modified_at}, cached: {metadata.fetched_at})"
                    )
                    pages_to_fetch.append(page)
                else:
                    # Our cached version is up-to-date: skip
                    logger.debug(
                        f"Skipping up-to-date page: {page.title} "
                        f"(wiki: {wiki_modified_at}, cached: {metadata.fetched_at})"
                    )
                    skipped += 1

        if skipped > 0:
            logger.info(f"Skipping {skipped} already up-to-date pages")

        # Extract unique page titles for pages we need to fetch
        page_titles_list = [page.title for page in pages_to_fetch]

        # Fetch pages in batches from MediaWiki
        if not dry_run and pages_to_fetch:
            try:
                self._console.print("[dim]Fetching pages from MediaWiki...[/dim]")
                fetched_pages = self._wiki_client.get_pages(page_titles_list)
                self._console.print(f"[dim]Fetched {len(fetched_pages)} pages[/dim]\n")

                # Save fetched pages to storage
                for page in track(
                    pages_to_fetch,
                    description="Saving pages",
                    total=len(pages_to_fetch),
                ):
                    try:
                        content = fetched_pages.get(page.title)

                        if content:
                            # Get entity names for metadata
                            entity_names: list[str] = []
                            for entity in page.entities:
                                name: str | None = None
                                if isinstance(entity, Item):
                                    name = entity.item_name
                                elif isinstance(entity, Character):
                                    name = entity.npc_name
                                elif isinstance(entity, Spell):
                                    name = entity.spell_name
                                elif isinstance(entity, Skill):
                                    name = entity.skill_name

                                if name is None:
                                    raise ValueError(f"Entity {entity.stable_key} has no name")
                                entity_names.append(name)

                            # Save fetched content
                            self._storage.save_fetched_by_title(
                                page.title,
                                page.stable_keys,
                                content,
                                entity_names,
                            )
                            succeeded += 1
                        else:
                            # Page doesn't exist yet - skip
                            skipped += 1

                    except Exception as e:
                        error_msg = f"Error saving {page.title}: {e}"
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
        display_operation_summary(
            console=self._console,
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

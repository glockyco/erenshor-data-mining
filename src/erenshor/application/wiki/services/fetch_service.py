"""Wiki fetch service for downloading pages from MediaWiki.

This service handles fetching wiki pages from MediaWiki with smart cache invalidation
based on recent changes timestamps.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.progress import track

if TYPE_CHECKING:
    from erenshor.application.wiki.generators.context import GeneratorContext

from erenshor.application.wiki.generators.registry import get_generators_by_name
from erenshor.application.wiki.services.helpers import display_operation_summary
from erenshor.application.wiki.services.page import OperationResult
from erenshor.application.wiki_deploy.article_identity import WikiPageEntity, build_article_identity_map
from erenshor.infrastructure.wiki.client import MediaWikiAPIError, MediaWikiClient


def build_fetch_page_index(context: GeneratorContext) -> dict[str, list[str]]:
    """Map each wiki page title to the stable keys of the entities it represents.

    Mirrors the entity page generator's grouping (every wiki-generated entity kind,
    including zones) so fetched-page metadata records the stable keys that actually
    contribute to each page.
    """
    entities: list[WikiPageEntity] = [
        *context.item_repo.get_items_for_wiki_generation(),
        *context.character_repo.get_characters_for_wiki_generation(),
        *context.spell_repo.get_spells_for_wiki_generation(),
        *context.skill_repo.get_skills_for_wiki_generation(),
        *context.stance_repo.get_all(),
        *context.zone_repo.get_all_zones(),
    ]
    return {title: list(stable_keys) for title, stable_keys in build_article_identity_map(entities).items()}


class WikiFetchService:
    """Service for fetching wiki pages from MediaWiki."""

    def __init__(
        self,
        wiki_client: MediaWikiClient,
        context: GeneratorContext,
        console: Console | None = None,
    ) -> None:
        """Initialize fetch service with a shared generator context."""
        self._wiki_client = wiki_client
        self._context = context
        self._storage = context.storage
        self._console = console or Console()

        logger.debug("WikiFetchService initialized")

    def _build_page_title_index(self) -> dict[str, list[str]]:
        """Build a mapping of wiki_page_name → [stable_keys] from all entities."""
        return build_fetch_page_index(self._context)

    def fetch_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        force_refetch: bool = False,
        page_titles: list[str] | None = None,
        generator_names: list[str] | None = None,
    ) -> OperationResult:
        """Fetch wiki pages using registered generators.

        Workflow:
        1. Get generators from registry
        2. Get page titles to fetch from each generator
        3. Fetch unique pages from MediaWiki

        Args:
            dry_run: If True, simulate fetch without actually downloading.
            limit: Maximum number of pages to fetch (for testing).
            force_refetch: If True, re-fetch pages even if already cached.
            page_titles: If specified, only fetch these specific page titles. If None, fetch all pages.
            generator_names: Optional list of generator names to use. If None, use all registered generators.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(
            f"Fetching wiki pages (dry_run={dry_run}, limit={limit}, "
            f"page_titles={len(page_titles) if page_titles else 'all'}, "
            f"generators={generator_names or 'all'})"
        )

        # Get generators from registry
        pairs = get_generators_by_name(self._context, generator_names)
        generators = [gen for _, gen in pairs]
        logger.debug(f"Using {len(generators)} generators")

        # Collect page titles to fetch from all generators
        all_page_titles = []
        for generator in generators:
            logger.debug(f"Getting pages to fetch from {generator.__class__.__name__}")
            page_titles_from_gen = generator.get_pages_to_fetch()
            all_page_titles.extend(page_titles_from_gen)
            logger.debug(f"  {len(page_titles_from_gen)} pages")

        # Deduplicate page titles
        unique_page_titles = list(set(all_page_titles))
        logger.info(f"Total unique pages to potentially fetch: {len(unique_page_titles)}")

        # Filter by requested page titles if specified
        if page_titles:
            page_titles_set = set(page_titles)
            unique_page_titles = [t for t in unique_page_titles if t in page_titles_set]
            logger.info(f"Filtered to {len(unique_page_titles)} pages matching requested titles")

        # Apply limit after filtering
        if limit:
            unique_page_titles = unique_page_titles[:limit]
            logger.info(f"Limited to {len(unique_page_titles)} pages")

        # Fetch pages
        return self._fetch_pages_bulk(unique_page_titles, dry_run, force_refetch)

    def _fetch_pages_bulk(
        self,
        page_titles_list: list[str],
        dry_run: bool,
        force_refetch: bool = False,
    ) -> OperationResult:
        """Fetch pages from MediaWiki (bulk operation)."""
        total = len(page_titles_list)
        succeeded = 0
        failed = 0
        skipped = 0
        warnings: list[str] = []
        errors: list[str] = []

        self._console.print(f"\n[bold]Fetching {total} wiki pages...[/bold]\n")

        if not page_titles_list:
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
        pages_to_fetch_titles = []
        for page_title in page_titles_list:
            metadata = self._storage.get_metadata_by_title(page_title)

            if force_refetch:
                pages_to_fetch_titles.append(page_title)
            elif not metadata:
                logger.debug(f"Fetching uncached page: {page_title}")
                pages_to_fetch_titles.append(page_title)
            elif not metadata.fetched_at:
                logger.debug(f"Fetching never-fetched page: {page_title}")
                pages_to_fetch_titles.append(page_title)
            else:
                wiki_modified_at = recent_changes.get(page_title)

                if not wiki_modified_at:
                    logger.debug(f"Skipping unmodified page: {page_title}")
                    skipped += 1
                elif wiki_modified_at > metadata.fetched_at:
                    logger.debug(
                        f"Re-fetching modified page: {page_title} "
                        f"(wiki: {wiki_modified_at}, cached: {metadata.fetched_at})"
                    )
                    pages_to_fetch_titles.append(page_title)
                else:
                    logger.debug(
                        f"Skipping up-to-date page: {page_title} "
                        f"(wiki: {wiki_modified_at}, cached: {metadata.fetched_at})"
                    )
                    skipped += 1

        if skipped > 0:
            logger.info(f"Skipping {skipped} already up-to-date pages")

        # Fetch pages in batches from MediaWiki
        if not dry_run and pages_to_fetch_titles:
            try:
                self._console.print("[dim]Fetching pages from MediaWiki...[/dim]")
                fetched_pages = self._wiki_client.get_pages(pages_to_fetch_titles)
                self._console.print(f"[dim]Fetched {len(fetched_pages)} pages[/dim]\n")

                # Build page_title → stable_keys index once for metadata
                page_index = self._build_page_title_index()

                # Save fetched pages to storage
                for page_title in track(
                    pages_to_fetch_titles,
                    description="Saving pages",
                    total=len(pages_to_fetch_titles),
                ):
                    try:
                        content = fetched_pages.get(page_title)

                        if content:
                            stable_keys = page_index.get(page_title, [])
                            entity_names = [sk.split(":", 1)[-1] for sk in stable_keys]

                            self._storage.save_fetched_by_title(
                                page_title,
                                stable_keys,
                                content,
                                entity_names,
                            )
                            succeeded += 1
                        else:
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

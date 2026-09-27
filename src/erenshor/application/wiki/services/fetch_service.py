"""Download wiki pages and refresh local copies when their revisions change.

The fetch checks each title's current revision before reusing cached text.
Missing wiki pages lose their local fetched copy so generation cannot reuse it.
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

        metadata_by_title = self._storage.get_metadata_by_titles(page_titles_list)
        try:
            revision_ids = {} if force_refetch else self._wiki_client.get_page_revision_ids(page_titles_list)
        except MediaWikiAPIError as error:
            message = f"Failed to check wiki page revisions: {error}"
            logger.error(message)
            return OperationResult(
                total=total,
                succeeded=0,
                failed=total,
                skipped=0,
                warnings=warnings,
                errors=[message],
            )

        pages_to_fetch_titles: list[str] = []
        for page_title in page_titles_list:
            if not force_refetch and revision_ids[page_title] is None:
                metadata = metadata_by_title.get(page_title)
                if not dry_run and (
                    self._storage.has_fetched_by_title(page_title)
                    or (metadata is not None and metadata.fetched_revision_id is not None)
                ):
                    self._storage.remove_fetched_by_title(page_title)
                logger.debug(f"Skipping missing wiki page: {page_title}")
                skipped += 1
                continue

            metadata = metadata_by_title.get(page_title)
            if (
                not force_refetch
                and metadata is not None
                and metadata.fetched_revision_id is not None
                and metadata.fetched_revision_id == revision_ids[page_title]
                and self._storage.has_fetched_by_title(page_title)
            ):
                logger.debug(f"Skipping up-to-date page: {page_title}")
                skipped += 1
                continue

            pages_to_fetch_titles.append(page_title)

        if skipped:
            logger.info(f"Skipping {skipped} unchanged or missing pages")

        if dry_run:
            succeeded = len(pages_to_fetch_titles)
        elif pages_to_fetch_titles:
            try:
                self._console.print("[dim]Fetching pages from MediaWiki...[/dim]")
                snapshots = self._wiki_client.get_page_snapshots(pages_to_fetch_titles)
                page_index = self._build_page_title_index()
                for page_title in track(
                    pages_to_fetch_titles,
                    description="Saving pages",
                    total=len(pages_to_fetch_titles),
                ):
                    snapshot = snapshots[page_title]
                    if snapshot.revision is None:
                        try:
                            self._storage.remove_fetched_by_title(page_title)
                            skipped += 1
                        except Exception as error:
                            message = f"Error removing fetched {page_title}: {error}"
                            logger.error(message)
                            errors.append(message)
                            failed += 1
                        continue

                    if snapshot.source_text is None:
                        raise MediaWikiAPIError(f"Page snapshot for {page_title!r} has a revision without content")
                    try:
                        stable_keys = page_index.get(page_title, [])
                        entity_names = [key.split(":", 1)[-1] for key in stable_keys]
                        self._storage.save_fetched_by_title(
                            page_title,
                            stable_keys,
                            snapshot.source_text,
                            entity_names,
                            snapshot.revision.revision_id,
                        )
                        succeeded += 1
                    except Exception as error:
                        message = f"Error saving {page_title}: {error}"
                        logger.error(message)
                        errors.append(message)
                        failed += 1
                self._console.print(f"[dim]Fetched {succeeded} pages[/dim]\n")
            except MediaWikiAPIError as error:
                message = f"Failed to fetch pages from MediaWiki: {error}"
                logger.error(message)
                errors.append(message)
                failed += len(pages_to_fetch_titles)

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

"""Wiki generate service for creating wiki pages locally.

This service handles generating wiki pages from database entities, merging with
fetched content, and preserving manual edits.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING

from loguru import logger
from rich.console import Console
from rich.progress import track

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from erenshor.application.wiki.generators.base import GeneratedPage
    from erenshor.application.wiki.generators.context import GeneratorContext
    from erenshor.application.wiki.lifecycle import ContentLifecycle
    from erenshor.application.wiki.semantic_validation import WikiPageExpectation
    from erenshor.application.wiki_lua.link_catalog import LinkCatalogEntry

from erenshor.application.wiki.generators.field_preservation import (
    ROOT_COMPANIONS,
    FieldPreservationConfig,
    FieldPreservationHandler,
)
from erenshor.application.wiki.generators.overview_table import replace_generated_table
from erenshor.application.wiki.generators.page_normalizer import PageNormalizer
from erenshor.application.wiki.generators.pages.armor_overview import ArmorOverviewPageGenerator
from erenshor.application.wiki.generators.pages.weapons_overview import WeaponsOverviewPageGenerator
from erenshor.application.wiki.generators.registry import get_generators_by_name
from erenshor.application.wiki.lifecycle import apply_lifecycle_fields, validate_generated_lifecycle
from erenshor.application.wiki.semantic_validation import page_expectation
from erenshor.application.wiki.services.page import OperationResult
from erenshor.application.wiki_deploy.link_audit import LinkTargets

# Pages whose generated text is one table among the text of editors.
_OVERVIEW_TITLES = frozenset({ArmorOverviewPageGenerator.PAGE_TITLE, WeaponsOverviewPageGenerator.PAGE_TITLE})


@dataclass(frozen=True, slots=True)
class GeneratedCorpus:
    """The pages of one generation run and the facts they were generated from.

    Both mappings hold the same titles in title order.
    """

    pages: Mapping[str, str]
    expectations: Mapping[str, WikiPageExpectation]


# Pages whose generated text is one table among the text of editors.
_OVERVIEW_TITLES = frozenset({ArmorOverviewPageGenerator.PAGE_TITLE, WeaponsOverviewPageGenerator.PAGE_TITLE})


class WikiGenerateService:
    """Service for generating wiki pages locally."""

    def __init__(
        self,
        context: GeneratorContext,
        link_catalog: Sequence[LinkCatalogEntry],
        console: Console | None = None,
        lifecycle: ContentLifecycle | None = None,
    ) -> None:
        """Initialize generate service with a shared generator context.

        Args:
            context: Repositories and storage shared by the generators.
            link_catalog: Link catalog of the generated data. Merged list fields
                identify their entries by the page that the catalog links.
            console: Console for progress output.
            lifecycle: Reviewed page states and renames to place in generated roots.
        """
        self._context = context
        self._storage = context.storage
        self._console = console or Console()

        self._lifecycle = lifecycle
        # Handlers for preservation and normalization
        self._preservation_handler = FieldPreservationHandler(
            FieldPreservationConfig(link_targets=LinkTargets(link_catalog))
        )
        self._page_normalizer = PageNormalizer()

        logger.debug("WikiGenerateService initialized")

    def generate_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        page_titles: list[str] | None = None,
        generator_names: list[str] | None = None,
        validate: Callable[[GeneratedCorpus], None] | None = None,
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
            validate: Optional callback that checks the pages of the run. It
                runs when every page succeeded, and an exception fails the run.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(
            f"Generating wiki pages (dry_run={dry_run}, limit={limit}, "
            f"page_titles={len(page_titles) if page_titles else 'all'}, "
            f"generators={generator_names or 'all'})"
        )

        generators = get_generators_by_name(self._context, generator_names)
        logger.debug(f"Using {len(generators)} generators")

        generated_pages: list[GeneratedPage] = []
        for generator in generators:
            logger.debug(f"Running generator: {generator.__class__.__name__}")
            pages = list(generator.generate_pages())
            logger.debug(f"  Generated {len(pages)} pages")
            generated_pages.extend(pages)

        logger.info(f"Total pages generated: {len(generated_pages)}")
        if self._lifecycle is not None and not page_titles and not limit and not generator_names:
            validate_generated_lifecycle({page.title: page.stable_keys for page in generated_pages}, self._lifecycle)

        # Remove stale storage entries on full unfiltered generation
        if not page_titles and not limit and not generator_names:
            removed = self._storage.remove_stale_pages({page.title for page in generated_pages})
            if removed:
                logger.info(f"Cleaned up {removed} stale pages")

        if page_titles:
            page_titles_set = set(page_titles)
            filtered = [page for page in generated_pages if page.title in page_titles_set]
            logger.info(
                f"Filtered to {len(filtered)} pages matching requested titles (out of {len(generated_pages)} total)"
            )
            generated_pages = filtered

        if limit:
            generated_pages = generated_pages[:limit]
            logger.info(f"Limited to {len(generated_pages)} pages")

        return self._process_generated_pages(generated_pages, dry_run, validate)

    def _process_generated_pages(
        self,
        generated_pages: list[GeneratedPage],
        dry_run: bool,
        validate: Callable[[GeneratedCorpus], None] | None = None,
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
        processed_content: dict[str, str] = {}
        expectations: dict[str, WikiPageExpectation] = {}

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
                if self._lifecycle is not None:
                    page_content = apply_lifecycle_fields(
                        gen_page.title, gen_page.stable_keys, page_content, self._lifecycle
                    )

                # Fetch existing content for preservation
                existing = self._storage.read_fetched_by_title(gen_page.title)

                # Merge into the live page when it exists
                kept_roots: tuple[str, ...] = ()
                if existing:
                    if gen_page.title in _OVERVIEW_TITLES:
                        final_content = self._page_normalizer.normalize(
                            replace_generated_table(existing, page_content), page_content
                        )
                    else:
                        # Merge generated roots and companions; keep everything else
                        merge = self._preservation_handler.merge_templates(
                            old_wikitext=existing,
                            new_wikitext=page_content,
                            template_names=list(ROOT_COMPANIONS),
                        )
                        kept_roots = merge.kept_roots
                        warnings.extend(
                            f"{gen_page.title}: kept live root {root} that matches no generated entity"
                            for root in kept_roots
                        )
                        final_content = self._page_normalizer.normalize(merge.text, page_content)
                else:
                    # New page, just normalize
                    final_content = self._page_normalizer.normalize(page_content)

                # Save to storage (skip in dry-run)
                if not dry_run:
                    self._storage.save_generated_by_title(
                        gen_page.title,
                        gen_page.stable_keys,
                        final_content,
                        kept_roots=kept_roots,
                    )

                processed_content[gen_page.title] = final_content
                expectations[gen_page.title] = page_expectation(gen_page.title, gen_page.stable_keys, existing)
                succeeded += 1

            except Exception as e:
                error_msg = f"Error generating page {gen_page.title}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        if validate is not None and failed == 0:
            titles = sorted(processed_content, key=lambda title: (title.casefold(), title))
            validate(
                GeneratedCorpus(
                    pages=MappingProxyType({title: processed_content[title] for title in titles}),
                    expectations=MappingProxyType({title: expectations[title] for title in titles}),
                )
            )

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

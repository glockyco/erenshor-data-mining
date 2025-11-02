"""Wiki deploy service for uploading pages to MediaWiki.

This service handles deploying generated wiki pages to MediaWiki with proper
error handling and progress tracking.
"""

from loguru import logger
from rich.console import Console
from rich.progress import track

from erenshor.application.services.wiki_helpers import display_operation_summary
from erenshor.application.services.wiki_page import OperationResult
from erenshor.application.services.wiki_storage import WikiStorage
from erenshor.infrastructure.wiki.client import MediaWikiAPIError, MediaWikiClient


class WikiDeployService:
    """Service for deploying wiki pages to MediaWiki."""

    def __init__(
        self,
        wiki_client: MediaWikiClient,
        storage: WikiStorage,
        console: Console | None = None,
    ) -> None:
        """Initialize deploy service.

        Args:
            wiki_client: MediaWiki API client for uploading pages.
            storage: Storage for reading generated pages.
            console: Rich console for output (optional).
        """
        self._wiki_client = wiki_client
        self._storage = storage
        self._console = console or Console()

        logger.debug("WikiDeployService initialized")

    def deploy_all(
        self,
        dry_run: bool = False,
        limit: int | None = None,
        page_titles: list[str] | None = None,
    ) -> OperationResult:
        """Deploy generated wiki pages to MediaWiki.

        Uploads pages from local storage to MediaWiki. Only pages that have been
        generated (exist in storage) will be deployed.

        Args:
            dry_run: If True, simulate deployment without actually uploading.
            limit: Maximum number of pages to deploy (for testing).
            page_titles: If specified, only deploy these specific page titles. If None, deploy all generated pages.

        Returns:
            OperationResult with summary statistics and warnings/errors.
        """
        logger.info(
            f"Deploying wiki pages (dry_run={dry_run}, limit={limit}, "
            f"page_titles={len(page_titles) if page_titles else 'all'})"
        )

        total = 0
        succeeded = 0
        failed = 0
        skipped = 0
        warnings: list[str] = []
        errors: list[str] = []

        # Get all generated page titles from storage metadata
        metadata = self._storage._load_metadata()
        all_generated_titles = [title for title, meta in metadata.items() if meta.generated_at is not None]

        # Filter by requested page titles if specified
        if page_titles:
            page_titles_set = set(page_titles)
            deploy_titles = [t for t in all_generated_titles if t in page_titles_set]
            logger.info(
                f"Filtered to {len(deploy_titles)} pages matching requested titles "
                f"(out of {len(all_generated_titles)} total)"
            )
        else:
            deploy_titles = all_generated_titles

        # Apply limit after filtering
        if limit:
            deploy_titles = deploy_titles[:limit]
            logger.info(f"Limited to {len(deploy_titles)} pages")

        total = len(deploy_titles)

        self._console.print(f"\n[bold]Deploying {total} wiki pages...[/bold]\n")

        if not deploy_titles:
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=["No generated pages found"],
                errors=[],
            )

        # Deploy each page with progress bar
        for page_title in track(
            deploy_titles,
            description="Deploying pages",
            total=total,
        ):
            try:
                # Read generated content
                content = self._storage.read_generated_by_title(page_title)
                if not content:
                    warning = f"No generated content for {page_title}"
                    warnings.append(warning)
                    skipped += 1
                    continue

                # Upload to wiki (skip in dry-run)
                if not dry_run:
                    try:
                        self._wiki_client.edit_page(
                            title=page_title,
                            content=content,
                            summary="Automated wiki page update from database",
                        )
                        succeeded += 1
                    except MediaWikiAPIError as e:
                        error_msg = f"Failed to upload {page_title}: {e}"
                        logger.error(error_msg)
                        errors.append(error_msg)
                        self._console.print(f"[red]✗[/red] {error_msg}")
                        failed += 1
                else:
                    # In dry-run, count as succeeded
                    succeeded += 1

            except Exception as e:
                error_msg = f"Error deploying {page_title}: {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        # Display summary
        display_operation_summary(
            console=self._console,
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

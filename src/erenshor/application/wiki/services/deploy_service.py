"""Wiki deploy service for uploading pages to MediaWiki.

This service handles deploying generated wiki pages to MediaWiki with proper
error handling and progress tracking.
"""

import time
from pathlib import Path

from loguru import logger
from rich.console import Console
from rich.progress import track

from erenshor.application.wiki.services.helpers import display_operation_summary
from erenshor.application.wiki.services.page import OperationResult
from erenshor.application.wiki.services.storage import WikiStorage
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

    def deploy_from_dir(
        self,
        source_dir: Path,
        dry_run: bool = False,
    ) -> OperationResult:
        """Deploy wiki pages from .txt files in a directory.

        Reads all .txt files from source_dir and uploads each to the wiki.
        The wiki page title is derived from the filename stem:
        - If the stem starts with a recognized namespace prefix (Template, Category,
          Module, Help, File, User, Project), the first underscore is replaced with
          a colon and remaining underscores become spaces.
        - Otherwise all underscores become spaces.

        Examples:
            Template_MapLink.txt  -> Template:MapLink
            Template_Zone_Navbox.txt -> Template:Zone Navbox
            Mysterious_Portal.txt -> Mysterious Portal

        Args:
            source_dir: Directory containing .txt files to deploy.
            dry_run: If True, simulate without actually uploading.

        Returns:
            OperationResult with summary statistics.
        """
        namespaces = {"Template", "Category", "Module", "Help", "File", "User", "Project"}

        def _stem_to_title(stem: str) -> str:
            """Convert filename stem to wiki page title.

            Encoding rules:
              - Single underscores become spaces
              - Double underscores (__) become a subpage slash (/)
              - Namespace prefix (e.g. Template_) is split off and followed by a colon

            Examples:
              Template_MapLink           -> Template:MapLink
              Template_Zone_Navbox__doc  -> Template:Zone Navbox/doc
              Hidden_Hills               -> Hidden Hills
            """
            # Resolve subpage separator before splitting on namespace,
            # so Template_Zone_Navbox__doc splits correctly.
            stem_with_slash = stem.replace("__", "/")
            parts = stem_with_slash.split("_", 1)
            if len(parts) == 2 and parts[0] in namespaces:
                return f"{parts[0]}:{parts[1].replace('_', ' ')}"
            return stem_with_slash.replace("_", " ")

        if not source_dir.exists():
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=[f"Source directory does not exist: {source_dir}"],
                errors=[],
            )

        txt_files = sorted(source_dir.glob("*.txt"))
        if not txt_files:
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=[f"No .txt files found in {source_dir}"],
                errors=[],
            )

        total = len(txt_files)
        succeeded = 0
        failed = 0
        warnings: list[str] = []
        errors: list[str] = []

        logger.info(f"Deploying {total} pages from {source_dir} (dry_run={dry_run})")
        self._console.print(f"\n[bold]Deploying {total} wiki pages from {source_dir}...[/bold]\n")

        if not dry_run:
            try:
                self._wiki_client.login()
            except Exception as e:
                error_msg = f"Failed to login to wiki: {e}"
                logger.error(error_msg)
                return OperationResult(
                    total=total,
                    succeeded=0,
                    failed=total,
                    skipped=0,
                    warnings=[],
                    errors=[error_msg],
                )

        for txt_file in track(txt_files, description="Deploying pages", total=total):
            title = _stem_to_title(txt_file.stem)
            try:
                content = txt_file.read_text(encoding="utf-8")
                if not dry_run:
                    self._wiki_client.edit_page(
                        title=title,
                        content=content,
                        summary="Manual wiki update",
                    )
                    time.sleep(2.0)  # rate limit: 30 uploads per minute
                succeeded += 1
                logger.debug(f"Deployed '{title}' from {txt_file.name}")
            except Exception as e:
                error_msg = f"Failed to deploy '{title}': {e}"
                logger.error(error_msg)
                errors.append(error_msg)
                self._console.print(f"[red]✗[/red] {error_msg}")
                failed += 1

        display_operation_summary(
            console=self._console,
            operation="Deploy from dir",
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
            candidate_titles = [t for t in all_generated_titles if t in page_titles_set]
            logger.info(
                f"Filtered to {len(candidate_titles)} pages matching requested titles "
                f"(out of {len(all_generated_titles)} total)"
            )
        else:
            candidate_titles = all_generated_titles

        if not candidate_titles:
            return OperationResult(
                total=0,
                succeeded=0,
                failed=0,
                skipped=0,
                warnings=["No generated pages found"],
                errors=[],
            )

        # Login to wiki before deploying (required for edit operations)
        if not dry_run:
            try:
                self._wiki_client.login()
            except Exception as e:
                error_msg = f"Failed to login to wiki: {e}"
                logger.error(error_msg)
                return OperationResult(
                    total=len(candidate_titles),
                    succeeded=0,
                    failed=len(candidate_titles),
                    skipped=0,
                    warnings=[],
                    errors=[error_msg],
                )

        self._console.print("\n[bold]Deploying wiki pages...[/bold]\n")

        # Deploy each page with progress bar, respecting limit
        for page_title in track(
            candidate_titles,
            description="Deploying pages",
            total=len(candidate_titles),
        ):
            try:
                # Check if limit reached (limit applies to successful deployments only)
                if limit and succeeded >= limit:
                    logger.info(f"Reached deployment limit of {limit}")
                    break

                # Check if page should be deployed
                page_metadata = metadata.get(page_title)
                if page_metadata:
                    should_deploy, reason = page_metadata.should_deploy()
                    if not should_deploy:
                        logger.debug(f"Skipping {page_title}: {reason}")
                        skipped += 1
                        continue

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
                            summary="Automated wiki update",
                        )
                        # Update deployment metadata after successful upload
                        self._storage.update_deployed(page_title, content)
                        succeeded += 1

                        # Rate limit: 30 uploads per minute = 2 seconds between uploads
                        time.sleep(2.0)
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

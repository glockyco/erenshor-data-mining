"""Service layer for upload operations - coordinates uploader, storage, and registry."""

from __future__ import annotations

import time
from collections.abc import Iterator
from datetime import datetime, timezone

from erenshor.application.upload.uploader import PageUploader
from erenshor.domain.events import (
    PageUploaded,
    UploadComplete,
    UploadEvent,
    UploadFailed,
)
from erenshor.infrastructure.storage.page_storage import PageStorage
from erenshor.registry.core import WikiRegistry

__all__ = ["UploadService"]


class UploadService:
    """Orchestrate upload operations with storage and registry integration.

    This service coordinates the uploading of pages, reading content from storage,
    and updating the registry with upload metadata.
    """

    def __init__(
        self,
        uploader: PageUploader,
        storage: PageStorage,
        cache_storage: PageStorage,
        registry: WikiRegistry,
    ):
        """Initialize upload service.

        Args:
            uploader: PageUploader for uploading pages
            storage: PageStorage for reading updated page content (wiki_updated/)
            cache_storage: PageStorage for reading cached page content (wiki_cache/)
            registry: WikiRegistry for tracking page metadata
        """
        self.uploader = uploader
        self.storage = storage
        self.cache_storage = cache_storage
        self.registry = registry

    def upload_pages(
        self,
        page_titles: list[str],
        summary: str,
        minor: bool = True,
        bot: bool = True,
        force: bool = False,
        batch_size: int | None = None,
    ) -> Iterator[UploadEvent]:
        """Upload pages, update registry timestamps, emit events.

        This method orchestrates the complete upload operation:
        1. Check for local changes (skip if no changes and not forced)
        2. Load content for all pages from storage
        3. Upload pages using PageUploader (with progress callbacks)
        4. Update registry with upload timestamps for successful uploads
        5. Emit events for progress tracking and final summary

        Batch size controls the maximum number of ACTUAL UPLOADS + FAILURES
        (skipped pages do not count toward the batch limit).

        Args:
            page_titles: List of page titles to upload
            summary: Edit summary for uploads
            minor: Mark uploads as minor edits
            bot: Mark uploads as bot edits (requires bot permissions)
            force: Force upload even if content is identical
            batch_size: Maximum number of actual uploads + failures (None = unlimited)

        Yields:
            UploadEvent instances (PageUploaded, UploadFailed, UploadComplete)
        """
        import hashlib

        start = time.time()
        uploaded_count = 0
        skipped_count = 0
        failed_count = 0
        processed_count = 0  # Uploaded + failed (not skipped)

        # Load content for all pages and check for local changes
        pages_with_content: list[tuple[str, str]] = []
        for title in page_titles:
            # Check batch limit (skips don't count)
            if batch_size is not None and processed_count >= batch_size:
                break
            page = self.registry.get_page_by_title(title)
            if not page:
                failed_count += 1
                processed_count += 1  # Failures count toward batch limit
                yield UploadFailed(
                    page_title=title,
                    error="Page not in registry",
                )
                continue

            # Read updated content (wiki_updated/)
            updated_content = self.storage.read(page)
            if not updated_content:
                failed_count += 1
                processed_count += 1  # Failures count toward batch limit
                yield UploadFailed(
                    page_title=title,
                    error="No content found in wiki_updated/",
                )
                continue

            # Compare with cached content (wiki_cache/) - trust actual files, not registry
            if not force:
                cached_content = self.cache_storage.read(page)
                if cached_content is not None:
                    # Compare actual file hashes
                    cached_hash = hashlib.sha256(cached_content.encode()).hexdigest()
                    updated_hash = hashlib.sha256(updated_content.encode()).hexdigest()

                    if cached_hash == updated_hash:
                        # Content unchanged between cache and updated - skip
                        skipped_count += 1
                        yield PageUploaded(
                            page_title=title,
                            action="skipped",
                            message="No changes between cached and updated content",
                        )
                        continue
                # If no cached content, proceed with upload (new page or never fetched)

            pages_with_content.append((title, updated_content))

        # Upload pages (streaming with progress callbacks)
        registry_modified = False
        for result in self.uploader.upload_pages(
            pages_with_content, summary, minor, bot, force=force
        ):
            # Check batch limit before processing result
            if batch_size is not None and processed_count >= batch_size:
                break

            if result.action == "uploaded":
                # Update registry for successful uploads
                page = self.registry.get_page_by_title(result.title)
                if page:
                    page.last_pushed = result.timestamp or datetime.now(timezone.utc)
                    # Sync original hash with updated hash - wiki now has our content
                    page.original_content_hash = page.updated_content_hash
                    registry_modified = True
                uploaded_count += 1
                processed_count += 1  # Uploads count toward batch limit
                yield PageUploaded(
                    page_title=result.title,
                    action="uploaded",
                    message=result.message,
                )
            elif result.action == "skipped":
                # Should rarely happen since we trust local state
                skipped_count += 1
                # Skips do NOT count toward batch limit
                yield PageUploaded(
                    page_title=result.title,
                    action="skipped",
                    message=result.message,
                )
            else:  # failed
                failed_count += 1
                processed_count += 1  # Failures count toward batch limit
                yield UploadFailed(
                    page_title=result.title,
                    error=result.message,
                )

        # Save registry once after all uploads (batch save)
        if registry_modified:
            self.registry.save()

        duration = time.time() - start

        # Emit completion event
        yield UploadComplete(
            total=len(page_titles),
            uploaded=uploaded_count,
            skipped=skipped_count,
            failed=failed_count,
            duration_seconds=duration,
        )

"""Core upload logic with content comparison and streaming results."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone

import httpx

from erenshor.domain.events import PageUploaded, ProgressEvent
from erenshor.infrastructure.wiki.client import WikiAPIClient

from .models import UploadResult

__all__ = ["PageUploader"]


logger = logging.getLogger(__name__)


class PageUploader:
    """Core upload logic with content comparison and progress tracking.

    This class handles the actual uploading of pages with content comparison,
    rate limiting, and progress callbacks. It's designed to be testable.
    """

    def __init__(
        self,
        client: WikiAPIClient,
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ):
        """Initialize uploader with API client and optional progress callback.

        Args:
            client: WikiAPIClient for making API requests
            on_progress: Optional callback for progress events
        """
        self.client = client
        self.on_progress = on_progress or (lambda e: None)
        self.last_upload_time = 0.0

    def upload_pages(
        self,
        pages_with_content: list[tuple[str, str]],  # (title, content)
        summary: str,
        minor: bool = True,
        delay: float = 1.0,
        force: bool = False,
    ) -> Iterator[UploadResult]:
        """Upload pages and yield results as they complete.

        If force=False, fetches current content and skips if identical.
        If force=True, always upload regardless of content comparison.

        Progress events are emitted via on_progress callback:
        - PageUploaded(title, success, action): After each page upload attempt

        Args:
            pages_with_content: List of (title, content) tuples to upload
            summary: Edit summary for uploads
            minor: Mark as minor edit
            delay: Delay in seconds between uploads (rate limiting)
            force: Force upload even if content is identical

        Yields:
            UploadResult for each page (uploaded, skipped, or failed)
        """
        for title, new_content in pages_with_content:
            # Check if content changed (unless forced)
            if not force:
                try:
                    current = self.client.fetch_page(title)
                    if current is not None and current == new_content:
                        # Skip because wiki content is identical
                        # This is a WIKI-BASED skip - we should update last_pushed
                        # because we've confirmed the wiki is up to date
                        result = UploadResult(
                            title=title,
                            success=True,
                            action="skipped_wiki",  # Distinguish from local skips
                            message="Content identical to wiki",
                            timestamp=datetime.now(timezone.utc),
                        )
                        self.on_progress(
                            PageUploaded(
                                page_title=title,
                                action="skipped",
                                message="Content identical to wiki",
                            )
                        )
                        yield result
                        continue
                except (httpx.HTTPStatusError, httpx.RequestError) as e:
                    # If fetch fails (network error, API error), proceed with upload anyway
                    logger.warning(
                        "Failed to fetch page %s for comparison: %s", title, e
                    )

            # Rate limiting
            if delay > 0:
                elapsed = time.time() - self.last_upload_time
                if elapsed < delay:
                    time.sleep(delay - elapsed)

            # Upload the page
            try:
                response = self.client.upload_page(title, new_content, summary, minor)
                result = UploadResult(
                    title=title,
                    success=True,
                    action="uploaded",
                    message="Upload successful",
                    revision_id=response.get("newrevid"),
                    timestamp=datetime.now(timezone.utc),
                )
                self.on_progress(
                    PageUploaded(
                        page_title=title,
                        action="uploaded",
                        message="Upload successful",
                    )
                )
                self.last_upload_time = time.time()
                yield result
            except Exception as e:
                result = UploadResult(
                    title=title,
                    success=False,
                    action="failed",
                    message=str(e),
                )
                self.on_progress(
                    PageUploaded(
                        page_title=title,
                        action="failed",
                        message=str(e),
                    )
                )
                yield result

"""Core upload logic with streaming results."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable, Iterator
from datetime import datetime, timezone

from erenshor.domain.events import PageUploaded, ProgressEvent
from erenshor.infrastructure.wiki.client import WikiAPIClient

from .models import UploadResult

__all__ = ["PageUploader"]


logger = logging.getLogger(__name__)


class PageUploader:
    """Core upload logic with rate limiting and progress tracking.

    This class handles the actual uploading of pages with rate limiting
    and progress callbacks. It trusts local state - if called to upload,
    it uploads. MediaWiki handles no-op edits efficiently.
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
        bot: bool = True,
        delay: float = 1.0,
        force: bool = False,
    ) -> Iterator[UploadResult]:
        """Upload pages and yield results as they complete.

        Trust local state - if we're told to upload, we upload.
        MediaWiki handles no-op edits efficiently.

        Progress events are emitted via on_progress callback:
        - PageUploaded(title, success, action): After each page upload attempt

        Args:
            pages_with_content: List of (title, content) tuples to upload
            summary: Edit summary for uploads
            minor: Mark as minor edit
            bot: Mark as bot edit (requires bot permissions)
            delay: Delay in seconds between uploads (rate limiting)
            force: Unused - kept for API compatibility

        Yields:
            UploadResult for each page (uploaded or failed)
        """
        for title, new_content in pages_with_content:
            # Rate limiting
            if delay > 0:
                elapsed = time.time() - self.last_upload_time
                if elapsed < delay:
                    time.sleep(delay - elapsed)

            # Upload the page
            try:
                response = self.client.upload_page(
                    title, new_content, summary, minor, bot
                )
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

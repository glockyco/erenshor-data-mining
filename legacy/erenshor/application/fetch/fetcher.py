"""Core fetching logic with streaming results and progress callbacks."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator

from erenshor.domain.events import ProgressEvent
from erenshor.infrastructure.wiki.client import WikiAPIClient

from .models import BatchStarted, FetchResult, PageFetched

__all__ = ["PageFetcher"]


class PageFetcher:
    """Core fetching logic with streaming results and progress tracking.

    This class handles the actual fetching of pages with batching, rate limiting,
    and progress callbacks. It's designed to be testable without network dependencies.
    """

    def __init__(
        self,
        client: WikiAPIClient,
        on_progress: Callable[[ProgressEvent], None] | None = None,
    ):
        """Initialize fetcher with API client and optional progress callback.

        Args:
            client: WikiAPIClient for making API requests
            on_progress: Optional callback for progress events
        """
        self.client = client
        self.on_progress = on_progress or (lambda e: None)

    def fetch_pages(
        self,
        titles: list[str],
        batch_size: int = 25,
        delay: float = 1.0,
    ) -> Iterator[FetchResult]:
        """Fetch pages and yield results as they complete.

        Progress events are emitted via on_progress callback:
        - BatchStarted(batch_num, total_batches): When each batch starts
        - PageFetched(title, success, size): After each page is fetched

        Args:
            titles: List of page titles to fetch
            batch_size: Number of pages per API batch request
            delay: Delay in seconds between batch requests (rate limiting)

        Yields:
            FetchResult for each page (successful or failed)
        """
        if not titles:
            return

        total_batches = (len(titles) + batch_size - 1) // batch_size

        for i in range(0, len(titles), batch_size):
            batch = titles[i : i + batch_size]
            batch_num = i // batch_size + 1

            # Emit batch started event
            self.on_progress(BatchStarted(batch_num, total_batches))

            # Fetch batch from API
            try:
                data = self.client.fetch_batch(batch)
            except Exception as e:
                # If batch fetch fails entirely, mark all pages as failed
                for title in batch:
                    result = FetchResult(
                        title=title,
                        success=False,
                        content=None,
                        error=f"Batch fetch failed: {str(e)}",
                        size_bytes=0,
                    )
                    self.on_progress(PageFetched(title, False, 0))
                    yield result
                continue

            # Process each page in the batch
            for title in batch:
                content = data.get(title)
                if content is not None:
                    size = len(content)
                    result = FetchResult(
                        title=title,
                        success=True,
                        content=content,
                        error=None,
                        size_bytes=size,
                    )
                    self.on_progress(PageFetched(title, True, size))
                    yield result
                else:
                    result = FetchResult(
                        title=title,
                        success=False,
                        content=None,
                        error="Page not found",
                        size_bytes=0,
                    )
                    self.on_progress(PageFetched(title, False, 0))
                    yield result

            # Rate limiting: delay between batches
            if i + batch_size < len(titles) and delay > 0:
                time.sleep(delay)

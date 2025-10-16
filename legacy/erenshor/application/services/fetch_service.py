"""Service layer for fetch operations - coordinates fetcher, storage, and registry."""

from __future__ import annotations

import time

from erenshor.application.fetch.fetcher import PageFetcher
from erenshor.application.fetch.models import FetchOperation, FetchResult
from erenshor.infrastructure.storage.page_storage import PageStorage
from erenshor.registry.core import WikiRegistry

__all__ = ["FetchService"]


class FetchService:
    """Orchestrate fetch operations with storage and registry integration.

    This service coordinates the fetching of pages, saving them to storage,
    and updating the registry with fetch metadata.
    """

    def __init__(
        self,
        fetcher: PageFetcher,
        storage: PageStorage,
        registry: WikiRegistry,
    ):
        """Initialize fetch service.

        Args:
            fetcher: PageFetcher for fetching pages
            storage: PageStorage for saving page content
            registry: WikiRegistry for tracking page metadata
        """
        self.fetcher = fetcher
        self.storage = storage
        self.registry = registry

    def fetch_pages(self, titles: list[str]) -> FetchOperation:
        """Fetch pages, store them, update registry, return structured result.

        This method orchestrates the complete fetch operation:
        1. Fetch pages using PageFetcher (with progress callbacks)
        2. Save successful fetches to storage
        3. Update registry with fetch metadata
        4. Return comprehensive operation result

        Args:
            titles: List of page titles to fetch

        Returns:
            FetchOperation with detailed results and metrics
        """
        start = time.time()
        successful: list[FetchResult] = []
        failed: list[FetchResult] = []
        bytes_fetched = 0

        # Fetch pages (streaming with progress callbacks)
        for result in self.fetcher.fetch_pages(titles):
            if result.success and result.content:
                # Get or create page in registry
                page = self.registry.get_or_create_page(result.title)

                # Save fetched content to storage
                self.storage.write_fetched(page, result.content)

                successful.append(result)
                bytes_fetched += result.size_bytes
            else:
                failed.append(result)

        duration = time.time() - start

        return FetchOperation(
            total=len(titles),
            successful=successful,
            failed=failed,
            duration_seconds=duration,
            bytes_fetched=bytes_fetched,
        )

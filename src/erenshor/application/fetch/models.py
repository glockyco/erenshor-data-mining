"""Data models for fetch operations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from erenshor.domain.events import ProgressEvent

__all__ = ["FetchResult", "PageFetched", "BatchStarted", "FetchOperation"]


@dataclass
class FetchResult:
    """Result of fetching a single page."""

    title: str
    success: bool
    content: str | None = None
    error: str | None = None
    size_bytes: int = 0
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class PageFetched(ProgressEvent):
    """Event emitted when a page is fetched (successfully or not)."""

    title: str
    success: bool
    size_bytes: int


@dataclass
class BatchStarted(ProgressEvent):
    """Event emitted when a batch fetch starts."""

    batch_num: int
    total_batches: int


@dataclass
class FetchOperation:
    """Comprehensive result of a complete fetch operation."""

    total: int
    successful: list[FetchResult]
    failed: list[FetchResult]
    duration_seconds: float
    bytes_fetched: int

"""Data models for upload operations."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

__all__ = ["UploadResult", "UploadOperation"]


@dataclass
class UploadResult:
    """Result of uploading a single page."""

    title: str
    success: bool
    action: str  # "uploaded", "skipped", "failed"
    message: str
    revision_id: int | None = None
    timestamp: datetime | None = None


@dataclass
class UploadOperation:
    """Comprehensive result of a complete upload operation."""

    total: int
    uploaded: list[UploadResult]
    skipped: list[UploadResult]
    failed: list[UploadResult]
    duration_seconds: float

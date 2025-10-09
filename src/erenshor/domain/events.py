"""Shared event base classes for progress tracking across operations."""

from __future__ import annotations

from dataclasses import dataclass

from erenshor.domain.validation.base import Violation

__all__ = [
    "ContentGenerated",
    "PageUpdated",
    "PageUploaded",
    "ProgressEvent",
    "UpdateComplete",
    "UpdateEvent",
    "UpdateFailed",
    "UploadComplete",
    "UploadEvent",
    "UploadFailed",
    "ValidationFailed",
]


class ProgressEvent:
    """Base class for progress events emitted during operations.

    Subclasses should be dataclasses with specific event information.
    This base class allows progress callbacks to handle any type of event.
    """

    pass


# Update-specific events


@dataclass
class UpdateEvent(ProgressEvent):
    """Base class for update operation events.

    All update events inherit from this to enable type-safe event handling
    in the update pipeline.
    """

    pass


@dataclass
class ContentGenerated(UpdateEvent):
    """Event emitted when content has been generated for an entity.

    This event is emitted after a generator yields GeneratedContent but before
    any page transformation or validation occurs.

    Attributes:
        page_title: Target wiki page title
        content_type: Type of content (items, abilities, characters, etc.)
        byte_size: Total size of rendered content in bytes
    """

    page_title: str
    content_type: str
    byte_size: int


@dataclass
class PageUpdated(UpdateEvent):
    """Event emitted when a page has been successfully updated.

    This event is emitted after content has been transformed, validated (if
    enabled), and written to storage.

    Attributes:
        page_title: Wiki page title that was updated
        changed: Whether the content actually changed (vs. identical re-write)
        validation_passed: Whether validation passed (or was skipped)
    """

    page_title: str
    changed: bool
    validation_passed: bool


@dataclass
class ValidationFailed(UpdateEvent):
    """Event emitted when validation fails for a page.

    This event is emitted when a page fails validation checks. The page will
    not be written to storage when validation fails.

    Attributes:
        page_title: Wiki page title that failed validation
        violations: List of validation violations found
    """

    page_title: str
    violations: list[Violation]


@dataclass
class UpdateFailed(UpdateEvent):
    """Event emitted when an update operation fails.

    This event is emitted when an unexpected error occurs during generation,
    transformation, or storage operations.

    Attributes:
        page_title: Wiki page title that failed to update
        error: Error message describing what went wrong
    """

    page_title: str
    error: str


@dataclass
class UpdateComplete(UpdateEvent):
    """Event emitted when the entire update operation completes.

    This is the final event in the update stream, providing summary statistics
    for the entire operation.

    Attributes:
        total: Total number of entities processed
        updated: Number of pages successfully updated
        unchanged: Number of pages that were unchanged
        failed: Number of pages that failed (validation or errors)
        duration_seconds: Total time spent in seconds
    """

    total: int
    updated: int
    unchanged: int
    failed: int
    duration_seconds: float


# Upload-specific events


@dataclass
class UploadEvent(ProgressEvent):
    """Base class for upload operation events.

    All upload events inherit from this to enable type-safe event handling
    in the upload pipeline.
    """

    pass


@dataclass
class PageUploaded(UploadEvent):
    """Event emitted when a page upload completes.

    This event is emitted after each page upload attempt, whether it succeeded,
    was skipped, or failed.

    Attributes:
        page_title: Wiki page title that was uploaded
        action: Upload action ("uploaded", "skipped", "failed")
        message: Optional message with details
    """

    page_title: str
    action: str  # "uploaded", "skipped", "failed"
    message: str = ""


@dataclass
class UploadFailed(UploadEvent):
    """Event emitted when an upload operation fails.

    This event is emitted when an unexpected error occurs during upload
    preparation or execution.

    Attributes:
        page_title: Wiki page title that failed to upload
        error: Error message describing what went wrong
    """

    page_title: str
    error: str


@dataclass
class UploadComplete(UploadEvent):
    """Event emitted when the entire upload operation completes.

    This is the final event in the upload stream, providing summary statistics
    for the entire operation.

    Attributes:
        total: Total number of pages processed
        uploaded: Number of pages successfully uploaded
        skipped: Number of pages skipped (unchanged)
        failed: Number of pages that failed
        duration_seconds: Total time spent in seconds
    """

    total: int
    uploaded: int
    skipped: int
    failed: int
    duration_seconds: float

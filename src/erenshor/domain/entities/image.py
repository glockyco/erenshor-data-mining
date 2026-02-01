"""Domain entities for image processing and lifecycle management.

This module defines the core domain models for the image processing pipeline:
- ImageInfo: Discovery information from game database
- ImageMetadata: Registry tracking for version management
- ProcessingResult: Output metadata from image processing
- ComparisonReport: Summary of image comparison results
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from erenshor.infrastructure.wiki.filename_sanitizer import sanitize_wiki_filename

__all__ = [
    "ChangeType",
    "ComparisonReport",
    "ImageInfo",
    "ImageMetadata",
    "ProcessingResult",
]


@dataclass
class ImageInfo:
    """Information about a source image discovered from game database.

    Used during the discovery phase to locate and identify images that need processing.

    Attributes:
        entity_type: Type of entity (item, spell, skill).
        stable_key: Stable identifier in format "entity_type:resource_name".
        entity_name: Human-readable entity name resolved from registry.
        image_name: Wiki image filename (without .png extension) from registry.
        icon_name: Source icon filename in Unity assets (without .png extension).
        source_path: Path to source PNG file in Unity Texture2D directory.
    """

    entity_type: str
    stable_key: str
    entity_name: str
    image_name: str
    icon_name: str
    source_path: Path | None


@dataclass
class ProcessingResult:
    """Result metadata from image processing.

    Returned after successfully processing an image, contains all metadata needed
    for registry tracking.

    Attributes:
        content_hash: SHA256 hash of processed PNG file.
        perceptual_hash: Perceptual hash (pHash) for visual similarity comparison.
        source_hash: SHA256 hash of source Unity texture file.
        file_size: Size of processed PNG file in bytes.
        dimensions: Image dimensions as (width, height) tuple.
        processed_at: ISO timestamp when processing completed.
    """

    content_hash: str
    perceptual_hash: str
    source_hash: str
    file_size: int
    dimensions: tuple[int, int]
    processed_at: str


@dataclass
class ImageMetadata:
    """Metadata for a processed image in the registry.

    Tracks the complete lifecycle of an image: source → process → upload.
    Follows the PageMetadata pattern from wiki storage, adapted for images.

    Attributes:
        stable_key: Primary key, stable identifier "entity_type:resource_name".
        entity_type: Type of entity (item, spell, skill).
        entity_name: Human-readable entity name.
        image_name: Wiki image filename base (without .png extension).
        source_icon_name: Unity asset filename (without .png extension).
        source_hash: SHA256 hash of source Unity texture.
        source_path: Relative path to source texture.
        current_hash: SHA256 hash of current processed PNG.
        current_phash: Perceptual hash of current processed PNG.
        current_processed_at: ISO timestamp when current version was processed.
        current_file_size: Size of current processed PNG in bytes.
        previous_hash: SHA256 hash of previous processed PNG.
        previous_phash: Perceptual hash of previous processed PNG.
        previous_processed_at: ISO timestamp when previous version was processed.
        previous_file_size: Size of previous processed PNG in bytes.
        uploaded_hash: SHA256 hash of version currently on wiki.
        uploaded_at: ISO timestamp when uploaded to wiki.
        uploaded_filename: Full wiki filename (image_name.png).
        is_changed: True if current differs from previous (perceptual comparison).
        change_type: Type of change (new, modified, unchanged, renamed, removed).
        similarity_score: Perceptual similarity score 0.0-1.0 (1.0 = identical).
        created_at: ISO timestamp when first seen.
        updated_at: ISO timestamp when last modified.
    """

    stable_key: str
    entity_type: str
    entity_name: str
    image_name: str

    # Source tracking
    source_icon_name: str
    source_hash: str | None = None
    source_path: str | None = None

    # Current version (in current/)
    current_hash: str | None = None
    current_phash: str | None = None
    current_processed_at: str | None = None
    current_file_size: int | None = None

    # Previous version (in previous/)
    previous_hash: str | None = None
    previous_phash: str | None = None
    previous_processed_at: str | None = None
    previous_file_size: int | None = None

    # Upload tracking
    uploaded_hash: str | None = None
    uploaded_at: str | None = None
    uploaded_filename: str | None = None

    # Change detection
    is_changed: bool = False
    change_type: str | None = None
    similarity_score: float | None = None

    # Metadata
    created_at: str | None = None
    updated_at: str | None = None

    @property
    def expected_wiki_filename(self) -> str:
        """The wiki filename this image should be uploaded as."""
        return f"{sanitize_wiki_filename(self.image_name)}.png"

    @property
    def is_renamed(self) -> bool:
        """Whether the image needs re-uploading under a new wiki filename."""
        if self.uploaded_filename is None:
            return False
        return self.expected_wiki_filename != self.uploaded_filename

    def should_upload(self) -> tuple[bool, str]:
        """Check if image should be uploaded to wiki.

        Follows the same logic pattern as PageMetadata.should_deploy() from wiki storage.

        Returns:
            Tuple of (should_upload, reason):
            - (True, "") if image should be uploaded
            - (False, reason) if image should be skipped with explanation
        """
        # Must have processed content
        if self.current_processed_at is None:
            return False, "not processed"

        # Always upload if the wiki filename changed (entity was renamed)
        if self.is_renamed:
            return True, ""

        # Skip if not reprocessed since last upload
        if self.uploaded_at is not None and self.current_processed_at <= self.uploaded_at:
            return False, "not reprocessed since upload"

        # Skip if content unchanged
        if self.current_hash == self.uploaded_hash:
            return False, "content unchanged"

        return True, ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization or SQL queries."""
        return {
            "stable_key": self.stable_key,
            "entity_type": self.entity_type,
            "entity_name": self.entity_name,
            "image_name": self.image_name,
            "source_icon_name": self.source_icon_name,
            "source_hash": self.source_hash,
            "source_path": self.source_path,
            "current_hash": self.current_hash,
            "current_phash": self.current_phash,
            "current_processed_at": self.current_processed_at,
            "current_file_size": self.current_file_size,
            "previous_hash": self.previous_hash,
            "previous_phash": self.previous_phash,
            "previous_processed_at": self.previous_processed_at,
            "previous_file_size": self.previous_file_size,
            "uploaded_hash": self.uploaded_hash,
            "uploaded_at": self.uploaded_at,
            "uploaded_filename": self.uploaded_filename,
            "is_changed": self.is_changed,
            "change_type": self.change_type,
            "similarity_score": self.similarity_score,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageMetadata:
        """Create from dictionary after database query or JSON deserialization."""
        return cls(**data)


class ChangeType:
    """Constants for change_type field values."""

    NEW = "new"  # First time seeing this image
    MODIFIED = "modified"  # Visual content changed (perceptual similarity < threshold)
    UNCHANGED = "unchanged"  # Visual content unchanged (perceptual similarity >= threshold)
    RENAMED = "renamed"  # Entity renamed, needs re-upload under new wiki filename
    REMOVED = "removed"  # Exists in previous but not in current


@dataclass
class ComparisonReport:
    """Summary of image comparison results.

    Generated after comparing current vs previous image versions.

    Attributes:
        total: Total number of images compared.
        new: Number of new images (not in previous).
        modified: Number of images with visual changes.
        unchanged: Number of images with no visual changes.
        renamed: Number of images needing re-upload under a new wiki filename.
        removed: Number of images removed (in previous but not current).
        changed_images: List of ImageMetadata for changed images.
        similarity_threshold: Threshold used for comparison (0.0-1.0).
    """

    total: int
    new: int
    modified: int
    unchanged: int
    renamed: int
    removed: int
    changed_images: list[ImageMetadata]
    similarity_threshold: float

    @property
    def changed_count(self) -> int:
        """Total number of changed images (new + modified + renamed)."""
        return self.new + self.modified + self.renamed

    def summary_text(self) -> str:
        """Generate human-readable summary text."""
        lines = [
            f"Total images: {self.total}",
            f"New: {self.new}",
            f"Modified: {self.modified}",
            f"Renamed: {self.renamed}",
            f"Unchanged: {self.unchanged}",
            f"Removed: {self.removed}",
            f"Similarity threshold: {self.similarity_threshold * 100:.0f}%",
        ]
        return "\n".join(lines)

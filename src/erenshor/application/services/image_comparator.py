"""Image comparison service for detecting changes between versions.

This module provides the ImageComparator service for comparing current and
previous image versions to detect visual changes using perceptual hashing.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

if TYPE_CHECKING:
    from erenshor.application.services.image_registry import ImageRegistry
    from erenshor.domain.entities.image import ComparisonReport

__all__ = ["ImageComparator"]


class ImageComparator:
    """Compare current and previous image versions to detect changes.

    Uses the ImageRegistry's perceptual hashing to detect visual differences
    between current and previous image versions.

    Example:
        >>> registry = ImageRegistry(Path("variants/main/images/registry.db"))
        >>> comparator = ImageComparator(
        ...     registry=registry,
        ...     current_dir=Path("variants/main/images/current"),
        ...     previous_dir=Path("variants/main/images/previous")
        ... )
        >>> report = comparator.compare_all(similarity_threshold=0.95)
        >>> print(report.summary_text())
    """

    def __init__(
        self,
        registry: ImageRegistry,
        current_dir: Path,
        previous_dir: Path,
    ):
        """Initialize image comparator.

        Args:
            registry: ImageRegistry instance for tracking changes.
            current_dir: Directory with current processed images.
            previous_dir: Directory with previous processed images (for comparison).
        """
        self.registry = registry
        self.current_dir = current_dir
        self.previous_dir = previous_dir

    def compare_all(self, similarity_threshold: float = 0.95) -> ComparisonReport:
        """Compare all images and generate report.

        Runs perceptual hash comparison via the registry and returns statistics
        about what changed.

        Args:
            similarity_threshold: Perceptual similarity threshold (0.0-1.0).
                Images with similarity >= threshold are considered unchanged.
                Default: 0.95 (95% similar = unchanged).

        Returns:
            ComparisonReport with statistics and list of changed images.
        """
        from erenshor.domain.entities.image import ComparisonReport

        logger.info(f"Comparing images with {similarity_threshold * 100:.0f}% similarity threshold")

        # Run perceptual hash comparison in registry
        self.registry.detect_changes(similarity_threshold)

        # Get statistics
        stats = self.registry.get_change_stats()

        # Get changed images
        changed = self.registry.get_changed_images()

        logger.info(
            f"Comparison complete: {stats['new']} new, {stats['modified']} modified, "
            f"{stats['unchanged']} unchanged, {stats['removed']} removed"
        )

        return ComparisonReport(
            total=stats["total"],
            new=stats["new"],
            modified=stats["modified"],
            unchanged=stats["unchanged"],
            removed=stats["removed"],
            changed_images=changed,
            similarity_threshold=similarity_threshold,
        )

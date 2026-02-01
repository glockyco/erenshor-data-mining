"""Image registry for tracking versions, changes, and deployments.

This module provides the ImageRegistry service for managing image lifecycle metadata:
- Track source, current, previous, and uploaded versions
- Detect changes using perceptual hashing
- Determine what needs reprocessing or uploading
- Maintain SQLite database of image metadata

The registry enables efficient image processing by:
- Skipping unchanged source files (source hash comparison)
- Detecting visual changes (perceptual hash comparison)
- Uploading only changed images (deduplication by image_name)
- Tracking deployment status
"""

from __future__ import annotations

import hashlib
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import imagehash
from loguru import logger
from PIL import Image

from erenshor.infrastructure.wiki.filename_sanitizer import sanitize_wiki_filename

if TYPE_CHECKING:
    from erenshor.domain.entities.image import ImageInfo, ImageMetadata, ProcessingResult

__all__ = ["ImageRegistry", "ImageRegistryError"]


class ImageRegistryError(Exception):
    """Base exception for image registry errors."""

    pass


class ImageRegistry:
    """Registry for tracking image versions and changes.

    Manages a SQLite database that tracks:
    - Source file hashes (to detect when Unity assets change)
    - Current and previous processed versions
    - Upload status and timestamps
    - Change detection via perceptual hashing

    Example:
        >>> registry = ImageRegistry(Path("variants/main/images/registry.db"))
        >>> registry.register_processed_image(
        ...     stable_key="item:gen - kgti",
        ...     image_info=image_info,
        ...     processing_result=result
        ... )
        >>> changed = registry.get_changed_images()
        >>> for img in changed:
        ...     print(f"{img.entity_name}: {img.change_type}")
    """

    def __init__(self, registry_db_path: Path):
        """Initialize image registry.

        Args:
            registry_db_path: Path to SQLite database file.
        """
        self.db_path = registry_db_path
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database schema.

        Creates the image_versions table and indexes if they don't exist.
        """
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create image_versions table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS image_versions (
                    -- Identity
                    stable_key TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_name TEXT NOT NULL,
                    image_name TEXT NOT NULL,

                    -- Source tracking
                    source_icon_name TEXT NOT NULL,
                    source_hash TEXT,
                    source_path TEXT,

                    -- Current version (in current/)
                    current_hash TEXT,
                    current_phash TEXT,
                    current_processed_at TEXT,
                    current_file_size INTEGER,

                    -- Previous version (in previous/)
                    previous_hash TEXT,
                    previous_phash TEXT,
                    previous_processed_at TEXT,
                    previous_file_size INTEGER,

                    -- Upload tracking
                    uploaded_hash TEXT,
                    uploaded_at TEXT,
                    uploaded_filename TEXT,

                    -- Change detection
                    is_changed INTEGER DEFAULT 0,
                    change_type TEXT,
                    similarity_score REAL,

                    -- Metadata
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Create indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_image_versions_entity_type
                ON image_versions(entity_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_image_versions_change_type
                ON image_versions(change_type)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_image_versions_is_changed
                ON image_versions(is_changed)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_image_versions_image_name
                ON image_versions(image_name)
            """)

            conn.commit()

        logger.debug(f"Initialized image registry database: {self.db_path}")

    def _calculate_file_hashes(self, file_path: Path) -> tuple[str, str, int]:
        """Calculate content hash, perceptual hash, and file size.

        Args:
            file_path: Path to the image file.

        Returns:
            Tuple of (content_hash, perceptual_hash, file_size).

        Raises:
            FileNotFoundError: If file doesn't exist.
        """
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        # Calculate SHA256 content hash
        sha256 = hashlib.sha256()
        with file_path.open("rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        content_hash = sha256.hexdigest()

        # Calculate perceptual hash
        with Image.open(file_path) as img:
            perceptual_hash = str(imagehash.phash(img))

        # Get file size
        file_size = file_path.stat().st_size

        return content_hash, perceptual_hash, file_size

    def register_processed_image(
        self,
        stable_key: str,
        image_info: ImageInfo,
        processing_result: ProcessingResult,
        previous_dir: Path | None = None,
    ) -> None:
        """Register a processed image in the registry.

        Updates current_* fields and calculates previous_* from filesystem if available.
        Creates new record if entity not seen before.

        Args:
            stable_key: Stable identifier "entity_type:resource_name".
            image_info: Discovery information (entity names, source path).
            processing_result: Processing metadata (hashes, size, timestamp).
            previous_dir: Optional path to previous/ directory for hash calculation.
                If provided, calculates hashes from actual backed-up files.
                If not provided, copies database values (for backward compatibility).
        """
        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check if record exists
            cursor.execute("SELECT stable_key FROM image_versions WHERE stable_key = ?", (stable_key,))
            exists = cursor.fetchone() is not None

            if exists:
                # Calculate previous_* from filesystem if available
                if previous_dir:
                    # Build filename from stable_key
                    filename = stable_key.replace(":", "@", 1).replace("/", "_").replace("\\", "_") + ".png"
                    previous_file = previous_dir / filename

                    if previous_file.exists():
                        # Calculate hashes from backed-up file
                        try:
                            prev_hash, prev_phash, prev_size = self._calculate_file_hashes(previous_file)
                            prev_processed_at = datetime.fromtimestamp(
                                previous_file.stat().st_mtime, tz=UTC
                            ).isoformat()
                        except Exception as e:
                            logger.warning(f"Failed to calculate hash for {previous_file}: {e}, using database values")
                            # Fall back to database copy
                            prev_hash = None
                            prev_phash = None
                            prev_processed_at = None
                            prev_size = None
                    else:
                        # File doesn't exist in previous/, use database copy
                        prev_hash = None
                        prev_phash = None
                        prev_processed_at = None
                        prev_size = None
                else:
                    # No previous_dir provided, use database copy
                    prev_hash = None
                    prev_phash = None
                    prev_processed_at = None
                    prev_size = None

                # Update previous_* (either from filesystem or from database)
                if prev_hash is not None:
                    # Use calculated values from filesystem
                    cursor.execute(
                        """
                        UPDATE image_versions
                        SET previous_hash = ?,
                            previous_phash = ?,
                            previous_processed_at = ?,
                            previous_file_size = ?,
                            updated_at = ?
                        WHERE stable_key = ?
                        """,
                        (prev_hash, prev_phash, prev_processed_at, prev_size, now, stable_key),
                    )
                else:
                    # Fall back to database copy
                    cursor.execute(
                        """
                        UPDATE image_versions
                        SET previous_hash = current_hash,
                            previous_phash = current_phash,
                            previous_processed_at = current_processed_at,
                            previous_file_size = current_file_size,
                            updated_at = ?
                        WHERE stable_key = ?
                        """,
                        (now, stable_key),
                    )

                # Update current_* and refresh identity fields
                cursor.execute(
                    """
                    UPDATE image_versions
                    SET entity_type = ?,
                        entity_name = ?,
                        image_name = ?,
                        source_icon_name = ?,
                        current_hash = ?,
                        current_phash = ?,
                        current_processed_at = ?,
                        current_file_size = ?,
                        source_hash = ?,
                        source_path = ?,
                        updated_at = ?
                    WHERE stable_key = ?
                    """,
                    (
                        image_info.entity_type,
                        image_info.entity_name,
                        image_info.image_name,
                        image_info.icon_name,
                        processing_result.content_hash,
                        processing_result.perceptual_hash,
                        processing_result.processed_at,
                        processing_result.file_size,
                        processing_result.source_hash,
                        str(image_info.source_path) if image_info.source_path else None,
                        now,
                        stable_key,
                    ),
                )
            else:
                # Create new record
                cursor.execute(
                    """
                    INSERT INTO image_versions (
                        stable_key,
                        entity_type,
                        entity_name,
                        image_name,
                        source_icon_name,
                        source_hash,
                        source_path,
                        current_hash,
                        current_phash,
                        current_processed_at,
                        current_file_size,
                        created_at,
                        updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        stable_key,
                        image_info.entity_type,
                        image_info.entity_name,
                        image_info.image_name,
                        image_info.icon_name,
                        processing_result.source_hash,
                        str(image_info.source_path) if image_info.source_path else None,
                        processing_result.content_hash,
                        processing_result.perceptual_hash,
                        processing_result.processed_at,
                        processing_result.file_size,
                        now,
                        now,
                    ),
                )

            conn.commit()

        logger.debug(f"Registered processed image: {stable_key}")

    def update_entity_names(self, stable_key: str, image_info: ImageInfo) -> bool:
        """Update entity identity fields without reprocessing the image.

        Called when an image is skipped (source unchanged) to ensure renamed
        entities have their current names in the registry.

        Args:
            stable_key: Stable identifier "entity_type:resource_name".
            image_info: Current discovery information with resolved names.

        Returns:
            True if any field was actually updated, False if already current.
        """
        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE image_versions
                SET entity_type = ?,
                    entity_name = ?,
                    image_name = ?,
                    source_icon_name = ?,
                    updated_at = ?
                WHERE stable_key = ?
                  AND (entity_type != ? OR entity_name != ?
                       OR image_name != ? OR source_icon_name != ?)
                """,
                (
                    image_info.entity_type,
                    image_info.entity_name,
                    image_info.image_name,
                    image_info.icon_name,
                    now,
                    stable_key,
                    image_info.entity_type,
                    image_info.entity_name,
                    image_info.image_name,
                    image_info.icon_name,
                ),
            )

            updated = cursor.rowcount > 0
            conn.commit()

        if updated:
            logger.info(f"Updated entity names for {stable_key}: {image_info.image_name}")

        return updated

    def detect_changes(self, similarity_threshold: float = 0.95) -> None:
        """Detect changes between current and previous versions.

        Compares perceptual hashes for visual changes and wiki filenames
        for renames. Updates is_changed, change_type, and similarity_score
        fields for all images.

        Args:
            similarity_threshold: Perceptual similarity threshold (0.0-1.0).
                Below this threshold = changed, above = unchanged.
                Default: 0.95 (95% similar = unchanged).
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT stable_key, current_phash, previous_phash,
                       image_name, uploaded_filename
                FROM image_versions
                WHERE current_phash IS NOT NULL
            """)

            for row in cursor.fetchall():
                stable_key = row["stable_key"]
                current_phash = row["current_phash"]
                previous_phash = row["previous_phash"]

                if previous_phash is None:
                    change_type = "new"
                    is_changed = True
                    similarity_score = 0.0
                else:
                    # Calculate perceptual similarity
                    try:
                        current_hash = imagehash.hex_to_hash(current_phash)
                        previous_hash = imagehash.hex_to_hash(previous_phash)

                        # Hamming distance (0 = identical, higher = different)
                        distance = current_hash - previous_hash

                        # Convert to similarity (1.0 = identical, 0.0 = completely different)
                        # pHash is 64-bit, so max distance is 64
                        similarity_score = 1.0 - (distance / 64.0)

                        if similarity_score >= similarity_threshold:
                            change_type = "unchanged"
                            is_changed = False
                        else:
                            change_type = "modified"
                            is_changed = True
                    except Exception as e:
                        logger.warning(f"Failed to compare perceptual hashes for {stable_key}: {e}")
                        change_type = "unchanged"
                        is_changed = False
                        similarity_score = 1.0

                # Detect renames: wiki filename changed but visual content didn't
                if not is_changed and row["uploaded_filename"] is not None:
                    expected = f"{sanitize_wiki_filename(row['image_name'])}.png"
                    if expected != row["uploaded_filename"]:
                        change_type = "renamed"
                        is_changed = True

                cursor.execute(
                    """
                    UPDATE image_versions
                    SET is_changed = ?,
                        change_type = ?,
                        similarity_score = ?
                    WHERE stable_key = ?
                    """,
                    (is_changed, change_type, similarity_score, stable_key),
                )

            conn.commit()

        logger.info(f"Detected changes with {similarity_threshold * 100:.0f}% similarity threshold")

    def get_image_metadata(self, stable_key: str) -> ImageMetadata | None:
        """Get metadata for a specific image.

        Args:
            stable_key: Stable identifier "entity_type:resource_name".

        Returns:
            ImageMetadata if found, None otherwise.
        """
        from erenshor.domain.entities.image import ImageMetadata

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("SELECT * FROM image_versions WHERE stable_key = ?", (stable_key,))
            row = cursor.fetchone()

            if row is None:
                return None

            return ImageMetadata(
                stable_key=row["stable_key"],
                entity_type=row["entity_type"],
                entity_name=row["entity_name"],
                image_name=row["image_name"],
                source_icon_name=row["source_icon_name"],
                source_hash=row["source_hash"],
                source_path=row["source_path"],
                current_hash=row["current_hash"],
                current_phash=row["current_phash"],
                current_processed_at=row["current_processed_at"],
                current_file_size=row["current_file_size"],
                previous_hash=row["previous_hash"],
                previous_phash=row["previous_phash"],
                previous_processed_at=row["previous_processed_at"],
                previous_file_size=row["previous_file_size"],
                uploaded_hash=row["uploaded_hash"],
                uploaded_at=row["uploaded_at"],
                uploaded_filename=row["uploaded_filename"],
                is_changed=bool(row["is_changed"]),
                change_type=row["change_type"],
                similarity_score=row["similarity_score"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

    def get_changed_images(self) -> list[ImageMetadata]:
        """Get all images that changed (new or modified).

        Returns:
            List of ImageMetadata for changed images, sorted by entity_type and entity_name.
        """
        from erenshor.domain.entities.image import ImageMetadata

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute("""
                SELECT * FROM image_versions
                WHERE is_changed = 1
                ORDER BY entity_type, entity_name
            """)

            return [
                ImageMetadata(
                    stable_key=row["stable_key"],
                    entity_type=row["entity_type"],
                    entity_name=row["entity_name"],
                    image_name=row["image_name"],
                    source_icon_name=row["source_icon_name"],
                    source_hash=row["source_hash"],
                    source_path=row["source_path"],
                    current_hash=row["current_hash"],
                    current_phash=row["current_phash"],
                    current_processed_at=row["current_processed_at"],
                    current_file_size=row["current_file_size"],
                    previous_hash=row["previous_hash"],
                    previous_phash=row["previous_phash"],
                    previous_processed_at=row["previous_processed_at"],
                    previous_file_size=row["previous_file_size"],
                    uploaded_hash=row["uploaded_hash"],
                    uploaded_at=row["uploaded_at"],
                    uploaded_filename=row["uploaded_filename"],
                    is_changed=bool(row["is_changed"]),
                    change_type=row["change_type"],
                    similarity_score=row["similarity_score"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
                for row in cursor.fetchall()
            ]

    def get_deployment_list(self) -> dict[str, ImageMetadata]:
        """Get unique image_names that need deployment.

        Returns a dictionary mapping image_name to ImageMetadata, deduplicating
        multiple entities that share the same image_name. Last entity wins for
        each image_name.

        This ensures we upload each unique wiki filename only once, even if
        multiple entities share the same image.

        Returns:
            Dictionary mapping image_name to ImageMetadata for images needing upload.
        """
        from erenshor.domain.entities.image import ImageMetadata

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            # Get all changed images that need upload
            cursor.execute("""
                SELECT * FROM image_versions
                WHERE is_changed = 1
                  AND (uploaded_hash IS NULL OR uploaded_hash != current_hash
                       OR change_type = 'renamed')
                ORDER BY entity_type, entity_name
            """)

            # Deduplicate by image_name (last one wins)
            deployment_dict: dict[str, ImageMetadata] = {}

            for row in cursor.fetchall():
                metadata = ImageMetadata(
                    stable_key=row["stable_key"],
                    entity_type=row["entity_type"],
                    entity_name=row["entity_name"],
                    image_name=row["image_name"],
                    source_icon_name=row["source_icon_name"],
                    source_hash=row["source_hash"],
                    source_path=row["source_path"],
                    current_hash=row["current_hash"],
                    current_phash=row["current_phash"],
                    current_processed_at=row["current_processed_at"],
                    current_file_size=row["current_file_size"],
                    previous_hash=row["previous_hash"],
                    previous_phash=row["previous_phash"],
                    previous_processed_at=row["previous_processed_at"],
                    previous_file_size=row["previous_file_size"],
                    uploaded_hash=row["uploaded_hash"],
                    uploaded_at=row["uploaded_at"],
                    uploaded_filename=row["uploaded_filename"],
                    is_changed=bool(row["is_changed"]),
                    change_type=row["change_type"],
                    similarity_score=row["similarity_score"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )

                # Use image_name as key to deduplicate
                deployment_dict[metadata.image_name] = metadata

            return deployment_dict

    def mark_uploaded(self, stable_key: str, uploaded_hash: str, wiki_filename: str) -> None:
        """Mark an image as successfully uploaded to wiki.

        Args:
            stable_key: Stable identifier "entity_type:resource_name".
            uploaded_hash: Hash of the uploaded file (should match current_hash).
            wiki_filename: Full wiki filename (e.g., "Kingly Gift.png").
        """
        now = datetime.now(UTC).isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE image_versions
                SET uploaded_hash = ?,
                    uploaded_at = ?,
                    uploaded_filename = ?,
                    updated_at = ?
                WHERE stable_key = ?
                """,
                (uploaded_hash, now, wiki_filename, now, stable_key),
            )

            conn.commit()

        logger.debug(f"Marked uploaded: {stable_key} → {wiki_filename}")

    def should_reprocess(self, stable_key: str, source_path: Path) -> bool:
        """Check if an image needs reprocessing.

        Determines if reprocessing is needed by:
        1. Checking if entity exists in registry
        2. Comparing source file hash
        3. Checking if output file exists

        Args:
            stable_key: Stable identifier "entity_type:resource_name".
            source_path: Path to source Unity texture file.

        Returns:
            True if image should be reprocessed, False if can skip.
        """
        # Get existing metadata
        metadata = self.get_image_metadata(stable_key)

        if metadata is None:
            # New entity - must process
            return True

        # Check if source file changed
        if source_path.exists():
            source_hash = self._sha256_file(source_path)
            if source_hash != metadata.source_hash:
                # Source updated - must reprocess
                logger.debug(f"Source changed for {stable_key}, reprocessing")
                return True

        # If we got here, source unchanged and entity exists
        # Could add additional checks (e.g., output file exists)
        return False

    def get_change_stats(self) -> dict[str, int]:
        """Get statistics about image changes.

        Returns:
            Dictionary with counts:
            - total: Total images in registry
            - new: New images
            - modified: Modified images
            - unchanged: Unchanged images
            - renamed: Renamed images (new wiki filename needed)
            - removed: Removed images (if tracked)
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Total count
            cursor.execute("SELECT COUNT(*) FROM image_versions")
            total = cursor.fetchone()[0]

            # Count by change_type
            cursor.execute("""
                SELECT change_type, COUNT(*) as count
                FROM image_versions
                GROUP BY change_type
            """)

            counts = {row[0]: row[1] for row in cursor.fetchall() if row[0]}

            return {
                "total": total,
                "new": counts.get("new", 0),
                "modified": counts.get("modified", 0),
                "unchanged": counts.get("unchanged", 0),
                "renamed": counts.get("renamed", 0),
                "removed": counts.get("removed", 0),
            }

    @staticmethod
    def _sha256_file(file_path: Path) -> str:
        """Calculate SHA256 hash of a file.

        Args:
            file_path: Path to file.

        Returns:
            Hex string of SHA256 hash.
        """
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            # Read file in chunks for memory efficiency
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

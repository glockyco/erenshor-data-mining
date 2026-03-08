"""Service for processing game images from Unity assets.

This service handles the image processing pipeline:
1. Discover images from database (Items, Spells, Skills)
2. Process images: resize, pad, add borders/backgrounds
3. Generate metadata (hashes, timestamps) for registry tracking

Processing rules:
- Spells/Skills: Add black border (8px), resize to 150x150
- Items: Overlay on background image, resize to 150x150
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import imagehash
from PIL import Image

if TYPE_CHECKING:
    from erenshor.domain.entities.image import ImageInfo, ProcessingResult

__all__ = ["ImageProcessor"]


class ImageProcessor:
    """Process game images: resize, pad, add borders."""

    # Output image size
    IMAGE_SIZE = (150, 150)

    # Border settings for spells/skills
    BORDER_SIZE = 8
    BORDER_COLOR = (0, 0, 0, 255)

    # Background image for items
    BACKGROUND_IMAGE_PATH = "images/icon-background.png"

    def __init__(
        self,
        texture_dir: Path,
        output_dir: Path,
        game_db_path: Path,
    ):
        """Initialize image processor.

        Args:
            texture_dir: Directory with source PNG files (from Unity)
            output_dir: Directory to write processed images
            game_db_path: Path to the clean game database (snake_case columns)
        """
        self.texture_dir = texture_dir
        self.output_dir = output_dir
        self.game_db_path = game_db_path

    def discover_images(self) -> Iterator[ImageInfo]:
        """Discover all images from game database.

        Queries the clean game database for icon file names and image_name.
        Only entities with a non-null wiki_page_name (i.e. not excluded) and a
        non-null image_name are yielded.

        Yields:
            ImageInfo for each entity with an icon
        """
        import sqlite3

        conn = sqlite3.connect(self.game_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Items
            cursor.execute(
                "SELECT stable_key, item_name, item_icon_name, wiki_page_name, image_name "
                "FROM items "
                "WHERE item_icon_name IS NOT NULL AND item_icon_name != '' "
                "AND wiki_page_name IS NOT NULL AND image_name IS NOT NULL"
            )
            for row in cursor.fetchall():
                stable_key = row["stable_key"]
                icon_name = row["item_icon_name"]
                entity_name = row["wiki_page_name"]
                image_name = row["image_name"]
                source_path = self.texture_dir / f"{icon_name}.png"

                from erenshor.domain.entities.image import ImageInfo

                yield ImageInfo(
                    entity_type="item",
                    stable_key=stable_key,
                    entity_name=entity_name,
                    image_name=image_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )

            # Spells
            cursor.execute(
                "SELECT stable_key, spell_name, spell_icon_name, wiki_page_name, image_name "
                "FROM spells "
                "WHERE spell_icon_name IS NOT NULL AND spell_icon_name != '' "
                "AND wiki_page_name IS NOT NULL AND image_name IS NOT NULL"
            )
            for row in cursor.fetchall():
                stable_key = row["stable_key"]
                icon_name = row["spell_icon_name"]
                entity_name = row["wiki_page_name"]
                image_name = row["image_name"]
                source_path = self.texture_dir / f"{icon_name}.png"

                from erenshor.domain.entities.image import ImageInfo

                yield ImageInfo(
                    entity_type="spell",
                    stable_key=stable_key,
                    entity_name=entity_name,
                    image_name=image_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )

            # Skills
            cursor.execute(
                "SELECT stable_key, skill_name, skill_icon_name, wiki_page_name, image_name "
                "FROM skills "
                "WHERE skill_icon_name IS NOT NULL AND skill_icon_name != '' "
                "AND wiki_page_name IS NOT NULL AND image_name IS NOT NULL"
            )
            for row in cursor.fetchall():
                stable_key = row["stable_key"]
                icon_name = row["skill_icon_name"]
                entity_name = row["wiki_page_name"]
                image_name = row["image_name"]
                source_path = self.texture_dir / f"{icon_name}.png"

                from erenshor.domain.entities.image import ImageInfo

                yield ImageInfo(
                    entity_type="skill",
                    stable_key=stable_key,
                    entity_name=entity_name,
                    image_name=image_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )
        finally:
            conn.close()

    def process_single_image(self, image_info: ImageInfo, output_path: Path) -> ProcessingResult:
        """Process a single image and generate metadata.

        Args:
            image_info: Image discovery information.
            output_path: Where to write processed image.

        Returns:
            ProcessingResult with hashes and metadata.

        Raises:
            ValueError: If source file doesn't exist.
            Exception: If processing fails.
        """
        from erenshor.domain.entities.image import ProcessingResult

        if not image_info.source_path or not image_info.source_path.exists():
            raise ValueError(f"Source not found: {image_info.icon_name}")

        # Calculate source hash before processing
        source_hash = self._sha256_file(image_info.source_path)

        # Process the image
        with Image.open(image_info.source_path) as source_img:
            img = source_img.convert("RGBA")

            if image_info.entity_type in ("spell", "skill"):
                # Spells/skills: resize with border
                img = self._resize_and_pad_with_border(img, self.IMAGE_SIZE, self.BORDER_COLOR, self.BORDER_SIZE)
            else:
                # Items: resize and overlay on background
                img = self._resize_and_pad(img, self.IMAGE_SIZE)
                img = self._overlay_on_background(img, self.IMAGE_SIZE)

            # Save processed image
            img.save(output_path, "PNG")

            # Generate perceptual hash
            perceptual_hash = str(imagehash.phash(img))

            # Get dimensions
            dimensions = img.size

        # Calculate content hash of processed file
        content_hash = self._sha256_file(output_path)

        # Get file size
        file_size = output_path.stat().st_size

        # Generate timestamp
        processed_at = datetime.now(UTC).isoformat()

        return ProcessingResult(
            content_hash=content_hash,
            perceptual_hash=perceptual_hash,
            source_hash=source_hash,
            file_size=file_size,
            dimensions=dimensions,
            processed_at=processed_at,
        )

    def _get_filename(self, image_info: ImageInfo) -> str:
        """Get output filename using stable key format."""
        filename_base = image_info.stable_key.replace(":", "@", 1)
        filename_base = filename_base.replace("/", "_").replace("\\", "_")
        return f"{filename_base}.png"

    @staticmethod
    def _sha256_file(file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        sha256_hash = hashlib.sha256()
        with file_path.open("rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def _resize_and_pad(self, image: Image.Image, size: tuple[int, int]) -> Image.Image:
        """Resize image to fit within size, preserving aspect ratio."""
        image.thumbnail(size, Image.Resampling.LANCZOS)

        new_image = Image.new("RGBA", size, (0, 0, 0, 0))

        left = (size[0] - image.width) // 2
        top = (size[1] - image.height) // 2
        new_image.paste(image, (left, top), image)

        return new_image

    def _overlay_on_background(self, icon: Image.Image, size: tuple[int, int]) -> Image.Image:
        """Overlay icon on background image (for items)."""
        background_path = Path(self.BACKGROUND_IMAGE_PATH)
        if not background_path.exists():
            return icon

        with Image.open(background_path) as bg_img:
            bg = bg_img.convert("RGBA")
            bg = bg.resize(size, Image.Resampling.LANCZOS)
            left = (size[0] - icon.width) // 2
            top = (size[1] - icon.height) // 2
            bg.paste(icon, (left, top), icon)
            return bg

    def _resize_and_pad_with_border(
        self,
        image: Image.Image,
        size: tuple[int, int],
        border_color: tuple[int, int, int, int],
        border_size: int,
    ) -> Image.Image:
        """Resize image and add border around it."""
        inner_width = size[0] - 2 * border_size
        inner_height = size[1] - 2 * border_size

        inner_image = self._resize_and_pad(image, (inner_width, inner_height))

        bordered_image = Image.new("RGBA", size, border_color)
        bordered_image.paste(inner_image, (border_size, border_size), inner_image)

        return bordered_image

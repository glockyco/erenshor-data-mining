"""Service for processing game images from Unity assets.

This service handles the image processing pipeline:
1. Discover images from database (Items, Spells, Skills)
2. Process images: resize, pad, add borders/backgrounds
3. Save processed images with stable_key naming

Processing rules:
- Spells/Skills: Add black border (8px), resize to 150x150
- Items: Overlay on background image, resize to 150x150
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from erenshor.registry.resolver import RegistryResolver

__all__ = ["ImageInfo", "ImageProcessor", "ProcessedImage"]


@dataclass
class ImageInfo:
    """Information about a source image."""

    entity_type: str  # "item", "spell", "skill"
    stable_key: str  # e.g., "item:gen - kgti"
    entity_name: str  # e.g., "Kingly Gift"
    icon_name: str  # e.g., "GEN - KGTI"
    source_path: Path | None  # Path to source PNG in Unity assets


@dataclass
class ProcessedImage:
    """Result of processing a single image."""

    entity_name: str
    entity_type: str
    action: str  # "processed", "skipped", "failed"
    message: str
    output_path: Path | None = None


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
        resolver: RegistryResolver,
        game_db_path: Path,
    ):
        """Initialize image processor.

        Args:
            texture_dir: Directory with source PNG files (from Unity)
            output_dir: Directory to write processed images
            resolver: Registry resolver for entity lookups
            game_db_path: Path to game database for icon file names
        """
        self.texture_dir = texture_dir
        self.output_dir = output_dir
        self.resolver = resolver
        self.game_db_path = game_db_path

    def discover_images(self) -> Iterator[ImageInfo]:
        """Discover all images from game database.

        Queries the game database directly for icon file names (ItemIconName,
        SpellIconName, SkillIconName) and uses registry for entity names.

        Yields:
            ImageInfo for each entity with an icon (excluding excluded entities)
        """
        import sqlite3

        # Connect to game database
        conn = sqlite3.connect(self.game_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Items
            cursor.execute(
                "SELECT StableKey, ItemName, ItemIconName FROM Items "
                "WHERE ItemIconName IS NOT NULL AND ItemIconName != ''"
            )
            for row in cursor.fetchall():
                stable_key = row["StableKey"]
                icon_name = row["ItemIconName"]

                # Check if excluded in registry
                try:
                    entity_name = self.resolver.resolve_page_title(stable_key)
                except ValueError:
                    continue

                if entity_name is None:
                    continue

                source_path = self.texture_dir / f"{icon_name}.png"

                yield ImageInfo(
                    entity_type="item",
                    stable_key=stable_key,
                    entity_name=entity_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )

            # Spells
            cursor.execute(
                "SELECT StableKey, SpellName, SpellIconName FROM Spells "
                "WHERE SpellIconName IS NOT NULL AND SpellIconName != ''"
            )
            for row in cursor.fetchall():
                stable_key = row["StableKey"]
                icon_name = row["SpellIconName"]

                try:
                    entity_name = self.resolver.resolve_page_title(stable_key)
                except ValueError:
                    continue

                if entity_name is None:
                    continue

                source_path = self.texture_dir / f"{icon_name}.png"

                yield ImageInfo(
                    entity_type="spell",
                    stable_key=stable_key,
                    entity_name=entity_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )

            # Skills
            cursor.execute(
                "SELECT StableKey, SkillName, SkillIconName FROM Skills "
                "WHERE SkillIconName IS NOT NULL AND SkillIconName != ''"
            )
            for row in cursor.fetchall():
                stable_key = row["StableKey"]
                icon_name = row["SkillIconName"]

                try:
                    entity_name = self.resolver.resolve_page_title(stable_key)
                except ValueError:
                    continue

                if entity_name is None:
                    continue

                source_path = self.texture_dir / f"{icon_name}.png"

                yield ImageInfo(
                    entity_type="skill",
                    stable_key=stable_key,
                    entity_name=entity_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )
        finally:
            conn.close()

    def process_images(self, force: bool = False) -> Iterator[ProcessedImage]:
        """Process all images: resize, pad, border.

        Args:
            force: Reprocess even if output exists

        Yields:
            ProcessedImage for each entity
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for image_info in self.discover_images():
            # Get final filename using stable key
            filename = self._get_filename(image_info)
            output_path = self.output_dir / filename

            # Skip if already processed (unless force)
            if not force and output_path.exists():
                yield ProcessedImage(
                    entity_name=image_info.entity_name,
                    entity_type=image_info.entity_type,
                    action="skipped",
                    message="Already processed",
                    output_path=output_path,
                )
                continue

            # Check if source exists
            if not image_info.source_path or not image_info.source_path.exists():
                yield ProcessedImage(
                    entity_name=image_info.entity_name,
                    entity_type=image_info.entity_type,
                    action="failed",
                    message=f"Source not found: {image_info.icon_name}",
                )
                continue

            # Process the image
            try:
                self._process_image(
                    image_info.source_path,
                    output_path,
                    image_info.entity_type,
                )
                yield ProcessedImage(
                    entity_name=image_info.entity_name,
                    entity_type=image_info.entity_type,
                    action="processed",
                    message="Processed successfully",
                    output_path=output_path,
                )
            except Exception as e:
                yield ProcessedImage(
                    entity_name=image_info.entity_name,
                    entity_type=image_info.entity_type,
                    action="failed",
                    message=f"Processing error: {e}",
                )

    def _get_filename(self, image_info: ImageInfo) -> str:
        """Get output filename using stable key format.

        Files are stored using stable key format with @ separator:
        "{entity_type}@{resource_name}.png" (e.g., "item@gen - kgti.png")

        This matches the stable_key format but uses @ instead of :
        since colons can be problematic on some filesystems.

        Args:
            image_info: Image information

        Returns:
            Filename with stable key format (e.g., "item@gen - kgti.png")
        """
        # Convert stable_key to filename (replace : with @)
        # stable_key format: "item:gen - kgti" → filename: "item@gen - kgti.png"
        filename_base = image_info.stable_key.replace(":", "@", 1)

        # Sanitize for filesystem (replace path separators)
        filename_base = filename_base.replace("/", "_").replace("\\", "_")

        return f"{filename_base}.png"

    def _process_image(self, source_path: Path, output_path: Path, entity_type: str) -> None:
        """Process a single image: resize, pad, background/border.

        Args:
            source_path: Source PNG path
            output_path: Output PNG path
            entity_type: Type of entity (item, spell, skill)
        """
        with Image.open(source_path) as source_img:
            img = source_img.convert("RGBA")

            if entity_type in ("spell", "skill"):
                # Spells/skills: resize with border
                img = self._resize_and_pad_with_border(img, self.IMAGE_SIZE, self.BORDER_COLOR, self.BORDER_SIZE)
            else:
                # Items: resize and overlay on background
                img = self._resize_and_pad(img, self.IMAGE_SIZE)
                img = self._overlay_on_background(img, self.IMAGE_SIZE)

            img.save(output_path, "PNG")

    def _resize_and_pad(self, image: Image.Image, size: tuple[int, int]) -> Image.Image:
        """Resize image to fit within size, preserving aspect ratio.

        Args:
            image: Source image
            size: Target size (width, height)

        Returns:
            Resized and padded image
        """
        # Resize preserving aspect ratio
        image.thumbnail(size, Image.Resampling.LANCZOS)

        # Create transparent background
        new_image = Image.new("RGBA", size, (0, 0, 0, 0))

        # Center the image
        left = (size[0] - image.width) // 2
        top = (size[1] - image.height) // 2
        new_image.paste(image, (left, top), image)

        return new_image

    def _overlay_on_background(self, icon: Image.Image, size: tuple[int, int]) -> Image.Image:
        """Overlay icon on background image (for items).

        Args:
            icon: Resized and padded icon
            size: Target size (width, height)

        Returns:
            Icon overlaid on background
        """
        background_path = Path(self.BACKGROUND_IMAGE_PATH)
        if not background_path.exists():
            # Fallback: return icon without background
            return icon

        with Image.open(background_path) as bg_img:
            bg = bg_img.convert("RGBA")
            bg = bg.resize(size, Image.Resampling.LANCZOS)
            # Center the icon on the background
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
        """Resize image and add border around it.

        Args:
            image: Source image
            size: Target size (width, height)
            border_color: RGBA color for border
            border_size: Border width in pixels

        Returns:
            Resized, padded, and bordered image
        """
        # Calculate inner size (leaving room for border)
        inner_width = size[0] - 2 * border_size
        inner_height = size[1] - 2 * border_size

        # Resize to inner size
        inner_image = self._resize_and_pad(image, (inner_width, inner_height))

        # Create image with border
        bordered_image = Image.new("RGBA", size, border_color)
        bordered_image.paste(inner_image, (border_size, border_size), inner_image)

        return bordered_image

"""Service for processing game images from Unity assets."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

from PIL import Image
from sqlalchemy import text

from erenshor.domain.entities.page import EntityRef
from erenshor.domain.value_objects.entity_type import EntityType
from erenshor.infrastructure.database import get_engine
from erenshor.registry.core import WikiRegistry

__all__ = ["ImageProcessor", "ImageInfo", "ProcessedImage"]


@dataclass
class ImageInfo:
    """Information about a source image."""

    entity_type: str  # "item", "spell", "skill"
    entity_id: str
    entity_name: str
    resource_name: str | None
    icon_name: str
    source_path: Path | None


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
        db_path: Path,
        texture_dir: Path,
        output_dir: Path,
        registry: WikiRegistry | None = None,
    ):
        """Initialize image processor.

        Args:
            db_path: Path to SQLite database with icon names
            texture_dir: Directory with source PNG files (from Unity)
            output_dir: Directory to write processed images
            registry: Optional WikiRegistry for name overrides
        """
        self.db_path = db_path
        self.texture_dir = texture_dir
        self.output_dir = output_dir
        self.registry = registry
        self.engine = get_engine(db_path)

    def discover_images(self) -> Iterator[ImageInfo]:
        """Discover all images from database.

        Yields:
            ImageInfo for each entity with an icon (excluding entities not in registry)
        """
        with self.engine.connect() as conn:
            # Items
            sql = text(
                "SELECT Id, ItemName, ItemIconName, ResourceName FROM Items WHERE ItemIconName IS NOT NULL AND ItemIconName != ''"
            )
            rows = conn.execute(sql).fetchall()
            for row in rows:
                entity_id, entity_name, icon_name, resource_name = row

                # Skip if excluded in registry
                if self.registry and not self._is_in_registry(
                    EntityType.ITEM, entity_id, entity_name, resource_name
                ):
                    continue

                source_path = self.texture_dir / f"{icon_name}.png"
                yield ImageInfo(
                    entity_type="item",
                    entity_id=entity_id,
                    entity_name=entity_name,
                    resource_name=resource_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )

            # Spells
            sql = text(
                "SELECT Id, SpellName, SpellIconName, ResourceName FROM Spells WHERE SpellIconName IS NOT NULL AND SpellIconName != ''"
            )
            rows = conn.execute(sql).fetchall()
            for row in rows:
                entity_id, entity_name, icon_name, resource_name = row

                # Skip if excluded in registry
                if self.registry and not self._is_in_registry(
                    EntityType.SPELL, entity_id, entity_name, resource_name
                ):
                    continue

                source_path = self.texture_dir / f"{icon_name}.png"
                yield ImageInfo(
                    entity_type="spell",
                    entity_id=entity_id,
                    entity_name=entity_name,
                    resource_name=resource_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )

            # Skills
            sql = text(
                "SELECT Id, SkillName, SkillIconName, ResourceName FROM Skills WHERE SkillIconName IS NOT NULL AND SkillIconName != ''"
            )
            rows = conn.execute(sql).fetchall()
            for row in rows:
                entity_id, entity_name, icon_name, resource_name = row

                # Skip if excluded in registry
                if self.registry and not self._is_in_registry(
                    EntityType.SKILL, entity_id, entity_name, resource_name
                ):
                    continue

                source_path = self.texture_dir / f"{icon_name}.png"
                yield ImageInfo(
                    entity_type="skill",
                    entity_id=entity_id,
                    entity_name=entity_name,
                    resource_name=resource_name,
                    icon_name=icon_name,
                    source_path=source_path if source_path.exists() else None,
                )

    def process_images(self, force: bool = False) -> Iterator[ProcessedImage]:
        """Process all images: resize, pad, border.

        Args:
            force: Reprocess even if output exists

        Yields:
            ProcessedImage for each entity
        """
        self.output_dir.mkdir(parents=True, exist_ok=True)

        for image_info in self.discover_images():
            # Get final filename (with registry overrides)
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

    def _is_in_registry(
        self,
        entity_type: EntityType,
        entity_id: str,
        entity_name: str,
        resource_name: str | None,
    ) -> bool:
        """Check if an entity is in the registry (not excluded).

        Args:
            entity_type: Type of entity
            entity_id: Database ID
            entity_name: Database name
            resource_name: Resource name (stable key component)

        Returns:
            True if entity is in registry, False if excluded
        """
        if not self.registry:
            return True

        entity_ref = EntityRef(
            entity_type=entity_type,
            db_id=entity_id,
            db_name=entity_name,
            resource_name=resource_name,
        )
        return self.registry.resolve_entity(entity_ref) is not None

    def _get_filename(self, image_info: ImageInfo) -> str:
        """Get output filename using stable key format.

        Files are stored using stable key format with @ separator:
        "{entity_type}@{resource_name}.png" (e.g., "item@GEN - KGTI.png")

        This matches the stable_key format from EntityRef but uses @ instead of :
        since colons can be problematic on some filesystems.

        Args:
            image_info: Image information

        Returns:
            Filename with stable key format (e.g., "item@GEN - KGTI.png")
        """
        # Use resource name if available, otherwise fall back to entity name
        if image_info.resource_name:
            key_part = image_info.resource_name
        else:
            # Fallback for entities without resource names (shouldn't happen)
            key_part = image_info.entity_name

        # Sanitize for filesystem (replace path separators)
        key_part = key_part.replace("/", "_").replace("\\", "_")

        # Use stable key format with @ separator
        return f"{image_info.entity_type}@{key_part}.png"

    def _sanitize_filename(self, name: str) -> str:
        """Sanitize entity name for use as filename.

        Uses the same pattern as WikiPage.safe_filename (URL encoding).
        When uploading to MediaWiki, the original name can be used directly
        since MediaWiki accepts special characters.

        Args:
            name: Entity name

        Returns:
            URL-encoded filename (no extension)
        """
        import urllib.parse

        # Replace forward slashes first to avoid directory issues (cleaner than %2F)
        safe_name = name.replace("/", "_")
        # URL-encode problematic characters (same as WikiPage.safe_filename)
        safe_name = urllib.parse.quote(safe_name, safe=" ()[]")

        return safe_name.strip()

    def _process_image(
        self, source_path: Path, output_path: Path, entity_type: str
    ) -> None:
        """Process a single image: resize, pad, background/border.

        Args:
            source_path: Source PNG path
            output_path: Output PNG path
            entity_type: Type of entity (item, spell, skill)
        """
        with Image.open(source_path) as img:
            img = img.convert("RGBA")

            if entity_type in ("spell", "skill"):
                # Spells/skills: resize with border
                img = self._resize_and_pad_with_border(
                    img, self.IMAGE_SIZE, self.BORDER_COLOR, self.BORDER_SIZE
                )
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

    def _overlay_on_background(
        self, icon: Image.Image, size: tuple[int, int]
    ) -> Image.Image:
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

        with Image.open(background_path) as bg:
            bg = bg.convert("RGBA")
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

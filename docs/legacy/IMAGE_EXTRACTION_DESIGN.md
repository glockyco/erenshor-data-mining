# Image Extraction Design Document

**Project**: Erenshor Data Mining Pipeline
**Feature**: Image extraction and processing for items, spells, skills, and other entities
**Date**: 2025-10-11
**Author**: Claude Code

---

## Executive Summary

This document proposes a **hybrid Unity + Python approach** for extracting, processing, and deploying entity icons from the Erenshor game to MediaWiki and Google Sheets. The design prioritizes simplicity, follows existing architectural patterns, and integrates seamlessly with the current two-layer CLI system.

**Key Decision**: Use Unity to locate and copy raw images, Python to process and publish them.

---

## Architecture Overview

### Current State

The project already extracts image metadata:
- **Unity Side**: `ItemRecord.ItemIconName`, `SpellRecord.SpellIconName`, `SkillRecord.SkillIconName`
- **Texture Files**: Located in `variants/{variant}/unity/Assets/Texture2D/`
- **Database**: Icon names stored in SQLite (e.g., `"1_Leather_Shoulder"`)
- **Registry**: `WikiRegistry.image_name_overrides` provides custom image name mappings

### Proposed Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Unity Export System                      │
│  • ItemListener, SpellListener, SkillListener              │
│  • NEW: ImageListener (locates and copies icon files)      │
│  • Copies PNG files to variants/{variant}/images/raw/      │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ↓ Raw PNG files
┌─────────────────────────────────────────────────────────────┐
│              Python Image Processing Service                │
│  • Resize images to standard dimensions (150x150)          │
│  • Add borders for spell/skill icons                        │
│  • Handle name conflicts and sanitization                   │
│  • Save to variants/{variant}/images/processed/            │
└───────────────────┬─────────────────────────────────────────┘
                    │
                    ↓ Processed images
┌─────────────────────────────────────────────────────────────┐
│                   Deployment Layer                          │
│  • MediaWiki: Upload via Special:Upload API                │
│  • Google Sheets: Embed via IMAGE() formula (URLs only)    │
└─────────────────────────────────────────────────────────────┘
```

---

## Design Decisions

### 1. Why Hybrid (Unity + Python)?

**Unity Side (Image Location)**:
- Unity Editor has direct access to `AssetDatabase` for finding Texture2D assets
- Can resolve icon name → file path using Unity's asset system
- Natural fit with existing listener pattern
- Handles Unity-specific metadata (asset GUIDs, etc.)

**Python Side (Image Processing)**:
- PIL/Pillow is mature and handles image operations elegantly
- Easier to test and iterate on processing logic
- Consistent with existing deployment code (MediaWiki, Sheets)
- No need to bundle image processing libraries in Unity

**Alternative Rejected**: Pure Python approach using `variants/{variant}/unity/Assets/Texture2D/` would work, but Unity's AssetDatabase provides more reliable asset resolution, especially for edge cases like missing icons or name collisions.

### 2. Database Schema: Minimal Changes

No new tables needed. Existing icon name columns are sufficient:
- `Items.ItemIconName` (already exists)
- `Spells.SpellIconName` (already exists)
- `Skills.SkillIconName` (already exists)

**Rationale**: Icon names are already exported. The image files themselves live in the filesystem, not the database. Registry handles name overrides.

### 3. Image Processing Requirements

**Items**:
- Resize/pad to **150x150px**
- Maintain aspect ratio with padding (letterbox or pillarbox)
- No borders

**Spells/Skills**:
- Resize/pad to **150x150px**
- Add **2-3px border** to distinguish from items
- Border color: `#888888` (gray) or theme-appropriate

**Output Format**:
- PNG with transparency
- Compression: Use PIL's `optimize=True` for smaller file sizes

---

## Implementation Plan

### Phase 1: Unity Image Listener

**File**: `src/Assets/Editor/ExportSystem/AssetScanner/Listener/ImageListener.cs`

**Responsibilities**:
1. Load all Texture2D assets from `Resources/`
2. Match icon names from database (Items, Spells, Skills)
3. Copy matched PNG files to `variants/{variant}/images/raw/`
4. Log missing icons for debugging

**Key Methods**:
```csharp
public class ImageListener : IAssetScannerListener
{
    private readonly SQLiteConnection _db;
    private readonly string _outputDir;

    public ImageListener(SQLiteConnection db, string outputDir)
    {
        _db = db;
        _outputDir = outputDir;
    }

    public void OnScanFinished()
    {
        // 1. Query database for all icon names
        var iconNames = GetAllIconNames();

        // 2. Load all Texture2D assets
        var textures = Resources.LoadAll<Texture2D>("");

        // 3. Match and copy files
        foreach (var iconName in iconNames)
        {
            var texture = FindTextureByName(textures, iconName);
            if (texture != null)
            {
                CopyTextureToOutput(texture, iconName);
            }
            else
            {
                Debug.LogWarning($"[IMAGE] Icon not found: {iconName}");
            }
        }
    }

    private List<string> GetAllIconNames()
    {
        var names = new HashSet<string>();

        // Items
        var items = _db.Table<ItemRecord>()
            .Where(i => !string.IsNullOrEmpty(i.ItemIconName))
            .ToList();
        foreach (var item in items)
            names.Add(item.ItemIconName);

        // Spells
        var spells = _db.Table<SpellRecord>()
            .Where(s => !string.IsNullOrEmpty(s.SpellIconName))
            .ToList();
        foreach (var spell in spells)
            names.Add(spell.SpellIconName);

        // Skills
        var skills = _db.Table<SkillRecord>()
            .Where(s => !string.IsNullOrEmpty(s.SkillIconName))
            .ToList();
        foreach (var skill in skills)
            names.Add(skill.SkillIconName);

        return names.ToList();
    }

    private void CopyTextureToOutput(Texture2D texture, string iconName)
    {
        // Get asset path
        string assetPath = AssetDatabase.GetAssetPath(texture);

        // Read PNG bytes
        byte[] pngBytes = File.ReadAllBytes(assetPath);

        // Write to output directory
        Directory.CreateDirectory(_outputDir);
        string outputPath = Path.Combine(_outputDir, $"{iconName}.png");
        File.WriteAllBytes(outputPath, pngBytes);
    }
}
```

**Registration** (in `ExportBatch.cs`):
```csharp
// After other listeners
["images"] = () => {
    string imageOutputDir = Path.Combine(
        Path.GetDirectoryName(args.dbPath),
        "images", "raw"
    );
    scanner.RegisterNullListener(new ImageListener(db, imageOutputDir));
}
```

**CLI Integration**:
```bash
# Export images along with data
erenshor export --entities items,spells,skills,images
```

---

### Phase 2: Python Image Processing Service

**File**: `src/erenshor/application/services/image_processor.py`

**Responsibilities**:
1. Process raw images (resize, pad, border)
2. Handle name conflicts and sanitization
3. Save processed images to output directory

**Implementation**:
```python
"""Image processing service for entity icons."""

from __future__ import annotations

import hashlib
import logging
from pathlib import Path
from typing import Literal

from PIL import Image, ImageDraw, ImageOps

logger = logging.getLogger(__name__)

__all__ = ["ImageProcessor", "ImageType"]

ImageType = Literal["item", "spell", "skill"]


class ImageProcessor:
    """Process game icon images for wiki deployment.

    Features:
    - Resize to standard dimensions (150x150)
    - Maintain aspect ratio with padding
    - Add borders for ability icons (spells/skills)
    - Handle name conflicts
    """

    def __init__(
        self,
        target_size: tuple[int, int] = (150, 150),
        border_width: int = 2,
        border_color: str = "#888888",
    ):
        """Initialize image processor.

        Args:
            target_size: Target dimensions (width, height)
            border_width: Border width for spell/skill icons
            border_color: Border color (hex string)
        """
        self.target_size = target_size
        self.border_width = border_width
        self.border_color = border_color

    def process_image(
        self,
        input_path: Path,
        output_path: Path,
        image_type: ImageType,
    ) -> None:
        """Process a single image.

        Args:
            input_path: Source PNG file
            output_path: Destination PNG file
            image_type: Type of image (item, spell, skill)

        Raises:
            FileNotFoundError: If input file doesn't exist
            ValueError: If image cannot be processed
        """
        if not input_path.exists():
            raise FileNotFoundError(f"Input image not found: {input_path}")

        try:
            # Load image
            img = Image.open(input_path)

            # Convert to RGBA for transparency support
            if img.mode != "RGBA":
                img = img.convert("RGBA")

            # Resize with aspect ratio maintained
            img = self._resize_with_padding(img)

            # Add border for abilities
            if image_type in ("spell", "skill"):
                img = self._add_border(img)

            # Save processed image
            output_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(output_path, "PNG", optimize=True)

            logger.debug(f"Processed {image_type} icon: {output_path.name}")

        except Exception as e:
            raise ValueError(f"Failed to process image {input_path.name}: {e}") from e

    def _resize_with_padding(self, img: Image.Image) -> Image.Image:
        """Resize image to target size, maintaining aspect ratio with padding.

        Args:
            img: Source image

        Returns:
            Resized image with padding
        """
        # Calculate scaling to fit within target size
        img.thumbnail(self.target_size, Image.Resampling.LANCZOS)

        # Create new image with transparent background
        new_img = Image.new("RGBA", self.target_size, (0, 0, 0, 0))

        # Center the resized image
        paste_x = (self.target_size[0] - img.width) // 2
        paste_y = (self.target_size[1] - img.height) // 2
        new_img.paste(img, (paste_x, paste_y), img)

        return new_img

    def _add_border(self, img: Image.Image) -> Image.Image:
        """Add border around image.

        Args:
            img: Source image

        Returns:
            Image with border
        """
        # Create border using ImageOps
        return ImageOps.expand(
            img,
            border=self.border_width,
            fill=self.border_color,
        )

    def sanitize_filename(self, name: str) -> str:
        """Sanitize filename for filesystem and wiki compatibility.

        Args:
            name: Raw filename

        Returns:
            Sanitized filename
        """
        # Replace unsafe characters
        safe_name = name.replace(" ", "_")
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-.")
        return safe_name

    def handle_name_conflict(
        self,
        base_name: str,
        existing_names: set[str],
    ) -> str:
        """Resolve filename conflicts by appending hash suffix.

        Args:
            base_name: Base filename (without extension)
            existing_names: Set of already-used filenames

        Returns:
            Unique filename
        """
        if base_name not in existing_names:
            return base_name

        # Append short hash to make unique
        name_hash = hashlib.md5(base_name.encode()).hexdigest()[:8]
        return f"{base_name}_{name_hash}"
```

---

### Phase 3: Python Image Export Command

**File**: `src/erenshor/cli/commands/images.py`

**CLI Interface**:
```python
"""Image export commands."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import typer
from rich.console import Console
from rich.progress import track

from erenshor.application.services.image_processor import ImageProcessor
from erenshor.infrastructure.config.settings import load_settings
from erenshor.infrastructure.database import get_db_connection

app = typer.Typer()


@app.command("export")
def export_images(
    variant: str = typer.Option("main", help="Variant to export images from"),
    entity_type: list[str] = typer.Option(
        ["items", "spells", "skills"],
        help="Entity types to process (items, spells, skills)",
    ),
    force: bool = typer.Option(False, "--force", help="Reprocess all images"),
) -> None:
    """Export and process entity icon images.

    Reads raw PNG files from variants/{variant}/images/raw/ and processes them
    into variants/{variant}/images/processed/.

    Examples:
        # Process all images for main variant
        python -m erenshor.cli.main images export

        # Process only item images
        python -m erenshor.cli.main images export --entity-type items

        # Reprocess all images (ignore cache)
        python -m erenshor.cli.main images export --force
    """
    config = load_settings()
    console = Console()

    # Get variant paths
    variant_config = config.variants.get(variant)
    if not variant_config:
        console.print(f"[red]Error: Unknown variant '{variant}'[/red]")
        raise typer.Exit(1)

    # Setup paths
    raw_dir = variant_config.get("images_raw") or Path(f"variants/{variant}/images/raw")
    processed_dir = variant_config.get("images_processed") or Path(f"variants/{variant}/images/processed")
    db_path = Path(variant_config["database"])

    if not raw_dir.exists():
        console.print(f"[yellow]No raw images found at {raw_dir}[/yellow]")
        console.print("Run 'erenshor export --entities images' first")
        raise typer.Exit(1)

    # Initialize processor
    processor = ImageProcessor()

    # Connect to database to get icon names
    db = get_db_connection(db_path)

    # Collect images to process
    images_to_process = []

    if "items" in entity_type:
        items = db.execute("SELECT DISTINCT ItemIconName FROM Items WHERE ItemIconName IS NOT NULL").fetchall()
        for (icon_name,) in items:
            images_to_process.append((icon_name, "item"))

    if "spells" in entity_type:
        spells = db.execute("SELECT DISTINCT SpellIconName FROM Spells WHERE SpellIconName IS NOT NULL").fetchall()
        for (icon_name,) in spells:
            images_to_process.append((icon_name, "spell"))

    if "skills" in entity_type:
        skills = db.execute("SELECT DISTINCT SkillIconName FROM Skills WHERE SkillIconName IS NOT NULL").fetchall()
        for (icon_name,) in skills:
            images_to_process.append((icon_name, "skill"))

    console.print(f"Found {len(images_to_process)} images to process")

    # Process images
    processed_count = 0
    skipped_count = 0
    failed_count = 0

    for icon_name, image_type in track(images_to_process, description="Processing images"):
        raw_path = raw_dir / f"{icon_name}.png"
        processed_path = processed_dir / f"{icon_name}.png"

        # Skip if already processed (unless force)
        if not force and processed_path.exists():
            skipped_count += 1
            continue

        # Process image
        try:
            processor.process_image(raw_path, processed_path, image_type)
            processed_count += 1
        except Exception as e:
            console.print(f"[red]Failed to process {icon_name}: {e}[/red]")
            failed_count += 1

    # Summary
    console.print()
    console.print(f"[green]Processed: {processed_count}[/green]")
    console.print(f"[yellow]Skipped: {skipped_count}[/yellow]")
    if failed_count > 0:
        console.print(f"[red]Failed: {failed_count}[/red]")
```

---

### Phase 4: MediaWiki Image Upload

**File**: `src/erenshor/infrastructure/wiki/image_uploader.py`

**Implementation**:
```python
"""MediaWiki image upload via Special:Upload API."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import httpx

from erenshor.domain.exceptions import WikiAPIError

logger = logging.getLogger(__name__)

__all__ = ["ImageUploader"]


class ImageUploader:
    """Upload images to MediaWiki via Special:Upload API."""

    def __init__(self, api_url: str, auth_session: httpx.Client):
        """Initialize uploader.

        Args:
            api_url: MediaWiki API URL
            auth_session: Authenticated httpx.Client
        """
        self.api_url = api_url
        self.session = auth_session

    def upload_image(
        self,
        file_path: Path,
        filename: str,
        comment: str = "Automated icon upload",
        text: str = "",
        ignore_warnings: bool = False,
    ) -> dict[str, object]:
        """Upload an image file to the wiki.

        Args:
            file_path: Path to image file
            filename: Target filename on wiki (e.g., "Sword_of_Flame.png")
            comment: Upload comment/edit summary
            text: Wiki text for the file description page
            ignore_warnings: Ignore API warnings (e.g., duplicate files)

        Returns:
            API response dict

        Raises:
            WikiAPIError: If upload fails
        """
        if not file_path.exists():
            raise FileNotFoundError(f"Image file not found: {file_path}")

        # Get CSRF token
        token_response = self.session.get(
            self.api_url,
            params={"action": "query", "meta": "tokens", "format": "json"},
        )
        token_response.raise_for_status()
        csrf_token = token_response.json()["query"]["tokens"]["csrftoken"]

        # Upload file
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "image/png")}
            data = {
                "action": "upload",
                "filename": filename,
                "comment": comment,
                "text": text,
                "token": csrf_token,
                "format": "json",
            }

            if ignore_warnings:
                data["ignorewarnings"] = "1"

            response = self.session.post(
                self.api_url,
                data=data,
                files=files,
                timeout=60.0,
            )
            response.raise_for_status()
            result = response.json()

        # Check result
        if "error" in result:
            error_info = result["error"]
            raise WikiAPIError(
                f"Upload failed: {error_info.get('code')}: {error_info.get('info')}"
            )

        if "upload" in result and result["upload"].get("result") == "Success":
            logger.info(f"Uploaded image: {filename}")
            return result["upload"]

        # Handle warnings
        if "upload" in result and "warnings" in result["upload"]:
            warnings = result["upload"]["warnings"]
            logger.warning(f"Upload warnings for {filename}: {warnings}")
            if not ignore_warnings:
                raise WikiAPIError(f"Upload warnings: {warnings}")

        raise WikiAPIError(f"Unexpected upload response: {result}")
```

**CLI Command** (`src/erenshor/cli/commands/images.py`):
```python
@app.command("upload")
def upload_images(
    variant: str = typer.Option("main", help="Variant to upload images from"),
    entity_type: list[str] = typer.Option(
        ["items", "spells", "skills"],
        help="Entity types to upload",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview without uploading"),
    batch_size: int = typer.Option(50, help="Max images per batch"),
) -> None:
    """Upload processed images to MediaWiki.

    Examples:
        # Dry-run upload for items
        python -m erenshor.cli.main images upload --entity-type items --dry-run

        # Upload all images
        python -m erenshor.cli.main images upload
    """
    # Implementation: Use ImageUploader + registry image names
    pass
```

---

### Phase 5: Google Sheets Integration

**Strategy**: Embed images using `IMAGE()` formula with wiki URLs.

**Why not upload to Google Drive?**
- Google Sheets can reference external image URLs
- MediaWiki provides stable image URLs: `https://erenshor.wiki.gg/wiki/File:{filename}`
- No need for Google Drive API integration
- Simpler deployment: one image storage location (wiki)

**Implementation** (modify existing formatters):
```python
# In src/erenshor/application/formatters/sheets/items.py
def format_item_row(item: DbItem, registry: WikiRegistry) -> list[object]:
    """Format item row with image URL."""
    # Get image name from registry (handles overrides)
    entity = EntityRef(
        entity_type=EntityType.ITEM,
        db_id=item.Id,
        db_name=item.ItemName,
        resource_name=item.ResourceName,
    )
    image_name = registry.get_image_name(entity)

    # Construct wiki image URL
    if image_name:
        image_url = f"https://erenshor.wiki.gg/wiki/File:{image_name}.png"
        image_formula = f'=IMAGE("{image_url}", 1)'  # Mode 1 = fit to cell
    else:
        image_formula = ""

    return [
        item.ItemName,
        image_formula,  # Image column
        item.ItemLevel,
        # ... other columns
    ]
```

---

## Directory Structure

```
variants/{variant}/
├── images/
│   ├── raw/                    # Unity export output
│   │   ├── 1_Leather_Shoulder.png
│   │   ├── SwordBasic01.png
│   │   └── ...
│   └── processed/              # Python processed output
│       ├── 1_Leather_Shoulder.png
│       ├── SwordBasic01.png
│       └── ...
├── game/                       # Steam download
├── unity/                      # Unity project
│   └── Assets/
│       └── Texture2D/          # AssetRipper extracted textures
│           ├── 1_Leather_Shoulder.png
│           └── ...
├── logs/                       # Logs
└── erenshor-{variant}.sqlite   # Database
```

---

## CLI Commands

### Bash CLI (Unity operations)
```bash
# Export data + images
erenshor export --entities items,spells,skills,images

# Export only images
erenshor export --entities images
```

### Python CLI (Processing & deployment)
```bash
# Process images
python -m erenshor.cli.main images export --variant main

# Upload to MediaWiki
python -m erenshor.cli.main images upload --variant main --dry-run

# Deploy to Google Sheets (with image URLs)
python -m erenshor.cli.main sheets deploy --sheet items
```

---

## Edge Cases & Considerations

### 1. Missing Icons
- **Unity**: Log warning if icon name in database but texture not found
- **Python**: Skip processing if raw image doesn't exist
- **Wiki**: Template should handle missing images gracefully (show placeholder or text)

### 2. Name Conflicts
- **Same icon used by multiple entities**: Registry overrides handle this
- **Different icons with same name**: Append hash suffix to make unique
- **Special characters in names**: Sanitize for filesystem and MediaWiki

### 3. Multi-Variant Support
- Each variant has separate `images/` directory
- Processed images stay variant-specific
- Wiki uploads can be shared (same image for main/playtest)

### 4. Large Image Batches
- Process in batches to avoid memory issues
- Upload with rate limiting (respect wiki API limits)
- Show progress bars for user feedback

### 5. Image Updates
- **Force flag**: Reprocess all images
- **Incremental**: Only process new/changed images (check file mtime)
- **Wiki**: Re-upload replaces existing file (creates new version)

---

## Testing Strategy

### Unit Tests
```python
# test_image_processor.py
def test_resize_with_padding():
    """Test image resizing maintains aspect ratio."""
    processor = ImageProcessor(target_size=(150, 150))
    # Create 200x100 test image
    # Process and verify output is 150x150 with padding

def test_add_border():
    """Test border is added for spell/skill icons."""
    processor = ImageProcessor(border_width=2)
    # Process spell icon and verify border exists

def test_sanitize_filename():
    """Test filename sanitization."""
    processor = ImageProcessor()
    assert processor.sanitize_filename("Sword of Flame") == "Sword_of_Flame"
```

### Integration Tests
```bash
# Test Unity export
erenshor export --entities images --variant main

# Verify raw images exist
ls variants/main/images/raw/*.png

# Test Python processing
python -m erenshor.cli.main images export --variant main

# Verify processed images
ls variants/main/images/processed/*.png
```

---

## Migration & Rollout Plan

### Phase 1: Foundation (Week 1)
- [ ] Implement `ImageListener.cs`
- [ ] Register listener in `ExportBatch.cs`
- [ ] Test Unity export: `erenshor export --entities images`

### Phase 2: Processing (Week 2)
- [ ] Implement `ImageProcessor` service
- [ ] Implement `images export` CLI command
- [ ] Add unit tests for image processing

### Phase 3: Wiki Upload (Week 3)
- [ ] Implement `ImageUploader`
- [ ] Implement `images upload` CLI command
- [ ] Test dry-run and real uploads

### Phase 4: Google Sheets (Week 4)
- [ ] Update sheet formatters to include image URLs
- [ ] Test IMAGE() formulas in Google Sheets
- [ ] Update documentation

### Phase 5: Documentation & Polish (Week 5)
- [ ] Update CLAUDE.md with image workflow
- [ ] Add examples to README
- [ ] Create troubleshooting guide

---

## Configuration Changes

Add to `config.toml`:
```toml
[global.images]
# Image processing settings
target_size = [150, 150]
border_width = 2
border_color = "#888888"

[variants.main]
# ... existing config ...
images_raw = "$REPO_ROOT/variants/main/images/raw"
images_processed = "$REPO_ROOT/variants/main/images/processed"

[variants.main.mediawiki]
# Image upload settings
image_upload_comment = "Automated icon upload"
image_batch_size = 50
```

---

## Performance Considerations

### Unity Export
- **Bottleneck**: File I/O for copying PNGs
- **Optimization**: Parallel file copies (if needed)
- **Estimate**: ~1000 images = ~10-30 seconds

### Python Processing
- **Bottleneck**: PIL image operations
- **Optimization**: Process in batches, multiprocessing for large sets
- **Estimate**: ~1000 images = ~2-5 minutes (single-threaded)

### MediaWiki Upload
- **Bottleneck**: API rate limits, network I/O
- **Optimization**: Batch uploads with delays, retry logic
- **Estimate**: ~1000 images = ~30-60 minutes (with rate limiting)

---

## Alternative Approaches Considered

### 1. Pure Python Approach
**Rejected**: Would need to reimplement Unity's asset resolution logic. Unity's `AssetDatabase` is more reliable.

### 2. Unity-only (Process + Copy)
**Rejected**: Adds complexity to Unity Editor scripts. Python is better suited for image processing.

### 3. Store Images in SQLite (BLOB)
**Rejected**: Database bloat, harder to manage/deploy. Filesystem is simpler and more flexible.

### 4. Direct Google Drive Upload
**Rejected**: Extra API integration complexity. MediaWiki hosting + IMAGE() URLs is simpler.

---

## Future Enhancements

1. **Lazy Processing**: Only process images when deploying (save time during export)
2. **Image Variants**: Generate multiple sizes (thumbnail, full-size) for different uses
3. **Sprite Sheets**: Combine small icons into sprite sheets for wiki templates
4. **Caching**: Hash-based caching to avoid reprocessing unchanged images
5. **Compression**: Optimize PNG compression for wiki bandwidth

---

## Summary

This design provides a **clean, testable, and maintainable** solution for image extraction that:
- Follows existing architectural patterns (Unity export → Python processing → Deployment)
- Minimizes database changes (no new tables needed)
- Integrates seamlessly with current CLI commands
- Supports both MediaWiki and Google Sheets deployment
- Handles edge cases (missing icons, name conflicts, multi-variant)
- Provides clear CLI interfaces for all operations

**Next Steps**: Review this design, then implement Phase 1 (Unity ImageListener) to validate the approach.

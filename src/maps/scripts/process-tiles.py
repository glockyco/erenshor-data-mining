#!/usr/bin/env python3
"""
Tile processing script for Erenshor maps.
1. Converts JPG tiles to WebP
2. Generates negative zoom levels until single tile per zone
"""

import math
import shutil
from pathlib import Path
from PIL import Image

TILE_SIZE = 256
TILES_DIR = Path("static/tiles")
WEBP_QUALITY = 85

# Zone configurations extracted from maps.ts
ZONES = {
    "Abyssal": {"baseTilesX": 3, "baseTilesY": 3},
    "Azure": {"baseTilesX": 2, "baseTilesY": 3},
    "Azynthi": {"baseTilesX": 3, "baseTilesY": 3},
    "AzynthiClear": {"baseTilesX": 3, "baseTilesY": 3},
    "Blight": {"baseTilesX": 4, "baseTilesY": 4},
    "BloomingSepulcher": {"baseTilesX": 4, "baseTilesY": 4},
    "Bonepits": {"baseTilesX": 2, "baseTilesY": 2},
    "Brake": {"baseTilesX": 2, "baseTilesY": 2},
    "Braxonia": {"baseTilesX": 3, "baseTilesY": 3},
    "Braxonian": {"baseTilesX": 5, "baseTilesY": 6},
    "Duskenlight": {"baseTilesX": 7, "baseTilesY": 4},
    "DuskenPortal": {"baseTilesX": 3, "baseTilesY": 2},
    "Elderstone": {"baseTilesX": 7, "baseTilesY": 10},
    "FernallaField": {"baseTilesX": 6, "baseTilesY": 6},
    "FernallaPortal": {"baseTilesX": 2, "baseTilesY": 3},
    "Hidden": {"baseTilesX": 2, "baseTilesY": 2},
    "Jaws": {"baseTilesX": 3, "baseTilesY": 2},
    "Krakengard": {"baseTilesX": 2, "baseTilesY": 2},
    "Loomingwood": {"baseTilesX": 4, "baseTilesY": 4},
    "Malaroth": {"baseTilesX": 5, "baseTilesY": 4},
    "PrielPlateau": {"baseTilesX": 3, "baseTilesY": 3},
    "Ripper": {"baseTilesX": 4, "baseTilesY": 3},
    "RipperPortal": {"baseTilesX": 4, "baseTilesY": 4},
    "Rockshade": {"baseTilesX": 4, "baseTilesY": 4},
    "Rottenfoot": {"baseTilesX": 4, "baseTilesY": 4},
    "SaltedStrand": {"baseTilesX": 4, "baseTilesY": 3},
    "Silkengrass": {"baseTilesX": 5, "baseTilesY": 6},
    "Soluna": {"baseTilesX": 4, "baseTilesY": 4},
    "Stowaway": {"baseTilesX": 3, "baseTilesY": 2},
    "ShiveringStep": {"baseTilesX": 3, "baseTilesY": 2},
    "SummerEvent": {"baseTilesX": 1, "baseTilesY": 2},
    "Tutorial": {"baseTilesX": 2, "baseTilesY": 2},
    "Undercity": {"baseTilesX": 2, "baseTilesY": 2},
    "Underspine": {"baseTilesX": 3, "baseTilesY": 3},
    "Vitheo": {"baseTilesX": 2, "baseTilesY": 2},
    "VitheosEnd": {"baseTilesX": 2, "baseTilesY": 2},
    "Windwashed": {"baseTilesX": 4, "baseTilesY": 4},
    "Willowwatch": {"baseTilesX": 4, "baseTilesY": 4},
}


def calculate_min_zoom(base_tiles_x: int, base_tiles_y: int) -> int:
    """Calculate negative minZoom needed to reach single tile."""
    max_dim = max(base_tiles_x, base_tiles_y)
    if max_dim <= 1:
        return 0
    return -math.ceil(math.log2(max_dim))


def convert_jpg_to_webp(zone_dir: Path) -> int:
    """Convert all JPG tiles to WebP in place. Returns count of converted tiles."""
    count = 0
    for jpg_file in zone_dir.rglob("*.jpg"):
        try:
            img = Image.open(jpg_file)
            webp_path = jpg_file.with_suffix(".webp")
            img.save(webp_path, "WEBP", quality=WEBP_QUALITY)
            jpg_file.unlink()
            count += 1
        except Exception as e:
            print(f"  Error converting {jpg_file}: {e}")
    return count


def generate_negative_zoom_level(
    zone_dir: Path,
    source_zoom: int,
    target_zoom: int,
    source_tiles_x: int,
    source_tiles_y: int,
) -> tuple[int, int]:
    """
    Generate a negative zoom level by combining 2x2 tiles from source zoom.
    Returns the number of tiles in the new zoom level (tiles_x, tiles_y).
    """
    source_dir = zone_dir / str(source_zoom)
    target_dir = zone_dir / str(target_zoom)
    target_dir.mkdir(exist_ok=True)

    # Calculate output tile grid (half the source, rounded up)
    out_tiles_x = math.ceil(source_tiles_x / 2)
    out_tiles_y = math.ceil(source_tiles_y / 2)

    for out_x in range(out_tiles_x):
        out_x_dir = target_dir / str(out_x)
        out_x_dir.mkdir(exist_ok=True)

        for out_y in range(out_tiles_y):
            # Create 256x256 canvas (transparent for padding)
            canvas = Image.new("RGBA", (TILE_SIZE, TILE_SIZE), (0, 0, 0, 0))

            # Combine 2x2 tiles from source
            # Y indices are negative: -1, -2, -3, etc.
            # More negative Y = lower in world space = bottom of image
            # out_y=0 -> source y=-1,-2; out_y=1 -> source y=-3,-4
            for dx in range(2):
                for dy in range(2):
                    in_x = out_x * 2 + dx
                    # Calculate source Y index (negative)
                    # dy=0: get the higher Y (less negative, top in world)
                    # dy=1: get the lower Y (more negative, bottom in world)
                    in_y = -(out_y * 2 + dy + 1)

                    # Try WebP first, then JPG
                    tile_path = source_dir / str(in_x) / f"{in_y}.webp"
                    if not tile_path.exists():
                        tile_path = source_dir / str(in_x) / f"{in_y}.jpg"

                    if tile_path.exists():
                        try:
                            tile = Image.open(tile_path).convert("RGBA")
                            # Scale down to 128x128
                            tile = tile.resize((128, 128), Image.LANCZOS)
                            # Place in canvas - FLIP Y placement
                            # dy=0 (higher world Y, y=-1) -> bottom of image (128)
                            # dy=1 (lower world Y, y=-2) -> top of image (0)
                            canvas_y = (1 - dy) * 128
                            canvas.paste(tile, (dx * 128, canvas_y))
                        except Exception as e:
                            print(f"  Error loading {tile_path}: {e}")

            # Save with negative Y index
            out_y_index = -(out_y + 1)
            out_path = out_x_dir / f"{out_y_index}.webp"
            canvas.save(out_path, "WEBP", quality=WEBP_QUALITY)

    return out_tiles_x, out_tiles_y


def process_zone(zone_name: str, config: dict) -> dict:
    """Process a single zone. Returns stats."""
    zone_dir = TILES_DIR / zone_name
    if not zone_dir.exists():
        print(f"  Zone directory not found: {zone_dir}")
        return {"skipped": True}

    stats = {
        "converted": 0,
        "negative_levels": 0,
        "min_zoom": 0,
    }

    # Step 1: Convert existing JPG tiles to WebP
    stats["converted"] = convert_jpg_to_webp(zone_dir)

    # Step 2: Calculate how many negative zoom levels needed
    base_x, base_y = config["baseTilesX"], config["baseTilesY"]
    min_zoom = calculate_min_zoom(base_x, base_y)
    stats["min_zoom"] = min_zoom

    if min_zoom >= 0:
        # Already at single tile, no negative zooms needed
        return stats

    # Step 3: Generate negative zoom levels
    current_x, current_y = base_x, base_y
    for target_zoom in range(-1, min_zoom - 1, -1):
        source_zoom = target_zoom + 1
        current_x, current_y = generate_negative_zoom_level(
            zone_dir, source_zoom, target_zoom, current_x, current_y
        )
        stats["negative_levels"] += 1

    return stats


def main():
    print("Tile Processing Script")
    print("=" * 50)

    # Verify backup exists
    backup_dir = TILES_DIR.parent / "tiles-backup"
    if not backup_dir.exists():
        print("ERROR: Backup directory not found at static/tiles-backup/")
        print("Please run: cp -r static/tiles static/tiles-backup")
        return

    print(f"Processing {len(ZONES)} zones...")
    print()

    total_converted = 0
    min_zoom_summary = {}

    for zone_name, config in sorted(ZONES.items()):
        print(f"Processing {zone_name}...")
        stats = process_zone(zone_name, config)

        if stats.get("skipped"):
            continue

        total_converted += stats["converted"]
        min_zoom_summary[zone_name] = stats["min_zoom"]

        print(
            f"  Converted: {stats['converted']} tiles, "
            f"Negative levels: {stats['negative_levels']}, "
            f"minZoom: {stats['min_zoom']}"
        )

    print()
    print("=" * 50)
    print(f"Total tiles converted to WebP: {total_converted}")
    print()
    print("minZoom values for maps.ts:")
    print("-" * 30)
    for zone, min_zoom in sorted(min_zoom_summary.items()):
        print(f"  {zone}: {min_zoom}")


if __name__ == "__main__":
    main()

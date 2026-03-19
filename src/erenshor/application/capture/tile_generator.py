from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image

TILE_SIZE = 256
WEBP_QUALITY = 85


def generate_tile_pyramid(
    master_path: Path,
    zone_key: str,
    variant: str,
    config: dict[str, Any],
    out_dir: Path,
) -> int:
    """Slice a master image into a Leaflet-style tile pyramid.

    Returns the total number of tiles written.

    Directory layout: ``out_dir / zone_key / variant / z / tx / tile_y_idx.webp``
    """
    max_zoom: int = config["maxZoom"]
    base_x: int = config["baseTilesX"]
    base_y: int = config["baseTilesY"]

    # min_zoom: the most zoomed-out level where everything fits in one tile
    if max(base_x, base_y) > 1:
        min_zoom = -math.ceil(math.log2(max(base_x, base_y)))
    else:
        min_zoom = 0

    img = Image.open(master_path)
    total = 0

    for z in range(max_zoom, min_zoom - 1, -1):
        scale = 2**z
        num_x = max(1, round(base_x * scale))
        num_y = max(1, round(base_y * scale))

        target_w = num_x * TILE_SIZE
        target_h = num_y * TILE_SIZE

        # Never upscale
        if target_w > img.width or target_h > img.height:
            continue

        scaled = img.resize((target_w, target_h), Image.LANCZOS)

        for tx in range(num_x):
            for ty in range(num_y):
                tile_y_idx = -(ty + 1)
                box = (
                    tx * TILE_SIZE,
                    ty * TILE_SIZE,
                    (tx + 1) * TILE_SIZE,
                    (ty + 1) * TILE_SIZE,
                )
                tile = scaled.crop(box)

                tile_dir = out_dir / zone_key / variant / str(z) / str(tx)
                tile_dir.mkdir(parents=True, exist_ok=True)
                tile_path = tile_dir / f"{tile_y_idx}.webp"
                tile.save(tile_path, "WEBP", quality=WEBP_QUALITY)
                total += 1

    logger.info(
        f"Generated {total} tiles for {zone_key}/{variant} "
        f"(zoom {min_zoom}..{max_zoom})"
    )
    return total

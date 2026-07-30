from __future__ import annotations

import math
from typing import Any


def estimate_tile_count(config: dict[str, Any]) -> dict[str, dict[str, int]]:
    """Estimate the total tile count per zone and a grand total.

    Returns a dict keyed by zone name (plus ``"_total"``), each containing
    ``{"tiles": int}`` with the count across all zoom levels and variants.
    """
    result: dict[str, dict[str, int]] = {}
    grand_total = 0

    for zone_key, zc in config.items():
        base_x: int = zc["baseTilesX"]
        base_y: int = zc["baseTilesY"]
        max_zoom: int = zc["maxZoom"]
        variants: list[str] = zc.get("captureVariants", ["open"])

        if max(base_x, base_y) > 1:
            min_zoom = -math.ceil(math.log2(max(base_x, base_y)))
        else:
            min_zoom = 0

        tiles_per_variant = sum(base_x * base_y * (4**zoom) for zoom in range(max_zoom + 1))
        source_x = base_x
        source_y = base_y
        for _target_zoom in range(-1, min_zoom - 1, -1):
            source_x = math.ceil(source_x / 2)
            source_y = math.ceil(source_y / 2)
            tiles_per_variant += source_x * source_y

        zone_total = tiles_per_variant * len(variants)
        result[zone_key] = {"tiles": zone_total}
        grand_total += zone_total

    result["_total"] = {"tiles": grand_total}
    return result

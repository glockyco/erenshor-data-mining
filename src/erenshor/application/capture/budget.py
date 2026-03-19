from __future__ import annotations

import math
from typing import Any

TILE_SIZE = 256


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

        tiles_per_variant = 0
        for z in range(max_zoom, min_zoom - 1, -1):
            scale = 2**z
            num_x = max(1, round(base_x * scale))
            num_y = max(1, round(base_y * scale))
            tiles_per_variant += num_x * num_y

        zone_total = tiles_per_variant * len(variants)
        result[zone_key] = {"tiles": zone_total}
        grand_total += zone_total

    result["_total"] = {"tiles": grand_total}
    return result

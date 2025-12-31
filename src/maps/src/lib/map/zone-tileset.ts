/**
 * Custom Tileset2D for rotated zone tiles with OrthographicView
 *
 * deck.gl's TileLayer modelMatrix only affects tile fetching for geospatial views,
 * not OrthographicView. This custom Tileset2D handles rotation-aware viewport culling
 * by transforming viewport bounds back to local tile coordinates.
 */

import type { ZoneConfig, ZoneWorldPosition } from '../types/world-map';

// Tile index with zone context
export interface ZoneTileIndex {
    x: number;
    y: number;
    z: number;
    zoneName: string;
}

// Combined config for tile operations
interface ZoneTileConfig {
    config: ZoneConfig;
    zone: ZoneWorldPosition;
}

/**
 * Forward transformation: Local tile coords -> World map coords
 * Used for rendering (BitmapLayer bounds)
 */
export function localToWorld(
    localX: number,
    localY: number,
    { config, zone }: ZoneTileConfig
): [number, number] {
    // 1. Local tile to game coordinates
    const gameX = localX + config.originX;
    const gameZ = -localY + config.originY;

    // 2. Game to map coordinates (Y-flip + rotation)
    const flippedY = -gameZ;
    const angleRad = ((180 - config.northBearing) * Math.PI) / 180;
    const cos = Math.cos(angleRad);
    const sin = Math.sin(angleRad);

    const rotatedX = gameX * cos - flippedY * sin;
    const rotatedY = gameX * sin + flippedY * cos;

    // 3. Map to world coordinates
    return [rotatedX + zone.worldX, rotatedY + zone.worldY];
}

/**
 * Inverse transformation: World map coords -> Local tile coords
 * Used for tile fetching (viewport culling)
 */
export function worldToLocal(
    worldX: number,
    worldY: number,
    { config, zone }: ZoneTileConfig
): [number, number] {
    // 1. World to map coordinates (remove offset)
    const mapX = worldX - zone.worldX;
    const mapY = worldY - zone.worldY;

    // 2. Inverse rotation (negative angle)
    const angleRad = -((180 - config.northBearing) * Math.PI) / 180;
    const cos = Math.cos(angleRad);
    const sin = Math.sin(angleRad);

    const unrotatedX = mapX * cos - mapY * sin;
    const unrotatedY = mapX * sin + mapY * cos;

    // 3. Map to game coordinates (undo Y-flip)
    const gameX = unrotatedX;
    const gameZ = -unrotatedY;

    // 4. Game to local tile coordinates
    const localX = gameX - config.originX;
    const localY = -(gameZ - config.originY);

    return [localX, localY];
}

/**
 * Get viewport bounds from OrthographicView viewport
 */
function getViewportBounds(viewport: {
    width: number;
    height: number;
    target?: [number, number, number];
    zoom: number;
    getBounds?: () => [number, number, number, number];
}): { minX: number; maxX: number; minY: number; maxY: number } {
    // OrthographicView provides getBounds() method
    if (viewport.getBounds) {
        const [minX, minY, maxX, maxY] = viewport.getBounds();
        return { minX, minY, maxX, maxY };
    }

    // Fallback: calculate from viewport properties
    const { width, height, target, zoom } = viewport;
    const scale = Math.pow(2, zoom);
    const halfWidth = width / 2 / scale;
    const halfHeight = height / 2 / scale;
    const centerX = target?.[0] ?? 0;
    const centerY = target?.[1] ?? 0;

    return {
        minX: centerX - halfWidth,
        maxX: centerX + halfWidth,
        minY: centerY - halfHeight,
        maxY: centerY + halfHeight
    };
}

/**
 * Calculate bounding box from array of points
 */
function getBoundingBox(points: [number, number][]): {
    minX: number;
    maxX: number;
    minY: number;
    maxY: number;
} {
    const xs = points.map((p) => p[0]);
    const ys = points.map((p) => p[1]);
    return {
        minX: Math.min(...xs),
        maxX: Math.max(...xs),
        minY: Math.min(...ys),
        maxY: Math.max(...ys)
    };
}

/**
 * Factory function to create a zone-specific Tileset2D class
 */
export function createZoneTileset2D(
    config: ZoneConfig,
    zone: ZoneWorldPosition,
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    Tileset2D: any
) {
    const tileConfig: ZoneTileConfig = { config, zone };
    const tileSize = config.tileSize;

    return class ZoneTileset2D extends Tileset2D {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        getTileIndices(opts: any): ZoneTileIndex[] {
            const { viewport, maxZoom = config.maxZoom, minZoom = config.minZoom } = opts;

            // Get viewport bounds in world coordinates
            const viewBounds = getViewportBounds(viewport);

            // Transform all 4 viewport corners to local tile coordinates
            const localCorners: [number, number][] = [
                worldToLocal(viewBounds.minX, viewBounds.minY, tileConfig),
                worldToLocal(viewBounds.maxX, viewBounds.minY, tileConfig),
                worldToLocal(viewBounds.maxX, viewBounds.maxY, tileConfig),
                worldToLocal(viewBounds.minX, viewBounds.maxY, tileConfig)
            ];

            // Calculate bounding box of transformed corners
            const localBounds = getBoundingBox(localCorners);

            // Calculate zoom level from viewport
            const z = Math.max(minZoom, Math.min(maxZoom, Math.round(viewport.zoom)));

            // Calculate scale factor for current zoom
            const scale = Math.pow(2, z);

            // Tile world size at this zoom level
            const tileWorldSize = tileSize / scale;

            // Calculate tile index range in local coordinates
            const tileMinX = Math.floor(localBounds.minX / tileWorldSize);
            const tileMaxX = Math.floor(localBounds.maxX / tileWorldSize);
            const tileMinY = Math.floor(localBounds.minY / tileWorldSize);
            const tileMaxY = Math.floor(localBounds.maxY / tileWorldSize);

            // Zone extent at this zoom level
            // For negative zoom (z < 0), tiles are combined so use ceiling for non-power-of-2 grids
            // For positive zoom (z >= 0), tiles are split so use exact multiplication
            const numTilesX =
                z < 0 ? Math.ceil(config.baseTilesX * scale) : config.baseTilesX * scale;
            const numTilesY =
                z < 0 ? Math.ceil(config.baseTilesY * scale) : config.baseTilesY * scale;
            const zoneMinX = 0;
            const zoneMaxX = numTilesX - 1;
            const zoneMinY = -numTilesY;
            const zoneMaxY = -1;

            // Clamp to zone extent
            const clampedMinX = Math.max(tileMinX, zoneMinX);
            const clampedMaxX = Math.min(tileMaxX, zoneMaxX);
            const clampedMinY = Math.max(tileMinY, zoneMinY);
            const clampedMaxY = Math.min(tileMaxY, zoneMaxY);

            // Generate tile indices
            const indices: ZoneTileIndex[] = [];
            for (let x = clampedMinX; x <= clampedMaxX; x++) {
                for (let y = clampedMinY; y <= clampedMaxY; y++) {
                    indices.push({ x, y, z, zoneName: config.zoneName });
                }
            }

            return indices;
        }

        getTileId(index: ZoneTileIndex): string {
            return `${zone.key}-${index.z}-${index.x}-${index.y}`;
        }

        getTileZoom(index: ZoneTileIndex): number {
            return index.z;
        }

        getParentIndex(index: ZoneTileIndex): ZoneTileIndex | null {
            if (index.z <= config.minZoom) {
                return null;
            }
            // For negative Y indices: floor properly groups tiles
            // y=-1,-2 → parent y=-1; y=-3,-4 → parent y=-2
            return {
                x: Math.floor(index.x / 2),
                y: Math.floor(index.y / 2),
                z: index.z - 1,
                zoneName: index.zoneName
            };
        }
    };
}

/**
 * Calculate world-coordinate corners for a tile (for BitmapLayer bounds)
 *
 * BitmapLayer bounds format: [[bottomLeft], [bottomRight], [topRight], [topLeft]]
 * This maps image corners to world positions:
 * - bounds[0] = where image bottom-left corner renders
 * - bounds[1] = where image bottom-right corner renders
 * - bounds[2] = where image top-right corner renders
 * - bounds[3] = where image top-left corner renders
 */
export function getTileWorldCorners(
    index: ZoneTileIndex,
    config: ZoneConfig,
    zone: ZoneWorldPosition
): [[number, number], [number, number], [number, number], [number, number]] {
    const tileConfig: ZoneTileConfig = { config, zone };
    const scale = Math.pow(2, index.z);
    const tileWorldSize = config.tileSize / scale;

    // Calculate tile corners in local coordinates
    // Local coord system: X increases right, Y increases up (negative tile indices)
    const left = index.x * tileWorldSize;
    const right = (index.x + 1) * tileWorldSize;
    const bottom = index.y * tileWorldSize;
    const top = (index.y + 1) * tileWorldSize;

    // Transform corners to world coordinates
    const worldBL = localToWorld(left, bottom, tileConfig);
    const worldBR = localToWorld(right, bottom, tileConfig);
    const worldTR = localToWorld(right, top, tileConfig);
    const worldTL = localToWorld(left, top, tileConfig);

    // Tiles need 90° rotation + Y flip to display correctly
    // This reorders corners so:
    // - Image bottom-left → world top-left
    // - Image bottom-right → world bottom-left
    // - Image top-right → world bottom-right
    // - Image top-left → world top-right
    return [worldTL, worldBL, worldBR, worldTR];
}

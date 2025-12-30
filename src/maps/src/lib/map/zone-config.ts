import type { ZoneWorldPosition, ZoneConfig } from '../types/map';
import { MAPS } from '../maps';
import { transformToMapCoords } from './config';

/**
 * Build ZoneConfig from MapConfig + northBearing
 */
export function buildZoneConfigs(bearings: Record<string, number>): Record<string, ZoneConfig> {
    const configs: Record<string, ZoneConfig> = {};

    for (const [key, map] of Object.entries(MAPS)) {
        const bearing = bearings[key];
        if (bearing === undefined) {
            throw new Error(`Missing northBearing for zone: ${key}`);
        }
        configs[key] = {
            ...map,
            northBearing: bearing
        };
    }

    return configs;
}

/**
 * Calculate zone bounds in game coordinates (before transformation)
 */
function calculateGameBounds(config: ZoneConfig): {
    minX: number;
    minZ: number;
    maxX: number;
    maxZ: number;
} {
    const width = config.baseTilesX * config.tileSize;
    const height = config.baseTilesY * config.tileSize;

    return {
        minX: config.originX,
        minZ: config.originY,
        maxX: config.originX + width,
        maxZ: config.originY + height
    };
}

/**
 * Calculate transformed zone geometry (after Y-flip and rotation)
 * Returns both the polygon corners and axis-aligned bounding box
 */
function calculateTransformedGeometry(
    config: ZoneConfig,
    worldOffsetX: number,
    worldOffsetY: number
): {
    bounds: { minX: number; minY: number; maxX: number; maxY: number };
    polygon: [number, number][];
} {
    const game = calculateGameBounds(config);

    // Transform all 4 corners
    const corners: [number, number][] = [
        [game.minX, game.minZ],
        [game.maxX, game.minZ],
        [game.maxX, game.maxZ],
        [game.minX, game.maxZ]
    ];

    const polygon: [number, number][] = corners.map(([x, z]) => {
        const [tx, ty] = transformToMapCoords(x, z, config.northBearing, 0, 0);
        return [tx + worldOffsetX, ty + worldOffsetY];
    });

    // Find axis-aligned bounding box of transformed corners
    const xs = polygon.map(([x]) => x);
    const ys = polygon.map(([, y]) => y);

    return {
        bounds: {
            minX: Math.min(...xs),
            minY: Math.min(...ys),
            maxX: Math.max(...xs),
            maxY: Math.max(...ys)
        },
        polygon
    };
}

/**
 * Calculate centroid of a polygon
 */
function calculateCentroid(polygon: [number, number][]): [number, number] {
    const xs = polygon.map(([x]) => x);
    const ys = polygon.map(([, y]) => y);
    return [xs.reduce((a, b) => a + b, 0) / xs.length, ys.reduce((a, b) => a + b, 0) / ys.length];
}

/**
 * Helper to create zone position with geometry
 */
function createZonePosition(
    key: string,
    config: ZoneConfig,
    worldX: number,
    worldY: number
): ZoneWorldPosition {
    const { bounds, polygon } = calculateTransformedGeometry(config, worldX, worldY);
    return {
        key,
        name: config.zoneName,
        worldX,
        worldY,
        bounds,
        polygon,
        centroid: calculateCentroid(polygon)
    };
}

/**
 * Calculate zone size at origin for layout planning
 */
function getZoneSize(config: ZoneConfig): { width: number; height: number } {
    const { bounds } = calculateTransformedGeometry(config, 0, 0);
    return {
        width: bounds.maxX - bounds.minX,
        height: bounds.maxY - bounds.minY
    };
}

const ZONE_PADDING = 100;

/**
 * Build world positions using a simple row layout
 */
export function buildZoneWorldPositions(
    configs: Record<string, ZoneConfig>,
    zoneKeys?: string[]
): ZoneWorldPosition[] {
    // Use provided keys or all keys from configs
    const keys = zoneKeys ?? Object.keys(configs);
    const positions: ZoneWorldPosition[] = [];

    let currentX = 0;
    let currentY = 0;
    let maxHeightInRow = 0;
    const maxZonesPerRow = 5;

    for (let i = 0; i < keys.length; i++) {
        const key = keys[i];
        const config = configs[key];
        if (!config) {
            throw new Error(`Missing zone config for key: ${key}`);
        }

        const size = getZoneSize(config);

        // Start new row if needed
        if (i > 0 && i % maxZonesPerRow === 0) {
            currentX = 0;
            currentY -= maxHeightInRow + ZONE_PADDING;
            maxHeightInRow = 0;
        }

        // Get the geometry at origin to find the min corner offset
        const { bounds: originBounds } = calculateTransformedGeometry(config, 0, 0);

        // Offset so the zone's min corner aligns with currentX, currentY
        const offsetX = currentX - originBounds.minX;
        const offsetY = currentY - originBounds.maxY;

        positions.push(createZonePosition(key, config, offsetX, offsetY));

        // Move X for next zone
        currentX += size.width + ZONE_PADDING;
        maxHeightInRow = Math.max(maxHeightInRow, size.height);
    }

    return positions;
}

/**
 * Calculate world bounds encompassing all zones
 */
export function calculateWorldBounds(positions: ZoneWorldPosition[]): {
    minX: number;
    minY: number;
    maxX: number;
    maxY: number;
} {
    if (positions.length === 0) {
        throw new Error('Cannot calculate world bounds: no zone positions provided');
    }

    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;

    for (const zone of positions) {
        minX = Math.min(minX, zone.bounds.minX);
        minY = Math.min(minY, zone.bounds.minY);
        maxX = Math.max(maxX, zone.bounds.maxX);
        maxY = Math.max(maxY, zone.bounds.maxY);
    }

    return { minX, minY, maxX, maxY };
}

/**
 * Calculate center point of world bounds
 */
export function calculateWorldCenter(positions: ZoneWorldPosition[]): [number, number] {
    const bounds = calculateWorldBounds(positions);
    return [(bounds.minX + bounds.maxX) / 2, (bounds.minY + bounds.maxY) / 2];
}

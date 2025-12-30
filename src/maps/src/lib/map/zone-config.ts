import type { ZoneWorldPosition, ZoneConfig } from '../types/map';
import { MAPS } from '../maps';
import { transformToMapCoords } from './config';
import zonePositions from '../data/zone-positions.json';

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
export function calculateTransformedGeometry(
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
export function calculateCentroid(polygon: [number, number][]): [number, number] {
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
 * Build world positions from static position data
 */
export function buildZoneWorldPositions(
    configs: Record<string, ZoneConfig>,
    zoneKeys?: string[]
): ZoneWorldPosition[] {
    const keys = zoneKeys ?? Object.keys(configs);

    return keys.map((key) => {
        const config = configs[key];
        if (!config) {
            throw new Error(`Missing zone config: ${key}`);
        }

        const position = (zonePositions as Record<string, { worldX: number; worldY: number }>)[key];
        if (!position) {
            throw new Error(`Missing zone position: ${key}`);
        }

        return createZonePosition(key, config, position.worldX, position.worldY);
    });
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

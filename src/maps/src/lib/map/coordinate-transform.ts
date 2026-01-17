/**
 * Shared coordinate transformation utilities for both server-side (SSR)
 * and client-side (live entities) rendering.
 *
 * Game coordinates use a zone-specific north bearing that must be corrected
 * to align with the map's compass orientation (north = up).
 */

import { transformToMapCoords } from './config';
import type { ZoneConfig, ZoneWorldPosition } from '../types/world-map';

// Track which zones we've warned about to avoid console spam
const warnedZones = new Set<string>();

/**
 * Transform game coordinates to world map coordinates.
 * Works on both server (during SSR) and client (for live entities).
 *
 * @param gameX - Game X coordinate
 * @param gameZ - Game Z coordinate (forward/back in game, becomes Y on 2D map)
 * @param zoneKey - Zone identifier (matches Unity scene name)
 * @param zoneConfigs - Zone configuration map
 * @param zonePositions - Zone world position data
 * @returns World map coordinates [x, y] or null if zone not found
 */
export function transformToWorld(
    gameX: number,
    gameZ: number,
    zoneKey: string,
    zoneConfigs: Record<string, ZoneConfig>,
    zonePositions: ZoneWorldPosition[]
): [number, number] | null {
    const zonePos = zonePositions.find((z) => z.key === zoneKey);
    const zoneConfig = zoneConfigs[zoneKey];

    // Return null instead of throwing - gracefully handle unmapped zones
    if (!zonePos || !zoneConfig) {
        // Warn once per zone to avoid console spam
        if (!warnedZones.has(zoneKey)) {
            console.warn(`Zone not found for transformation: ${zoneKey}`);
            warnedZones.add(zoneKey);
        }
        return null;
    }

    // Validate coordinates
    if (!Number.isFinite(gameX) || !Number.isFinite(gameZ)) {
        console.warn(`Invalid coordinates: gameX=${gameX}, gameZ=${gameZ}`);
        return null;
    }

    const [mapX, mapY] = transformToMapCoords(gameX, gameZ, zoneConfig.northBearing, 0, 0);

    return [mapX + zonePos.worldX, mapY + zonePos.worldY];
}

/**
 * Transform entity position (from InteractiveMapCompanion) to world coordinates.
 * Handles debug zone overrides for consistency with static markers.
 *
 * @param entity - Entity with position and zone
 * @param zones - Zone world positions
 * @param zoneConfigs - Zone configurations
 * @param overrides - Debug zone position overrides (optional)
 * @returns World map coordinates [x, y] or null if transformation fails
 */
export function transformEntityToWorld(
    entity: { position: [number, number, number]; zone: string },
    zones: ZoneWorldPosition[],
    zoneConfigs: Record<string, ZoneConfig>,
    overrides: Record<string, { worldX: number; worldY: number }> = {}
): [number, number] | null {
    // entity.position is [x, y, z] where y is vertical (ignored for 2D map)
    const [gameX, , gameZ] = entity.position;

    const worldPos = transformToWorld(gameX, gameZ, entity.zone, zoneConfigs, zones);
    if (!worldPos) return null;

    // Apply debug zone overrides (if any)
    const override = overrides[entity.zone];
    if (!override) return worldPos;

    const originalZone = zones.find((z) => z.key === entity.zone);
    if (!originalZone) return worldPos;

    const deltaX = override.worldX - originalZone.worldX;
    const deltaY = override.worldY - originalZone.worldY;

    return [worldPos[0] + deltaX, worldPos[1] + deltaY];
}

/**
 * Transform entity rotation from game coordinates to map coordinates.
 * Applies the same bearing adjustment used for position coordinates.
 *
 * Game rotation is in degrees where 0° = north in game space. Each zone has
 * a northBearing that indicates where true north is in game coordinates. We
 * apply the same rotation transformation (180 - northBearing) to align the
 * rotation with the map's compass orientation.
 *
 * @param gameRotation - Entity rotation in degrees (0-360, where 0 = north in game)
 * @param zoneKey - Zone identifier
 * @param zoneConfigs - Zone configuration map
 * @returns Rotation angle for deck.gl icon or null if zone not found
 */
export function transformRotationToMap(
    gameRotation: number,
    zoneKey: string,
    zoneConfigs: Record<string, ZoneConfig>
): number | null {
    const zoneConfig = zoneConfigs[zoneKey];

    if (!zoneConfig) {
        // Warn once per zone to avoid console spam
        if (!warnedZones.has(zoneKey)) {
            console.warn(`Zone not found for rotation transformation: ${zoneKey}`);
            warnedZones.add(zoneKey);
        }
        return null;
    }

    if (!Number.isFinite(gameRotation)) {
        console.warn(`Invalid rotation: ${gameRotation}`);
        return null;
    }

    // Apply same rotation transformation as coordinates
    // angle = -(gameRotation + (180 - northBearing))
    const bearingAdjustment = 180 - zoneConfig.northBearing;
    return -(gameRotation + bearingAdjustment);
}

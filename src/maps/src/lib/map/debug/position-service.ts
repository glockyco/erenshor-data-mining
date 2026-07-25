import type { ZoneWorldPosition, ZoneConfig } from '../../types/world-map';
import { calculateTransformedGeometry, calculateCentroid } from '../zone-config';
import type { PositionOverrides } from './persistence';

/**
 * Stateless position calculation utilities.
 * All methods take zones/configs as parameters to avoid capturing stale references.
 */
export function getEffectiveZones(
    zones: ZoneWorldPosition[],
    configs: Record<string, ZoneConfig>,
    overrides: PositionOverrides
): ZoneWorldPosition[] {
    if (Object.keys(overrides).length === 0) {
        return zones;
    }

    return zones.map((zone) => {
        const override = overrides[zone.key];
        if (!override) return zone;
        return applyZoneOverride(zone, configs[zone.key], override);
    });
}

export function adjustMarkerPosition(
    worldPos: [number, number],
    zoneKey: string,
    zones: ZoneWorldPosition[],
    overrides: PositionOverrides
): [number, number] {
    const delta = getZoneDelta(zoneKey, zones, overrides);
    return [worldPos[0] + delta.x, worldPos[1] + delta.y];
}

function getZoneDelta(
    zoneKey: string,
    zones: ZoneWorldPosition[],
    overrides: PositionOverrides
): { x: number; y: number } {
    const override = overrides[zoneKey];
    if (!override) {
        return { x: 0, y: 0 };
    }

    const originalZone = zones.find((z) => z.key === zoneKey);
    if (!originalZone) {
        return { x: 0, y: 0 };
    }

    return {
        x: override.worldX - originalZone.worldX,
        y: override.worldY - originalZone.worldY
    };
}

function applyZoneOverride(
    zone: ZoneWorldPosition,
    config: ZoneConfig,
    override: { worldX: number; worldY: number }
): ZoneWorldPosition {
    if (!config) {
        throw new Error(`Missing zone config: ${zone.key}`);
    }

    const { bounds, polygon } = calculateTransformedGeometry(
        config,
        override.worldX,
        override.worldY
    );

    return {
        ...zone,
        worldX: override.worldX,
        worldY: override.worldY,
        bounds,
        polygon,
        centroid: calculateCentroid(polygon)
    };
}

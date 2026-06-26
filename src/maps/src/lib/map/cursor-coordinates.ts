import type { ZoneConfig, ZoneWorldPosition } from '$lib/types/world-map';
import { worldToGameCoordinates } from './coordinate-transform';

export type CursorCoordinates = {
    zoneKey?: string;
    zoneName: string;
    x: number;
    z: number;
};

type ZoneMapCoordinateConfig = Pick<ZoneConfig, 'originX' | 'originY' | 'zoneName'>;

export function formatCursorCoordinates({ zoneName, x, z }: CursorCoordinates): string {
    return `${zoneName} · X ${Math.round(x).toLocaleString('en-US')} · Z ${Math.round(z).toLocaleString('en-US')}`;
}

export function getZoneMapCursorCoordinates(
    latLng: { lat: number; lng: number },
    config: ZoneMapCoordinateConfig
): CursorCoordinates | null {
    const x = latLng.lng + config.originX;
    const z = latLng.lat + config.originY;
    if (!Number.isFinite(x) || !Number.isFinite(z)) return null;

    return {
        zoneName: config.zoneName,
        x,
        z
    };
}

export function findWorldCursorCoordinates(
    point: [number, number],
    zones: ZoneWorldPosition[],
    zoneConfigs: Record<string, ZoneConfig>
): CursorCoordinates | null {
    const [worldX, worldY] = point;
    if (!Number.isFinite(worldX) || !Number.isFinite(worldY)) return null;

    for (const zone of zones) {
        if (!isWithinBounds(point, zone.bounds) || !isPointInPolygon(point, zone.polygon)) {
            continue;
        }

        const config = zoneConfigs[zone.key];
        if (!config) continue;

        const coordinates = worldToGameCoordinates([worldX, worldY], zone, config);
        if (!coordinates) return null;

        const [x, z] = coordinates;
        if (!Number.isFinite(x) || !Number.isFinite(z)) return null;

        return {
            zoneKey: zone.key,
            zoneName: zone.name,
            x,
            z
        };
    }

    return null;
}

function isWithinBounds(
    [x, y]: [number, number],
    bounds: ZoneWorldPosition['bounds']
): boolean {
    return x >= bounds.minX && x <= bounds.maxX && y >= bounds.minY && y <= bounds.maxY;
}

function isPointInPolygon([x, y]: [number, number], polygon: [number, number][]): boolean {
    if (polygon.length < 3) return false;

    let inside = false;
    for (let i = 0, j = polygon.length - 1; i < polygon.length; j = i++) {
        const [xi, yi] = polygon[i];
        const [xj, yj] = polygon[j];
        const crosses = yi > y !== yj > y;
        if (!crosses) continue;

        const intersectionX = ((xj - xi) * (y - yi)) / (yj - yi) + xi;
        if (x < intersectionX) inside = !inside;
    }

    return inside;
}

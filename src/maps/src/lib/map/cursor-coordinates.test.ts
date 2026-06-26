import { describe, expect, it } from 'vitest';
import type { ZoneConfig, ZoneWorldPosition } from '$lib/types/world-map';
import {
    findWorldCursorCoordinates,
    formatCursorCoordinates,
    getZoneMapCursorCoordinates
} from './cursor-coordinates';
import { transformToWorld, worldToGameCoordinates } from './coordinate-transform';
import { calculateCentroid, calculateTransformedGeometry } from './zone-config';

const zoneConfig: ZoneConfig = {
    zoneName: 'Test Zone',
    tileUrl: '/tiles/Test/{z}/{x}/{y}.webp',
    baseTilesX: 2,
    baseTilesY: 1,
    tileSize: 100,
    zoom: 0,
    minZoom: -1,
    maxZoom: 2,
    originX: -40,
    originY: 120,
    northBearing: 135
};

const zone: ZoneWorldPosition = {
    key: 'Test',
    name: 'Test Zone',
    worldX: 500,
    worldY: -200,
    bounds: { minX: 0, minY: 0, maxX: 0, maxY: 0 },
    polygon: [],
    centroid: [0, 0]
};

const geometry = calculateTransformedGeometry(zoneConfig, zone.worldX, zone.worldY);
zone.polygon = geometry.polygon;
zone.bounds = geometry.bounds;
zone.centroid = calculateCentroid(zone.polygon);

describe('worldToGameCoordinates', () => {
    it('inverts the same transform used to place markers on the world map', () => {
        const point = transformToWorld(35, 180, 'Test', { Test: zoneConfig }, [zone]);
        expect(point).not.toBeNull();

        const coordinates = worldToGameCoordinates(point!, zone, zoneConfig);
        expect(coordinates?.[0]).toBeCloseTo(35);
        expect(coordinates?.[1]).toBeCloseTo(180);
    });
});

describe('findWorldCursorCoordinates', () => {
    it('returns local game X/Z for a point inside a rotated world-map zone footprint', () => {
        const point = transformToWorld(35, 180, 'Test', { Test: zoneConfig }, [zone]);
        expect(point).not.toBeNull();

        const coordinates = findWorldCursorCoordinates(point!, [zone], { Test: zoneConfig });
        expect(coordinates?.zoneKey).toBe('Test');
        expect(coordinates?.zoneName).toBe('Test Zone');
        expect(coordinates?.x).toBeCloseTo(35);
        expect(coordinates?.z).toBeCloseTo(180);
    });

    it('returns null outside every world-map zone footprint', () => {
        expect(findWorldCursorCoordinates([5000, 5000], [zone], { Test: zoneConfig })).toBeNull();
    });
});

describe('getZoneMapCursorCoordinates', () => {
    it('converts Leaflet local map coordinates back to game X/Z', () => {
        expect(getZoneMapCursorCoordinates({ lng: 75, lat: 30 }, zoneConfig)).toEqual({
            zoneName: 'Test Zone',
            x: 35,
            z: 150
        });
    });
});

describe('formatCursorCoordinates', () => {
    it('uses in-game X/Z labels with rounded whole units', () => {
        expect(formatCursorCoordinates({ zoneName: 'Test Zone', x: 34.6, z: -89.4 })).toBe(
            'Test Zone · X 35 · Z -89'
        );
    });
});

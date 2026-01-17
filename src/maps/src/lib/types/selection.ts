import type { AnyWorldMarker, ZoneWorldPosition, ZoneConfig } from './world-map';
import type { EntityData } from '$lib/map/live/types';
import { transformEntityToWorld } from '$lib/map/coordinate-transform';

/**
 * Discriminated union for all selectable entities on the map.
 * Unifies static markers, live entities, and zones under one type system.
 */
export type Selection =
    | { type: 'marker'; marker: AnyWorldMarker }
    | { type: 'live'; entity: EntityData; zone: string }
    | { type: 'zone'; zone: ZoneWorldPosition }
    | null;

/**
 * Get world position from any selection type.
 * Returns null if selection doesn't have a valid position.
 *
 * @param liveEntities - Current live entities array (used to look up fresh position data)
 */
export function getSelectionPosition(
    selection: Selection,
    zones: ZoneWorldPosition[],
    zoneConfigs: Record<string, ZoneConfig>,
    overrides: Record<string, { worldX: number; worldY: number }>,
    liveEntities?: EntityData[]
): [number, number] | null {
    if (!selection) return null;

    switch (selection.type) {
        case 'marker': {
            // Markers already have worldPosition, just apply zone override if needed
            const override = overrides[selection.marker.zone];
            if (override) {
                const [x, y] = selection.marker.worldPosition;
                const zonePos = zones.find((z) => z.key === selection.marker.zone);
                if (!zonePos) return null;
                return [x - zonePos.worldX + override.worldX, y - zonePos.worldY + override.worldY];
            }
            return selection.marker.worldPosition;
        }
        case 'live': {
            // Look up current entity data (selection.entity may be stale snapshot)
            const currentEntity = liveEntities?.find((e) => e.id === selection.entity.id);
            if (!currentEntity) return null;
            return transformEntityToWorld(
                { ...currentEntity, zone: selection.zone },
                zones,
                zoneConfigs,
                overrides
            );
        }
        case 'zone': {
            const bounds = selection.zone.bounds;
            return [(bounds.minX + bounds.maxX) / 2, (bounds.minY + bounds.maxY) / 2];
        }
    }
}

/**
 * Get zone name from any selection type.
 */
export function getSelectionZone(selection: Selection): string | null {
    if (!selection) return null;

    switch (selection.type) {
        case 'marker':
            return selection.marker.zone;
        case 'live':
            return selection.zone;
        case 'zone':
            return selection.zone.key;
    }
}

/**
 * Get border color for selection.
 */
export function getSelectionBorderColor(selection: Selection): string {
    if (!selection) return 'border-gray-400';

    switch (selection.type) {
        case 'marker':
            return getMarkerBorderColor(selection.marker);
        case 'live':
            return getLiveEntityBorderColor(selection.entity);
        case 'zone':
            return 'border-purple-500';
    }
}

function getMarkerBorderColor(marker: AnyWorldMarker): string {
    switch (marker.category) {
        case 'enemy': {
            const chars = marker.characters;
            if (chars.length === 0) return 'border-gray-500';
            const hasUnique = chars.some((c) => c.isUnique);
            const hasRare = chars.some((c) => c.isRare);
            if (hasUnique) return 'border-white';
            if (hasRare) return 'border-red-500';
            return 'border-blue-500';
        }
        case 'npc':
            return 'border-green-500';
        case 'zone-line':
            return 'border-purple-500';
        case 'door':
            return 'border-yellow-500';
        case 'teleport':
            return 'border-cyan-500';
        default:
            return 'border-gray-500';
    }
}

function getLiveEntityBorderColor(entity: EntityData): string {
    switch (entity.entityType) {
        case 'player':
            return 'border-blue-500';
        case 'simplayer':
            return 'border-cyan-500';
        case 'pet':
            return 'border-green-500';
        case 'npc_friendly':
            return 'border-green-500';
        case 'npc_enemy':
            if (entity.rarity === 'boss') return 'border-white';
            if (entity.rarity === 'rare') return 'border-red-500';
            return 'border-blue-500';
        default:
            return 'border-gray-400';
    }
}

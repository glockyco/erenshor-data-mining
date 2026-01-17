import type { AnyWorldMarker, ZoneWorldPosition } from './world-map';
import type { EntityData } from '$lib/map/live/types';
import type { ZoneConfig } from '$lib/map/zone-tileset';
import { adjustMarkerPosition } from '$lib/map/coordinate-transform';
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
 */
export function getSelectionPosition(
    selection: Selection,
    zones: ZoneWorldPosition[],
    zoneConfigs: Record<string, ZoneConfig>,
    overrides: Record<string, { worldX: number; worldY: number }>
): [number, number] | null {
    if (!selection) return null;

    switch (selection.type) {
        case 'marker':
            return adjustMarkerPosition(
                selection.marker.worldPosition,
                selection.marker.zone,
                zones,
                overrides
            );
        case 'live':
            return transformEntityToWorld(
                { ...selection.entity, zone: selection.zone },
                zones,
                zoneConfigs,
                overrides
            );
        case 'zone': {
            const bounds = selection.zone.bounds;
            return [(bounds[0] + bounds[2]) / 2, (bounds[1] + bounds[3]) / 2];
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
 * Check if selection can be persisted to URL.
 * Only static markers are URL-persistable.
 */
export function isUrlPersistable(selection: Selection): boolean {
    return selection?.type === 'marker';
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

import type { AnyWorldMarker, ZoneWorldPosition, ZoneConfig } from './world-map';
import type { EntityData } from '$lib/map/live/types';
import { transformEntityToWorld } from '$lib/map/coordinate-transform';
import { MARKER_BORDER_COLORS } from '$lib/map/config';

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
    if (!selection) return 'border-l-gray-400';

    switch (selection.type) {
        case 'marker':
            return getMarkerBorderColor(selection.marker);
        case 'live':
            return getLiveEntityBorderColor(selection.entity);
        case 'zone':
            return 'border-l-purple-500';
    }
}

function getMarkerBorderColor(marker: AnyWorldMarker): string {
    // Special handling for enemy markers (need to check rarity)
    if (marker.category === 'enemy') {
        const chars = marker.characters;
        if (chars.length === 0) return 'border-l-gray-500';
        const hasUnique = chars.some((c) => c.isUnique);
        const hasRare = chars.some((c) => c.isRare);
        if (hasUnique) return 'border-l-violet-700';
        if (hasRare) return 'border-l-rose-600';
        return 'border-l-amber-600';
    }

    // For all other markers, use the centralized color mapping
    const borderColor = MARKER_BORDER_COLORS[marker.category];
    if (borderColor) {
        // Already has border-l- prefix (popups and tooltips expect border-l-{color})
        return borderColor;
    }

    return 'border-l-gray-500';
}

function getLiveEntityBorderColor(entity: EntityData): string {
    switch (entity.entityType) {
        case 'player':
            return 'border-l-lime-500';
        case 'simplayer':
            return 'border-l-cyan-500';
        case 'pet':
            return 'border-l-fuchsia-500';
        case 'npc_friendly':
            return 'border-l-emerald-500';
        case 'npc_enemy':
            if (entity.rarity === 'boss') return 'border-l-zinc-900';
            if (entity.rarity === 'rare') return 'border-l-red-500';
            return 'border-l-orange-500';
        default:
            return 'border-l-gray-400';
    }
}

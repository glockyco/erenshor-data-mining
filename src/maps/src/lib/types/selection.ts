import { Rarity } from '$lib/map-markers';
import type { AnyWorldMarker, ZoneWorldPosition, ZoneConfig } from './world-map';
import type { EntityData } from '$lib/map/live/types';
import type { SearchResult } from '$lib/map/search';
import type { SearchIndex } from '$lib/map/search';
import { transformEntityToWorld } from '$lib/map/coordinate-transform';
import { MARKER_BORDER_COLORS } from '$lib/map/config';

// =============================================================================
// Selection Type
// =============================================================================

/**
 * Discriminated union for all selectable entities on the map.
 * Unifies static markers, live entities, zones, and search results.
 */
export type Selection =
    | { type: 'marker'; marker: AnyWorldMarker }
    | { type: 'live'; entity: EntityData; zone: string }
    | { type: 'zone'; zone: ZoneWorldPosition }
    | { type: 'search'; result: SearchResult }
    | { type: 'search-not-found'; searchType: 'enemy' | 'npc' | 'zone'; name: string }
    | null;

// =============================================================================
// Selection Helpers
// =============================================================================

/**
 * Get world position from any selection type.
 * Returns null for search selections (they have multiple positions).
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
        case 'search':
            // Search selections have multiple positions; no single position
            return null;
        case 'search-not-found':
            return null;
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
        case 'search':
            // Search results span multiple zones
            return null;
        case 'search-not-found':
            return null;
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
        case 'search':
            return getSearchBorderColor(selection.result);
        case 'search-not-found':
            return 'border-l-zinc-500';
    }
}

function getSearchBorderColor(result: SearchResult): string {
    switch (result.type) {
        case 'enemy':
            if (result.effectiveRarity === Rarity.unique) return 'border-l-violet-700';
            if (result.effectiveRarity === Rarity.rare) return 'border-l-rose-600';
            return 'border-l-amber-600';
        case 'npc':
            return 'border-l-sky-500';
        case 'zone':
            return 'border-l-purple-500';
    }
}

function getMarkerBorderColor(marker: AnyWorldMarker): string {
    if (marker.category === 'enemy') {
        const chars = marker.characters;
        if (chars.length === 0) return 'border-l-gray-500';
        const hasUnique = chars.some((c) => c.effectiveRarity === Rarity.unique);
        const hasRare = chars.some((c) => c.effectiveRarity === Rarity.rare);
        if (hasUnique) return 'border-l-violet-700';
        if (hasRare) return 'border-l-rose-600';
        return 'border-l-amber-600';
    }

    const borderColor = MARKER_BORDER_COLORS[marker.category];
    if (borderColor) {
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

// =============================================================================
// URL Serialization
// =============================================================================

/**
 * Serialize a selection to a URL-safe string.
 *
 * Format: `type:value`
 * - `marker:<stableKey>`
 * - `zone:<zoneKey>`
 * - `enemy:<name>`
 * - `npc:<name>`
 * - Live selections are not serializable (ephemeral).
 */
export function serializeSelection(selection: Selection): string | null {
    if (!selection) return null;

    switch (selection.type) {
        case 'marker':
            return `marker:${selection.marker.stableKey}`;
        case 'zone':
            return `zone:${selection.zone.key}`;
        case 'search': {
            const r = selection.result;
            switch (r.type) {
                case 'enemy':
                    return `enemy:${r.name}`;
                case 'npc':
                    return `npc:${r.name}`;
                case 'zone':
                    // Zone search results serialize as regular zone selections
                    return `zone:${r.key}`;
            }
            break;
        }
        case 'search-not-found': {
            const s = selection;
            if (s.searchType === 'zone') return `zone:${s.name}`;
            return `${s.searchType}:${s.name}`;
        }
        case 'live':
            return null;
    }
    return null;
}

/**
 * Data needed to deserialize a selection from a URL string.
 */
export interface DeserializeContext {
    findMarkerByStableKey: (stableKey: string) => AnyWorldMarker | null;
    findZoneByKey: (key: string) => ZoneWorldPosition | null;
    searchIndex: SearchIndex;
}

/**
 * Deserialize a selection from a URL string.
 * Returns null if the string is invalid or the referenced entity doesn't exist.
 */
export function deserializeSelection(raw: string, ctx: DeserializeContext): Selection {
    const colonIdx = raw.indexOf(':');
    if (colonIdx === -1) return null;

    const prefix = raw.slice(0, colonIdx);
    const value = raw.slice(colonIdx + 1);

    switch (prefix) {
        case 'marker': {
            const marker = ctx.findMarkerByStableKey(value);
            if (!marker) {
                console.warn(`Selection restore: marker not found: ${value}`);
                return null;
            }
            return { type: 'marker', marker };
        }
        case 'zone': {
            const zone = ctx.findZoneByKey(value);
            if (!zone) {
                return { type: 'search-not-found', searchType: 'zone', name: value };
            }
            return { type: 'zone', zone };
        }
        case 'enemy': {
            const markers = ctx.searchIndex.enemyProvider.getMarkers(value);
            if (markers.length === 0) {
                return { type: 'search-not-found', searchType: 'enemy', name: value };
            }
            const zones = new Set(markers.map((m) => m.zone));
            const chars = markers.flatMap((m) => m.characters.filter((c) => c.name === value));
            const effectiveRarity = chars.some((c) => c.effectiveRarity === Rarity.unique)
                ? Rarity.unique
                : chars.some((c) => c.effectiveRarity === Rarity.rare)
                  ? Rarity.rare
                  : Rarity.common;
            return {
                type: 'search',
                result: {
                    type: 'enemy',
                    name: value,
                    effectiveRarity,
                    spawnCount: markers.length,
                    zoneCount: zones.size
                }
            };
        }
        case 'npc': {
            const markers = ctx.searchIndex.npcProvider.getMarkers(value);
            if (markers.length === 0) {
                return { type: 'search-not-found', searchType: 'npc', name: value };
            }
            const zones = new Set(markers.map((m) => m.zone));
            return {
                type: 'search',
                result: {
                    type: 'npc',
                    name: value,
                    isVendor: markers.some((m) => m.characters.some((c) => c.isVendor)),
                    spawnCount: markers.length,
                    zoneCount: zones.size
                }
            };
        }
        default:
            console.warn(`Selection restore: unknown prefix: ${prefix}`);
            return null;
    }
}

/**
 * Item search provider.
 *
 * Indexes every map-visible droppable item. A single search result represents
 * ALL spawn points where any character that drops the item can appear. Items
 * are keyed by stable key, not display name, because display names are not
 * unique (e.g. "Scribbles of a Mad Priest" has two distinct stable keys) —
 * keying by name would wrongly merge unrelated drop sets.
 */

import type { WorldEnemy, WorldNpc } from '$lib/types/world-map';
import type { ItemDropperRow } from '$lib/map-markers';
import type {
    SearchProvider,
    IndexEntry,
    ResolvedHighlight,
    SearchResult,
    ItemSearchResult
} from './types';

type AnySpawnMarker = WorldEnemy | WorldNpc;

interface ItemEntry {
    result: ItemSearchResult;
    /** Character stable keys that drop this item */
    characterStableKeys: string[];
    /** All drop rows for this item (for popup rendering) */
    dropRows: ItemDropperRow[];
}

export class ItemSearchProvider implements SearchProvider {
    readonly categoryLabel = 'Drops';
    readonly categoryOrder = 0;

    private readonly itemByStableKey: Map<string, ItemEntry>;
    /** Character stable key → spawn markers containing that character */
    private readonly markersByCharacter: Map<string, AnySpawnMarker[]>;

    constructor(
        rows: ItemDropperRow[],
        allMarkers: AnySpawnMarker[]
    ) {
        this.itemByStableKey = new Map();
        this.markersByCharacter = new Map();

        // Index markers by every character stable key they contain
        for (const marker of allMarkers) {
            const seen = new Set<string>();
            for (const char of marker.characters) {
                if (seen.has(char.stableKey)) continue;
                seen.add(char.stableKey);
                const existing = this.markersByCharacter.get(char.stableKey);
                if (existing) {
                    existing.push(marker);
                } else {
                    this.markersByCharacter.set(char.stableKey, [marker]);
                }
            }
        }

        // Group drop rows by item stable key
        const rowsByKey = new Map<string, ItemDropperRow[]>();
        for (const row of rows) {
            const existing = rowsByKey.get(row.itemStableKey);
            if (existing) {
                existing.push(row);
            } else {
                rowsByKey.set(row.itemStableKey, [row]);
            }
        }

        // Build one search result per item, cross-referencing dropper
        // character stable keys against loaded markers to compute the set
        // of spawn points and zones.
        for (const [itemStableKey, itemRows] of rowsByKey) {
            const first = itemRows[0];
            const characterStableKeys = [
                ...new Set(itemRows.map((r) => r.characterStableKey))
            ];

            // Collect every spawn marker containing at least one dropper
            const markerSet = new Set<AnySpawnMarker>();
            const zoneSet = new Set<string>();
            for (const charKey of characterStableKeys) {
                const markers = this.markersByCharacter.get(charKey);
                if (!markers) continue;
                for (const marker of markers) {
                    markerSet.add(marker);
                    zoneSet.add(marker.zone);
                }
            }

            // Only index items that have at least one resolvable spawn point
            // on the map. Items whose droppers never spawn (e.g. vendor-only
            // or event-only sources) are invisible to the map and excluded.
            if (markerSet.size === 0) continue;

            this.itemByStableKey.set(itemStableKey, {
                result: {
                    type: 'item',
                    itemStableKey,
                    itemName: first.displayName,
                    wikiPageName: first.wikiPageName,
                    dropperCount: characterStableKeys.length,
                    zoneCount: zoneSet.size
                },
                characterStableKeys,
                dropRows: itemRows
            });
        }
    }

    buildIndex(): IndexEntry[] {
        const entries: IndexEntry[] = [];
        for (const entry of this.itemByStableKey.values()) {
            entries.push({
                searchText: entry.result.itemName.toLowerCase(),
                result: entry.result
            });
        }
        return entries;
    }

    resolveHighlight(result: SearchResult): ResolvedHighlight {
        if (result.type !== 'item') return { type: 'none' };

        const entry = this.itemByStableKey.get(
            (result as ItemSearchResult).itemStableKey
        );
        if (!entry) return { type: 'none' };

        const markerSet = new Set<AnySpawnMarker>();
        for (const charKey of entry.characterStableKeys) {
            const markers = this.markersByCharacter.get(charKey);
            if (!markers) continue;
            for (const marker of markers) markerSet.add(marker);
        }
        if (markerSet.size === 0) return { type: 'none' };

        const markers = [...markerSet];
        return {
            type: 'positions',
            positions: markers.map((m) => m.worldPosition),
            stableKeys: markers.map((m) => m.stableKey)
        };
    }

    /** All spawn markers containing a dropper of the given item (popup) */
    getMarkersForItem(itemStableKey: string): AnySpawnMarker[] {
        const entry = this.itemByStableKey.get(itemStableKey);
        if (!entry) return [];

        const markerSet = new Set<AnySpawnMarker>();
        for (const charKey of entry.characterStableKeys) {
            const markers = this.markersByCharacter.get(charKey);
            if (!markers) continue;
            for (const marker of markers) markerSet.add(marker);
        }
        return [...markerSet];
    }

    /** Drop rows for the given item, sorted by drop probability descending */
    getDropRowsForItem(itemStableKey: string): ItemDropperRow[] {
        const entry = this.itemByStableKey.get(itemStableKey);
        if (!entry) return [];
        return [...entry.dropRows].sort((a, b) => b.dropProbability - a.dropProbability);
    }

    /**
     * Get the cached search result for an item stable key (URL restore).
     * Returns null if the item has no resolvable spawn points and was never
     * indexed — in that case the selection cannot be restored.
     */
    getResult(itemStableKey: string): ItemSearchResult | null {
        return this.itemByStableKey.get(itemStableKey)?.result ?? null;
    }
}

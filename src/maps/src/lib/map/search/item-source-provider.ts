/**
 * Item search provider.
 *
 * Indexes every map-visible item acquisition source with a fixed map location:
 * drops, vendors, mining nodes, fishing spots, and item bags. A single search
 * result represents all resolved source locations for the item. Items are keyed
 * by stable key, not display name, because display names are not unique (e.g.
 * "Scribbles of a Mad Priest" has two distinct stable keys) — keying by name
 * would wrongly merge unrelated source sets.
 */

import type {
    WorldEnemy,
    WorldNpc,
    WorldMiningNode,
    WorldWater,
    WorldItemBag
} from '$lib/types/world-map';
import type {
    ItemSourceRow,
    ItemSourceItemMeta,
    ItemDropSource,
    ItemVendorSource,
    ItemMiningSource,
    ItemFishingSource,
    ItemBagSource
} from '$lib/map-markers';
import type {
    SearchProvider,
    IndexEntry,
    ResolvedHighlight,
    SearchResult,
    ItemSearchResult,
    ItemSourceCounts
} from './types';

export type AnySpawnMarker = WorldEnemy | WorldNpc;
export type AnySourceMarker = AnySpawnMarker | WorldMiningNode | WorldWater | WorldItemBag;

export type ResolvedItemSource =
    | { kind: 'drop'; row: ItemDropSource; markers: AnySpawnMarker[] }
    | { kind: 'vendor'; row: ItemVendorSource; markers: AnySpawnMarker[] }
    | { kind: 'mining'; row: ItemMiningSource; marker: WorldMiningNode }
    | { kind: 'fishing'; row: ItemFishingSource; marker: WorldWater }
    | { kind: 'bag'; row: ItemBagSource; marker: WorldItemBag };

interface ItemEntry {
    result: ItemSearchResult;
    sources: ResolvedItemSource[];
}

export class ItemSearchProvider implements SearchProvider {
    readonly categoryLabel = 'Items';
    readonly categoryOrder = 0;

    private readonly itemByStableKey: Map<string, ItemEntry>;
    /** Character stable key → spawn markers containing that character */
    private readonly markersByCharacter: Map<string, AnySpawnMarker[]>;

    constructor(
        rows: ItemSourceRow[],
        spawnMarkers: AnySpawnMarker[],
        miningNodes: WorldMiningNode[],
        water: WorldWater[],
        itemBags: WorldItemBag[],
        allItems: ItemSourceItemMeta[] = rows
    ) {
        this.itemByStableKey = new Map();
        this.markersByCharacter = new Map();

        // Index markers by every character stable key they contain
        for (const marker of spawnMarkers) {
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

        const miningByKey = new Map<string, WorldMiningNode>(
            miningNodes.map(
                (marker): [string, WorldMiningNode] => [marker.stableKey, marker]
            )
        );
        const waterByKey = new Map<string, WorldWater>(
            water.map((marker): [string, WorldWater] => [marker.stableKey, marker])
        );
        const bagByKey = new Map<string, WorldItemBag>(
            itemBags.map(
                (marker): [string, WorldItemBag] => [marker.stableKey, marker]
            )
        );

        // Group source rows by item stable key
        const rowsByKey = new Map<string, ItemSourceRow[]>();
        for (const row of rows) {
            const existing = rowsByKey.get(row.itemStableKey);
            if (existing) {
                existing.push(row);
            } else {
                rowsByKey.set(row.itemStableKey, [row]);
            }
        }

        const itemsByKey = new Map<string, ItemSourceItemMeta>();
        for (const item of allItems) {
            if (!item.wikiPageName?.trim()) continue;
            itemsByKey.set(item.itemStableKey, item);
        }

        // Build one search result per wiki item, retaining only sources whose
        // map markers are loaded. Items without a resolvable source remain in
        // the index so their obtainability can be shown as unknown.
        for (const [itemStableKey, item] of itemsByKey) {
            const itemRows = rowsByKey.get(itemStableKey) ?? [];
            const sources: ResolvedItemSource[] = [];

            for (const row of itemRows) {
                switch (row.kind) {
                    case 'drop': {
                        const markers = this.markersByCharacter.get(row.characterStableKey);
                        if (markers?.length) sources.push({ kind: 'drop', row, markers });
                        break;
                    }
                    case 'vendor': {
                        const markers = this.markersByCharacter.get(row.characterStableKey);
                        if (markers?.length) sources.push({ kind: 'vendor', row, markers });
                        break;
                    }
                    case 'mining': {
                        const marker = miningByKey.get(row.nodeStableKey);
                        if (marker) sources.push({ kind: 'mining', row, marker });
                        break;
                    }
                    case 'fishing': {
                        const marker = waterByKey.get(row.waterStableKey);
                        if (marker) sources.push({ kind: 'fishing', row, marker });
                        break;
                    }
                    case 'bag': {
                        const marker = bagByKey.get(row.bagStableKey);
                        if (marker) sources.push({ kind: 'bag', row, marker });
                        break;
                    }
                }
            }

            const dropperKeys = new Set<string>();
            const vendorKeys = new Set<string>();
            const miningKeys = new Set<string>();
            const fishingKeys = new Set<string>();
            const bagKeys = new Set<string>();
            const zoneSet = new Set<string>();

            for (const source of sources) {
                if (source.kind === 'drop') {
                    dropperKeys.add(source.row.characterStableKey);
                    for (const marker of source.markers) zoneSet.add(marker.zone);
                } else if (source.kind === 'vendor') {
                    vendorKeys.add(source.row.characterStableKey);
                    for (const marker of source.markers) zoneSet.add(marker.zone);
                } else if (source.kind === 'mining') {
                    miningKeys.add(source.marker.stableKey);
                    zoneSet.add(source.marker.zone);
                } else if (source.kind === 'fishing') {
                    fishingKeys.add(source.marker.stableKey);
                    zoneSet.add(source.marker.zone);
                } else {
                    bagKeys.add(source.marker.stableKey);
                    zoneSet.add(source.marker.zone);
                }
            }

            const sourceCounts: ItemSourceCounts = {
                droppers: dropperKeys.size,
                vendors: vendorKeys.size,
                miningNodes: miningKeys.size,
                fishingSpots: fishingKeys.size,
                itemBags: bagKeys.size
            };

            this.itemByStableKey.set(itemStableKey, {
                result: {
                    type: 'item',
                    itemStableKey,
                    itemName: item.displayName,
                    iconName: item.iconName,
                    wikiPageName: item.wikiPageName,
                    sourceCounts,
                    zoneCount: zoneSet.size,
                    hasKnownSource: sources.length > 0
                },
                sources
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

        const markers = this.getMarkersForItem(entry.result.itemStableKey);
        if (markers.length === 0) return { type: 'none' };

        return {
            type: 'positions',
            positions: markers.map((marker) => marker.worldPosition),
            stableKeys: markers.map((marker) => marker.stableKey)
        };
    }

    /** All source markers for the given item (popup) */
    getMarkersForItem(itemStableKey: string): AnySourceMarker[] {
        const entry = this.itemByStableKey.get(itemStableKey);
        if (!entry) return [];

        const markerSet = new Set<AnySourceMarker>();
        for (const source of entry.sources) {
            if (source.kind === 'drop' || source.kind === 'vendor') {
                for (const marker of source.markers) markerSet.add(marker);
            } else {
                markerSet.add(source.marker);
            }
        }
        return [...markerSet];
    }

    /** All resolved acquisition sources for the given item (popup) */
    getSourcesForItem(itemStableKey: string): ResolvedItemSource[] {
        return this.itemByStableKey.get(itemStableKey)?.sources ?? [];
    }

    /**
     * Get the cached search result for an item stable key (URL restore).
     * Returns null if the item has no resolvable source locations and was never
     * indexed — in that case the selection cannot be restored.
     */
    getResult(itemStableKey: string): ItemSearchResult | null {
        return this.itemByStableKey.get(itemStableKey)?.result ?? null;
    }
}

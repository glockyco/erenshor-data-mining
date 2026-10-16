/**
 * Item search provider.
 *
 * Indexes acquisition sources with map locations and listed sources without
 * locations. A single search result represents all sources for the item. Items are
 * keyed by stable key, not display name, because display names are not unique
 * (e.g. "Scribbles of a Mad Priest" has two distinct stable keys) — keying by
 * name would wrongly merge unrelated source sets.
 */

import type {
    WorldEnemy,
    WorldNpc,
    WorldMiningNode,
    WorldWater,
    WorldItemBag,
    WorldTreasureLoc
} from '$lib/types/world-map';
import type {
    ItemSourceRow,
    ItemSourceItemMeta,
    ItemDropSource,
    ItemVendorSource,
    ItemAuctionHouseSource,
    ItemTreasureSource,
    ItemMiningSource,
    ItemFishingSource,
    ItemBagSource,
    ItemWorldDropSource,
    ItemCommonWorldSource,
    ItemDialogSource,
    ItemQuestSource,
    ItemCraftSource,
    ItemUseSource,
    ItemStartingSource
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
export type AnySourceMarker = AnySpawnMarker | WorldMiningNode | WorldWater | WorldItemBag | WorldTreasureLoc;

export type ResolvedItemSource =
    | { kind: 'drop'; row: ItemDropSource; markers: AnySpawnMarker[] }
    | { kind: 'vendor'; row: ItemVendorSource; markers: AnySpawnMarker[] }
    | {
        kind: 'auction_house';
        row: ItemAuctionHouseSource;
        markers: AnySpawnMarker[];
        brokers: { row: ItemAuctionHouseSource['brokers'][number]; markers: AnySpawnMarker[] }[];
    }
    | { kind: 'treasure'; row: ItemTreasureSource; markers: WorldTreasureLoc[] }
    | { kind: 'mining'; row: ItemMiningSource; marker: WorldMiningNode }
    | { kind: 'fishing'; row: ItemFishingSource; marker: WorldWater }
    | { kind: 'bag'; row: ItemBagSource; marker: WorldItemBag }
    | { kind: 'world'; row: ItemWorldDropSource }
    | { kind: 'common_world_item'; row: ItemCommonWorldSource }
    | { kind: 'dialog'; row: ItemDialogSource; markers: AnySpawnMarker[] }
    | { kind: 'quest'; row: ItemQuestSource; markers: AnySpawnMarker[] }
    | { kind: 'craft'; row: ItemCraftSource }
    | { kind: 'item_use'; row: ItemUseSource }
    | { kind: 'starting'; row: ItemStartingSource };

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
        allItems: ItemSourceItemMeta[] = rows,
        treasureLocs: WorldTreasureLoc[] = []
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
            miningNodes.map((marker): [string, WorldMiningNode] => [marker.stableKey, marker])
        );
        const waterByKey = new Map<string, WorldWater>(
            water.map((marker): [string, WorldWater] => [marker.stableKey, marker])
        );
        const bagByKey = new Map<string, WorldItemBag>(
            itemBags.map((marker): [string, WorldItemBag] => [marker.stableKey, marker])
        );
        const treasureByKey = new Map(treasureLocs.map((marker) => [marker.stableKey, marker]));

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

        // Explicit sources survive even when the export cannot locate their
        // character. Location-bound sources use only the markers loaded here.
        for (const [itemStableKey, item] of itemsByKey) {
            const itemRows = rowsByKey.get(itemStableKey) ?? [];
            const sources: ResolvedItemSource[] = [];

            for (const row of itemRows) {
                switch (row.kind) {
                    case 'drop': {
                        const markers = this.markersByCharacter.get(row.characterStableKey) ?? [];
                        sources.push({ kind: 'drop', row, markers });
                        break;
                    }
                    case 'vendor': {
                        const markers = this.markersByCharacter.get(row.characterStableKey) ?? [];
                        sources.push({ kind: 'vendor', row, markers });
                        break;
                    }
                    case 'auction_house': {
                        const brokers = row.brokers.map((broker) => ({
                            row: broker,
                            markers: this.markersByCharacter.get(broker.characterStableKey) ?? []
                        }));
                        const markers = [...new Set(brokers.flatMap((broker) => broker.markers))];
                        sources.push({ kind: 'auction_house', row, markers, brokers });
                        break;
                    }
                    case 'treasure': {
                        const marker = treasureByKey.get(row.treasureLocationStableKey);
                        sources.push({ kind: 'treasure', row, markers: marker ? [marker] : [] });
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
                    case 'dialog': {
                        const markers = this.markersByCharacter.get(row.characterStableKey);
                        if (markers?.length) sources.push({ kind: 'dialog', row, markers });
                        break;
                    }
                    case 'quest': {
                        const markers = row.turnInCharacterStableKey
                            ? (this.markersByCharacter.get(row.turnInCharacterStableKey) ?? [])
                            : [];
                        sources.push({ kind: 'quest', row, markers });
                        break;
                    }
                    case 'craft':
                        sources.push({ kind: 'craft', row });
                        break;
                    case 'item_use':
                        sources.push({ kind: 'item_use', row });
                        break;
                    case 'starting':
                        sources.push({ kind: 'starting', row });
                        break;
                    case 'common_world_item':
                        sources.push({ kind: 'common_world_item', row });
                        break;
                    case 'world': {
                        sources.push({ kind: 'world', row });
                        break;
                    }
                }
            }

            const dropperKeys = new Set<string>();
            const vendorKeys = new Set<string>();
            const miningKeys = new Set<string>();
            const fishingKeys = new Set<string>();
            const bagKeys = new Set<string>();
            let worldDrops = 0;
            const giverKeys = new Set<string>();
            const questKeys = new Set<string>();
            const recipeKeys = new Set<string>();
            const itemUseKeys = new Set<string>();
            const startingKeys = new Set<string>();
            const zoneSet = new Set<string>();

            for (const source of sources) {
                if (source.kind === 'drop' || source.kind === 'treasure') {
                    dropperKeys.add(source.row.characterStableKey);
                    for (const marker of source.markers) zoneSet.add(marker.zone);
                } else if (source.kind === 'vendor') {
                    vendorKeys.add(source.row.characterStableKey);
                    for (const marker of source.markers) zoneSet.add(marker.zone);
                } else if (source.kind === 'auction_house') {
                    for (const marker of source.markers) zoneSet.add(marker.zone);
                } else if (source.kind === 'mining') {
                    miningKeys.add(source.marker.stableKey);
                    zoneSet.add(source.marker.zone);
                } else if (source.kind === 'fishing') {
                    fishingKeys.add(source.marker.stableKey);
                    zoneSet.add(source.marker.zone);
                } else if (source.kind === 'bag') {
                    bagKeys.add(source.marker.stableKey);
                    zoneSet.add(source.marker.zone);
                } else if (source.kind === 'dialog') {
                    giverKeys.add(source.row.characterStableKey);
                    for (const marker of source.markers) zoneSet.add(marker.zone);
                } else if (source.kind === 'quest') {
                    questKeys.add(source.row.questStableKey);
                    for (const marker of source.markers) zoneSet.add(marker.zone);
                } else if (source.kind === 'craft') {
                    recipeKeys.add(source.row.recipeStableKey);
                } else if (source.kind === 'item_use') {
                    itemUseKeys.add(source.row.sourceItemStableKey);
                } else if (source.kind === 'starting') {
                    startingKeys.add(source.row.className);
                } else if (source.kind === 'world' || source.kind === 'common_world_item') {
                    worldDrops++;
                }
            }

            const sourceCounts: ItemSourceCounts = {
                droppers: dropperKeys.size,
                vendors: vendorKeys.size,
                miningNodes: miningKeys.size,
                fishingSpots: fishingKeys.size,
                itemBags: bagKeys.size,
                worldDrops,
                auctionHouses: sources.some((source) => source.kind === 'auction_house') ? 1 : 0,
                givers: giverKeys.size,
                quests: questKeys.size,
                recipes: recipeKeys.size,
                itemUses: itemUseKeys.size,
                startingClasses: startingKeys.size
            };

            this.itemByStableKey.set(itemStableKey, {
                result: {
                    type: 'item',
                    itemStableKey,
                    itemName: item.displayName,
                    iconHash: item.iconHash,
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

        const entry = this.itemByStableKey.get((result as ItemSearchResult).itemStableKey);
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
            if ('markers' in source) {
                for (const marker of source.markers) markerSet.add(marker);
            } else if ('marker' in source) {
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
     * Returns null only when the item has no wiki page and was not indexed.
     */
    getResult(itemStableKey: string): ItemSearchResult | null {
        return this.itemByStableKey.get(itemStableKey)?.result ?? null;
    }
}

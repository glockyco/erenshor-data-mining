import type { WorldEnemy, WorldNpc, WorldMiningNode, WorldWater, WorldItemBag, WorldTreasureLoc, WorldZoneLine } from '$lib/types/world-map';
import type { ItemSourceRow, ItemSourceItemMeta } from '$lib/map-markers';
import { isActionableAcquisition, conditionsSatisfiable } from '../../item-provenance';
import type { SearchProvider, IndexEntry, ResolvedHighlight, SearchResult, ItemSearchResult, ItemSourceCounts } from './types';

export type AnySpawnMarker = WorldEnemy | WorldNpc;
export type AnySourceMarker = AnySpawnMarker | WorldMiningNode | WorldWater | WorldItemBag | WorldTreasureLoc;
export interface ResolvedItemSource {
    kind: string;
    row: ItemSourceRow;
    presentation: 'source' | 'any_water';
    /** Complete final acquisition rows represented by this presentation source. */
    members: ItemSourceRow[];
    markers: AnySourceMarker[];
    entries: WorldZoneLine[];
    /** Explicit locations without a marker remain listed, never inferred from the source character. */
    unlocated: ItemSourceRow['provenance']['locations'];
}
interface ItemEntry {
    result: ItemSearchResult;
    sources: ResolvedItemSource[];
}

const SOURCE_CATEGORY: Record<string, keyof ItemSourceCounts> = {
    character_drop: 'droppers', vendor: 'vendors', mining: 'miningNodes', fishing: 'fishingSpots',
    fishing_bonus: 'fishingSpots', item_bag: 'itemBags', common_world_item: 'worldDrops',
    special_world_drop: 'worldDrops', auction_house: 'auctionHouses', dialog: 'givers',
    ui_grant: 'givers', quest_reward: 'quests', crafting: 'recipes', item_drop: 'itemUses',
    spell_created: 'itemUses', item_conversion: 'itemUses', starting_class: 'startingClasses'
};

function isGlobalFishingReplacement(row: ItemSourceRow): boolean {
    const fact = row.provenance;
    const bonus = row.fishingBonus;
    return fact.kind === 'fishing' && fact.probability_stage === 'final_acquisition' &&
        fact.probability_kind === 'exact' && fact.probability_min === fact.probability_max &&
        bonus !== null && bonus.kind === 'fishing_bonus' && bonus.probability_stage === 'native_pool' &&
        bonus.mechanic === 'fishing_global_replacement' && bonus.probability_kind === 'exact' &&
        bonus.item_stable_key === fact.item_stable_key && bonus.probability_min === fact.probability_min &&
        bonus.probability_max === fact.probability_max;
}

export class ItemSearchProvider implements SearchProvider {
    readonly categoryLabel = 'Items';
    readonly categoryOrder = 0;
    private readonly itemByStableKey = new Map<string, ItemEntry>();

    constructor(rows: ItemSourceRow[], spawnMarkers: AnySpawnMarker[], miningNodes: WorldMiningNode[],
        water: WorldWater[], itemBags: WorldItemBag[], allItems: ItemSourceItemMeta[] = rows,
        treasureLocs: WorldTreasureLoc[] = [], zoneLines: WorldZoneLine[] = []) {
        const entrances = new Map(zoneLines.map((marker) => [marker.stableKey, marker]));
        const byMarker = new Map<string, AnySourceMarker>();
        for (const marker of [...spawnMarkers, ...miningNodes, ...water, ...itemBags, ...treasureLocs]) {
            byMarker.set(marker.stableKey, marker);
        }
        const byItem = new Map<string, ItemSourceRow[]>();
        for (const row of rows) {
            if (!isActionableAcquisition(row.provenance)) continue;
            if (row.originatingDisposition.item_stable_key !== row.provenance.item_stable_key ||
                row.displayDisposition.item_stable_key !== row.itemStableKey) throw new Error('Map source lifecycle identity mismatch');
            if (row.originatingDisposition.disposition !== 'current' || row.displayDisposition.disposition !== 'current') continue;
            const group = byItem.get(row.itemStableKey) ?? [];
            group.push(row);
            byItem.set(row.itemStableKey, group);
        }
        for (const item of allItems) {
            if (!item.wikiPageName?.trim() || this.itemByStableKey.has(item.itemStableKey)) continue;
            const sources: ResolvedItemSource[] = [];
            let anyWater: Map<string, ResolvedItemSource> | null = null;
            for (const row of byItem.get(item.itemStableKey) ?? []) {
                if (isGlobalFishingReplacement(row)) {
                    anyWater ??= new Map<string, ResolvedItemSource>();
                    const key = row.fishingBonus!.acquisition_key;
                    const existing = anyWater.get(key);
                    if (existing) existing.members.push(row);
                    else {
                        const grouped: ResolvedItemSource = { kind: row.kind, row, presentation: 'any_water',
                            members: [row], markers: [], unlocated: [], entries: [] };
                        anyWater.set(key, grouped);
                        sources.push(grouped);
                    }
                    continue;
                }
                const markers = new Map<string, AnySourceMarker>();
                const unlocated: ResolvedItemSource['unlocated'] = [];
                for (const location of row.provenance.locations) {
                    if (!conditionsSatisfiable([...row.provenance.conditions, ...location.conditions])) {
                        unlocated.push(location);
                        continue;
                    }
                    const marker = location.coordinate_stable_key ? byMarker.get(location.coordinate_stable_key) : undefined;
                    if (marker && location.relation !== 'unlocated') markers.set(marker.stableKey, marker);
                    else unlocated.push(location);
                }
                const entries = [...new Set(row.provenance.locations.filter((location) => conditionsSatisfiable([...row.provenance.conditions, ...location.conditions]))
                    .flatMap((location) => location.entry_zone_line_keys))].flatMap((key) => {
                    const entrance = entrances.get(key);
                    return entrance ? [entrance] : [];
                });
                sources.push({ kind: row.kind, row, presentation: 'source', members: [row],
                    markers: [...markers.values()], unlocated, entries });
            }
            const sourceCounts: ItemSourceCounts = { droppers: 0, vendors: 0, miningNodes: 0,
                fishingSpots: 0, anyWater: 0, itemBags: 0, worldDrops: 0, auctionHouses: 0, givers: 0,
                quests: 0, recipes: 0, itemUses: 0, startingClasses: 0 };
            const counts = new Map<keyof ItemSourceCounts, Set<string>>();
            const zones = new Set<string>();
            for (const source of sources) {
                if (source.presentation === 'any_water') {
                    sourceCounts.anyWater++;
                    continue;
                }
                const fact = source.row.provenance;
                const key = SOURCE_CATEGORY[fact.kind];
                if (key) {
                    const identities = counts.get(key) ?? new Set<string>();
                    identities.add(fact.source_group_key ?? fact.source_stable_key ?? fact.acquisition_key);
                    counts.set(key, identities);
                }
                for (const marker of source.markers) zones.add(marker.zone);
                for (const location of fact.locations) if (location.scene && conditionsSatisfiable([...fact.conditions, ...location.conditions])) zones.add(location.scene);
            }
            for (const [key, identities] of counts) sourceCounts[key] = identities.size;
            this.itemByStableKey.set(item.itemStableKey, { sources, result: {
                type: 'item', itemStableKey: item.itemStableKey, itemName: item.displayName,
                iconHash: item.iconHash, wikiPageName: item.wikiPageName, sourceCounts,
                zoneCount: zones.size, hasKnownSource: sources.length > 0
            } });
        }
    }

    buildIndex(): IndexEntry[] {
        return [...this.itemByStableKey.values()].map(({ result }) => ({ searchText: result.itemName.toLowerCase(), result }));
    }

    resolveHighlight(result: SearchResult): ResolvedHighlight {
        if (result.type !== 'item') return { type: 'none' };
        const markers = this.getMarkersForItem(result.itemStableKey);
        return markers.length ? { type: 'positions', positions: markers.map((marker) => marker.worldPosition),
            stableKeys: markers.map((marker) => marker.stableKey) } : { type: 'none' };
    }

    getMarkersForItem(itemStableKey: string): AnySourceMarker[] {
        const markers = new Map<string, AnySourceMarker>();
        for (const source of this.getSourcesForItem(itemStableKey)) {
            for (const marker of source.markers) markers.set(marker.stableKey, marker);
        }
        return [...markers.values()];
    }

    getSourcesForItem(itemStableKey: string): ResolvedItemSource[] {
        return this.itemByStableKey.get(itemStableKey)?.sources ?? [];
    }

    getResult(itemStableKey: string): ItemSearchResult | null {
        return this.itemByStableKey.get(itemStableKey)?.result ?? null;
    }
}

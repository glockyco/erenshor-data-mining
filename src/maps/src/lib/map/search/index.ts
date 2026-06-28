/**
 * Search index builder and search function.
 *
 * Combines all registered providers into a single flat index and provides
 * prefix-then-substring matching with round-robin interleaving across categories.
 */

import type { WorldEnemy, WorldNpc, ZoneWorldPosition } from '$lib/types/world-map';
import type { ItemDropperRow } from '$lib/map-markers';
import type {
    SearchProvider,
    IndexEntry,
    SearchResult,
    ResolvedHighlight,
    EnemySearchResult,
    SearchMatch
} from './types';
import { EnemySearchProvider } from './enemy-provider';
import { NpcSearchProvider } from './npc-provider';
import { ZoneSearchProvider } from './zone-provider';
import { ItemSearchProvider } from './item-drop-provider';
import { searchTiered } from './fuse-index';

export type { SearchResult, IndexEntry, ResolvedHighlight, SearchMatch } from './types';
export type {
    EnemySearchResult,
    NpcSearchResult,
    ZoneSearchResult,
    ItemSearchResult
} from './types';

// =============================================================================
// Search Index
// =============================================================================

export interface SearchIndex {
    /** Flat array of all index entries across all providers */
    entries: IndexEntry[];
    /** Providers by result type for highlight resolution and data access */
    enemyProvider: EnemySearchProvider;
    npcProvider: NpcSearchProvider;
    zoneProvider: ZoneSearchProvider;
    itemProvider: ItemSearchProvider;
    /** All providers for generic dispatch */
    providers: SearchProvider[];
}

/**
 * Build the search index from preloaded map data.
 * Called once at page load, rebuilt when live entities change.
 */
export function buildSearchIndex(
    enemiesCommon: WorldEnemy[],
    enemiesRare: WorldEnemy[],
    enemiesUnique: WorldEnemy[],
    npcs: WorldNpc[],
    zones: ZoneWorldPosition[],
    itemDroppers: ItemDropperRow[]
): SearchIndex {
    const enemyProvider = new EnemySearchProvider(enemiesCommon, enemiesRare, enemiesUnique);
    const npcProvider = new NpcSearchProvider(npcs);
    const zoneProvider = new ZoneSearchProvider(zones);
    const itemProvider = new ItemSearchProvider(itemDroppers, [
        ...enemiesCommon,
        ...enemiesRare,
        ...enemiesUnique,
        ...npcs
    ]);

    const providers: SearchProvider[] = [
        itemProvider,
        enemyProvider,
        npcProvider,
        zoneProvider
    ];

    const entries: IndexEntry[] = [];
    for (const provider of providers) {
        entries.push(...provider.buildIndex());
    }

    return { entries, enemyProvider, npcProvider, zoneProvider, itemProvider, providers };
}

// =============================================================================
// Search Function
// =============================================================================

/**
 * Search the index for matching entries.
 *
 * Algorithm: tiered matching (prefix → substring → Fuse fuzzy) via
 * searchTiered. Results are split into three tier buckets (by matchRange:
 * prefix at [0,..], substring at [>0,..], fuzzy with null), each bucket is
 * grouped by category, sorted within category, and round-robin interleaved
 * across categories. Tiers are consumed in order (prefix first, then
 * substring, then fuzzy) so exact matches always rank above fuzzy ones.
 */
export function searchMarkers(query: string, index: IndexEntry[], limit = 20): SearchMatch[] {
    const matches = searchTiered(query, index, limit);
    if (matches.length === 0) return [];

    // Split into tier buckets: prefix (range starts at 0), substring
    // (range starts > 0), fuzzy (null range)
    const prefixByCategory = new Map<string, SearchMatch[]>();
    const substringByCategory = new Map<string, SearchMatch[]>();
    const fuzzyByCategory = new Map<string, SearchMatch[]>();

    for (const match of matches) {
        const cat = match.result.type;
        let bucket: Map<string, SearchMatch[]>;
        if (match.matchRange === null) {
            bucket = fuzzyByCategory;
        } else if (match.matchRange[0] === 0) {
            bucket = prefixByCategory;
        } else {
            bucket = substringByCategory;
        }
        const existing = bucket.get(cat);
        if (existing) {
            existing.push(match);
        } else {
            bucket.set(cat, [match]);
        }
    }

    // Sort results within each category for each tier
    sortCategories(prefixByCategory);
    sortCategories(substringByCategory);
    sortCategories(fuzzyByCategory);

    // Round-robin interleave within each priority tier
    const results: SearchMatch[] = [];
    interleave(prefixByCategory, results, limit);
    if (results.length < limit) {
        interleave(substringByCategory, results, limit);
    }
    if (results.length < limit) {
        interleave(fuzzyByCategory, results, limit);
    }
    return results;
}

/**
 * Sort results within each category bucket.
 *
 * Enemies: unique > rare > common, then alphabetically by name.
 * Items / NPCs / Zones: alphabetically by name.
 */
function sortCategories(byCategory: Map<string, SearchMatch[]>): void {
    for (const [cat, results] of byCategory) {
        if (cat === 'enemy') {
            results.sort((a, b) => {
                const ae = a.result as EnemySearchResult;
                const be = b.result as EnemySearchResult;
                return ae.effectiveRarity - be.effectiveRarity || ae.name.localeCompare(be.name);
            });
        } else {
            results.sort((a, b) => sortName(a.result).localeCompare(sortName(b.result)));
        }
    }
}

/** Display name used for alphabetical sort across npc/zone/item results. */
function sortName(result: SearchResult): string {
    return result.type === 'item' ? result.itemName : result.name;
}

/**
 * Round-robin interleave results from multiple categories into the output array.
 */
function interleave(
    byCategory: Map<string, SearchMatch[]>,
    output: SearchMatch[],
    limit: number
): void {
    if (byCategory.size === 0) return;

    // Sort categories by their order for stable output.
    // Items first (primary new use case), then enemies, npcs, zones.
    const categoryOrder: Record<string, number> = {
        item: 0,
        enemy: 1,
        npc: 2,
        zone: 3
    };
    const categories = [...byCategory.entries()].sort(
        ([a], [b]) => (categoryOrder[a] ?? 99) - (categoryOrder[b] ?? 99)
    );

    const taken = new Array(categories.length).fill(0);
    let addedThisRound = true;

    while (output.length < limit && addedThisRound) {
        addedThisRound = false;
        for (let i = 0; i < categories.length; i++) {
            if (output.length >= limit) break;
            const [, results] = categories[i];
            if (taken[i] < results.length) {
                output.push(results[taken[i]]);
                taken[i]++;
                addedThisRound = true;
            }
        }
    }
}

// =============================================================================
// Highlight Resolution
// =============================================================================

/**
 * Resolve a search result to map highlights using the appropriate provider.
 * Supports both sync and async providers.
 */
export async function resolveHighlight(
    result: SearchResult,
    searchIndex: SearchIndex
): Promise<ResolvedHighlight> {
    for (const provider of searchIndex.providers) {
        const resolved = provider.resolveHighlight(result);
        if (resolved instanceof Promise) {
            const awaited = await resolved;
            if (awaited.type !== 'none') return awaited;
        } else {
            if (resolved.type !== 'none') return resolved;
        }
    }
    return { type: 'none' };
}

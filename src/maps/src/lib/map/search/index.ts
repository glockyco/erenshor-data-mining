/**
 * Search index builder and search function.
 *
 * Combines all registered providers into a single flat index and provides
 * prefix-then-substring matching with round-robin interleaving across categories.
 */

import type { WorldEnemy, WorldNpc, ZoneWorldPosition } from '$lib/types/world-map';
import type {
    SearchProvider,
    IndexEntry,
    SearchResult,
    ResolvedHighlight,
    EnemySearchResult,
    NpcSearchResult,
    ZoneSearchResult
} from './types';
import { EnemySearchProvider } from './enemy-provider';
import { NpcSearchProvider } from './npc-provider';
import { ZoneSearchProvider } from './zone-provider';

export type { SearchResult, IndexEntry, ResolvedHighlight } from './types';
export type { EnemySearchResult, NpcSearchResult, ZoneSearchResult } from './types';

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
    zones: ZoneWorldPosition[]
): SearchIndex {
    const enemyProvider = new EnemySearchProvider(enemiesCommon, enemiesRare, enemiesUnique);
    const npcProvider = new NpcSearchProvider(npcs);
    const zoneProvider = new ZoneSearchProvider(zones);

    const providers: SearchProvider[] = [enemyProvider, npcProvider, zoneProvider];

    const entries: IndexEntry[] = [];
    for (const provider of providers) {
        entries.push(...provider.buildIndex());
    }

    return { entries, enemyProvider, npcProvider, zoneProvider, providers };
}

// =============================================================================
// Search Function
// =============================================================================

/**
 * Search the index for matching entries.
 *
 * Algorithm: prefix matches first, then substring matches.
 * Results are interleaved across categories via round-robin to prevent
 * one category from dominating.
 */
export function searchMarkers(query: string, index: IndexEntry[], limit = 20): SearchResult[] {
    const q = query.toLowerCase().trim();
    if (q.length < 2) return [];

    // Split matches into prefix and substring buckets, grouped by category
    const prefixByCategory = new Map<string, SearchResult[]>();
    const substringByCategory = new Map<string, SearchResult[]>();

    for (const entry of index) {
        if (entry.searchText.startsWith(q)) {
            const cat = entry.result.type;
            const bucket = prefixByCategory.get(cat);
            if (bucket) {
                bucket.push(entry.result);
            } else {
                prefixByCategory.set(cat, [entry.result]);
            }
        } else if (entry.searchText.includes(q)) {
            const cat = entry.result.type;
            const bucket = substringByCategory.get(cat);
            if (bucket) {
                bucket.push(entry.result);
            } else {
                substringByCategory.set(cat, [entry.result]);
            }
        }
    }

    // Sort results within each category before interleaving
    sortCategories(prefixByCategory);
    sortCategories(substringByCategory);

    // Round-robin interleave within each priority tier
    const results: SearchResult[] = [];
    interleave(prefixByCategory, results, limit);
    if (results.length < limit) {
        interleave(substringByCategory, results, limit);
    }

    return results;
}

/**
 * Sort results within each category bucket.
 *
 * Enemies: unique > rare > common, then alphabetically by name.
 * NPCs: alphabetically by name.
 * Zones: alphabetically by name.
 */
function sortCategories(byCategory: Map<string, SearchResult[]>): void {
    for (const [cat, results] of byCategory) {
        if (cat === 'enemy') {
            results.sort((a, b) => {
                const ae = a as EnemySearchResult;
                const be = b as EnemySearchResult;
                return ae.effectiveRarity - be.effectiveRarity || ae.name.localeCompare(be.name);
            });
        } else {
            results.sort((a, b) => {
                const na = (a as NpcSearchResult | ZoneSearchResult).name;
                const nb = (b as NpcSearchResult | ZoneSearchResult).name;
                return na.localeCompare(nb);
            });
        }
    }
}

/**
 * Round-robin interleave results from multiple categories into the output array.
 */
function interleave(
    byCategory: Map<string, SearchResult[]>,
    output: SearchResult[],
    limit: number
): void {
    if (byCategory.size === 0) return;

    // Sort categories by their order for stable output
    const categoryOrder: Record<string, number> = { enemy: 0, npc: 1, zone: 2 };
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

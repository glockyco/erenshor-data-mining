/**
 * Search system types.
 *
 * Extensible via SearchProvider interface — each searchable entity type
 * implements a provider that builds index entries and resolves highlights.
 */

import type { Rarity } from '$lib/map-markers';
import type { ZoneWorldPosition } from '$lib/types/world-map';

// =============================================================================
// Search Results (discriminated union — one variant per searchable type)
// =============================================================================

export type EnemySearchResult = {
    type: 'enemy';
    name: string;
    effectiveRarity: Rarity;
    spawnCount: number;
    zoneCount: number;
};

export type NpcSearchResult = {
    type: 'npc';
    name: string;
    isVendor: boolean;
    spawnCount: number;
    zoneCount: number;
};

export type ZoneSearchResult = {
    type: 'zone';
    key: string;
    name: string;
};

export type SearchResult = EnemySearchResult | NpcSearchResult | ZoneSearchResult;
// Future: | ItemSearchResult | QuestSearchResult

// =============================================================================
// Index Entry (flat, for matching)
// =============================================================================

export interface IndexEntry {
    /** Lowercased text to match against */
    searchText: string;
    /** The full result returned on match */
    result: SearchResult;
}

// =============================================================================
// Resolved Highlight (what to show on the map after selection)
// =============================================================================

export type ResolvedHighlight =
    | { type: 'positions'; positions: [number, number][]; stableKeys: string[] }
    | { type: 'zone'; zone: ZoneWorldPosition }
    | { type: 'none' };

// =============================================================================
// Search Provider Interface
// =============================================================================

/**
 * Each searchable entity type implements this interface.
 * Adding a new searchable type (e.g. items) means writing a new provider
 * and registering it — no changes to the search infrastructure.
 */
export interface SearchProvider {
    /** Display label for grouping in the command palette */
    categoryLabel: string;
    /** Sort order for result interleaving (lower = higher priority) */
    categoryOrder: number;
    /** Build index entries from preloaded map data */
    buildIndex(): IndexEntry[];
    /** Resolve a search result to map highlights (may be async for DB-backed types) */
    resolveHighlight(result: SearchResult): ResolvedHighlight | Promise<ResolvedHighlight>;
}

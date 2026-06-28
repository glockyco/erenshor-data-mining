import Fuse from 'fuse.js';
import type { IndexEntry, SearchMatch, SearchResult } from './types';

/**
 * Tiered search: prefix → substring → Fuse fuzzy fallback.
 *
 * Each tier is fully exhausted before the next. Prefix and substring matches
 * carry matchRange for highlighting; fuzzy matches have null matchRange.
 * Within each tier, results keep their array order (already sorted by the
 * provider's buildIndex). The caller handles category interleaving.
 */
export function searchTiered(
    query: string,
    entries: IndexEntry[],
    limit: number
): SearchMatch[] {
    const q = query.toLowerCase().trim();
    if (q.length < 2) return [];

    const prefix: SearchMatch[] = [];
    const substring: SearchMatch[] = [];

    for (const entry of entries) {
        const startIdx = entry.searchText.indexOf(q);
        if (startIdx === 0) {
            prefix.push({
                result: entry.result,
                matchRange: [0, q.length]
            });
        } else if (startIdx > 0) {
            substring.push({
                result: entry.result,
                matchRange: [startIdx, startIdx + q.length]
            });
        }
    }

    // Combine prefix + substring; if we have enough, skip fuzzy
    const exactMatches = [...prefix, ...substring];
    if (exactMatches.length >= limit) {
        return exactMatches.slice(0, limit);
    }

    // Fuse fallback for typos — only if exact matching didn't fill the limit
    const fuse = new Fuse(entries, {
        keys: ['searchText'],
        threshold: 0.5,
        distance: 100,
        minMatchCharLength: 2,
        includeScore: true,
        ignoreLocation: false
    });

    const fuzzyResults = fuse.search(q);
    const exactKeys = new Set(exactMatches.map((m) => getMatchKey(m.result)));
    const fuzzy: SearchMatch[] = [];

    for (const fr of fuzzyResults) {
        if (exactKeys.has(getMatchKey(fr.item.result))) continue;
        fuzzy.push({
            result: fr.item.result,
            matchRange: null
        });
        if (exactMatches.length + fuzzy.length >= limit) break;
    }

    return [...exactMatches, ...fuzzy].slice(0, limit);
}

/** Stable key for deduplication — items use stableKey, others use name. */
function getMatchKey(result: SearchResult): string {
    return result.type === 'item' ? result.itemStableKey : result.name;
}

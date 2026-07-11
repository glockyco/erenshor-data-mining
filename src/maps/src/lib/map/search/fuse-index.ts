import Fuse from 'fuse.js';
import type { IndexEntry, SearchMatch, SearchResult } from './types';

/** Normalize case and punctuation without changing the displayed result text. */
export function normalizeSearchText(value: string): string {
    return value
        .toLocaleLowerCase()
        .replace(/[^\p{L}\p{N}]+/gu, ' ')
        .trim()
        .replace(/\s+/g, ' ');
}

type NormalizedText = {
    text: string;
    sourceStarts: number[];
    sourceEnds: number[];
};

function normalizeWithSource(value: string): NormalizedText {
    const sourceStarts: number[] = [];
    const sourceEnds: number[] = [];
    let text = '';
    let pendingSeparatorStart: number | null = null;

    for (let index = 0; index < value.length; index++) {
        const char = value[index];
        if (/^[\p{L}\p{N}]$/u.test(char)) {
            if (pendingSeparatorStart !== null && text.length > 0) {
                text += ' ';
                sourceStarts.push(pendingSeparatorStart);
                sourceEnds.push(index);
            }
            const lower = char.toLocaleLowerCase();
            text += lower;
            for (let offset = 0; offset < lower.length; offset++) {
                sourceStarts.push(index);
                sourceEnds.push(index + 1);
            }
            pendingSeparatorStart = null;
        } else if (text.length > 0 && pendingSeparatorStart === null) {
            pendingSeparatorStart = index;
        }
    }

    return { text, sourceStarts, sourceEnds };
}

function findMatchRange(candidate: NormalizedText, query: string): [number, number] | null {
    const normalizedStart = candidate.text.indexOf(query);
    if (normalizedStart < 0 || query.length === 0) return null;

    const normalizedEnd = normalizedStart + query.length - 1;
    return [candidate.sourceStarts[normalizedStart], candidate.sourceEnds[normalizedEnd]];
}

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
    const q = normalizeSearchText(query);
    if (q.length < 2) return [];

    const prefix: SearchMatch[] = [];
    const substring: SearchMatch[] = [];

    for (const entry of entries) {
        const normalized = normalizeWithSource(entry.searchText);
        const range = findMatchRange(normalized, q);
        if (!range) continue;

        if (range[0] === 0) {
            prefix.push({
                result: entry.result,
                matchRange: range
            });
        } else {
            substring.push({
                result: entry.result,
                matchRange: range
            });
        }
    }

    // Combine prefix + substring. Fuzzy fallback only fires when there are
    // NO exact matches — if the user typed "island" and got "Island" and
    // "Island Portal", they don't need 18 fuzzy guesses like "grassland"
    // padding out the list. Fuzzy is a rescue for zero-result searches (typos),
    // not a supplement for good matches.
    const exactMatches = [...prefix, ...substring];
    if (exactMatches.length > 0) {
        return exactMatches.slice(0, limit);
    }

    // Fuse fallback for typos — only if exact matching didn't fill the limit
    const normalizedEntries = entries.map((entry) => ({
        ...entry,
        searchText: normalizeSearchText(entry.searchText)
    }));
    const fuzzyResults = new Fuse(normalizedEntries, {
        keys: ['searchText'],
        threshold: 0.5,
        distance: 100,
        minMatchCharLength: 2,
        includeScore: true,
        ignoreLocation: false
    }).search(q);
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

/**
 * Combine the loot tables of characters that share a display name.
 *
 * The live overlay identifies an NPC only by the name the game shows, and names
 * are not identities: 39 map-visible names are worn by more than one character,
 * and for 22 of those the characters drop different things. When the name alone
 * cannot say which one is standing in front of the player, presenting a single
 * variant's table as the answer is a guess dressed as a fact.
 *
 * Combining them is the honest alternative. Every item any candidate can drop is
 * listed, and where candidates disagree on a chance the range is shown rather
 * than one endpoint, so nothing here asserts a number no variant actually has.
 */
import type { CharacterDrop } from '$lib/map-markers';
import type { ItemAcquisition } from '$lib/item-provenance';

export interface AggregatedDrop {
	itemName: string;
	/** Lowest chance among the candidates that drop it. */
	minProbability: number;
	/** Highest chance among the candidates that drop it. */
	maxProbability: number;
	/** How many of the candidates drop it at all. */
	droppedBy: number;
    acquisitions: ItemAcquisition[];
}

/**
 * Merge per-character drop lists into one list, most likely first.
 *
 * Ordering is by highest chance, then by name, matching the single-character
 * list so the two render identically when there is only one candidate.
 */
export function aggregateDropVariants(lists: CharacterDrop[][]): AggregatedDrop[] {
	const merged = new Map<string, AggregatedDrop>();

    for (const list of lists) {
        const seen = new Set<string>();
        for (const drop of list) {
            const key = drop.provenance.item_stable_key;
            const existing = merged.get(key);
            if (!existing) {
                merged.set(key, {
                    itemName: drop.itemName,
                    minProbability: drop.dropProbability,
                    maxProbability: drop.dropProbability,
                    droppedBy: 1,
                    acquisitions: [drop.provenance]
                });
            } else {
                existing.minProbability = Math.min(existing.minProbability, drop.dropProbability);
                existing.maxProbability = Math.max(existing.maxProbability, drop.dropProbability);
                if (!seen.has(key)) existing.droppedBy += 1;
                if (!existing.acquisitions.some((fact) => fact.acquisition_key === drop.provenance.acquisition_key)) {
                    existing.acquisitions.push(drop.provenance);
                }
            }
            seen.add(key);
		}
	}

	return [...merged.values()].sort(
		(a, b) => b.maxProbability - a.maxProbability || a.itemName.localeCompare(b.itemName)
	);
}

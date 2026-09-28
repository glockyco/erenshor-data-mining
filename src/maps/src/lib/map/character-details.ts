/**
 * Per-character popup details, built from data that the world map already
 * prerenders. The map item search and the popups read the same item-source
 * rows, so both show exactly the items that the mapping keeps on the map.
 */
import type { CharacterDrop, ItemSourceRow, VendorItem } from '$lib/map-markers';

/** A map-visible character that wears a display name, with the scenes it is placed in. */
export interface LiveCandidate {
    stableKey: string;
    scenes: string[];
}

export interface CharacterDetails {
    /** Drops by character, most likely first, then by item name. */
    drops: ReadonlyMap<string, CharacterDrop[]>;
    /** Direct and quest-unlocked vendor stock by character, by item name. */
    vendorItems: ReadonlyMap<string, VendorItem[]>;
    /** Every map-visible character by display name. */
    charactersByName: ReadonlyMap<string, readonly LiveCandidate[]>;
}

// Binary order, as SQLite sorts text, so the popups keep their established order.
function compareText(a: string, b: string): number {
    return a < b ? -1 : a > b ? 1 : 0;
}

export function indexCharacterDetails(
    sources: readonly ItemSourceRow[],
    charactersByName: ReadonlyMap<string, readonly LiveCandidate[]>
): CharacterDetails {
    const drops = new Map<string, CharacterDrop[]>();
    const vendorItems = new Map<string, VendorItem[]>();

    for (const source of sources) {
        if (source.kind === 'drop') {
            let list = drops.get(source.characterStableKey);
            if (!list) drops.set(source.characterStableKey, (list = []));
            list.push({ itemName: source.displayName, dropProbability: source.dropProbability });
        } else if (source.kind === 'vendor') {
            let list = vendorItems.get(source.characterStableKey);
            if (!list) vendorItems.set(source.characterStableKey, (list = []));
            list.push({ name: source.displayName, price: source.price });
        }
    }

    for (const list of drops.values()) {
        list.sort((a, b) => b.dropProbability - a.dropProbability || compareText(a.itemName, b.itemName));
    }
    for (const list of vendorItems.values()) {
        list.sort((a, b) => compareText(a.name, b.name));
    }

    return { drops, vendorItems, charactersByName };
}

/**
 * The characters that a live entity can be. The game reports a name and a
 * scene, never a stable key, and a name can belong to several characters with
 * different loot. Prefer the characters placed in the live scene, and fall
 * back to every match when none is placed there, which is what a dynamically
 * spawned character looks like.
 */
export function resolveLiveCandidates(
    charactersByName: ReadonlyMap<string, readonly LiveCandidate[]>,
    name: string,
    scene: string | null
): readonly LiveCandidate[] {
    const matches = charactersByName.get(name) ?? [];
    const placed = scene === null ? [] : matches.filter((candidate) => candidate.scenes.includes(scene));
    return placed.length > 0 ? placed : matches;
}

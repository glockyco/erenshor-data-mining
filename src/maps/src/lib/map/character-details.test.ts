import { beforeAll, describe, expect, it } from 'vitest';

import { getMapsDatabasePath } from '$lib/database-path.server';
import { Repository } from '$lib/database.node';
import type { ItemDropSource } from '$lib/map-markers';
import { indexCharacterDetails, resolveLiveCandidates, type CharacterDetails } from './character-details';

let details: CharacterDetails;

beforeAll(async () => {
    const db = new Repository();
    await db.init(getMapsDatabasePath());
    try {
        details = indexCharacterDetails(await db.getItemSources(), await db.getCharactersByName());
    } finally {
        db.close();
    }
});

function drop(displayName: string, dropProbability: number): ItemDropSource {
    return {
        kind: 'drop',
        itemStableKey: `item:${displayName}`,
        displayName,
        wikiPageName: null,
        iconName: null,
        characterStableKey: 'character:hoarder',
        npcName: 'Hoarder',
        encounterTier: 'enemy',
        dropProbability
    };
}

describe('indexCharacterDetails', () => {
    it('lists every drop of a character, most likely first, then by name', () => {
        // Deliberately more than ten rows: a truncated list is indistinguishable
        // from a complete one, and many characters drop more than ten items.
        const names = Array.from({ length: 12 }, (_, i) => `Item ${String(i + 1).padStart(2, '0')}`);
        const sources = [...names.map((name, i) => drop(name, 60 - i * 5)), drop('Tie A', 25)].reverse();

        const drops = indexCharacterDetails(sources, new Map()).drops.get('character:hoarder');

        expect(drops?.map((row) => row.itemName)).toEqual([
            'Item 01', 'Item 02', 'Item 03', 'Item 04', 'Item 05', 'Item 06', 'Item 07',
            'Item 08', 'Tie A', 'Item 09', 'Item 10', 'Item 11', 'Item 12'
        ]);
    });

    it('lists direct and quest-unlocked vendor stock by item name', () => {
        expect(details.vendorItems.get('character:breena carpenter')).toEqual([
            { name: 'Enchanted Smithy', price: 250 },
            { name: 'Fixture Key', price: 10 }
        ]);
    });

    it('leaves out drops that the mapping hides from the map', () => {
        // The fixture enemy also drops twelve hoard items that are not map-visible.
        expect(details.drops.get('character:fixture enemy')).toEqual([
            { itemName: 'Fixture Drop', dropProbability: 25 }
        ]);
    });
});

describe('resolveLiveCandidates', () => {
    it('prefers the characters placed in the live scene', () => {
        expect(resolveLiveCandidates(details.charactersByName, 'Fixture Enemy', 'StowawayPortal')).toEqual([
            { stableKey: 'character:fixture enemy twin', scenes: ['StowawayPortal'] }
        ]);
    });

    it('falls back to every character with the name when none is placed in the scene', () => {
        // The companion mod reports whatever scene the game is in, which can be
        // one this database does not know. Every candidate must still show.
        for (const scene of ['NotAScene', null]) {
            expect(
                resolveLiveCandidates(details.charactersByName, 'Fixture Enemy', scene).map(
                    (candidate) => candidate.stableKey
                )
            ).toEqual(['character:fixture enemy', 'character:fixture enemy twin']);
        }
    });

    it('returns nothing for a name that no map-visible character wears', () => {
        expect(resolveLiveCandidates(details.charactersByName, 'constructor', 'Stowaway')).toEqual([]);
    });
});

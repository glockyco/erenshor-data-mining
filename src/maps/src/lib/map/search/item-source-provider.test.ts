import { describe, expect, it } from 'vitest';
import type { WorldEnemy } from '$lib/types/world-map';
import { acquisition, condition, location, source } from '$lib/testing/item-provenance';
import { ItemSearchProvider } from './item-source-provider';

const marker: WorldEnemy = {
    stableKey: 'spawn:fixture', category: 'enemy', characters: [], spawnDelay: null, isNightSpawn: false,
    position: { x: 10, y: 30 }, worldPosition: [10, 30], zone: 'Stowaway', zoneName: 'Stowaway Step',
    isEnabled: true, encounterTier: 'enemy', movement: null,
    worldPatrolWaypoints: null, levelMin: 1, levelMax: 1
};

describe('canonical ItemSearchProvider', () => {
    it('retains public source identities through serialization, resolution and highlighting', () => {
        const fact = acquisition({ locations: [location()], conditions: [condition()] });
        const row = source(fact);
        const provider = new ItemSearchProvider(JSON.parse(JSON.stringify([row])), [marker], [], [], []);
        const result = provider.getResult(row.itemStableKey)!;
        expect(provider.getSourcesForItem(row.itemStableKey)).toEqual([{ kind: fact.kind, row,
            presentation: 'source', members: [row], markers: [marker], unlocated: [], entries: [] }]);
        expect(JSON.parse(JSON.stringify(provider.getSourcesForItem(row.itemStableKey)[0].row.provenance))).toEqual(fact);
        expect(result).toMatchObject({ hasKnownSource: true, zoneCount: 1, sourceCounts: { droppers: 1 } });
        expect(provider.resolveHighlight(result)).toEqual({ type: 'positions', positions: [[10, 30]], stableKeys: ['spawn:fixture'] });
    });

    it('lists every unlocated kind rather than dropping location-bound or UI sources', () => {
        const kinds = ['character_drop', 'common_world_item', 'special_world_drop', 'vendor', 'dialog', 'quest_reward',
            'crafting', 'item_drop', 'spell_created', 'mining', 'fishing', 'fishing_bonus', 'auction_house',
            'item_bag', 'starting_class', 'ui_grant', 'item_conversion'];
        const rows = kinds.map((kind) => source(acquisition({ kind, source_key: `source:${kind}`,
            locations: [location({ relation: 'unlocated', marker_stable_key: null })] })));
        const provider = new ItemSearchProvider(rows, [marker], [], [], []);
        expect(provider.getSourcesForItem('item:fixture').map((entry) => entry.row.acquisitionKey)).toEqual(rows.map((row) => row.acquisitionKey));
        expect(provider.getSourcesForItem('item:fixture').every((entry) => entry.unlocated.length === 1)).toBe(true);
        expect(provider.getMarkersForItem('item:fixture')).toEqual([]);
        expect(provider.getResult('item:fixture')?.hasKnownSource).toBe(true);
    });

    it('does not substitute character markers for missing or explicitly unlocated placements', () => {
        const row = source(acquisition({ locations: [location({ marker_stable_key: 'missing' })] }));
        const provider = new ItemSearchProvider([row], [{ ...marker, characters: [{ stableKey: 'character:fixture' }] } as WorldEnemy], [], [], []);
        expect(provider.getMarkersForItem(row.itemStableKey)).toEqual([]);
        expect(provider.getSourcesForItem(row.itemStableKey)[0].unlocated).toEqual(row.provenance.locations);
    });

    it('preserves source, copy and original item keys when aliases share one visible result', () => {
        const rows = ['one', 'two'].map((suffix) => source(acquisition({ source_key: suffix,
            item_stable_key: `item:hidden-${suffix}`, source_copy_stable_key: `copy:${suffix}` }),
        { itemStableKey: 'item:visible' }));
        const provider = new ItemSearchProvider(rows, [], [], [], []);
        expect(provider.getSourcesForItem('item:visible').map((entry) => entry.row)).toEqual(rows);
        expect(provider.getResult('item:hidden-one')).toBeNull();
        expect(provider.getResult('item:visible')?.sourceCounts.droppers).toBe(1);
    });

    it('shows the stored any-water source beside enhanced local fishing sources', () => {
        const global = source(acquisition({ source_key: 'global', kind: 'fishing',
            mechanic: 'fishing_global_replacement', probability_kind: 'exact', probability_min: 1.25, probability_max: 1.25 }));
        const local = source(acquisition({ source_key: 'local', kind: 'fishing', mechanic: 'fishing',
            probability_min: 7.1875, probability_max: 7.1875, locations: [location()],
            conditions: [condition({ predicate: 'time_of_day', value: 'day' })] }));
        const provider = new ItemSearchProvider([global, local], [marker], [], [], []);
        const sources = provider.getSourcesForItem('item:fixture');
        expect(sources.map((entry) => entry.presentation)).toEqual(['any_water', 'source']);
        expect(sources[0].members).toEqual([global]);
        expect(sources[0].markers).toEqual([]);
        expect(sources[1].markers).toEqual([marker]);
        expect(provider.getResult('item:fixture')?.sourceCounts).toMatchObject({ anyWater: 1, fishingSpots: 1 });
    });

    it('keeps distinct stable keys with the same display name and unknown-source items', () => {
        const row = source();
        const other = { ...row, itemStableKey: 'item:other' };
        const provider = new ItemSearchProvider([row], [], [], [], [], [row, other]);
        expect(provider.buildIndex()).toHaveLength(2);
        expect(provider.getResult('item:other')?.hasKnownSource).toBe(false);
        expect(provider.resolveHighlight(provider.getResult('item:other')!)).toEqual({ type: 'none' });
    });

});

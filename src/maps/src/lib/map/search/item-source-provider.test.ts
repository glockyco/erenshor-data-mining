import { describe, expect, it } from 'vitest';
import type { WorldEnemy } from '$lib/types/world-map';
import type { ItemAcquisition } from '$lib/item-provenance';
import { acquisition, condition, disposition, location, source } from '$lib/testing/item-provenance';
import { ItemSearchProvider } from './item-source-provider';

const marker: WorldEnemy = {
    stableKey: 'spawn:fixture', category: 'enemy', characters: [], spawnDelay: null, isNightSpawn: false,
    position: { x: 10, y: 30 }, worldPosition: [10, 30], zone: 'Stowaway', zoneName: 'Stowaway Step',
    popup: '', isEnabled: true, encounterTier: 'enemy', movement: null,
    worldPatrolWaypoints: null, levelMin: 1, levelMax: 1
};

describe('canonical ItemSearchProvider', () => {
    it('retains every dimension and identity through serialization, resolution and highlighting', () => {
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
        const rows = kinds.map((kind) => source(acquisition({ kind, acquisition_key: `acquisition:${kind}`,
            locations: [location({ relation: 'unlocated', coordinate_stable_key: null })] })));
        const provider = new ItemSearchProvider(rows, [marker], [], [], []);
        expect(provider.getSourcesForItem('item:fixture').map((entry) => entry.row.acquisitionKey)).toEqual(rows.map((row) => row.acquisitionKey));
        expect(provider.getSourcesForItem('item:fixture').every((entry) => entry.unlocated.length === 1)).toBe(true);
        expect(provider.getMarkersForItem('item:fixture')).toEqual([]);
        expect(provider.getResult('item:fixture')?.hasKnownSource).toBe(true);
    });

    it('does not substitute character markers for missing or explicitly unlocated placements', () => {
        const row = source(acquisition({ locations: [location({ coordinate_stable_key: 'missing' })] }));
        const provider = new ItemSearchProvider([row], [{ ...marker, characters: [{ stableKey: 'character:fixture' }] } as WorldEnemy], [], [], []);
        expect(provider.getMarkersForItem(row.itemStableKey)).toEqual([]);
        expect(provider.getSourcesForItem(row.itemStableKey)[0].unlocated).toEqual(row.provenance.locations);
    });

    it('preserves variant, copy and original item keys when aliases share one visible result', () => {
        const rows = ['one', 'two'].map((suffix) => source(acquisition({ acquisition_key: suffix,
            item_stable_key: `item:hidden-${suffix}`, variant_key: suffix, source_copy_stable_key: `copy:${suffix}` }),
        { itemStableKey: 'item:visible' }));
        const provider = new ItemSearchProvider(rows, [], [], [], []);
        expect(provider.getSourcesForItem('item:visible').map((entry) => entry.row)).toEqual(rows);
        expect(provider.getResult('item:hidden-one')).toBeNull();
        expect(provider.getResult('item:visible')?.sourceCounts.droppers).toBe(1);
    });

    it.each([null, 0, 1, 7])('keeps guaranteed pool roll count %s through the provider payload without promoting item chance', (count) => {
        const fact = acquisition({ guarantee_scope: 'pool', guaranteed_roll_count: count,
            probability_kind: 'exact', probability_min: 25, probability_max: 25 });
        const row = source(fact);
        const provider = new ItemSearchProvider(JSON.parse(JSON.stringify([row])), [], [], [], []);
        const projected = provider.getSourcesForItem(row.itemStableKey)[0].row.provenance;
        expect(JSON.parse(JSON.stringify(projected))).toEqual(fact);
        expect(projected.guaranteed_roll_count).toBe(count);
        expect(projected.guarantee_scope).toBe('pool');
        expect(projected.probability_min).toBe(25);
        expect(projected.probability_max).toBe(25);
    });

    it('uses matching canonical bonus metadata only and never publishes the native-pool record itself', () => {
        const bonus = acquisition({ acquisition_key: 'bonus', kind: 'fishing_bonus', source_stable_key: null,
            mechanic: 'fishing_global_replacement', probability_kind: 'exact', probability_stage: 'native_pool',
            probability_min: 1.25, probability_max: 1.25 });
        const final = acquisition({ acquisition_key: 'final', kind: 'fishing', probability_kind: 'exact',
            probability_min: 1.25, probability_max: 1.25, conditions: [condition({ predicate: 'time_of_day', value: 'day' })] });
        const first = source(final, { fishingBonus: bonus });
        const second = source({ ...final, acquisition_key: 'second', variant_key: 'NightFishable',
            conditions: [condition({ predicate: 'time_of_day', value: 'night' })] }, { fishingBonus: bonus });
        const provider = new ItemSearchProvider([first, second, source(bonus)], [], [], [], []);
        const summaries = provider.getSourcesForItem(final.item_stable_key);
        expect(summaries).toHaveLength(1);
        expect(summaries[0].presentation).toBe('any_water');
        expect(JSON.parse(JSON.stringify(summaries[0].members))).toEqual([first, second]);
        expect(summaries[0].markers).toEqual([]);
        expect(summaries[0].row.provenance.probability_min).toBe(1.25);
        expect(summaries[0].members.map((member) => member.provenance.conditions[0].value)).toEqual(['day', 'night']);
        const invalidBonuses: Partial<ItemAcquisition>[] = [{ item_stable_key: 'item:other-origin' },
            { probability_stage: 'final_acquisition' }, { mechanic: 'other' }, { probability_kind: 'bounded' },
            { probability_max: 1.2500000001 }];
        for (const invalid of invalidBonuses) {
            const row = source(final, { fishingBonus: { ...bonus, ...invalid } });
            expect(new ItemSearchProvider([row], [], [], [], []).getSourcesForItem(final.item_stable_key)[0].presentation).toBe('source');
        }
        const enhanced = source({ ...final, probability_min: 7.1875, probability_max: 7.1875 }, { fishingBonus: bonus });
        const unchanged = new ItemSearchProvider([enhanced], [], [], [], []).getSourcesForItem(final.item_stable_key)[0];
        expect(unchanged.presentation).toBe('source');
        expect(unchanged.row.provenance.probability_min).toBe(7.1875);
    });

    it('keeps distinct stable keys with the same display name and unknown-source items', () => {
        const row = source();
        const other = { ...row, itemStableKey: 'item:other' };
        const provider = new ItemSearchProvider([row], [], [], [], [], [row, other]);
        expect(provider.buildIndex()).toHaveLength(2);
        expect(provider.getResult('item:other')?.hasKnownSource).toBe(false);
        expect(provider.resolveHighlight(provider.getResult('item:other')!)).toEqual({ type: 'none' });
    });

    it('requires current lifecycle on both the originating variant and its visible representative', () => {
        const fact = acquisition();
        const retired = source(fact, { originatingDisposition: disposition(fact.item_stable_key, { disposition: 'removed' }) });
        const retiredProvider = new ItemSearchProvider([retired], [], [], [], []);
        expect(retiredProvider.getResult(retired.itemStableKey)?.hasKnownSource).toBe(false);
        expect(retiredProvider.getSourcesForItem(retired.itemStableKey)).toEqual([]);
        const alias = source(fact, { itemStableKey: 'item:alias',
            displayDisposition: disposition('item:alias', { disposition: 'unused' }) });
        expect(new ItemSearchProvider([alias], [], [], [], []).getResult('item:alias')?.hasKnownSource).toBe(false);
        const mismatched = source(fact, { originatingDisposition: disposition('item:unrelated') });
        expect(() => new ItemSearchProvider([mismatched], [], [], [], [])).toThrow('lifecycle identity mismatch');
    });
});

import { describe, expect, it } from 'vitest';
import type { CharacterDrop } from '$lib/map-markers';
import { acquisition, condition, location } from '$lib/testing/item-provenance';
import { aggregateDropVariants } from './drop-variants';

function drop(itemName: string, probability: number, copy: string, itemKey = `item:${itemName}`): CharacterDrop {
    return { itemName, dropProbability: probability, provenance: acquisition({ acquisition_key: `${copy}:${itemKey}`,
        item_stable_key: itemKey, source_copy_stable_key: copy, variant_key: copy,
        probability_min: probability, probability_max: probability, conditions: [condition()], locations: [location()] }) };
}

describe('aggregateDropVariants', () => {
    it('retains every full acquisition and reports the candidate probability range', () => {
        const first = drop('Sea Silk', 2, 'copy:one');
        const second = drop('Sea Silk', 9, 'copy:two');
        expect(aggregateDropVariants([[first], [second]])).toEqual([{ itemName: 'Sea Silk',
            minProbability: 2, maxProbability: 9, droppedBy: 2, acquisitions: [first.provenance, second.provenance] }]);
    });
    it('keeps equal display names with different item identities separate', () => {
        const first = drop('Shared Name', 5, 'copy:one', 'item:one');
        const second = drop('Shared Name', 5, 'copy:two', 'item:two');
        const result = aggregateDropVariants([[first], [second]]);
        expect(result).toHaveLength(2);
        expect(result.map((entry) => entry.acquisitions[0].item_stable_key)).toEqual(['item:one', 'item:two']);
    });
    it('counts candidates rather than acquisition routes and deduplicates only acquisition identities', () => {
        const first = drop('Item', 5, 'copy:one');
        const alternate = { ...first, provenance: { ...first.provenance, acquisition_key: 'other-route', variant_key: 'other' } };
        const second = drop('Item', 40, 'copy:two');
        const [result] = aggregateDropVariants([[first, alternate, first], [second]]);
        expect(result.droppedBy).toBe(2);
        expect(result.acquisitions.map((fact) => fact.acquisition_key)).toEqual([first.provenance.acquisition_key, 'other-route', second.provenance.acquisition_key]);
        expect(result.maxProbability).toBe(40);
    });
    it('sorts by highest chance then by name without truncating the list', () => {
        const result = aggregateDropVariants([[drop('Zinc', 5, 'one'), drop('Alum', 5, 'one'), drop('Rare Thing', 1, 'one')], [drop('Zinc', 40, 'two')]]);
        expect(result.map((entry) => entry.itemName)).toEqual(['Zinc', 'Alum', 'Rare Thing']);
    });
});

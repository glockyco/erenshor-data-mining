import type { ItemAcquisition, ItemDisposition, ProvenanceCondition, ProvenanceLocation } from '$lib/item-provenance';
import type { ItemSourceRow } from '$lib/map-markers';

export function acquisition(overrides: Partial<ItemAcquisition> = {}): ItemAcquisition {
    return {
        source_key: 'source:fixture', item_stable_key: 'item:fixture', kind: 'character_drop',
        source_stable_key: 'group:fixture', source_group_key: 'group:fixture', source_copy_stable_key: 'character:fixture',
        mechanic: 'loot', probability_kind: 'bounded', probability_min: 2, probability_max: 8, probability_basis: 'per_kill',
        quantity_min: 1, quantity_max: 3, quantity_kind: 'bounded', expected_quantity: 2,
        guaranteed: false, place_set_key: 'places:fixture',
        conditions: [], locations: [],
        ...overrides
    };
}

export function condition(overrides: Partial<ProvenanceCondition> = {}): ProvenanceCondition {
    return { gate_key: 'gate', gate_index: 0, alternative_index: 0, atom_index: 0, predicate: 'actor_level', reference_stable_key: null,
        reference_slot: null, actor: 'player', value: null, minimum: 10, maximum: 35,
        minimum_inclusive: true, maximum_inclusive: true, phase: 'availability', ...overrides };
}

export function location(overrides: Partial<ProvenanceLocation> = {}): ProvenanceLocation {
    return { place_key: 'location:fixture', relation: 'spawn', scene: 'Stowaway', zone_stable_key: 'zone:stowaway',
        marker_stable_key: 'spawn:fixture', x: 10, z: 30, player_level_min: 10, player_level_max: 35,
        conditions: [condition()], entry_zone_line_keys: ['entrance:fixture'],
        source_copy_stable_key: 'character:fixture', ...overrides };
}
export function disposition(itemKey: string, overrides: Partial<ItemDisposition> = {}): ItemDisposition {
    return { item_stable_key: itemKey, disposition: 'current', reason: null,
        current_pages: [], former_pages: [], ...overrides };
}


export function source(fact: ItemAcquisition = acquisition(), overrides: Partial<ItemSourceRow> = {}): ItemSourceRow {
    return { kind: fact.kind, acquisitionKey: fact.source_key, originatingItemStableKey: fact.item_stable_key,
        itemStableKey: fact.item_stable_key, displayName: 'Fixture', wikiPageName: 'Fixture', iconHash: null,
        provenance: fact, sourceName: 'Fixture Character', sourceWikiPageName: 'Fixture Character',
        characterStableKey: 'character:fixture', price: null, referenceNames: {}, locationSources: {}, ...overrides };
}

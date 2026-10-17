import type { ItemAcquisition, ItemDisposition, ProvenanceCondition, ProvenanceLocation } from '$lib/item-provenance';
import type { ItemSourceRow } from '$lib/map-markers';

export function acquisition(overrides: Partial<ItemAcquisition> = {}): ItemAcquisition {
    return {
        acquisition_key: 'acquisition:fixture', item_stable_key: 'item:fixture', kind: 'character_drop',
        source_stable_key: 'group:fixture', source_group_key: 'group:fixture', source_copy_stable_key: 'character:fixture',
        variant_key: 'variant:fixture', mechanic: 'loot', player_access_state: 'verified_player',
        probability_kind: 'bounded', probability_min: 2, probability_max: 8, probability_basis: 'per_kill',
        probability_stage: 'final_acquisition', quantity_min: 1, quantity_max: 3, quantity_kind: 'bounded',
        expected_quantity: 2, count_distribution: '[0.25,0.5,0.25]', guarantee_scope: 'successful_roll',
        guaranteed_roll_count: null,
        conditions: [], locations: [], evidence: [{ input_relation: 'fixture', input_primary_key: 'row:1' }],
        ...overrides
    };
}

export function condition(overrides: Partial<ProvenanceCondition> = {}): ProvenanceCondition {
    return { gate_key: 'gate', group_index: 0, atom_index: 0, predicate: 'actor_level', reference_stable_key: null,
        reference_slot: null, actor: 'player', value: null, minimum: 10, maximum: 35,
        minimum_inclusive: true, maximum_inclusive: true, scope: 'source', phase: 'availability', ...overrides };
}

export function location(overrides: Partial<ProvenanceLocation> = {}): ProvenanceLocation {
    return { location_key: 'location:fixture', relation: 'spawn', scene: 'Stowaway', zone_stable_key: 'zone:stowaway',
        placement_key: 'character:fixture:spawn:fixture:direct', coordinate_stable_key: 'spawn:fixture',
        x: 10, y: 20, z: 30, gate_scope: 'placement:fixture', player_level_min: 10, player_level_max: 35,
        conditions: [condition({ scope: 'location' })], entry_zone_line_keys: ['entrance:fixture'],
        source_copy_stable_key: 'character:fixture', ...overrides };
}
export function disposition(itemKey: string, overrides: Partial<ItemDisposition> = {}): ItemDisposition {
    return { item_stable_key: itemKey, disposition: 'current', reason: null, evidence: null,
        current_pages: [], former_pages: [], ...overrides };
}


export function source(fact: ItemAcquisition = acquisition(), overrides: Partial<ItemSourceRow> = {}): ItemSourceRow {
    const displayKey = overrides.itemStableKey ?? fact.item_stable_key;
    return { kind: fact.kind, acquisitionKey: fact.acquisition_key, originatingItemStableKey: fact.item_stable_key,
        itemStableKey: fact.item_stable_key, displayName: 'Fixture', wikiPageName: 'Fixture', iconHash: null,
        provenance: fact, sourceName: 'Fixture Character', sourceWikiPageName: 'Fixture Character',
        originatingDisposition: disposition(fact.item_stable_key), displayDisposition: disposition(displayKey),
        characterStableKey: 'character:fixture', price: null, referenceNames: {}, locationSources: {}, fishingBonus: null, ...overrides };
}

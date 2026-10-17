import type { Database, SqlValue } from 'sql.js/dist/sql-wasm.js';
import type { ZoneLineDestinationSnapshot } from './zone-line-destinations';

export type ConditionPhase = 'availability' | 'source_initialization' | 'operation_input' | 'operation_outcome' | 'mechanic_parameter';
export interface ProvenanceCondition {
    gate_key: string;
    group_index: number;
    atom_index: number;
    predicate: string;
    reference_stable_key: string | null;
    reference_slot: string | null;
    actor: string | null;
    value: string | null;
    minimum: number | null;
    maximum: number | null;
    minimum_inclusive: boolean;
    maximum_inclusive: boolean;
    scope: string;
    phase: ConditionPhase;
}

export interface ProvenanceLocation {
    location_key: string;
    relation: string;
    scene: string | null;
    zone_stable_key: string | null;
    placement_key: string | null;
    coordinate_stable_key: string | null;
    x: number | null;
    y: number | null;
    z: number | null;
    gate_scope: string | null;
    player_level_min: number | null;
    player_level_max: number | null;
    conditions: ProvenanceCondition[];
    entry_zone_line_keys: string[];
    source_copy_stable_key: string | null;
}

export interface ItemAcquisition {
    acquisition_key: string;
    item_stable_key: string;
    kind: string;
    source_stable_key: string | null;
    source_group_key: string | null;
    source_copy_stable_key: string | null;
    variant_key: string | null;
    mechanic: string | null;
    player_access_state: 'verified_player' | 'unconfirmed_player' | 'internal_only' | 'non_acquirable';
    probability_kind: 'exact' | 'bounded' | 'unknown' | 'not_applicable';
    probability_min: number | null;
    probability_max: number | null;
    probability_basis: string | null;
    probability_stage: 'native_pool' | 'final_acquisition';
    quantity_min: number | null;
    quantity_max: number | null;
    quantity_kind: string;
    expected_quantity: number | null;
    count_distribution: string | null;
    guarantee_scope: string | null;
    guaranteed_roll_count: number | null;
    conditions: ProvenanceCondition[];
    locations: ProvenanceLocation[];
    evidence: { input_relation: string; input_primary_key: string }[];
}

export interface ItemDisposition {
    item_stable_key: string;
    disposition: 'current' | 'removed' | 'unobtainable' | 'unused';
    reason: string | null;
    evidence: string | null;
    current_pages: string[];
    former_pages: string[];
}

export interface ItemUse {
    use_key: string;
    item_stable_key: string;
    target_stable_key: string | null;
    kind: string;
    variant_key: string | null;
    material_slot: number | null;
    quantity_min: number | null;
    quantity_max: number | null;
    quantity_kind: string;
    mechanic: string | null;
    outcome_key: string | null;
    conditions: ProvenanceCondition[];
    locations: ProvenanceLocation[];
    evidence: { input_relation: string; input_primary_key: string }[];
}

export interface ProvenanceMetadata {
    schema_version: 1;
    game_build_id: string;
    input_digests: Record<string, string>;
}

export interface ItemProvenanceSnapshot {
    metadata: ProvenanceMetadata;
    acquisitions: ItemAcquisition[];
    uses: ItemUse[];
    dispositions: ItemDisposition[];
    items: { stable_key: string; is_map_visible: boolean; wiki_page_name: string | null }[];
    zone_line_destinations: ZoneLineDestinationSnapshot[];
}

type SqlRow = Record<string, SqlValue>;

function query(db: Database, sql: string): SqlRow[] {
    const statement = db.prepare(sql);
    const rows: SqlRow[] = [];
    try {
        while (statement.step()) rows.push(statement.getAsObject());
    } finally {
        statement.free();
    }
    return rows;
}

const CONDITION_COLUMNS = 'owner_key, gate_key, group_index, atom_index, predicate, reference_stable_key, reference_slot, actor, value, minimum, maximum, minimum_inclusive, maximum_inclusive, scope, phase';
const LOCATION_COLUMNS = 'owner_key, location_key, relation, scene, zone_stable_key, placement_key, coordinate_stable_key, x, y, z, gate_scope, player_level_min, player_level_max, conditions, entry_zone_line_keys, source_copy_stable_key';
const PROVENANCE_COLUMNS: Record<string, string> = {
    item_provenance_meta: 'schema_version, game_build_id, input_digests',
    item_acquisitions: 'acquisition_key, item_stable_key, kind, source_stable_key, source_group_key, source_copy_stable_key, variant_key, mechanic, player_access_state, probability_kind, probability_min, probability_max, probability_basis, probability_stage, quantity_min, quantity_max, quantity_kind, expected_quantity, count_distribution, guarantee_scope, guaranteed_roll_count',
    item_uses: 'use_key, item_stable_key, target_stable_key, kind, variant_key, material_slot, quantity_min, quantity_max, quantity_kind, mechanic, outcome_key',
    item_acquisition_conditions: CONDITION_COLUMNS,
    item_use_conditions: CONDITION_COLUMNS,
    item_acquisition_locations: LOCATION_COLUMNS,
    item_use_locations: LOCATION_COLUMNS,
    item_provenance_evidence: 'owner_key, input_relation, input_primary_key',
    item_dispositions: 'item_stable_key, disposition, reason, evidence, current_pages, former_pages'
};

export const ACQUISITION_KINDS: Record<string, true> = { character_drop: true, common_world_item: true,
    special_world_drop: true, vendor: true, dialog: true, quest_reward: true, crafting: true, item_drop: true,
    spell_created: true, mining: true, fishing: true, fishing_bonus: true, auction_house: true, item_bag: true,
    starting_class: true, ui_grant: true, item_conversion: true, internal_equipment: true };
export const USE_KINDS: Record<string, true> = { crafting_material: true, crafting_recipe: true, quest_requirement: true,
    item_drop: true, spell_created: true, item_conversion: true, smithing: true, quality_offering: true, zone_restriction: true };

function validateInterval(row: SqlRow, prefix: 'quantity' | 'probability'): void {
    const kind = row[`${prefix}_kind`];
    const minimum = row[`${prefix}_min`];
    const maximum = row[`${prefix}_max`];
    if (typeof kind !== 'string' || !['exact', 'bounded', 'unknown', 'not_applicable'].includes(kind) ||
        [minimum, maximum].some((value) => value !== null && (typeof value !== 'number' || !Number.isFinite(value) ||
            value < 0 || (prefix === 'probability' && value > 100))) ||
        (typeof minimum === 'number' && typeof maximum === 'number' && minimum > maximum) ||
        ((kind === 'unknown' || kind === 'not_applicable') && (minimum !== null || maximum !== null)) ||
        ((kind === 'exact' || kind === 'bounded') && (minimum === null || maximum === null)) ||
        (kind === 'exact' && minimum !== maximum)) throw new Error(`Invalid canonical ${prefix} interval`);
}

function validateScalarFact(row: SqlRow, family: 'acquisition' | 'use', identity: string): void {
    if (Object.keys(row).sort().join(',') !== PROVENANCE_COLUMNS[`item_${family}s`].split(', ').sort().join(',') ||
        [identity, 'item_stable_key', 'kind'].some((key) => typeof row[key] !== 'string' || !row[key]) ||
        !Object.hasOwn(family === 'acquisition' ? ACQUISITION_KINDS : USE_KINDS, row.kind as string)) {
        throw new Error(`Invalid canonical ${family} fields`);
    }
    validateInterval(row, 'quantity');
    const textFields = family === 'acquisition'
        ? ['source_stable_key', 'source_group_key', 'source_copy_stable_key', 'variant_key', 'mechanic', 'probability_basis', 'count_distribution', 'guarantee_scope']
        : ['target_stable_key', 'variant_key', 'mechanic', 'outcome_key'];
    if (textFields.some((key) => row[key] !== null && (typeof row[key] !== 'string' || !row[key]))) {
        throw new Error(`Invalid canonical ${family} text`);
    }
    if (family === 'use') {
        if (row.material_slot !== null && !Number.isInteger(row.material_slot)) throw new Error('Invalid canonical material slot');
        return;
    }
    validateInterval(row, 'probability');
    if (!['verified_player', 'unconfirmed_player', 'internal_only', 'non_acquirable'].includes(row.player_access_state as string) ||
        !['native_pool', 'final_acquisition'].includes(row.probability_stage as string) ||
        (row.probability_basis !== null && !['per_kill', 'per_use', 'per_node', 'per_successful_catch', 'per_listing_opportunity', 'not_applicable'].includes(row.probability_basis as string)) ||
        (row.guarantee_scope !== null && !['pool', 'pool_roll', 'item', 'successful_roll', 'successful_ui_transfer'].includes(row.guarantee_scope as string)) ||
        (row.expected_quantity !== null && (typeof row.expected_quantity !== 'number' || !Number.isFinite(row.expected_quantity) || row.expected_quantity < 0)) ||
        (row.guaranteed_roll_count !== null && (typeof row.guaranteed_roll_count !== 'number' ||
            !Number.isInteger(row.guaranteed_roll_count) || row.guaranteed_roll_count < 0))) {
        throw new Error(`Invalid canonical acquisition semantics: ${row.acquisition_key}`);
    }
    if (typeof row.count_distribution === 'string') {
        const distribution: unknown = JSON.parse(row.count_distribution);
        const chances: unknown[] = Array.isArray(distribution) ? distribution :
            distribution && typeof distribution === 'object' ? Object.values(distribution) : [];
        if (!chances.length || chances.some((chance) => typeof chance !== 'number' || !Number.isFinite(chance) || chance < 0 || chance > 1) ||
            chances.reduce<number>((sum, chance) => sum + (chance as number), 0) > 1 + 1e-9 ||
            (!Array.isArray(distribution) && distribution && typeof distribution === 'object' &&
                Object.keys(distribution).some((key) => !/^[0-9]+$/.test(key)))) {
            throw new Error(`Invalid canonical count distribution: ${row.acquisition_key}`);
        }
    }
}

const CONDITION_PREDICATES: Record<string, true> = { never: true, quest_done: true, quest_not_done: true,
    room_furnished: true, key_held: true, item_held: true, encounter_won: true, item_not_owned: true,
    actor_level: true, actor_class: true, account_state: true, time_of_day: true, zone_use: true, quality: true,
    formula_operand: true, route: true, source_replenishment: true };
const REFERENCE_PREDICATES: Record<string, true> = { quest_done: true, quest_not_done: true, room_furnished: true,
    key_held: true, item_held: true, item_not_owned: true, encounter_won: true, actor_class: true, account_state: true, zone_use: true };
const CONDITION_KEYS = CONDITION_COLUMNS.split(', ').filter((key) => key !== 'owner_key').sort().join(',');
const LOCATION_KEYS = LOCATION_COLUMNS.split(', ').filter((key) => key !== 'owner_key').sort().join(',');

function decodeConditions(value: unknown): ProvenanceCondition[] {
    if (!Array.isArray(value)) throw new Error('Canonical conditions must be an array');
    const identities = new Set<string>();
    return value.map((value: unknown) => {
        if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error('Invalid canonical condition');
        const atom = value as Record<string, unknown>;
        if (Object.keys(atom).sort().join(',') !== CONDITION_KEYS ||
            ['gate_key', 'predicate', 'scope'].some((key) => typeof atom[key] !== 'string' || !atom[key]) ||
            typeof atom.predicate !== 'string' || !Object.hasOwn(CONDITION_PREDICATES, atom.predicate) ||
            !Number.isInteger(atom.group_index) || !Number.isInteger(atom.atom_index) ||
            ['reference_stable_key', 'reference_slot', 'actor', 'value'].some((key) =>
                atom[key] !== null && (typeof atom[key] !== 'string' || !atom[key])) ||
            ['minimum', 'maximum'].some((key) => atom[key] !== null && (typeof atom[key] !== 'number' || !Number.isFinite(atom[key]))) ||
            typeof atom.minimum_inclusive !== 'boolean' || typeof atom.maximum_inclusive !== 'boolean' ||
            !['availability', 'source_initialization', 'operation_input', 'operation_outcome', 'mechanic_parameter'].includes(atom.phase as string) ||
            (atom.actor !== null && !['player', 'sim', 'sim_player', 'enemy', 'account'].includes(atom.actor as string)) ||
            (atom.predicate === 'time_of_day' && !['day', 'night'].includes(atom.value as string)) ||
            (atom.predicate === 'account_state' && (atom.reference_stable_key !== 'account_state:reliquary_claimed' ||
                atom.actor !== 'account' || !['true', 'false'].includes(atom.value as string) ||
                !['availability', 'operation_outcome'].includes(atom.phase as string))) ||
            (Object.hasOwn(REFERENCE_PREDICATES, atom.predicate) && atom.reference_stable_key === null) ||
            (atom.predicate === 'actor_level' && (atom.actor === null || (atom.minimum === null && atom.maximum === null))) ||
            (['route', 'source_replenishment', 'formula_operand'].includes(atom.predicate) && atom.value === null)) {
            throw new Error(`Invalid canonical condition: ${atom.gate_key}`);
        }
        const identity = JSON.stringify([atom.scope, atom.gate_key, atom.phase, atom.group_index, atom.atom_index]);
        if (identities.has(identity)) throw new Error(`Duplicate condition identity: ${identity}`);
        identities.add(identity);
        return { ...atom } as unknown as ProvenanceCondition;
    });
}

function decodeLocation(location: Record<string, unknown>): ProvenanceLocation {
    if (Object.keys(location).sort().join(',') !== LOCATION_KEYS ||
        typeof location.location_key !== 'string' || !location.location_key ||
        !['fixed', 'spawn', 'possible_treasure', 'unlocated', 'mechanic_zone', 'interaction'].includes(location.relation as string) ||
        ['scene', 'zone_stable_key', 'placement_key', 'coordinate_stable_key', 'gate_scope', 'source_copy_stable_key']
            .some((key) => location[key] !== null && (typeof location[key] !== 'string' || !location[key])) ||
        ['x', 'y', 'z'].some((key) => location[key] !== null && (typeof location[key] !== 'number' || !Number.isFinite(location[key]))) ||
        (['x', 'y', 'z'].some((key) => location[key] === null) && ['x', 'y', 'z'].some((key) => location[key] !== null)) ||
        ['player_level_min', 'player_level_max'].some((key) => location[key] !== null && !Number.isInteger(location[key])) ||
        (typeof location.player_level_min === 'number' && typeof location.player_level_max === 'number' &&
            location.player_level_min > location.player_level_max) ||
        !Array.isArray(location.entry_zone_line_keys) ||
        location.entry_zone_line_keys.some((key) => typeof key !== 'string' || !key) ||
        new Set(location.entry_zone_line_keys).size !== location.entry_zone_line_keys.length) {
        throw new Error(`Invalid canonical location: ${location.location_key}`);
    }
    return { ...location, conditions: decodeConditions(location.conditions) } as unknown as ProvenanceLocation;
}

export function readProvenanceMetadata(db: Database): ProvenanceMetadata {
    const rows = query(db, 'SELECT * FROM item_provenance_meta');
    if (rows.length !== 1 || rows[0].schema_version !== 1) {
        throw new Error('Map requires item provenance schema version 1. Regenerate the clean database.');
    }
    const row = rows[0];
    if (Object.keys(row).sort().join(',') !== 'game_build_id,input_digests,schema_version' ||
        typeof row.game_build_id !== 'string' || !row.game_build_id ||
        typeof row.input_digests !== 'string') throw new Error('Invalid canonical provenance metadata');
    const digests: unknown = JSON.parse(row.input_digests);
    if (!digests || typeof digests !== 'object' || Array.isArray(digests) ||
        Object.entries(digests).some(([key, value]) => !key || typeof value !== 'string' || !/^[0-9a-f]{64}$/.test(value))) {
        throw new Error('Invalid canonical provenance input digests');
    }
    return { schema_version: 1, game_build_id: row.game_build_id, input_digests: digests as Record<string, string> };
}

export function assertProvenanceSchema(db: Database): void {
    readProvenanceMetadata(db);
    for (const [table, columns] of Object.entries(PROVENANCE_COLUMNS)) {
        db.prepare(`SELECT ${columns} FROM ${table} LIMIT 0`).free();
    }
}

function readFacts<T extends ItemAcquisition | ItemUse>(
    db: Database, family: 'acquisition' | 'use', identity: 'acquisition_key' | 'use_key'
): T[] {
    assertProvenanceSchema(db);
    const byKey = new Map<string, T>();
    for (const row of query(db, `SELECT * FROM item_${family}s ORDER BY ${identity}`)) {
        validateScalarFact(row, family, identity);
        const fact = { ...row, conditions: [], locations: [], evidence: [] } as unknown as T;
        byKey.set(row[identity] as string, fact);
    }
    for (const row of query(db, `SELECT * FROM item_${family}_conditions ORDER BY owner_key, gate_key, group_index, atom_index, scope, phase`)) {
        const { owner_key, ...atom } = row;
        const fact = byKey.get(owner_key as string);
        if (!fact) throw new Error(`Orphan ${family} condition: ${owner_key}`);
        if (![0, 1].includes(atom.minimum_inclusive as number) || ![0, 1].includes(atom.maximum_inclusive as number)) {
            throw new Error(`Invalid condition inclusivity: ${owner_key}`);
        }
        fact.conditions.push(...decodeConditions([{ ...atom, minimum_inclusive: atom.minimum_inclusive === 1,
            maximum_inclusive: atom.maximum_inclusive === 1 }]));
    }
    for (const row of query(db, `SELECT * FROM item_${family}_locations ORDER BY owner_key, location_key`)) {
        const { owner_key, ...location } = row;
        const fact = byKey.get(owner_key as string);
        if (!fact) throw new Error(`Orphan ${family} location: ${owner_key}`);
        if (typeof location.conditions !== 'string' || typeof location.entry_zone_line_keys !== 'string') {
            throw new Error(`Invalid ${family} location JSON: ${location.location_key}`);
        }
        fact.locations.push(decodeLocation({ ...location, conditions: JSON.parse(location.conditions),
            entry_zone_line_keys: JSON.parse(location.entry_zone_line_keys) }));
    }
    for (const row of query(db, 'SELECT * FROM item_provenance_evidence ORDER BY owner_key, input_relation, input_primary_key')) {
        if (Object.keys(row).sort().join(',') !== 'input_primary_key,input_relation,owner_key' ||
            typeof row.owner_key !== 'string' || !row.owner_key ||
            typeof row.input_relation !== 'string' || !row.input_relation ||
            typeof row.input_primary_key !== 'string' || !row.input_primary_key) {
            throw new Error('Invalid canonical evidence');
        }
        const fact = byKey.get(row.owner_key as string);
        if (fact) fact.evidence.push({ input_relation: row.input_relation as string,
            input_primary_key: row.input_primary_key as string });
    }
    return [...byKey.values()];
}

export function readItemAcquisitions(db: Database): ItemAcquisition[] {
    return readFacts<ItemAcquisition>(db, 'acquisition', 'acquisition_key');
}

export function readItemUses(db: Database): ItemUse[] {
    return readFacts<ItemUse>(db, 'use', 'use_key');
}

export function readItemDispositions(db: Database): ItemDisposition[] {
    assertProvenanceSchema(db);
    const records = new Map<string, ItemDisposition>();
    for (const row of query(db, 'SELECT * FROM item_dispositions ORDER BY item_stable_key')) {
        if (Object.keys(row).sort().join(',') !== PROVENANCE_COLUMNS.item_dispositions.split(', ').sort().join(',') ||
            typeof row.item_stable_key !== 'string' || typeof row.disposition !== 'string' ||
            !['current', 'removed', 'unobtainable', 'unused'].includes(row.disposition) ||
            !(row.reason === null || typeof row.reason === 'string') ||
            !(row.evidence === null || typeof row.evidence === 'string') ||
            typeof row.current_pages !== 'string' || typeof row.former_pages !== 'string') {
            throw new Error('Invalid canonical item disposition');
        }
        const current: unknown = JSON.parse(row.current_pages);
        const former: unknown = JSON.parse(row.former_pages);
        if (!Array.isArray(current) || current.some((page) => typeof page !== 'string') ||
            !Array.isArray(former) || former.some((page) => typeof page !== 'string')) {
            throw new Error(`Invalid disposition pages: ${row.item_stable_key}`);
        }
        if (records.has(row.item_stable_key)) throw new Error(`Duplicate item disposition: ${row.item_stable_key}`);
        records.set(row.item_stable_key, { ...row, current_pages: current, former_pages: former } as ItemDisposition);
    }
    for (const item of query(db, 'SELECT stable_key FROM items')) {
        if (!records.has(item.stable_key as string)) throw new Error(`Missing canonical item disposition: ${item.stable_key}`);
    }
    return [...records.values()];
}

function atomsSatisfiable(atoms: ProvenanceCondition[]): boolean {
    const positive = new Set<string>();
    const negative = new Set<string>();
    const choices = new Map<string, string>();
    let accountStates: Map<string, string> | null = null;
    const numeric = new Map<string, { low: number; high: number; lowInclusive: boolean; highInclusive: boolean }>();
    for (const atom of atoms) {
        const context = atom.phase === 'availability' || atom.phase === 'operation_input' ? 'current' : atom.phase;
        if (atom.predicate === 'never') return false;
        if (atom.predicate === 'account_state' && atom.value !== null) {
            accountStates ??= new Map<string, string>();
            const key = JSON.stringify([context, atom.reference_stable_key, atom.actor]);
            if (accountStates.has(key) && accountStates.get(key) !== atom.value) return false;
            accountStates.set(key, atom.value);
        }
        if (['quest_done', 'quest_not_done', 'item_held', 'item_not_owned'].includes(atom.predicate)) {
            const family = atom.predicate.startsWith('quest_') ? 'quest' : 'item';
            const key = JSON.stringify([context, family, atom.actor, atom.reference_stable_key, family === 'item' ? atom.value : null]);
            if (atom.predicate === 'quest_not_done' || atom.predicate === 'item_not_owned') negative.add(key);
            else positive.add(key);
            if (positive.has(key) && negative.has(key)) return false;
        }
        if (atom.predicate === 'time_of_day' || atom.predicate === 'actor_class') {
            const choice = atom.predicate === 'time_of_day' ? atom.value : atom.reference_stable_key;
            if (choice !== null) {
                const key = JSON.stringify([context, atom.predicate, atom.actor]);
                if (choices.has(key) && choices.get(key) !== choice) return false;
                choices.set(key, choice);
            }
        }
        if (atom.predicate === 'actor_level' || atom.predicate === 'quality' || atom.minimum !== null || atom.maximum !== null) {
            const key = atom.predicate === 'actor_level' ? JSON.stringify([context, 'actor_state', atom.predicate, atom.actor, null, null]) :
                JSON.stringify([context, atom.scope, atom.predicate, atom.actor, atom.reference_stable_key, atom.value]);
            const bounds = numeric.get(key) ?? { low: -Infinity, high: Infinity, lowInclusive: true, highInclusive: true };
            if (atom.minimum !== null && atom.minimum >= bounds.low) {
                bounds.lowInclusive = atom.minimum === bounds.low ? bounds.lowInclusive && atom.minimum_inclusive : atom.minimum_inclusive;
                bounds.low = atom.minimum;
            }
            if (atom.maximum !== null && atom.maximum <= bounds.high) {
                bounds.highInclusive = atom.maximum === bounds.high ? bounds.highInclusive && atom.maximum_inclusive : atom.maximum_inclusive;
                bounds.high = atom.maximum;
            }
            if (bounds.low > bounds.high || (bounds.low === bounds.high && !(bounds.lowInclusive && bounds.highInclusive))) return false;
            numeric.set(key, bounds);
        }
    }
    return true;
}

export function conditionsSatisfiable(conditions: ProvenanceCondition[]): boolean {
    const gates = new Map<string, Map<number, ProvenanceCondition[]>>();
    for (const atom of conditions) {
        const key = JSON.stringify([atom.scope, atom.gate_key, atom.phase]);
        let groups = gates.get(key);
        if (!groups) gates.set(key, (groups = new Map()));
        const atoms = groups.get(atom.group_index) ?? [];
        atoms.push(atom);
        groups.set(atom.group_index, atoms);
    }
    const alternatives = [...gates.values()].map((groups) => [...groups.values()]);
    const selected: ProvenanceCondition[] = [];
    function compatible(index: number): boolean {
        if (index === alternatives.length) return true;
        for (const group of alternatives[index]) {
            const previousLength = selected.length;
            selected.push(...group);
            const possible = atomsSatisfiable(selected) && compatible(index + 1);
            selected.length = previousLength;
            if (possible) return true;
        }
        return false;
    }
    return compatible(0);
}

/** Keep this public-source policy aligned with the canonical domain's is_actionable_acquisition. */
export function isActionableAcquisition(fact: ItemAcquisition): boolean {
    return fact.player_access_state === 'verified_player' && fact.probability_stage === 'final_acquisition' &&
        !(fact.probability_max !== null && fact.probability_max <= 0) && conditionsSatisfiable(fact.conditions) &&
        (!fact.locations.length || fact.locations.some((location) => conditionsSatisfiable([...fact.conditions, ...location.conditions])));
}

function words(value: string): string {
    return value.replaceAll('_', ' ');
}

export function conditionText(condition: ProvenanceCondition, names: Record<string, string> = {}): string {
    const reference = condition.reference_stable_key;
    const subject = reference ? (names[reference] ?? reference.replace(/^[^:]+:/, '')) : '';
    const bounds = [condition.minimum === null ? '' : `${condition.minimum_inclusive ? 'at least' : 'above'} ${condition.minimum}`,
        condition.maximum === null ? '' : `${condition.maximum_inclusive ? 'at most' : 'below'} ${condition.maximum}`].filter(Boolean).join(' and ');
    switch (condition.predicate) {
        case 'quest_done': return `Complete ${subject}`;
        case 'quest_not_done': return `Do not complete ${subject}`;
        case 'item_held':
        case 'key_held': return `Carry ${condition.minimum ?? 1} ${subject}`;
        case 'item_not_owned': return `Do not already own ${subject}`;
        case 'room_furnished': return `Place ${subject}${condition.reference_slot ? ` in ${condition.reference_slot}` : ' in the room'}`;
        case 'encounter_won': return `Defeat ${subject}`;
        case 'actor_class': return `${condition.actor === 'sim' || condition.actor === 'sim_player' ? 'Simulated player class' : 'Play as'} ${subject}`;
        case 'account_state': {
            const name = reference === 'account_state:reliquary_claimed' ? (names[reference] ?? 'your Reliquary') : subject;
            return `${condition.value === 'false' ? 'Before' : 'After'} claiming ${name}`;
        }
        case 'never': return 'Not obtainable through this route';
        case 'time_of_day': return `Fish ${condition.value === 'day' ? 'during the day' : condition.value === 'night' ? 'at night' : `during ${condition.value}`}`;
        case 'actor_level': return `${condition.actor === 'enemy' ? 'Enemy' : condition.actor === 'sim' || condition.actor === 'sim_player' ? 'Simulated player' : 'Player'} level ${bounds}`;
        case 'zone_use': return `Use in ${subject}`;
        case 'quality': return `Quality ${condition.value ?? subject}`;
        default: return [condition.actor ? words(condition.actor) : '', words(condition.predicate), subject,
            condition.value, bounds].filter(Boolean).join(' ');
    }
}

export function publicConditionOmissionReason(condition: ProvenanceCondition): string | null {
    if (condition.phase === 'mechanic_parameter') return 'static_mechanic_parameter';
    if (condition.predicate === 'formula_operand') return 'formula_operand';
    if (condition.predicate === 'source_replenishment') return 'source_replenishment_mechanic';
    if (condition.predicate === 'account_state' && condition.phase === 'operation_outcome') return 'account_state_outcome';
    if (condition.phase === 'source_initialization' &&
        ['item_not_owned', 'item_held', 'key_held'].includes(condition.predicate)) return 'historical_ownership_selection';
    return null;
}

export interface PublicConditionGate {
    alternatives: ProvenanceCondition[][];
}

/** A private-only alternative must not turn another alternative into a mandatory public prerequisite. */
export function publicConditionGates(conditions: ProvenanceCondition[]): PublicConditionGate[] {
    const gates = new Map<string, Map<number, ProvenanceCondition[]>>();
    for (const condition of conditions) {
        const key = JSON.stringify([condition.scope, condition.gate_key, condition.phase]);
        let groups = gates.get(key);
        if (!groups) gates.set(key, (groups = new Map()));
        const atoms = groups.get(condition.group_index) ?? [];
        atoms.push(condition);
        groups.set(condition.group_index, atoms);
    }
    const projected: PublicConditionGate[] = [];
    for (const groups of gates.values()) {
        const alternatives: ProvenanceCondition[][] = [];
        for (const atoms of groups.values()) {
            const visible = atoms.filter((atom) => !publicConditionOmissionReason(atom));
            if (!visible.length) {
                alternatives.length = 0;
                break;
            }
            alternatives.push(visible);
        }
        if (alternatives.length) projected.push({ alternatives });
    }
    return projected;
}

/** Groups are alternatives within one gate. Separate gates must all be satisfied. */
export function conditionLines(conditions: ProvenanceCondition[], names: Record<string, string> = {}): string[] {
    return publicConditionGates(conditions).map((gate) => gate.alternatives.map((atoms) => atoms
        .sort((a, b) => a.atom_index - b.atom_index).map((atom) => conditionText(atom, names)).join(' and ')).join(' or '));
}

export function probabilityText(fact: ItemAcquisition): string {
    if (fact.probability_kind === 'not_applicable') return '';
    const value = fact.probability_kind === 'unknown' ? 'Chance unknown' :
        fact.probability_min === fact.probability_max ? `${fact.probability_min}%` :
            `${fact.probability_min ?? '?'}% to ${fact.probability_max ?? '?'}%`;
    const basis: Record<string, string> = { per_kill: 'per kill', per_successful_catch: 'per successful catch',
        per_node: 'per node', per_use: 'per use', per_listing_opportunity: 'per listing opportunity' };
    return `${value}${fact.probability_stage === 'native_pool' ? ' within pool' : fact.probability_basis && basis[fact.probability_basis] ? ` ${basis[fact.probability_basis]}` : ''}`;
}

export function quantityText(fact: ItemAcquisition): string {
    const count = fact.quantity_min === fact.quantity_max ? `${fact.quantity_min ?? '?'}` :
        `${fact.quantity_min ?? '?'} to ${fact.quantity_max ?? '?'}`;
    const parts = [fact.quantity_kind === 'unknown' ? '' : `Quantity ${count}`,
        fact.expected_quantity === null ? '' : `Average ${fact.expected_quantity}${fact.probability_basis === 'per_kill' ? ' per kill' : ''}`,
        fact.guarantee_scope === 'item' ? 'Guaranteed' : ''].filter(Boolean);
    return parts.length ? parts.join(', ') : 'Quantity unknown';
}

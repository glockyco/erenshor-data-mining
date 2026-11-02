import type { Database, SqlValue } from 'sql.js/dist/sql-wasm.js';
import type { ZoneLineDestinationSnapshot } from './zone-line-destinations';

export type ConditionPhase = 'availability' | 'source_initialization' | 'operation_input' | 'operation_outcome' | 'mechanic_parameter';
export interface ProvenanceCondition {
    gate_index: number;
    alternative_index: number;
    atom_index: number;
    gate_key: string;
    predicate: string;
    reference_stable_key: string | null;
    reference_slot: string | null;
    actor: string | null;
    value: string | null;
    minimum: number | null;
    maximum: number | null;
    minimum_inclusive: boolean;
    maximum_inclusive: boolean;
    phase: ConditionPhase;
}
export interface ProvenanceLocation {
    place_key: string;
    relation: string;
    scene: string | null;
    zone_stable_key: string | null;
    marker_stable_key: string | null;
    x: number | null;
    z: number | null;
    player_level_min: number | null;
    player_level_max: number | null;
    source_copy_stable_key: string | null;
    entry_zone_line_keys: string[];
    conditions: ProvenanceCondition[];
}
/** Only source fields used by map presentation are sent to the browser. */
export interface ItemAcquisition {
    source_key: string;
    item_stable_key: string;
    kind: string;
    source_stable_key: string | null;
    source_group_key: string | null;
    source_copy_stable_key: string | null;
    mechanic: string | null;
    probability_kind: 'exact' | 'bounded' | 'unknown' | 'not_applicable';
    probability_min: number | null;
    probability_max: number | null;
    probability_basis: string | null;
    quantity_kind: string;
    quantity_min: number | null;
    quantity_max: number | null;
    expected_quantity: number | null;
    guaranteed: boolean;
    place_set_key: string | null;
    conditions: ProvenanceCondition[];
    locations: ProvenanceLocation[];
}
export interface ItemDisposition {
    item_stable_key: string;
    disposition: 'current' | 'removed' | 'unobtainable' | 'unused';
    reason: string | null;
    current_pages: string[];
    former_pages: string[];
}
export const PROVENANCE_SCHEMA_VERSION = 3;
export interface ProvenanceMetadata {
    schema_version: typeof PROVENANCE_SCHEMA_VERSION;
    game_build_id: string;
    input_digests: Record<string, string>;
}
export interface ItemProvenanceSnapshot {
    metadata: ProvenanceMetadata;
    acquisitions: ItemAcquisition[];
    dispositions: ItemDisposition[];
    items: { stable_key: string; is_map_visible: boolean; wiki_page_name: string | null }[];
    zone_line_destinations: ZoneLineDestinationSnapshot[];
}
type SqlRow = Record<string, SqlValue>;
function query(db: Database, sql: string): SqlRow[] {
    const statement = db.prepare(sql);
    const rows: SqlRow[] = [];
    try { while (statement.step()) rows.push(statement.getAsObject()); }
    finally { statement.free(); }
    return rows;
}
const CONDITION_COLUMNS = 'gate_index, alternative_index, atom_index, gate_key, predicate, reference_stable_key, reference_slot, actor, value, minimum, maximum, minimum_inclusive, maximum_inclusive, phase';
const SOURCE_COLUMNS = 'source_key, item_stable_key, kind, source_stable_key, source_group_key, source_copy_stable_key, mechanic, probability_kind, probability_min, probability_max, probability_basis, quantity_kind, quantity_min, quantity_max, expected_quantity, guaranteed, place_set_key';
const PLACE_COLUMNS = 'place_key, relation, scene, zone_stable_key, marker_stable_key, x, z, player_level_min, player_level_max, source_copy_stable_key, entry_zone_line_keys';
export function readProvenanceMetadata(db: Database): ProvenanceMetadata {
    const rows = query(db, 'SELECT * FROM item_provenance_meta');
    if (rows.length !== 1 || rows[0].schema_version !== PROVENANCE_SCHEMA_VERSION) {
        throw new Error(`Map requires item provenance schema version ${PROVENANCE_SCHEMA_VERSION}. Regenerate the clean database.`);
    }
    const row = rows[0];
    if (typeof row.game_build_id !== 'string' || !row.game_build_id || typeof row.input_digests !== 'string') {
        throw new Error('Invalid canonical provenance metadata');
    }
    return { schema_version: PROVENANCE_SCHEMA_VERSION, game_build_id: row.game_build_id, input_digests: JSON.parse(row.input_digests) };
}
export function assertProvenanceSchema(db: Database): void {
    readProvenanceMetadata(db);
    for (const [table, columns] of Object.entries({
        item_sources: SOURCE_COLUMNS, item_conditions: `owner_key, ${CONDITION_COLUMNS}`,
        item_places: `place_set_key, ${PLACE_COLUMNS}`, item_place_conditions: `place_set_key, place_key, ${CONDITION_COLUMNS}`,
        item_statuses: 'item_stable_key, disposition, reason, current_pages, former_pages'
    })) db.prepare(`SELECT ${columns} FROM ${table} LIMIT 0`).free();
}
export function readItemSources(db: Database): ItemAcquisition[] {
    assertProvenanceSchema(db);
    const conditions = new Map<string, ProvenanceCondition[]>();
    for (const row of query(db, `SELECT owner_key, ${CONDITION_COLUMNS} FROM item_conditions ORDER BY owner_key, gate_index, alternative_index, atom_index`)) {
        const { owner_key, ...atom } = row;
        const atoms = conditions.get(owner_key as string) ?? [];
        atoms.push({ ...atom, minimum_inclusive: atom.minimum_inclusive === 1, maximum_inclusive: atom.maximum_inclusive === 1 } as unknown as ProvenanceCondition);
        conditions.set(owner_key as string, atoms);
    }
    const placeConditions = new Map<string, ProvenanceCondition[]>();
    for (const row of query(db, `SELECT place_set_key, place_key, ${CONDITION_COLUMNS} FROM item_place_conditions ORDER BY place_set_key, place_key, gate_index, alternative_index, atom_index`)) {
        const { place_set_key, place_key, ...atom } = row;
        const key = JSON.stringify([place_set_key, place_key]);
        const atoms = placeConditions.get(key) ?? [];
        atoms.push({ ...atom, minimum_inclusive: atom.minimum_inclusive === 1, maximum_inclusive: atom.maximum_inclusive === 1 } as unknown as ProvenanceCondition);
        placeConditions.set(key, atoms);
    }
    // Svelte's page serializer stores each shared place set once and references it from sources.
    const places = new Map<string, ProvenanceLocation[]>();
    for (const row of query(db, `SELECT place_set_key, ${PLACE_COLUMNS} FROM item_places ORDER BY place_set_key, place_key`)) {
        const { place_set_key, entry_zone_line_keys, ...place } = row;
        const locations = places.get(place_set_key as string) ?? [];
        locations.push({ ...place, entry_zone_line_keys: entry_zone_line_keys === null ? [] : JSON.parse(entry_zone_line_keys as string),
            conditions: placeConditions.get(JSON.stringify([place_set_key, place.place_key])) ?? [] } as unknown as ProvenanceLocation);
        places.set(place_set_key as string, locations);
    }
    return query(db, `SELECT ${SOURCE_COLUMNS} FROM item_sources ORDER BY source_key`).map((row) => ({
        ...row, guaranteed: row.guaranteed === 1, conditions: conditions.get(row.source_key as string) ?? [],
        locations: row.place_set_key === null ? [] : places.get(row.place_set_key as string) ?? []
    } as unknown as ItemAcquisition));
}
export function readItemDispositions(db: Database): ItemDisposition[] {
    return query(db, 'SELECT item_stable_key, disposition, reason, current_pages, former_pages FROM item_statuses ORDER BY item_stable_key')
        .map((row) => ({ ...row, current_pages: JSON.parse(row.current_pages as string), former_pages: JSON.parse(row.former_pages as string) } as unknown as ItemDisposition));
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
        default: return [condition.actor?.replaceAll('_', ' '), condition.predicate.replaceAll('_', ' '), subject, condition.value, bounds].filter(Boolean).join(' ');
    }
}
/** Stored gates all hold, with alternatives inside each gate. No consumer filtering. */
export function conditionLines(conditions: ProvenanceCondition[], names: Record<string, string> = {}): string[] {
    const gates = new Map<number, Map<number, ProvenanceCondition[]>>();
    for (const atom of conditions) {
        const alternatives = gates.get(atom.gate_index) ?? new Map<number, ProvenanceCondition[]>();
        const atoms = alternatives.get(atom.alternative_index) ?? [];
        atoms.push(atom);
        alternatives.set(atom.alternative_index, atoms);
        gates.set(atom.gate_index, alternatives);
    }
    return [...gates].sort(([a], [b]) => a - b).map(([, alternatives]) => [...alternatives].sort(([a], [b]) => a - b)
        .map(([, atoms]) => [...atoms].sort((a, b) => a.atom_index - b.atom_index).map((atom) => conditionText(atom, names)).join(' and ')).join(' or '));
}
export function probabilityText(fact: ItemAcquisition): string {
    if (fact.probability_kind === 'not_applicable') return '';
    const value = fact.probability_kind === 'unknown' ? 'Chance unknown' : fact.probability_min === fact.probability_max ? `${fact.probability_min}%` : `${fact.probability_min ?? '?'}% to ${fact.probability_max ?? '?'}%`;
    const basis: Record<string, string> = { per_kill: 'per kill', per_successful_catch: 'per successful catch', per_node: 'per node', per_use: 'per use', per_listing_opportunity: 'per listing opportunity' };
    return `${value}${fact.probability_basis && basis[fact.probability_basis] ? ` ${basis[fact.probability_basis]}` : ''}`;
}
export function quantityText(fact: ItemAcquisition): string {
    const count = fact.quantity_min === fact.quantity_max ? `${fact.quantity_min ?? '?'}` : `${fact.quantity_min ?? '?'} to ${fact.quantity_max ?? '?'}`;
    const parts = [fact.quantity_kind === 'unknown' ? '' : `Quantity ${count}`, fact.expected_quantity === null ? '' : `Average ${fact.expected_quantity}${fact.probability_basis === 'per_kill' ? ' per kill' : ''}`, fact.guaranteed ? 'Guaranteed' : ''].filter(Boolean);
    return parts.length ? parts.join(', ') : 'Quantity unknown';
}

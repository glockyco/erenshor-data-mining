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
export interface ConditionContext {
    /** The item the source gives, so a condition that the player does not own it reads "one". */
    itemStableKey?: string;
    /** The quest whose turn-in gives the item, so a condition that it is not done yet reads "Once per character". */
    rewardQuestStableKey?: string | null;
}

const PHRASE_ORDER = ['quest_done', 'encounter_won', 'quest_not_done', 'account_state', 'room_furnished', 'held', 'item_not_owned',
    'actor_level', 'zone_use', 'time_of_day', 'quality', 'route', 'never'];

function list(parts: string[], conjunction = 'and'): string {
    const unique = [...new Set(parts)];
    return unique.length < 2 ? unique.join('') : `${unique.slice(0, -1).join(', ')} ${conjunction} ${unique[unique.length - 1]}`;
}

function range(atom: ProvenanceCondition): string {
    const { minimum: min, maximum: max } = atom;
    if (min !== null && max !== null && atom.minimum_inclusive && atom.maximum_inclusive) return min === max ? `${min}` : `${min}–${max}`;
    return [min === null ? '' : atom.minimum_inclusive ? `${min} or higher` : `above ${min}`,
        max === null ? '' : atom.maximum_inclusive ? `${max} or lower` : `below ${max}`].filter(Boolean).join(' and ');
}

/** One phrase per kind of requirement, so several quests or keys read as one list. */
function phrases(atoms: ProvenanceCondition[], names: Record<string, string>, context: ConditionContext): string[] {
    const name = (atom: ProvenanceCondition) => {
        const reference = atom.reference_stable_key;
        return reference ? names[reference] ?? reference.replace(/^[^:]+:/, '') : '';
    };
    const groups = new Map<string, ProvenanceCondition[]>();
    for (const atom of atoms) {
        const kind = atom.predicate === 'key_held' || atom.predicate === 'item_held' ? 'held' : atom.predicate;
        groups.set(kind, [...(groups.get(kind) ?? []), atom]);
    }
    const ordered = [...groups].sort(([a], [b]) => (PHRASE_ORDER.indexOf(a) + 1 || Infinity) - (PHRASE_ORDER.indexOf(b) + 1 || Infinity));
    return ordered.flatMap(([kind, group]): string[] => {
        switch (kind) {
            case 'quest_done': return [`Requires ${list(group.map(name))}`];
            case 'encounter_won': return [`Requires defeating ${list(group.map(name))}`];
            case 'quest_not_done': {
                const own = group.filter((atom) => atom.reference_stable_key === context.rewardQuestStableKey);
                const others = group.filter((atom) => !own.includes(atom));
                return [...(own.length ? ['Once per character'] : []), ...(others.length ? [`Only before ${list(others.map(name))}`] : [])];
            }
            case 'account_state': return group.map((atom) => atom.reference_stable_key === 'account_state:reliquary_claimed'
                ? atom.value === 'false' ? 'Only before claiming your Reliquary' : 'Requires a claimed Reliquary'
                : `${atom.value === 'false' ? 'Only before' : 'Requires'} ${name(atom)}`);
            case 'room_furnished': return [`Requires the ${list(group.map(name), 'or')} in its room`];
            case 'held': return [`Requires ${list(group.map((atom) => (atom.minimum ?? 1) > 1 ? `${name(atom)} ×${atom.minimum}` : name(atom)))}`];
            case 'item_not_owned': return [group.every((atom) => atom.reference_stable_key === context.itemStableKey)
                ? "Only if you don't have one" : `Only if you don't have ${list(group.map(name))}`];
            case 'actor_level': return group.map((atom) => atom.actor === 'enemy' ? `Requires enemy level ${range(atom)}` :
                atom.actor === 'sim' || atom.actor === 'sim_player' ? `Requires simulated player level ${range(atom)}` : `Requires level ${range(atom)}`);
            case 'actor_class': return group.map((atom) => atom.actor === 'sim' || atom.actor === 'sim_player'
                ? `Requires a simulated player of class ${name(atom)}` : `Requires the ${name(atom)} class`);
            case 'zone_use': return [`Only in ${list(group.map(name))}`];
            case 'time_of_day': return group.map((atom) => atom.value === 'day' ? 'Only during the day' : atom.value === 'night' ? 'Only at night' : `Only during ${atom.value}`);
            case 'quality': return group.map((atom) => `Requires quality ${range(atom)}`);
            case 'route': return group.map((atom) => atom.value === 'normal_pointer_inventory_transfer'
                ? 'Drag it into your inventory' : capitalize((atom.value ?? '').replaceAll('_', ' ')));
            case 'never': return ['Never'];
            default: return group.map((atom) => capitalize([atom.predicate.replaceAll('_', ' '), name(atom), atom.value, range(atom)].filter(Boolean).join(' ')));
        }
    });
}

function capitalize(text: string): string {
    return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Branches of one gate as one line: "Requires A or B" when each branch only requires one thing. */
function alternativeLine(branches: string[][]): string {
    const texts = branches.map((branch) => branch.join(', '));
    if (texts.every((text) => text.startsWith('Requires ') && !text.includes(', '))) {
        return `Requires ${texts.map((text) => text.slice('Requires '.length)).join(' or ')}`;
    }
    return texts.map((text, index) => index === 0 ? text : text.charAt(0).toLowerCase() + text.slice(1)).join(' or ');
}

/** A place's eligible player levels, worded like a player level condition. */
export function playerLevelPhrase(minimum: number | null, maximum: number | null): string {
    return phrases([{ gate_index: 0, alternative_index: 0, atom_index: 0, gate_key: '', predicate: 'actor_level', reference_stable_key: null,
        reference_slot: null, actor: 'player', value: null, minimum, maximum, minimum_inclusive: true, maximum_inclusive: true,
        phase: 'availability' }], {}, {})[0];
}

/**
 * Brief player-facing phrases for stored gates, such as "Requires Claiming the Reliquary".
 * Each group keeps its own gate numbers. Every gate holds, so single-branch gates merge
 * into one list per kind, and the branches of any other gate read as "or".
 */
export function conditionPhrases(groups: readonly (readonly ProvenanceCondition[])[], names: Record<string, string> = {},
    context: ConditionContext = {}): string[] {
    const conjunction: ProvenanceCondition[] = [];
    const alternatives: string[] = [];
    for (const atoms of groups) {
        const gates = new Map<number, Map<number, ProvenanceCondition[]>>();
        for (const atom of atoms) {
            const branches = gates.get(atom.gate_index) ?? new Map<number, ProvenanceCondition[]>();
            branches.set(atom.alternative_index, [...(branches.get(atom.alternative_index) ?? []), atom]);
            gates.set(atom.gate_index, branches);
        }
        for (const [, branches] of [...gates].sort(([a], [b]) => a - b)) {
            const ordered = [...branches].sort(([a], [b]) => a - b).map(([, branch]) => [...branch].sort((a, b) => a.atom_index - b.atom_index));
            if (ordered.length === 1) conjunction.push(...ordered[0]);
            else alternatives.push(alternativeLine(ordered.map((branch) => phrases(branch, names, context))));
        }
    }
    return [...phrases(conjunction, names, context), ...alternatives];
}

/**
 * Conditions of several facts at one marker: the phrases every fact needs, shown once,
 * and each fact's remaining phrases by source key. `omit` leaves out atoms the popup
 * already states in its established form.
 */
export function markerConditions(facts: readonly ItemAcquisition[], markerKey: string, names: (fact: ItemAcquisition) => Record<string, string>,
    omit: (atom: ProvenanceCondition) => boolean = () => false): { shared: string[]; own: Map<string, string[]> } {
    const lines = facts.map((fact) => {
        const place = fact.locations.find((location) => location.marker_stable_key === markerKey);
        return conditionPhrases([fact.conditions.filter((atom) => !omit(atom)), (place?.conditions ?? []).filter((atom) => !omit(atom))], names(fact),
            { itemStableKey: fact.item_stable_key });
    });
    const shared = lines.length ? lines[0].filter((line) => lines.every((other) => other.includes(line))) : [];
    return { shared, own: new Map(facts.map((fact, index) => [fact.source_key, lines[index].filter((line) => !shared.includes(line))])) };
}

import { beforeAll, afterAll, describe, expect, it } from 'vitest';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import initSqlJs from 'sql.js/dist/sql-wasm.js';
import type { Database, SqlJsStatic } from 'sql.js/dist/sql-wasm.js';
import { getMapsDatabasePath } from './database-path.server';
import { Repository } from './database.node';
import { assertProvenanceSchema, readItemSources, readItemDispositions, readProvenanceMetadata, conditionLines, probabilityText, quantityText, PROVENANCE_SCHEMA_VERSION } from './item-provenance';
import type { ItemProvenanceSnapshot } from './item-provenance';
import { ItemSearchProvider } from './map/search/item-source-provider';
import { buildMapProvenanceCoverage, writeMapProvenanceManifest } from './item-provenance-coverage.server';
import type { MapProvenanceCoverage } from './item-provenance-coverage.server';
import type { ItemSourceRow } from './map-markers';
import { acquisition, condition, source, disposition } from './testing/item-provenance';

let SQL: SqlJsStatic;
let database: Database;
let repository: Repository;
beforeAll(async () => {
    SQL = await initSqlJs({ locateFile: () => createRequire(import.meta.url).resolve('sql.js/dist/sql-wasm.wasm') });
    database = new SQL.Database(readFileSync(getMapsDatabasePath()));
    repository = new Repository();
    await repository.init(getMapsDatabasePath());
});
afterAll(() => { database.close(); repository.close(); });

function identityFixture() {
    const fact = acquisition({ source_key: 'source:shown', item_stable_key: 'item:shown' });
    const row = source(fact);
    const snapshot: ItemProvenanceSnapshot = {
        metadata: readProvenanceMetadata(database), acquisitions: [fact],
        dispositions: [disposition(fact.item_stable_key)],
        items: [{ stable_key: fact.item_stable_key, is_map_visible: true, wiki_page_name: row.wikiPageName }],
        zone_line_destinations: []
    };
    return { snapshot, row };
}

function providerFor(rows: ItemSourceRow[]) {
    return new ItemSearchProvider(rows, [], [], [], []);
}

describe('public schema reader', () => {
    it('reads every persisted public source identity and public lifecycle record', async () => {
        assertProvenanceSchema(database);
        const facts = readItemSources(database);
        const persistedKeys = database.exec('SELECT source_key FROM item_sources ORDER BY source_key')[0].values.flat();
        expect(facts.length).toBeGreaterThan(0);
        expect(facts.map((fact) => fact.source_key)).toEqual(persistedKeys);
        const snapshot = await repository.getItemProvenanceSnapshot();
        expect(snapshot.acquisitions).toEqual(facts);
        expect(snapshot.dispositions).toEqual(readItemDispositions(database));
        expect(snapshot.metadata.schema_version).toBe(PROVENANCE_SCHEMA_VERSION);
        expect(snapshot).not.toHaveProperty('uses');
        for (const fact of facts) {
            expect(typeof fact.guaranteed).toBe('boolean');
            expect(fact).not.toHaveProperty('variant_key');
            expect(fact).not.toHaveProperty('probability_stage');
            for (const atom of [...fact.conditions, ...fact.locations.flatMap((place) => place.conditions)]) {
                expect(atom).toHaveProperty('gate_index');
                expect(atom).toHaveProperty('alternative_index');
                expect(atom).not.toHaveProperty('scope');
                expect(atom).not.toHaveProperty('group_index');
            }
            for (const place of fact.locations) {
                expect(place).toHaveProperty('place_key');
                expect(place).toHaveProperty('marker_stable_key');
                expect(place).not.toHaveProperty('location_key');
            }
        }
    });

    it.each(['missing', 'duplicate', 'unsupported'] as const)('rejects %s provenance metadata', (mutation) => {
        const mutated = new SQL.Database(database.export());
        try {
            if (mutation === 'missing') mutated.run('DELETE FROM item_provenance_meta');
            if (mutation === 'duplicate') mutated.run('INSERT INTO item_provenance_meta SELECT * FROM item_provenance_meta');
            if (mutation === 'unsupported') mutated.run('UPDATE item_provenance_meta SET schema_version = -1');
            expect(() => assertProvenanceSchema(mutated)).toThrow('schema version');
        } finally { mutated.close(); }
    });

    it('requires the public source table', () => {
        const mutated = new SQL.Database(database.export());
        try {
            mutated.run('DROP TABLE item_sources');
            expect(() => readItemSources(mutated)).toThrow();
        } finally { mutated.close(); }
    });

    it('decodes a shared place set once across distinct source identities', () => {
        const mutated = new SQL.Database(database.export());
        try {
            const facts = readItemSources(mutated);
            const located = facts.find((fact) => fact.place_set_key !== null && fact.locations.length > 0);
            expect(located).toBeDefined();
            const other = facts.find((fact) => fact.source_key !== located!.source_key);
            expect(other).toBeDefined();
            mutated.run('UPDATE item_sources SET place_set_key = ? WHERE source_key = ?', [located!.place_set_key!, other!.source_key]);
            const shared = readItemSources(mutated);
            const first = shared.find((fact) => fact.source_key === located!.source_key)!;
            const second = shared.find((fact) => fact.source_key === other!.source_key)!;
            expect(first.locations.length).toBeGreaterThan(0);
            expect(second.locations).toBe(first.locations);
            expect(second.locations[0].conditions).toBe(first.locations[0].conditions);
        } finally { mutated.close(); }
    });

    it('formats stored gate and alternative indices without deriving policy', () => {
        const atoms = [
            condition({ gate_index: 1, alternative_index: 0, atom_index: 0, gate_key: 'same', predicate: 'quest_done', reference_stable_key: 'quest:gate' }),
            condition({ gate_index: 0, alternative_index: 1, atom_index: 0, gate_key: 'same', predicate: 'time_of_day', value: 'night' }),
            condition({ gate_index: 0, alternative_index: 0, atom_index: 1, gate_key: 'same', predicate: 'quest_done', reference_stable_key: 'quest:route' }),
            condition({ gate_index: 0, alternative_index: 0, atom_index: 0, gate_key: 'same', predicate: 'item_held', reference_stable_key: 'item:key', minimum: 1 })
        ];
        const mutated = new SQL.Database(database.export());
        try {
            const owner = readItemSources(mutated)[0].source_key;
            mutated.run('DELETE FROM item_conditions WHERE owner_key = ?', [owner]);
            for (const atom of atoms) {
                mutated.run(`INSERT INTO item_conditions
                    (owner_key, gate_index, alternative_index, atom_index, gate_key, predicate, reference_stable_key,
                    reference_slot, actor, value, minimum, maximum, minimum_inclusive, maximum_inclusive, phase)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
                [owner, atom.gate_index, atom.alternative_index, atom.atom_index, atom.gate_key, atom.predicate,
                    atom.reference_stable_key, atom.reference_slot, atom.actor, atom.value, atom.minimum, atom.maximum,
                    Number(atom.minimum_inclusive), Number(atom.maximum_inclusive), atom.phase]);
            }
            const stored = readItemSources(mutated).find((fact) => fact.source_key === owner)!.conditions;
            const lines = conditionLines(stored, { 'quest:gate': 'Gate Quest', 'quest:route': 'Route Quest', 'item:key': 'Key' });
            expect(lines).toHaveLength(2);
            expect(lines[0]).toContain('Carry 1 Key and Complete Route Quest or ');
            expect(lines[1]).toBe('Complete Gate Quest');
        } finally { mutated.close(); }
        expect(conditionLines([condition({ predicate: 'account_state', actor: 'account', reference_stable_key: 'account_state:reliquary_claimed', value: 'false' })])).toEqual(['Before claiming your Reliquary']);
    });
});

describe('offline identity coverage', () => {
    it('accounts for the exact public source keys through rows and search', async () => {
        const snapshot = await repository.getItemProvenanceSnapshot();
        const rows = await repository.getItemSources();
        const provider = new ItemSearchProvider(rows, [], [], [], [], await repository.getAllItems());
        const manifest = buildMapProvenanceCoverage(snapshot, rows, provider);
        expect(manifest.acquisitions.map((entry) => entry.source_key).sort()).toEqual(snapshot.acquisitions.map((fact) => fact.source_key).sort());
        const shown = manifest.acquisitions.filter((entry) => entry.status === 'shown').map((entry) => entry.source_key).sort();
        expect(shown).toEqual(rows.map((row) => row.acquisitionKey).sort());
        expect(manifest.groups.flatMap((group) => group.source_keys).sort()).toEqual(shown);
        expect(manifest.acquisitions.filter((entry) => entry.status === 'omitted').every((entry) => entry.reason !== null)).toBe(true);
    });

    it('records only map display omissions and preserves hidden source origins through a unique visible alias', () => {
        const { snapshot, row } = identityFixture();
        const hidden = acquisition({ source_key: 'source:hidden', item_stable_key: 'item:hidden' });
        const retiredAlias = acquisition({ source_key: 'source:retired-alias', item_stable_key: 'item:retired-origin' });
        const unaliased = acquisition({ source_key: 'source:no-alias', item_stable_key: 'item:no-alias' });
        snapshot.acquisitions.push(hidden, retiredAlias, unaliased);
        snapshot.items.push(
            { stable_key: hidden.item_stable_key, is_map_visible: false, wiki_page_name: row.wikiPageName },
            { stable_key: retiredAlias.item_stable_key, is_map_visible: false, wiki_page_name: 'Retired' },
            { stable_key: 'item:retired-display', is_map_visible: true, wiki_page_name: 'Retired' },
            { stable_key: unaliased.item_stable_key, is_map_visible: false, wiki_page_name: 'No alias' }
        );
        snapshot.dispositions.push(disposition(hidden.item_stable_key), disposition(retiredAlias.item_stable_key),
            disposition('item:retired-display', { disposition: 'removed' }), disposition(unaliased.item_stable_key));
        const aliasRow = source(hidden, { itemStableKey: row.itemStableKey, wikiPageName: row.wikiPageName });
        const rows = [row, aliasRow];
        const manifest = buildMapProvenanceCoverage(snapshot, rows, providerFor(rows));
        expect(manifest.acquisitions).toContainEqual(expect.objectContaining({ source_key: hidden.source_key, originating_item_key: hidden.item_stable_key, display_item_key: row.itemStableKey, status: 'shown', reason: null }));
        expect(manifest.acquisitions).toContainEqual(expect.objectContaining({ source_key: retiredAlias.source_key, status: 'omitted', reason: 'display_lifecycle_not_current' }));
        expect(manifest.acquisitions).toContainEqual(expect.objectContaining({ source_key: unaliased.source_key, status: 'omitted', reason: 'map_visibility_no_unique_alias' }));
    });

    it('rejects missing, duplicate and extra shown identities', () => {
        const { snapshot, row } = identityFixture();
        expect(() => buildMapProvenanceCoverage(snapshot, [], providerFor([]))).toThrow('Missing map source identity');
        expect(() => buildMapProvenanceCoverage(snapshot, [row, row], providerFor([row]))).toThrow('Duplicate map source identity');
        const extra = { ...row, acquisitionKey: 'source:extra' };
        expect(() => buildMapProvenanceCoverage(snapshot, [row, extra], providerFor([row]))).toThrow('Extra map source identity');
        expect(() => buildMapProvenanceCoverage({ ...snapshot, acquisitions: [...snapshot.acquisitions, snapshot.acquisitions[0]] }, [row], providerFor([row]))).toThrow('Duplicate public source identity');
    });

    it('rejects missing, duplicate and extra search identities', () => {
        const { snapshot, row } = identityFixture();
        expect(() => buildMapProvenanceCoverage(snapshot, [row], providerFor([]))).toThrow('Missing map search source identity');
        expect(() => buildMapProvenanceCoverage(snapshot, [row], providerFor([row, row]))).toThrow('Duplicate map search source identity');
        const extra = { ...row, acquisitionKey: 'source:extra' };
        expect(() => buildMapProvenanceCoverage(snapshot, [row], providerFor([row, extra]))).toThrow('Invalid map search source identity');
    });

    it('preserves offline lifecycle and conditional zone-line destination records in the emitted manifest', async () => {
        const snapshot = await repository.getItemProvenanceSnapshot();
        const rows = await repository.getItemSources();
        const manifest = buildMapProvenanceCoverage(snapshot, rows, new ItemSearchProvider(rows, [], [], [], [], await repository.getAllItems()));
        expect(manifest.item_dispositions).toEqual(readItemDispositions(database));
        expect(manifest.item_dispositions).toContainEqual(expect.objectContaining({ item_stable_key: 'item:reviewed absent', disposition: 'removed', current_pages: [], former_pages: ['Former Fixture Page'] }));
        expect(manifest.zone_line_destinations).toEqual(snapshot.zone_line_destinations);
        expect(manifest.zone_line_destinations).toContainEqual(expect.objectContaining({ zone_line_stable_key: 'zone-line:reliquary-return', context: expect.objectContaining({ kind: 'stored_return' }), serialized_default: expect.objectContaining({ destination_scene: 'Hidden' }) }));
        const directory = await mkdtemp(path.join(tmpdir(), 'map-provenance-manifest-'));
        try {
            const outputPath = path.join(directory, 'item-provenance-map.json');
            await writeMapProvenanceManifest(outputPath, getMapsDatabasePath());
            const emitted = JSON.parse(await readFile(outputPath, 'utf8')) as MapProvenanceCoverage & { input_database: string };
            expect(emitted).toEqual({ input_database: path.resolve(getMapsDatabasePath()), ...manifest });
            expect(emitted).not.toHaveProperty('item_uses');
        } finally { await rm(directory, { recursive: true, force: true }); }
    });
});

describe('public source presentation', () => {
    it('keeps global fishing singleton identities without inventing locations', () => {
        const { snapshot, row } = identityFixture();
        row.provenance.mechanic = 'fishing_global_replacement';
        row.provenance.kind = 'fishing';
        row.kind = 'fishing';
        const provider = providerFor([row]);
        const resolved = provider.getSourcesForItem(row.itemStableKey);
        expect(resolved).toMatchObject([{ presentation: 'any_water', members: [row], markers: [], entries: [], unlocated: [] }]);
        expect(buildMapProvenanceCoverage(snapshot, [row], provider).groups[0].source_keys).toEqual([row.acquisitionKey]);
    });

    it('presents stored public probabilities, quantities and item guarantees', () => {
        const fact = acquisition({ probability_kind: 'exact', probability_min: 12, probability_max: 12, probability_basis: 'per_kill', guaranteed: false });
        expect(probabilityText(fact)).toBe('12% per kill');
        expect(probabilityText({ ...fact, probability_kind: 'unknown' })).toContain('unknown');
        expect(probabilityText({ ...fact, probability_kind: 'not_applicable' })).toBe('');
        expect(quantityText(fact)).toContain('1 to 3');
        expect(quantityText(fact)).not.toContain('Guaranteed');
        expect(quantityText({ ...fact, guaranteed: true })).toContain('Guaranteed');
    });
});

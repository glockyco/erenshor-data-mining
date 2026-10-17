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
import { assertProvenanceSchema, readItemAcquisitions, readItemDispositions, conditionLines, probabilityText, quantityText, isActionableAcquisition, conditionsSatisfiable } from './item-provenance';
import { ItemSearchProvider } from './map/search/item-source-provider';
import { indexCharacterDetails } from './map/character-details';
import { buildMapProvenanceCoverage, writeMapProvenanceManifest } from './item-provenance-coverage.server';
import type { MapProvenanceCoverage } from './item-provenance-coverage.server';
import type { ItemSourceRow } from './map-markers';
import { acquisition, condition, location } from './testing/item-provenance';

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

describe('offline canonical map coverage', () => {
    it('accounts for every persisted acquisition, dimension and identity, including excluded player states', async () => {
        const facts = readItemAcquisitions(database);
        const lifecycle = new Map(readItemDispositions(database).map((record) => [record.item_stable_key, record]));
        const rows = await repository.getItemSources();
        const entrances = await Promise.all((await repository.getZoneLineMarkers('Stowaway')).map(async (marker) => ({
            ...marker, zone: 'Stowaway', zoneName: 'Stowaway Step',
            worldPosition: [marker.position.x, marker.position.y] as [number, number],
            destinationWorldPosition: null, destinationEnemyInfo: marker.destinationZone && !marker.destinationContext
                ? await repository.getZoneEnemyInfo(marker.destinationZone) : { levelRange: null, bosses: [], elites: [], chests: [] }
        })));
        const provider = new ItemSearchProvider(JSON.parse(JSON.stringify(rows)), [], [], [], [], await repository.getAllItems(), [], entrances);
        const expectedColumns = database.exec('PRAGMA table_info(item_acquisitions)')[0].values.map((row) => row[1] as string).sort();
        expect(facts.length).toBeGreaterThan(rows.length);
        expect(rows.length).toBeGreaterThan(20);
        const omitted: Record<string, number> = {};
        let hidden = 0;
        for (const fact of facts) {
            expect(Object.keys(fact).filter((key) => !['conditions', 'locations', 'evidence'].includes(key)).sort()).toEqual(expectedColumns);
            const projected = rows.filter((row) => row.acquisitionKey === fact.acquisition_key);
            const disposition = lifecycle.get(fact.item_stable_key)!;
            if (disposition.disposition !== 'current') {
                omitted[`lifecycle_${disposition.disposition}`] = (omitted[`lifecycle_${disposition.disposition}`] ?? 0) + 1;
                expect(projected).toEqual([]);
                continue;
            }
            if (!isActionableAcquisition(fact)) {
                const reason = fact.player_access_state !== 'verified_player' ? fact.player_access_state :
                    fact.probability_stage === 'native_pool' ? 'native_pool' :
                        fact.probability_max !== null && fact.probability_max <= 0 ? 'zero_probability' : 'impossible_conditions';
                omitted[reason] = (omitted[reason] ?? 0) + 1;
                expect(projected).toEqual([]);
                continue;
            }
            const statement = database.prepare(`SELECT target.stable_key FROM items original JOIN items target
                ON target.stable_key = original.stable_key OR (original.is_map_visible = 0
                    AND original.wiki_page_name = target.wiki_page_name AND 1 = (
                        SELECT COUNT(*) FROM items visible WHERE visible.wiki_page_name = original.wiki_page_name AND visible.is_map_visible = 1))
                WHERE original.stable_key = ? AND target.is_map_visible = 1`, [fact.item_stable_key]);
            const hasVisibleAlias = statement.step();
            statement.free();
            if (!hasVisibleAlias) { hidden++; expect(projected).toEqual([]); continue; }
            expect(projected).toHaveLength(1);
            const row = projected[0];
            expect(row.originatingItemStableKey).toBe(fact.item_stable_key);
            expect(row.provenance).toEqual(fact);
            if (row.wikiPageName?.trim()) {
                const resolved = provider.getSourcesForItem(row.itemStableKey).filter((entry) =>
                    entry.members.some((member) => member.acquisitionKey === fact.acquisition_key));
                expect(resolved).toHaveLength(1);
                const member = resolved[0].members.find((member) => member.acquisitionKey === fact.acquisition_key)!;
                expect(JSON.parse(JSON.stringify(member.provenance))).toEqual(fact);
                if (resolved[0].presentation === 'source') expect(resolved[0].unlocated).toEqual(fact.locations);
                else {
                    expect(resolved[0].markers).toEqual([]);
                    expect(member.fishingBonus).toEqual(facts.find((bonus) => bonus.acquisition_key === member.fishingBonus?.acquisition_key));
                }
            }
        }
        expect(omitted).toMatchObject({ internal_only: 1, unconfirmed_player: 1, native_pool: 1, impossible_conditions: 1 });
        expect(hidden).toBeGreaterThan(0);
        const ui = rows.find((row) => row.kind === 'ui_grant')!.provenance;
        expect(ui.conditions).toHaveLength(2);
        expect(ui.locations[0].conditions).toHaveLength(3);
        expect(ui.evidence).toHaveLength(1);
        expect(ui.locations[0].entry_zone_line_keys).toHaveLength(1);
        expect(provider.getSourcesForItem('item:fixture relic').find((source) => source.kind === 'ui_grant')?.entries).toEqual(entrances);
        expect(Object.keys(ui.conditions[0]).sort()).toEqual(database.exec('PRAGMA table_info(item_acquisition_conditions)')[0].values
            .map((row) => row[1] as string).filter((key) => key !== 'owner_key').sort());
        expect(Object.keys(ui.locations[0]).sort()).toEqual(database.exec('PRAGMA table_info(item_acquisition_locations)')[0].values
            .map((row) => row[1] as string).filter((key) => key !== 'owner_key').sort());
    });

    it('retains complete canonical facts through character, mining and fishing popup projections', async () => {
        const rows = await repository.getItemSources();
        const details = indexCharacterDetails(rows, await repository.getCharactersByName());
        const popupFacts = [...details.drops.values(), ...details.vendorItems.values()].flat().map((entry) => entry.provenance);
        expect(popupFacts.length).toBeGreaterThan(5);
        for (const fact of popupFacts) expect(fact).toEqual(rows.find((row) => row.acquisitionKey === fact.acquisition_key)!.provenance);
        const mining = await repository.getMiningNodeMarkers('Stowaway');
        const water = await repository.getWaterMarkers('Stowaway');
        const naturalFacts = [...mining.flatMap((marker) => marker.items), ...water.flatMap((marker) => [...marker.daytimeItems, ...marker.nighttimeItems])]
            .map((entry) => entry.provenance);
        expect(naturalFacts.some((fact) => fact.kind === 'mining')).toBe(true);
        expect(naturalFacts.some((fact) => fact.kind === 'fishing')).toBe(true);
        expect(naturalFacts.some((fact) => fact.kind === 'fishing_bonus')).toBe(false);
        expect(readItemAcquisitions(database).filter((fact) => fact.kind === 'fishing_bonus')).toHaveLength(1);
        for (const fact of naturalFacts) expect(fact).toEqual(readItemAcquisitions(database).find((original) => original.acquisition_key === fact.acquisition_key));
    });

    it.each([null, 0, 1, 7])('preserves a mutated pool roll count %s independently of item probability and quantity', (count) => {
        const mutated = new SQL.Database(database.export());
        try {
            const before = readItemAcquisitions(mutated).find((fact) =>
                fact.item_stable_key === 'item:fixture drop' && fact.source_copy_stable_key === 'character:fixture enemy')!;
            expect(before.guaranteed_roll_count).toBe(2);
            expect(before.guarantee_scope).toBe('pool');
            expect(before.probability_max).toBe(25);
            mutated.run('UPDATE item_acquisitions SET guaranteed_roll_count = ? WHERE acquisition_key = ?', [count, before.acquisition_key]);
            const after = readItemAcquisitions(mutated).find((fact) => fact.acquisition_key === before.acquisition_key)!;
            expect(JSON.parse(JSON.stringify(after))).toEqual({ ...before, guaranteed_roll_count: count });
            expect(probabilityText(after)).toBe(probabilityText(before));
            expect(quantityText(after)).toBe(quantityText(before));
            expect(quantityText(after)).not.toContain('Guaranteed');
        } finally {
            mutated.close();
        }
    });

    it('fails closed on missing, duplicated and unsupported schema versions', () => {
        const missing = new SQL.Database();
        expect(() => assertProvenanceSchema(missing)).toThrow();
        missing.run('CREATE TABLE item_provenance_meta (schema_version INTEGER)');
        expect(() => assertProvenanceSchema(missing)).toThrow('schema version 1');
        missing.run('INSERT INTO item_provenance_meta VALUES (2)');
        expect(() => assertProvenanceSchema(missing)).toThrow('schema version 1');
        missing.run('UPDATE item_provenance_meta SET schema_version = 1');
        expect(() => assertProvenanceSchema(missing)).toThrow();
        expect(() => assertProvenanceSchema(database)).not.toThrow();
        expect(() => readItemAcquisitions(missing)).toThrow();
        missing.run('INSERT INTO item_provenance_meta VALUES (1)');
        expect(() => assertProvenanceSchema(missing)).toThrow('schema version 1');
        missing.close();
    });

    it('guards maintained source selectors against raw producer fallback', () => {
        const source = readFileSync(new URL('./database.base.ts', import.meta.url), 'utf8');
        expect((source.match(/JOIN item_acquisitions/g) ?? []).length).toBe(3);
        expect((source.match(/(?:FROM|JOIN)\s+(?:loot_drops|vendor_offers|mining_node_items|water_fishables|special_world_drops|character_dialogs|quest_variants|crafting_rewards|item_drops|spell_created_items|item_conversions|class_starting_items|auction_house_items)\b/g) ?? []).length).toBe(0);
    });

    it('preserves complete reviewed lifecycle records and emits a real offline manifest', async () => {
        const snapshot = await repository.getItemProvenanceSnapshot();
        const rows = await repository.getItemSources();
        const allItems = await repository.getAllItems();
        const provider = new ItemSearchProvider(rows, [], [], [], [], allItems);
        const manifest = buildMapProvenanceCoverage(snapshot, rows, provider);
        expect(manifest.item_dispositions).toEqual(readItemDispositions(database));
        expect(manifest.item_dispositions).toContainEqual({
            item_stable_key: 'item:reviewed absent', disposition: 'removed',
            reason: 'Reviewed identity absent from native items', evidence: 'fixture:absent-lifecycle',
            current_pages: [], former_pages: ['Former Fixture Page']
        });
        expect(snapshot.items.some((item) => item.stable_key === 'item:reviewed absent')).toBe(false);
        expect(manifest.item_dispositions.find((record) => record.item_stable_key === 'item:fixture unknown')?.disposition).toBe('current');
        expect(manifest.acquisitions.filter((entry) => entry.acquisition_key.startsWith('lifecycle:'))
            .map((entry) => entry.source_row_status)).toEqual(['lifecycle_removed', 'lifecycle_removed']);
        expect(rows.some((row) => row.originatingItemStableKey === 'item:fixture meditate retired')).toBe(false);
        expect(manifest.groups.find((group) => group.presentation === 'any_water')?.members).toHaveLength(4);
        expect(manifest.item_uses).toMatchObject([{ use_key: 'use:fixture', reason: 'map_has_no_item_use_listing',
            fact: { material_slot: 2, quantity_min: 2, quantity_max: 3, conditions: expect.arrayContaining([
                expect.objectContaining({ reference_slot: 'slot:2', phase: 'operation_input' }),
                expect.objectContaining({ reference_slot: 'slot:2', phase: 'operation_outcome' }),
                expect.objectContaining({ phase: 'mechanic_parameter' })
            ]) } }]);
        const phases = new Set([...snapshot.acquisitions, ...snapshot.uses].flatMap((fact) => [
            ...fact.conditions, ...fact.locations.flatMap((location) => location.conditions)
        ]).map((condition) => condition.phase));
        expect([...phases].sort()).toEqual(['availability', 'mechanic_parameter', 'operation_input', 'operation_outcome', 'source_initialization']);
        const historical = manifest.acquisitions.find((entry) => entry.acquisition_key === 'drop:character:fixture enemy:item:fixture drop')!;
        expect(historical.public_condition_omissions).toContainEqual({
            location_key: null, reason: 'historical_ownership_selection',
            condition: expect.objectContaining({ phase: 'source_initialization', predicate: 'item_not_owned', scope: 'source' })
        });
        expect(conditionLines(historical.fact.conditions, { 'item:fixture key': 'Fixture Key' })).toEqual(['Carry 1 Fixture Key']);
        const accountOutcome = manifest.acquisitions.find((entry) => entry.acquisition_key === 'ui:fixture')!;
        expect(accountOutcome.public_condition_omissions).toContainEqual({
            location_key: 'room:unlocated', reason: 'account_state_outcome',
            condition: expect.objectContaining({ predicate: 'account_state', actor: 'account',
                reference_stable_key: 'account_state:reliquary_claimed', value: 'true',
                scope: 'room:unlocated', phase: 'operation_outcome' })
        });
        expect(manifest.zone_line_destinations).toEqual(snapshot.zone_line_destinations);
        expect(manifest.zone_line_destinations.find((line) => line.zone_line_stable_key === 'zone-line:reliquary-return')).toMatchObject({
            serialized_default: { destination_zone_stable_key: 'zone:hidden', destination_scene: 'Hidden',
                landing_position: { x: 123, y: 45, z: 678 } },
            context: { kind: 'stored_return', destination_state_key: 'character_state:reliquary_return_zone',
                landing_state_key: 'character_state:reliquary_return_landing', source_key: 'activator:reliquary_return_controller' }
        });
        const missingLifecycle = { ...snapshot, dispositions: snapshot.dispositions.filter((record) => record.item_stable_key !== 'item:fixture fish') };
        expect(() => buildMapProvenanceCoverage(missingLifecycle, rows, provider)).toThrow('Missing canonical item disposition');
        const dropped = rows.slice(1);
        expect(() => buildMapProvenanceCoverage(snapshot, dropped, new ItemSearchProvider(dropped, [], [], [], [], allItems))).toThrow();
        const lossy = JSON.parse(JSON.stringify(rows)) as ItemSourceRow[];
        delete (lossy[0].provenance as unknown as Record<string, unknown>).guaranteed_roll_count;
        expect(() => buildMapProvenanceCoverage(snapshot, lossy, new ItemSearchProvider(lossy, [], [], [], [], allItems))).toThrow('dimension mismatch');
        const directory = await mkdtemp(path.join(tmpdir(), 'map-provenance-manifest-'));
        try {
            const outputPath = path.join(directory, 'item-provenance-map.json');
            await writeMapProvenanceManifest(outputPath, getMapsDatabasePath());
            const emitted = JSON.parse(await readFile(outputPath, 'utf8')) as MapProvenanceCoverage & { input_database: string };
            expect(emitted.input).toEqual(snapshot.metadata);
            expect(emitted.input_database).toBe(path.resolve(getMapsDatabasePath()));
            expect(emitted.item_dispositions).toEqual(manifest.item_dispositions);
            expect(emitted.zone_line_destinations).toEqual(manifest.zone_line_destinations);
            expect(emitted.groups.flatMap((group) => group.members.map((member) => member.acquisitionKey)).sort()).toEqual(
                manifest.groups.flatMap((group) => group.members.map((member) => member.acquisitionKey)).sort());
        } finally {
            await rm(directory, { recursive: true, force: true });
        }
    });

    it('fails closed when a native item loses its required disposition', () => {
        const mutated = new SQL.Database(database.export());
        try {
            mutated.run("DELETE FROM item_dispositions WHERE item_stable_key = 'item:fixture fish'");
            expect(() => readItemDispositions(mutated)).toThrow('Missing canonical item disposition: item:fixture fish');
        } finally {
            mutated.close();
        }
    });

    it.each(['condition_field', 'condition_phase', 'invalid_phase', 'entry_identity', 'coordinates', 'relation'] as const)('rejects a lost or malformed nested %s dimension', (mutation) => {
        const mutated = new SQL.Database(database.export());
        try {
            const location = readItemAcquisitions(mutated).find((fact) => fact.acquisition_key === 'ui:fixture')!.locations[0];
            if (mutation === 'condition_field' || mutation === 'condition_phase' || mutation === 'invalid_phase') {
                const atom = { ...location.conditions[0] } as unknown as Record<string, unknown>;
                if (mutation === 'invalid_phase') atom.phase = 'at_spawn';
                else delete atom[mutation === 'condition_phase' ? 'phase' : 'reference_slot'];
                mutated.run("UPDATE item_acquisition_locations SET conditions = ? WHERE owner_key = 'ui:fixture'", [JSON.stringify([atom])]);
            } else if (mutation === 'entry_identity') {
                mutated.run("UPDATE item_acquisition_locations SET entry_zone_line_keys = ? WHERE owner_key = 'ui:fixture'",
                    [JSON.stringify([location.entry_zone_line_keys[0], location.entry_zone_line_keys[0]])]);
            } else if (mutation === 'coordinates') {
                mutated.run("UPDATE item_acquisition_locations SET x = 1 WHERE owner_key = 'ui:fixture'");
            } else {
                mutated.run("UPDATE item_acquisition_locations SET relation = 'inferred' WHERE owner_key = 'ui:fixture'");
            }
            expect(() => readItemAcquisitions(mutated)).toThrow('Invalid canonical');
        } finally {
            mutated.close();
        }
    });

    it.each(['actor', 'reference', 'value', 'phase'] as const)('rejects invalid account-state %s without quest aliases or coercion', (field) => {
        const mutated = new SQL.Database(database.export());
        try {
            const account = readItemAcquisitions(mutated).find((fact) => fact.acquisition_key === 'ui:fixture')!
                .locations[0].conditions.find((condition) => condition.predicate === 'account_state' && condition.phase === 'availability')!;
            const invalid = { ...account } as unknown as Record<string, unknown>;
            if (field === 'actor') invalid.actor = 'player';
            else if (field === 'reference') invalid.reference_stable_key = 'quest:reliquary_claimed';
            else if (field === 'value') invalid.value = false;
            else invalid.phase = 'operation_input';
            mutated.run("UPDATE item_acquisition_locations SET conditions = ? WHERE owner_key = 'ui:fixture'", [JSON.stringify([invalid])]);
            expect(() => readItemAcquisitions(mutated)).toThrow('Invalid canonical condition');
        } finally {
            mutated.close();
        }
    });
});

describe('actionable canonical summaries', () => {
    it('keeps AND/OR gate semantics, actors and strict level boundaries', () => {
        const conditions = [condition({ gate_key: 'level', actor: 'enemy', minimum: 30, minimum_inclusive: false, maximum: null }),
            condition({ gate_key: 'route', predicate: 'time_of_day', minimum: null, maximum: null, value: 'day' }),
            condition({ gate_key: 'route', group_index: 1, predicate: 'quest_done', minimum: null, maximum: null,
                reference_stable_key: 'quest:fixture' })];
        const lines = conditionLines(conditions, { 'quest:fixture': 'Fixture Quest' });
        expect(lines).toHaveLength(2);
        expect(lines[0]).toContain('30');
        expect(lines[1]).toContain(' or ');
        expect(lines[1]).toContain('Fixture Quest');
    });
    it('does not promote native-pool percentages to final acquisition chances', () => {
        expect(probabilityText(acquisition({ probability_stage: 'native_pool' }))).toContain('within pool');
        expect(probabilityText(acquisition({ probability_kind: 'unknown' }))).toContain('unknown');
        expect(probabilityText(acquisition({ probability_kind: 'not_applicable' }))).toBe('');
        expect(quantityText(acquisition())).toContain('1 to 3');
        expect(isActionableAcquisition(acquisition({ probability_stage: 'native_pool' }))).toBe(false);
        expect(isActionableAcquisition(acquisition({ player_access_state: 'unconfirmed_player' }))).toBe(false);
        expect(conditionsSatisfiable([condition({ predicate: 'never' }), condition({ group_index: 1 })])).toBe(true);
        expect(conditionsSatisfiable([condition({ predicate: 'never' }), condition({ atom_index: 1 })])).toBe(false);
        expect(conditionsSatisfiable([condition({ minimum: 10, maximum: 10, maximum_inclusive: false })])).toBe(false);
    });

    it('requires compatible source and placement gates rather than validating them independently', () => {
        const complete = condition({ predicate: 'quest_done', gate_key: 'source', reference_stable_key: 'quest:fixture',
            minimum: null, maximum: null });
        const incomplete = condition({ predicate: 'quest_not_done', gate_key: 'placement', reference_stable_key: 'quest:fixture',
            minimum: null, maximum: null, scope: 'placement' });
        expect(conditionsSatisfiable([complete])).toBe(true);
        expect(conditionsSatisfiable([incomplete])).toBe(true);
        expect(isActionableAcquisition(acquisition({ conditions: [complete], locations: [location({ conditions: [incomplete] })] }))).toBe(false);
        expect(isActionableAcquisition(acquisition({ conditions: [complete], locations: [
            location({ conditions: [incomplete] }), location({ location_key: 'compatible', conditions: [] })
        ] }))).toBe(true);
        expect(conditionsSatisfiable([complete, incomplete, { ...incomplete, group_index: 1, predicate: 'room_furnished' }])).toBe(true);
        const low = condition({ predicate: 'actor_level', gate_key: 'source', minimum: 30, maximum: null });
        const high = condition({ predicate: 'actor_level', gate_key: 'placement', minimum: null, maximum: 20, scope: 'placement' });
        expect(isActionableAcquisition(acquisition({ conditions: [low], locations: [location({ conditions: [high] })] }))).toBe(false);
        expect(conditionsSatisfiable([
            condition({ predicate: 'time_of_day', value: 'day', minimum: null, maximum: null }),
            condition({ predicate: 'time_of_day', gate_key: 'placement', value: 'night', minimum: null, maximum: null, scope: 'placement' })
        ])).toBe(false);
    });

    it('separates historical initialization ownership from current operation requirements without public denials', () => {
        const absentAtInitialization = condition({ predicate: 'item_not_owned', gate_key: 'ownership', phase: 'source_initialization',
            reference_stable_key: 'item:fixture key', value: 'inventory', minimum: null, maximum: null });
        const heldNow = condition({ ...absentAtInitialization, predicate: 'item_held', phase: 'operation_input', minimum: 1 });
        expect(conditionsSatisfiable([absentAtInitialization, heldNow])).toBe(true);
        expect(isActionableAcquisition(acquisition({ conditions: [absentAtInitialization, heldNow] }))).toBe(true);
        expect(conditionsSatisfiable([{ ...absentAtInitialization, phase: 'availability' }, heldNow])).toBe(false);
        expect(conditionsSatisfiable([absentAtInitialization, { ...heldNow, phase: 'source_initialization' }])).toBe(false);
        expect(conditionLines([absentAtInitialization, heldNow], { 'item:fixture key': 'Fixture Key' })).toEqual(['Carry 1 Fixture Key']);
        expect(conditionsSatisfiable([
            condition({ predicate: 'never', gate_key: 'same', phase: 'source_initialization' }),
            condition({ gate_key: 'same', group_index: 1, phase: 'operation_input' })
        ])).toBe(false);
        expect(conditionLines([absentAtInitialization, condition({ ...absentAtInitialization, group_index: 1,
            predicate: 'quest_done', reference_stable_key: 'quest:fixture', value: null })])).toEqual([]);
    });

    it('shares availability and operation-input state but separates outcomes and static parameters', () => {
        const input = condition({ predicate: 'quality', gate_key: 'input', phase: 'operation_input', value: 'normal', minimum: 2, maximum: 5 });
        const outcome = condition({ ...input, gate_key: 'outcome', phase: 'operation_outcome', minimum: 8, maximum: 10 });
        expect(conditionsSatisfiable([input, outcome])).toBe(true);
        expect(conditionsSatisfiable([input, { ...outcome, phase: 'availability' }])).toBe(false);
        const historicalLevel = condition({ phase: 'source_initialization', minimum: 30, maximum: null });
        const currentLevel = condition({ gate_key: 'current', phase: 'operation_input', minimum: null, maximum: 20 });
        expect(conditionsSatisfiable([historicalLevel, currentLevel])).toBe(true);
        expect(conditionsSatisfiable([{ ...historicalLevel, phase: 'availability' }, currentLevel])).toBe(false);
        const parameter = condition({ gate_key: 'parameter', phase: 'mechanic_parameter', minimum: 1, maximum: 5 });
        expect(conditionsSatisfiable([parameter, { ...currentLevel, minimum: 15 }])).toBe(true);
        expect(conditionLines([parameter])).toEqual([]);
        const day = condition({ predicate: 'time_of_day', phase: 'source_initialization', minimum: null, maximum: null, value: 'day' });
        const night = condition({ ...day, gate_key: 'current', phase: 'operation_input', value: 'night' });
        expect(conditionsSatisfiable([day, night])).toBe(true);
        expect(conditionsSatisfiable([{ ...day, phase: 'availability' }, night])).toBe(false);
    });

    it('keeps account claim availability separate from its outcome and displays only the ordinary prerequisite', () => {
        const unclaimed = condition({ predicate: 'account_state', actor: 'account',
            reference_stable_key: 'account_state:reliquary_claimed', value: 'false',
            gate_key: 'claim', scope: 'room:unlocated', phase: 'availability', minimum: null, maximum: null });
        const claimedAfter = condition({ ...unclaimed, phase: 'operation_outcome', value: 'true' });
        expect(conditionsSatisfiable([unclaimed, claimedAfter])).toBe(true);
        expect(conditionsSatisfiable([unclaimed, { ...claimedAfter, phase: 'availability', scope: 'other:location' }])).toBe(false);
        expect(isActionableAcquisition(acquisition({ locations: [location({ conditions: [unclaimed, claimedAfter] })] }))).toBe(true);
        expect(conditionLines([unclaimed, claimedAfter])).toEqual(['Before claiming your Reliquary']);
        expect(conditionLines([{ ...unclaimed, value: 'true' }])).toEqual(['After claiming your Reliquary']);
        expect(conditionLines([unclaimed], { 'account_state:reliquary_claimed': 'your home' })).toEqual(['Before claiming your home']);
    });
});

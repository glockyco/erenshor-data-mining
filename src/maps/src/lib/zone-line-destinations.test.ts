import { afterAll, beforeAll, describe, expect, it } from 'vitest';
import { readFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import initSqlJs from 'sql.js/dist/sql-wasm.js';
import { Repository } from './database.node';
import { getMapsDatabasePath } from './database-path.server';
import { buildMapWorldData } from './map-world-data.server';
import { readZoneLineDestinationContexts, STORED_RETURN_LABEL } from './zone-line-destinations';

let repository: Repository;
beforeAll(async () => { repository = new Repository(); await repository.init(getMapsDatabasePath()); });
afterAll(() => repository.close());

describe('common zone-line destination contexts', () => {
    it('retains fixed destinations but overlays stored returns without a false Hidden target', async () => {
        const fixed = await repository.getZoneLineMarkers('Stowaway');
        expect(fixed).toHaveLength(1);
        expect(fixed[0]).toMatchObject({ stableKey: 'zone-line:stowaway-fixture', destinationContext: null,
            destinationZone: 'StowawayPortal', landingPosition: { x: 0, y: 0, z: 0 }, isEnabled: true });
        const returns = await repository.getZoneLineMarkers('Reliquary');
        expect(returns).toHaveLength(1);
        expect(returns[0]).toMatchObject({ stableKey: 'zone-line:reliquary-return', destinationZone: null,
            destinationZoneName: STORED_RETURN_LABEL, landingPosition: null, levelRangeLow: null, levelRangeHigh: null,
            isEnabled: false, destinationContext: {
                zone_line_stable_key: 'zone-line:reliquary-return', kind: 'stored_return',
                destination_state_key: 'character_state:reliquary_return_zone',
                landing_state_key: 'character_state:reliquary_return_landing',
                source_key: 'activator:reliquary_return_controller'
            } });
        expect(returns[0].popup).not.toContain('Hidden');
        expect(returns[0].popup).not.toContain('href=');
        expect(JSON.stringify(returns[0])).not.toContain('serialized_default');
    });

    it('omits lines that players cannot use, including a reviewed exclusion of a capable line', async () => {
        const keys = (await repository.getZoneLineMarkers('Stowaway')).map((line) => line.stableKey);
        for (const key of ['zone-line:disabled-component', 'zone-line:non-trigger', 'zone-line:no-enabled-trigger',
            'zone-line:reviewed-exclusion']) {
            expect(keys).not.toContain(key);
        }
        const snapshot = await repository.getItemProvenanceSnapshot();
        expect(snapshot.zone_line_destinations.find((line) => line.zone_line_stable_key === 'zone-line:reviewed-exclusion'))
            .toMatchObject({ zoning_capable: true });
    });

    it('keeps raw serialized defaults and capability exclusions in the offline snapshot', async () => {
        const snapshot = await repository.getItemProvenanceSnapshot();
        const returned = snapshot.zone_line_destinations.find((line) => line.zone_line_stable_key === 'zone-line:reliquary-return')!;
        expect(returned).toMatchObject({ zoning_capable: true, has_physical_location: true,
            serialized_default: { destination_zone_stable_key: 'zone:hidden', destination_scene: 'Hidden',
                landing_position: { x: 123, y: 45, z: 678 } }, context: { kind: 'stored_return' } });
        expect(returned.context?.source_key).not.toBe(returned.zone_line_stable_key);
        for (const key of ['zone-line:disabled-component', 'zone-line:non-trigger', 'zone-line:no-enabled-trigger']) {
            expect(snapshot.zone_line_destinations.find((line) => line.zone_line_stable_key === key)?.zoning_capable).toBe(false);
        }
        expect(snapshot.zone_line_destinations.find((line) => line.zone_line_stable_key === 'zone-line:unlocated-prefab'))
            .toMatchObject({ zoning_capable: true, has_physical_location: false });
    });

    it('never derives a world destination or enemy levels from the stored-return serialized default', async () => {
        const world = await buildMapWorldData();
        const returned = world.markers.zoneLines.find((line) => line.stableKey === 'zone-line:reliquary-return')!;
        expect(returned.destinationWorldPosition).toBeNull();
        expect(returned.destinationEnemyInfo).toEqual({ levelRange: null, bosses: [], elites: [], chests: [] });
        const fixed = world.markers.zoneLines.find((line) => line.stableKey === 'zone-line:stowaway-fixture')!;
        expect(fixed.destinationWorldPosition).not.toBeNull();
    });

    it.each(['unknown_kind', 'missing_state_key', 'orphan_line'] as const)('rejects %s instead of falling back to serialized destinations', async (mutation) => {
        const SQL = await initSqlJs({ locateFile: () => createRequire(import.meta.url).resolve('sql.js/dist/sql-wasm.wasm') });
        const database = new SQL.Database(await readFile(getMapsDatabasePath()));
        try {
            database.run('PRAGMA foreign_keys = OFF');
            database.run('PRAGMA ignore_check_constraints = ON');
            if (mutation === 'unknown_kind') database.run("UPDATE zone_line_destination_contexts SET kind = 'fixed_guess'");
            else if (mutation === 'missing_state_key') database.run("UPDATE zone_line_destination_contexts SET destination_state_key = ''");
            else database.run("UPDATE zone_line_destination_contexts SET zone_line_stable_key = 'zone-line:missing'");
            expect(() => readZoneLineDestinationContexts(database)).toThrow('Invalid common zone-line destination context');
        } finally {
            database.close();
        }
    });
});

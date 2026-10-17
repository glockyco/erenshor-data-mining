import { describe, expect, it } from 'vitest';
import { mkdtemp, readFile, rm, writeFile } from 'node:fs/promises';
import { createRequire } from 'node:module';
import { tmpdir } from 'node:os';
import path from 'node:path';
import initSqlJs from 'sql.js/dist/sql-wasm.js';
import { getMapsDatabasePath } from './database-path.server';
import { Repository } from './database.node';
import { buildMapWorldData } from './map-world-data.server';
import { formatSpawnLevels } from './map-markers';

describe('actual-copy combat eligibility', () => {
    it('excludes permanent immunity but retains proven releases before grouping and level filtering', async () => {
        const directory = await mkdtemp(path.join(tmpdir(), 'map-combat-eligibility-'));
        try {
            const databasePath = path.join(directory, 'combat.sqlite');
            const SQL = await initSqlJs({ locateFile: () => createRequire(import.meta.url).resolve('sql.js/dist/sql-wasm.wasm') });
            const database = new SQL.Database(await readFile(getMapsDatabasePath()));
            try {
                database.run(await readFile(new URL('../../tests/fixtures/combat-eligibility.sql', import.meta.url), 'utf8'));
                await writeFile(databasePath, database.export());
            } finally {
                database.close();
            }
            const repository = new Repository();
            try {
                await repository.init(databasePath);
                const markers = await repository.getSpawnPointMarkers('Reliquary');
                expect(markers.map((marker) => marker.stableKey).sort()).toEqual([
                    'spawn:eligibility evadne', 'spawn:eligibility shadow', 'spawn:eligibility shared', 'spawn:eligibility stardust'
                ]);
                for (const name of ['Stardust', 'Warded Shadow', 'Evadne']) {
                    const character = markers.flatMap((marker) => marker.characters).find((character) => character.name === name)!;
                    expect(character.isInvulnerable).toBe(true);
                    expect(character.canBeDamaged).toBe(true);
                }
                const shared = markers.find((marker) => marker.stableKey === 'spawn:eligibility shared')!;
                expect(shared.characters).toMatchObject([{ stableKey: 'character:copygroup 0 representative',
                    level: 24, levelMax: 26, canBeDamaged: true, isInvulnerable: false }]);
                expect(formatSpawnLevels(shared.characters)).toBe('Level 24–26');
                expect(await repository.getZoneEnemyInfo('Reliquary')).toEqual({
                    levelRange: { min: 24, max: 35 }, bosses: [{ name: 'Shared Sentinel', wikiPageName: null, level: 24, levelMax: 26 }],
                    elites: [], chests: []
                });
            } finally {
                repository.close();
            }
            const world = await buildMapWorldData({ databasePath });
            expect(world.levelRange).toEqual({ min: 2, max: 36 });
            const shared = world.markers.enemiesBoss.find((marker) => marker.stableKey === 'spawn:eligibility shared')!;
            expect([shared.levelMin, shared.levelMax]).toEqual([24, 26]);
            expect([...world.markers.enemiesEnemy, ...world.markers.enemiesBoss]
                .some((marker) => marker.characters.some((character) => character.name === 'Ward'))).toBe(false);
        } finally {
            await rm(directory, { recursive: true, force: true });
        }
    });
});

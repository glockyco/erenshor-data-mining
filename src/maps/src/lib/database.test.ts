import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { getMapsDatabasePath } from './database-path.server';
import { Repository } from './database.node';
import { MAPS } from './maps';

const DETAIL_ZONE = 'Stowaway';

let db: Repository;

beforeAll(async () => {
	db = new Repository();
	await db.init(getMapsDatabasePath());
});

afterAll(() => {
	db.close();
});

describe('Repository', () => {
	it('loads every marker category needed by the fixture zone detail', async () => {
		const markerGroups = await Promise.all([
			db.getAchievementTriggerMarkers(DETAIL_ZONE),
			db.getDoorMarkers(DETAIL_ZONE),
			db.getForgeMarkers(DETAIL_ZONE),
			db.getItemBagMarkers(DETAIL_ZONE),
			db.getMiningNodeMarkers(DETAIL_ZONE),
			db.getSecretPassageMarkers(DETAIL_ZONE),
			db.getSpawnPointMarkers(DETAIL_ZONE),
			db.getTeleportMarkers(DETAIL_ZONE),
			db.getTreasureLocMarkers(DETAIL_ZONE),
			db.getWaterMarkers(DETAIL_ZONE),
			db.getWishingWellMarkers(DETAIL_ZONE),
			db.getZoneLineMarkers(DETAIL_ZONE)
		]);

		expect(markerGroups.flat().map((marker) => marker.category).sort()).toEqual([
			'achievement-trigger',
			'door',
			'enemy',
			'enemy',
			'forge',
			'item-bag',
			'mining-node',
			'npc',
			'secret-passage',
			'teleport',
			'treasure-loc',
			'water',
			'wishing-well',
			'zone-line'
		]);
	});

	it('provides a bearing for every registered world-map zone', async () => {
		const bearings = await db.getAllZoneNorthBearings();

		expect(Object.keys(bearings).sort()).toEqual(Object.keys(MAPS).sort());
		expect(await db.getZoneNorthBearing(DETAIL_ZONE)).toBe(0);
	});

	it('loads deterministic enemy data for the fixture zone', async () => {
		expect(await db.getZoneEnemyInfo(DETAIL_ZONE)).toEqual({
			levelRange: { min: 7, max: 7 },
			bosses: [{ name: 'Fixture Enemy', wikiPageName: 'Fixture Enemy', level: 7 }],
			elites: [],
			chests: [{ name: 'Fixture Chest', wikiPageName: 'Fixture Chest', level: 18 }]
		});
	});

	it('keeps chests in the character spawn category with their own tier', async () => {
		const spawns = await db.getSpawnPointMarkers(DETAIL_ZONE);
		expect(spawns.find((marker) => marker.stableKey === 'spawn:stowaway-chest')).toMatchObject({
			category: 'enemy',
			encounterTier: 'chest',
			characters: [expect.objectContaining({ name: 'Fixture Chest', encounterTier: 'chest' })],
			popup: expect.stringContaining('Chest @')
		});
	});

	it('indexes every map-visible character by name with the scenes it is placed in', async () => {
		// A name is not an identity: 39 map-visible names cover more than one
		// character and 22 of those disagree on loot, so the index keeps them all.
		const byName = await db.getCharactersByName();

		expect(byName.get('Fixture Enemy')).toEqual([
			{ stableKey: 'character:fixture enemy', scenes: ['Stowaway'] },
			{ stableKey: 'character:fixture enemy twin', scenes: ['StowawayPortal'] }
		]);
		// An enemy that only a script spawns has no placement, but the live
		// overlay can still report it.
		expect(byName.get('Runtime Enemy')).toEqual([{ stableKey: 'character:runtime enemy', scenes: [] }]);
	});

	it('loads map-visible enemies without fixed spawn points', async () => {
		expect(await db.getUnlocatedEnemies()).toEqual([
			{
				stableKey: 'character:runtime enemy',
				name: 'Runtime Enemy',
				wikiPageName: 'Runtime Enemy',
				level: 12,
				encounterTier: 'elite'
			}
		]);
	});

	it('loads all searchable items and the quest-unlocked vendor item', async () => {
		const items = await db.getAllItems();
		expect(items).toHaveLength(7);
		expect(items.every((item) => (item.wikiPageName?.trim().length ?? 0) > 0)).toBe(true);
		expect(items.find((item) => item.itemStableKey === 'item:furniture - enchanted smithy')).toEqual({
			itemStableKey: 'item:furniture - enchanted smithy',
			displayName: 'Enchanted Smithy',
			wikiPageName: 'Enchanted Smithy',
			iconName: 'enchanted_smithy'
		});

		const sources = await db.getItemSources();
		expect(
			sources.find(
				(source) =>
					source.kind === 'vendor' &&
					source.itemStableKey === 'item:furniture - enchanted smithy'
			)
		).toMatchObject({
			kind: 'vendor',
			characterStableKey: 'character:breena carpenter'
		});
		expect(
			sources.find(
				(source) => source.kind === 'drop' && source.characterStableKey === 'character:fixture enemy'
			)
		).toMatchObject({ kind: 'drop', encounterTier: 'boss' });
	});

	it('loads every map-visible acquisition source kind', async () => {
		const rows = await db.getItemSources();

		expect([...new Set(rows.map((row) => row.kind))].sort()).toEqual([
			'bag',
			'drop',
			'fishing',
			'mining',
			'vendor',
			'world'
		]);
		expect(rows.every((row) => row.itemStableKey.length > 0)).toBe(true);
		expect(rows.every((row) => row.displayName.length > 0)).toBe(true);
	});
});

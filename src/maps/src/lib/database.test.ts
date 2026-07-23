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

	it('loads deterministic enemy and popup data for the fixture zone', async () => {
		expect(await db.getZoneEnemyInfo(DETAIL_ZONE)).toEqual({
			levelRange: { min: 7, max: 7 },
			uniques: [{ name: 'Fixture Enemy', wikiPageName: 'Fixture Enemy', level: 7 }],
			rares: []
		});
		expect(await db.getCharacterByName('Fixture Enemy')).toEqual({
			stableKey: 'character:fixture enemy'
		});
		expect(await db.getDropsForCharacter('character:fixture enemy')).toEqual([
			{ itemName: 'Fixture Drop', dropProbability: 25 }
		]);
	});

	it('loads all searchable items and the quest-unlocked vendor item', async () => {
		const items = await db.getAllItems();
		expect(items).toHaveLength(6);
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
		expect(await db.getVendorItems('character:breena carpenter')).toEqual([
			{ name: 'Enchanted Smithy', price: 250 }
		]);
	});

	it('loads every map-visible acquisition source kind', async () => {
		const rows = await db.getItemSources();

		expect(rows.map((row) => row.kind).sort()).toEqual([
			'bag',
			'drop',
			'fishing',
			'mining',
			'vendor'
		]);
		expect(rows.every((row) => row.itemStableKey.length > 0)).toBe(true);
		expect(rows.every((row) => row.displayName.length > 0)).toBe(true);
	});
});

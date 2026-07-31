import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { Rarity } from './map-markers';
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
		expect(await db.getCharactersByName('Fixture Enemy', DETAIL_ZONE)).toEqual([
			{ stableKey: 'character:fixture enemy', inScene: true },
			{ stableKey: 'character:fixture enemy twin', inScene: false }
		]);
		// Every drop, not the first ten: a cap here is indistinguishable from a
		// short loot table, and 165 of the game's 728 characters with drops have
		// more than ten. 'Fixture Drop' and 'Hoard Item 11' share a probability,
		// so their order also pins the name tiebreaker.
		expect(await db.getDropsForCharacter('character:fixture enemy')).toEqual([
			{ itemName: 'Hoard Item 01', dropProbability: 90 },
			{ itemName: 'Hoard Item 02', dropProbability: 80 },
			{ itemName: 'Hoard Item 03', dropProbability: 70 },
			{ itemName: 'Hoard Item 04', dropProbability: 60 },
			{ itemName: 'Hoard Item 05', dropProbability: 50 },
			{ itemName: 'Hoard Item 06', dropProbability: 40 },
			{ itemName: 'Hoard Item 07', dropProbability: 30 },
			{ itemName: 'Fixture Drop', dropProbability: 25 },
			{ itemName: 'Hoard Item 11', dropProbability: 25 },
			{ itemName: 'Hoard Item 08', dropProbability: 20 },
			{ itemName: 'Hoard Item 09', dropProbability: 15 },
			{ itemName: 'Hoard Item 10', dropProbability: 10 }
		]);
	});

	it('batches drops for several characters in one query', async () => {
		// The spawn popup asks for every character at a point at once. A crowded
		// point hosts fourteen, so per-character queries made latency scale with
		// how busy the spot is.
		const drops = await db.getDropsForCharacters([
			'character:fixture enemy',
			'character:runtime enemy'
		]);

		// Same rows and same order as the single-character call, so the batched
		// path cannot drift from it.
		expect(drops.get('character:fixture enemy')).toEqual(
			await db.getDropsForCharacter('character:fixture enemy')
		);
		// A character with no loot is absent rather than mapping to an empty list,
		// so callers can tell "no drops" from "not asked".
		expect(drops.has('character:runtime enemy')).toBe(false);
		expect(await db.getDropsForCharacters([])).toEqual(new Map());
	});

	it('returns every character sharing a name, flagged by scene', async () => {
		// A name is not an identity: 39 map-visible names cover more than one
		// character and 22 of those disagree on loot, so answering with one of them
		// presents a guess as a fact.
		expect(await db.getCharactersByName('Fixture Enemy', 'StowawayPortal')).toEqual([
			{ stableKey: 'character:fixture enemy', inScene: false },
			{ stableKey: 'character:fixture enemy twin', inScene: true }
		]);

		// With no scene to prefer, no candidate is favoured over another.
		expect(await db.getCharactersByName('Fixture Enemy')).toEqual([
			{ stableKey: 'character:fixture enemy', inScene: false },
			{ stableKey: 'character:fixture enemy twin', inScene: false }
		]);

		// An unrecognised scene behaves the same way. The live overlay takes its
		// scene from whatever the companion mod reports, so a mod that reports
		// something this database does not know must still yield every candidate
		// rather than none.
		expect(await db.getCharactersByName('Fixture Enemy', 'NotAScene')).toEqual([
			{ stableKey: 'character:fixture enemy', inScene: false },
			{ stableKey: 'character:fixture enemy twin', inScene: false }
		]);

		expect(await db.getCharactersByName('No Such Enemy', DETAIL_ZONE)).toEqual([]);
	});

	it('loads map-visible enemies without fixed spawn points', async () => {
		expect(await db.getUnlocatedEnemies()).toEqual([
			{
				stableKey: 'character:runtime enemy',
				name: 'Runtime Enemy',
				wikiPageName: 'Runtime Enemy',
				level: 12,
				effectiveRarity: Rarity.rare
			}
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

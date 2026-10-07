import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { getMapsDatabasePath } from './database-path.server';
import { Repository } from './database.node';
import { MAPS } from './maps';
import { buildSearchIndex } from './map/search';
import { deserializeSelection } from './types/selection';
import type { WorldTreasureLoc } from './types/world-map';

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

	it('loads catalog portraits for spawn characters and omits missing portraits', async () => {
		const spawns = await db.getSpawnPointMarkers(DETAIL_ZONE);
		const enemy = spawns.find((marker) => marker.stableKey === 'spawn:stowaway-enemy');
		const npc = spawns.find((marker) => marker.stableKey === 'spawn:stowaway-breena');

		expect(enemy?.characters[0].portraitHash).toBe('fixture_enemy');
		expect(enemy?.popup).toContain('/characters/fixture_enemy.w192.webp 2x');
		expect(npc?.characters[0].portraitHash).toBeNull();
		expect(npc?.popup).not.toContain('<img');
	});

	it('names the furniture set of a Reliquary furnishing instead of calling it disabled', async () => {
		const spawns = await db.getSpawnPointMarkers(DETAIL_ZONE);
		const dummy = spawns.find((marker) => marker.stableKey === 'spawn:stowaway-dummy');

		expect(dummy).toMatchObject({
			category: 'npc',
			isEnabled: false,
			characters: [
				expect.objectContaining({
					name: 'Fixture Dummy',
					furniture: { name: 'Wood Training Set', wikiPageName: 'Wood Training Set' }
				})
			]
		});
		expect(dummy?.popup).toContain(
			"Appears when the player places the <a href='https://erenshor.wiki.gg/wiki/Wood%20Training%20Set'>Wood Training Set</a> in this room."
		);
		expect(dummy?.popup).not.toContain('disabled');
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
				portraitHash: null,
				level: 12,
				encounterTier: 'elite'
			}
		]);
	});

	it('loads all searchable items and the quest-unlocked vendor item', async () => {
		const items = await db.getAllItems();
		expect(items).toHaveLength(8);
		expect(items.every((item) => (item.wikiPageName?.trim().length ?? 0) > 0)).toBe(true);
		expect(items.find((item) => item.itemStableKey === 'item:furniture - enchanted smithy')).toEqual({
			itemStableKey: 'item:furniture - enchanted smithy',
			displayName: 'Enchanted Smithy',
			wikiPageName: 'Enchanted Smithy',
			iconHash: 'enchanted_smithy'
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
	it('derives reachable chest levels and guardian ranges from reading eligibility', async () => {
		const [hidden] = await db.getTreasureLocMarkers('Hidden');
		const [stowaway] = await db.getTreasureLocMarkers('Stowaway');
		const [blight] = await db.getTreasureLocMarkers('Blight');
		expect(hidden.minReadingLevel).toBe(1);
		expect(hidden.chests.map((c) => [c.name, c.digLevelMin, c.digLevelMax])).toEqual([
			['Lost Treasure (1-10)', 1, 9],
			['Lost Treasure (10-20)', 10, 19],
			['Lost Treasure (20-30)', 20, 29],
			['Lost Treasure (30+)', 30, 35]
		]);
		expect(stowaway.minReadingLevel).toBe(21);
		expect(stowaway.chests.map((c) => [c.digLevelMin, c.digLevelMax])).toEqual([[21, 29], [30, 35]]);
		expect(blight.minReadingLevel).toBe(31);
		expect(blight.chests.map((c) => [c.name, c.digLevelMin, c.digLevelMax])).toEqual([
			['Lost Treasure (30+)', 31, 35]
		]);
		for (const [site, min] of [[hidden, 2], [stowaway, 17], [blight, 27]] as const) {
			expect([site.levelMin, site.levelMax]).toEqual([min, 36]);
			expect(site.guardians.map((g) => [g.name, g.wikiPageName, g.levelMin, g.levelMax])).toEqual([
				['Ancient Demon', 'Ancient Demon', min, 36],
				['Ancient Horror', 'Ancient Horror', min, 36],
				['Ancient Skeleton', 'Ancient Skeleton', min, 36]
			]);
		}
	});

	it('finds only a chest’s possible sites and every guardian site', async () => {
		const sites: WorldTreasureLoc[] = (await Promise.all(['Hidden', 'Stowaway', 'Blight'].map(async (zone) =>
			(await db.getTreasureLocMarkers(zone)).map((marker) => ({
				...marker, zone, zoneName: zone,
				worldPosition: [marker.position.x, marker.position.y] as [number, number]
			}))
		))).flat();
		const searchIndex = buildSearchIndex({
			enemiesEnemy: [], enemiesElite: [], enemiesBoss: [], enemiesChest: [],
			unlocatedEnemies: await db.getUnlocatedEnemies(), treasureLocs: sites,
			npcs: [], zones: [], miningNodes: [], water: [], itemBags: [], itemSources: [], allItems: []
		});
		const provider = searchIndex.enemyProvider;
		for (const [name, expectedKeys] of [
			['Lost Treasure (1-10)', ['treasure:hidden-fixture']],
			['Lost Treasure (10-20)', ['treasure:hidden-fixture']],
			['Lost Treasure (20-30)', ['treasure:hidden-fixture', 'treasure:stowaway-fixture']],
			['Lost Treasure (30+)', sites.map((site) => site.stableKey)],
			...['Ancient Demon', 'Ancient Horror', 'Ancient Skeleton'].map((name) =>
				[name, sites.map((site) => site.stableKey)] as const)
		] as const) {
			const result = provider.getResult(name);
			expect(result).not.toBeNull();
			expect(result?.spawnCount).toBe(expectedKeys.length);
			expect(provider.buildIndex().some((entry) => entry.searchText === name.toLowerCase())).toBe(true);
			expect(provider.resolveHighlight(result!)).toMatchObject({ type: 'positions', stableKeys: expectedKeys });
			expect(provider.getUnlocated(name)).toEqual([]);
			expect(deserializeSelection(`enemy:${name}`, {
				findMarkerByStableKey: () => null, findZoneByKey: () => null, searchIndex
			})).toEqual({ type: 'search', result });
		}
	});
});

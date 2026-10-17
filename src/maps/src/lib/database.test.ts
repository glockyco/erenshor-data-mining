import { afterAll, beforeAll, describe, expect, it } from 'vitest';

import { getMapsDatabasePath } from './database-path.server';
import { Repository } from './database.node';
import { MAPS } from './maps';
import { buildSearchIndex, itemResultSummaryParts } from './map/search';
import { ItemSearchProvider } from './map/search/item-source-provider';
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

        expect(
            markerGroups
                .flat()
                .map((marker) => marker.category)
                .sort()
        ).toEqual([
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
            bosses: [{ name: 'Fixture Enemy', wikiPageName: 'Fixture Enemy', level: 7, levelMax: 7 }],
            elites: [],
            chests: [{ name: 'Fixture Chest', wikiPageName: 'Fixture Chest', level: 18, levelMax: 18 }]
        });
    });

    it('keeps chests in the character spawn category with their own tier', async () => {
        const spawns = await db.getSpawnPointMarkers(DETAIL_ZONE);
        expect(spawns.find((marker) => marker.stableKey === 'spawn:stowaway-chest')).toMatchObject({
            category: 'enemy',
            encounterTier: 'chest',
            characters: [
                expect.objectContaining({ name: 'Fixture Chest', encounterTier: 'chest' })
            ],
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
        expect(byName.get('Runtime Enemy')).toEqual([
            { stableKey: 'character:runtime enemy', scenes: [] }
        ]);
    });

    it('loads map-visible enemies without fixed spawn points', async () => {
        expect(await db.getUnlocatedEnemies()).toEqual([
            {
                stableKey: 'character:runtime enemy',
                name: 'Runtime Enemy',
                wikiPageName: 'Runtime Enemy',
                portraitHash: null,
                level: 12,
                levelMax: 12,
                encounterTier: 'elite'
            }
        ]);
    });

    it('loads searchable items and preserves canonical vendor unlocks', async () => {
        expect(await db.getAllItems()).toHaveLength(11);
        const rows = await db.getItemSources();
        expect(rows.find((row) => row.kind === 'vendor' && row.itemStableKey === 'item:furniture - enchanted smithy')).toMatchObject({
            characterStableKey: 'character:breena carpenter',
            provenance: { source_copy_stable_key: 'character:breena carpenter', conditions: [
                expect.objectContaining({ predicate: 'quest_done', reference_stable_key: 'quest:vendor-unlock' })
            ] }
        });
        expect(rows.some((row) => row.provenance.source_copy_stable_key === 'character:fixture enemy backup')).toBe(false);
        expect(rows.filter((row) => row.kind === 'character_drop').some((row) => row.itemStableKey === 'item:fixture key')).toBe(false);
    });

    it('keeps every persisted player acquisition kind and its route identity', async () => {
        const rows = await db.getItemSources();
        expect([...new Set(rows.map((row) => row.kind))].sort()).toEqual([
            'auction_house', 'character_drop', 'common_world_item', 'crafting', 'dialog', 'fishing',
            'item_bag', 'item_conversion', 'item_drop', 'mining', 'quest_reward',
            'special_world_drop', 'spell_created', 'starting_class', 'ui_grant', 'vendor'
        ]);
        const auctions = rows.filter((row) => row.kind === 'auction_house');
        expect(auctions.map((row) => row.provenance.variant_key).sort()).toEqual(['consumable', 'equipment']);
        expect(new Set(rows.map((row) => row.acquisitionKey)).size).toBe(rows.length);
        expect(rows.every((row) => row.acquisitionKey === row.provenance.acquisition_key &&
            row.originatingItemStableKey === row.provenance.item_stable_key)).toBe(true);
    });

    it('retains unlocated sources and conditional native UI grants without inventing markers', async () => {
        const rows = await db.getItemSources();
        const provider = new ItemSearchProvider(rows, [], [], [], [], await db.getAllItems());
        const ui = provider.getSourcesForItem('item:fixture relic').find((source) => source.kind === 'ui_grant')!;
        expect(ui.markers).toEqual([]);
        expect(ui.row.provenance).toMatchObject({
            player_access_state: 'verified_player', quantity_min: 1, quantity_max: 2,
            locations: [expect.objectContaining({ relation: 'unlocated', conditions: expect.arrayContaining([
                expect.objectContaining({ predicate: 'room_furnished', reference_slot: 'room:1' }),
                expect.objectContaining({ predicate: 'account_state', actor: 'account',
                    reference_stable_key: 'account_state:reliquary_claimed', value: 'false', phase: 'availability', scope: 'room:unlocated' }),
                expect.objectContaining({ predicate: 'account_state', value: 'true', phase: 'operation_outcome' })
            ]), entry_zone_line_keys: ['zone-line:stowaway-fixture'] })]
        });
        expect(provider.getResult('item:fixture relic')?.hasKnownSource).toBe(true);
        expect(provider.getMarkersForItem('item:fixture relic')).toEqual([]);
        expect(provider.getSourcesForItem('item:fixture relic').some((source) => source.kind === 'internal_equipment')).toBe(false);
    });

    it('carries hidden variants to exactly one visible alias without collapsing acquisition origins', async () => {
        const rows = (await db.getItemSources()).filter((row) => row.itemStableKey === 'item:fixture meditate');
        expect(rows).toHaveLength(3);
        expect(rows.map((row) => row.originatingItemStableKey).sort()).toEqual([
            'item:fixture meditate', 'item:fixture meditate dru', 'item:fixture meditate dru'
        ]);
        expect(new Set(rows.map((row) => row.acquisitionKey)).size).toBe(3);
        const provider = new ItemSearchProvider(rows, [], [], [], [], await db.getAllItems());
        expect(provider.getResult('item:fixture meditate dru')).toBeNull();
        expect(provider.getSourcesForItem('item:fixture meditate')).toHaveLength(3);
        expect(provider.getResult('item:fixture meditate')?.sourceCounts.vendors).toBe(2);
    });

    it('groups pure global fishing finals as Any water while retaining local enhanced rates and every member identity', async () => {
        const rows = (await db.getItemSources()).filter((row) => row.itemStableKey === 'item:fixture fish' && row.kind === 'fishing');
        const waters = (await Promise.all(['Stowaway', 'StowawayPortal', 'Brake'].map(async (zone) =>
            (await db.getWaterMarkers(zone)).map((marker) => ({ ...marker, zone, zoneName: zone,
                worldPosition: [marker.position.x, marker.position.y] as [number, number],
                worldPolygon: [[marker.position.x, marker.position.y],
                    [marker.position.x + marker.width, marker.position.y],
                    [marker.position.x + marker.width, marker.position.y + marker.height],
                    [marker.position.x, marker.position.y + marker.height]] as [number, number][] }))))).flat();
        const provider = new ItemSearchProvider(rows, [], [], waters, []);
        const sources = provider.getSourcesForItem('item:fixture fish');
        const grouped = sources.filter((source) => source.presentation === 'any_water');
        expect(grouped).toHaveLength(1);
        expect(grouped[0].members).toHaveLength(4);
        expect(grouped[0].markers).toEqual([]);
        expect(grouped[0].unlocated).toEqual([]);
        expect(grouped[0].members.every((row) => row.provenance.probability_min === 1.25 &&
            row.fishingBonus?.probability_stage === 'native_pool')).toBe(true);
        const local = sources.filter((source) => source.presentation === 'source');
        expect(local.map((source) => source.row.provenance.probability_min).sort()).toEqual([7.1875, 7.583333333333333]);
        expect(local.map((source) => source.row.provenance.conditions[0].value).sort()).toEqual(['day', 'night']);
        expect(provider.getMarkersForItem('item:fixture fish').map((marker) => marker.stableKey)).toEqual(['water:stowaway-fixture']);
        expect(provider.getResult('item:fixture fish')).toMatchObject({
            hasKnownSource: true, zoneCount: 1, sourceCounts: { fishingSpots: 1, anyWater: 1 }
        });
        expect(sources.flatMap((source) => source.members.map((member) => member.acquisitionKey)).sort()).toEqual(rows.map((row) => row.acquisitionKey).sort());
        const globalOnly = new ItemSearchProvider(grouped[0].members, [], [], waters, []);
        expect(globalOnly.getResult('item:fixture fish')).toMatchObject({ zoneCount: 0, sourceCounts: { fishingSpots: 0, anyWater: 1 } });
        expect(globalOnly.resolveHighlight(globalOnly.getResult('item:fixture fish')!)).toEqual({ type: 'none' });
        expect(itemResultSummaryParts(globalOnly.getResult('item:fixture fish')!)).toEqual(['Any water']);
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
        expect(stowaway.chests.map((c) => [c.digLevelMin, c.digLevelMax])).toEqual([
            [21, 29],
            [30, 35]
        ]);
        expect(blight.minReadingLevel).toBe(31);
        expect(blight.chests.map((c) => [c.name, c.digLevelMin, c.digLevelMax])).toEqual([
            ['Lost Treasure (30+)', 31, 35]
        ]);
        for (const [site, min] of [
            [hidden, 2],
            [stowaway, 17],
            [blight, 27]
        ] as const) {
            expect([site.levelMin, site.levelMax]).toEqual([min, 36]);
            expect(
                site.guardians.map((g) => [g.name, g.wikiPageName, g.levelMin, g.levelMax])
            ).toEqual([
                ['Ancient Demon', 'Ancient Demon', min, 36],
                ['Ancient Horror', 'Ancient Horror', min, 36],
                ['Ancient Skeleton', 'Ancient Skeleton', min, 36]
            ]);
        }
    });

    it('finds only a chest’s possible sites and every guardian site', async () => {
        const sites: WorldTreasureLoc[] = (
            await Promise.all(
                ['Hidden', 'Stowaway', 'Blight'].map(async (zone) =>
                    (await db.getTreasureLocMarkers(zone)).map((marker) => ({
                        ...marker,
                        zone,
                        zoneName: zone,
                        worldPosition: [marker.position.x, marker.position.y] as [number, number]
                    }))
                )
            )
        ).flat();
        const searchIndex = buildSearchIndex({
            enemiesEnemy: [],
            enemiesElite: [],
            enemiesBoss: [],
            enemiesChest: [],
            unlocatedEnemies: await db.getUnlocatedEnemies(),
            treasureLocs: sites,
            npcs: [],
            zones: [],
            miningNodes: [],
            water: [],
            itemBags: [],
            itemSources: await db.getItemSources(),
            allItems: await db.getAllItems()
        });
        const provider = searchIndex.enemyProvider;
        for (const [name, expectedKeys] of [
            ['Lost Treasure (1-10)', ['treasure:hidden-fixture']],
            ['Lost Treasure (10-20)', ['treasure:hidden-fixture']],
            ['Lost Treasure (20-30)', ['treasure:hidden-fixture', 'treasure:stowaway-fixture']],
            ['Lost Treasure (30+)', sites.map((site) => site.stableKey)],
            ...['Ancient Demon', 'Ancient Horror', 'Ancient Skeleton'].map(
                (name) => [name, sites.map((site) => site.stableKey)] as const
            )
        ] as const) {
            const result = provider.getResult(name);
            expect(result).not.toBeNull();
            expect(result?.spawnCount).toBe(expectedKeys.length);
            expect(
                provider.buildIndex().some((entry) => entry.searchText === name.toLowerCase())
            ).toBe(true);
            expect(provider.resolveHighlight(result!)).toMatchObject({
                type: 'positions',
                stableKeys: expectedKeys
            });
            expect(provider.getUnlocated(name)).toEqual([]);
            expect(
                deserializeSelection(`enemy:${name}`, {
                    findMarkerByStableKey: () => null,
                    findZoneByKey: () => null,
                    searchIndex
                })
            ).toEqual({ type: 'search', result });
        }
        const items = searchIndex.itemProvider;
        const reward = items.getResult('item:fixture treasure')!;
        expect(reward).toMatchObject({
            hasKnownSource: true, sourceCounts: { droppers: 2 }, zoneCount: 3
        });
        expect(items.getSourcesForItem(reward.itemStableKey)).toHaveLength(2);
        expect(items.getSourcesForItem(reward.itemStableKey).flatMap((source) => source.row.provenance.locations)).toEqual(
            expect.arrayContaining([expect.objectContaining({
                relation: 'possible_treasure', player_level_min: 21, player_level_max: 29,
                coordinate_stable_key: 'treasure:stowaway-fixture'
            })])
        );
        expect(items.resolveHighlight(reward)).toMatchObject({
            type: 'positions', stableKeys: expect.arrayContaining(sites.map((site) => site.stableKey))
        });
        expect(items.getMarkersForItem(reward.itemStableKey)).toHaveLength(3);
        expect(items.getSourcesForItem(reward.itemStableKey).every((source) =>
            source.row.provenance.locations.every((location) => location.relation === 'possible_treasure'))).toBe(true);
        const runtime = items.getResult('item:fixture runtime')!;
        expect(runtime).toMatchObject({
            hasKnownSource: true, zoneCount: 0, sourceCounts: { droppers: 1, vendors: 1 }
        });
        expect(items.getSourcesForItem(runtime.itemStableKey).every((source) => source.markers.length === 0)).toBe(true);
        expect(items.getSourcesForItem(runtime.itemStableKey).map((source) => source.row.sourceWikiPageName)).toEqual([
            'Runtime Enemy', 'Runtime Enemy'
        ]);
        expect(items.getResult('item:fixture meditate dru')).toBeNull();
        expect(items.getSourcesForItem('item:fixture meditate')).toHaveLength(3);
    });
});

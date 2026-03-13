import type { Database, SqlJsStatic } from 'sql.js/dist/sql-wasm.js';

import { Rarity } from './map-markers';
import type {
    AchievementTriggerMarker,
    CharacterDrop,
    DoorMarker,
    EnemyMarker,
    ForgeMarker,
    ItemBagMarker,
    MiningNodeMarker,
    MiningNodeItem,
    MovementData,
    NpcMarker,
    SecretPassageMarker,
    SpawnCharacter,
    TeleportMarker,
    TreasureLocMarker,
    VendorItem,
    WaterMarker,
    WishingWellMarker,
    ZoneLineMarker
} from './map-markers';

function formatCoordinates(x: number, y: number, z: number): string {
    return `(X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}, Z: ${z.toFixed(2)})`;
}

function formatWikiLink(label: string, pageName: string | null): string {
    if (!pageName) return label;
    return `<a href='https://erenshor.wiki.gg/wiki/${encodeURIComponent(pageName)}'>${label}</a>`;
}

// Parse patrol path string "x1,z1;x2,z2;..." into local coordinate pairs [x, z]
// Note: z becomes y on the 2D map (game Y is height, ignored)
function parsePatrolPath(patrolPath: string | null): [number, number][] | null {
    if (!patrolPath) return null;
    const waypoints: [number, number][] = [];
    for (const point of patrolPath.split(';')) {
        const [x, z] = point.split(',').map(Number);
        if (!isNaN(x) && !isNaN(z)) {
            waypoints.push([x, z]);
        }
    }
    return waypoints.length > 0 ? waypoints : null;
}

// Build movement data from spawn point fields
function buildMovementData(
    wanderRange: number | null,
    loopPatrol: boolean,
    patrolPath: string | null
): MovementData | null {
    const patrolWaypoints = parsePatrolPath(patrolPath);
    if (!wanderRange && !patrolWaypoints) return null;
    return {
        wanderRange,
        patrolWaypoints,
        loopPatrol
    };
}

export class RepositoryBase {
    protected SQL: SqlJsStatic | null = null;
    protected db: Database | null = null;

    async getAchievementTriggerMarkers(mapName: string): Promise<AchievementTriggerMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                at.stable_key AS StableKey,
                at.x AS PositionX,
                at.y AS PositionY,
                at.z AS PositionZ,
                at.achievement_name AS AchievementName
            FROM achievement_triggers at
            WHERE at.scene = ?
        `,
            [mapName]
        );

        const markers: AchievementTriggerMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const achievementName = row.AchievementName as string;
            markers.push({
                stableKey: row.StableKey as string,
                category: 'achievement-trigger',
                achievementName,
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: `Achievement @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}<br><br>${achievementName}`
            });
        }
        stmt.free();
        return markers;
    }

    getNpcMarker(
        stableKey: string,
        characters: SpawnCharacter[],
        coordinates: { x: number; y: number; z: number },
        position: { x: number; y: number },
        spawnDelay: number | null,
        isEnabled: boolean,
        isNightSpawn: boolean,
        movement: MovementData | null = null
    ): NpcMarker {
        const sortedCharacters = characters.slice().sort((a, b) => b.spawnChance - a.spawnChance);

        const characterLines =
            '<br><br>' +
            sortedCharacters
                .map((character) => {
                    return formatWikiLink(character.name, character.wikiPageName);
                })
                .join('<br>');

        const positionText = `NPC @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;
        const disabledInfo = isEnabled ? '' : '<br><br>This NPC is (initially) disabled.';
        const respawnInfo = this.getRespawnInfo(spawnDelay, isNightSpawn);

        const popupText = `${positionText}${characterLines}${disabledInfo}${respawnInfo}`.trim();

        return {
            stableKey: stableKey,
            category: 'npc',
            characters: sortedCharacters,
            spawnDelay,
            isNightSpawn,
            position: position,
            popup: popupText.trim(),
            isEnabled: isEnabled,
            movement
        };
    }

    async getDoorMarkers(mapName: string): Promise<DoorMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                d.stable_key AS StableKey,
                d.x AS PositionX,
                d.y AS PositionY,
                d.z AS PositionZ,
                i.display_name AS ItemName,
                i.wiki_page_name AS ItemWikiPageName
            FROM doors d
            JOIN items i ON d.key_item_stable_key = i.stable_key
            WHERE d.scene = ? AND d.key_item_stable_key IS NOT NULL AND i.display_name != ''
        `,
            [mapName]
        );

        const markers: DoorMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const keyItemName = row.ItemName as string;
            const keyItemWikiPageName = row.ItemWikiPageName as string | null;

            const positionText = `Locked Door @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const keyText = `<br><br>Requires ${formatWikiLink(keyItemName, keyItemWikiPageName)} to unlock.`;

            const popupText = `${positionText}${keyText}`;

            markers.push({
                stableKey: row.StableKey as string,
                category: 'door',
                keyItemName,
                keyItemWikiPageName,
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: popupText
            });
        }
        stmt.free();
        return markers;
    }

    async getForgeMarkers(mapName: string): Promise<ForgeMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                f.stable_key AS StableKey,
                f.x AS PositionX,
                f.y AS PositionY,
                f.z AS PositionZ
            FROM forges f
            WHERE f.scene = ?
        `,
            [mapName]
        );

        const markers: ForgeMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();

            const positionText = `Forge @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const descriptionText =
                '<br><br>A <a href="https://erenshor.wiki.gg/wiki/Forge">Forge</a> you can <a href="https://erenshor.wiki.gg/wiki/Crafting">craft</a> at.';
            const popupText = `${positionText}${descriptionText}`;

            markers.push({
                stableKey: row.StableKey as string,
                category: 'forge',
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: popupText
            });
        }
        stmt.free();
        return markers;
    }

    async getItemBagMarkers(mapName: string): Promise<ItemBagMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                ib.stable_key AS StableKey,
                ib.x AS PositionX,
                ib.y AS PositionY,
                ib.z AS PositionZ,
                i.display_name AS ItemName,
                i.wiki_page_name AS ItemWikiPageName,
                ib.respawns AS Respawns,
                ib.respawn_timer AS RespawnTimer
            FROM item_bags ib
            JOIN items i ON i.stable_key = ib.item_stable_key
            WHERE ib.scene = ?
        `,
            [mapName]
        );

        const markers: ItemBagMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const itemName = row.ItemName as string;
            const respawnTimer = row.RespawnTimer as number;
            const itemWikiPageName = row.ItemWikiPageName as string | null;
            const respawns = !!row.Respawns;

            const positionText = `Item Bag @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const itemText = `<br><br>Contains ${formatWikiLink(itemName, itemWikiPageName)}.`;

            const respawnText =
                respawnTimer > 0
                    ? `<br><br>Respawns after ca. ${this.convertToMinutesAndSeconds(respawnTimer)} or when re-entering the zone.`
                    : '<br><br>Respawns when re-entering the zone.';

            const popupText = `${positionText}${itemText}${respawnText}`;

            markers.push({
                stableKey: row.StableKey as string,
                category: 'item-bag',
                itemName,
                itemWikiPageName,
                respawnTimer,
                respawns,
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: popupText
            });
        }
        stmt.free();
        return markers;
    }

    async getMiningNodeMarkers(mapName: string): Promise<MiningNodeMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                m.stable_key AS StableKey,
                m.x AS PositionX,
                m.y AS PositionY,
                m.z AS PositionZ,
                m.respawn_time AS RespawnTime,
                i.display_name AS ItemName,
                i.wiki_page_name AS ItemWikiPageName,
                mi.drop_chance AS DropChance
            FROM mining_nodes m
            JOIN mining_node_items mi ON mi.mining_node_stable_key = m.stable_key
            JOIN items i ON i.stable_key = mi.item_stable_key
            WHERE m.scene = ?
        `,
            [mapName]
        );

        // Group by mining node stable key
        const nodeMap = new Map<
            string,
            {
                stableKey: string;
                position: { x: number; y: number };
                coordinates: { x: number; y: number; z: number };
                respawnTime: number;
                items: MiningNodeItem[];
            }
        >();

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const stableKey = row.StableKey as string;
            if (!nodeMap.has(stableKey)) {
                nodeMap.set(stableKey, {
                    stableKey: stableKey,
                    position: {
                        x: row.PositionX as number,
                        y: row.PositionZ as number
                    },
                    coordinates: {
                        x: row.PositionX as number,
                        y: row.PositionY as number,
                        z: row.PositionZ as number
                    },
                    respawnTime: row.RespawnTime as number,
                    items: []
                });
            }
            nodeMap.get(stableKey)!.items.push({
                name: row.ItemName as string,
                wikiPageName: row.ItemWikiPageName as string | null,
                dropChance: row.DropChance as number
            });
        }
        stmt.free();

        // Build markers with popup lines for each item
        const markers: MiningNodeMarker[] = [];
        for (const { stableKey, position, coordinates, respawnTime, items } of nodeMap.values()) {
            const sortedItems = items.slice().sort((a, b) => b.dropChance - a.dropChance);

            const itemLines = sortedItems
                .map(
                    (item) =>
                        `${formatWikiLink(item.name, item.wikiPageName)} (${Number(item.dropChance).toFixed(1)}%)`
                )
                .join('<br>');

            markers.push({
                stableKey: stableKey,
                category: 'mining-node',
                items: sortedItems,
                respawnTime,
                position,
                popup: `Mining Node @ ${formatCoordinates(
                    coordinates.x,
                    coordinates.y,
                    coordinates.z
                )}<br><br>${itemLines}<br><br>Respawns after ca. ${this.convertToMinutesAndSeconds(respawnTime)} or when re-entering the zone.`
            });
        }
        return markers;
    }

    async getSecretPassageMarkers(mapName: string): Promise<SecretPassageMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const descriptionMap: Record<string, string> = {
            HiddenDoor: 'A hidden door you can click to open.',
            IllusoryWall: 'An illusory wall you can walk through.',
            InvisibleFloor: 'An invisible floor you can walk on.'
        };

        const stmt = this.db.prepare(
            `
        SELECT
            sp.stable_key AS StableKey,
            sp.x AS PositionX,
            sp.y AS PositionY,
            sp.z AS PositionZ,
            sp.type AS Type
        FROM secret_passages sp
        WHERE sp.scene = ? AND (sp.object_name NOT LIKE '%nav%' OR sp.object_name IS NULL)
    `,
            [mapName]
        );

        const markers: SecretPassageMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const passageType = row.Type as string;

            const positionText = `Secret Passage @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const descriptionText = descriptionMap[passageType] || '';
            const popupText = `${positionText}<br><br>${descriptionText}`;

            markers.push({
                stableKey: row.StableKey as string,
                category: 'secret-passage',
                passageType,
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: popupText
            });
        }
        stmt.free();
        return markers;
    }

    async getSpawnPointMarkers(mapName: string): Promise<(NpcMarker | EnemyMarker)[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            WITH rep_groups AS (
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.is_map_visible = 1
                GROUP BY d.group_key
            )
            SELECT
                cs.spawn_point_stable_key       AS StableKey,
                cs.x                            AS PositionX,
                cs.y                            AS PositionY,
                cs.z                            AS PositionZ,
                cs.spawn_delay_4                AS SpawnDelay,
                cs.is_enabled                   AS IsEnabled,
                cs.night_spawn                  AS IsNightSpawn,
                cs.random_wander_range          AS WanderRange,
                cs.loop_patrol                  AS LoopPatrol,
                (SELECT GROUP_CONCAT(pp.x || ',' || pp.z, ';')
                 FROM spawn_point_patrol_points pp
                 WHERE pp.spawn_point_stable_key = cs.spawn_point_stable_key
                 ORDER BY pp.sequence_index)     AS PatrolPath,
                rep.display_name                AS NPCName,
                rep.wiki_page_name              AS WikiPageName,
                rep.stable_key                  AS CharacterStableKey,
                rep.level                       AS Level,
                rep.is_vendor                   AS IsVendor,
                rep.has_dialog                  AS HasDialog,
                rep.invulnerable                AS Invulnerable,
                sum(cs.spawn_chance)            AS SpawnChance,
                rep.is_common                   AS IsCommon,
                rep.is_rare                     AS IsRare,
                rep.is_unique                   AS IsUnique,
                min(rep.is_friendly)            AS IsFriendly
            FROM rep_groups rg
            JOIN characters rep ON rep.stable_key = rg.rep_stable_key
            JOIN character_deduplications d ON d.group_key = rg.group_key AND d.is_map_visible = 1
            JOIN map_character_spawns cs ON cs.character_stable_key = d.member_stable_key
            WHERE cs.scene = ? AND cs.spawn_chance > 0 AND cs.spawn_point_stable_key IS NOT NULL
            GROUP BY cs.spawn_point_stable_key, rep.stable_key
        `,
            [mapName]
        );

        // Group by spawn point stable key
        const spawnPointMap = new Map<
            string,
            {
                stableKey: string;
                position: { x: number; y: number };
                coordinates: { x: number; y: number; z: number };
                spawnDelay: number;
                isEnabled: boolean;
                isNightSpawn: boolean;
                wanderRange: number | null;
                loopPatrol: boolean;
                patrolPath: string | null;
                characters: SpawnCharacter[];
            }
        >();

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const stableKey = row.StableKey as string;
            if (!spawnPointMap.has(stableKey)) {
                spawnPointMap.set(stableKey, {
                    stableKey: stableKey,
                    position: {
                        x: row.PositionX as number,
                        y: row.PositionZ as number
                    },
                    coordinates: {
                        x: row.PositionX as number,
                        y: row.PositionY as number,
                        z: row.PositionZ as number
                    },
                    spawnDelay: row.SpawnDelay as number,
                    isEnabled: !!row.IsEnabled,
                    isNightSpawn: !!row.IsNightSpawn,
                    wanderRange: (row.WanderRange as number) || null,
                    loopPatrol: !!row.LoopPatrol,
                    patrolPath: (row.PatrolPath as string) || null,
                    characters: []
                });
            }
            spawnPointMap.get(stableKey)!.characters.push({
                name: row.NPCName as string,
                wikiPageName: row.WikiPageName as string | null,
                stableKey: row.CharacterStableKey as string,
                level: (row.Level as number) ?? 1,
                spawnChance: row.SpawnChance as number,
                isCommon: !!row.IsCommon,
                isRare: !!row.IsRare,
                isUnique: !!row.IsUnique,
                effectiveRarity: row.IsUnique
                    ? Rarity.unique
                    : !!row.IsRare && !row.IsCommon
                      ? Rarity.rare
                      : Rarity.common,
                isFriendly: !!row.IsFriendly,
                isInvulnerable: !!row.Invulnerable,
                isVendor: !!row.IsVendor,
                hasDialog: !!row.HasDialog
            });
        }

        // Build markers with popup lines for each character
        const markers: (NpcMarker | EnemyMarker)[] = [];
        for (const {
            stableKey,
            position,
            coordinates,
            spawnDelay,
            isEnabled,
            isNightSpawn,
            wanderRange,
            loopPatrol,
            patrolPath,
            characters
        } of spawnPointMap.values()) {
            const movement = buildMovementData(wanderRange, loopPatrol, patrolPath);
            const isNpc = characters.every((c) => c.isFriendly);
            if (isNpc) {
                markers.push(
                    this.getNpcMarker(
                        stableKey,
                        characters,
                        coordinates,
                        position,
                        spawnDelay,
                        isEnabled,
                        isNightSpawn,
                        movement
                    )
                );
            } else {
                markers.push(
                    this.getEnemyMarker(
                        stableKey,
                        characters,
                        coordinates,
                        position,
                        spawnDelay,
                        isEnabled,
                        isNightSpawn,
                        movement
                    )
                );
            }
        }
        return markers;
    }

    getEnemyMarker(
        stableKey: string,
        characters: SpawnCharacter[],
        coordinates: { x: number; y: number; z: number },
        position: { x: number; y: number },
        spawnDelay: number | null,
        isEnabled: boolean,
        isNightSpawn: boolean,
        movement: MovementData | null = null
    ): EnemyMarker {
        const sortedCharacters = characters.slice().sort((a, b) => b.spawnChance - a.spawnChance);

        const characterLines =
            '<br><br>' +
            sortedCharacters
                .map((character) => {
                    let tag = '';
                    if (character.isUnique) tag += ' (Unique)';
                    else if (character.isRare && !character.isCommon) tag += ' (Rare)';

                    return `${formatWikiLink(character.name, character.wikiPageName)} (${Number(character.spawnChance).toFixed(1)}%)${tag}`;
                })
                .join('<br>');

        const positionText = `Enemy @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;
        const disabledText = isEnabled ? '' : '<br><br>This enemy is (initially) disabled.';
        const respawnInfo = this.getRespawnInfo(spawnDelay, isNightSpawn);
        const popupText = `${positionText}${characterLines}${disabledText}${respawnInfo}`;

        const isUnique = characters.some((c) => c.isUnique);
        const isRare = characters.some((c) => c.isRare && !c.isCommon);

        return {
            stableKey: stableKey,
            category: 'enemy',
            characters: sortedCharacters,
            spawnDelay,
            isNightSpawn,
            position: position,
            popup: popupText,
            isEnabled: isEnabled,
            isUnique: isUnique,
            isRare: isRare,
            movement
        };
    }

    getRespawnInfo(spawnDelay: number | null, isNightSpawn: boolean): string {
        const spawnDelayInfo = spawnDelay
            ? `Respawns after ca. ${this.convertToMinutesAndSeconds(spawnDelay)}.`
            : 'Respawns when re-entering the zone.';

        if (isNightSpawn) {
            return `<br><br>Only spawns at night.<br>${spawnDelayInfo}`;
        } else {
            return `<br><br>${spawnDelayInfo}`;
        }
    }

    async getTeleportMarkers(mapName: string): Promise<TeleportMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                t.stable_key AS StableKey,
                t.x AS PositionX,
                t.y AS PositionY,
                t.z AS PositionZ,
                i.display_name AS ItemName,
                i.wiki_page_name AS ItemWikiPageName
            FROM teleports t
            JOIN items i ON i.stable_key = t.teleport_item_stable_key
            WHERE t.scene = ?
        `,
            [mapName]
        );

        const markers: TeleportMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const teleportItemName = row.ItemName as string;
            const teleportItemWikiPageName = row.ItemWikiPageName as string | null;

            const positionText = `Teleport Destination @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const teleportText = `<br><br>Use ${formatWikiLink(teleportItemName, teleportItemWikiPageName)} to teleport here.`;

            const popupText = `${positionText}${teleportText}`;

            markers.push({
                stableKey: row.StableKey as string,
                category: 'teleport',
                teleportItemName,
                teleportItemWikiPageName,
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: popupText
            });
        }
        stmt.free();
        return markers;
    }

    async getTreasureLocMarkers(mapName: string): Promise<TreasureLocMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                tl.stable_key AS StableKey,
                tl.x AS PositionX,
                tl.y AS PositionY,
                tl.z AS PositionZ
            FROM treasure_locations tl
            WHERE tl.scene = ?
        `,
            [mapName]
        );

        const markers: TreasureLocMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();

            const positionText = `Lost Treasure @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const treasureHuntingText = `<br><br>See <a href='https://erenshor.wiki.gg/wiki/Treasure_Hunting'>Treasure Hunting</a> on the Erenshor Wiki.`;

            const popupText = `${positionText}${treasureHuntingText}`;

            markers.push({
                stableKey: row.StableKey as string,
                category: 'treasure-loc',
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: popupText
            });
        }
        stmt.free();
        return markers;
    }

    async getWaterMarkers(mapName: string): Promise<WaterMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                w.stable_key AS StableKey,
                w.x AS PositionX,
                w.y AS PositionY,
                w.z AS PositionZ,
                w.width AS Width,
                w.depth AS Depth,
                wf.type AS Type,
                i.display_name AS ItemName,
                i.wiki_page_name AS ItemWikiPageName,
                wf.drop_chance AS DropChance
            FROM waters w
            JOIN water_fishables wf ON wf.water_stable_key = w.stable_key
            JOIN items i ON i.stable_key = wf.item_stable_key
            WHERE w.scene = ?
        `,
            [mapName]
        );

        // Group by water stable key
        const waterMap = new Map<
            string,
            {
                stableKey: string;
                position: { x: number; y: number };
                coordinates: { x: number; y: number; z: number };
                width: number;
                height: number;
                daytimeItems: { name: string; wikiPageName: string | null; dropChance: number }[];
                nighttimeItems: { name: string; wikiPageName: string | null; dropChance: number }[];
            }
        >();

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const stableKey = row.StableKey as string;
            if (!waterMap.has(stableKey)) {
                waterMap.set(stableKey, {
                    stableKey: stableKey,
                    position: {
                        x: row.PositionX as number,
                        y: row.PositionZ as number
                    },
                    coordinates: {
                        x: row.PositionX as number,
                        y: row.PositionY as number,
                        z: row.PositionZ as number
                    },
                    width: row.Width as number,
                    height: row.Depth as number,
                    daytimeItems: [],
                    nighttimeItems: []
                });
            }

            const itemInfo = {
                name: row.ItemName as string,
                wikiPageName: row.ItemWikiPageName as string | null,
                dropChance: row.DropChance as number
            };

            if (row.Type === 'DayFishable') {
                waterMap.get(stableKey)!.daytimeItems.push(itemInfo);
            } else if (row.Type === 'NightFishable') {
                waterMap.get(stableKey)!.nighttimeItems.push(itemInfo);
            }
        }
        stmt.free();

        // Build markers with popup lines for each item
        const markers: WaterMarker[] = [];
        for (const {
            stableKey,
            position,
            coordinates,
            width,
            height,
            daytimeItems,
            nighttimeItems
        } of waterMap.values()) {
            const sortByChanceAndName = (
                a: { dropChance: number; name: string },
                b: { dropChance: number; name: string }
            ) => {
                return b.dropChance - a.dropChance || a.name.localeCompare(b.name);
            };

            const sortedDaytimeItems = daytimeItems.slice().sort(sortByChanceAndName);
            const sortedNighttimeItems = nighttimeItems.slice().sort(sortByChanceAndName);

            const daytimeItemLines = sortedDaytimeItems
                .map(
                    (item) =>
                        `${formatWikiLink(item.name, item.wikiPageName)} (${Number(item.dropChance).toFixed(1)}%)`
                )
                .join('<br>');

            const nighttimeItemLines = sortedNighttimeItems
                .map(
                    (item) =>
                        `${formatWikiLink(item.name, item.wikiPageName)} (${Number(item.dropChance).toFixed(1)}%)`
                )
                .join('<br>');

            const positionText = `Fishable Water @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;

            const popupText = `${positionText}<br><br>Fishable at daytime: <br>${daytimeItemLines}<br><br>Fishable at nighttime: <br>${nighttimeItemLines}`;

            markers.push({
                stableKey: stableKey,
                category: 'water',
                position,
                width,
                height,
                daytimeItems: sortedDaytimeItems,
                nighttimeItems: sortedNighttimeItems,
                popup: popupText
            });
        }
        return markers;
    }

    async getWishingWellMarkers(mapName: string): Promise<WishingWellMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                ww.stable_key AS StableKey,
                ww.x AS PositionX,
                ww.y AS PositionY,
                ww.z AS PositionZ
            FROM wishing_wells ww
            WHERE ww.scene = ?
        `,
            [mapName]
        );

        const markers: WishingWellMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();

            const positionText = `Wishing Well @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const descriptionText =
                '<br><br>A <a href="https://erenshor.wiki.gg/wiki/Wishing_Well">Wishing Well</a> you can set your respawn point at.';
            const popupText = `${positionText}${descriptionText}`;

            markers.push({
                stableKey: row.StableKey as string,
                category: 'wishing-well',
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: popupText
            });
        }
        stmt.free();
        return markers;
    }

    async getZoneLineMarkers(mapName: string): Promise<ZoneLineMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                zl.stable_key AS StableKey,
                zl.x AS PositionX,
                zl.y AS PositionY,
                zl.z AS PositionZ,
                zl.is_enabled AS IsEnabled,
                zl.landing_position_x AS LandingPositionX,
                zl.landing_position_y AS LandingPositionY,
                zl.landing_position_z AS LandingPositionZ,
                z.scene_name AS DestinationZone,
                z.display_name AS ZoneName,
                z.is_map_visible AS IsMapVisible,
                zae.level_range_low AS LevelRangeLow,
                zae.level_range_high AS LevelRangeHigh
            FROM zone_lines zl
            JOIN zones z ON z.stable_key = zl.destination_zone_stable_key
            LEFT JOIN zone_atlas_entries zae ON zae.zone_name = z.scene_name
            WHERE zl.scene = ?
        `,
            [mapName]
        );

        const markers: ZoneLineMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const disabledText = row.IsEnabled
                ? ''
                : '<br><br>This zone connection is (initially) disabled.';
            const levelRange =
                row.LevelRangeLow && row.LevelRangeHigh
                    ? ` (Level: ${row.LevelRangeLow}-${row.LevelRangeHigh})`
                    : '';

            const isMapVisible = !!row.IsMapVisible;

            // Remove links for ShiveringTomb zones and show consistent name
            const destinationZone = row.DestinationZone as string;
            let zoneLink: string;
            if (!isMapVisible) {
                zoneLink = row.ZoneName as string;
            } else if (
                destinationZone === 'ShiveringTomb' ||
                destinationZone === 'ShiveringTomb2'
            ) {
                zoneLink = 'Shivering Tomb';
            } else {
                zoneLink = `<a href='/${destinationZone}'>${row.ZoneName}</a>`;
            }

            markers.push({
                stableKey: row.StableKey as string,
                category: 'zone-line',
                position: {
                    x: row.PositionX as number,
                    y: row.PositionZ as number
                },
                popup: `Zone Connection @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}<br><br>${zoneLink}${levelRange}${disabledText}`,
                destinationZone: row.DestinationZone as string,
                destinationZoneName: row.ZoneName as string,
                landingPosition: {
                    x: row.LandingPositionX as number,
                    y: row.LandingPositionY as number,
                    z: row.LandingPositionZ as number
                },
                levelRangeLow: row.LevelRangeLow as number | null,
                levelRangeHigh: row.LevelRangeHigh as number | null,
                isEnabled: !!row.IsEnabled
            });
        }
        stmt.free();
        return markers;
    }

    convertToMinutesAndSeconds = (seconds: number) => {
        const minutes = Math.floor(seconds / 60);
        const remainingSeconds = Math.round(seconds % 60);

        if (minutes > 0 && remainingSeconds > 0) {
            return `${minutes} min ${remainingSeconds} sec`;
        } else if (minutes > 0) {
            return `${minutes} min`;
        } else if (remainingSeconds > 0) {
            return `${remainingSeconds} sec`;
        } else {
            return 'an unknown time';
        }
    };

    async getZoneNorthBearing(mapName: string): Promise<number> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT north_bearing AS NorthBearing
            FROM zones
            WHERE scene_name = ?
        `,
            [mapName]
        );

        if (stmt.step()) {
            const row = stmt.getAsObject();
            stmt.free();
            return row.NorthBearing as number;
        }
        stmt.free();
        return 0; // Default to 0 if not found
    }

    async getAllZoneNorthBearings(): Promise<Record<string, number>> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(`
			SELECT scene_name AS SceneName, north_bearing AS NorthBearing
			FROM zones
		`);

        const bearings: Record<string, number> = {};

        while (stmt.step()) {
            const row = stmt.getAsObject();
            bearings[row.SceneName as string] = row.NorthBearing as number;
        }
        stmt.free();
        return bearings;
    }

    async getDropsForCharacter(stableKey: string): Promise<CharacterDrop[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT
                i.display_name AS itemName,
                ld.drop_probability AS dropProbability
            FROM loot_drops ld
            JOIN items i ON i.stable_key = ld.item_stable_key
            WHERE ld.character_stable_key = ?
            ORDER BY ld.drop_probability DESC
            LIMIT 10
        `,
            [stableKey]
        );

        const drops: CharacterDrop[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            drops.push({
                itemName: row.itemName as string,
                dropProbability: row.dropProbability as number
            });
        }
        stmt.free();
        return drops;
    }

    async getVendorItems(stableKey: string): Promise<VendorItem[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT i.display_name AS ItemName, i.item_value AS ItemValue
            FROM character_vendor_items cvi
            JOIN items i ON i.stable_key = cvi.item_stable_key
            WHERE cvi.character_stable_key = ?
            ORDER BY i.display_name
            `,
            [stableKey]
        );

        const items: VendorItem[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            items.push({
                name: row.ItemName as string,
                price: (row.ItemValue as number) ?? 0
            });
        }
        stmt.free();
        return items;
    }

    async getCharacterByName(name: string): Promise<{ stableKey: string } | null> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            WITH reps AS (
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.is_map_visible = 1
                GROUP BY d.group_key
            )
            SELECT c.stable_key AS StableKey
            FROM reps r
            JOIN characters c ON c.stable_key = r.rep_stable_key
            WHERE c.display_name = ?
            ORDER BY c.stable_key
            LIMIT 1
            `,
            [name]
        );

        if (stmt.step()) {
            const row = stmt.getAsObject();
            stmt.free();
            return { stableKey: row.StableKey as string };
        }

        stmt.free();
        return null;
    }

    async getZoneEnemyInfo(zoneName: string): Promise<{
        levelRange: { min: number; max: number } | null;
        uniques: { name: string; wikiPageName: string | null; level: number }[];
        rares: { name: string; wikiPageName: string | null; level: number }[];
    }> {
        if (!this.db) throw new Error('DB not initialized');

        // Query level range from both directly placed and spawn point enemies
        const levelStmt = this.db.prepare(
            `
            WITH rep_groups AS (
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.is_map_visible = 1
                GROUP BY d.group_key
            ),
            zone_groups AS (
                SELECT DISTINCT d.group_key
                FROM character_deduplications d
                JOIN map_character_spawns cs ON cs.character_stable_key = d.member_stable_key
                WHERE cs.scene = ? AND d.is_map_visible = 1
            ),
            zone_reps AS (
                SELECT rg.rep_stable_key
                FROM rep_groups rg
                JOIN zone_groups zg ON zg.group_key = rg.group_key
            )
            SELECT MIN(c.level) as MinLevel, MAX(c.level) as MaxLevel
            FROM characters c
            WHERE c.stable_key IN (SELECT rep_stable_key FROM zone_reps)
              AND c.is_friendly = 0
            `,
            [zoneName]
        );

        let levelRange: { min: number; max: number } | null = null;
        if (levelStmt.step()) {
            const row = levelStmt.getAsObject();
            const minLevel = row.MinLevel as number | null;
            const maxLevel = row.MaxLevel as number | null;
            if (minLevel !== null && maxLevel !== null) {
                levelRange = { min: minLevel, max: maxLevel };
            }
        }
        levelStmt.free();

        // Query unique enemies
        const uniqueStmt = this.db.prepare(
            `
            WITH rep_groups AS (
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.is_map_visible = 1
                GROUP BY d.group_key
            ),
            zone_groups AS (
                SELECT DISTINCT d.group_key
                FROM character_deduplications d
                JOIN map_character_spawns cs ON cs.character_stable_key = d.member_stable_key
                WHERE cs.scene = ? AND d.is_map_visible = 1
            ),
            zone_reps AS (
                SELECT rg.rep_stable_key
                FROM rep_groups rg
                JOIN zone_groups zg ON zg.group_key = rg.group_key
            )
            SELECT c.display_name AS NPCName, c.wiki_page_name AS WikiPageName, c.level AS Level
            FROM characters c
            WHERE c.stable_key IN (SELECT rep_stable_key FROM zone_reps)
              AND c.is_friendly = 0
              AND c.is_unique = 1
            ORDER BY c.level, c.display_name
            `,
            [zoneName]
        );

        const uniques: { name: string; wikiPageName: string | null; level: number }[] = [];
        while (uniqueStmt.step()) {
            const row = uniqueStmt.getAsObject();
            uniques.push({
                name: row.NPCName as string,
                wikiPageName: row.WikiPageName as string | null,
                level: row.Level as number
            });
        }
        uniqueStmt.free();

        // Query rare enemies (exclude uniques)
        const rareStmt = this.db.prepare(
            `
            WITH rep_groups AS (
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.is_map_visible = 1
                GROUP BY d.group_key
            ),
            zone_groups AS (
                SELECT DISTINCT d.group_key
                FROM character_deduplications d
                JOIN map_character_spawns cs ON cs.character_stable_key = d.member_stable_key
                WHERE cs.scene = ? AND d.is_map_visible = 1
            ),
            zone_reps AS (
                SELECT rg.rep_stable_key
                FROM rep_groups rg
                JOIN zone_groups zg ON zg.group_key = rg.group_key
            )
            SELECT c.display_name AS NPCName, c.wiki_page_name AS WikiPageName, c.level AS Level
            FROM characters c
            WHERE c.stable_key IN (SELECT rep_stable_key FROM zone_reps)
              AND c.is_friendly = 0
              AND c.is_rare = 1
              AND c.is_unique = 0
            ORDER BY c.level, c.display_name
            `,
            [zoneName]
        );

        const rares: { name: string; wikiPageName: string | null; level: number }[] = [];
        while (rareStmt.step()) {
            const row = rareStmt.getAsObject();
            rares.push({
                name: row.NPCName as string,
                wikiPageName: row.WikiPageName as string | null,
                level: row.Level as number
            });
        }
        rareStmt.free();

        return { levelRange, uniques, rares };
    }
}

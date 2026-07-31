import type { Database, SqlJsStatic } from 'sql.js/dist/sql-wasm.js';

import { Rarity } from './map-markers';
import type {
    AchievementTriggerMarker,
    CharacterDrop,
    DoorMarker,
    EnemyMarker,
    ForgeMarker,
    ItemBagMarker,
    ItemSourceItemMeta,
    ItemSourceRow,
    MiningNodeMarker,
    MiningNodeItem,
    MovementData,
    NpcMarker,
    SecretPassageMarker,
    SpawnCharacter,
    TeleportMarker,
    TreasureLocMarker,
    UnlocatedEnemy,
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
        const sortedCharacters = characters
            .slice()
            .sort((a, b) => (b.spawnChance ?? 0) - (a.spawnChance ?? 0));

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
        WHERE sp.scene = ? AND sp.is_excluded = 0
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

    async getUnlocatedEnemies(): Promise<UnlocatedEnemy[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(`
            WITH rep_groups AS (
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.is_map_visible = 1
                GROUP BY d.group_key
            )
            SELECT
                rep.stable_key AS StableKey,
                rep.display_name AS Name,
                rep.wiki_page_name AS WikiPageName,
                rep.level AS Level,
                rep.is_common AS IsCommon,
                rep.is_rare AS IsRare,
                rep.is_unique AS IsUnique
            FROM rep_groups rg
            JOIN characters rep ON rep.stable_key = rg.rep_stable_key
            WHERE rep.is_friendly = 0
              AND NOT EXISTS (
                  SELECT 1
                  FROM character_deduplications d
                  JOIN map_character_spawns cs
                    ON cs.character_stable_key = d.member_stable_key
                  WHERE d.group_key = rg.group_key
                    AND d.is_map_visible = 1
                    AND (cs.spawn_chance > 0 OR cs.source_script IS NOT NULL)
                    AND cs.spawn_point_stable_key IS NOT NULL
              )
              AND NOT EXISTS (
                  SELECT 1
                  FROM spells sp
                  WHERE sp.pet_to_summon_stable_key = rep.stable_key
              )
            ORDER BY rep.display_name, rep.stable_key
        `);

        const enemies: UnlocatedEnemy[] = [];
        while (stmt.step()) {
            const row = stmt.getAsObject();
            enemies.push({
                stableKey: row.StableKey as string,
                name: row.Name as string,
                wikiPageName: row.WikiPageName as string | null,
                level: row.Level as number,
                effectiveRarity: row.IsUnique
                    ? Rarity.unique
                    : !!row.IsRare && !row.IsCommon
                      ? Rarity.rare
                      : Rarity.common
            });
        }
        stmt.free();
        return enemies;
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
                MAX(cs.source_script)             AS SourceScript,
                MAX(cs.event_x)                   AS EventX,
                MAX(cs.event_y)                   AS EventY,
                MAX(cs.event_z)                   AS EventZ,
                rep.is_common                   AS IsCommon,
                rep.is_rare                     AS IsRare,
                rep.is_unique                   AS IsUnique,
                min(rep.is_friendly)            AS IsFriendly
            FROM rep_groups rg
            JOIN characters rep ON rep.stable_key = rg.rep_stable_key
            JOIN character_deduplications d ON d.group_key = rg.group_key AND d.is_map_visible = 1
            JOIN map_character_spawns cs ON cs.character_stable_key = d.member_stable_key
            WHERE cs.scene = ?
              AND (cs.spawn_chance > 0 OR cs.source_script IS NOT NULL)
              AND cs.spawn_point_stable_key IS NOT NULL
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
                spawnChance: (row.SpawnChance as number | null) ?? null,
                sourceScript: (row.SourceScript as string | null) ?? null,
                eventPosition:
                    row.EventX != null && row.EventY != null && row.EventZ != null
                        ? {
                              x: row.EventX as number,
                              y: row.EventY as number,
                              z: row.EventZ as number
                          }
                        : null,
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
        const sortedCharacters = characters
            .slice()
            .sort((a, b) => (b.spawnChance ?? 0) - (a.spawnChance ?? 0));

        const characterLines =
            '<br><br>' +
            sortedCharacters
                .map((character) => {
                    let tag = '';
                    if (character.isUnique) tag += ' (Unique)';
                    else if (character.isRare && !character.isCommon) tag += ' (Rare)';

                    const spawnText = character.sourceScript
                        ? 'Dynamic event spawn'
                        : `${(character.spawnChance ?? 0).toFixed(1)}%`;
                    return `${formatWikiLink(character.name, character.wikiPageName)} (${spawnText})${tag}`;
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

    /**
     * Every drop a character can yield, most likely first.
     *
     * Deliberately uncapped. A truncated list is indistinguishable from a
     * complete one, and 165 of the 728 characters with drops have more than ten,
     * so a cap silently misinforms a quarter of the enemies anyone would look up.
     * The popup body scrolls, so length costs nothing but scrolling, and the
     * largest table in the game is 26 rows.
     *
     * Name breaks probability ties so the order is stable across renders.
     */
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
            ORDER BY ld.drop_probability DESC, i.display_name
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

    /**
     * Every drop for each of several characters, most likely first.
     *
     * One statement for the whole set. A spawn point can host fourteen
     * characters, and querying them one at a time made popup latency scale with
     * how crowded the spot is.
     *
     * Characters with no loot are absent from the result rather than mapping to
     * an empty list, so a caller can still tell "no drops" from "not asked".
     */
    async getDropsForCharacters(stableKeys: string[]): Promise<Map<string, CharacterDrop[]>> {
        if (!this.db) throw new Error('DB not initialized');

        const drops = new Map<string, CharacterDrop[]>();
        if (stableKeys.length === 0) return drops;

        const placeholders = stableKeys.map(() => '?').join(', ');
        const stmt = this.db.prepare(
            `
            SELECT
                ld.character_stable_key AS characterStableKey,
                i.display_name AS itemName,
                ld.drop_probability AS dropProbability
            FROM loot_drops ld
            JOIN items i ON i.stable_key = ld.item_stable_key
            WHERE ld.character_stable_key IN (${placeholders})
            ORDER BY ld.character_stable_key, ld.drop_probability DESC, i.display_name
        `,
            stableKeys
        );

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const key = row.characterStableKey as string;
            let list = drops.get(key);
            if (!list) {
                list = [];
                drops.set(key, list);
            }
            list.push({
                itemName: row.itemName as string,
                dropProbability: row.dropProbability as number
            });
        }
        stmt.free();
        return drops;
    }

    /**
     * Preload every item with a wiki page for the map item search. This includes
     * items whose acquisition sources are not represented by map markers.
     */
    async getAllItems(): Promise<ItemSourceItemMeta[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(`
            SELECT
                stable_key     AS itemStableKey,
                display_name   AS displayName,
                wiki_page_name AS wikiPageName,
                item_icon_name AS iconName
            FROM items
            WHERE wiki_page_name IS NOT NULL
              AND TRIM(wiki_page_name) != ''
            ORDER BY display_name, stable_key
        `);

        const items: ItemSourceItemMeta[] = [];
        while (stmt.step()) {
            const row = stmt.getAsObject();
            items.push({
                itemStableKey: row.itemStableKey as string,
                displayName: row.displayName as string,
                wikiPageName: row.wikiPageName as string,
                iconName: (row.iconName as string) ?? null
            });
        }
        stmt.free();
        return items;
    }

    /**
     * Preload every map-visible item acquisition source (drops, vendors, mining, fishing, item bags).
     * Used by the map item search — one query batch at page load, no runtime DB access. Items with is_map_visible = 0 are excluded.
     */
    async getItemSources(): Promise<ItemSourceRow[]> {
        if (!this.db) throw new Error('DB not initialized');

        const rows: ItemSourceRow[] = [];

        {
            const stmt = this.db.prepare(`
                SELECT
                    i.stable_key        AS itemStableKey,
                    i.display_name      AS displayName,
                    i.wiki_page_name    AS wikiPageName,
                    i.item_icon_name    AS iconName,
                    c.stable_key        AS characterStableKey,
                    c.npc_name          AS npcName,
                    c.is_rare           AS isRare,
                    c.is_unique         AS isUnique,
                    ld.drop_probability AS dropProbability
                FROM loot_drops ld
                JOIN items i ON i.stable_key = ld.item_stable_key
                JOIN characters c ON c.stable_key = ld.character_stable_key
                WHERE i.is_map_visible = 1
                ORDER BY i.display_name, ld.drop_probability DESC
            `);

            while (stmt.step()) {
                const row = stmt.getAsObject();
                rows.push({
                    kind: 'drop',
                    itemStableKey: row.itemStableKey as string,
                    displayName: row.displayName as string,
                    wikiPageName: (row.wikiPageName as string) ?? null,
                    iconName: (row.iconName as string) ?? null,
                    characterStableKey: row.characterStableKey as string,
                    npcName: (row.npcName as string) ?? '',
                    isRare: Boolean(row.isRare),
                    isUnique: Boolean(row.isUnique),
                    dropProbability: row.dropProbability as number
                });
            }
            stmt.free();
        }

        {
            const stmt = this.db.prepare(`
                SELECT
                    i.stable_key        AS itemStableKey,
                    i.display_name      AS displayName,
                    i.wiki_page_name    AS wikiPageName,
                    i.item_icon_name    AS iconName,
                    c.stable_key        AS characterStableKey,
                    c.npc_name          AS npcName,
                    i.item_value        AS price
                FROM character_vendor_items cvi
                JOIN items i ON i.stable_key = cvi.item_stable_key
                JOIN characters c ON c.stable_key = cvi.character_stable_key
                WHERE i.is_map_visible = 1
                UNION
                SELECT
                    i.stable_key        AS itemStableKey,
                    i.display_name      AS displayName,
                    i.wiki_page_name    AS wikiPageName,
                    i.item_icon_name    AS iconName,
                    c.stable_key        AS characterStableKey,
                    c.npc_name          AS npcName,
                    i.item_value        AS price
                FROM character_vendor_quest_unlocks cvqu
                JOIN quest_variants qv ON qv.quest_stable_key = cvqu.quest_stable_key
                JOIN items i ON i.stable_key = qv.unlock_item_for_vendor_stable_key
                JOIN characters c ON c.stable_key = cvqu.character_stable_key
                WHERE i.is_map_visible = 1
                ORDER BY displayName, itemStableKey, characterStableKey
            `);

            while (stmt.step()) {
                const row = stmt.getAsObject();
                rows.push({
                    kind: 'vendor',
                    itemStableKey: row.itemStableKey as string,
                    displayName: row.displayName as string,
                    wikiPageName: (row.wikiPageName as string) ?? null,
                    iconName: (row.iconName as string) ?? null,
                    characterStableKey: row.characterStableKey as string,
                    npcName: (row.npcName as string) ?? '',
                    price: (row.price as number) ?? 0
                });
            }
            stmt.free();
        }

        {
            const stmt = this.db.prepare(`
                SELECT
                    i.stable_key             AS itemStableKey,
                    i.display_name           AS displayName,
                    i.wiki_page_name        AS wikiPageName,
                    i.item_icon_name        AS iconName,
                    mi.mining_node_stable_key AS nodeStableKey,
                    mi.drop_chance           AS dropChance
                FROM mining_node_items mi
                JOIN items i ON i.stable_key = mi.item_stable_key
                WHERE i.is_map_visible = 1
                ORDER BY i.display_name
            `);

            while (stmt.step()) {
                const row = stmt.getAsObject();
                rows.push({
                    kind: 'mining',
                    itemStableKey: row.itemStableKey as string,
                    displayName: row.displayName as string,
                    wikiPageName: (row.wikiPageName as string) ?? null,
                    iconName: (row.iconName as string) ?? null,
                    nodeStableKey: row.nodeStableKey as string,
                    dropChance: (row.dropChance as number) ?? 0
                });
            }
            stmt.free();
        }

        {
            const stmt = this.db.prepare(`
                SELECT
                    i.stable_key        AS itemStableKey,
                    i.display_name      AS displayName,
                    i.wiki_page_name    AS wikiPageName,
                    i.item_icon_name    AS iconName,
                    wf.water_stable_key AS waterStableKey,
                    wf.type             AS fishType,
                    wf.drop_chance      AS dropChance
                FROM water_fishables wf
                JOIN items i ON i.stable_key = wf.item_stable_key
                WHERE i.is_map_visible = 1
                ORDER BY i.display_name
            `);

            while (stmt.step()) {
                const row = stmt.getAsObject();
                rows.push({
                    kind: 'fishing',
                    itemStableKey: row.itemStableKey as string,
                    displayName: row.displayName as string,
                    wikiPageName: (row.wikiPageName as string) ?? null,
                    iconName: (row.iconName as string) ?? null,
                    waterStableKey: row.waterStableKey as string,
                    period: row.fishType === 'NightFishable' ? 'night' : 'day',
                    dropChance: (row.dropChance as number) ?? 0
                });
            }
            stmt.free();
        }

        {
            const stmt = this.db.prepare(`
                SELECT
                    i.stable_key        AS itemStableKey,
                    i.display_name      AS displayName,
                    i.wiki_page_name    AS wikiPageName,
                    i.item_icon_name    AS iconName,
                    ib.stable_key       AS bagStableKey
                FROM item_bags ib
                JOIN items i ON i.stable_key = ib.item_stable_key
                WHERE i.is_map_visible = 1
                ORDER BY i.display_name
            `);

            while (stmt.step()) {
                const row = stmt.getAsObject();
                rows.push({
                    kind: 'bag',
                    itemStableKey: row.itemStableKey as string,
                    displayName: row.displayName as string,
                    wikiPageName: (row.wikiPageName as string) ?? null,
                    iconName: (row.iconName as string) ?? null,
                    bagStableKey: row.bagStableKey as string
                });
            }
            stmt.free();
        }

        return rows;
    }

    async getVendorItems(stableKey: string): Promise<VendorItem[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            WITH vendor_items AS (
                SELECT i.display_name AS ItemName, i.item_value AS ItemValue
                FROM character_vendor_items cvi
                JOIN items i ON i.stable_key = cvi.item_stable_key
                WHERE cvi.character_stable_key = ?
                UNION
                SELECT i.display_name AS ItemName, i.item_value AS ItemValue
                FROM character_vendor_quest_unlocks cvqu
                JOIN quest_variants qv ON qv.quest_stable_key = cvqu.quest_stable_key
                JOIN items i ON i.stable_key = qv.unlock_item_for_vendor_stable_key
                WHERE cvqu.character_stable_key = ?
            )
            SELECT ItemName, ItemValue
            FROM vendor_items
            ORDER BY ItemName
            `,
            [stableKey, stableKey]
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

    /**
     * Every map-visible character sharing a display name, with whether each one
     * is placed in the given scene.
     *
     * Names are not identities. 39 display names are worn by more than one
     * deduplicated character, and for 22 of those the characters drop different
     * things -- `Molorai Archaeologist` covers four with four distinct loot
     * tables. Returning one arbitrarily, as this did while it answered with a
     * single row and `LIMIT 1`, presents one variant's loot as the whole truth.
     *
     * The scene flag lets a caller prefer the variants that actually exist where
     * the player is standing, while still seeing the rest when the live zone
     * holds no placed copy, which happens for dynamically spawned characters.
     */
    async getCharactersByName(
        name: string,
        scene: string | null = null
    ): Promise<{ stableKey: string; inScene: boolean }[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            WITH reps AS (
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.is_map_visible = 1
                GROUP BY d.group_key
            )
            SELECT
                c.stable_key AS StableKey,
                EXISTS (
                    SELECT 1
                    FROM character_deduplications m
                    JOIN map_character_spawns s
                      ON s.character_stable_key = m.member_stable_key
                    WHERE m.group_key = r.group_key AND s.scene = ?
                ) AS InScene
            FROM reps r
            JOIN characters c ON c.stable_key = r.rep_stable_key
            WHERE c.display_name = ?
            ORDER BY c.stable_key
            `,
            [scene, name]
        );

        const matches: { stableKey: string; inScene: boolean }[] = [];
        while (stmt.step()) {
            const row = stmt.getAsObject();
            matches.push({
                stableKey: row.StableKey as string,
                inScene: Boolean(row.InScene)
            });
        }
        stmt.free();
        return matches;
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

    getWorldStats(): { zones: number; classes: number; items: number; quests: number } {
        if (!this.db) throw new Error('DB not initialized');
        const count = (table: string): number => {
            const res = this.db!.exec(`SELECT COUNT(*) AS n FROM ${table}`);
            return (res[0]?.values[0][0] as number) ?? 0;
        };
        return {
            zones: count('zones'),
            classes: count('classes'),
            items: count('items'),
            quests: count('quests')
        };
    }

    /**
     * Data provenance for the exported game build.
     *
     * Erenshor publishes only coarse version strings, so the Steam build ID is
     * the precise, publicly verifiable identifier. It is stamped into the raw
     * DB by `erenshor extract code-facts` and carried into the clean DB
     * verbatim, alongside Valve's own publish time for that build.
     *
     * The date deliberately tracks the game build, not the extraction run: an
     * honest older date is correct for a reference tool, whereas re-running a
     * pipeline step must never advertise freshness the data does not have.
     * Returns null unless both fields are known, so callers omit the line
     * rather than render a fabricated one.
     */
    getDataProvenance(): { gameBuildId: string; buildPublishedAt: string } | null {
        if (!this.db) throw new Error('DB not initialized');
        const res = this.db.exec(
            'SELECT game_build_id, game_build_published_at FROM code_facts_meta ' +
                'WHERE game_build_id IS NOT NULL AND game_build_published_at IS NOT NULL LIMIT 1'
        );
        const row = res[0]?.values[0];
        if (!row) return null;
        return { gameBuildId: String(row[0]), buildPublishedAt: String(row[1]) };
    }
}

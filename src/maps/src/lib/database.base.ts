import type { Database, SqlJsStatic } from 'sql.js/dist/sql-wasm.js';

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
    WaterMarker,
    WishingWellMarker,
    ZoneLineMarker
} from './map-markers';

function formatCoordinates(x: number, y: number, z: number): string {
    return `(X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}, Z: ${z.toFixed(2)})`;
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
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				at.AchievementName
			FROM AchievementTriggers at
			JOIN Coordinates co ON co.AchievementTriggerId = at.Id
			WHERE co.Scene = ?
		`,
            [mapName]
        );

        const markers: AchievementTriggerMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const achievementName = row.AchievementName as string;
            markers.push({
                coordinateId: row.CoordinateId as number,
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

    async getCharacterMarkers(mapName: string): Promise<(NpcMarker | EnemyMarker)[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
			SELECT
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				c.NPCName,
				c.StableKey,
				c.Level,
				c.IsEnabled,
				c.IsVendor,
				c.HasDialog,
				c.IsCommon,
				c.IsRare,
				c.IsUnique,
				c.IsFriendly,
				c.Invulnerable
			FROM Characters c
			JOIN Coordinates co ON co.CharacterStableKey = c.StableKey
			WHERE co.Scene = ?
		`,
            [mapName]
        );

        const markers: (NpcMarker | EnemyMarker)[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const coordinateId = row.CoordinateId as number;
            const coordinates = {
                x: row.PositionX as number,
                y: row.PositionY as number,
                z: row.PositionZ as number
            };
            const stableKey = row.StableKey as string;
            const level = (row.Level as number) ?? 1;
            const isFriendly = row.IsFriendly;
            if (isFriendly) {
                markers.push(
                    this.getNpcMarker(
                        coordinateId,
                        coordinates,
                        row.NPCName as string,
                        stableKey,
                        level,
                        null,
                        !!row.IsEnabled,
                        !!row.IsVendor,
                        !!row.HasDialog,
                        false
                    )
                );
            } else {
                markers.push(
                    this.getEnemyMarker(
                        coordinateId,
                        [
                            {
                                name: row.NPCName as string,
                                stableKey,
                                level,
                                spawnChance: 100,
                                isCommon: !!row.IsCommon,
                                isRare: !!row.IsRare,
                                isUnique: !!row.IsUnique,
                                isFriendly: !!row.IsFriendly,
                                isInvulnerable: !!row.Invulnerable
                            }
                        ],
                        coordinates,
                        { x: coordinates.x, y: coordinates.z },
                        null,
                        !!row.IsEnabled,
                        false
                    )
                );
            }
        }
        stmt.free();
        return markers;
    }

    getNpcMarker(
        coordinateId: number,
        coordinates: { x: number; y: number; z: number },
        npcName: string,
        stableKey: string,
        level: number,
        spawnDelay: number | null,
        isEnabled: boolean,
        isVendor: boolean,
        hasDialog: boolean,
        isNightSpawn: boolean,
        movement: MovementData | null = null
    ): NpcMarker {
        const positionText = `NPC @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;
        const npcLink = `<br><br><a href='https://erenshor.wiki.gg/wiki/${encodeURIComponent(npcName)}'>${npcName}</a>`;
        const disabledInfo = isEnabled ? '' : '<br><br>This NPC is (initially) disabled.';
        const respawnInfo = this.getRespawnInfo(spawnDelay, isNightSpawn);

        const popupText = `${positionText}${npcLink}${disabledInfo}${respawnInfo}`.trim();

        return {
            coordinateId: coordinateId,
            category: 'npc',
            name: npcName,
            stableKey,
            level,
            spawnDelay,
            isNightSpawn,
            position: {
                x: coordinates.x,
                y: coordinates.z
            },
            popup: popupText.trim(),
            isEnabled: isEnabled,
            isVendor,
            hasDialog,
            movement
        };
    }

    async getDoorMarkers(mapName: string): Promise<DoorMarker[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
			SELECT
				co.Id AS CoordinateId,
				d.Id AS DoorId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				i.ItemName
			FROM Doors d
			JOIN Coordinates co ON co.DoorId = d.Id
			JOIN Items i ON d.KeyItemStableKey = i.StableKey
			WHERE co.Scene = ? AND d.KeyItemStableKey IS NOT NULL AND i.ItemName != ''
		`,
            [mapName]
        );

        const markers: DoorMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const keyItemName = row.ItemName as string;

            const positionText = `Locked Door @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const keyText = `<br><br>Requires <a href="https://erenshor.wiki.gg/wiki/${encodeURIComponent(keyItemName)}">${keyItemName}</a> to unlock.`;

            const popupText = `${positionText}${keyText}`;

            markers.push({
                coordinateId: row.CoordinateId as number,
                category: 'door',
                keyItemName,
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
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ
			FROM Coordinates co
			WHERE co.Scene = ? AND co.Category = 'Forge'
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
                coordinateId: row.CoordinateId as number,
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
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				i.ItemName,
				ib.Respawns,
				ib.RespawnTimer
			FROM ItemBags ib
			JOIN Coordinates co ON co.ItemBagId = ib.Id
			JOIN Items i ON i.StableKey = ib.ItemStableKey
			WHERE co.Scene = ?
		`,
            [mapName]
        );

        const markers: ItemBagMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const itemName = row.ItemName as string;
            const respawnTimer = row.RespawnTimer as number;
            const respawns = !!row.Respawns;

            const positionText = `Item Bag @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const itemText = `<br><br>Contains <a href="https://erenshor.wiki.gg/wiki/${encodeURIComponent(itemName)}">${itemName}</a>.`;

            const respawnText =
                respawnTimer > 0
                    ? `<br><br>Respawns after ca. ${this.convertToMinutesAndSeconds(respawnTimer)} or when re-entering the zone.`
                    : '<br><br>Respawns when re-entering the zone.';

            const popupText = `${positionText}${itemText}${respawnText}`;

            markers.push({
                coordinateId: row.CoordinateId as number,
                category: 'item-bag',
                itemName,
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
				co.Id AS CoordinateId,
				m.Id AS MiningNodeId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				m.RespawnTime,
				i.ItemName,
				mi.DropChance
			FROM MiningNodes m
			JOIN MiningNodeItems mi ON mi.MiningNodeId = m.Id
			JOIN Items i ON i.StableKey = mi.ItemStableKey
			JOIN Coordinates co ON co.MiningNodeId = m.Id
			WHERE co.Scene = ?
		`,
            [mapName]
        );

        // Group by mining node ID
        const nodeMap = new Map<
            number,
            {
                coordinateId: number;
                position: { x: number; y: number };
                coordinates: { x: number; y: number; z: number };
                respawnTime: number;
                items: MiningNodeItem[];
            }
        >();

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const coordinateId = row.CoordinateId as number;
            const nodeId = row.MiningNodeId as number;
            if (!nodeMap.has(nodeId)) {
                nodeMap.set(nodeId, {
                    coordinateId: coordinateId,
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
            nodeMap.get(nodeId)!.items.push({
                name: row.ItemName as string,
                dropChance: row.DropChance as number
            });
        }
        stmt.free();

        // Build markers with popup lines for each item
        const markers: MiningNodeMarker[] = [];
        for (const {
            coordinateId,
            position,
            coordinates,
            respawnTime,
            items
        } of nodeMap.values()) {
            const sortedItems = items.slice().sort((a, b) => b.dropChance - a.dropChance);

            const itemLines = sortedItems
                .map(
                    (item) =>
                        `<a href='https://erenshor.wiki.gg/wiki/${item.name}'>${item.name}</a> (${Number(item.dropChance).toFixed(1)}%)`
                )
                .join('<br>');

            markers.push({
                coordinateId: coordinateId,
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
            co.Id AS CoordinateId,
            co.X AS PositionX,
            co.Y AS PositionY,
            co.Z AS PositionZ,
            sp.Type AS Type
        FROM SecretPassages sp
        JOIN Coordinates co ON co.SecretPassageId = sp.Id
        WHERE co.Scene = ? AND co.Category = 'SecretPassage' AND (sp.ObjectName NOT LIKE '%nav%' OR sp.ObjectName IS NULL)
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
                coordinateId: row.CoordinateId as number,
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
			SELECT
				co.Id AS CoordinateId,
				sp.Id AS SpawnPointId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				sp.SpawnDelay4 AS SpawnDelay,
				sp.IsEnabled AS IsEnabled,
				sp.NightSpawn AS IsNightSpawn,
				sp.RandomWanderRange AS WanderRange,
				sp.LoopPatrol AS LoopPatrol,
				(SELECT GROUP_CONCAT(pp.X || ',' || pp.Z, ';')
				 FROM SpawnPointPatrolPoints pp
				 WHERE pp.SpawnPointId = sp.Id
				 ORDER BY pp.SequenceIndex) AS PatrolPath,
				c.NPCName,
				c.StableKey,
				c.Level,
				c.IsVendor,
				c.HasDialog,
				c.Invulnerable,
				sum(spc.SpawnChance) AS SpawnChance,
				max(spc.IsCommon) AS IsCommon,
				max(spc.IsRare) AS IsRare,
				min(c.IsUnique) AS IsUnique,
				min(c.IsFriendly) AS IsFriendly
			FROM SpawnPoints sp
			JOIN SpawnPointCharacters spc ON spc.SpawnPointId = sp.Id
			JOIN Characters c ON c.StableKey = spc.CharacterStableKey
			JOIN Coordinates co ON co.SpawnPointId = sp.Id
			WHERE co.Scene = ? AND spc.SpawnChance > 0
			GROUP BY co.Id, c.StableKey
		`,
            [mapName]
        );

        // Group by spawn point ID
        const spawnPointMap = new Map<
            number,
            {
                coordinateId: number;
                position: { x: number; y: number };
                coordinates: { x: number; y: number; z: number };
                spawnDelay: number;
                isEnabled: boolean;
                isNightSpawn: boolean;
                wanderRange: number | null;
                loopPatrol: boolean;
                patrolPath: string | null;
                characters: {
                    name: string;
                    stableKey: string;
                    level: number;
                    spawnChance: number;
                    isCommon: boolean;
                    isRare: boolean;
                    isUnique: boolean;
                    isFriendly: boolean;
                    isInvulnerable: boolean;
                    isVendor: boolean;
                    hasDialog: boolean;
                }[];
            }
        >();

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const coordinateId = row.CoordinateId as number;
            const spawnPointId = row.SpawnPointId as number;
            if (!spawnPointMap.has(spawnPointId)) {
                spawnPointMap.set(spawnPointId, {
                    coordinateId: coordinateId,
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
            spawnPointMap.get(spawnPointId)!.characters.push({
                name: row.NPCName as string,
                stableKey: row.StableKey as string,
                level: (row.Level as number) ?? 1,
                spawnChance: row.SpawnChance as number,
                isCommon: !!row.IsCommon,
                isRare: !!row.IsRare,
                isUnique: !!row.IsUnique,
                isFriendly: !!row.IsFriendly,
                isInvulnerable: !!row.Invulnerable,
                isVendor: !!row.IsVendor,
                hasDialog: !!row.HasDialog
            });
        }

        // Build markers with popup lines for each character
        const markers: (NpcMarker | EnemyMarker)[] = [];
        for (const {
            coordinateId,
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
            const isNpc = characters.length == 1 && characters[0].isFriendly;
            if (isNpc) {
                const npc = characters[0];
                markers.push(
                    this.getNpcMarker(
                        coordinateId,
                        coordinates,
                        npc.name,
                        npc.stableKey,
                        npc.level,
                        spawnDelay,
                        isEnabled,
                        npc.isVendor,
                        npc.hasDialog,
                        isNightSpawn,
                        movement
                    )
                );
            } else {
                markers.push(
                    this.getEnemyMarker(
                        coordinateId,
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
        coordinateId: number,
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

                    return `<a href='https://erenshor.wiki.gg/wiki/${character.name}'>${character.name}</a> (${Number(character.spawnChance).toFixed(1)}%)${tag}`;
                })
                .join('<br>');

        const positionText = `Enemy @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;
        const disabledText = isEnabled ? '' : '<br><br>This enemy is (initially) disabled.';
        const respawnInfo = this.getRespawnInfo(spawnDelay, isNightSpawn);
        const popupText = `${positionText}${characterLines}${disabledText}${respawnInfo}`;

        const isUnique = characters.some((c) => c.isUnique);
        const isRare = characters.some((c) => c.isRare && !c.isCommon);

        return {
            coordinateId: coordinateId,
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
				co.Id AS CoordinateId,
				t.Id AS TeleportId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				i.ItemName
			FROM Teleports t
			JOIN Coordinates co ON co.TeleportId = t.Id
			JOIN Items i ON i.StableKey = t.TeleportItemStableKey
			WHERE co.Scene = ?
		`,
            [mapName]
        );

        const markers: TeleportMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const teleportItemName = row.ItemName as string;

            const positionText = `Teleport Destination @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
            const teleportText = `<br><br>Use <a href="https://erenshor.wiki.gg/wiki/${encodeURIComponent(teleportItemName)}">${teleportItemName}</a> to teleport here.`;

            const popupText = `${positionText}${teleportText}`;

            markers.push({
                coordinateId: row.CoordinateId as number,
                category: 'teleport',
                teleportItemName,
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
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ
			FROM Coordinates co
			WHERE co.Scene = ? AND co.Category = 'TreasureLoc'
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
                coordinateId: row.CoordinateId as number,
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
				co.Id AS CoordinateId,
				w.Id AS WaterId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				w.Width,
				w.Depth,
				wf.Type,
				i.ItemName,
				wf.DropChance
			FROM Waters w
			JOIN WaterFishables wf ON wf.WaterId = w.Id
			JOIN Items i ON i.StableKey = wf.ItemStableKey
			JOIN Coordinates co ON co.WaterId = w.Id
			WHERE co.Scene = ?
		`,
            [mapName]
        );

        // Group by water ID
        const waterMap = new Map<
            number,
            {
                coordinateId: number;
                position: { x: number; y: number };
                coordinates: { x: number; y: number; z: number };
                width: number;
                height: number;
                daytimeItems: { name: string; dropChance: number }[];
                nighttimeItems: { name: string; dropChance: number }[];
            }
        >();

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const coordinateId = row.CoordinateId as number;
            const waterId = row.WaterId as number;
            if (!waterMap.has(waterId)) {
                waterMap.set(waterId, {
                    coordinateId: coordinateId,
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
                dropChance: row.DropChance as number
            };

            if (row.Type === 'DayFishable') {
                waterMap.get(waterId)!.daytimeItems.push(itemInfo);
            } else if (row.Type === 'NightFishable') {
                waterMap.get(waterId)!.nighttimeItems.push(itemInfo);
            }
        }
        stmt.free();

        // Build markers with popup lines for each item
        const markers: WaterMarker[] = [];
        for (const {
            coordinateId,
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
                        `<a href='https://erenshor.wiki.gg/wiki/${item.name}'>${item.name}</a> (${Number(item.dropChance).toFixed(1)}%)`
                )
                .join('<br>');

            const nighttimeItemLines = sortedNighttimeItems
                .map(
                    (item) =>
                        `<a href='https://erenshor.wiki.gg/wiki/${item.name}'>${item.name}</a> (${Number(item.dropChance).toFixed(1)}%)`
                )
                .join('<br>');

            const positionText = `Fishable Water @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;

            const popupText = `${positionText}<br><br>Fishable at daytime: <br>${daytimeItemLines}<br><br>Fishable at nighttime: <br>${nighttimeItemLines}`;

            markers.push({
                coordinateId: coordinateId,
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
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ
			FROM Coordinates co
			WHERE co.Scene = ? AND co.Category = 'WishingWell'
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
                coordinateId: row.CoordinateId as number,
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
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				zl.IsEnabled,
				zl.LandingPositionX,
				zl.LandingPositionY,
				zl.LandingPositionZ,
				z.SceneName AS DestinationZone,
				z.ZoneName,
				zae.LevelRangeLow,
				zae.LevelRangeHigh
			FROM ZoneLines zl
		 	JOIN Zones z ON z.StableKey = zl.DestinationZoneStableKey
		 	LEFT JOIN ZoneAtlasEntries zae ON zae.ZoneName = z.SceneName
		 	JOIN Coordinates co ON co.ZoneLineId = zl.Id
			WHERE co.Scene = ?
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

            // Remove links for ShiveringTomb zones and show consistent name
            const destinationZone = row.DestinationZone as string;
            let zoneLink: string;
            if (destinationZone === 'ShiveringTomb' || destinationZone === 'ShiveringTomb2') {
                zoneLink = 'Shivering Tomb';
            } else {
                zoneLink = `<a href='/${destinationZone}'>${row.ZoneName}</a>`;
            }

            markers.push({
                coordinateId: row.CoordinateId as number,
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
			SELECT NorthBearing
			FROM Zones
			WHERE SceneName = ?
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
			SELECT SceneName, NorthBearing
			FROM Zones
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
                i.ItemName AS itemName,
                ld.DropProbability AS dropProbability
            FROM LootDrops ld
            JOIN Items i ON i.StableKey = ld.ItemStableKey
            WHERE ld.CharacterStableKey = ?
            ORDER BY ld.DropProbability DESC
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

    async getVendorItems(stableKey: string): Promise<string[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT i.ItemName
            FROM CharacterVendorItems cvi
            JOIN Items i ON i.StableKey = cvi.ItemStableKey
            WHERE cvi.CharacterStableKey = ?
            ORDER BY i.ItemName
            `,
            [stableKey]
        );

        const items: string[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            items.push(row.ItemName as string);
        }
        stmt.free();
        return items;
    }

    async getCharacterByName(name: string): Promise<{ stableKey: string } | null> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(`SELECT StableKey FROM Characters WHERE NPCName = ? LIMIT 1`, [
            name
        ]);

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
        uniques: { name: string; level: number }[];
        rares: { name: string; level: number }[];
    }> {
        if (!this.db) throw new Error('DB not initialized');

        // Query level range from both directly placed and spawn point enemies
        const levelStmt = this.db.prepare(
            `
            SELECT MIN(Level) as MinLevel, MAX(Level) as MaxLevel
            FROM (
                SELECT c.Level
                FROM Characters c
                JOIN Coordinates co ON co.CharacterStableKey = c.StableKey
                WHERE co.Scene = ? AND c.IsFriendly = 0

                UNION ALL

                SELECT c.Level
                FROM SpawnPointCharacters spc
                JOIN Characters c ON c.StableKey = spc.CharacterStableKey
                JOIN SpawnPoints sp ON sp.Id = spc.SpawnPointId
                JOIN Coordinates co ON co.SpawnPointId = sp.Id
                WHERE co.Scene = ? AND c.IsFriendly = 0
            )
            `,
            [zoneName, zoneName]
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
            SELECT DISTINCT c.NPCName, c.Level
            FROM (
                SELECT c.StableKey, c.NPCName, c.Level
                FROM Characters c
                JOIN Coordinates co ON co.CharacterStableKey = c.StableKey
                WHERE co.Scene = ? AND c.IsFriendly = 0 AND c.IsUnique = 1

                UNION

                SELECT c.StableKey, c.NPCName, c.Level
                FROM SpawnPointCharacters spc
                JOIN Characters c ON c.StableKey = spc.CharacterStableKey
                JOIN SpawnPoints sp ON sp.Id = spc.SpawnPointId
                JOIN Coordinates co ON co.SpawnPointId = sp.Id
                WHERE co.Scene = ? AND c.IsFriendly = 0 AND c.IsUnique = 1
            ) c
            ORDER BY c.Level, c.NPCName
            `,
            [zoneName, zoneName]
        );

        const uniques: { name: string; level: number }[] = [];
        while (uniqueStmt.step()) {
            const row = uniqueStmt.getAsObject();
            uniques.push({ name: row.NPCName as string, level: row.Level as number });
        }
        uniqueStmt.free();

        // Query rare enemies (exclude uniques)
        const rareStmt = this.db.prepare(
            `
            SELECT DISTINCT c.NPCName, c.Level
            FROM (
                SELECT c.StableKey, c.NPCName, c.Level
                FROM Characters c
                JOIN Coordinates co ON co.CharacterStableKey = c.StableKey
                WHERE co.Scene = ? AND c.IsFriendly = 0 AND c.IsRare = 1 AND c.IsUnique = 0

                UNION

                SELECT c.StableKey, c.NPCName, c.Level
                FROM SpawnPointCharacters spc
                JOIN Characters c ON c.StableKey = spc.CharacterStableKey
                JOIN SpawnPoints sp ON sp.Id = spc.SpawnPointId
                JOIN Coordinates co ON co.SpawnPointId = sp.Id
                WHERE co.Scene = ? AND c.IsFriendly = 0 AND c.IsRare = 1 AND c.IsUnique = 0
            ) c
            ORDER BY c.Level, c.NPCName
            `,
            [zoneName, zoneName]
        );

        const rares: { name: string; level: number }[] = [];
        while (rareStmt.step()) {
            const row = rareStmt.getAsObject();
            rares.push({ name: row.NPCName as string, level: row.Level as number });
        }
        rareStmt.free();

        return { levelRange, uniques, rares };
    }
}

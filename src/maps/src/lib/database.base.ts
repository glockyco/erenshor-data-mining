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
				at.StableKey,
				at.X AS PositionX,
				at.Y AS PositionY,
				at.Z AS PositionZ,
				at.AchievementName
			FROM AchievementTriggers at
			WHERE at.Scene = ?
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
                    return `<a href='https://erenshor.wiki.gg/wiki/${encodeURIComponent(character.name)}'>${character.name}</a>`;
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
				d.StableKey,
				d.X AS PositionX,
				d.Y AS PositionY,
				d.Z AS PositionZ,
				i.ItemName
			FROM Doors d
			JOIN Items i ON d.KeyItemStableKey = i.StableKey
			WHERE d.Scene = ? AND d.KeyItemStableKey IS NOT NULL AND i.ItemName != ''
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
                stableKey: row.StableKey as string,
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
				f.StableKey,
				f.X AS PositionX,
				f.Y AS PositionY,
				f.Z AS PositionZ
			FROM Forges f
			WHERE f.Scene = ?
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
				ib.StableKey,
				ib.X AS PositionX,
				ib.Y AS PositionY,
				ib.Z AS PositionZ,
				i.ItemName,
				ib.Respawns,
				ib.RespawnTimer
			FROM ItemBags ib
			JOIN Items i ON i.StableKey = ib.ItemStableKey
			WHERE ib.Scene = ?
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
                stableKey: row.StableKey as string,
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
				m.StableKey,
				m.X AS PositionX,
				m.Y AS PositionY,
				m.Z AS PositionZ,
				m.RespawnTime,
				i.ItemName,
				mi.DropChance
			FROM MiningNodes m
			JOIN MiningNodeItems mi ON mi.MiningNodeStableKey = m.StableKey
			JOIN Items i ON i.StableKey = mi.ItemStableKey
			WHERE m.Scene = ?
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
                        `<a href='https://erenshor.wiki.gg/wiki/${item.name}'>${item.name}</a> (${Number(item.dropChance).toFixed(1)}%)`
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
            sp.StableKey,
            sp.X AS PositionX,
            sp.Y AS PositionY,
            sp.Z AS PositionZ,
            sp.Type AS Type
        FROM SecretPassages sp
        WHERE sp.Scene = ? AND (sp.ObjectName NOT LIKE '%nav%' OR sp.ObjectName IS NULL)
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
			SELECT
				sp.StableKey,
				sp.X AS PositionX,
				sp.Y AS PositionY,
				sp.Z AS PositionZ,
				sp.SpawnDelay4 AS SpawnDelay,
				sp.IsEnabled AS IsEnabled,
				sp.NightSpawn AS IsNightSpawn,
				sp.RandomWanderRange AS WanderRange,
				sp.LoopPatrol AS LoopPatrol,
				(SELECT GROUP_CONCAT(pp.X || ',' || pp.Z, ';')
				 FROM SpawnPointPatrolPoints pp
				 WHERE pp.SpawnPointStableKey = sp.StableKey
				 ORDER BY pp.SequenceIndex) AS PatrolPath,
				c.NPCName,
				c.StableKey AS CharacterStableKey,
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
			JOIN SpawnPointCharacters spc ON spc.SpawnPointStableKey = sp.StableKey
			JOIN Characters c ON c.StableKey = spc.CharacterStableKey
			WHERE sp.Scene = ? AND spc.SpawnChance > 0
			GROUP BY sp.StableKey, c.StableKey
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
				t.StableKey,
				t.X AS PositionX,
				t.Y AS PositionY,
				t.Z AS PositionZ,
				i.ItemName
			FROM Teleports t
			JOIN Items i ON i.StableKey = t.TeleportItemStableKey
			WHERE t.Scene = ?
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
                stableKey: row.StableKey as string,
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
				tl.StableKey,
				tl.X AS PositionX,
				tl.Y AS PositionY,
				tl.Z AS PositionZ
			FROM TreasureLocations tl
			WHERE tl.Scene = ?
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
				w.StableKey,
				w.X AS PositionX,
				w.Y AS PositionY,
				w.Z AS PositionZ,
				w.Width,
				w.Depth,
				wf.Type,
				i.ItemName,
				wf.DropChance
			FROM Waters w
			JOIN WaterFishables wf ON wf.WaterStableKey = w.StableKey
			JOIN Items i ON i.StableKey = wf.ItemStableKey
			WHERE w.Scene = ?
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
                daytimeItems: { name: string; dropChance: number }[];
                nighttimeItems: { name: string; dropChance: number }[];
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
				ww.StableKey,
				ww.X AS PositionX,
				ww.Y AS PositionY,
				ww.Z AS PositionZ
			FROM WishingWells ww
			WHERE ww.Scene = ?
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
				zl.StableKey,
				zl.X AS PositionX,
				zl.Y AS PositionY,
				zl.Z AS PositionZ,
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
			WHERE zl.Scene = ?
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

    async getVendorItems(stableKey: string): Promise<VendorItem[]> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(
            `
            SELECT i.ItemName, i.ItemValue
            FROM CharacterVendorItems cvi
            JOIN Items i ON i.StableKey = cvi.ItemStableKey
            WHERE cvi.CharacterStableKey = ?
            ORDER BY i.ItemName
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
                WHERE c.Scene = ? AND c.IsFriendly = 0

                UNION ALL

                SELECT c.Level
                FROM SpawnPointCharacters spc
                JOIN Characters c ON c.StableKey = spc.CharacterStableKey
                JOIN SpawnPoints sp ON sp.StableKey = spc.SpawnPointStableKey
                WHERE sp.Scene = ? AND c.IsFriendly = 0
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
                WHERE c.Scene = ? AND c.IsFriendly = 0 AND c.IsUnique = 1

                UNION

                SELECT c.StableKey, c.NPCName, c.Level
                FROM SpawnPointCharacters spc
                JOIN Characters c ON c.StableKey = spc.CharacterStableKey
                JOIN SpawnPoints sp ON sp.StableKey = spc.SpawnPointStableKey
                WHERE sp.Scene = ? AND c.IsFriendly = 0 AND c.IsUnique = 1
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
                WHERE c.Scene = ? AND c.IsFriendly = 0 AND c.IsRare = 1 AND c.IsUnique = 0

                UNION

                SELECT c.StableKey, c.NPCName, c.Level
                FROM SpawnPointCharacters spc
                JOIN Characters c ON c.StableKey = spc.CharacterStableKey
                JOIN SpawnPoints sp ON sp.StableKey = spc.SpawnPointStableKey
                WHERE sp.Scene = ? AND c.IsFriendly = 0 AND c.IsRare = 1 AND c.IsUnique = 0
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

import type { Database, SqlJsStatic } from 'sql.js/dist/sql-wasm.js';

import type {
	AchievementTriggerMarker,
	CharacterMarker,
	DoorMarker,
	ForgeMarker,
	ItemBagMarker,
	Marker,
	MiningNodeMarker,
	SecretPassageMarker,
	SpawnPointMarker,
	TeleportMarker,
	TreasureLocMarker,
	WaterMarker, WishingWellMarker,
	ZoneLineMarker
} from './map-markers';

function formatCoordinates(x: number, y: number, z: number): string {
	return `(X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}, Z: ${z.toFixed(2)})`;
}

export class RepositoryBase {
	protected SQL: SqlJsStatic | null = null;
	protected db: Database | null = null;

	async getAchievementTriggerMarkers(mapName: string): Promise<AchievementTriggerMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				at.AchievementName
			FROM AchievementTriggers at
			JOIN Coordinates co ON co.AchievementTriggerId = at.Id
			WHERE co.Scene = ?
		`, [mapName]);

		const markers: AchievementTriggerMarker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();
			markers.push({
				coordinateId: row.CoordinateId as number,
				category: 'achievement-trigger',
				position: {
					x: row.PositionX as number,
					y: row.PositionZ as number,
				},
				popup: `Achievement @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}<br><br>${row.AchievementName}`,
			});
		}
		stmt.free();
		return markers;
	}

	async getCharacterMarkers(mapName: string): Promise<Marker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				c.NPCName,
				c.IsEnabled,
				c.IsCommon,
				c.IsRare,
				c.IsUnique,
				c.IsFriendly
			FROM Characters c
			JOIN Coordinates co ON co.CharacterStableKey = c.StableKey
			WHERE co.Scene = ?
		`, [mapName]);

		const markers: Marker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();
			const coordinateId = row.CoordinateId as number;
			const coordinates = {x: row.PositionX as number, y: row.PositionY as number, z: row.PositionZ as number};
			const isFriendly = row.IsFriendly;
			if (isFriendly) {
				markers.push(this.getCharacterMarker(
					coordinateId,
					coordinates,
					row.NPCName as string,
					null,
					!!row.IsEnabled,
					false,
					!!row.IsUnique
				))
			} else {
				markers.push(this.getSpawnPointMarker(
					coordinateId,
					[{
						name: row.NPCName as string,
						spawnChance: 100,
						isCommon: !!row.IsCommon,
						isRare: !!row.IsRare,
						isUnique: !!row.IsUnique,
						isFriendly: !!row.IsFriendly
					}],
					coordinates,
					{x: coordinates.x, y: coordinates.z},
					null,
					!!row.IsEnabled,
					false,
				))
			}
		}
		stmt.free();
		return markers;
	}

	getCharacterMarker(
		coordinateId: number,
		coordinates: {x: number, y: number, z: number},
		npcName: string,
		spawnDelay: number | null,
		isEnabled: boolean,
		isNightSpawn: boolean,
		isUnique: boolean,
	): CharacterMarker {
		const positionText = `Character @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;
		const npcLink = `<br><br><a href='https://erenshor.wiki.gg/wiki/${encodeURIComponent(npcName)}'>${npcName}</a>`;
		const disabledInfo = isEnabled ? '' : '<br><br>This character is (initially) disabled.';
		const respawnInfo = this.getRespawnInfo(spawnDelay, isNightSpawn);

		const popupText = `${positionText}${npcLink}${disabledInfo}${respawnInfo}`.trim();

		return {
			coordinateId: coordinateId,
			category: 'character',
			position: {
				x: coordinates.x,
				y: coordinates.z,
			},
			popup: popupText.trim(),
			isEnabled: isEnabled,
			isUnique: isUnique,
		};
	}

	async getDoorMarkers(mapName: string): Promise<DoorMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
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
		`, [mapName]);

		const markers: DoorMarker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();

			const positionText = `Locked Door @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
			const keyText = `<br><br>Requires <a href="https://erenshor.wiki.gg/wiki/${encodeURIComponent(row.ItemName as string)}">${row.ItemName}</a> to unlock.`;

			const popupText = `${positionText}${keyText}`;

			markers.push({
				coordinateId: row.CoordinateId as number,
				category: 'door',
				position: {
					x: row.PositionX as number,
					y: row.PositionZ as number,
				},
				popup: popupText,
			});
		}
		stmt.free();
		return markers;
	}

	async getForgeMarkers(mapName: string): Promise<ForgeMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ
			FROM Coordinates co
			WHERE co.Scene = ? AND co.Category = 'Forge'
		`, [mapName]);

		const markers: ForgeMarker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();

			const positionText = `Forge @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
			const descriptionText = '<br><br>A <a href="https://erenshor.wiki.gg/wiki/Forge">Forge</a> you can <a href="https://erenshor.wiki.gg/wiki/Crafting">craft</a> at.';
			const popupText = `${positionText}${descriptionText}`;

			markers.push({
				coordinateId: row.CoordinateId as number,
				category: 'forge',
				position: {
					x: row.PositionX as number,
					y: row.PositionZ as number,
				},
				popup: popupText,
			});
		}
		stmt.free();
		return markers;
	}

	async getItemBagMarkers(mapName: string): Promise<ItemBagMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
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
		`, [mapName]);

		const markers: ItemBagMarker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();

			const positionText = `Item Bag @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
			const itemText = `<br><br>Contains <a href="https://erenshor.wiki.gg/wiki/${encodeURIComponent(row.ItemName as string)}">${row.ItemName}</a>.`;

			const respawnTimer = row.RespawnTimer as number;
			const respawnText = respawnTimer > 0
					? `<br><br>Respawns after ca. ${this.convertToMinutesAndSeconds(respawnTimer)} or when re-entering the zone.`
					: '<br><br>Respawns when re-entering the zone.';

			const popupText = `${positionText}${itemText}${respawnText}`;

			markers.push({
				coordinateId: row.CoordinateId as number,
				category: 'item-bag',
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

		const stmt = this.db.prepare(`
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
		`, [mapName]);

		// Group by mining node ID
		const nodeMap = new Map<number, {
			coordinateId: number,
			position: { x: number, y: number },
			coordinates: { x: number, y: number, z: number },
			respawnTime: number,
			items: { name: string, dropChance: number }[]
		}>();

		while (stmt.step()) {
			const row = stmt.getAsObject();
			const coordinateId = row.CoordinateId as number;
			const nodeId = row.MiningNodeId as number;
			if (!nodeMap.has(nodeId)) {
				nodeMap.set(nodeId, {
					coordinateId: coordinateId,
					position: {
						x: row.PositionX as number,
						y: row.PositionZ as number,
					},
					coordinates: {
						x: row.PositionX as number,
						y: row.PositionY as number,
						z: row.PositionZ as number,
					},
					respawnTime: row.RespawnTime as number,
					items: [],
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
		for (const { coordinateId, position, coordinates, respawnTime, items } of nodeMap.values()) {
			const sortedItems = items.slice().sort((a, b) => b.dropChance - a.dropChance);

			const itemLines = sortedItems
				.map(item => `<a href='https://erenshor.wiki.gg/wiki/${item.name}'>${item.name}</a> (${Number(item.dropChance).toFixed(1)}%)`)
				.join('<br>');

			markers.push({
				coordinateId: coordinateId,
				category: 'mining-node',
				position,
				popup: `Mining Node @ ${formatCoordinates(
					coordinates.x,
					coordinates.y,
					coordinates.z
				)}<br><br>${itemLines}<br><br>Respawns after ca. ${this.convertToMinutesAndSeconds(respawnTime)} or when re-entering the zone.`,
			});
		}
		return markers;
	}

	async getSecretPassageMarkers(mapName: string): Promise<SecretPassageMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const descriptionMap: Record<string, string> = {
			HiddenDoor: 'A hidden door you can click to open.',
			IllusoryWall: 'An illusory wall you can walk through.',
			InvisibleFloor: 'An invisible floor you can walk on.',
		};

		const stmt = this.db.prepare(`
        SELECT
            co.Id AS CoordinateId,
            co.X AS PositionX,
            co.Y AS PositionY,
            co.Z AS PositionZ,
            sp.Type AS Type
        FROM SecretPassages sp
        JOIN Coordinates co ON co.SecretPassageId = sp.Id
        WHERE co.Scene = ? AND co.Category = 'SecretPassage' AND (sp.ObjectName NOT LIKE '%nav%' OR sp.ObjectName IS NULL)
    `, [mapName]);

		const markers: SecretPassageMarker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();

			const positionText = `Secret Passage @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
			const descriptionText = descriptionMap[row.Type as string] || '';
			const popupText = `${positionText}<br><br>${descriptionText}`;

			markers.push({
				coordinateId: row.CoordinateId as number,
				category: 'secret-passage',
				position: {
					x: row.PositionX as number,
					y: row.PositionZ as number,
				},
				popup: popupText,
			});
		}
		stmt.free();
		return markers;
	}

	async getSpawnPointMarkers(mapName: string): Promise<Marker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT
				co.Id AS CoordinateId,
				sp.Id AS SpawnPointId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				sp.SpawnDelay4 AS SpawnDelay,
				sp.IsEnabled AS IsEnabled,
				sp.NightSpawn AS IsNightSpawn,
				c.NPCName,
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
			GROUP BY co.Id, c.NPCName
		`, [mapName]);

		// Group by spawn point ID
		const spawnPointMap = new Map<number, {
			coordinateId: number,
			position: { x: number, y: number },
			coordinates: { x: number, y: number, z: number },
			spawnDelay: number,
			isEnabled: boolean,
			isNightSpawn: boolean,
			characters: { name: string, spawnChance: number, isCommon: boolean, isRare: boolean, isUnique: boolean, isFriendly: boolean }[],
		}>();

		while (stmt.step()) {
			const row = stmt.getAsObject();
			const coordinateId = row.CoordinateId as number;
			const spawnPointId = row.SpawnPointId as number;
			if (!spawnPointMap.has(spawnPointId)) {
				spawnPointMap.set(spawnPointId, {
					coordinateId: coordinateId,
					position: {
						x: row.PositionX as number,
						y: row.PositionZ as number,
					},
					coordinates: {
						x: row.PositionX as number,
						y: row.PositionY as number,
						z: row.PositionZ as number,
					},
					spawnDelay: row.SpawnDelay as number,
					isEnabled: !!row.IsEnabled,
					isNightSpawn: !!row.IsNightSpawn,
					characters: [],
				});
			}
			spawnPointMap.get(spawnPointId)!.characters.push({
				name: row.NPCName as string,
				spawnChance: row.SpawnChance as number,
				isCommon: !!row.IsCommon,
				isRare: !!row.IsRare,
				isUnique: !!row.IsUnique,
				isFriendly: !!row.IsFriendly,
			});
		}

		// Build markers with popup lines for each character
		const markers: Marker[] = [];
		for (const { coordinateId, position, coordinates, spawnDelay, isEnabled, isNightSpawn, characters } of spawnPointMap.values()) {
			const isCharacter = characters.length == 1 && characters[0].isFriendly;
			if (isCharacter) {
				const character = characters[0];
				markers.push(this.getCharacterMarker(coordinateId, coordinates, character.name, spawnDelay, isEnabled, isNightSpawn, character.isUnique))
			} else {
				markers.push(this.getSpawnPointMarker(coordinateId, characters, coordinates, position, spawnDelay, isEnabled, isNightSpawn))
			}
		}
		return markers;
	}

	getSpawnPointMarker(
		coordinateId: number,
		characters: { name: string, spawnChance: number, isCommon: boolean, isRare: boolean, isUnique: boolean, isFriendly: boolean }[],
		coordinates: { x: number, y: number, z: number },
		position: { x: number, y: number },
		spawnDelay: number | null,
		isEnabled: boolean,
		isNightSpawn: boolean,
	): SpawnPointMarker {
		const sortedCharacters = characters.slice().sort((a, b) => b.spawnChance - a.spawnChance);

		const characterLines = '<br><br>' + sortedCharacters
			.map(character => {
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

		const hasUnique = characters.some(c => c.isUnique);
		const hasRare = characters.some(c => c.isRare && !c.isCommon);

		return {
			coordinateId: coordinateId,
			category: 'spawn-point',
			position: position,
			popup: popupText,
			isEnabled: isEnabled,
			hasUnique: hasUnique,
			hasRare: hasRare,
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

		const stmt = this.db.prepare(`
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
		`, [mapName]);

		const markers: TeleportMarker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();

			const positionText = `Teleport Destination @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
			const teleportText = `<br><br>Use <a href="https://erenshor.wiki.gg/wiki/${encodeURIComponent(row.ItemName as string)}">${row.ItemName}</a> to teleport here.`;

			const popupText = `${positionText}${teleportText}`;

			markers.push({
				coordinateId: row.CoordinateId as number,
				category: 'teleport',
				position: {
					x: row.PositionX as number,
					y: row.PositionZ as number
				},
				popup: popupText,
			});
		}
		stmt.free();
		return markers;
	}

	async getTreasureLocMarkers(mapName: string): Promise<TreasureLocMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ
			FROM Coordinates co
			WHERE co.Scene = ? AND co.Category = 'TreasureLoc'
		`, [mapName]);

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
					y: row.PositionZ as number,
				},
				popup: popupText,
			});
		}
		stmt.free();
		return markers;
	}

	async getWaterMarkers(mapName: string): Promise<WaterMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT
				co.Id AS CoordinateId,
				w.Id AS WaterId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				wf.Type,
				i.ItemName,
				wf.DropChance
			FROM Waters w
			JOIN WaterFishables wf ON wf.WaterId = w.Id
			JOIN Items i ON i.StableKey = wf.ItemStableKey
			JOIN Coordinates co ON co.WaterId = w.Id
			WHERE co.Scene = ?
		`, [mapName]);

		// Group by water ID
		const waterMap = new Map<number, {
			coordinateId: number,
			position: { x: number, y: number },
			coordinates: { x: number, y: number, z: number },
			daytimeItems: { name: string, dropChance: number }[],
			nighttimeItems: { name: string, dropChance: number }[]
		}>();

		while (stmt.step()) {
			const row = stmt.getAsObject();
			const coordinateId = row.CoordinateId as number;
			const waterId = row.WaterId as number;
			if (!waterMap.has(waterId)) {
				waterMap.set(waterId, {
					coordinateId: coordinateId,
					position: {
						x: row.PositionX as number,
						y: row.PositionZ as number,
					},
					coordinates: {
						x: row.PositionX as number,
						y: row.PositionY as number,
						z: row.PositionZ as number,
					},
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
		for (const { coordinateId, position, coordinates, daytimeItems, nighttimeItems } of waterMap.values()) {

			const sortByChanceAndName = (a: { dropChance: number, name: string }, b: { dropChance: number, name: string }) => {
				return b.dropChance - a.dropChance || a.name.localeCompare(b.name);
			};

			const sortedDaytimeItems = daytimeItems.slice().sort(sortByChanceAndName);
			const sortedNighttimeItems = nighttimeItems.slice().sort(sortByChanceAndName);

			const daytimeItemLines = sortedDaytimeItems
				.map(item => `<a href='https://erenshor.wiki.gg/wiki/${item.name}'>${item.name}</a> (${Number(item.dropChance).toFixed(1)}%)`)
				.join('<br>');

			const nighttimeItemLines = sortedNighttimeItems
				.map(item => `<a href='https://erenshor.wiki.gg/wiki/${item.name}'>${item.name}</a> (${Number(item.dropChance).toFixed(1)}%)`)
				.join('<br>');

			const positionText = `Fishable Water @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;

			const popupText = `${positionText}<br><br>Fishable at daytime: <br>${daytimeItemLines}<br><br>Fishable at nighttime: <br>${nighttimeItemLines}`;

			markers.push({
				coordinateId: coordinateId,
				category: 'water',
				position,
				popup: popupText,
			});
		}
		return markers;
	}

	async getWishingWellMarkers(mapName: string): Promise<WishingWellMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ
			FROM Coordinates co
			WHERE co.Scene = ? AND co.Category = 'WishingWell'
		`, [mapName]);

		const markers: WishingWellMarker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();

			const positionText = `Wishing Well @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`;
			const descriptionText = '<br><br>A <a href="https://erenshor.wiki.gg/wiki/Wishing_Well">Wishing Well</a> you can set your respawn point at.';
			const popupText = `${positionText}${descriptionText}`;

			markers.push({
				coordinateId: row.CoordinateId as number,
				category: 'wishing-well',
				position: {
					x: row.PositionX as number,
					y: row.PositionZ as number,
				},
				popup: popupText,
			});
		}
		stmt.free();
		return markers;
	}

	async getZoneLineMarkers(mapName: string): Promise<ZoneLineMarker[]> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT
				co.Id AS CoordinateId,
				co.X AS PositionX,
				co.Y AS PositionY,
				co.Z AS PositionZ,
				zl.IsEnabled,
				z.SceneName AS DestinationZone,
				z.ZoneName,
				zae.LevelRangeLow,
				zae.LevelRangeHigh
			FROM ZoneLines zl
		 	JOIN Zones z ON z.StableKey = zl.DestinationZoneStableKey
		 	LEFT JOIN ZoneAtlasEntries zae ON zae.ZoneName = z.SceneName
		 	JOIN Coordinates co ON co.ZoneLineId = zl.Id
			WHERE co.Scene = ?
		`, [mapName]);

		const markers: ZoneLineMarker[] = [];

		while (stmt.step()) {
			const row = stmt.getAsObject();
			const disabledText = row.IsEnabled ? '' : '<br><br>This zone connection is (initially) disabled.';
			const levelRange = (row.LevelRangeLow && row.LevelRangeHigh) ? ` (Level: ${row.LevelRangeLow}-${row.LevelRangeHigh})` : '';

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
				isEnabled: !!row.IsEnabled,
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
			return "an unknown time"
		}
	};

	async getZoneNorthBearing(mapName: string): Promise<number> {
		if (!this.db) throw new Error('DB not initialized');

		const stmt = this.db.prepare(`
			SELECT NorthBearing
			FROM Zones
			WHERE SceneName = ?
		`, [mapName]);

		if (stmt.step()) {
			const row = stmt.getAsObject();
			stmt.free();
			return row.NorthBearing as number;
		}
		stmt.free();
		return 0; // Default to 0 if not found
	}
}

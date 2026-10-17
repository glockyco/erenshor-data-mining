import type { Database, SqlJsStatic } from 'sql.js/dist/sql-wasm.js';
import { readItemAcquisitions, readItemDispositions, readItemUses, readProvenanceMetadata, probabilityText, conditionLines, quantityText, isActionableAcquisition, conditionsSatisfiable } from './item-provenance';
import type { ItemAcquisition, ItemDisposition, ItemProvenanceSnapshot } from './item-provenance';
import { readZoneLineDestinationContexts, readZoneLineDestinationSnapshot, STORED_RETURN_LABEL } from './zone-line-destinations';
import type { ZoneLineDestinationContext } from './zone-line-destinations';

import {
    isFurnishingSpawn,
    mostNotableEnemyTier,
    type EncounterTier,
    type EnemyTier
} from './map-markers';
import type {
    AchievementTriggerMarker,
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
    WaterMarker,
    WishingWellMarker,
    ZoneLineMarker
} from './map-markers';
import type { LiveCandidate } from './map/character-details';
import type { ZoneEnemyInfo } from './types/world-map';

function formatCoordinates(x: number, y: number, z: number): string {
    return `(X: ${x.toFixed(2)}, Y: ${y.toFixed(2)}, Z: ${z.toFixed(2)})`;
}

function formatWikiLink(label: string, pageName: string | null): string {
    if (!pageName) return label;
    return `<a href='https://erenshor.wiki.gg/wiki/${encodeURIComponent(pageName)}'>${label}</a>`;
}

// The planning table places a furnishing in a Reliquary room only while the room holds its set.
function furnitureText(character: SpawnCharacter): string {
    if (!character.furniture) return '';
    const set = formatWikiLink(character.furniture.name, character.furniture.wikiPageName);
    return `<br>Appears when the player places the ${set} in this room.`;
}

function portraitHtml(hash: string | null): string {
    if (!hash) return '';
    const url = `/characters/${encodeURIComponent(hash)}`;
    return `<img src="${url}.w96.webp" srcset="${url}.w96.webp 1x, ${url}.w192.webp 2x" alt="" width="96" height="96" style="display:block;margin:0 auto 8px;object-fit:contain">`;
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

function acquisitionPopupHtml(fact: ItemAcquisition, coordinateKey: string): string {
    return [probabilityText(fact), quantityText(fact), ...conditionLines(fact.conditions),
        ...fact.locations.filter((location) => location.coordinate_stable_key === coordinateKey &&
            conditionsSatisfiable([...fact.conditions, ...location.conditions])).flatMap((location) => conditionLines(location.conditions))]
        .filter(Boolean).join('<br>');
}

interface MapItemProvenance {
    database: Database;
    acquisitions: ItemAcquisition[];
    actionableByKey: Map<string, ItemAcquisition>;
    dispositions: ItemDisposition[];
    dispositionByKey: Map<string, ItemDisposition>;
}

export class RepositoryBase {
    protected SQL: SqlJsStatic | null = null;
    protected db: Database | null = null;
    private provenanceCache: MapItemProvenance | null = null;
    private zoneLineContextCache: { database: Database; records: Map<string, ZoneLineDestinationContext> } | null = null;

    private getProvenance(): MapItemProvenance {
        if (!this.db) throw new Error('DB not initialized');
        if (this.provenanceCache?.database !== this.db) {
            const acquisitions = readItemAcquisitions(this.db);
            const dispositions = readItemDispositions(this.db);
            const dispositionByKey = new Map(dispositions.map((record) => [record.item_stable_key, record]));
            this.provenanceCache = { database: this.db, acquisitions, dispositions, dispositionByKey,
                actionableByKey: new Map(acquisitions.filter((fact) => dispositionByKey.get(fact.item_stable_key)?.disposition === 'current' &&
                    isActionableAcquisition(fact)).map((fact) => [fact.acquisition_key, fact])) };
        }
        return this.provenanceCache;
    }

    private getZoneLineContexts(): Map<string, ZoneLineDestinationContext> {
        if (!this.db) throw new Error('DB not initialized');
        if (this.zoneLineContextCache?.database !== this.db) {
            this.zoneLineContextCache = { database: this.db, records: readZoneLineDestinationContexts(this.db) };
        }
        return this.zoneLineContextCache.records;
    }

    /** Read complete offline coverage inputs without adding audit records to page props. */
    async getItemProvenanceSnapshot(): Promise<ItemProvenanceSnapshot> {
        if (!this.db) throw new Error('DB not initialized');
        const provenance = this.getProvenance();
        const items: ItemProvenanceSnapshot['items'] = [];
        const statement = this.db.prepare('SELECT stable_key, is_map_visible, wiki_page_name FROM items ORDER BY stable_key');
        try {
            while (statement.step()) {
                const row = statement.getAsObject();
                items.push({ stable_key: row.stable_key as string, is_map_visible: row.is_map_visible === 1,
                    wiki_page_name: row.wiki_page_name as string | null });
            }
        } finally {
            statement.free();
        }
        return { metadata: readProvenanceMetadata(this.db), acquisitions: provenance.acquisitions,
            dispositions: provenance.dispositions, uses: readItemUses(this.db), items,
            zone_line_destinations: readZoneLineDestinationSnapshot(this.db, this.getZoneLineContexts()) };
    }

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
                    return `${portraitHtml(character.portraitHash)}${formatWikiLink(character.name, character.wikiPageName)}${furnitureText(character)}`;
                })
                .join('<br>');

        const positionText = `NPC @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;
        const disabledInfo =
            isEnabled || isFurnishingSpawn(characters)
                ? ''
                : '<br><br>This NPC is (initially) disabled.';
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
        const facts = this.getProvenance().actionableByKey;

        const stmt = this.db.prepare(
            `
            SELECT
                ib.stable_key AS StableKey,
                ib.x AS PositionX,
                ib.y AS PositionY,
                ib.z AS PositionZ,
                i.display_name AS ItemName,
                a.acquisition_key AS AcquisitionKey,
                i.wiki_page_name AS ItemWikiPageName,
                ib.respawns AS Respawns,
                ib.respawn_timer AS RespawnTimer
            FROM item_bags ib
            JOIN item_acquisitions a ON a.source_stable_key = ib.stable_key AND a.kind = 'item_bag'
                AND a.player_access_state IN ('verified_player', 'unconfirmed_player')
            JOIN items i ON i.stable_key = a.item_stable_key
            WHERE ib.scene = ?
        `,
            [mapName]
        );

        const markers: ItemBagMarker[] = [];

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const fact = facts.get(row.AcquisitionKey as string);
            if (!fact || !fact.locations.some((location) => location.coordinate_stable_key === row.StableKey &&
                conditionsSatisfiable([...fact.conditions, ...location.conditions]))) continue;
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

            const popupText = `${positionText}${itemText}<br>${acquisitionPopupHtml(fact, row.StableKey as string)}${respawnText}`;

            markers.push({
                stableKey: row.StableKey as string,
                category: 'item-bag',
                itemName,
                itemWikiPageName,
                respawnTimer,
                respawns,
                provenance: fact,
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
        const facts = this.getProvenance().actionableByKey;

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
                a.probability_max AS DropChance,
                a.acquisition_key AS AcquisitionKey
            FROM mining_nodes m
            JOIN item_acquisitions a ON a.source_stable_key = m.stable_key AND a.kind = 'mining'
                AND a.player_access_state IN ('verified_player', 'unconfirmed_player')
            JOIN items i ON i.stable_key = a.item_stable_key
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
            const fact = facts.get(row.AcquisitionKey as string);
            if (!fact || !fact.locations.some((location) => location.coordinate_stable_key === row.StableKey &&
                conditionsSatisfiable([...fact.conditions, ...location.conditions]))) continue;
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
                dropChance: (row.DropChance as number | null) ?? 0,
                provenance: fact
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
                        `${formatWikiLink(item.name, item.wikiPageName)}<br>${acquisitionPopupHtml(item.provenance, stableKey)}`
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
            ), combat_groups AS (
                SELECT member.group_key, MIN(combat_copy.level) AS Level, MAX(combat_copy.level) AS LevelMax
                FROM character_deduplications member
                JOIN characters combat_copy ON combat_copy.stable_key = member.member_stable_key
                    AND combat_copy.can_be_damaged = 1 AND combat_copy.encounter_tier != 'npc'
                WHERE member.is_map_visible = 1 GROUP BY member.group_key
            )
            SELECT
                rep.stable_key AS StableKey,
                rep.display_name AS Name,
                rep.wiki_page_name AS WikiPageName,
                rep.image_hash AS PortraitHash,
                combat_groups.Level AS Level,
                combat_groups.LevelMax AS LevelMax,
                rep.encounter_tier AS EncounterTier
            FROM rep_groups rg
            JOIN characters rep ON rep.stable_key = rg.rep_stable_key
            JOIN combat_groups ON combat_groups.group_key = rg.group_key
            WHERE rep.encounter_tier != 'npc'
              AND NOT EXISTS (
                  SELECT 1
                  FROM character_deduplications d
                  JOIN map_character_spawns cs
                    ON cs.character_stable_key = d.member_stable_key
                  JOIN characters placed_copy ON placed_copy.stable_key = d.member_stable_key
                    AND placed_copy.can_be_damaged = 1 AND placed_copy.encounter_tier != 'npc'
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
              AND NOT EXISTS (
                  SELECT 1 FROM treasure_chest_possible_spawns ts
                  WHERE ts.chest_character_stable_key = rep.stable_key
              )
              AND NOT EXISTS (
                  SELECT 1 FROM character_chained_spawns chain
                  JOIN treasure_chest_possible_spawns ts
                    ON ts.chest_character_stable_key = chain.parent_stable_key
                  WHERE chain.source_script = 'TreasureChestEvent'
                    AND chain.child_stable_key = rep.stable_key
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
                portraitHash: (row.PortraitHash as string | null) ?? null,
                level: row.Level as number,
                levelMax: row.LevelMax as number,
                encounterTier: row.EncounterTier as EnemyTier
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
                rep.image_hash                  AS PortraitHash,
                rep.stable_key                  AS CharacterStableKey,
                MIN(combat_copy.level)          AS Level,
                MAX(combat_copy.level)          AS LevelMax,
                MAX(combat_copy.level_scales_with_player) AS LevelScalesWithPlayer,
                rep.is_vendor                   AS IsVendor,
                rep.has_dialog                  AS HasDialog,
                MIN(combat_copy.invulnerable)   AS Invulnerable,
                MAX(combat_copy.can_be_damaged) AS CanBeDamaged,
                sum(cs.spawn_chance)            AS SpawnChance,
                MAX(cs.source_script)             AS SourceScript,
                MAX(cs.event_x)                   AS EventX,
                MAX(cs.event_y)                   AS EventY,
                MAX(cs.event_z)                   AS EventZ,
                MAX(fi.display_name)              AS FurnitureName,
                MAX(fi.wiki_page_name)            AS FurnitureWikiPageName,
                rep.encounter_tier              AS EncounterTier
            FROM rep_groups rg
            JOIN characters rep ON rep.stable_key = rg.rep_stable_key
            JOIN character_deduplications d ON d.group_key = rg.group_key AND d.is_map_visible = 1
            JOIN characters combat_copy ON combat_copy.stable_key = d.member_stable_key
            JOIN map_character_spawns cs ON cs.character_stable_key = d.member_stable_key
            LEFT JOIN items fi ON fi.stable_key = cs.furniture_item_stable_key
            WHERE cs.scene = ?
              AND (cs.spawn_chance > 0 OR cs.source_script IS NOT NULL)
              AND cs.spawn_point_stable_key IS NOT NULL
              AND (rep.encounter_tier = 'npc' OR
                  (combat_copy.can_be_damaged = 1 AND combat_copy.encounter_tier != 'npc'))
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
                portraitHash: (row.PortraitHash as string | null) ?? null,
                stableKey: row.CharacterStableKey as string,
                level: (row.Level as number) ?? 1,
                levelMax: row.LevelMax as number,
                levelScalesWithPlayer: !!row.LevelScalesWithPlayer,
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
                encounterTier: row.EncounterTier as EncounterTier,
                isInvulnerable: !!row.Invulnerable,
                canBeDamaged: row.CanBeDamaged === 1,
                isVendor: !!row.IsVendor,
                hasDialog: !!row.HasDialog,
                furniture:
                    row.FurnitureName != null
                        ? {
                              name: row.FurnitureName as string,
                              wikiPageName: (row.FurnitureWikiPageName as string | null) ?? null
                          }
                        : null
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
            const isNpc = characters.every((c) => c.encounterTier === 'npc');
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
                    if (character.encounterTier === 'boss') tag = ' (Boss)';
                    else if (character.encounterTier === 'elite') tag = ' (Elite)';
                    else if (character.encounterTier === 'chest') tag = ' (Chest)';

                    const spawnText = character.sourceScript
                        ? 'Event spawn'
                        : `${(character.spawnChance ?? 0).toFixed(1)}%`;
                    return `${portraitHtml(character.portraitHash)}${formatWikiLink(character.name, character.wikiPageName)} (${spawnText})${tag}${furnitureText(character)}`;
                })
                .join('<br>');

        const encounterTier = mostNotableEnemyTier(characters);
        const kind = encounterTier === 'chest' ? 'Chest' : 'Enemy';
        const positionText = `${kind} @ ${formatCoordinates(coordinates.x, coordinates.y, coordinates.z)}`;
        const disabledText =
            isEnabled || isFurnishingSpawn(characters)
                ? ''
                : `<br><br>This ${kind.toLowerCase()} is (initially) disabled.`;
        const respawnInfo = this.getRespawnInfo(spawnDelay, isNightSpawn);
        const popupText = `${positionText}${characterLines}${disabledText}${respawnInfo}`;

        return {
            stableKey: stableKey,
            category: 'enemy',
            characters: sortedCharacters,
            spawnDelay,
            isNightSpawn,
            position: position,
            popup: popupText,
            isEnabled: isEnabled,
            encounterTier,
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

        // The clean build gives the player levels at which a site brings up
        // each chest, and the guardians scale with the player who digs.
        const guardiansStmt = this.db.prepare(
            `
            SELECT tl.stable_key AS SiteKey, c.stable_key AS StableKey,
                   c.display_name AS Name, c.wiki_page_name AS WikiPageName,
                   MIN(gs.level_min) AS LevelMin, MAX(gs.level_max) AS LevelMax
            FROM treasure_locations tl
            JOIN treasure_chest_possible_spawns ts ON ts.treasure_location_stable_key = tl.stable_key
            JOIN character_chained_spawns chain ON chain.parent_stable_key = ts.chest_character_stable_key
                AND chain.source_script = 'TreasureChestEvent'
            JOIN characters c ON c.stable_key = chain.child_stable_key
            JOIN treasure_guardian_scaling gs ON gs.guardian_character_stable_key = c.stable_key
                AND gs.player_level BETWEEN ts.player_level_min AND ts.player_level_max
            WHERE tl.scene = ?
            GROUP BY tl.stable_key, c.stable_key
            ORDER BY tl.stable_key, c.display_name, c.stable_key
        `,
            [mapName]
        );
        const guardiansBySite = new Map<string, TreasureLocMarker['guardians']>();
        while (guardiansStmt.step()) {
            const row = guardiansStmt.getAsObject();
            const siteKey = row.SiteKey as string;
            const guardians = guardiansBySite.get(siteKey) ?? [];
            guardians.push({
                stableKey: row.StableKey as string,
                name: row.Name as string,
                wikiPageName: row.WikiPageName as string | null,
                levelMin: row.LevelMin as number,
                levelMax: row.LevelMax as number
            });
            guardiansBySite.set(siteKey, guardians);
        }
        guardiansStmt.free();

        const stmt = this.db.prepare(
            `
            SELECT tl.stable_key AS StableKey, tl.x AS PositionX, tl.y AS PositionY, tl.z AS PositionZ,
                   th.min_reading_level AS MinReadingLevel,
                   c.stable_key AS ChestKey, c.display_name AS ChestName, c.wiki_page_name AS WikiPageName,
                   ts.player_level_min AS DigLevelMin,
                   ts.player_level_max AS DigLevelMax
            FROM treasure_locations tl
            JOIN treasure_hunting th ON th.zone_name = tl.scene
            JOIN treasure_chest_possible_spawns ts ON ts.treasure_location_stable_key = tl.stable_key
            JOIN characters c ON c.stable_key = ts.chest_character_stable_key
            WHERE tl.scene = ?
            ORDER BY tl.stable_key, DigLevelMin, c.stable_key
        `,
            [mapName]
        );
        const markers = new Map<string, TreasureLocMarker>();
        while (stmt.step()) {
            const row = stmt.getAsObject();
            const stableKey = row.StableKey as string;
            let marker = markers.get(stableKey);
            if (!marker) {
                const guardians = guardiansBySite.get(stableKey) ?? [];
                if (guardians.length === 0)
                    throw new Error(`Missing treasure guardian scaling: ${stableKey}`);
                marker = {
                    stableKey,
                    category: 'treasure-loc',
                    position: { x: row.PositionX as number, y: row.PositionZ as number },
                    minReadingLevel: row.MinReadingLevel as number,
                    chests: [],
                    guardians,
                    levelMin: Math.min(...guardians.map((g) => g.levelMin)),
                    levelMax: Math.max(...guardians.map((g) => g.levelMax)),
                    popup: `Lost Treasure @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}`
                };
                markers.set(stableKey, marker);
            }
            marker.chests.push({
                stableKey: row.ChestKey as string,
                name: row.ChestName as string,
                wikiPageName: row.WikiPageName as string | null,
                digLevelMin: row.DigLevelMin as number,
                digLevelMax: row.DigLevelMax as number
            });
        }
        stmt.free();
        for (const marker of markers.values()) {
            const readingLevel =
                marker.minReadingLevel === 1 ? 'any level' : `${marker.minReadingLevel} or higher`;
            marker.popup += `<br><br>Reading level: ${readingLevel}<br><br>Chest by player digging level:<br>`;
            marker.popup += marker.chests
                .map(
                    (c) =>
                        `${c.digLevelMin}–${c.digLevelMax}: ${formatWikiLink(c.name, c.wikiPageName)}`
                )
                .join('<br>');
            marker.popup += '<br><br>Guardians (scale with the player):<br>';
            marker.popup += marker.guardians
                .map(
                    (g) =>
                        `${formatWikiLink(g.name, g.wikiPageName)}: Level ${g.levelMin}–${g.levelMax}`
                )
                .join('<br>');
            marker.popup += `<br><br>${formatWikiLink('Treasure Hunting', 'Treasure_Hunting')}`;
        }
        return [...markers.values()];
    }

    async getWaterMarkers(mapName: string): Promise<WaterMarker[]> {
        if (!this.db) throw new Error('DB not initialized');
        const facts = this.getProvenance().actionableByKey;

        const stmt = this.db.prepare(
            `
            SELECT
                w.stable_key AS StableKey,
                w.x AS PositionX,
                w.y AS PositionY,
                w.z AS PositionZ,
                w.width AS Width,
                w.depth AS Depth,
                a.variant_key AS Type,
                i.display_name AS ItemName,
                i.wiki_page_name AS ItemWikiPageName,
                a.probability_max AS DropChance,
                a.acquisition_key AS AcquisitionKey
            FROM waters w
            JOIN item_acquisitions a ON a.source_stable_key = w.stable_key AND a.kind IN ('fishing', 'fishing_bonus')
                AND a.player_access_state IN ('verified_player', 'unconfirmed_player')
            JOIN items i ON i.stable_key = a.item_stable_key
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
                daytimeItems: MiningNodeItem[];
                nighttimeItems: MiningNodeItem[];
            }
        >();

        while (stmt.step()) {
            const row = stmt.getAsObject();
            const sourceFact = facts.get(row.AcquisitionKey as string);
            if (!sourceFact || !sourceFact.locations.some((location) => location.coordinate_stable_key === row.StableKey &&
                conditionsSatisfiable([...sourceFact.conditions, ...location.conditions]))) continue;
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
                dropChance: (row.DropChance as number | null) ?? 0,
                provenance: sourceFact
            };

            const period = sourceFact.conditions.find((condition) => condition.predicate === 'time_of_day')?.value;
            if (period !== 'night') waterMap.get(stableKey)!.daytimeItems.push(itemInfo);
            if (period !== 'day') waterMap.get(stableKey)!.nighttimeItems.push(itemInfo);
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
                        `${formatWikiLink(item.name, item.wikiPageName)}<br>${acquisitionPopupHtml(item.provenance, stableKey)}`
                )
                .join('<br>');

            const nighttimeItemLines = sortedNighttimeItems
                .map(
                    (item) =>
                        `${formatWikiLink(item.name, item.wikiPageName)}<br>${acquisitionPopupHtml(item.provenance, stableKey)}`
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
        const contexts = this.getZoneLineContexts();
        const statement = this.db.prepare(`
            SELECT zl.stable_key AS StableKey, zl.x AS PositionX, zl.y AS PositionY, zl.z AS PositionZ,
                zl.is_enabled AS IsEnabled, zl.landing_position_x AS LandingPositionX,
                zl.landing_position_y AS LandingPositionY, zl.landing_position_z AS LandingPositionZ,
                destination.scene_name AS DestinationZone, destination.display_name AS ZoneName,
                destination.is_map_visible AS IsMapVisible,
                atlas.level_range_low AS LevelRangeLow, atlas.level_range_high AS LevelRangeHigh
            FROM zone_lines_with_zoning_capability zl
            LEFT JOIN zones destination ON destination.stable_key = zl.destination_zone_stable_key
            LEFT JOIN zone_atlas_entries atlas ON atlas.zone_name = destination.scene_name
            WHERE zl.scene = ? AND zl.x IS NOT NULL AND zl.y IS NOT NULL AND zl.z IS NOT NULL
            ORDER BY zl.stable_key
        `, [mapName]);
        const markers: ZoneLineMarker[] = [];
        try {
            while (statement.step()) {
                const row = statement.getAsObject();
                if (![row.PositionX, row.PositionY, row.PositionZ].every((value) => typeof value === 'number' && Number.isFinite(value))) continue;
                const context = contexts.get(row.StableKey as string) ?? null;
                const destinationZone = context ? null : row.DestinationZone as string | null;
                const destinationName = context ? STORED_RETURN_LABEL :
                    (row.ZoneName as string | null) ?? destinationZone ?? 'Destination unknown';
                const landingPosition = !context && [row.LandingPositionX, row.LandingPositionY, row.LandingPositionZ]
                    .every((value) => typeof value === 'number' && Number.isFinite(value))
                    ? { x: row.LandingPositionX as number, y: row.LandingPositionY as number, z: row.LandingPositionZ as number }
                    : null;
                const low = context ? null : row.LevelRangeLow as number | null;
                const high = context ? null : row.LevelRangeHigh as number | null;
                const levelRange = low !== null && high !== null ? ` (Level: ${low}-${high})` : '';
                const disabledText = row.IsEnabled ? '' : '<br><br>This zone connection is (initially) disabled.';
                let zoneLink = destinationName;
                if (!context && destinationZone && row.IsMapVisible) {
                    zoneLink = destinationZone === 'ShiveringTomb' || destinationZone === 'ShiveringTomb2'
                        ? 'Shivering Tomb' : `<a href='/${destinationZone}'>${destinationName}</a>`;
                }
                markers.push({
                    stableKey: row.StableKey as string, category: 'zone-line',
                    position: { x: row.PositionX as number, y: row.PositionZ as number },
                    popup: `Zone Connection @ ${formatCoordinates(row.PositionX as number, row.PositionY as number, row.PositionZ as number)}<br><br>${zoneLink}${levelRange}${disabledText}`,
                    destinationZone, destinationZoneName: destinationName, landingPosition, destinationContext: context,
                    levelRangeLow: low, levelRangeHigh: high, isEnabled: row.IsEnabled === 1
                });
            }
        } finally {
            statement.free();
        }
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
     * Preload every item with a wiki page for the map item search. This includes
     * items whose acquisition sources are not represented by map markers.
     */
    async getAllItems(): Promise<ItemSourceItemMeta[]> {
        if (!this.db) throw new Error('DB not initialized');
        this.getProvenance();

        const stmt = this.db.prepare(`
            SELECT
                stable_key     AS itemStableKey,
                display_name   AS displayName,
                wiki_page_name AS wikiPageName,
                image_hash     AS iconHash
            FROM items
            WHERE is_map_visible = 1 AND wiki_page_name IS NOT NULL
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
                iconHash: (row.iconHash as string) ?? null
            });
        }
        stmt.free();
        return items;
    }

    /** Canonical facts keep their original identities when a hidden item aliases one visible item. */
    async getItemSources(): Promise<ItemSourceRow[]> {
        if (!this.db) throw new Error('DB not initialized');
        const provenance = this.getProvenance();
        const facts = provenance.acquisitions;
        const fishingBonuses = new Map<string, ItemAcquisition[]>();
        for (const fact of facts) {
            if (fact.kind !== 'fishing_bonus' || fact.probability_stage !== 'native_pool' ||
                fact.mechanic !== 'fishing_global_replacement' || fact.probability_kind !== 'exact') continue;
            const bonuses = fishingBonuses.get(fact.item_stable_key) ?? [];
            bonuses.push(fact);
            fishingBonuses.set(fact.item_stable_key, bonuses);
        }
        const metadata = new Map<string, ItemSourceItemMeta & { visible: boolean; price: number }>();
        const names: Record<string, string> = {};
        const pages: Record<string, string | null> = {};
        const itemStmt = this.db.prepare('SELECT * FROM items ORDER BY stable_key');
        while (itemStmt.step()) {
            const item = itemStmt.getAsObject();
            const key = item.stable_key as string;
            names[key] = item.display_name as string;
            pages[key] = item.wiki_page_name as string | null;
            metadata.set(key, { itemStableKey: key, displayName: names[key], wikiPageName: pages[key],
                iconHash: item.image_hash as string | null, visible: item.is_map_visible === 1,
                price: item.item_value as number });
        }
        itemStmt.free();
        const representatives = new Map<string, string>();
        const characters = this.db.prepare(`
            SELECT c.stable_key, c.display_name AS npc_name, c.wiki_page_name, d.group_key, d.is_map_visible
            FROM characters c LEFT JOIN character_deduplications d ON d.member_stable_key = c.stable_key
            ORDER BY c.stable_key
        `);
        while (characters.step()) {
            const row = characters.getAsObject();
            const key = row.stable_key as string;
            names[key] = row.npc_name as string;
            pages[key] = row.wiki_page_name as string | null;
            if (row.is_map_visible === 1 && !representatives.has(row.group_key as string)) {
                representatives.set(row.group_key as string, key);
                names[row.group_key as string] = names[key];
                pages[row.group_key as string] = pages[key];
            }
        }
        characters.free();
        for (const [table, name] of [['quests', 'display_name'], ['zones', 'display_name']] as const) {
            const statement = this.db.prepare(`SELECT stable_key, ${name} AS name${table === 'quests' ? ', wiki_page_name' : ''} FROM ${table}`);
            while (statement.step()) {
                const row = statement.getAsObject();
                names[row.stable_key as string] = row.name as string;
                if (table === 'quests') pages[row.stable_key as string] = row.wiki_page_name as string | null;
            }
            statement.free();
        }
        const classes = this.db.prepare('SELECT class_name, COALESCE(display_name, class_name) AS name FROM classes');
        while (classes.step()) {
            const row = classes.getAsObject();
            names[`class:${(row.class_name as string).toLowerCase()}`] = row.name as string;
        }
        classes.free();
        const visibleByPage = new Map<string, ItemSourceItemMeta[]>();
        for (const item of metadata.values()) {
            if (!item.visible || !item.wikiPageName?.trim()) continue;
            const group = visibleByPage.get(item.wikiPageName) ?? [];
            group.push(item);
            visibleByPage.set(item.wikiPageName, group);
        }
        const rows: ItemSourceRow[] = [];
        for (const fact of facts) {
            if (!provenance.actionableByKey.has(fact.acquisition_key)) continue;
            const original = metadata.get(fact.item_stable_key);
            if (!original) throw new Error(`Missing canonical acquisition item: ${fact.item_stable_key}`);
            const aliases = original.wikiPageName ? visibleByPage.get(original.wikiPageName) : undefined;
            const item = original.visible ? original : aliases?.length === 1 ? aliases[0] : null;
            if (!item) continue;
            const originatingDisposition = provenance.dispositionByKey.get(fact.item_stable_key)!;
            const displayDisposition = provenance.dispositionByKey.get(item.itemStableKey)!;
            if (displayDisposition.disposition !== 'current') continue;
            const characterKey = representatives.get(fact.source_group_key ?? fact.source_stable_key ?? '') ??
                (fact.source_copy_stable_key && names[fact.source_copy_stable_key] ? fact.source_copy_stable_key : null);
            const sourceKey = fact.source_stable_key;
            rows.push({
                itemStableKey: item.itemStableKey, displayName: item.displayName, wikiPageName: item.wikiPageName,
                iconHash: item.iconHash, kind: fact.kind, acquisitionKey: fact.acquisition_key,
                originatingItemStableKey: fact.item_stable_key, provenance: fact,
                originatingDisposition, displayDisposition,
                fishingBonus: fact.kind === 'fishing' && fact.probability_kind === 'exact'
                    ? fishingBonuses.get(fact.item_stable_key)?.find((bonus) => bonus.probability_min === fact.probability_min &&
                        bonus.probability_max === fact.probability_max) ?? null : null,
                sourceName: fact.kind === 'common_world_item' ? 'Any enemy with common drops' :
                    fact.kind === 'special_world_drop' ? 'Any enemy' :
                    fact.kind === 'auction_house' ? 'Auction House' :
                    fact.kind === 'ui_grant' && fact.mechanic === 'cosmetic_panel' ? 'Cosmetic panel' :
                    fact.kind === 'ui_grant' && fact.mechanic === 'planning_table' ? 'Planning table' :
                    fact.kind === 'mining' ? 'Mining node' : fact.kind === 'fishing' ? 'Fishable water' :
                    fact.kind === 'item_bag' ? 'Ground item' :
                    sourceKey ? (names[sourceKey] ?? (characterKey ? names[characterKey] : null) ?? sourceKey.replace(/^[^:]+:/, '').replaceAll('_', ' ')) : fact.kind.replaceAll('_', ' '),
                sourceWikiPageName: fact.kind === 'auction_house' ? 'Auction House' :
                    sourceKey ? (pages[sourceKey] ?? (characterKey ? pages[characterKey] : null) ?? null) : null,
                characterStableKey: characterKey, price: fact.kind === 'vendor' ? original.price : null,
                locationSources: Object.fromEntries(fact.locations.flatMap((location) => {
                    const copy = location.source_copy_stable_key;
                    return copy && names[copy] ? [[copy, { name: names[copy], wikiPageName: pages[copy] ?? null }]] : [];
                })),
                referenceNames: Object.fromEntries([...new Set([
                    ...fact.conditions.flatMap((condition) => condition.reference_stable_key ? [condition.reference_stable_key] : []),
                    ...fact.locations.flatMap((location) => [
                        ...(location.zone_stable_key ? [location.zone_stable_key] : []),
                        ...location.conditions.flatMap((condition) => condition.reference_stable_key ? [condition.reference_stable_key] : [])
                    ])
                ])].filter((key) => names[key]).map((key) => [key, names[key]]))
            });
        }
        return rows;
    }

    /**
     * Every map-visible character by display name, with the scenes that any
     * member of its deduplication group is placed in.
     *
     * Names are not identities. 39 display names are worn by more than one
     * deduplicated character, and for 22 of those the characters drop different
     * things. The live popup uses the scenes to prefer the characters that
     * actually exist where the player is standing.
     */
    async getCharactersByName(): Promise<Map<string, LiveCandidate[]>> {
        if (!this.db) throw new Error('DB not initialized');

        const stmt = this.db.prepare(`
            WITH reps AS (
                SELECT d.group_key, MIN(d.member_stable_key) AS rep_stable_key
                FROM character_deduplications d
                WHERE d.is_map_visible = 1
                GROUP BY d.group_key
            )
            SELECT DISTINCT
                c.display_name AS Name,
                c.stable_key AS StableKey,
                s.scene AS Scene
            FROM reps r
            JOIN characters c ON c.stable_key = r.rep_stable_key
            LEFT JOIN character_deduplications m ON m.group_key = r.group_key
            LEFT JOIN map_character_spawns s ON s.character_stable_key = m.member_stable_key
            ORDER BY c.display_name, c.stable_key, s.scene
        `);

        const byName = new Map<string, LiveCandidate[]>();
        while (stmt.step()) {
            const row = stmt.getAsObject();
            const name = row.Name as string;
            const stableKey = row.StableKey as string;
            const scene = row.Scene as string | null;

            let candidates = byName.get(name);
            if (!candidates) byName.set(name, (candidates = []));
            let candidate = candidates.at(-1);
            if (candidate?.stableKey !== stableKey) {
                candidate = { stableKey, scenes: [] };
                candidates.push(candidate);
            }
            if (scene !== null) candidate.scenes.push(scene);
        }
        stmt.free();
        return byName;
    }

    async getZoneEnemyInfo(zoneName: string): Promise<ZoneEnemyInfo> {
        if (!this.db) throw new Error('DB not initialized');
        const statement = this.db.prepare(`
            WITH representatives AS (
                SELECT group_key, MIN(member_stable_key) AS representative_key
                FROM character_deduplications WHERE is_map_visible = 1 GROUP BY group_key
            )
            SELECT representative.display_name AS Name, representative.wiki_page_name AS WikiPageName,
                representative.encounter_tier AS EncounterTier,
                MIN(combat_copy.level) AS Level, MAX(combat_copy.level) AS LevelMax
            FROM representatives
            JOIN characters representative ON representative.stable_key = representatives.representative_key
            JOIN character_deduplications member
                ON member.group_key = representatives.group_key AND member.is_map_visible = 1
            JOIN characters combat_copy
                ON combat_copy.stable_key = member.member_stable_key AND combat_copy.can_be_damaged = 1
            JOIN map_character_spawns placement ON placement.character_stable_key = combat_copy.stable_key
            WHERE placement.scene = ?
                AND combat_copy.encounter_tier IN ('boss', 'elite', 'enemy', 'chest')
                AND representative.encounter_tier IN ('boss', 'elite', 'enemy', 'chest')
            GROUP BY representative.stable_key
            ORDER BY Level, representative.display_name, representative.stable_key
        `, [zoneName]);
        const info: ZoneEnemyInfo = { levelRange: null, bosses: [], elites: [], chests: [] };
        try {
            while (statement.step()) {
                const row = statement.getAsObject();
                const level = row.Level as number;
                const levelMax = row.LevelMax as number;
                if (row.EncounterTier !== 'chest') {
                    info.levelRange = info.levelRange
                        ? { min: Math.min(info.levelRange.min, level), max: Math.max(info.levelRange.max, levelMax) }
                        : { min: level, max: levelMax };
                }
                const character = { name: row.Name as string, wikiPageName: row.WikiPageName as string | null, level, levelMax };
                if (row.EncounterTier === 'boss') info.bosses.push(character);
                else if (row.EncounterTier === 'elite') info.elites.push(character);
                else if (row.EncounterTier === 'chest') info.chests.push(character);
            }
        } finally {
            statement.free();
        }
        return info;
    }

    getWorldStats(): { zones: number; classes: number; items: number; quests: number } {
        if (!this.db) throw new Error('DB not initialized');
        const count = (query: string): number => {
            const res = this.db!.exec(query);
            return (res[0]?.values[0][0] as number) ?? 0;
        };
        return {
            zones: count('SELECT COUNT(*) FROM zones'),
            // Default is the game's template class, which players cannot pick.
            classes: count("SELECT COUNT(*) FROM classes WHERE class_name != 'Default'"),
            items: count('SELECT COUNT(*) FROM items'),
            quests: count('SELECT COUNT(*) FROM quests')
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

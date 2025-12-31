import { Repository } from '$lib/database.node';
import {
    buildZoneConfigs,
    buildZoneWorldPositions,
    calculateWorldCenter
} from '$lib/map/zone-config';
import { transformToMapCoords } from '$lib/map/config';
import type {
    ZoneConfig,
    ZoneWorldPosition,
    AchievementTriggerMarker,
    DoorMarker,
    EnemyMarker,
    ForgeMarker,
    ItemBagMarker,
    MiningNodeMarker,
    NpcMarker,
    SecretPassageMarker,
    TeleportMarker,
    TreasureLocMarker,
    WaterMarker,
    WishingWellMarker,
    ZoneLineMarker
} from '$lib/types/map';

export const prerender = true;

/**
 * Calculate zone bounds in game coordinates
 */
function getZoneGameBounds(config: ZoneConfig): {
    minX: number;
    minZ: number;
    maxX: number;
    maxZ: number;
} {
    const width = config.baseTilesX * config.tileSize;
    const height = config.baseTilesY * config.tileSize;
    return {
        minX: config.originX,
        minZ: config.originY,
        maxX: config.originX + width,
        maxZ: config.originY + height
    };
}

/**
 * Clamp a rectangle to bounds in game coordinates, returning null if no overlap
 */
function clampRectToBounds(
    rect: { minX: number; minZ: number; maxX: number; maxZ: number },
    bounds: { minX: number; minZ: number; maxX: number; maxZ: number }
): { minX: number; minZ: number; maxX: number; maxZ: number } | null {
    const clampedMinX = Math.max(rect.minX, bounds.minX);
    const clampedMinZ = Math.max(rect.minZ, bounds.minZ);
    const clampedMaxX = Math.min(rect.maxX, bounds.maxX);
    const clampedMaxZ = Math.min(rect.maxZ, bounds.maxZ);

    // Check if there's any overlap
    if (clampedMinX >= clampedMaxX || clampedMinZ >= clampedMaxZ) {
        return null;
    }

    return { minX: clampedMinX, minZ: clampedMinZ, maxX: clampedMaxX, maxZ: clampedMaxZ };
}

/**
 * Transform game coordinates to world map coordinates
 */
function transformToWorld(
    gameX: number,
    gameZ: number,
    zoneKey: string,
    zoneConfigs: Record<string, ZoneConfig>,
    zonePositions: ZoneWorldPosition[]
): [number, number] {
    const zonePos = zonePositions.find((z) => z.key === zoneKey);
    const zoneConfig = zoneConfigs[zoneKey];

    if (!zonePos) {
        throw new Error(`Zone position not found for: ${zoneKey}`);
    }
    if (!zoneConfig) {
        throw new Error(`Zone config not found for: ${zoneKey}`);
    }

    const [mapX, mapY] = transformToMapCoords(gameX, gameZ, zoneConfig.northBearing, 0, 0);

    return [mapX + zonePos.worldX, mapY + zonePos.worldY];
}

export async function load() {
    const repo = new Repository();
    await repo.init();

    // Query all zone bearings from database
    const bearings = await repo.getAllZoneNorthBearings();

    // Build zone configs and positions dynamically
    const zoneConfigs = buildZoneConfigs(bearings);
    const zonePositions = buildZoneWorldPositions(zoneConfigs);
    const worldCenter = calculateWorldCenter(zonePositions);

    // Calculate world bounds from all zone bounds
    let minX = Infinity,
        minY = Infinity,
        maxX = -Infinity,
        maxY = -Infinity;
    for (const zone of zonePositions) {
        minX = Math.min(minX, zone.bounds.minX);
        minY = Math.min(minY, zone.bounds.minY);
        maxX = Math.max(maxX, zone.bounds.maxX);
        maxY = Math.max(maxY, zone.bounds.maxY);
    }
    const worldBounds = { minX, minY, maxX, maxY };

    // Get zone keys for marker loading
    const zoneKeys = zonePositions.map((z) => z.key);

    // Load markers for each zone
    const achievementTriggers: AchievementTriggerMarker[] = [];
    const npcs: NpcMarker[] = [];
    const doors: DoorMarker[] = [];
    const forges: ForgeMarker[] = [];
    const itemBags: ItemBagMarker[] = [];
    const miningNodes: MiningNodeMarker[] = [];
    const secretPassages: SecretPassageMarker[] = [];
    const enemiesCommon: EnemyMarker[] = [];
    const enemiesRare: EnemyMarker[] = [];
    const enemiesUnique: EnemyMarker[] = [];
    const teleports: TeleportMarker[] = [];
    const treasureLocs: TreasureLocMarker[] = [];
    const water: WaterMarker[] = [];
    const wishingWells: WishingWellMarker[] = [];
    const zoneLines: ZoneLineMarker[] = [];

    for (const zoneKey of zoneKeys) {
        // Load spawn points (split by category and rarity for layer ordering)
        const zoneSpawnPoints = await repo.getSpawnPointMarkers(zoneKey);
        for (const marker of zoneSpawnPoints) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            // NPC spawn points go with NPCs, enemy spawn points sorted by rarity
            if (marker.category === 'npc') {
                npcs.push({
                    ...marker,
                    zone: zoneKey,
                    worldPosition: worldPos
                } as NpcMarker);
            } else {
                const enemyMarker = {
                    ...marker,
                    zone: zoneKey,
                    worldPosition: worldPos
                } as EnemyMarker;
                if (enemyMarker.isUnique) {
                    enemiesUnique.push(enemyMarker);
                } else if (enemyMarker.isRare) {
                    enemiesRare.push(enemyMarker);
                } else {
                    enemiesCommon.push(enemyMarker);
                }
            }
        }

        // Load NPCs and non-spawn enemies
        const zoneNpcsAndEnemies = await repo.getCharacterMarkers(zoneKey);
        for (const marker of zoneNpcsAndEnemies) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            // Sort into appropriate array based on category and rarity
            if (marker.category === 'npc') {
                npcs.push({
                    ...marker,
                    zone: zoneKey,
                    worldPosition: worldPos
                } as NpcMarker);
            } else {
                const enemyMarker = {
                    ...marker,
                    zone: zoneKey,
                    worldPosition: worldPos
                } as EnemyMarker;
                if (enemyMarker.isUnique) {
                    enemiesUnique.push(enemyMarker);
                } else if (enemyMarker.isRare) {
                    enemiesRare.push(enemyMarker);
                } else {
                    enemiesCommon.push(enemyMarker);
                }
            }
        }

        // Load zone lines (portals)
        const zoneZoneLines = await repo.getZoneLineMarkers(zoneKey);
        for (const marker of zoneZoneLines) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );

            // Calculate destination world position from landing coordinates
            // Landing position uses game coords (X=horizontal, Y=height, Z=depth)
            // For 2D map we use X and Z (ignoring Y height)
            let destinationWorldPos: [number, number] | null = null;
            const destZoneConfig = zoneConfigs[marker.destinationZone];
            const destZonePos = zonePositions.find((z) => z.key === marker.destinationZone);
            if (destZoneConfig && destZonePos) {
                destinationWorldPos = transformToWorld(
                    marker.landingPosition.x,
                    marker.landingPosition.z,
                    marker.destinationZone,
                    zoneConfigs,
                    zonePositions
                );
            }

            zoneLines.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos,
                destinationWorldPosition: destinationWorldPos
            });
        }

        // Load forges
        const zoneForges = await repo.getForgeMarkers(zoneKey);
        for (const marker of zoneForges) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            forges.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load wishing wells
        const zoneWishingWells = await repo.getWishingWellMarkers(zoneKey);
        for (const marker of zoneWishingWells) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            wishingWells.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load achievement triggers
        const zoneAchievementTriggers = await repo.getAchievementTriggerMarkers(zoneKey);
        for (const marker of zoneAchievementTriggers) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            achievementTriggers.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load doors
        const zoneDoors = await repo.getDoorMarkers(zoneKey);
        for (const marker of zoneDoors) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            doors.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load item bags
        const zoneItemBags = await repo.getItemBagMarkers(zoneKey);
        for (const marker of zoneItemBags) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            itemBags.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load mining nodes
        const zoneMiningNodes = await repo.getMiningNodeMarkers(zoneKey);
        for (const marker of zoneMiningNodes) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            miningNodes.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load secret passages
        const zoneSecretPassages = await repo.getSecretPassageMarkers(zoneKey);
        for (const marker of zoneSecretPassages) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            secretPassages.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load teleports
        const zoneTeleports = await repo.getTeleportMarkers(zoneKey);
        for (const marker of zoneTeleports) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            teleports.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load treasure locations
        const zoneTreasureLocs = await repo.getTreasureLocMarkers(zoneKey);
        for (const marker of zoneTreasureLocs) {
            const worldPos = transformToWorld(
                marker.position.x,
                marker.position.y,
                zoneKey,
                zoneConfigs,
                zonePositions
            );
            treasureLocs.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos
            });
        }

        // Load water (fishing spots) - compute polygon corners and clip to zone bounds
        const zoneWater = await repo.getWaterMarkers(zoneKey);
        const zoneConfig = zoneConfigs[zoneKey];
        const zoneBounds = getZoneGameBounds(zoneConfig);

        for (const marker of zoneWater) {
            // Compute water bounds in game coordinates
            const halfWidth = marker.width / 2;
            const halfHeight = marker.height / 2;
            const cx = marker.position.x;
            const cz = marker.position.y; // position.y is game Z coordinate

            const waterBounds = {
                minX: cx - halfWidth,
                minZ: cz - halfHeight,
                maxX: cx + halfWidth,
                maxZ: cz + halfHeight
            };

            // Clamp water to zone bounds in game coordinates
            const clampedBounds = clampRectToBounds(waterBounds, zoneBounds);
            if (!clampedBounds) continue; // Water completely outside zone

            // Transform clamped corners to world coordinates
            const corners: [number, number][] = [
                [clampedBounds.minX, clampedBounds.minZ],
                [clampedBounds.maxX, clampedBounds.minZ],
                [clampedBounds.maxX, clampedBounds.maxZ],
                [clampedBounds.minX, clampedBounds.maxZ]
            ];

            const worldPolygon = corners.map(([gx, gz]) =>
                transformToWorld(gx, gz, zoneKey, zoneConfigs, zonePositions)
            );

            // Use clamped center for world position
            const clampedCenterX = (clampedBounds.minX + clampedBounds.maxX) / 2;
            const clampedCenterZ = (clampedBounds.minZ + clampedBounds.maxZ) / 2;
            const worldPos = transformToWorld(
                clampedCenterX,
                clampedCenterZ,
                zoneKey,
                zoneConfigs,
                zonePositions
            );

            water.push({
                ...marker,
                zone: zoneKey,
                worldPosition: worldPos,
                worldPolygon
            });
        }
    }

    return {
        markers: {
            achievementTriggers,
            doors,
            enemiesCommon,
            enemiesRare,
            enemiesUnique,
            forges,
            itemBags,
            miningNodes,
            npcs,
            secretPassages,
            teleports,
            treasureLocs,
            water,
            wishingWells,
            zoneLines
        },
        zones: zonePositions,
        zoneConfigs,
        worldCenter,
        worldBounds
    };
}

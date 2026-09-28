import { error } from '@sveltejs/kit';
import { getMapsDatabasePath } from '$lib/database-path.server';
import { Repository } from '$lib/database.node';
import { compareEncounterTier, type Marker } from '$lib/map-markers';
import { MAPS } from '$lib/maps';
import type { EntryGenerator, PageServerLoad } from './$types';

/**
 * Prerendered per-zone pages. The zone slugs come from the same MAPS
 * registry the world map and sitemap use, so this stays in sync as zones
 * are added or removed. Search-param state (e.g. ?marker=...) is applied
 * client-side and does not affect the prerendered data.
 */
export const prerender = true;

export const entries: EntryGenerator = () => Object.keys(MAPS).map((mapName) => ({ mapName }));

export const load: PageServerLoad = async ({ params }) => {
    const { mapName } = params;
    if (!MAPS[mapName]) {
        error(404, `Unknown zone map: ${mapName}`);
    }

    const repo = new Repository();
    await repo.init(getMapsDatabasePath());
    try {
        const [
            northBearing,
            achievementMarkers,
            doorMarkers,
            forgeMarkers,
            itemBagMarkers,
            miningNodeMarkers,
            secretPassageMarkers,
            spawnPointMarkers,
            teleportMarkers,
            treasureLocMarkers,
            waterMarkers,
            wishingWellMarkers,
            zoneLineMarkers
        ] = await Promise.all([
            repo.getZoneNorthBearing(mapName),
            repo.getAchievementTriggerMarkers(mapName),
            repo.getDoorMarkers(mapName),
            repo.getForgeMarkers(mapName),
            repo.getItemBagMarkers(mapName),
            repo.getMiningNodeMarkers(mapName),
            repo.getSecretPassageMarkers(mapName),
            repo.getSpawnPointMarkers(mapName),
            repo.getTeleportMarkers(mapName),
            repo.getTreasureLocMarkers(mapName),
            repo.getWaterMarkers(mapName),
            repo.getWishingWellMarkers(mapName),
            repo.getZoneLineMarkers(mapName)
        ]);

        // Enemies before NPCs, and bosses last among enemies, so that the most
        // notable encounters are painted on top.
        spawnPointMarkers.sort((a, b) => {
            if (a.category !== b.category) return a.category === 'enemy' ? -1 : 1;
            if (a.category === 'enemy' && b.category === 'enemy') {
                return -compareEncounterTier(a.encounterTier, b.encounterTier);
            }
            return 0;
        });

        // Paint order: later markers draw on top.
        const markers: Marker[] = [
            ...waterMarkers,
            ...zoneLineMarkers,
            ...secretPassageMarkers,
            ...forgeMarkers,
            ...teleportMarkers,
            ...wishingWellMarkers,
            ...doorMarkers,
            ...miningNodeMarkers,
            ...treasureLocMarkers,
            ...itemBagMarkers,
            ...achievementMarkers,
            ...spawnPointMarkers
        ];

        return { northBearing, markers };
    } finally {
        repo.close();
    }
};

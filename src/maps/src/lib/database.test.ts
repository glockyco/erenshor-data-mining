import { describe, it, expect, beforeAll, afterAll } from 'vitest';
import { Repository } from './database.node';

let db: Repository;

beforeAll(async () => {
    db = new Repository();
    await db.init();
});

afterAll(() => {
    db.close();
});

describe('Repository', () => {
    it('gets achievement-trigger markers', async () => {
        const zone = 'Duskenlight';
        const markers = await db.getAchievementTriggerMarkers(zone);
        expect(Array.isArray(markers)).toBe(true);
        expect(markers.length).toBeGreaterThan(0);
        expect(markers[0].category).toBe('achievement-trigger');
    });
    it('gets door markers', async () => {
        const zone = 'Tutorial';
        const markers = await db.getDoorMarkers(zone);
        expect(Array.isArray(markers)).toBe(true);
        expect(markers.length).toBeGreaterThan(0);
        expect(markers[0].category).toBe('door');
    });
    it('gets mining-node markers', async () => {
        const zone = 'Braxonian';
        const markers = await db.getMiningNodeMarkers(zone);
        expect(Array.isArray(markers)).toBe(true);
        expect(markers.length).toBeGreaterThan(0);
        expect(markers[0].category).toBe('mining-node');
    });
    it('gets teleport markers', async () => {
        const zone = 'Silkengrass';
        const markers = await db.getTeleportMarkers(zone);
        expect(Array.isArray(markers)).toBe(true);
        expect(markers.length).toBeGreaterThan(0);
        expect(markers[0].category).toBe('teleport');
    });
    it('gets secret-passage markers', async () => {
        const zone = 'Jaws';
        const markers = await db.getSecretPassageMarkers(zone);
        expect(Array.isArray(markers)).toBe(true);
        expect(markers.length).toBeGreaterThan(0);
        expect(markers[0].category).toBe('secret-passage');
    });
    it('gets spawn-point markers (npcs and enemies)', async () => {
        const zone = 'Stowaway';
        const markers = await db.getSpawnPointMarkers(zone);
        expect(Array.isArray(markers)).toBe(true);
        expect(markers.length).toBeGreaterThan(0);
        // Function returns 'npc' or 'enemy' markers depending on spawn type
        expect(['npc', 'enemy']).toContain(markers[0].category);
    });
    it('gets zone-line markers', async () => {
        const zone = 'Stowaway';
        const markers = await db.getZoneLineMarkers(zone);
        expect(Array.isArray(markers)).toBe(true);
        expect(markers.length).toBeGreaterThan(0);
        expect(markers[0].category).toBe('zone-line');
    });
    it('gets all wiki items, including quest-unlocked vendor sources', async () => {
        const items = await db.getAllItems();
        expect(items.length).toBeGreaterThan(0);
        expect(items.every((item) => (item.wikiPageName?.trim().length ?? 0) > 0)).toBe(true);

        const enchantedSmithy = items.find(
            (item) => item.itemStableKey === 'item:furniture - enchanted smithy'
        );
        expect(enchantedSmithy).toBeDefined();

        const sources = await db.getItemSources();
        expect(
            sources.some(
                (source) =>
                    source.kind === 'vendor' &&
                    source.itemStableKey === 'item:furniture - enchanted smithy' &&
                    source.characterStableKey === 'character:breena carpenter'
            )
        ).toBe(true);

        const vendorItems = await db.getVendorItems('character:breena carpenter');
        expect(vendorItems.some((item) => item.name === 'Enchanted Smithy')).toBe(true);
    });

    it('gets all map-visible item acquisition sources', async () => {
        const rows = await db.getItemSources();
        expect(Array.isArray(rows)).toBe(true);
        expect(rows.length).toBeGreaterThan(0);

        for (const kind of ['drop', 'vendor', 'mining', 'fishing', 'bag'] as const) {
            expect(rows.some((row) => row.kind === kind)).toBe(true);
        }
        expect(rows.every((row) => row.itemStableKey.length > 0)).toBe(true);
        expect(rows.every((row) => row.displayName.length > 0)).toBe(true);
    });
});

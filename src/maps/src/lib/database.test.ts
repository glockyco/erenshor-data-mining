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
    it('gets character markers (npcs and enemies)', async () => {
        const zone = 'Azure';
        const markers = await db.getCharacterMarkers(zone);
        expect(Array.isArray(markers)).toBe(true);
        expect(markers.length).toBeGreaterThan(0);
        expect(['npc', 'enemy']).toContain(markers[0].category);
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
});

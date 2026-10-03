import { describe, expect, it } from 'vitest';
import { DEFAULT_LAYER_VISIBILITY } from '$lib/types/world-map';
import { parseLayerVisibility, serializeLayers } from './layer-url';

describe('layers URL parameter', () => {
    it('hides every spawn layer for the query that shipped companion overlays load', () => {
        expect(parseLayerVisibility('-sp,-spr,-spu,-npc')).toMatchObject({
            spawnPoints: false,
            spawnPointsElite: false,
            spawnPointsBoss: false,
            characters: false,
            spawnPointsChest: true
        });
    });

    it('writes current keys and reads them back', () => {
        const layers = { ...DEFAULT_LAYER_VISIBILITY, spawnPointsElite: false, spawnPointsBoss: false, spawnPointsChest: false };

        const serialized = serializeLayers(layers);

        expect(serialized).toBe('-spe,-spb,-spc');
        expect(parseLayerVisibility(serialized)).toEqual(layers);
    });
});

import { describe, expect, it } from 'vitest';
import { serializeSelection } from './selection';

describe('serializeSelection', () => {
    it('preserves not-found search URLs', () => {
        expect(
            serializeSelection({ type: 'search-not-found', searchType: 'enemy', name: 'Missing' })
        ).toBe('enemy:Missing');
        expect(
            serializeSelection({ type: 'search-not-found', searchType: 'zone', name: 'Unknown Zone' })
        ).toBe('zone:Unknown Zone');
    });

    it('does not serialize screen-space marker groups', () => {
        expect(serializeSelection({ type: 'marker-group', markers: [] })).toBeNull();
    });
});

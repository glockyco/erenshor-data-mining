import { describe, it, expect } from 'vitest';
import { canonicalUrl, SITE_URL } from './site';

describe('canonicalUrl', () => {
    it('maps root and empty path to the trailing-slash origin', () => {
        expect(canonicalUrl('/')).toBe(`${SITE_URL}/`);
        expect(canonicalUrl('')).toBe(`${SITE_URL}/`);
    });

    it('prefixes a leading slash when missing', () => {
        expect(canonicalUrl('map')).toBe(`${SITE_URL}/map`);
    });

    it('strips a trailing slash on non-root paths', () => {
        expect(canonicalUrl('/map/')).toBe(`${SITE_URL}/map`);
    });

    it('strips query strings', () => {
        expect(canonicalUrl('/map?sel=enemy:Reliquary+Ward')).toBe(`${SITE_URL}/map`);
    });

    it('strips hash fragments', () => {
        expect(canonicalUrl('/map#section')).toBe(`${SITE_URL}/map`);
    });

    it('strips both query and hash together', () => {
        expect(canonicalUrl('/map?sel=foo#x')).toBe(`${SITE_URL}/map`);
    });
});

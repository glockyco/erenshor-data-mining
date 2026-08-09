import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import ts from 'typescript';
import { describe, expect, it } from 'vitest';
import { GAME_VERSION_PATH } from '$lib/game-version';

/**
 * The two hostnames are served by two Cloudflare services with deliberately
 * opposite asset policies. Nothing at runtime catches a config that quietly
 * merges them back together, so the split is asserted here.
 */
interface WranglerConfig {
    name: string;
    main: string;
    workers_dev: boolean;
    routes?: { pattern: string; custom_domain?: boolean }[];
    assets: {
        directory: string;
        binding: string;
        run_worker_first: boolean | string[];
        html_handling: string;
        not_found_handling: string;
    };
}

function readConfig(fileName: string): WranglerConfig {
    const path = fileURLToPath(new URL(`../${fileName}`, import.meta.url));
    // These files are JSONC. TypeScript already ships a JSONC reader for
    // tsconfig, so this needs no extra dependency.
    const { config, error } = ts.parseConfigFileTextToJson(path, readFileSync(path, 'utf8'));
    expect(error).toBeUndefined();
    return config as WranglerConfig;
}

const site = readConfig('wrangler.jsonc');
const legacy = readConfig('wrangler.legacy.jsonc');

describe('canonical service', () => {
    it('serves the custom domain from the canonical entrypoint', () => {
        expect(site.name).toBe('erenshor-maps-site');
        expect(site.main).toBe('./src/site-worker.ts');
        expect(site.routes).toEqual([
            { pattern: 'erenshor.compendiums.org', custom_domain: true }
        ]);
    });

    it('leaves the workers.dev hostname to the compatibility service', () => {
        expect(site.workers_dev).toBe(false);
    });

    it('runs the Worker first only for the dynamic endpoint', () => {
        // Plain asset-first routing lets a static file at this path shadow the
        // endpoint and serve stale JSON, so the path must be listed.
        expect(site.assets.run_worker_first).toEqual([GAME_VERSION_PATH]);
    });
});

describe('compatibility service', () => {
    it('keeps the Worker name that the workers.dev hostname is derived from', () => {
        // Shipped companion overlays hardcode erenshor-maps.wowmuch1.workers.dev.
        expect(legacy.name).toBe('erenshor-maps');
        expect(legacy.main).toBe('./src/legacy-worker.ts');
        expect(legacy.workers_dev).toBe(true);
    });

    it('declares no route, so deploying it never moves the custom domain', () => {
        expect(legacy.routes).toBeUndefined();
    });

    it('runs the Worker first, because its routing depends on the hostname', () => {
        expect(legacy.assets.run_worker_first).toBe(true);
    });
});

describe('the two services together', () => {
    it('deploys one build to both, so responses cannot diverge', () => {
        expect(site.assets.directory).toBe('./build');
        expect(legacy.assets.directory).toBe(site.assets.directory);
    });

    it('matches asset-matching behaviour so shared paths resolve identically', () => {
        expect(site.assets.html_handling).toBe(legacy.assets.html_handling);
        expect(site.assets.not_found_handling).toBe(legacy.assets.not_found_handling);
    });

    it('gives each hostname exactly one owner', () => {
        const owningWorkersDev = [site, legacy].filter((config) => config.workers_dev);
        const owningCustomDomain = [site, legacy].filter((config) => config.routes?.length);

        expect(owningWorkersDev).toHaveLength(1);
        expect(owningCustomDomain).toHaveLength(1);
        expect(owningWorkersDev[0].name).not.toBe(owningCustomDomain[0].name);
    });
});

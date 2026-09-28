/**
 * Build the site from the deterministic map fixture into temporary
 * directories, then serve that build until the process receives SIGTERM or
 * SIGINT. The Playwright smoke test starts this script as its web server.
 *
 * Usage: node scripts/serve-fixture-site.mjs <port>
 */
import { mkdtemp, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { createMapDatabaseFixture } from '../src/lib/testing/map-database.js';

const port = Number(process.argv[2]);
if (!Number.isInteger(port) || port <= 0) {
    console.error('Usage: node scripts/serve-fixture-site.mjs <port>');
    process.exit(2);
}

const mapsDirectory = fileURLToPath(new URL('..', import.meta.url));
const temporaryDirectory = await mkdtemp(path.join(tmpdir(), 'erenshor-maps-site-'));
// SvelteKit resolves its output directory inside the project, so this one
// cannot live under the system temporary directory.
const svelteDirectory = await mkdtemp(path.join(mapsDirectory, '.svelte-kit-prerender-'));

async function cleanUp() {
    await rm(temporaryDirectory, { recursive: true, force: true });
    await rm(svelteDirectory, { recursive: true, force: true });
}

let server;
async function stop() {
    await server?.close();
    await cleanUp();
    process.exit(0);
}
process.once('SIGTERM', stop);
process.once('SIGINT', stop);

try {
    process.env.ERENSHOR_MAPS_DATABASE_PATH = await createMapDatabaseFixture(temporaryDirectory);
    process.env.ERENSHOR_MAPS_BUILD_DIR = path.join(temporaryDirectory, 'build');
    process.env.ERENSHOR_MAPS_SVELTE_OUT_DIR = path.relative(mapsDirectory, svelteDirectory);
    process.chdir(mapsDirectory);

    const { build, preview } = await import('vite');
    await build({ logLevel: 'warn' });
    server = await preview({ preview: { host: '127.0.0.1', port, strictPort: true } });
    server.printUrls();
} catch (error) {
    await cleanUp();
    throw error;
}

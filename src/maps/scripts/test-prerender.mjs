import assert from 'node:assert/strict';
import { mkdtemp, readFile, rm } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

import { createMapDatabaseFixture } from '../src/lib/testing/map-database.js';

const MAPS_DATABASE_PATH_ENV = 'ERENSHOR_MAPS_DATABASE_PATH';
const MAPS_BUILD_DIR_ENV = 'ERENSHOR_MAPS_BUILD_DIR';
const MAPS_SVELTE_OUT_DIR_ENV = 'ERENSHOR_MAPS_SVELTE_OUT_DIR';
const mapsDirectory = fileURLToPath(new URL('..', import.meta.url));

function restoreEnvironment(name, previous) {
    if (previous === undefined) {
        delete process.env[name];
    } else {
        process.env[name] = previous;
    }
}

async function assertPrerenderedHtml(outputDirectory, relativePath, expectedText) {
    const html = await readFile(path.join(outputDirectory, relativePath), 'utf8');
    assert.ok(
        html.includes(expectedText),
        `${relativePath} did not contain fixture evidence: ${expectedText}`
    );
}

const temporaryDirectory = await mkdtemp(path.join(tmpdir(), 'erenshor-maps-prerender-'));
const temporarySvelteDirectory = await mkdtemp(path.join(mapsDirectory, '.svelte-kit-prerender-'));
const outputDirectory = path.join(temporaryDirectory, 'build');
const previousDatabasePath = process.env[MAPS_DATABASE_PATH_ENV];
const previousBuildDirectory = process.env[MAPS_BUILD_DIR_ENV];
const previousSvelteOutDirectory = process.env[MAPS_SVELTE_OUT_DIR_ENV];
const previousWorkingDirectory = process.cwd();

try {
    process.env[MAPS_DATABASE_PATH_ENV] = await createMapDatabaseFixture(temporaryDirectory);
    process.env[MAPS_BUILD_DIR_ENV] = outputDirectory;
    process.env[MAPS_SVELTE_OUT_DIR_ENV] = path.relative(mapsDirectory, temporarySvelteDirectory);
    process.chdir(mapsDirectory);

    const { build } = await import('vite');
    await build();

    await assertPrerenderedHtml(outputDirectory, 'index.html', 'two classes');
    await assertPrerenderedHtml(outputDirectory, 'map.html', 'Fixture Enemy');
    await assertPrerenderedHtml(outputDirectory, 'maps/Stowaway.html', "Stowaway's Step");
    console.log('Fixture prerender smoke passed for /, /map, and /maps/Stowaway.');
} finally {
    process.chdir(previousWorkingDirectory);
    restoreEnvironment(MAPS_DATABASE_PATH_ENV, previousDatabasePath);
    restoreEnvironment(MAPS_BUILD_DIR_ENV, previousBuildDirectory);
    restoreEnvironment(MAPS_SVELTE_OUT_DIR_ENV, previousSvelteOutDirectory);
    await rm(temporaryDirectory, { recursive: true, force: true });
    await rm(temporarySvelteDirectory, { recursive: true, force: true });
}

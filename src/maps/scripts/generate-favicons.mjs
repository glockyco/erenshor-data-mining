#!/usr/bin/env node
/**
 * Generates the transparent browser favicons and the header logo from the PWA
 * icon. The flood-fill removes the app-badge background so the mark sits cleanly
 * on a dark surface (browser tab, site header).
 *
 * Deliberately does NOT touch apple-touch-icon.png or the PWA icons: home-screen
 * / installable icons need an opaque, background-safe badge.
 *
 * Run on demand when the logo changes: `node scripts/generate-favicons.mjs`.
 * Requires ImageMagick (`magick`) for the multi-resolution .ico.
 */
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';
import { rmSync } from 'node:fs';
import sharp from 'sharp';
import { makeTransparentIconBuffer } from './transparent-icon.mjs';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(root, 'static/icons/pwa-512.png');

const transparent = await makeTransparentIconBuffer(source);

// size -> output path (relative to project root)
const pngTargets = [
    [256, 'static/logo.png'], // header logo
    [128, 'static/favicon.png'],
    [48, 'static/favicon-48.png'], // only used to assemble the .ico
    [32, 'static/favicon-32.png'],
    [16, 'static/favicon-16.png']
];

for (const [size, out] of pngTargets) {
    await sharp(transparent).resize(size, size).png().toFile(resolve(root, out));
}

// Multi-resolution .ico for legacy/browser-tab fallback.
execFileSync(
    'magick',
    ['static/favicon-16.png', 'static/favicon-32.png', 'static/favicon-48.png', 'static/favicon.ico'],
    { cwd: root, stdio: 'inherit' }
);

// favicon-48 is only an intermediate for the .ico.
rmSync(resolve(root, 'static/favicon-48.png'), { force: true });

console.log('Wrote transparent logo.png + favicon.{png,ico,-16,-32}');

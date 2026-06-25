#!/usr/bin/env node
/**
 * Build-time renderer for static/og-default.png.
 *
 * Open Graph and Twitter card images need a raster asset. This composes the
 * existing PWA icon with site-wide brand text into a 1200x630 PNG, matching
 * the visual language used by the Ancient Kingdoms Compendium card.
 */

import { writeFileSync } from 'node:fs';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import { makeTransparentIconDataUrl } from './transparent-icon.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '..');
const iconPath = resolve(projectRoot, 'static/icons/pwa-512.png');
const outPath = resolve(projectRoot, 'static/og-default.png');

const WIDTH = 1200;
const HEIGHT = 630;

const iconDataUrl = await makeTransparentIconDataUrl(iconPath);

const svg = `<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="${WIDTH}" height="${HEIGHT}" viewBox="0 0 ${WIDTH} ${HEIGHT}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#0b1220" />
      <stop offset="100%" stop-color="#111c33" />
    </linearGradient>
    <filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="18" stdDeviation="18" flood-color="#000000" flood-opacity="0.35" />
    </filter>
  </defs>

  <rect width="${WIDTH}" height="${HEIGHT}" fill="url(#bg)" />
  <rect x="20" y="20" width="${WIDTH - 40}" height="${HEIGHT - 40}" fill="none" stroke="#1f2a44" stroke-width="2" rx="18" />

  <image href="${iconDataUrl}" x="70" y="145" width="315" height="315" filter="url(#softShadow)" />

  <text x="425" y="300" font-family="Inter, Helvetica, Arial, sans-serif" font-size="78" font-weight="700"><tspan fill="#f8fafc">Erenshor</tspan><tspan fill="#e2b15a" dx="22">Maps</tspan></text>
  <text x="425" y="358" font-family="Inter, Helvetica, Arial, sans-serif" font-size="32" font-weight="500" fill="#94a3b8">
    Interactive maps, companion mods, and data
  </text>
</svg>`;

const png = await sharp(Buffer.from(svg)).png().toBuffer();
writeFileSync(outPath, png);

console.log(`Wrote ${outPath} (${png.length} bytes, ${WIDTH}x${HEIGHT})`);

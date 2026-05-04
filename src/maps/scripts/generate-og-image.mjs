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

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '..');
const iconPath = resolve(projectRoot, 'static/icons/pwa-512.png');
const outPath = resolve(projectRoot, 'static/og-default.png');

const WIDTH = 1200;
const HEIGHT = 630;

const iconDataUrl = await makeTransparentIconDataUrl(iconPath);

async function makeTransparentIconDataUrl(path) {
    const bg = { r: 13, g: 27, b: 42 };
    const { data, info } = await sharp(path).ensureAlpha().raw().toBuffer({ resolveWithObject: true });
    const { width, height } = info;
    const visited = new Uint8Array(width * height);
    const queue = new Int32Array(width * height);
    let head = 0;
    let tail = 0;

    const isBackground = (pixel) => {
        const offset = pixel * 4;
        const distance =
            Math.abs(data[offset] - bg.r) +
            Math.abs(data[offset + 1] - bg.g) +
            Math.abs(data[offset + 2] - bg.b);
        return distance <= 44;
    };

    const enqueue = (pixel) => {
        if (visited[pixel] || !isBackground(pixel)) return;
        visited[pixel] = 1;
        queue[tail++] = pixel;
    };

    for (let x = 0; x < width; x += 1) {
        enqueue(x);
        enqueue((height - 1) * width + x);
    }
    for (let y = 0; y < height; y += 1) {
        enqueue(y * width);
        enqueue(y * width + width - 1);
    }

    while (head < tail) {
        const pixel = queue[head++];
        const x = pixel % width;
        const y = Math.floor(pixel / width);

        data[pixel * 4 + 3] = 0;

        if (x > 0) enqueue(pixel - 1);
        if (x < width - 1) enqueue(pixel + 1);
        if (y > 0) enqueue(pixel - width);
        if (y < height - 1) enqueue(pixel + width);
    }

    const png = await sharp(data, { raw: { width, height, channels: 4 } }).png().toBuffer();
    return `data:image/png;base64,${png.toString('base64')}`;
}

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

  <text x="425" y="260" font-family="Inter, Helvetica, Arial, sans-serif" font-size="76" font-weight="700" fill="#f8fafc">
    Erenshor
  </text>
  <text x="425" y="345" font-family="Inter, Helvetica, Arial, sans-serif" font-size="76" font-weight="700" fill="#22d3ee">
    Community Tools
  </text>
  <text x="425" y="420" font-family="Inter, Helvetica, Arial, sans-serif" font-size="32" font-weight="500" fill="#94a3b8">
    Maps, Mods, Guides, and Data
  </text>
</svg>`;

const png = await sharp(Buffer.from(svg)).png().toBuffer();
writeFileSync(outPath, png);

console.log(`Wrote ${outPath} (${png.length} bytes, ${WIDTH}x${HEIGHT})`);

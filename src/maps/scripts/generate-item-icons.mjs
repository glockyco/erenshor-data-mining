#!/usr/bin/env node
/**
 * Build-time generator for item icon WebP assets.
 *
 * Reads distinct item_icon_name values from the maps SQLite DB, finds the
 * matching PNG in the Unity Texture2D export, and converts each to WebP at
 * two display sizes (20px palette, 48px popup). Idempotent — skips icons
 * already converted.
 */
import { existsSync, mkdirSync, readFileSync, statSync } from 'node:fs';
import { resolve, join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import initSqlJs from 'sql.js/dist/sql-wasm.js';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '..');
const dbPath = resolve(projectRoot, 'static/db/erenshor.sqlite');
const outDir = resolve(projectRoot, 'static/items');

// Unity Texture2D export path — resolve relative to repo root.
// The maps build runs from the maps dir; the variant unity export lives at
// <repo>/variants/<variant>/unity/ExportedProject/Assets/Texture2D/
const variant = process.argv[2] ?? 'main';
const textureDir = resolve(projectRoot, '..', '..', 'variants', variant, 'unity', 'ExportedProject', 'Assets', 'Texture2D');

async function main() {
    if (!existsSync(dbPath)) {
        console.error(`DB not found: ${dbPath}`);
        process.exit(1);
    }
    if (!existsSync(textureDir)) {
        console.error(`Texture2D export not found: ${textureDir}`);
        console.error('Run `uv run erenshor extract export` first.');
        process.exit(1);
    }

    mkdirSync(outDir, { recursive: true });

    // Load DB and read distinct icon names
    const SQL = await initSqlJs({
        locateFile: () => resolve(projectRoot, 'node_modules/sql.js/dist/sql-wasm.wasm')
    });
    const dbBuffer = readFileSync(dbPath);
    const db = new SQL.Database(new Uint8Array(dbBuffer));

    const result = db.exec(`
        SELECT DISTINCT item_icon_name
        FROM items
        WHERE is_map_visible = 1 AND item_icon_name IS NOT NULL AND item_icon_name != ''
    `);
    db.close();

    if (result.length === 0) {
        console.log('Item icons: no icons to generate.');
        return;
    }

    const iconNames = result[0].values.map((row) => row[0]);

    let generated = 0;
    let skipped = 0;
    let missing = 0;

    for (const iconName of iconNames) {
        const sourcePng = join(textureDir, `${iconName}.png`);
        if (!existsSync(sourcePng)) {
            missing++;
            continue;
        }

        // Skip only when both WebP variants exist AND are at least as new as the
        // source PNG. Keying on mere existence stranded stale icons: a game update
        // can repoint an already-generated icon name (e.g. "8_2") at a different
        // sprite, and the old WebP would never be rebuilt.
        const w20 = join(outDir, `${iconName}.w20.webp`);
        const w48 = join(outDir, `${iconName}.w48.webp`);
        if (existsSync(w20) && existsSync(w48)) {
            const srcMtime = statSync(sourcePng).mtimeMs;
            if (statSync(w20).mtimeMs >= srcMtime && statSync(w48).mtimeMs >= srcMtime) {
                skipped++;
                continue;
            }
        }

        // Generate 20px (palette) and 48px (popup) WebP
        await sharp(sourcePng)
            .resize(20, 20, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
            .webp({ quality: 90 })
            .toFile(join(outDir, `${iconName}.w20.webp`));

        await sharp(sourcePng)
            .resize(48, 48, { fit: 'contain', background: { r: 0, g: 0, b: 0, alpha: 0 } })
            .webp({ quality: 90 })
            .toFile(join(outDir, `${iconName}.w48.webp`));

        generated++;
    }

    console.log(
        `Item icons: ${generated} generated, ${skipped} skipped (already exist), ${missing} missing (no source PNG).`
    );
}

main().catch((err) => {
    console.error(err);
    process.exit(1);
});

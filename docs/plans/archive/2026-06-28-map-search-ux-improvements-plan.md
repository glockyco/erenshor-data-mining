---
title: Map Search UX Improvements — Implementation Plan
type: plan
status: implemented
created: 2026-06-28
parent: 2026-06-28-map-search-ux-improvements
archived: 2026-06-28
---

# Map Search UX Improvements Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add category filter chips, item icons, Fuse.js fuzzy search, matched-substring highlighting, and arrow-key chip navigation to the `/map` command palette — covering both static results and live companion-mod entities.

**Architecture:** Layered changes across the search pipeline: a build-time Node script generates WebP item icons; `getItemDroppers` gains `iconName`; `searchMarkers` returns tiered (prefix → substring → Fuse fuzzy) matches with match-range metadata; `searchLiveEntities` gains match-range metadata without Fuse; `MapSearch.svelte` renders pill chips with live counts, icons, highlighted matches, and arrow-key navigation.

**Tech Stack:** SvelteKit, bits-ui `Command`, Svelte 5 (`$state`/`$derived`), TypeScript, Fuse.js (new runtime dep), sharp (existing dev dep), Node prebuild scripts.

**Spec:** `docs/plans/2026-06-28-map-search-ux-improvements.md`

---

## File Structure

**Create:**
- `src/maps/scripts/generate-item-icons.mjs` — build-time PNG→WebP icon conversion
- `src/maps/src/lib/map/search/fuse-index.ts` — Fuse instance wrapper + tiered search logic
- `src/maps/src/lib/map/search/match-highlight.ts` — match-range → rendered HTML segments helper
- `src/maps/src/lib/components/map/SearchChips.svelte` — the pill chip row component
- `src/maps/src/lib/map/search/fuse-index.test.ts` — Fuse tiered matching tests
- `src/maps/src/lib/map/search/match-highlight.test.ts` — highlight segmentation tests
- `src/maps/src/lib/components/map/SearchChips.test.ts` — chip count/filter tests

**Modify:**
- `src/maps/package.json` — add `fuse.js` dependency
- `src/maps/src/lib/map-markers.ts` — add `iconName` to `ItemDropperRow`
- `src/maps/src/lib/database.base.ts` — add `item_icon_name` to `getItemDroppers` query
- `src/maps/src/lib/map/search/types.ts` — add `iconName` to `ItemSearchResult`; add `SearchMatch` type
- `src/maps/src/lib/map/search/index.ts` — `searchMarkers` returns `SearchMatch[]`; tiered matching; Fuse integration
- `src/maps/src/lib/map/search/item-drop-provider.ts` — propagate `iconName`
- `src/maps/src/lib/components/map/MapSearch.svelte` — chips, icons, highlight, arrow nav, live chip
- `src/maps/src/lib/components/map/popups/SearchItemPopup.svelte` — 48px icon in header
- `src/erenshor/cli/commands/maps.py` — register `generate-item-icons.mjs` in prebuild

---

## Task 1: Add Fuse.js dependency and icon-name to data pipeline

**Files:**
- Modify: `src/maps/package.json`
- Modify: `src/maps/src/lib/map-markers.ts`
- Modify: `src/maps/src/lib/database.base.ts`

- [ ] **Step 1: Add fuse.js to package.json**

In `src/maps/package.json`, add to `dependencies`:
```json
"fuse.js": "^7.4.2"
```

Then install:
```bash
cd src/maps && pnpm install
```

- [ ] **Step 2: Add iconName to ItemDropperRow type**

In `src/maps/src/lib/map-markers.ts`, add `iconName` to the `ItemDropperRow` type (after `wikiPageName`):
```typescript
export type ItemDropperRow = {
    itemStableKey: string;
    displayName: string;
    wikiPageName: string | null;
    iconName: string | null;
    characterStableKey: string;
    npcName: string;
    isFriendly: boolean;
    isRare: boolean;
    isUnique: boolean;
    dropProbability: number; // 0–100
};
```

- [ ] **Step 3: Add item_icon_name to getItemDroppers query**

In `src/maps/src/lib/database.base.ts`, in the `getItemDroppers()` method, add `i.item_icon_name AS iconName` to the SELECT and push it into the row object:

```sql
SELECT
    i.stable_key        AS itemStableKey,
    i.display_name      AS displayName,
    i.wiki_page_name    AS wikiPageName,
    i.item_icon_name    AS iconName,
    c.stable_key        AS characterStableKey,
    c.npc_name          AS npcName,
    c.is_friendly       AS isFriendly,
    c.is_rare           AS isRare,
    c.is_unique         AS isUnique,
    ld.drop_probability AS dropProbability
FROM loot_drops ld
JOIN items i ON i.stable_key = ld.item_stable_key
JOIN characters c ON c.stable_key = ld.character_stable_key
WHERE i.is_map_visible = 1
ORDER BY i.display_name, ld.drop_probability DESC
```

And in the row push:
```typescript
rows.push({
    itemStableKey: row.itemStableKey as string,
    displayName: row.displayName as string,
    wikiPageName: (row.wikiPageName as string) ?? null,
    iconName: (row.iconName as string) ?? null,
    characterStableKey: row.characterStableKey as string,
    npcName: (row.npcName as string) ?? '',
    isFriendly: Boolean(row.isFriendly),
    isRare: Boolean(row.isRare),
    isUnique: Boolean(row.isUnique),
    dropProbability: row.dropProbability as number
});
```

- [ ] **Step 4: Verify the existing getItemDroppers test still passes**

Run: `cd src/maps && pnpm exec vitest run src/lib/database.test.ts`
Expected: PASS (the existing test checks row shape; `iconName` is additive)

- [ ] **Step 5: Commit**

```bash
git add src/maps/package.json src/maps/pnpm-lock.yaml src/maps/src/lib/map-markers.ts src/maps/src/lib/database.base.ts
git commit -m "feat(map): add fuse.js dep and iconName to item droppers"
```

---

## Task 2: Propagate iconName through ItemSearchResult

**Files:**
- Modify: `src/maps/src/lib/map/search/types.ts`
- Modify: `src/maps/src/lib/map/search/item-drop-provider.ts`
- Modify: `src/maps/src/lib/map/search/index.ts`

- [ ] **Step 1: Add iconName to ItemSearchResult**

In `src/maps/src/lib/map/search/types.ts`, add `iconName` to `ItemSearchResult`:
```typescript
export type ItemSearchResult = {
    type: 'item';
    itemStableKey: string;
    itemName: string;
    iconName: string | null;
    wikiPageName: string | null;
    dropperCount: number;
    zoneCount: number;
};
```

- [ ] **Step 2: Set iconName in ItemSearchProvider constructor**

In `src/maps/src/lib/map/search/item-drop-provider.ts`, in the constructor where `this.itemByStableKey.set(...)` is called, add `iconName` to the result object (read from `first.iconName`):
```typescript
this.itemByStableKey.set(itemStableKey, {
    result: {
        type: 'item',
        itemStableKey,
        itemName: first.displayName,
        iconName: first.iconName,
        wikiPageName: first.wikiPageName,
        dropperCount: characterStableKeys.length,
        zoneCount: zoneSet.size
    },
    characterStableKeys,
    dropRows: itemRows
});
```

- [ ] **Step 3: Update the item-drop-provider test fixture**

In `src/maps/src/lib/map/search/item-drop-provider.test.ts`, the `row()` helper must include `iconName`. Add `iconName: null` to the default in the `opts` spread:
```typescript
function row(
    itemStableKey: string,
    displayName: string,
    charStableKey: string,
    npcName: string,
    dropProbability: number,
    opts: Partial<ItemDropperRow> = {}
): ItemDropperRow {
    return {
        itemStableKey,
        displayName,
        wikiPageName: null,
        iconName: null,
        characterStableKey: charStableKey,
        npcName,
        isFriendly: false,
        isRare: false,
        isUnique: false,
        dropProbability,
        ...opts
    };
}
```

- [ ] **Step 4: Verify typecheck and tests pass**

Run: `cd src/maps && pnpm check && pnpm exec vitest run src/lib/map/search/`
Expected: 0 errors, all tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/maps/src/lib/map/search/types.ts src/maps/src/lib/map/search/item-drop-provider.ts src/maps/src/lib/map/search/item-drop-provider.test.ts
git commit -m "feat(map): propagate iconName through ItemSearchResult"
```

---

## Task 3: Build-time icon generation script

**Files:**
- Create: `src/maps/scripts/generate-item-icons.mjs`
- Modify: `src/erenshor/cli/commands/maps.py`

- [ ] **Step 1: Write the icon generation script**

Create `src/maps/scripts/generate-item-icons.mjs`:

```javascript
#!/usr/bin/env node
/**
 * Build-time generator for item icon WebP assets.
 *
 * Reads distinct item_icon_name values from the maps SQLite DB, finds the
 * matching PNG in the Unity Texture2D export, and converts each to WebP at
 * two display sizes (20px palette, 48px popup). Idempotent — skips icons
 * already converted.
 */
import { existsSync, readdirSync, mkdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { dirname } from 'node:path';
import { fileURLToPath } from 'node:url';
import sharp from 'sharp';
import initSqlJs from 'sql.js/dist/sql-wasm.js';
import { readFileSync } from 'node:fs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const projectRoot = resolve(__dirname, '..');
const dbPath = resolve(projectRoot, 'static/db/erenshor.sqlite');
const outDir = resolve(projectRoot, 'static/items');

// Unity Texture2D export path — resolve relative to repo root
// The maps build runs from the maps dir; the variant unity export lives at
// <repo>/variants/<variant>/unity/ExportedProject/Assets/Texture2D/
// We detect the variant from the DB path or accept a CLI arg.
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
    const SQL = await initSqlJs({ locateFile: () => resolve(projectRoot, 'node_modules/sql.js/dist/sql-wasm.wasm') });
    const dbBuffer = readFileSync(dbPath);
    const db = new SQL.Database(new Uint8Array(dbBuffer));

    const result = db.exec(`
        SELECT DISTINCT item_icon_name
        FROM items
        WHERE is_map_visible = 1 AND item_icon_name IS NOT NULL AND item_icon_name != ''
    `);
    db.close();

    if (result.length === 0) {
        console.log('No item icons to generate.');
        return;
    }

    const iconNames = result[0].values.map(row => row[0]);
    const existing = new Set(readdirSync(outDir).map(f => f.replace(/\.\w+\.webp$/, '')));

    let generated = 0;
    let skipped = 0;
    let missing = 0;

    for (const iconName of iconNames) {
        const sourcePng = join(textureDir, `${iconName}.png`);
        if (!existsSync(sourcePng)) {
            missing++;
            continue;
        }

        // Skip if both sizes already exist
        const w20Exists = existing.has(iconName);
        if (w20Exists) {
            skipped++;
            continue;
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

    console.log(`Item icons: ${generated} generated, ${skipped} skipped (already exist), ${missing} missing (no source PNG).`);
}

main().catch(err => {
    console.error(err);
    process.exit(1);
});
```

- [ ] **Step 2: Register the script in maps prebuild**

In `src/erenshor/cli/commands/maps.py`, in the prebuild section (after the `generate-og-image.mjs` line, before the DB copy), add:

```python
_run(["node", "scripts/generate-item-icons.mjs", cli_ctx.variant], maps_dir)
```

- [ ] **Step 3: Test the script manually**

Run: `cd src/maps && node scripts/generate-item-icons.mjs main`
Expected: prints "Item icons: N generated, 0 skipped, 0 missing" (N ≈ 1324)

Verify output: `ls src/maps/static/items/ | head` shows `*.w20.webp` and `*.w48.webp` files.

- [ ] **Step 4: Add static/items/ to gitignore if not already covered**

Check if `src/maps/static/items/` is gitignored. If not, add to `src/maps/.gitignore`:
```
static/items/
```
(Generated assets should not be committed — same as the DB copy.)

- [ ] **Step 5: Commit**

```bash
git add src/maps/scripts/generate-item-icons.mjs src/erenshor/cli/commands/maps.py src/maps/.gitignore
git commit -m "feat(map): add build-time item icon WebP generation"
```

---

## Task 4: Fuse index wrapper with tiered matching

**Files:**
- Create: `src/maps/src/lib/map/search/fuse-index.ts`
- Create: `src/maps/src/lib/map/search/fuse-index.test.ts`
- Modify: `src/maps/src/lib/map/search/types.ts` (add `SearchMatch` type)

- [ ] **Step 1: Add SearchMatch type to types.ts**

In `src/maps/src/lib/map/search/types.ts`, add after the `IndexEntry` interface:
```typescript
/** A search match with optional character range for highlighting. */
export type SearchMatch = {
    result: SearchResult;
    /** [start, end] offsets into the lowercased name for prefix/substring; null for fuzzy */
    matchRange: [number, number] | null;
};
```

- [ ] **Step 2: Write the failing test for tiered matching**

Create `src/maps/src/lib/map/search/fuse-index.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import type { IndexEntry, SearchResult } from './types';
import { searchTiered } from './fuse-index';

function enemy(name: string): IndexEntry {
    return { searchText: name.toLowerCase(), result: { type: 'enemy', name, effectiveRarity: 2, spawnCount: 1, zoneCount: 1 } };
}
function item(name: string): IndexEntry {
    return { searchText: name.toLowerCase(), result: { type: 'item', itemStableKey: `item:${name}`, itemName: name, iconName: null, wikiPageName: null, dropperCount: 1, zoneCount: 1 } };
}

const entries: IndexEntry[] = [
    enemy('Goblin'),
    enemy('Luminstone Guardian'),
    item('Luminstone'),
    item('Golden Luminstone Ring'),
    enemy('Orc')
];

describe('searchTiered', () => {
    it('returns prefix matches first with matchRange', () => {
        const matches = searchTiered('lumin', entries, 20);
        expect(matches.length).toBeGreaterThan(0);
        // Prefix matches should come first
        const first = matches[0];
        expect(first.matchRange).not.toBeNull();
        expect(first.matchRange).toEqual([0, 5]);
    });

    it('returns substring matches after prefix matches', () => {
        const matches = searchTiered('stone', entries, 20);
        // All should have matchRange
        for (const m of matches) {
            expect(m.matchRange).not.toBeNull();
        }
    });

    it('falls back to fuzzy matching for typos', () => {
        const matches = searchTiered('lumsten', entries, 20);
        expect(matches.length).toBeGreaterThan(0);
        // Fuzzy matches have null matchRange
        const hasFuzzy = matches.some(m => m.matchRange === null);
        expect(hasFuzzy).toBe(true);
    });

    it('returns empty array for queries shorter than 2 chars', () => {
        expect(searchTiered('l', entries, 20)).toEqual([]);
        expect(searchTiered('', entries, 20)).toEqual([]);
    });

    it('prefix matches rank above substring matches', () => {
        const matches = searchTiered('lumin', entries, 20);
        // "Luminstone" (prefix) should rank above "Golden Luminstone Ring" (substring)
        const luminstoneIdx = matches.findIndex(m => m.result.type === 'item' && m.result.itemName === 'Luminstone');
        const goldenIdx = matches.findIndex(m => m.result.type === 'item' && m.result.itemName === 'Golden Luminstone Ring');
        expect(luminstoneIdx).toBeLessThan(goldenIdx);
    });
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd src/maps && pnpm exec vitest run src/lib/map/search/fuse-index.test.ts`
Expected: FAIL with "Cannot find module './fuse-index'"

- [ ] **Step 4: Implement the fuse-index module**

Create `src/maps/src/lib/map/search/fuse-index.ts`:

```typescript
import Fuse from 'fuse.js';
import type { IndexEntry, SearchMatch, SearchResult } from './types';

/**
 * Tiered search: prefix → substring → Fuse fuzzy fallback.
 *
 * Each tier is fully exhausted before the next. Prefix and substring matches
 * carry matchRange for highlighting; fuzzy matches have null matchRange.
 * Within each tier, results keep their array order (already sorted by the
 * provider's buildIndex). The caller handles category interleaving.
 */
export function searchTiered(
    query: string,
    entries: IndexEntry[],
    limit: number
): SearchMatch[] {
    const q = query.toLowerCase().trim();
    if (q.length < 2) return [];

    const prefix: SearchMatch[] = [];
    const substring: SearchMatch[] = [];

    for (const entry of entries) {
        const startIdx = entry.searchText.indexOf(q);
        if (startIdx === 0) {
            prefix.push({
                result: entry.result,
                matchRange: [0, q.length]
            });
        } else if (startIdx > 0) {
            substring.push({
                result: entry.result,
                matchRange: [startIdx, startIdx + q.length]
            });
}
    }

    // Combine prefix + substring; if we have enough, skip fuzzy
    const exactMatches = [...prefix, ...substring];
    if (exactMatches.length >= limit) {
        return exactMatches.slice(0, limit);
    }

    // Fuse fallback for typos — only if exact matching didn't fill the limit
    const fuse = new Fuse(entries, {
        keys: ['searchText'],
        threshold: 0.4,
        distance: 100,
        minMatchCharLength: 2,
        includeScore: true,
        ignoreLocation: false
    });

    const fuzzyResults = fuse.search(q);
    const exactKeys = new Set(exactMatches.map(m => getMatchKey(m.result)));
    const fuzzy: SearchMatch[] = [];

    for (const fr of fuzzyResults) {
        if (exactKeys.has(getMatchKey(fr.item.result))) continue;
        fuzzy.push({
            result: fr.item.result,
            matchRange: null
        });
        if (exactMatches.length + fuzzy.length >= limit) break;
    }

    return [...exactMatches, ...fuzzy].slice(0, limit);
}

/** Stable key for deduplication — items use stableKey, others use name. */
function getMatchKey(result: SearchResult): string {
    return result.type === 'item' ? result.itemStableKey : result.name;
}
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd src/maps && pnpm exec vitest run src/lib/map/search/fuse-index.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 6: Commit**

```bash
git add src/maps/src/lib/map/search/fuse-index.ts src/maps/src/lib/map/search/fuse-index.test.ts src/maps/src/lib/map/search/types.ts
git commit -m "feat(map): add Fuse.js tiered search with match metadata"
```

---

## Task 5: Wire searchMarkers to return SearchMatch[]

**Files:**
- Modify: `src/maps/src/lib/map/search/index.ts`
- Modify: `src/maps/src/lib/components/map/MapSearch.svelte` (caller adaptation)

- [ ] **Step 1: Update searchMarkers signature and implementation**

In `src/maps/src/lib/map/search/index.ts`, replace the `searchMarkers` function to use `searchTiered` and return `SearchMatch[]`:

```typescript
import { searchTiered } from './fuse-index';
import type { SearchMatch } from './types';

export function searchMarkers(
    query: string,
    index: IndexEntry[],
    limit = 20
): SearchMatch[] {
    return searchTiered(query, index, limit);
}
```

Keep the existing `sortCategories` and `interleave` functions — but they now operate on `SearchMatch[]` instead of `SearchResult[]`. Update their signatures:

```typescript
function sortCategories(byCategory: Map<string, SearchMatch[]>): void {
    for (const [cat, results] of byCategory) {
        if (cat === 'enemy') {
            results.sort((a, b) => {
                const ae = a.result as EnemySearchResult;
                const be = b.result as EnemySearchResult;
                return ae.effectiveRarity - be.effectiveRarity || ae.name.localeCompare(be.name);
            });
        } else {
            results.sort((a, b) => sortName(a.result).localeCompare(sortName(b.result)));
        }
    }
}
```

The `interleave` function takes `Map<string, SearchMatch[]>` and outputs `SearchMatch[]`.

Update the bucket logic in `searchMarkers` to push `SearchMatch` objects (the `searchTiered` already returns them with `matchRange`).

**Note:** The round-robin interleave across categories should happen *after* `searchTiered` returns — `searchTiered` returns flat matches; `searchMarkers` groups them by category, sorts within category, then interleaves. Restructure `searchMarkers` to:
1. Call `searchTiered` to get flat `SearchMatch[]`
2. Group by `result.type` into buckets
3. `sortCategories` on each bucket
4. `interleave` across buckets

- [ ] **Step 2: Update MapSearch.svelte to consume SearchMatch[]**

In `src/maps/src/lib/components/map/MapSearch.svelte`, the `staticResults` state type changes:
```typescript
import { searchMarkers, type SearchMatch } from '$lib/map/search';
let staticResults = $state<SearchMatch[]>([]);
```

The `handleSelect` and rendering must access `.result` on each match. The `AnyResult` type updates:
```typescript
type AnyResult = { kind: 'static'; match: SearchMatch } | LiveSearchResult;
```

The `onselect` callback still receives `SearchResult` (extracted from `match.result`).

- [ ] **Step 3: Update searchLiveEntities to return match metadata**

In `src/maps/src/lib/components/map/MapSearch.svelte`, update `searchLiveEntities` to return match-range metadata:

```typescript
type LiveSearchMatch = {
    kind: 'live';
    entity: EntityData;
    zone: string;
    matchRange: [number, number] | null;
};

function searchLiveEntities(q: string): LiveSearchMatch[] {
    if (!liveZone || liveEntities.length === 0) return [];
    const lower = q.toLowerCase().trim();
    const zone = liveZone;
    const prefix: LiveSearchMatch[] = [];
    const substring: LiveSearchMatch[] = [];
    for (const entity of liveEntities) {
        const nameLower = entity.name.toLowerCase();
        const startIdx = nameLower.indexOf(lower);
        if (startIdx === 0) {
            prefix.push({ kind: 'live', entity, zone, matchRange: [0, lower.length] });
        } else if (startIdx > 0) {
            substring.push({ kind: 'live', entity, zone, matchRange: [startIdx, startIdx + lower.length] });
        }
    }
    return [...prefix, ...substring].slice(0, 5);
}
```

Update `liveResults` state type to `LiveSearchMatch[]`.

- [ ] **Step 4: Verify typecheck passes**

Run: `cd src/maps && pnpm check`
Expected: 0 errors (may need to fix rendering references to `.result` — trace and fix any type errors)

- [ ] **Step 5: Commit**

```bash
git add src/maps/src/lib/map/search/index.ts src/maps/src/lib/components/map/MapSearch.svelte
git commit -m "feat(map): wire searchMarkers to return match metadata"
```

---

## Task 6: Match-highlight helper

**Files:**
- Create: `src/maps/src/lib/map/search/match-highlight.ts`
- Create: `src/maps/src/lib/map/search/match-highlight.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/maps/src/lib/map/search/match-highlight.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { splitByMatchRange } from './match-highlight';

describe('splitByMatchRange', () => {
    it('splits a name into before/match/after segments', () => {
        const result = splitByMatchRange('Luminstone', [0, 5]);
        expect(result).toEqual([
            { text: 'Lumin', highlighted: true },
            { text: 'stone', highlighted: false }
        ]);
    });

    it('handles substring match in the middle', () => {
        const result = splitByMatchRange('Golden Luminstone Ring', [7, 16]);
        expect(result).toEqual([
            { text: 'Golden ', highlighted: false },
            { text: 'Luminstone', highlighted: true },
            { text: ' Ring', highlighted: false }
        ]);
    });

    it('returns single unhighlighted segment when range is null', () => {
        const result = splitByMatchRange('Luminstone', null);
        expect(result).toEqual([{ text: 'Luminstone', highlighted: false }]);
    });

    it('handles match at the end', () => {
        const result = splitByMatchRange('Luminstone', [5, 10]);
        expect(result).toEqual([
            { text: 'Lumin', highlighted: false },
            { text: 'stone', highlighted: true }
        ]);
    });

    it('returns full string highlighted when range covers all', () => {
        const result = splitByMatchRange('Lum', [0, 3]);
        expect(result).toEqual([{ text: 'Lum', highlighted: true }]);
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/maps && pnpm exec vitest run src/lib/map/search/match-highlight.test.ts`
Expected: FAIL with "Cannot find module './match-highlight'"

- [ ] **Step 3: Implement the helper**

Create `src/maps/src/lib/map/search/match-highlight.ts`:

```typescript
export type TextSegment = {
    text: string;
    highlighted: boolean;
};

/**
 * Split a display name into highlighted/unhighlighted segments based on a
 * match range. Returns a single unhighlighted segment when range is null
 * (fuzzy matches — no highlight).
 */
export function splitByMatchRange(
    name: string,
    range: [number, number] | null
): TextSegment[] {
    if (range === null) {
        return [{ text: name, highlighted: false }];
    }

    const [start, end] = range;
    const segments: TextSegment[] = [];

    if (start > 0) {
        segments.push({ text: name.slice(0, start), highlighted: false });
    }
    segments.push({ text: name.slice(start, end), highlighted: true });
    if (end < name.length) {
        segments.push({ text: name.slice(end), highlighted: false });
    }

    return segments;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/maps && pnpm exec vitest run src/lib/map/search/match-highlight.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 5: Commit**

```bash
git add src/maps/src/lib/map/search/match-highlight.ts src/maps/src/lib/map/search/match-highlight.test.ts
git commit -m "feat(map): add match-range highlight segmentation helper"
```

---

## Task 7: Render highlighted matches and item icons in palette rows

**Files:**
- Modify: `src/maps/src/lib/components/map/MapSearch.svelte`

- [ ] **Step 1: Import the highlight helper and add icon rendering**

In `src/maps/src/lib/components/map/MapSearch.svelte` script section, add:
```typescript
import { splitByMatchRange } from '$lib/map/search/match-highlight';
```

- [ ] **Step 2: Add item icon to palette rows**

In the static results `{#each}` loop, update the icon branch to show item sprites when available:

```svelte
{#if result.type === 'enemy'}
    <Skull class="h-4 w-4 shrink-0 text-amber-500" />
{:else if result.type === 'npc'}
    <User class="h-4 w-4 shrink-0 text-sky-500" />
{:else if result.type === 'item' && result.iconName}
    <img src={`/items/${result.iconName}.w20.webp`} alt="" class="h-5 w-5 shrink-0" />
{:else if result.type === 'item'}
    <Package class="h-4 w-4 shrink-0 text-emerald-500" />
{:else}
    <MapIcon class="h-4 w-4 shrink-0 text-purple-500" />
{/if}
```

- [ ] **Step 3: Render highlighted name in result rows**

Replace the plain `{getStaticResultLabel(result)}` with segmented rendering. Add a helper that takes the match and returns segments:

```typescript
function getResultSegments(match: SearchMatch): TextSegment[] {
    const name = match.result.type === 'item' ? match.result.itemName : match.result.name;
    return splitByMatchRange(name, match.matchRange);
}
```

In the template, replace:
```svelte
<div class="truncate">{getStaticResultLabel(result)}</div>
```
with:
```svelte
<div class="truncate">
    {#each getResultSegments(match) as seg}
        {#if seg.highlighted}
            <mark class="bg-transparent text-white font-semibold">{seg.text}</mark>
        {:else}
            {seg.text}
        {/if}
    {/each}
</div>
```

- [ ] **Step 4: Render highlighted live entity names**

Apply the same segmentation to live entity rows using their `matchRange`.

- [ ] **Step 5: Verify typecheck passes**

Run: `cd src/maps && pnpm check`
Expected: 0 errors

- [ ] **Step 6: Commit**

```bash
git add src/maps/src/lib/components/map/MapSearch.svelte
git commit -m "feat(map): render highlighted matches and item icons in palette"
```

---

## Task 8: SearchChips component

**Files:**
- Create: `src/maps/src/lib/components/map/SearchChips.svelte`
- Create: `src/maps/src/lib/components/map/search-chips.ts`
- Create: `src/maps/src/lib/components/map/search-chips.test.ts`

- [ ] **Step 1: Write the failing test for chip counts**

Create `src/maps/src/lib/components/map/search-chips.test.ts`:

```typescript
import { describe, it, expect } from 'vitest';
import { computeChipCounts } from './SearchChips.svelte';

describe('computeChipCounts', () => {
    it('counts static results by type', () => {
        const matches = [
            { result: { type: 'item', itemName: 'A' }, matchRange: null },
            { result: { type: 'item', itemName: 'B' }, matchRange: null },
            { result: { type: 'enemy', name: 'Goblin' }, matchRange: null },
        ];
        const counts = computeChipCounts(matches, 0);
        expect(counts.get('item')).toBe(2);
        expect(counts.get('enemy')).toBe(1);
        expect(counts.get('npc')).toBe(0);
        expect(counts.get('zone')).toBe(0);
    });

    it('includes live count when provided', () => {
        const matches = [
            { result: { type: 'item', itemName: 'A' }, matchRange: null },
        ];
        const counts = computeChipCounts(matches, 3);
        expect(counts.get('live')).toBe(3);
    });

    it('excludes live key when liveCount is 0', () => {
        const matches = [];
        const counts = computeChipCounts(matches, 0);
        expect(counts.has('live')).toBe(false);
    });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd src/maps && pnpm exec vitest run src/lib/components/map/search-chips.test.ts`
Expected: FAIL — module not found

- [ ] **Step 3: Implement the chip-count utility**

Create `src/maps/src/lib/components/map/search-chips.ts`:

```svelte
<script lang="ts">
    import type { SearchMatch } from '$lib/map/search';

    export type Category = 'all' | 'live' | 'item' | 'enemy' | 'npc' | 'zone';

    interface Props {
        activeCategory: Category;
        counts: Map<string, number>;
        onSelect: (cat: Category) => void;
    }

    let { activeCategory, counts, onSelect }: Props = $props();

    // Import the count computation from the utility module
    import { computeChipCounts } from './search-chips';

    // Chip order: All, Live (if present), Drops, Enemies, NPCs, Zones
    const chipOrder: { key: Category; label: string }[] = [
        { key: 'all', label: 'All' },
        { key: 'live', label: 'Live' },
        { key: 'item', label: 'Drops' },
        { key: 'enemy', label: 'Enemies' },
        { key: 'npc', label: 'NPCs' },
        { key: 'zone', label: 'Zones' }
    ];

    const visibleChips = $derived(
        chipOrder.filter(c => c.key === 'all' || (counts.get(c.key) ?? 0) > 0 || (c.key !== 'live' && counts.has(c.key)))
    );
</script>

<div class="flex items-center gap-1.5 px-2 py-1.5" role="group" aria-label="Filter by category">
    {#each visibleChips as chip (chip.key)}
        {@const count = counts.get(chip.key) ?? 0}
        {@const isActive = activeCategory === chip.key}
        {@const isDisabled = count === 0 && chip.key !== 'all'}
        <button
            type="button"
            class="rounded-full px-2.5 py-1 text-xs font-medium transition-colors
                   {isActive ? 'bg-accent text-accent-ink' : 'bg-surface-2 text-muted hover:text-ink'}
                   {isDisabled ? 'opacity-40 cursor-not-allowed' : ''}"
            aria-pressed={isActive}
            disabled={isDisabled}
            onclick={() => onSelect(chip.key)}
        >
            {chip.label}
            {#if count > 0}
                <span class="ml-1 opacity-70">({count})</span>
            {/if}
        </button>
    {/each}
</div>
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd src/maps && pnpm exec vitest run src/lib/components/map/search-chips.test.ts`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/maps/src/lib/components/map/SearchChips.svelte src/maps/src/lib/components/map/search-chips.ts src/maps/src/lib/components/map/search-chips.test.ts
git commit -m "feat(map): add SearchChips category filter component"
```

---

## Task 9: Wire chips, icons, and arrow-key navigation into MapSearch

**Files:**
- Modify: `src/maps/src/lib/components/map/MapSearch.svelte`

- [ ] **Step 1: Import SearchChips and add state**

In `src/maps/src/lib/components/map/MapSearch.svelte`:
```typescript
import SearchChips, { type Category } from './SearchChips.svelte';

let activeCategory = $state<Category>('all');
```

- [ ] **Step 2: Compute chip counts from results**

```typescript
const chipCounts = $derived.by(() => {
    const counts = new Map<string, number>();
    if (liveResults.length > 0) counts.set('live', liveResults.length);
    for (const m of staticResults) {
        const type = m.result.type;
        counts.set(type, (counts.get(type) ?? 0) + 1);
    }
    return counts;
});
```

- [ ] **Step 3: Filter results by active category**

```typescript
const filteredStatic = $derived(
    activeCategory === 'all' || activeCategory === 'live'
        ? staticResults
        : staticResults.filter(m => m.result.type === activeCategory)
);
const filteredLive = $derived(
    activeCategory === 'all' || activeCategory === 'live'
        ? liveResults
        : []
);
```

- [ ] **Step 4: Render the chip row in the template**

Below the search input, above the results list:
```svelte
<SearchChips
    activeCategory={activeCategory}
    counts={chipCounts}
    onSelect={(cat) => activeCategory = cat}
/>
```

- [ ] **Step 5: Add arrow-key category navigation**

Add a keydown handler on the chip container that switches category on `←`/`→`:

```typescript
function handleChipKeydown(e: KeyboardEvent) {
    const order: Category[] = ['all', 'live', 'item', 'enemy', 'npc', 'zone'];
    const available = order.filter(c => c === 'all' || (chipCounts.get(c) ?? 0) > 0 || c === 'live');
    const currentIdx = available.indexOf(activeCategory);
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
        e.preventDefault();
        const dir = e.key === 'ArrowRight' ? 1 : -1;
        const nextIdx = (currentIdx + dir + available.length) % available.length;
        activeCategory = available[nextIdx];
    }
}
```

Bind it on the chip container: `<div onkeydown={handleChipKeydown} ...>`

- [ ] **Step 6: Use filtered results in the render loop**

Replace the `{#each groupStaticByCategory(staticResults) ...}` with `filteredStatic`, and the live results `{#if liveResults.length > 0}` with `filteredLive`.

- [ ] **Step 7: Verify typecheck passes**

Run: `cd src/maps && pnpm check`
Expected: 0 errors

- [ ] **Step 8: Commit**

```bash
git add src/maps/src/lib/components/map/MapSearch.svelte
git commit -m "feat(map): wire filter chips and arrow-key navigation"
```

---

## Task 10: Item icon in SearchItemPopup header

**Files:**
- Modify: `src/maps/src/lib/components/map/popups/SearchItemPopup.svelte`

- [ ] **Step 1: Add 48px icon to popup header**

In `src/maps/src/lib/components/map/popups/SearchItemPopup.svelte`, update the summary/header row to show the icon:

```svelte
<div class="flex items-center justify-between">
    <div class="flex items-center gap-3">
        {#if result.iconName}
            <img src={`/items/${result.iconName}.w48.webp`} alt="" class="h-12 w-12" />
        {/if}
        <div class="text-sm text-zinc-300">
            {result.dropperCount} dropper{result.dropperCount !== 1 ? 's' : ''}
        </div>
    </div>
    <WikiLink pageName={result.wikiPageName} />
</div>
```

- [ ] **Step 2: Verify typecheck passes**

Run: `cd src/maps && pnpm check`
Expected: 0 errors

- [ ] **Step 3: Commit**

```bash
git add src/maps/src/lib/components/map/popups/SearchItemPopup.svelte
git commit -m "feat(map): show item icon in search popup header"
```

---

## Task 11: Final verification and cleanup

- [ ] **Step 1: Run full maps build**

Run: `uv run erenshor maps build`
Expected: lint ✓, typecheck ✓, all tests ✓, prerender ✓ (including icon generation)

- [ ] **Step 2: Smoke test in browser**

Start dev server: `cd src/maps && pnpm exec vite dev --port 5175`

Test with `_browser` tool:
1. Navigate to `http://localhost:5175/map`
2. Open search, type "lumin" — verify chips appear with counts, item icons show, "Lumin" is bolded
3. Type "lumsten" — verify fuzzy fallback returns "Luminstone" (no highlight)
4. Click the "Drops" chip — verify results filter to items only
5. Press Tab then ←/→ — verify category switches
6. Select an item — verify popup shows 48px icon

- [ ] **Step 3: Run all tests**

Run: `cd src/maps && pnpm exec vitest run`
Expected: all tests PASS

- [ ] **Step 4: Mark plan complete**

```bash
omp-plans complete 2026-06-28-map-search-ux-improvements
```

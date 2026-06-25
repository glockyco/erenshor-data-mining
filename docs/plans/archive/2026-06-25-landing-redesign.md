---
title: Landing Page Redesign (Erenshor Maps) — Implementation
type: plan
status: implemented
created: 2026-06-25
archived: 2026-06-25
parent: 2026-06-25-landing-redesign-design
---

# Erenshor Maps Landing Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the anemic world-map-preview landing with a proper "Erenshor Maps" home page (hero, tool previews, prose, official/community links, interactive coordinate layer) and establish a shared design-token system + restyled header/footer chrome.

**Architecture:** A new design-token theme (`@theme` in `app.css`) drives Tailwind utilities. The shared `(app)` layout gets a real `SiteHeader` + `SiteFooter` (replacing the gradient tab bar). The landing route composes small Svelte 5 components; `(app)/+page.server.ts` injects world stats counted from the clean DB at prerender time. A small interactive module wires a live coordinate HUD and real page-coordinate survey tags. Inner page bodies are out of scope (they inherit the new chrome/tokens; their internal styling migrates later).

**Tech Stack:** SvelteKit (Svelte 5 runes, prerendered, `adapter-static`/Cloudflare), Tailwind v4, sql.js (`$lib/database.node`), `@fontsource` self-hosted fonts, vitest + Playwright.

**Visual source of truth:** `docs/mockups/landing/index.html` (committed). Where a step says "port from the mock," copy the exact CSS/markup from the named section of that file. All commands run from `src/maps/` unless noted; use `pnpm`.

**Design spec:** `docs/plans/2026-06-25-landing-redesign-design.md`.

**Conventions:** Implement inline in the main tree (no worktrees — Erenshor AGENTS.md). Conventional Commits via `skill://commit`. Run gates once at the end (subagents skip gates).

---

## File structure

| File | Responsibility |
|---|---|
| `src/maps/src/app.css` | `@theme` design tokens (colors, radius, fonts) |
| `src/maps/src/routes/+layout.svelte` | add self-hosted font imports (root; wraps everything) |
| `src/maps/src/app.html` | `theme-color` → `#0a0e14` |
| `src/maps/src/lib/seo/site.ts` | rename to "Erenshor Maps"; titles/description |
| `src/maps/src/lib/seo/jsonld.ts` | reflect rename in JSON-LD |
| `src/maps/src/lib/components/map/popups/SearchNotFoundContent.svelte` | Discord invite → `discord.gg/erenshor` |
| `src/maps/src/lib/database.base.ts` | `getWorldStats()` method |
| `src/maps/tests/world-stats.test.ts` | unit test for `getWorldStats()` |
| `src/maps/src/routes/(app)/+page.server.ts` | **new** — world stats load (prerender) |
| `src/maps/src/lib/components/landing/SiteHeader.svelte` | wordmark, nav, social icons, mobile menu |
| `src/maps/src/lib/components/landing/SiteFooter.svelte` | disclaimer + quick links |
| `src/maps/src/lib/components/landing/Hero.svelte` | masthead + `CompassRuler` |
| `src/maps/src/lib/components/landing/CompassRuler.svelte` | W·▲N·E tick ruler |
| `src/maps/src/lib/components/landing/ToolsSection.svelte` | flagship tile + 4-up grid |
| `src/maps/src/lib/components/landing/AboutSection.svelte` | dual prose + watermark + coord tags |
| `src/maps/src/lib/components/landing/CommunitySection.svelte` | grouped link lists |
| `src/maps/src/lib/components/landing/SectionDivider.svelte` | understated divider |
| `src/maps/src/lib/components/landing/CoordTag.svelte` | coordinate tag (heading) |
| `src/maps/src/lib/components/landing/coordinates.ts` | HUD + survey-tag interaction (onMount) |
| `src/maps/src/lib/components/landing/CoordHud.svelte` | fixed live coordinate HUD |
| `src/maps/src/lib/components/landing/icons.ts` | inline SVG path strings (brand + line icons) |
| `src/maps/src/routes/(app)/+page.svelte` | compose the landing |
| `src/maps/package.json` | `@fontsource/*` deps |

Naming/links/copy come verbatim from the spec §9 table and the mock; do not paraphrase link descriptions.

---

## Task 1: Design tokens, fonts, theme-color

**Files:**
- Modify: `src/maps/src/app.css`
- Modify: `src/maps/src/routes/+layout.svelte`
- Modify: `src/maps/src/app.html`
- Modify: `src/maps/package.json` (via pnpm add)

- [ ] **Step 1: Install self-hosted fonts**

Run: `pnpm add @fontsource/hanken-grotesk @fontsource/jetbrains-mono`
Expected: both added under `dependencies`.

- [ ] **Step 2: Define tokens in `app.css`**

Replace the entire file contents with:

```css
@import 'tailwindcss';

@theme {
    --color-bg: #0a0e14;
    --color-surface: #111922;
    --color-surface-2: #18222e;
    --color-ink: #e8eff6;
    --color-muted: #94a6b8;
    --color-line: #1f2c39;
    --color-accent: #e2b15a;
    --color-accent-ink: #0a0e14;
    --color-accent-2: #5ab0c8;
    --radius-card: 12px;
    --font-display: 'Hanken Grotesk', ui-sans-serif, system-ui, sans-serif;
    --font-mono: 'JetBrains Mono', ui-monospace, monospace;
}

body {
    background-color: var(--color-bg);
    color: var(--color-ink);
    font-family: var(--font-display);
}
```

This makes utilities like `bg-bg`, `bg-surface`, `text-ink`, `text-muted`, `text-accent`, `text-accent-ink`, `border-line`, `rounded-card`, `font-display`, `font-mono` available.

- [ ] **Step 3: Import fonts in the root layout**

In `src/maps/src/routes/+layout.svelte`, add to the top of `<script>` (after the existing imports, before `import '../app.css'`):

```ts
import '@fontsource/hanken-grotesk/400.css';
import '@fontsource/hanken-grotesk/500.css';
import '@fontsource/hanken-grotesk/600.css';
import '@fontsource/hanken-grotesk/700.css';
import '@fontsource/hanken-grotesk/800.css';
import '@fontsource/jetbrains-mono/400.css';
import '@fontsource/jetbrains-mono/500.css';
```

- [ ] **Step 4: Update theme-color**

In `src/maps/src/app.html`, change `<meta name="theme-color" content="#0d1b2a" />` to `content="#0a0e14"`.

- [ ] **Step 5: Verify build compiles**

Run: `pnpm check`
Expected: no new errors from these files.

- [ ] **Step 6: Commit**

```bash
git add src/maps/src/app.css src/maps/src/routes/+layout.svelte src/maps/src/app.html src/maps/package.json src/maps/pnpm-lock.yaml
git commit -m "feat(map): add Erenshor Maps design tokens and self-hosted fonts"
```

---

## Task 2: SEO rename + Discord standardization

**Files:**
- Modify: `src/maps/src/lib/seo/site.ts`
- Modify: `src/maps/src/lib/seo/jsonld.ts:31-37` (verify `name`/`url`/`sameAs`)
- Modify: `src/maps/src/lib/components/map/popups/SearchNotFoundContent.svelte:27`

- [ ] **Step 1: Rename brand in `site.ts`**

In `src/maps/src/lib/seo/site.ts` set:

```ts
export const SITE_NAME = 'Erenshor Maps';
export const DEFAULT_TITLE = 'Erenshor Maps – Interactive Maps, Data & Mods';
export const DEFAULT_DESCRIPTION =
    'Interactive maps, reference data, and companion mods for Erenshor, the single-player simulated MMORPG. Spawn points, NPC markers, item drop data, and live in-game tracking, refreshed every patch.';
```

Leave `SITE_AUTHOR` and URL helpers unchanged (the author meta is non-visible; spec §10).

- [ ] **Step 2: Verify JSON-LD reflects the rename**

Read `src/maps/src/lib/seo/jsonld.ts`. Ensure the website/webApplication JSON-LD `name` derives from `SITE_NAME` (it should via import). If `videoGameJsonLd` hardcodes a publisher/name, leave the *game's* name ("Erenshor") as-is — only the *site* brand changes. No code change unless a literal "Erenshor Community Tools" appears; if it does, replace with `SITE_NAME`.

- [ ] **Step 3: Standardize the Discord invite**

In `SearchNotFoundContent.svelte`, change the `href="https://discord.gg/fTvgzKy5"` to `href="https://discord.gg/erenshor"`.

- [ ] **Step 4: Verify**

Run: `pnpm check`
Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add src/maps/src/lib/seo/site.ts src/maps/src/lib/seo/jsonld.ts src/maps/src/lib/components/map/popups/SearchNotFoundContent.svelte
git commit -m "feat(map): rebrand site to Erenshor Maps; use official Discord vanity"
```

---

## Task 3: `getWorldStats()` + unit test

**Files:**
- Modify: `src/maps/src/lib/database.base.ts` (add method to `RepositoryBase`, before the closing `}` at line ~1246)
- Test: `src/maps/tests/world-stats.test.ts`

- [ ] **Step 1: Write the failing test**

Create `src/maps/tests/world-stats.test.ts`:

```ts
import { describe, it, expect } from 'vitest';
import initSqlJs from 'sql.js/dist/sql-wasm.js';
import path from 'path';
import { RepositoryBase } from '$lib/database.base';

// Subclass to inject an in-memory DB built with known row counts, so the test
// asserts the counting logic — not whatever the current game data happens to be.
class TestRepo extends RepositoryBase {
    async initWith(sql: Awaited<ReturnType<typeof initSqlJs>>) {
        this.SQL = sql;
        this.db = new sql.Database();
        this.db.run(`
            CREATE TABLE zones (id INTEGER);
            CREATE TABLE classes (id INTEGER);
            CREATE TABLE items (id INTEGER);
            CREATE TABLE quests (id INTEGER);
            INSERT INTO zones (id) VALUES (1),(2),(3);
            INSERT INTO classes (id) VALUES (1),(2);
            INSERT INTO items (id) VALUES (1),(2),(3),(4);
            INSERT INTO quests (id) VALUES (1);
        `);
    }
}

describe('getWorldStats', () => {
    it('counts rows per world table', async () => {
        const sql = await initSqlJs({
            locateFile: () => path.resolve('node_modules/sql.js/dist/sql-wasm.wasm')
        });
        const repo = new TestRepo();
        await repo.initWith(sql);
        expect(repo.getWorldStats()).toEqual({ zones: 3, classes: 2, items: 4, quests: 1 });
    });
});
```

- [ ] **Step 2: Run it to verify it fails**

Run: `pnpm test -- world-stats`
Expected: FAIL — `getWorldStats is not a function`.

- [ ] **Step 3: Implement `getWorldStats()`**

In `src/maps/src/lib/database.base.ts`, add this method inside `RepositoryBase` (before its closing brace):

```ts
    getWorldStats(): { zones: number; classes: number; items: number; quests: number } {
        if (!this.db) throw new Error('DB not initialized');
        const count = (table: string): number => {
            const res = this.db!.exec(`SELECT COUNT(*) AS n FROM ${table}`);
            return (res[0]?.values[0][0] as number) ?? 0;
        };
        return {
            zones: count('zones'),
            classes: count('classes'),
            items: count('items'),
            quests: count('quests')
        };
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pnpm test -- world-stats`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/maps/src/lib/database.base.ts src/maps/tests/world-stats.test.ts
git commit -m "feat(map): add getWorldStats DB counts with test"
```

---

## Task 4: Landing server load (world stats)

**Files:**
- Create: `src/maps/src/routes/(app)/+page.server.ts`

- [ ] **Step 1: Create the load**

```ts
import type { PageServerLoad } from './$types';
import { Repository } from '$lib/database.node';

export const prerender = true;

export const load: PageServerLoad = async () => {
    const repo = new Repository();
    await repo.init();
    try {
        return { stats: repo.getWorldStats() };
    } finally {
        repo.close();
    }
};
```

- [ ] **Step 2: Verify it runs at build (stdout visible)**

Run: `pnpm build`
Expected: build succeeds; no errors from `(app)/+page.server.ts`. (Per the interactive-map skill, prerendered server loads execute during build.)

- [ ] **Step 3: Commit**

```bash
git add "src/maps/src/routes/(app)/+page.server.ts"
git commit -m "feat(map): load world stats for the landing page"
```

---

## Task 5: Icons module

**Files:**
- Create: `src/maps/src/lib/components/landing/icons.ts`

- [ ] **Step 1: Extract icon SVGs**

Create `icons.ts` exporting the inner SVG markup used in the mock. Copy the exact `<path>`/`<line>` contents from `docs/mockups/landing/index.html`:
- Brand icons (header), `fill="currentColor"`, 24×24: `steam`, `discord`, `kofi` — from the `.header-icons` block.
- Line icons (community list), stroke style, 24×24: `steam` (gamepad), `globe`, `discord`, `wiki` (book-open), `vault` (database), `lunaris` (package), `guide` (map), `kofi` (heart) — from the `.link .ic` blocks.
- HUD `crosshair` icon.

```ts
// Brand glyphs (filled). Inner markup only; caller wraps in <svg>.
export const brand = {
    steam: `<path d="..."/>`,   // copy from mock .header-icons Steam
    discord: `<path d="..."/>`, // copy from mock .header-icons Discord
    kofi: `<path d="..."/>`     // copy from mock .header-icons Ko-fi
};
// Line glyphs (stroke). Inner markup only.
export const line = {
    steam: `...`, globe: `...`, discord: `...`, wiki: `...`,
    vault: `...`, lunaris: `...`, guide: `...`, kofi: `...`, crosshair: `...`
};
```

Render with `{@html}` inside an `<svg viewBox="0 0 24 24">` wrapper in each component.

- [ ] **Step 2: Commit**

```bash
git add "src/maps/src/lib/components/landing/icons.ts"
git commit -m "feat(map): add landing icon set"
```

---

## Task 6: SiteHeader + SiteFooter

**Files:**
- Create: `src/maps/src/lib/components/landing/SiteHeader.svelte`
- Create: `src/maps/src/lib/components/landing/SiteFooter.svelte`

- [ ] **Step 1: SiteHeader**

Svelte 5 component. Wordmark `Erenshor` + `<span class="text-accent">Maps</span>`; nav links (World Map → `/map`, Zone Maps → `/zone-maps`, Adventure Guide → `/adventure-guide`, Mods → `/mod`, Spreadsheet → `/spreadsheet`); social icon cluster (Steam/Discord/Ko-fi from `icons.brand`, with `aria-label`/`title`, URLs from spec §9). Use the `eslint-disable svelte/no-navigation-without-resolve` comment pattern already used in the repo for internal `href`s.

Mobile: below `md`, hide the text nav and show a menu button that toggles a dropdown panel of the same links (state via `$state(false)`). Social icons stay visible. Use Tailwind utilities + token colors. Port the visual treatment (spacing, hover `text-accent`, icon sizing, border-left divider on the icon cluster) from the mock `header` block.

- [ ] **Step 2: SiteFooter**

Port from the mock `<footer>`: two spans — disclaimer "Erenshor Maps. A fan project, not affiliated with Burgee Media." and quick links (erenshor.com · wiki · discord). **Use only vertical padding** (`py-*`) so the parent container's horizontal padding is preserved (spec/mock bug fix); add bottom padding (~`pb-20`) to reserve space for the HUD, dropping to normal under 640px. Stack to a column under `md`.

- [ ] **Step 3: Verify**

Run: `pnpm check`
Expected: passes (components compile, no a11y errors on icon links).

- [ ] **Step 4: Commit**

```bash
git add "src/maps/src/lib/components/landing/SiteHeader.svelte" "src/maps/src/lib/components/landing/SiteFooter.svelte"
git commit -m "feat(map): add SiteHeader and SiteFooter chrome"
```

---

## Task 7: Wire shared chrome into the (app) layout

**Files:**
- Modify: `src/maps/src/routes/(app)/+layout.svelte`

- [ ] **Step 1: Replace the tab bar**

Replace the current tab-navigation markup with `<SiteHeader />`, keep `<slot />` for page content, and add `<SiteFooter />` after it. Set the outer wrapper background to `bg-bg` (token). Keep the `import '../../app.css'` line.

```svelte
<script lang="ts">
    import '../../app.css';
    import SiteHeader from '$lib/components/landing/SiteHeader.svelte';
    import SiteFooter from '$lib/components/landing/SiteFooter.svelte';
</script>

<div class="bg-bg min-h-screen">
    <SiteHeader />
    <slot />
    <SiteFooter />
</div>
```

(Note: this changes chrome for all `(app)` pages — intended per spec §11. Inner page bodies keep their own styling for now.)

- [ ] **Step 2: Verify all (app) routes still render**

Run: `pnpm dev`, visit `/`, `/zone-maps`, `/mod`, `/adventure-guide`, `/spreadsheet` — header/footer present, no layout crash. Stop dev server.

- [ ] **Step 3: Commit**

```bash
git add "src/maps/src/routes/(app)/+layout.svelte"
git commit -m "feat(map): replace tab bar with shared header/footer chrome"
```

---

## Task 8: Hero + CompassRuler

**Files:**
- Create: `src/maps/src/lib/components/landing/CompassRuler.svelte`
- Create: `src/maps/src/lib/components/landing/Hero.svelte`

- [ ] **Step 1: CompassRuler**

Port the `.ruler` block from the mock (symmetric two-half tick line with a 60px center gap; `W` / `E` ends; `N` with the CSS north-arrow `::before`). Bespoke gradients live in a scoped `<style>` block; expose nothing (`aria-hidden`).

- [ ] **Step 2: Hero**

Port the `.hero` block: full-bleed section (`border-b border-line`), faint contour `::before` (scoped style), inner container, mono `kicker`, H1 "Chart the world of Erenshor.", `.hero-row` (lede left, CTA group right), CTAs (`primary` filled accent, `secondary` filled surface-2, both identical size; text link "New to Erenshor?"), then `<CompassRuler />`. Primary CTA → `/map`; secondary → `#tools`; text link → `#about`. Use token utilities; keep the contour/`::before` in scoped style.

- [ ] **Step 3: Verify**

Run: `pnpm check`
Expected: passes.

- [ ] **Step 4: Commit**

```bash
git add "src/maps/src/lib/components/landing/CompassRuler.svelte" "src/maps/src/lib/components/landing/Hero.svelte"
git commit -m "feat(map): add landing hero and compass ruler"
```

---

## Task 9: Tools section

**Files:**
- Create: `src/maps/src/lib/components/landing/ToolsSection.svelte`

- [ ] **Step 1: Build the section**

Port the `#tools` block: section head (`CoordTag` + H2 "Tools & resources", accent underline; **no** "5 things to explore"); a flagship `<a class="featured">` (image `/world-map-preview.webp`, eyebrow `EVERY ZONE · ONE MAP`, H3 "Interactive World Map", copy, "Open the map →") → `/map`; then a 4-up grid of tiles. Tile data array:

```ts
const tiles = [
    { href: '/adventure-guide', img: '/adventure-guide-window.webp', title: 'Adventure Guide',
      desc: 'In-game quest companion. 170+ quests with walkthroughs, world markers, and navigation.' },
    { href: '/mod', img: '/world-map-companion.gif', title: 'Companion Mods',
      desc: 'Live tracking on the maps. See your character, SimPlayers, NPCs, and enemies move in real time.' },
    { href: '/spreadsheet', img: '/spreadsheet.png', title: 'Reference Spreadsheet',
      desc: 'Searchable items, drop chances, characters, classes, spells, skills, ascensions, and more.' },
    { href: '/zone-maps', img: '/maps/Braxonia.jpg', title: 'Zone Maps', tag: 'Legacy',
      desc: 'Per-zone maps with spawn, NPC, and connection markers. Superseded by the world map.' }
];
```

Calm hover (border + surface change, no transform). Images use `loading="lazy"` and real `width`/`height` where known. Use the repo's `eslint-disable svelte/no-navigation-without-resolve` pattern for the internal links.

- [ ] **Step 2: Verify**

Run: `pnpm check`
Expected: passes.

- [ ] **Step 3: Commit**

```bash
git add "src/maps/src/lib/components/landing/ToolsSection.svelte"
git commit -m "feat(map): add tools & resources section"
```

---

## Task 10: CoordTag, SectionDivider, About section

**Files:**
- Create: `src/maps/src/lib/components/landing/CoordTag.svelte`
- Create: `src/maps/src/lib/components/landing/SectionDivider.svelte`
- Create: `src/maps/src/lib/components/landing/AboutSection.svelte`

- [ ] **Step 1: CoordTag**

A mono `<span class="coord-tag">` with placeholder `X 0 · Y 0` (real value set at runtime in Task 12). Port `.coord-tag` styling. Accepts no props; the interaction module finds it by class.

- [ ] **Step 2: SectionDivider**

Port `.divider` (fading hairline `::before`/`::after` + centered diamond `<span>`), `aria-hidden`.

- [ ] **Step 3: AboutSection**

Props: `stats: { zones; classes; items; quests }`. Two columns over the faded contour watermark (`#about::before`, scoped style with the layered-gradient vignette — **not** `mask-image`). Each column: `<CoordTag />` + H2 + two paragraphs. Copy from the mock, with the stats sentence built from props:

```svelte
<p>Developed by Burgee Media, it spans {fmtZones} zones, {fmtClasses} classes,
   over {fmtItems} items, and hundreds of quests and NPCs to discover.</p>
```

where `fmtZones = roundDown(stats.zones)` etc. Define a small `roundDown(n) => Math.floor(n/10)*10 + '+'` for zones/items, spell out classes (`numberToWord(stats.classes)` for ≤12, else the digits). Keep "About Erenshor" and "About Erenshor Maps" copy verbatim from the mock (semicolon-free, no "non-commercial"). First column links "Erenshor" → `https://erenshor.com/`.

- [ ] **Step 4: Verify**

Run: `pnpm check`
Expected: passes.

- [ ] **Step 5: Commit**

```bash
git add "src/maps/src/lib/components/landing/CoordTag.svelte" "src/maps/src/lib/components/landing/SectionDivider.svelte" "src/maps/src/lib/components/landing/AboutSection.svelte"
git commit -m "feat(map): add about section with DB-derived stats"
```

---

## Task 11: Community section

**Files:**
- Create: `src/maps/src/lib/components/landing/CommunitySection.svelte`

- [ ] **Step 1: Build grouped link lists**

Port `#community`: section head (`CoordTag` + H2 "The game & the wider community") and two groups. Data arrays (icons from `icons.line`, exact labels/descriptions/URLs from spec §9 — **Thunderstore omitted**):

```ts
const official = [
    { icon: 'steam', href: 'https://store.steampowered.com/app/2382520/Erenshor/', title: 'Erenshor on Steam', desc: 'Buy the game on Steam.' },
    { icon: 'globe', href: 'https://erenshor.com/', title: 'Official Website', desc: 'erenshor.com, by Burgee Media.' },
    { icon: 'discord', href: 'https://discord.gg/erenshor', title: 'Official Discord', desc: 'News, help, and the community.' },
    { icon: 'wiki', href: 'https://erenshor.wiki.gg/', title: 'Official Wiki', desc: 'erenshor.wiki.gg, the full game reference.' }
];
const community = [
    { icon: 'vault', href: 'https://erenshorvault.app/', title: 'Erenshor Vault', desc: 'Community tools, guides & the mod registry.' },
    { icon: 'lunaris', href: 'https://github.com/MizukiBelhi/Lunaris', title: 'Lunaris Mod Loader', desc: 'Install & update mods while the game runs.' },
    { icon: 'guide', href: 'https://steamcommunity.com/sharedfiles/filedetails/?id=3500398991', title: 'Steam Guide', desc: 'The maps & spreadsheet, on Steam.' },
    { icon: 'kofi', href: 'https://ko-fi.com/wowmuch', title: 'Support on Ko-fi', desc: 'Optional thanks if the tools helped, never required.' }
];
```

Divided list rows, line icons in tinted squares, hover surface change, **no rotated arrows**. External links get `target="_blank" rel="noopener"`.

- [ ] **Step 2: Verify**

Run: `pnpm check`
Expected: passes.

- [ ] **Step 3: Commit**

```bash
git add "src/maps/src/lib/components/landing/CommunitySection.svelte"
git commit -m "feat(map): add community & links section"
```

---

## Task 12: Interactive coordinate layer

**Files:**
- Create: `src/maps/src/lib/components/landing/CoordHud.svelte`
- Create: `src/maps/src/lib/components/landing/coordinates.ts`

- [ ] **Step 1: CoordHud**

Fixed bottom-right panel: crosshair icon (`icons.line.crosshair`) + `<span class="hud-xy">`. Port `.coord-hud` styles (hidden until `.on`; `pointer-events:none`; hidden on `pointer:coarse` and `max-width:640px`; reduced-motion safe). Scoped `<style>` for the bespoke bits.

- [ ] **Step 2: Interaction module**

`coordinates.ts` exports `initCoordinates(): () => void` (returns cleanup) — port the mock's `<script>` logic to a module:

```ts
export function initCoordinates(): () => void {
    const hud = document.querySelector<HTMLElement>('.coord-hud');
    const hudXY = document.querySelector<HTMLElement>('.hud-xy');
    const tags = [...document.querySelectorAll<HTMLElement>('.coord-tag')];
    if (!hud || !hudXY) return () => {};
    const placeTags = () => {
        for (const t of tags) {
            const r = t.getBoundingClientRect();
            t.innerHTML = `<b>X</b> ${Math.round(r.left + scrollX)} · <b>Y</b> ${Math.round(r.top + scrollY)}`;
        }
    };
    let cx: number | null = null, cy: number | null = null;
    const update = () => {
        if (cx === null || cy === null) return;
        hudXY.innerHTML = `<b>X</b> ${Math.round(cx + scrollX)} · <b>Y</b> ${Math.round(cy + scrollY)}`;
    };
    const onMove = (e: PointerEvent) => { cx = e.clientX; cy = e.clientY; hud.classList.add('on'); update(); };
    const onResize = () => { placeTags(); update(); };
    placeTags();
    addEventListener('pointermove', onMove, { passive: true });
    addEventListener('scroll', update, { passive: true });
    addEventListener('resize', onResize, { passive: true });
    return () => {
        removeEventListener('pointermove', onMove);
        removeEventListener('scroll', update);
        removeEventListener('resize', onResize);
    };
}
```

Coordinate tags' `<b>` accent styling: add `.coord-tag b { color: var(--color-accent); }` (and `.hud-xy b`) in scoped styles or the component.

- [ ] **Step 3: Commit**

```bash
git add "src/maps/src/lib/components/landing/CoordHud.svelte" "src/maps/src/lib/components/landing/coordinates.ts"
git commit -m "feat(map): add interactive coordinate HUD and survey tags"
```

---

## Task 13: Compose the landing page

**Files:**
- Modify: `src/maps/src/routes/(app)/+page.svelte`

- [ ] **Step 1: Assemble**

Replace the file with the SEO block + composed sections:

```svelte
<script lang="ts">
    import { onMount } from 'svelte';
    import type { PageData } from './$types';
    import Seo from '$lib/components/Seo.svelte';
    import { websiteJsonLd, webApplicationJsonLd, videoGameJsonLd } from '$lib/seo/jsonld';
    import Hero from '$lib/components/landing/Hero.svelte';
    import ToolsSection from '$lib/components/landing/ToolsSection.svelte';
    import SectionDivider from '$lib/components/landing/SectionDivider.svelte';
    import AboutSection from '$lib/components/landing/AboutSection.svelte';
    import CommunitySection from '$lib/components/landing/CommunitySection.svelte';
    import CoordHud from '$lib/components/landing/CoordHud.svelte';
    import { initCoordinates } from '$lib/components/landing/coordinates';

    let { data }: { data: PageData } = $props();
    onMount(() => initCoordinates());
</script>

<Seo
    path="/"
    title="Erenshor Maps – Interactive Maps, Data & Mods"
    description="Interactive maps, reference data, and companion mods for Erenshor, the single-player simulated MMORPG."
    jsonLd={[websiteJsonLd(), webApplicationJsonLd(), videoGameJsonLd()]}
/>

<Hero />
<main class="mx-auto max-w-[1140px] px-7">
    <ToolsSection />
    <SectionDivider />
    <AboutSection stats={data.stats} />
    <SectionDivider />
    <CommunitySection />
</main>
<CoordHud />
```

(Match the mock's container width/padding; Hero is full-bleed so it sits outside `main`.)

- [ ] **Step 2: Run the dev server and smoke-test**

Run: `pnpm dev`; open `/`. Verify: hero, flagship + 4 tiles, About with real stats, community links, footer, HUD appears on mouse move and updates on scroll, coord tags show real `X·Y`. No console errors, no broken images.

- [ ] **Step 3: Commit**

```bash
git add "src/maps/src/routes/(app)/+page.svelte"
git commit -m "feat(map): compose Erenshor Maps landing page"
```

---

## Task 14: Responsive + a11y pass

**Files:** (adjust components as needed)

- [ ] **Step 1: Breakpoints**

With dev server running, check 1280 / 880 / 375 widths: header collapses to mobile menu (button toggles link panel; icons stay), featured tile stacks, prose/links single-column, footer stacks, HUD hidden ≤640. Fix any overflow (test the H1 copy at 375 — reduce clamp max if it overflows).

- [ ] **Step 2: a11y**

Verify: one `<h1>`; icon-only links have `aria-label`; decorative flourishes `aria-hidden`; keyboard-tab through header → menu → CTAs → links; `prefers-reduced-motion` disables non-essential transitions. Contrast spot-check `--muted` on `--bg` (≥4.5:1).

- [ ] **Step 3: Commit any fixes**

```bash
git add -A -- src/maps/src/lib/components/landing src/maps/src/routes/'(app)'
git commit -m "fix(map): responsive and a11y refinements for landing"
```

---

## Task 15: Verification & gates

- [ ] **Step 1: Visual parity vs mock**

With `pnpm dev` running, write a throwaway Playwright script (per the interactive-map skill pattern; **do not commit**) that loads `/`, screenshots at 1280/880/375, and lists any `img` with `naturalWidth===0`. Compare screenshots to `docs/mockups/landing/index.html`. Delete the script after.

- [ ] **Step 2: Interactivity check**

In the same script: dispatch `pointermove`, assert `.hud-xy` text updates; `window.scrollTo(0, 400)` then assert it changed by the scroll delta; assert all 8 community `href`s and 5 nav targets are present and correct.

- [ ] **Step 3: Run gates**

```bash
pnpm check        # svelte-check: 0 errors
pnpm lint         # eslint: clean
pnpm test         # vitest: world-stats passes
pnpm build        # prerender succeeds; stats query runs at build
```

Expected: all green. Fix any failures (including pre-existing ones touched).

- [ ] **Step 4: Final commit (if fixes)**

```bash
git add -A -- src/maps
git commit -m "test(map): verify landing redesign; fix gate failures"
```

- [ ] **Step 5: Update plan status**

Set this plan's front-matter `status: implemented` and the design spec's `status: implemented` in the same commit as the last change.

---

## Self-review notes

- **Spec coverage:** tokens (T1), fonts (T1), rename+SEO+Discord (T2), DB stats (T3–T4, §8), chrome/header/footer/mobile menu (T6–T7, §11), hero+ruler (T8), tools (T9), about+watermark+coord tags (T10), community links (T11), interactive HUD+scroll (T12), composition+JSON-LD (T13), responsive/a11y (T14), verification (T15). All spec sections mapped.
- **Out of scope (confirmed):** inner page bodies, `/map` UI, WoWBot, Thunderstore.
- **Watch-outs:** use the layered-gradient vignette for the watermark (not `mask-image` — it stalls headless raster); footer uses vertical-only padding so container side padding survives; coord tags are populated at runtime, so prerendered HTML ships the `X 0 · Y 0` placeholder (acceptable — JS fills real values on mount).

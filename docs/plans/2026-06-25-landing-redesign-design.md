---
title: Landing Page Redesign (Erenshor Maps)
type: spec
status: implemented
created: 2026-06-25
parent: 2026-06-19-website-redesign
---

# Landing Page Redesign — Design Spec

**Surface:** `src/maps/` (SvelteKit, prerendered, Tailwind v4)
**Visual source of truth:** `docs/mockups/landing/index.html` (throwaway HTML mock, iterated and signed off in-browser)

---

## 0. Relationship to prior work

This **supersedes** `2026-06-19-website-redesign.md` (a broader, draft "whole
non-map site" redesign), which is now retired to `docs/plans/archive/`. The
decisions made in the 2026-06-25 design session are authoritative. Deferred
inner-page work (mod catalog, `/spreadsheet`, `/zone-maps`, a possible WoWBot
page) will be **planned fresh under the new Erenshor Maps identity** when tackled —
the old doc's specifics for those pages are stale and should not be followed as-is.

Where this spec diverges from the retired draft (all decided this session):

- **Brand:** "Erenshor Maps" (not "Erenshor Community Tools").
- **Register:** brand-leaning identity (committed accent, cartographic flourishes), vs. the old doc's strict product/tool register.
- **Thunderstore:** removed from links (community moved to Lunaris); the old doc treated Thunderstore as a primary install channel.
- **Primary nav:** World Map · Zone Maps · Adventure Guide · Mods · Spreadsheet + social icons (as designed and reviewed this session). The old doc's leaner Home · World Map · Mods · Data · WoWBot proposal is not adopted.
- **WoWBot / `/wiki-bot` page:** proposed only in the old doc; out of scope here.

## 1. Goal

Replace the current anemic landing page — a single hero image linking to the world map — with a proper home page that:

- Surfaces every tool the site offers (world map, zone maps, adventure guide, companion mods, spreadsheet) with previews and plain-language explanations, instead of forcing discovery through the top tab bar.
- Cross-links the official game and the wider community (Steam, site, Discord, wiki, Erenshor Vault, Lunaris, Steam guide, Ko-fi).
- Adds prose describing the game and the site for newcomers and for SEO.
- Establishes a real, distinctive visual identity (replacing the copy-pasted purple→pink gradient) and a reusable design-token system the rest of the site can adopt later.

Success = a coherent, fast, accessible home page that ranks better, orients new visitors, and reads as "made with care," not "AI-generated."

## 2. Identity & direction

- **Brand / positioning:** lean into **"Erenshor Maps"** (the recognizable name; the maps are the flagship), not "Erenshor Community Tools." Wordmark: `Erenshor` in ink + `Maps` in accent.
- **Register:** impeccable **brand** register (the landing page *is* the product impression).
- **Direction:** **Modern Dark** — a readable dark theme with one committed warm-gold accent and subtle cartographic cues (compass ruler, contour watermark, coordinate motifs). Chosen over the bolder "Cartographer's Atlas" serif variant for legibility, while keeping enough cartographic character to stay distinctive.
- **Concept hook:** the site is an explorer's instrument for charting Erenshor. The cursor is a position on the map; survey markers carry real page coordinates.

## 3. Design tokens

Author as CSS custom properties via Tailwind v4 `@theme` in `src/maps/src/app.css` (today it only does `@import 'tailwindcss'` + a body bg). Values below are the in-browser-validated hex from the mock; convert to OKLCH during implementation if desired, preserving the same rendered result. Contrast verified (e.g. `--muted` `#94a6b8` on `--bg` ≈ 7.5:1, well above the 4.5:1 body-text floor).

| Token | Value | Role |
|---|---|---|
| `--bg` | `#0a0e14` | page background (also `<meta name="theme-color">`, replacing `#0d1b2a`) |
| `--surface` | `#111922` | cards, tiles, list rows |
| `--surface-2` | `#18222e` | secondary button, hover surface |
| `--ink` | `#e8eff6` | headings, primary text |
| `--muted` | `#94a6b8` | body/secondary text, labels (passes contrast) |
| `--line` | `#1f2c39` | borders, dividers, ticks |
| `--accent` | `#e2b15a` | warm gold — single committed accent |
| `--accent-ink` | `#0a0e14` | text on accent (primary button) |
| `--accent-2` | `#5ab0c8` | reserved cool counter-accent (sparing) |
| radius | `12px` | default corner radius |

Color strategy: **Restrained→Committed** — tinted-neutral dark surfaces + one saturated accent carrying CTAs, links, and cartographic marks.

## 4. Typography

- **Display + body:** Hanken Grotesk (weights 400/500/600/700/800). One family, committed weight contrast (headings 800, body 400).
- **Mono (labels, coordinates, kickers):** JetBrains Mono.
- Neither font is on impeccable's reflex-reject lists (Inter/DM/Space Grotesk banned; Hanken Grotesk and JetBrains Mono are clear).
- **Self-host** via `@fontsource/hanken-grotesk` and `@fontsource/jetbrains-mono` (no Google Fonts CDN — better perf/privacy on the Cloudflare-hosted prerendered site). Import in the root layout; subset to latin.
- Headings: `text-wrap: balance`, fluid `clamp()`, tight tracking (`-.015em` on the H1). Body line-length capped ~50–62ch.

## 5. Information architecture

Single landing route (`(app)/+page.svelte`), full-width sections within a `max-width:1140px` container:

1. **Header** — wordmark left; nav links (World Map, Zone Maps, Adventure Guide, Mods, Spreadsheet) + Steam/Discord/Ko-fi brand icons right.
2. **Hero** — full-width editorial masthead, no image: mono kicker, H1 "Chart the world of Erenshor.", lede + CTA row (primary "Open the world map", secondary "Browse all tools", text link "New to Erenshor?"), and a compass ruler (`W · ▲N · E`) as the closing flourish.
3. **Tools & resources** — flagship **Interactive World Map** tile (large, image + copy, eyebrow `EVERY ZONE · ONE MAP`) followed by a 4-up grid: Adventure Guide, Companion Mods, Reference Spreadsheet, Zone Maps (`Legacy` tag).
4. **About** — two balanced, semicolon-free columns: *About Erenshor* and *About Erenshor Maps*, over a faded contour watermark.
5. **The game & the wider community** — two grouped, divided link lists: *Official Erenshor* (Steam, Website, Discord, Wiki) and *Community & support* (Erenshor Vault, Lunaris Mod Loader, Steam Guide, Support on Ko-fi).
6. **Footer** — fan-project disclaimer + quick links (erenshor.com · wiki · discord).

Understated cartographic flourishes between/around sections: compass ruler (hero), fading hairline dividers with a center diamond (between sections), contour watermark (About), and `X · Y` coordinate tags on each section heading (real values — see §7).

## 6. Component breakdown

Each unit is small, single-purpose, and independently testable. Likely Svelte components under `src/maps/src/lib/components/landing/` (or inline in `+page.svelte` where trivial):

- `SiteHeader` — wordmark, nav, social icon cluster. Shared chrome (see §11).
- `Hero` — kicker, H1, lede, CTAs, `CompassRuler`.
- `CompassRuler` — symmetric tick line split into two mirrored halves with a 60px center gap; `▲N` north marker in accent, `W`/`E` ends.
- `ToolCardFeatured` — flagship world-map tile (image + copy + go link).
- `ToolCard` — image-top card (thumb, title, optional `Legacy` tag, one-line description). Calm hover: border + surface change, no transform.
- `AboutColumns` — two prose blocks + contour watermark; stats injected from `+page.server.ts` (see §8).
- `LinkList` — grouped divided lists with line icons; one `LinkRow` per entry.
- `CoordHud` + `coordinates` action — interactive layer (see §7).
- `SectionDivider`, `CoordTag` — flourishes.

## 7. Interactive coordinate layer

A delight that reinforces the cartographic identity. Cursor = position on the page; section headings = real survey markers.

- **HUD** (`CoordHud`): fixed bottom-right panel, crosshair glyph + live `X · Y`. Shows **page coordinates** (`clientX/Y + scrollX/Y`).
- **Survey tags** (`CoordTag` on each heading): on mount/resize compute each tag's real page position (`getBoundingClientRect().left/top + scroll`) and render it. They share the HUD's coordinate space, so the HUD reading matches a tag as the cursor passes it.
- **Scroll updates:** track the last cursor viewport position; recompute on `scroll` and `resize` (not just `pointermove`) so a stationary cursor stays accurate while scrolling. Verified: cursor `X900·Y420`, scroll +148 → `X900·Y568`.
- **Behavior:** HUD fades in on first pointer move; `pointer-events:none` (never blocks clicks); hidden on touch (`pointer:coarse`) and under 640px; footer reserves bottom padding so the HUD never overlaps footer content.
- **Removed:** proximity-highlight (tags lighting up near the cursor) — cut per review as noise.
- **A11y/perf:** decorative (`aria-hidden`), all listeners `passive`, reduced-motion safe (only opacity transition). In Svelte: a small `use:` action + `onMount` listeners; tags via `bind:this` recomputed on mount/resize.

## 8. DB-derived world stats

The About copy cites world stats. **The Steam page is stale (it says 4 classes; the DB has 7).** Compute these at prerender time from the clean DB (`src/maps/static/db/erenshor.sqlite`) in `(app)/+page.server.ts` (`prerender = true`, so it runs at build) and inject into the page, so they never drift again.

Counts (current main DB): `zones` 43, `classes` 7, `items` 1348, `quests` 176, `characters` 1111. Present as stable, lightly-rounded figures (e.g. "40+ zones, seven classes, over 1,000 items, hundreds of quests and NPCs"), derived from `COUNT(*)` so updates flow automatically. (Rounding/labels are a copy choice; the source is the DB.)

## 9. Content & copy

Final, fact-checked copy lives in the mock. Key rules applied: no personal name/handle in visible text; honest framing (no "everything in one place," no false roadmap claim, Ko-fi optional/never-required, Steam guide described as "the maps & spreadsheet, on Steam"); no em-dashes or semicolons in card/about copy; balanced About columns.

**External links:**

| Group | Label | URL |
|---|---|---|
| Official | Erenshor on Steam | `https://store.steampowered.com/app/2382520/Erenshor/` |
| Official | Official Website | `https://erenshor.com/` |
| Official | Official Discord | `https://discord.gg/erenshor` |
| Official | Official Wiki | `https://erenshor.wiki.gg/` |
| Community | Erenshor Vault | `https://erenshorvault.app/` |
| Community | Lunaris Mod Loader | `https://github.com/MizukiBelhi/Lunaris` |
| Community | Steam Guide | `https://steamcommunity.com/sharedfiles/filedetails/?id=3500398991` |
| Community | Support on Ko-fi | `https://ko-fi.com/wowmuch` |

Header social icons: Steam, Discord, Ko-fi (brand glyphs). Thunderstore is intentionally **omitted** (community has moved to Lunaris).

## 10. SEO, JSON-LD & the "Erenshor Maps" rename

- `src/maps/src/lib/seo/site.ts`: `SITE_NAME` → "Erenshor Maps"; refresh `DEFAULT_TITLE`/`DEFAULT_DESCRIPTION` toward the Maps positioning while keeping keywords (interactive maps, spawn points, companion mods, spreadsheet, simulated MMORPG). The handle must not appear in any **visible** landing copy (already handled in the mock); the non-visible `<meta name="author">` (`SITE_AUTHOR`) may remain.
- Landing `<Seo>` keeps `websiteJsonLd` / `webApplicationJsonLd` / `videoGameJsonLd`; verify `name`/`url` reflect the rename.
- The richer prose + section headings improve on-page SEO; keep one `<h1>`, semantic `<section>`/`<h2>` structure.
- `app.html`: `theme-color` `#0d1b2a` → `#0a0e14`.
- Standardize the Discord invite repo-wide: replace the stale `https://discord.gg/fTvgzKy5` in `SearchNotFoundContent.svelte` with `https://discord.gg/erenshor`.

## 11. Shared chrome & scope

**Scope (approved):** landing page **+ shared chrome (nav/header/footer) + the design-token system**. Inner page *bodies* (`/map`, `/zone-maps`, `/mod`, `/adventure-guide`, `/spreadsheet`) keep their current look for now and migrate to the tokens in a later pass.

- The current tab-bar nav in `(app)/+layout.svelte` (purple→pink) is replaced by the new `SiteHeader`. Because it's shared, all inner pages immediately get the new header/footer/tokens; their internal bodies remain styled as-is until migrated.
- **Mobile nav:** the desktop text links collapse under 880px. Add a real mobile menu (hamburger → dropdown/sheet) rather than hiding navigation; the social icon cluster stays visible. (The mock hides text links and keeps icons as a placeholder; the implementation must add the menu.)

## 12. Responsive & accessibility

- Breakpoints: ~880px (nav → mobile menu, featured tile stacks, prose/links single-column, footer stacks), ~640px (HUD hidden, footer bottom padding reduced).
- Cards: `repeat(auto-fit, minmax(240px, 1fr))`.
- Contrast: all text ≥ 4.5:1 (large ≥ 3:1); verified for `--muted` on `--bg`.
- Motion: subtle, transform/opacity only; every transition reduced-motion safe. Flourishes are decorative and `aria-hidden`.
- Semantic landmarks: `<header>`, `<main>`, `<section>` with headings, `<footer>`; links have discernible names (icon-only links get `aria-label`/`title`).

## 13. Files touched (implementation map)

- `src/maps/src/app.css` — `@theme` tokens.
- `src/maps/src/routes/(app)/+layout.svelte` — replace tab nav with `SiteHeader` + footer; apply tokens.
- `src/maps/src/routes/(app)/+page.svelte` — new landing composition.
- `src/maps/src/routes/(app)/+page.server.ts` — **new**: DB stat counts (prerender).
- `src/maps/src/lib/components/landing/*` — new components (§6).
- `src/maps/src/lib/seo/site.ts`, `jsonld.ts` — rename + metadata.
- `src/maps/src/app.html` — `theme-color`.
- `src/maps/src/lib/.../SearchNotFoundContent.svelte` — Discord invite.
- `package.json` — `@fontsource/*` deps; root layout font imports.

## 14. Non-goals

- No redesign of the interactive map app itself (`/map` deck.gl UI) or the inner page bodies (deferred migration).
- No CMS/data-entry; copy is in-component, stats are DB-derived.
- No new backend; everything stays prerendered + static on Cloudflare.

## 15. Risks & open questions

- **Primary nav (decided):** World Map · Zone Maps · Adventure Guide · Mods · Spreadsheet + Steam/Discord/Ko-fi icons, as designed and reviewed this session. The old doc's leaner alternative is explicitly not adopted.
- **Fonts add weight** — mitigate by self-hosting + latin subset + `font-display:swap`.
- **DB-stat rounding** — confirm preferred phrasing (exact "43 zones" vs rounded "40+ zones") at implementation; source is the DB either way.
- **Mobile menu pattern** — dropdown vs slide-over sheet (project already depends on `vaul-svelte`; a sheet is available). Decide in the plan.
- **Inner-page visual clash** — until inner bodies migrate, they show the new chrome over old-styled bodies; acceptable interim, tracked as follow-up.

## 16. Verification

- Visual: re-create the approved mock in SvelteKit; screenshot key breakpoints (≥1280, 880, 375) and compare to the mock.
- Interactivity: HUD updates on move **and** scroll; tags carry real coords; HUD hidden on touch/≤640; no footer overlap.
- Stats: assert the rendered figures equal `COUNT(*)` from the clean DB at build.
- A11y: contrast check; keyboard nav through header/menu/links; reduced-motion.
- Gates: `pnpm --filter maps check` (svelte-check), `lint`, build; `uv run erenshor golden capture` only if data outputs change (not expected for a UI-only change).

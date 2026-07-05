---
title: Crawlable Zone Content Layer (/zones)
type: spec
status: draft
created: 2026-07-04
parent: 2026-06-26-maps-domain-url-migration
---

# Crawlable Zone Content Layer (/zones)

**Goal:** Give the interactive maps a crawlable, human-readable companion layer
so the site can rank for its highest-value terms ("erenshor map", "erenshor
zones", per-zone "[zone] map") without touching the interactive-map UX. Today
the money pages (`/map`, the zone maps) are WebGL/Leaflet canvases whose only
indexable text is a single `sr-only` H1 — Google has nothing to assess for
depth or relevance, so `/map` plateaus around position 6–7 for the 452-impression
term "erenshor map". This layer supplies real HTML content that describes *what
each map contains* and links out to the wiki for detail.

**Architecture:** Progressive enhancement / HTML-first. The canvas apps stay
exactly as they are; crawlable content lives in prerendered DOM on companion
routes and in a below-the-fold section of `/map`. All content is generated at
prerender time from the clean SQLite DB (the same source the markers already
read) — no new backend, no CMS, no per-entity pages. Every entity row links to
its authoritative wiki page and deep-links into the interactive map; we describe
spatial presence ("where"), the wiki owns stats and lore ("what"). This realizes
the `2026-06-26-maps-domain-url-migration` backlog item "Crawlable textual
content layer at `/zones/{slug}`".

**Tech Stack:** SvelteKit (Svelte 5, `prerender = true`, `adapter-static`/
Cloudflare), `sql.js` via `$lib/database.node`, existing `Seo.svelte` + JSON-LD
helpers, Tailwind v4 `@theme` tokens. Visual source of truth:
`docs/mockups/zones/index.html`.

---

## Rationale (why content, not meta)

Verified against current guidance (2025–26): content quality is Google's #1
ranking factor (Helpful Content, now continuous/sitewide); meta descriptions are
*not* a ranking signal (CTR only); title tags matter but are secondary. Moving a
page-1 term up is driven by content coverage, intent match, internal linking, and
topical authority — not tag edits. For a JS-canvas app the prerequisite is
crawlable DOM: render real content server-side and let the canvas enhance on top
(HTML-first progressive enhancement). The site's meta/JSON-LD scaffold is already
solid from prior SEO passes; the remaining ceiling is missing body content, which
is exactly what this layer adds.

## Surfaces

### 1. `/zones/{slug}` — per-zone reference page (primary)

One prerendered page per zone (43 zones). Sections, in order:

- **Header** — zone name (`<h1>`), a mono meta tag (`ZONE · LV {min}–{max} · {n}
  exits`), and a one-line summary generated from counts ("Interactive Braxonian
  Desert map for Erenshor: 14 enemy spawns across levels 4–30, 14 NPCs and
  vendors, 29 mineral deposits, and 7 treasure sites.").
- **Open in interactive map →** primary link to `/maps/{slug}` (the canvas app).
- **On this map** — legend of marker types actually present in this zone.
- **Enemies ({n})** — scannable table: name · level · rarity (common/rare/unique)
  · `→ wiki`. Sorted by level; uniques visually emphasized. Rare/unique names
  deep-link into `/map?sel=enemy:{name}`.
- **NPCs & vendors ({n})** — list; vendors flagged; each `→ wiki`.
- **Resources** — inline counts with icons: mining nodes (by material), fishing
  waters, wishing wells, teleports, treasure sites.
- **Connects to** — outbound zone lines (`DisplayText` → destination zone),
  each linking the destination `/zones/{slug}`. Builds the internal-link cluster.
- **Wiki callout** — "Full stats, drops, and lore live on the Erenshor Wiki →".
- **Footer** — provenance line (see Freshness).

### 2. `/zones` — zone index

A single prerendered directory of all 43 zones (deduplicated display names),
grouped overworld vs. dungeon, each linking `/zones/{slug}`. Serves the "erenshor
zones" query (48 impressions, position 9.2, 0 clicks today) and hubs the cluster.

### 3. `/map` — below-the-fold content section

The deck.gl map stays full-bleed at 100vh, untouched. Below it, a prerendered
section: a short intro with site-wide aggregates (43 zones, 3,685 spawn points,
717 NPCs, 102 mining nodes, 55 treasure sites), the marker legend, a "Browse by
zone" directory of real `<a href>` links to every `/zones/{slug}`, and the wiki
cross-link. Users who came for the map never scroll; crawlers and readers get
substance. This is prerendered DOM, not a `<noscript>` block — Google renders JS,
so real DOM content is the durable mechanism; a `<noscript>` mirror is an optional
accessibility floor, not the primary lever.

## Data sources

All from the clean DB (`erenshor-{variant}.sqlite`, PascalCase schema). Per-zone
queries key on `Scene` = `Zones.SceneName`:

- **Enemies:** `SpawnPoints` (`IsEnabled=1`) ⋈ `SpawnPointCharacters`
  (`SpawnChance>0`) ⋈ `Characters` (`IsFriendly=0`), distinct by
  `CharacterStableKey`. Rarity from `Characters.IsUnique/IsRare` (else common);
  level from `Characters.Level`.
- **NPCs & vendors:** same join with `IsFriendly=1`; `IsVendor` flags vendors.
- **Mining nodes:** `MiningNodes` grouped by `NPCName` (material).
- **Resources:** `Waters`, `WishingWells`, `Teleports`, `TreasureLocations` by `Scene`.
- **Connections:** `ZoneLines` (`IsEnabled=1`), `DestinationZoneStableKey` →
  `Zones.StableKey` → `ZoneName`.
- **Level range:** min/max `Characters.Level` over enemy spawns in the zone.

Reuse the existing `+page.server.ts` world-map loader shape where practical; the
marker query already computes most of this per zone.

## Wiki cross-linking ("complement, don't replicate")

Locked decision from the migration plan. This layer never restates wiki stats —
it links to them. Two directions:

- **Out:** every enemy/NPC/vendor row links to its wiki page (character name →
  wiki title; resolve via the existing name/registry mapping used by the wiki
  build). Zone pages link to the zone's wiki page.
- **In (highest-value backlink):** the migration plan's task to repoint the
  wiki's map-link template should also point zone/enemy pages at the matching
  `/zones/{slug}`, so the wiki's traffic flows into the cluster.

## Freshness / provenance

Surface a truthful data-provenance line, not a synthetic "updated today":

- Display: *"Map data synced to Erenshor build `{buildid}` · {export month/year}"*,
  with `{buildid}` linking to SteamDB app history
  (`https://steamdb.info/app/2382520/patchnotes/`).
- Erenshor publishes only coarse versions (0.7 + unnumbered patches); the **Steam
  build ID** (e.g. `20370413`, read from `appmanifest_2382520.acf` by
  `_read_build_id` in `extract.py`, stored in `export_profile`) is the precise,
  verifiable identifier.
- Wiring gap: `.build-info.json` (maps build sidecar) only hashes inputs; it does
  not carry the build ID. Thread `game_build_id` + export date from
  `export_profile` into the clean DB (a small provenance row/table) → maps data →
  footer. An honest older date is fine for a reference tool; never auto-bump a
  date without a data change.

## SEO specifics

- **Titles:** `{Zone} Map – Enemies, NPCs & Resources | Erenshor` per zone;
  `Erenshor Zones – All 43 Zone Maps` for the index. `/map` title unchanged.
- **Headings:** real `<h1>` per zone (replacing the `sr-only` pattern where the
  page is content-first); `<h2>` per section.
- **Internal links:** zone↔zone via connections, index→zones, `/map`→zones,
  zones→`/maps/{slug}`. All real `<a href>`.
- **JSON-LD:** reuse `breadcrumbJsonLd`; add a modest `Place`/`WebPage` per zone.
  (Migration dropped `Dataset` and per-page OG images — keep that scope.)
- **Sitemap:** add `/zones` and every `/zones/{slug}` to `sitemap.xml/+server.ts`.
- **Canonicals:** inherit from `Seo.svelte` (single `SITE_URL` source).

## Design

`docs/mockups/zones/index.html` is the visual source of truth (two views: the
zone page and the `/map` footer section; toggles the shipped "modern" theme and an
"atlas" alternate). Honors the shipped tokens (`app.css`: bg `#0a0e14`, gold
accent `#e2b15a`, cyan `#5ab0c8`, Hanken Grotesk + JetBrains Mono) and impeccable
guardrails: cartographic ledger aesthetic (not another card grid — the `/zone-maps`
page already leans on one), no eyebrow kicker per section, no side-stripe borders,
no gradient text; body copy on `--color-ink`, `--color-muted` reserved for
secondary text; rarity badges use tinted fills with verified contrast; row-reveal
motion has a `prefers-reduced-motion` fallback.

## Non-goals

- No redesign or restructuring of the interactive map apps (`/map`, `/maps/{slug}`).
- No per-entity pages, no drop tables, no lore — that is the wiki's job.
- No accounts, no backend, no runtime DB (stays prerendered + static).
- No new OG imagery or `Dataset` JSON-LD (out of scope per migration plan).

## Open questions (for iteration)

- **Slug collisions:** several scenes share a display name (Island Tomb ×3,
  Mysterious Portal ×3, Azynthi's Garden ×2). `/zones/{slug}` and `/maps/{slug}`
  must be unique — scene-qualified slug, merged page, or exclude portal/instanced
  scenes? Must align with the migration's `/maps/{slug}` slug scheme.
- **Dungeon depth:** do dungeons get the same treatment, or a lighter page?
- **Sequencing:** ship with the domain/URL migration (URLs churn once) or as an
  independent follow-up after it lands?
- **Enemy→wiki resolution:** confirm the name→wiki-title mapping the wiki build
  uses is importable here, or whether a shared slug map is needed.

## Acceptance criteria

- Every non-excluded zone has a prerendered `/zones/{slug}` page whose enemy, NPC,
  resource, and connection data matches the clean DB for that zone.
- `/zones` lists all zones; `/map` renders the below-fold content section with the
  full zone directory; the deck.gl map behavior and layout are unchanged.
- All entity rows link to the correct wiki page; all connection/zone links resolve
  to real routes; no broken internal links.
- New routes appear in `sitemap.xml` with correct canonicals; JSON-LD validates in
  Google's Rich Results Test.
- Provenance line shows the real Steam build ID and export date and links to SteamDB.
- Content is present in the prerendered HTML (view-source / crawler-visible), not
  only after hydration.

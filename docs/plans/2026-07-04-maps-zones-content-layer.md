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

- **Header** — zone name (`<h1>`), a mono meta tag (`OVERWORLD · {n}
  ZONE CONNECTIONS`), player-facing level guidance, and a small set of
  planning-relevant chips. Keep this header factual and data-derived; do not add
  editorial flavor text or prose summaries that belong on the wiki. Header chips
  should answer "is this zone worth opening for my character right now?" Examples:
  recommended level, main enemy band, unique/rare spawn counts, or vendor/facility
  presence. Do not surface routine resource density such as mineral-deposit counts
  in the header. Counts belong in chips and tables, not prose.
- **Open in interactive map →** primary link to `/maps/{slug}` (the canvas app).
  Do not add row/category-level `show on map` links until the map supports stable
  URL selections for those exact targets.
- **Level guidance** — display a recommendation such as `Recommended Lv 16+` and
  a secondary distribution hint such as `Most Enemies Lv 16–22`. This is a
  player-planning signal ("when should I come here?"), not a claim that every
  enemy falls in the band. Raw min/max enemy levels stay out of the header because
  one-off rares, bosses, invulnerable encounters, or high-level strays make them
  misleading. Do not add a separate enemy-level distribution section in v1.
- **Enemies ({n})** — scannable table: name · exact level · rarity
  (common/rare/unique) · `→ wiki`. Section metadata should use high-signal counts
  such as `4 Unique · 3 Rare`, not explanatory filler such as "exact levels listed
  below." Sorted by level; uniques visually emphasized.
- **NPCs & Vendors ({n})** — list; vendors grouped first and flagged; each row gets
  `→ wiki`.
- **Resources & Points of Interest** — inline counts with the same map-marker
  icons/colors used by the interactive map. Show categories when present:
  `Teleport Destination`, `Wishing Wells`, `Forges`, `Mineral Deposits`,
  `Fishing Waters`, `Treasure Sites`, `Item Bags`, `Secret Passages`, and
  `Achievement Triggers`. Sort semantically by player intent: teleports, wishing
  wells, and forges first; repeatable gathering next; loot/pickups after that;
  progression/completion last. For high-value facilities players check
  intentionally (forge, wishing well, teleport, vendor, and future
  bank/auction-house locations), show explicit `Not present` rows when absence is
  useful. Labels must use player-facing game/map terminology — never generic
  implementation shorthand such as `nodes`.
- **Connected Zones ({n})** — outbound zone links (`DestinationZoneStableKey` →
  zone), without duplicating route text such as `DisplayText` unless it materially
  helps. Use one arrow/wayfinding language per pill; do not prefix every
  destination with the current zone name.
- **Footer** — provenance line (see Freshness).

### 2. `/zones` — zone index

A single prerendered directory of all 43 zones (deduplicated display names),
grouped overworld vs. dungeon and enriched with data-derived browse sections:
zones by recommended level, zones with teleports, zones with vendors, zones with
fishing waters, zones with treasure sites, and zones with unique spawns. Every
entry links `/zones/{slug}`. Serves the "erenshor zones" query (48 impressions,
position 9.2, 0 clicks today) and hubs the cluster.

### 3. `/map` — below-the-fold content section

The deck.gl map stays full-bleed at 100vh, untouched. Below it, a prerendered
section: a short intro with site-wide aggregates (43 zones, 3,685 spawn points,
717 NPCs, 102 mineral deposits, 55 treasure sites) and a "Browse By Zone"
directory of real `<a href>` links to every `/zones/{slug}`. No standalone marker legend or
generic wiki callout — those read as explanatory filler. Users who came for the
map never scroll; crawlers and readers get substance. This is prerendered DOM,
not a `<noscript>` block — Google renders JS, so real DOM content is the durable
mechanism; a `<noscript>` mirror is an optional accessibility floor, not the
primary lever.

## Data sources

All from the clean DB (`erenshor-{variant}.sqlite`, PascalCase schema). Per-zone
queries key on `Scene` = `Zones.SceneName`:

- **Enemies:** `SpawnPoints` (`IsEnabled=1`) ⋈ `SpawnPointCharacters`
  (`SpawnChance>0`) ⋈ `Characters` (`IsFriendly=0`), distinct by
  `CharacterStableKey`. Rarity from `Characters.IsUnique/IsRare` (else common);
  level from `Characters.Level`.
- **NPCs & vendors:** same join with `IsFriendly=1`; `IsVendor` flags vendors.
- **Resources/POIs:** `MiningNodes`, `Waters`, `WishingWells`, `Teleports`,
  `TreasureLocations`, `Forges`, `ItemBags`, `SecretPassages`, and
  `AchievementTriggers` by `Scene`.
- **Connections:** `ZoneLines` (`IsEnabled=1`), `DestinationZoneStableKey` →
  `Zones.StableKey` → `ZoneName`.
- **Recommended level:** derive a player-facing guidance signal from enemy levels
  rather than displaying raw min/max. Use spawn-weighted enemy levels, cap all
  values at the current player max level (35), and choose an outlier-resistant
  band during implementation (for example median-centered spread, IQR, or an
  inner percentile interval). The acceptance target is usefulness to players:
  "when should I come here?" The enemy table still lists exact levels.

## Wiki cross-linking ("complement, don't replicate")

Locked decision from the migration plan. This layer can mention map-derived
availability (locations, drops, vendors, resources, route connections) but should
not become the canonical long-form reference. Two directions:

- **Out:** every enemy/NPC/vendor row links to its wiki page (character name →
  wiki title; resolve via the existing name/registry mapping used by the wiki
  build). Zone pages link to the zone's wiki page for fuller notes, quest
  context, and reference details.
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

- **Titles:** `{Zone} – Enemies, NPCs & Resources | Erenshor` per zone;
  `Erenshor Zones – Enemies, NPCs & Resources` for the index. `/map` title unchanged.
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
zone page and the `/map` footer section; Modern theme only). Honors the shipped
tokens (`app.css`: bg `#0a0e14`, gold accent `#e2b15a`, cyan `#5ab0c8`, Hanken
Grotesk + JetBrains Mono) and impeccable guardrails: cartographic ledger
aesthetic (not another card grid — the `/zone-maps` page already leans on one),
no eyebrow kicker per section, no side-stripe borders, no gradient text; body
copy on `--color-ink`, `--color-muted` reserved for secondary text; rarity
badges use tinted fills with verified contrast. V1 does **not** include a static
zone image in the header. A future iteration may add a small interactive zone
map after the header if it carries real interaction value; do not spend v1 scope
on static image crops or tile-composite previews.

## Non-goals

- No redesign or restructuring of the interactive map apps (`/map`, `/maps/{slug}`).
- No per-entity reference pages and no full stat/lore duplication — that is the
  wiki's job. Map-derived drop availability may be linked or summarized, but
  detailed item/stat references stay out of this spec.
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
- **Future map embed:** after v1, consider an interactive zone-map embed directly
  below the header if it can reuse the existing map component without duplicating
  rendering logic.
- **Banks / auction houses:** current clean DB has no persistent `Bank` or
  `AuctionHouse` facility table. Name searches find disabled `Summoned: Pocket
  Bank` / `Summoned: Pocket Auctions` rift characters, not normal map-visible
  facilities. If the game has persistent bank or auction-house locations, model
  and export them separately before listing them here.

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

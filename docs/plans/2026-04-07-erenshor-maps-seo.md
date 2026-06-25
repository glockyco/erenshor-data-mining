---
title: 'SEO: erenshor-maps.wowmuch1.workers.dev'
type: plan
status: active
created: 2026-04-07
parent:
---

# SEO: erenshor-maps.wowmuch1.workers.dev

**Date:** 2026-04-07
**Scope:** `src/maps/` only
**Deploy:** `pnpm --filter maps build` then existing Cloudflare Workers deploy

---

## 1. Situation Analysis

### Search Console data

| Query | Clicks | Impressions | Position |
|---|---|---|---|
| erenshor interactive map | 4 | 12 | 5.2 |
| erenshor map | 0 | 24 | 6.4 |
| erenshor maps | 0 | 2 | 8.0 |
| erenshor world map | 0 | 1 | 4.0 |
| erenshore map | 0 | 1 | 8.0 |

The ranking story is fine — the site is already on page 1 for all five terms. The
problem is CTR. "erenshor map" has 24 impressions and 0 clicks at position 6.4.
That is not a ranking problem. It is a snippet problem. Google is auto-generating
the description from page markup (a JS-heavy prerendered app with very little
prose), and whatever it generates is not convincing anyone to click.

### What Google is seeing today

Audited the live site (`https://erenshor-maps.wowmuch1.workers.dev/`):

**Missing entirely:**
- `<meta name="description">` — on every single page
- `robots.txt` — returns 404
- `sitemap.xml` — returns 404
- Open Graph tags (`og:title`, `og:description`, `og:image`, `og:url`)
- Canonical URL tags
- JSON-LD structured data

**Semantically wrong:**
- Every page uses `<h2>` as its primary heading. There is no `<h1>` anywhere in
  the content. Google weights `<h1>` as the primary topic signal for a page.

**Title situation:**
- `(app)/+layout.svelte` sets `<title>Erenshor Interactive Maps</title>` as the
  layout-level fallback. Only `adventure-guide` and `map` set their own titles.
  Home (`/`), zone-maps, mod, and spreadsheet all inherit the generic layout title.
- The `/map` page title is `World Map | Erenshor Maps` — correct direction but no
  keyword targeting and no description.

**On-page text:**
- The home page has one `<h2>` ("Interactive World Map") and a clickable preview
  image. Zero prose. Google has almost nothing to index except the heading tex
  and the navigation links.

### Competitive contex

For "erenshor interactive map", the SERP is dominated by:
1. erenshor.fandom.com/wiki/Special:AllMaps
2. steamcommunity.com/sharedfiles/filedetails/?id=3500398991 (our own Steam guide!)
3. erenshor.wiki.gg/wiki/Zone_Maps

Our Steam guide at position ~2 links directly to the site. That is the primary
inbound traffic driver. The site itself is at position 5 — below a page tha
exists only to link to it. We can realistically move to positions 2-4 with
correct on-page signals.

---

## 2. Strategy

Three levers in order of impact:

**1. Fix the snippet** (titles + descriptions) — This is the only thing tha
fixes the 0-click-on-24-impressions problem. Targeted descriptions tell users
exactly what they will find before they click. Expected: 3-8× CTR improvemen
for "erenshor map" and similar terms.

**2. Signal topical relevance more precisely** (h1 headings, on-page text, per-page
titles) — Right now every page in the app group presents the same title to
Google. Adding per-page titles with distinct keyword targets lets Google understand
that `/map` is the interactive map, `/zone-maps` is the zone index, and so on.
Expected: stronger topical relevance scores, potentially closing the gap with wiki
competitors.

**3. Fix crawlability** (robots.txt, sitemap) — Not having a robots.txt causes
Google to apply defaults and potentially deprioritize crawl budget. The sitemap
gives Google an authoritative URL list, which matters when the fallback is
`index.html` (static adapter SPA mode) since Google cannot discover all URLs from
link-following alone.

JSON-LD and Open Graph are lower-impact for pure ranking but help with rich
results appearance and social link previews (Steam guide, Discord posts).

---

## 3. Planned Changes

### Commit 1: `chore(map): add robots.txt and sitemap`

#### `src/maps/static/robots.txt` — NEW

```
User-agent: *
Allow: /
Sitemap: https://erenshor-maps.wowmuch1.workers.dev/sitemap.xml
```

No crawl restrictions. The map page (`/map`) is prerendered via the static
adapter, so Google gets full HTML, not a blank JS shell.

#### `src/maps/static/sitemap.xml` — NEW

```xml
<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>https://erenshor-maps.wowmuch1.workers.dev/</loc>
    <changefreq>weekly</changefreq>
    <priority>1.0</priority>
  </url>
  <url>
    <loc>https://erenshor-maps.wowmuch1.workers.dev/map</loc>
    <changefreq>weekly</changefreq>
    <priority>0.9</priority>
  </url>
  <url>
    <loc>https://erenshor-maps.wowmuch1.workers.dev/zone-maps</loc>
    <changefreq>weekly</changefreq>
    <priority>0.8</priority>
  </url>
  <url>
    <loc>https://erenshor-maps.wowmuch1.workers.dev/adventure-guide</loc>
    <changefreq>weekly</changefreq>
    <priority>0.7</priority>
  </url>
  <url>
    <loc>https://erenshor-maps.wowmuch1.workers.dev/mod</loc>
    <changefreq>monthly</changefreq>
    <priority>0.6</priority>
  </url>
  <url>
    <loc>https://erenshor-maps.wowmuch1.workers.dev/spreadsheet</loc>
    <changefreq>monthly</changefreq>
    <priority>0.5</priority>
  </url>
</urlset>
```

Note: individual zone map URLs (`/[mapName]`) are not enumerated here. Zone-specific
queries don't appear in the GSC data yet, and the sitemap can be extended later
if/when they generate impressions. The zone-maps index page (`/zone-maps`) links
to all of them, which is sufficient for crawl discovery.

---

### Commit 2: `feat(map): add per-page SEO titles, descriptions, Open Graph, and JSON-LD`

This commit touches: `(app)/+layout.svelte`, `(app)/+page.svelte`,
`(app)/zone-maps/+page.svelte`, `(app)/adventure-guide/+page.svelte`,
`(app)/mod/+page.svelte`, `(app)/spreadsheet/+page.svelte`,
`map/+page.svelte`, `[mapName]/+page.svelte`.

#### `(app)/+layout.svelte` — MODIFY

Add two things:

**Canonical link** (dynamic, strips URL params — critical for the `/map` page
which accumulates `?zone=`, `?sel=`, `?layers=` etc.):

```svelte
<script lang="ts">
    import { page } from '$app/state';
    // ... existing imports
</script>

<svelte:head>
    <title>Erenshor Interactive Maps</title>  <!-- fallback; each page overrides -->
    <link
        rel="canonical"
        href="https://erenshor-maps.wowmuch1.workers.dev{$page.url.pathname}"
    />
    <script type="application/ld+json">
    {JSON.stringify({
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": "Erenshor Interactive Maps",
        "url": "https://erenshor-maps.wowmuch1.workers.dev/",
        "description": "Interactive world map for Erenshor with spawn point locations, NPC markers, zone connections, level filtering, and live player tracking."
    })}
    </script>
```

**Decision note:** The canonical is in the layout (not per-page) so every route in
the app group automatically strips URL params. The `/map` route is outside the
`(app)` group and gets its canonical directly in its own `<svelte:head>`.

**Decision note:** The JSON-LD WebSite schema goes in the layout (applies to all
pages). I am not adding a `SearchAction` potentialAction because the map search
URL format (`?sel=search:...`) is complex enough that an incorrect template would
be worse than none.

#### Per-page titles and descriptions

All titles are under 60 characters (SERP display limit). All descriptions are
under 155 characters.

| Route | Title | Description |
|---|---|---|
| `/` | `Erenshor Interactive Map – World Map & Zone Maps` | `Interactive maps for Erenshor: spawn point locations, NPC markers, zone connections, level filtering, and live player tracking.` |
| `/map` | `Erenshor Interactive Map – Enemy Spawns & NPCs` | `Explore the full Erenshor world map. Find enemy spawn points, NPC locations, teleports, and mining nodes. Filter by level and track your character live.` |
| `/zone-maps` | `Erenshor Zone Maps – All Zones & Area Maps` | `Browse all Erenshor zone maps with interactive markers for spawn points, NPC locations, and zone connections across every area in the game.` |
| `/adventure-guide` | `Erenshor Adventure Guide – Quest Companion Mod` | `In-game quest companion for Erenshor. Over 170 quests with step-by-step walkthroughs, GPS navigation, and world markers above every quest NPC.` |
| `/mod` | `Erenshor Companion Mods – Live Map Tracking` | `BepInEx companion mods for Erenshor. See your character, SimPlayers, NPCs, and enemies on the interactive map in real time.` |
| `/spreadsheet` | `Erenshor Data Spreadsheet – Items & Drop Chances` | `Erenshor data spreadsheets automatically extracted from game files: item drop chances, characters, classes, spells, skills, and ascensions.` |
| `/[mapName]` | `{zoneName} – Erenshor Zone Map` | `Interactive zone map for {zoneName} in Erenshor with spawn point markers, NPC locations, and area details.` (dynamic) |

#### Open Graph tags (same svelte:head block on each page)

Pattern applied to every page:

```html
<meta property="og:type" content="website" />
<meta property="og:site_name" content="Erenshor Interactive Maps" />
<meta property="og:title" content="…" />
<meta property="og:description" content="…" />
<meta property="og:url" content="https://erenshor-maps.wowmuch1.workers.dev/…" />
<meta property="og:image" content="https://erenshor-maps.wowmuch1.workers.dev/world-map-preview.webp" />
<meta name="twitter:card" content="summary_large_image" />
```

Image: `/world-map-preview.webp` is used for all pages. It already exists in
`static/`. The adventure-guide page uses `/adventure-guide-window.webp` instead
(more relevant visual for that page).

**Why OG tags matter here:** The Steam community guide at position ~2 links to
this site. When players share that guide link or link to the map directly on
Discord/Reddit, OG tags determine the embed appearance. Better embeds → more
clicks → more backlinks → improved ranking signal.

---

### Commit 3: `feat(map): upgrade primary headings to h1 and add home page intro`

#### h2 → h1 on primary headings

Every page in the `(app)` group uses `<h2>` as its first and only conten
heading. There is no `<h1>` anywhere in the page content. The CSS classes stay
identical — this is purely a semantic change.

Affected:
- `(app)/+page.svelte` — "Interactive World Map" h2 → h1
- `(app)/zone-maps/+page.svelte` — "Interactive Zone Maps" h2 → h1
- `(app)/adventure-guide/+page.svelte` — "Adventure Guide" h2 → h1
- `(app)/mod/+page.svelte` — "Companion Mods" h2 → h1
- `(app)/spreadsheet/+page.svelte` — needs inspection (h2 expected)

The `(app)/+layout.svelte` navigation tabs (`<a>` elements) are not headings —
no change there.

#### Home page intro paragraph — `(app)/+page.svelte`

Current: h2 heading → preview image link. No prose.

Add a short paragraph between the heading and the image:

```html
<p class="text-slate-400 mt-4 max-w-2xl mx-auto">
    Find enemy spawn points, NPC locations, teleports, mining nodes, and zone
    connections across the entire Erenshor world. Filter enemies by level range,
    search by name, and track your character live with the companion mod.
</p>
```

This is the only content change. It is factually accurate, not keyword-stuffed,
and useful to a first-time visitor who wants to know what the map does before
clicking into it. It also gives Google 40+ words of indexable prose on a page
that currently has almost none.

---

## 4. What this does NOT change

- No changes to the map's interactive behavior
- No changes to the visual design (Tailwind classes are identical)
- No changes to the data pipeline or database
- The `erenshore` misspelling (one impression, pos 8) is not explicitly targeted.
  Google's spelling normalization handles this adequately; adding misspellings
  to page content looks spammy and provides no real benefit.
- Zone map individual pages (`/[mapName]`) get titles and descriptions but are
  not added to the sitemap (can be revisited once zone-specific impressions appear).

---

## 5. Commit plan

```
chore(map): add robots.txt and sitemap
feat(map): add per-page SEO titles, descriptions, Open Graph, and JSON-LD
feat(map): upgrade primary headings to h1 and add home page intro tex
```

Three atomic commits. The first is infra-only (two new static files). The second
is all `<svelte:head>` metadata. The third is the one content/semantic change
that touches the rendered DOM, isolated so the diff is easy to review.

---

## 6. Expected impac

| Term | Current position | Expected after |
|---|---|---|
| erenshor interactive map | 5.2 | 2–4 |
| erenshor map | 6.4 | 3–5 |
| erenshor world map | 4.0 | 2–4 |
| erenshor maps | 8.0 | 4–6 |

CTR for "erenshor map" (24 impressions, 0 clicks) should move from ~0% to
something in the 5–15% range once the description gives users a clear reason to
click. At 24 impressions/period that is roughly 1–4 additional clicks per period
— modest in absolute terms but significant for a hobby project with a small total
search volume.

Ranking position improvements (not just CTR) will take 2–6 weeks to manifes
after Google re-crawls, which it will do faster once the sitemap is submitted via
Search Console.

---

## 7. Out of scope / future work

- **Custom domain** — The `.workers.dev` subdomain is functional but Google gives
  some authority preference to custom domains. If the project ever gets
  `erenshor-maps.com` or similar, the canonical tags installed here make migration
  trivial (update one string).
- **Backlinks** — The Steam guide is the best existing backlink. Posting the map
  link in the official Erenshor Discord and linking from the wiki.gg page would
  provide meaningful backlink diversity. Out of scope for this code change.
- **Zone-specific queries** — As the game grows and zone-specific searches appear
  in GSC, the individual zone map pages (`/[mapName]`) can be added to the
  sitemap and given richer descriptions.
- **Search Console sitemap submission** — After deploying, manually submit the
  sitemap URL in Google Search Console for faster re-indexing.

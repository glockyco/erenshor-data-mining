---
title: Maps SEO & Content Improvements
type: plan
status: active
created: 2026-06-26
parent: 2026-05-18-maps-seo-hardening
---

# Maps SEO & Content Improvements

Execution tracker for the current SEO and content push on `src/maps/`, prompted by
Search Console data (~33 clicks / ~715 impressions per quarter, dominated by
brand and navigational terms) and an expert plus community-mining review. The
detailed design for the domain move and the I-series items lives in the parent
hardening spec. This doc tracks what actually ships and the decisions behind it.

## Decisions (locked)

- **Interactive zone maps move to `/maps/{slug}`.** `/zones/{slug}` is reserved
  for a future textual reference layer (ancient-kingdoms-compendium style). Do the
  URL move together with the domain migration so URLs change only once.
- **Domain: `erenshor.compendiums.org`.** We already own `compendiums.org`, and the
  sister project follows a `{game}.compendiums.org` pattern (`ancient-kingdoms.compendiums.org`).
  `erenshor.compendiums.org` is shorter than `erenshor-maps.compendiums.org` and
  fits better, because the site covers the maps, the spreadsheet, the mods, and the
  Adventure Guide, not maps alone. Pointing the subdomain at the Worker is Cloudflare
  config (a custom-domain route), not a domain registration.
- **FAQ is a generative-engine / AI-citation play, not a Google rich result.** Google
  removed FAQ rich results from Search in May 2026. Keep `FAQPage` JSON-LD anyway,
  since AI engines and Bing still parse it.
- **We complement the official wiki, we do not replicate it.** The wiki has drop
  rates, stats, lore, and coordinates, and its enemy and zone pages link to our map.
  We are the visual and live layer, and we link back to the wiki.
- **Crawlable content layer (`/zones/{slug}` reference pages) is future work**, out
  of scope here. It needs its own brainstorm and spec.

## Tasks

### SEO quick wins (valid under the current host)
- [x] Fix zone-maps blurb link to `/map`. Fix `WebApplication` JSON-LD `url` to `/map`
- [x] `canonicalUrl()` strips query and hash (spec I2) plus unit test
- [x] Sitemap `<lastmod>` build timestamp (spec I1) plus test
- [x] Broaden `/map` title to `Erenshor Interactive Map – Spawns, Drops, Resources & NPCs`
- [x] Weave the "Erenshor map" keyword into the landing lede, keeping the `Chart the world of Erenshor.` H1
- [x] Add a FAQ section plus `FAQPage` JSON-LD to the landing page (wording in Appendix A)
- [ ] Add `Dataset` JSON-LD (`dateModified` = patch refresh date) and enrich `VideoGame` (publisher, expanded `sameAs`) (audit E)
- [ ] Per-page OG images for `/map`, `/spreadsheet`, `/mod` (spec I5) plus a `rel="noopener"` audit on external `_blank` links (spec N5)
- [ ] Consolidate per-page JSON-LD into one `@graph` (spec I4, optional)
- [ ] CWV freebies: swap the landing GIF for the existing MP4, and drop production sourcemaps in `vite.config.ts` (audit D)

### Domain migration (blocked on a decision to proceed; no registration needed)
- [ ] Bind `erenshor.compendiums.org` to the production Worker in `src/maps/wrangler.jsonc`: set `workers_dev` to false and add a route with `custom_domain` true, mirroring ak-mods `wrangler.toml`. Rename the production Worker (for example `erenshor-maps-site`) so the original `erenshor-maps` name stays free for the redirect Worker
- [ ] Add a redirect-only Worker that keeps the legacy `erenshor-maps.wowmuch1.workers.dev` hostname (Worker name stays `erenshor-maps`) and 301s every path to `https://erenshor.compendiums.org`, modeled on ak-mods `redirect-worker.ts` and `wrangler.redirect.toml`. Serve the Google verification path directly so the old GSC property can still verify. Deploy this only after the custom domain is verified
- [ ] Swap `SITE_URL` in `src/maps/src/lib/seo/site.ts`, add the new GSC property, run Change of Address, and resubmit the sitemap
- [ ] Repoint the references we control. The **official wiki is the most important**: it is admin-controlled and its enemy and zone pages cross-link to the map, which drives most of the map's traffic, so update the map-link template there to the new domain. Then update the Steam guide, the in-game and mod links, and the README

### URL restructure (bundle with the domain migration)
- [ ] Move `/[mapName]` to `/maps/{slug}`. 301 the old root zone URLs, and update the internal links, the `zoneMapJsonLd` url, and the sitemap zone routes

### Deferred / follow-ups (not this push)
- [ ] (deferred) 404 `noindex` page (spec I3). Needs an adapter `fallback` plus a `wrangler` `not_found_handling` change to actually be served. Lowest value, behavioral wrinkle
- [ ] (feature) Item-to-droppers search in `MapSearch`. Index items and render a "drops from" result that deep-links to each enemy, which lets the drops FAQ point straight at an item. `loot_drops` already supports the reverse lookup
- [ ] (future) Crawlable content layer at `/zones/{slug}`, its own spec

## Notes

- The April scaffold (`2026-04-07-erenshor-maps-seo`) appears fully implemented on
  the live site (robots, sitemap, per-page titles, descriptions, OG, JSON-LD, H1s,
  landing prose). A later refactor moved it to the `Seo` component plus endpoint
  routes. It is a candidate for `omp-plans complete`.
- Parent hardening spec status: I1 and I2 shipped here, I3 deferred, I4, I5, and C1
  tracked above.

## Appendix A — FAQ content (approved wording)

Answer-first, verified against the game code, the official wiki, Steam discussions
and reviews, and web and press coverage. Every reference is a working link.

**Core "where / what":**

1. **Where do I find a specific enemy, NPC, or vendor?**
   Search the [world map](/map) by name. It shows every spawn with its exact
   coordinates and spawn chance, along with vendors, resource and fishing nodes,
   treasure, and zone exits. Run the [companion mod](/mod) to add a live view that
   places your character, your party, and nearby creatures on the map as you play.

2. **How do I see what an enemy drops?**
   Click a spawn point on the [world map](/map) to open its popup. The popup lists
   the creatures that spawn there and each one's full drop table with exact
   percentages, taken straight from the game files and refreshed every patch.

3. **I cannot find an enemy that should be here. Where is it?**
   It is probably on its respawn timer or away on a patrol route. The
   [world map](/map) shows respawn timers and patrol paths for each spawn, and the
   [companion mod](/mod) adds live markers so you can see exactly where everything
   is right now.

4. **Do I need to install anything to use this?**
   No. The [world map](/map) and the rest of the site run in your browser with
   nothing installed. The optional [companion mod](/mod) adds the live view, and the
   [Adventure Guide](/adventure-guide) adds in-game quest guidance.

**Disambiguation:**

5. **Does Erenshor have a map and quest markers?**
   Yes. Erenshor has a world map, a minimap, and optional quest markers. This site
   adds a [searchable map](/map) of every enemy, vendor, resource node, and treasure
   location, and the [Adventure Guide](/adventure-guide) adds full step-by-step quest
   routing on top of the in-game markers.

6. **Is Erenshor multiplayer?**
   No. Erenshor is an offline single-player "simulated MMORPG" where the other
   adventurers are AI SimPlayers. There is no official multiplayer. If you want to
   play together, the community
   [co-op mod](https://thunderstore.io/c/erenshor/p/mizuki/Erenshor_COOP/) brings
   co-op to the game.

7. **Are SimPlayers real players or AI chatbots?**
   Neither. [SimPlayers](https://erenshor.wiki.gg/wiki/Simulated_Players) are
   scripted AI characters (state machines and decision trees, not an LLM) that level
   up, group, trade, and chat to make the world feel populated.

8. **How is this different from the official wiki?**
   They work together and link to each other. The
   [official wiki](https://erenshor.wiki.gg) has drop rates, stats, and lore, and its
   enemy pages link to this map. The [world map](/map) shows you visually where
   everything is, with every spawn on one map, filtering, and live positions, and
   links back to the wiki for the deeper details.

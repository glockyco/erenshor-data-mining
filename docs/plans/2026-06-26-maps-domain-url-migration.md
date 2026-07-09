---
title: Maps Domain Migration & URL Restructure
type: plan
status: active
created: 2026-06-26
parent: 2026-07-09-erenshor-planning-overview
---

# Maps Domain Migration & URL Restructure

The remaining `src/maps/` SEO work after the quick-wins and content push shipped.
This is one coordinated release (domain + URL move, so URLs churn once) plus a
short independent backlog. The section-nav lens shipped separately and is unrelated.

For background: archived `2026-06-26-maps-seo-and-content` records what already
landed (and the approved FAQ wording); archived `2026-05-18-maps-seo-hardening`
holds the full findings, the C1 domain rationale, and the per-route canonical audit.

## Decisions (locked)

- **Domain: `erenshor.compendiums.org`.** We own `compendiums.org`; the sister
  project uses `ancient-kingdoms.compendiums.org`. `erenshor.compendiums.org` is
  shorter than `erenshor-maps.compendiums.org` and fits the whole site (maps,
  spreadsheet, mods, Adventure Guide), not maps alone. Pointing the subdomain at
  the Worker is Cloudflare config (a custom-domain route), not a registration.
- **Interactive zone maps move to `/maps/{slug}`.** `/zones/{slug}` stays reserved
  for the future textual reference layer. Do the URL move with the domain migration
  so URLs change only once.
- **Complement the wiki, don't replicate it.** The wiki's enemy and zone pages
  cross-link to our map and drive most of its traffic, so repointing that map-link
  template is the highest-value backlink task in the migration.
- **Dropped, will not do:** `Dataset` JSON-LD, per-page OG images (spec I5), the
  external-link `rel` audit (spec N5), and the optional `@graph` consolidation (spec I4).

## Tasks

### Domain migration (C1 — blocked on a go-ahead; no registration needed)
- [ ] Bind `erenshor.compendiums.org` to the production Worker in `src/maps/wrangler.jsonc`: set `workers_dev` false and add a `custom_domain` route, mirroring ak-mods `wrangler.toml`. Rename the production Worker (e.g. `erenshor-maps-site`) so the `erenshor-maps` name stays free for the redirect Worker
- [ ] Add a redirect-only Worker that keeps the legacy `erenshor-maps.wowmuch1.workers.dev` host (Worker name stays `erenshor-maps`) and 301s every path to `https://erenshor.compendiums.org`, modeled on ak-mods `redirect-worker.ts` + `wrangler.redirect.toml`. Serve the Google verification path directly so the old GSC property still verifies. Deploy only after the custom domain verifies
- [ ] Swap `SITE_URL` in `src/maps/src/lib/seo/site.ts` (single source of truth — canonicals, OG, JSON-LD `@id`, sitemap, robots all inherit). Replace `static/google279cf61d0b725839.html` with the new property's token. Add the new GSC property, run Change of Address, resubmit the sitemap
- [ ] Repoint the references we control, wiki first: update the wiki's map-link template (admin-controlled; its enemy/zone cross-links drive most map traffic), then the Steam guide, the in-game and mod links, and the README

### URL restructure (ship with the domain migration so URLs churn once)
- [ ] Move `/[mapName]` to `/maps/{slug}`: 301 the old root zone URLs, and update the internal links, the `zoneMapJsonLd` url, and the sitemap zone routes

### Backlog (independent of the migration)
- [ ] (low value) 404 `noindex` page (spec I3): needs an adapter `fallback` plus a `wrangler` `not_found_handling` change to actually be served
- [ ] (feature) Item-to-droppers search in `MapSearch`: index items and render a "drops from" result that deep-links each enemy, so the drops FAQ can point straight at an item. `loot_drops` already supports the reverse lookup
- [ ] (future, own spec) Crawlable textual content layer at `/zones/{slug}`

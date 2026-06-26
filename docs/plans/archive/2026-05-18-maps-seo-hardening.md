---
title: Maps SEO Hardening Spec
type: spec
status: implemented
created: 2026-05-18
parent:
archived: 2026-06-26
---

# Maps SEO Hardening Spec

**Date:** 2026-05-18
**Scope:** `src/maps/` only
**Trigger:** Google Search Console flagged `https://erenshor-maps.wowmuch1.workers.dev/map?sel=enemy:Reliquary+Ward` under "Alternate page with proper canonical tag" (1 affected URL, first detected 5/16/26).
**Predecessor:** `docs/plans/2026-04-07-erenshor-maps-seo.md` (initial SEO scaffold — robots, sitemap, per-page titles, JSON-LD).

**Status (2026-06-26):** Findings triaged. I1 and I2 shipped (see archived `2026-06-26-maps-seo-and-content`); I4, I5, and N5 dropped; I3 and C1 carried to `2026-06-26-maps-domain-url-migration`, which holds the live domain decision (`erenshor.compendiums.org`) and the URL move. This spec is kept as the research reference for the C1 rationale and the per-route canonical audit.

---

## 1. TL;DR

The reported GSC notice **is not an error**. "Alternate page with proper canonical tag" is the *Not indexed* status Google emits when it discovers a URL, follows its `rel="canonical"`, and respects the canonical instead of indexing the alternate. The current implementation hardcodes `<link rel="canonical" href=".../map">` on the `/map` route regardless of `?sel=…`, so Google is correctly consolidating the filtered URL into the bare `/map`. That is exactly the user's intuition ("canonical should be plain `/map` without parameters") and it is already what the codebase does. No action required for the immediate symptom.

However, the audit surfaced one critical structural issue (`.workers.dev` hostname) and several lower-severity gaps worth addressing now while the surface is fresh. The remediation is a small, contained set of commits — no architecture changes.

---

## 2. Verdict on the reported symptom

### What GSC means by "Alternate page with proper canonical tag"

Google Search Console catalogues every URL it discovers. URLs Google chose *not* to index because a canonical tag pointed elsewhere are bucketed under this informational status. It is the success case for canonicalization — sources [1][3]:

> "Alternate page with proper canonical tag" is *Not indexed*, not *Error*. Google deliberately did not index the URL because the canonical you set pointed it at the preferred version. In most cases no action is necessary; the status confirms your setup is working. Investigate only if (a) the URLs listed are pages you *do* want indexed (canonical misconfiguration), (b) the count is unexpectedly large and growing, or (c) the canonical target itself has issues. — *seotesting.com, aioseo.com*

Our case fails all three "investigate" triggers:
- (a) The flagged URL (`/map?sel=enemy:Reliquary+Ward`) is a transient filtered view of the world map, not a standalone document we want indexed.
- (b) One affected page in three months.
- (c) Canonical target `/map` is the prerendered, indexable primary URL.

The user can dismiss the notice. Clicking "Validate fix" in GSC is harmless but not meaningful here — the configuration is already correct.

### Confirmation that the current canonical strategy is righ

For our `/map` view-state query parameters (`?sel`, `?layers`, `?zone`, `?lvl`, `?x`, `?y`, `?z`, `?debug`), every modern SEO source agrees the correct canonical target is the parameterless URL — sources [2][7]:

> Reserve query parameters for filtering and sorting with canonical tag management. Use a canonical tag to point each set of parameterised URLs to a single, preferred address — in most cases the clean version without tracking tags. […] If a URL parameter doesn't make a significant or unique change to the rendered content (in the sense that crawlers can't and shouldn't index dozens of permutations), implement URL canonicalization to avoid duplicate content. — *stackmatix.com, matomo.org, LogRocket*

Our parameters describe ephemeral viewport/selection/filter state, not distinct content. Self-referencing canonicals on `?sel=…` URLs would tell Google to index a near-infinite combinatorial space of view states — strictly worse than the current setup. Keep the hardcoded canonical.

---

## 3. Findings & Recommendations

### CRITICAL

#### C1. Production host is `*.workers.dev`

**Problem.** `SITE_URL = 'https://erenshor-maps.wowmuch1.workers.dev'` (`src/maps/src/lib/seo/site.ts:10`) is Cloudflare's default per-account preview subdomain. This bleeds into every canonical, every Open Graph URL, every JSON-LD `@id`, the sitemap, robots, and the GSC verification file (`static/google279cf61d0b725839.html`). Cloudflare's own documentation explicitly recommends against using it for production — source [8]:

> Your `workers.dev` subdomain allows you to get started quickly without first onboarding a custom domain to Cloudflare. It's recommended to run production Workers on a Workers route or custom domain, rather than on your workers.dev subdomain. — *developers.cloudflare.com/workers/configuration/routing/workers-dev/*

The SEO impact is concrete:
- **Brand dilution.** Position 5 in SERP for "erenshor interactive map" (per prior audit) is below `erenshor.fandom.com` and our own Steam guide. A `.workers.dev` URL in the result snippet reads as a staging/preview link — visible CTR penalty independent of ranking.
- **Backlink consolidation risk.** Anyone linking to the site (Steam guide, Discord, Reddit, the in-game mod) gets a `.workers.dev` URL. Future migration to a real domain requires 301 redirects to preserve link equity — source [9]: *"Set up 301 redirects from your old domain to the new one. This tells search engines your site has moved for good and helps keep your search rankings intact."*
- **Trust / sharing.** Browser address bar, OG preview cards (Discord, Steam, Twitter) all surface `wowmuch1.workers.dev` — a string visibly bound to a Cloudflare account name rather than the project.

**Recommendation.** Decide on and configure a custom domain (e.g., `erenshor.wowmuch.com`, `erenshor-maps.wowmuch.com`, `erenshor.tools`, or similar). The migration is mechanical once the domain exists:

1. Add Cloudflare custom domain binding in `wrangler.jsonc` (`routes` or `custom_domains` field, depending on which workers offering is used).
2. Change `SITE_URL` in `src/maps/src/lib/seo/site.ts`. Single source of truth — every downstream (`Seo.svelte`, `jsonld.ts`, `sitemap.xml/+server.ts`, `robots.txt/+server.ts`) inherits automatically.
3. Configure a Cloudflare redirect rule (or keep the `.workers.dev` route bound and add a Worker `fetch` handler that 301s to the custom domain) for any inbound links still hitting the old host. Cloudflare bulk redirects work for this without touching the application.
4. In GSC: add the new host as a property, re-upload `google279cf61d0b725839.html` to verify, submit the new sitemap, request indexing on the homepage, and leave the old property in place to monitor 301 traffic.
5. Update the Steam Community guide and any in-game / mod-side links (search the repo for `erenshor-maps.wowmuch1.workers.dev` — it's already isolated to the SEO module, but mod-side WebSocket URLs use a different domain and aren't affected).

This is the single highest-impact change in this spec. **The remaining findings should be implemented in the same release window so the new domain debuts with all SEO improvements in place** — avoids a second round of GSC re-validation.

---

### IMPORTANT

#### I1. Sitemap is missing `<lastmod>`

**Problem.** `src/maps/src/routes/sitemap.xml/+server.ts:13-15` emits bare `<url><loc>…</loc></url>` entries. Google's current sitemap guidance (2025/2026) is unambiguous: drop `<changefreq>` and `<priority>` (Google ignores both), but **keep `<lastmod>`** because Google uses it to schedule recrawls — sources [4][5][6]:

> Google ignores `priority` and `changefreq`, but it does use `lastmod` when that value is consistently and verifiably accurate. […] It's more effective to maintain accurate lastmod dates, since Google actively uses those to decide when to re-crawl pages. — *w3era.com, iridium-works.com*

The constraint is "consistently and verifiably accurate" — fabricated or always-now timestamps get ignored. For a prerendered static site, the correct lastmod is the build timestamp (every prerendered page rebuilds together) or, ideally, the source content's last-touched timestamp.

**Recommendation.** Emit one `<lastmod>` per `<url>` using the build timestamp embedded at prerender time. Implementation options:

- **Simple (recommended).** Capture `new Date().toISOString()` at module load time in `sitemap.xml/+server.ts`. Since the file is prerendered (`export const prerender = true`), this freezes to the build timestamp and matches Google's "build-time accurate" expectation.
- **Per-route (optional, low ROI).** Track per-route content provenance (e.g., zone slug → max `mtime` of `variants/main/erenshor-main.sqlite` for `[mapName]` routes, max source mtime for static pages). Worth doing only if rebuilds happen frequently for unchanged content — not our case.

Use full W3C Datetime (`YYYY-MM-DDThh:mm:ss+00:00`), not date-only, per source [7].

#### I2. `canonicalUrl()` does not defensively strip query strings or fragments

**Problem.** `src/maps/src/lib/seo/site.ts:40-44`:

```ts
export function canonicalUrl(path: string): string {
    if (path === '/' || path === '') return `${SITE_URL}/`;
    const normalized = path.startsWith('/') ? path : `/${path}`;
    return `${SITE_URL}${normalized.replace(/\/$/, '')}`;
}
```

Every current caller passes a clean path string, so this works. But it is one mistake away from emitting `<link rel="canonical" href=".../map?sel=foo">`. A future maintainer who writes `<Seo path={$page.url.pathname + $page.url.search} ... />` (a plausible mistake when retrofitting per-page canonicals) would silently introduce the duplicate-content problem this spec is trying to prevent.

**Recommendation.** Defensively strip query strings and hash fragments inside `canonicalUrl()` itself. Add a corresponding unit test asserting `canonicalUrl('/map?sel=foo#x') === 'https://…/map'`. Cost: ~3 lines + 1 test. Benefit: invariant becomes mechanically enforced.

#### I3. No custom 404 page, and Cloudflare's default 404 is indexable

**Problem.** `src/maps/wrangler.jsonc:12` sets `"not_found_handling": "none"`. Good — this avoids the SPA-fallback soft-404 trap (every unknown URL resolving to `index.html` and ranking as a duplicate of the home page). But there is no `+error.svelte` in the routes tree, so unknown URLs hit Cloudflare's default 404 HTML, which contains no `<meta name="robots">` tag and is theoretically indexable. In practice Google handles HTTP 404 correctly and de-indexes such pages, but a small surface improvement is cheap.

**Recommendation.** Add `src/maps/src/routes/+error.svelte` that renders a friendly 404 panel with `<Seo path="/" noindex={true} />` and an explicit 404 status. The `<Seo noindex>` path already emits `<meta name="robots" content="noindex, nofollow">` (per `Seo.svelte:72-74`). This costs ~30 LOC and gives users hitting a stale URL (e.g., a deleted zone slug after a data export) something better than the raw Cloudflare page.

#### I4. JSON-LD entities are scattered, not joined via `@graph`

**Problem.** `src/maps/src/lib/seo/jsonld.ts` defines three stable `@id`s — `${SITE_URL}/#game`, `${SITE_URL}/#website`, `${SITE_URL}/#webapp` — and pages emit multiple `<script type="application/ld+json">` blocks one after another (e.g., home page emits website + webapp + videogame as three separate JSON-LD scripts). Schema.org allows this, but the modern recommended shape is one `@graph` array per page so Google can resolve the relations in one pass. Source [11]: Google's structured data crawler handles either form, but `@graph` is the preferred pattern when multiple entities share stable `@id`s and reference each other via `about` / `isPartOf`.

This is **nice-to-have**, not a bug — leaving it as-is doesn't break anything.

**Recommendation (optional).** Add a `graph(...entities)` helper in `jsonld.ts` that wraps `{ '@context': 'https://schema.org', '@graph': [...] }`, and migrate page-side `jsonLd={[a(), b(), c()]}` to `jsonLd={graph(a(), b(), c())}`. Validate with Google's Rich Results Test after the domain change so any warnings reference the production URL.

#### I5. Open Graph image is generic on every page; zone pages have richer assets available

**Problem.** Every page sets `og:image` to `/og-default.png`. Zone pages have per-zone preview thumbnails in `src/maps/static/maps/{ZoneKey}.jpg` (43 of them). Discord / Steam / Reddit embeds for a specific zone (`/Reliquary`, `/Vitheo`, etc.) would visually match the linked content if the per-zone thumbnail were used. Same applies to `/map` (could use `world-map-preview.webp` already in `static/`) and `/adventure-guide` (could use `adventure-guide-window.webp`).

**Recommendation.** Wire per-page `image` props:

| Route | OG image |
|---|---|
| `/` | Keep `/og-default.png` |
| `/map` | `/world-map-preview.webp` (1200×630 — verify dimensions, regenerate if needed) |
| `/zone-maps` | Keep `/og-default.png` (it's an index, generic is correct) |
| `/[mapName]` | `/maps/${mapName}.jpg` (verify each thumbnail meets OG 1200×630 minimum; regen via `scripts/generate-thumbnails.mjs` if not) |
| `/adventure-guide` | `/adventure-guide-window.webp` |
| `/mod` | A still frame from `/world-map-companion.gif`, or keep default |
| `/spreadsheet` | `/spreadsheet.png` (exists in `static/`) |

Dimensions matter for Twitter `summary_large_image`: minimum 600×314, recommended 1200×630. The Seo component already takes `imageWidth` / `imageHeight` overrides.

---

### NICE-TO-HAVE

#### N1. Sitemap could ping search engines on rebuild

Not really worth it. Google retired the sitemap ping endpoint in 2023. Bing's IndexNow is an option but our prerendered build cadence is low. Skip.

#### N2. Service worker caches DB and tiles but not HTML

`src/maps/src/service-worker.ts` deliberately caches only the SQLite DB and zone tile images, never HTML. This is correct — crawlers don't execute service workers, but skipping HTML caching also avoids ever serving stale HTML to returning users that could lag canonical changes. No action.

#### N3. Trailing slash policy is internally consisten

`wrangler.jsonc` sets `"html_handling": "auto-trailing-slash"`. SvelteKit's adapter-static emits `build/map.html` (no slash) for a route declared as `trailingSlash: 'never'` (the unspecified default). Cloudflare Workers Assets with `auto-trailing-slash` serves `/map` directly from `map.html` (canonical) and 307-redirects `/map/` and `/map.html` to `/map`. SvelteKit's own links never produce trailing slashes. Internal `<a href>` audit (`src/maps/src/routes/(app)/zone-maps/+page.svelte:38` uses `href={\`${mapName}\`}` — relative, no slash) shows no internal links generate trailing-slash variants. No action.

#### N4. GSC verification file is hostname-specific

`src/maps/static/google279cf61d0b725839.html` is bound to the current GSC property. When the domain changes (C1), this file needs replacement with the new property's token — it's just a string in a file Cloudflare serves, no code change.

#### N5. External link audi

`src/maps/src/routes/(app)/spreadsheet/+page.svelte` has many `https://docs.google.com/...` links. They are user-action links (open the spreadsheet), so `rel="nofollow"` is wrong (we *do* endorse them). `rel="noopener"` should be paired with any `target="_blank"`. Verify all 11 sheet links and the Ko-fi / Thunderstore links carry `rel="noopener noreferrer"` when `target="_blank"`. Cheap pass; do it during the I5 work.

---

## 4. Per-route audit (canonical correctness)

| Route | Canonical emitted | Query params accepted | Indexable? | Status |
|---|---|---|---|---|
| `/` | `${SITE_URL}/` | none | yes | ✓ correct |
| `/map` | `${SITE_URL}/map` (hardcoded) | `sel`, `layers`, `zone`, `lvl`, `x`, `y`, `z`, `debug` | yes (canonical only) | ✓ correct — **this is the GSC notice case** |
| `/zone-maps` | `${SITE_URL}/zone-maps` | none | yes | ✓ correct |
| `/[mapName]` | `${SITE_URL}/${mapName}` | `marker` | yes (canonical only); `noindex` if config missing | ✓ correct |
| `/adventure-guide` | `${SITE_URL}/adventure-guide` | none | yes | ✓ correct |
| `/mod` | `${SITE_URL}/mod` | none | yes | ✓ correct |
| `/spreadsheet` | `${SITE_URL}/spreadsheet` | none | yes | ✓ correct |
| `/sitemap.xml` | n/a | n/a | n/a (XML) | ✓ |
| `/robots.txt` | n/a | n/a | n/a | ✓ |

Every canonical is correct under both the user's stated intent and 2025/2026 SEO best practice. The `/map` route — the exact one in the GSC notice — is doing the right thing.

---

## 5. Implementation order (commit plan)

This is a spec, not a step-by-step plan. Follow-up work should be sequenced as separate commits, in this order:

1. **`feat(map): strip query strings and hashes in canonicalUrl helper`** (I2). Cheapest defensive change; lands first because it enforces an invariant the rest of the spec relies on.
2. **`feat(map): emit lastmod in sitemap`** (I1). Self-contained.
3. **`feat(map): add 404 error page with noindex`** (I3). Self-contained.
4. **`feat(map): per-page Open Graph images`** (I5). Self-contained; verify image dimensions during the commit.
5. **`refactor(map): consolidate JSON-LD into @graph wrapper`** (I4). Optional; defer if low priority.
6. **`feat(map): migrate to custom domain`** (C1). Coordinated change — touches `wrangler.jsonc`, `src/maps/src/lib/seo/site.ts`, possibly DNS, and requires post-deploy actions in Cloudflare dashboard and GSC. Do this last so all on-page improvements ship under the new host on the first crawl. Update Steam Community guide and any other backlink sources after the domain is live and 301s are confirmed.

Pre-C1 commits remain fully valid under the `.workers.dev` host — no work is wasted if the domain decision slips.

---

## 6. Explicit non-goals

- **No** content rewrites. Titles, descriptions, and JSON-LD bodies introduced by the April 2026 spec are working as designed.
- **No** removal of the GSC verification file (`static/google279cf61d0b725839.html`) until the new domain is verified; it stays for the current property.
- **No** change to crawl directives. `robots.txt` stays fully permissive.
- **No** self-referencing canonicals for `?sel=…` URLs (research [2][7] explicitly recommends against this for filter-state parameters in SPAs).
- **No** AMP, no hreflang, no rich-result-specific schema beyond what `jsonld.ts` already emits. The site is en-only and not a content site that needs Article / FAQ / Recipe shapes.
- **No** changes to mod-side code, in-game WebSocket URLs, or the Python pipeline. This spec is `src/maps/`-only.

---

## 7. Open questions for the user

1. **Custom domain choice** (blocks C1). Candidates: `erenshor.wowmuch.com`, `erenshor-maps.wowmuch.com`, a new TLD like `erenshor.tools`, or something else. The choice has minor SEO weight beyond "must not be `.workers.dev`" — keyword-in-domain matters very little to Google in 2025/2026, brand consistency matters more.
2. **Priority of I4 (`@graph` refactor)**. Marked optional. Skip it if visible-page changes have higher value.
3. **Per-zone OG image regeneration** (I5). The existing `static/maps/{Zone}.jpg` thumbnails may not be 1200×630. If they need regenerating, that's an extra step inside the I5 commit using `scripts/generate-thumbnails.mjs`.

---

## 8. Sources

1. [Alternate Page with Proper Canonical Tag: Fix Guide 2026 — SEOTesting](https://seotesting.com/google-search-console/alternate-page-with-proper-canonical-tag/)
2. [SPA URL Structure and SEO Best Practices — Stackmatix](https://www.stackmatix.com/blog/spa-url-structure-seo-best-practices)
3. [Understanding the Alternate Page with Proper Canonical Tag Status — AIOSEO](https://aioseo.com/docs/understanding-the-alternate-page-with-proper-canonical-tag-status-in-google-search-console/)
4. [XML Sitemap Setup Guide (2026) — RightBlogger](https://rightblogger.com/blog/xml-sitemap-setup)
5. [XML Sitemap Guide 2026 — W3era](https://www.w3era.com/blog/seo/xml-sitemap-seo-guide/)
6. [Change Frequency, Last Change and Priority Values in Sitemaps — Iridium Works](https://www.iridium-works.com/en/blog-post/change-frequency-last-change-and-priority-values-in-sitemaps)
7. [The Ultimate URL Parameter Playbook — Matomo](https://matomo.org/blog/2025/11/url-parameter/)
8. [`workers.dev` documentation — Cloudflare](https://developers.cloudflare.com/workers/configuration/routing/workers-dev/)
9. [SEO Best Practices with Cloudflare Workers, Part 1: Subdomain vs. Subdirectory — Cloudflare Blog](https://blog.cloudflare.com/subdomains-vs-subdirectories-best-practices-workers-part-1/)
10. [Consolidate Duplicate URLs — Google Search Central](https://developers.google.com/search/docs/crawling-indexing/consolidate-duplicate-urls)
11. [rel=canonical: the ultimate guide — Yoast](https://yoast.com/rel-canonical/)

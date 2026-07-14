---
title: Maps Domain Migration & URL Restructure
type: plan
status: implemented
created: 2026-06-26
parent: 2026-07-09-erenshor-planning-overview
archived: 2026-07-14
---

# Maps Domain Migration & URL Restructure

This plan owns one coordinated release that serves the maps site from
`erenshor.compendiums.org` and moves interactive zone pages to `/maps/{slug}`.
The retained Cloudflare Worker is named `erenshor-maps`, keeps
`workers_dev: true`, and serves both `erenshor-maps.wowmuch1.workers.dev` and
the custom-domain route. Both hosts use one Worker entrypoint and one static
build. No deployment or external cutover is authorized until the repository
work and every manual gate below is complete. The independent backlog is not
part of this cutover.

The migration is complete. The shared Worker is deployed and verified on both
hosts; Search Console Change of Address and the custom-domain sitemap submission
are complete; wiki, Steam, compendiums.org, and repository-controlled backlinks
use the canonical origin. The legacy `/map` runtime and verification token remain
healthy for shipped companion overlays and old-property monitoring.

## Decisions (locked)

- **One retained Worker.** Keep the existing Worker name
  `erenshor-maps`, its workers.dev origin, and `workers_dev: true`. Add the
  custom-domain route for `erenshor.compendiums.org` to that same Worker. Do
  not create another Worker, change the Worker name, or maintain separate
  production and redirect configurations.
- **One entrypoint and one build.** Wrangler invokes a Worker entrypoint that
  has an `ASSETS` static-assets binding and `run_worker_first`. The entrypoint
  performs host-aware routing before delegating eligible requests to the
  shared static build. The build is produced once and is the only asset set
  deployed to both hosts; there is no host-specific or redirect-only build.
- **Domain: `erenshor.compendiums.org`.** We own `compendiums.org`; the sister
  project uses `ancient-kingdoms.compendiums.org`. The shorter subdomain fits
  the whole site (maps, spreadsheet, mods, and Adventure Guide), not maps
  alone. Pointing it at the Worker is a Cloudflare custom-domain route, not a
  registration.
- **Interactive zone maps move to `/maps/{slug}`.** `/zones/{slug}` remains
  reserved for a future textual reference layer. Do the URL move with the
  domain migration so URLs change only once.
- **Preserve old companion overlays.** Shipped companion DLLs hardcode
  `https://erenshor-maps.wowmuch1.workers.dev/map` and reject full-document
  navigation to another host. Therefore the legacy `/map` document and every
  runtime resource it loads remain same-origin `200` responses on the legacy
  host. This behavior is selected by request host and path, never by
  user-agent sniffing. Updating the current companion source is repository
  work, but does not require a companion release for this migration.
- **Complement the wiki, don't replicate it.** The wiki's enemy and zone pages
  cross-link to the map and drive most of its traffic, so repointing the
  MapLink surface is the highest-value backlink task.
- **Dropped, will not do:** `Dataset` JSON-LD, per-page OG images (spec I5),
  the external-link `rel` audit (spec N5), and optional `@graph` consolidation
  (spec I4).

## Host, route, and response matrix

The Worker must implement this matrix using the request hostname and URL path.
A request's `User-Agent` must not affect the result. Query strings are retained
byte-for-byte by redirects; HTTP requests do not carry fragments.

| Host and request | Required response |
| --- | --- |
| `erenshor.compendiums.org`, normal application document or `/maps/{exact-key}` | Serve normally from the shared build with `200`; `/maps/{exact-key}` is the only canonical interactive-zone spelling. |
| `erenshor.compendiums.org/map` | Serve the world map from the shared build with `200`; its canonical is the new host's `/map`. |
| `erenshor.compendiums.org`, runtime resource | Serve from the shared build with `200`, including `/service-worker.js`, Svelte assets and `__data.json`, SQLite, tiles, images, icons, fonts, and other non-HTML resources. |
| `erenshor-maps.wowmuch1.workers.dev/map` | Serve the world-map document with `200` from the shared build. It must be usable by shipped companion DLLs and carry a cross-domain canonical to `https://erenshor.compendiums.org/map`. |
| Legacy host, any runtime resource needed by `/map` | Serve directly from the shared build with same-origin `200`, including `/service-worker.js`, Svelte assets/data, SQLite, tiles, images, fonts, and other non-HTML resources. Never redirect these resources to the new host. |
| Legacy host, exact root `/<mapKey>` where `mapKey` is an exact, case-sensitive `Object.keys(MAPS)` key | `301` to `https://erenshor.compendiums.org/maps/<mapKey>`, preserving the complete query string byte-for-byte. |
| Legacy host, another real HTML document (`/`, `/zone-maps`, `/adventure-guide`, `/mod`, `/spreadsheet`, and `/maps/<key>`) | `301` to the same path on `https://erenshor.compendiums.org`, preserving path casing and the complete query string. `/map` is the explicit `200` exception above. |
| Legacy host, `/google279cf61d0b725839.html` | Serve the existing token body directly with `200` and `text/html`; do not redirect it. |
| Either host, unknown path, malformed encoding, case-variant root key, or reserved `/zones/{slug}` | Deliberate `404`; never redirect to home or guess a map. |
| New host, exact root `/<mapKey>` | `404`; canonical map pages exist at `/maps/<mapKey>`, not at root. |

The static-resource allowlist must be explicit enough to keep runtime resources
on the legacy host, but must not turn into a wildcard for unknown paths. The
same build must return the same resource bytes on both hosts. Test both hosts,
representative casing, encoded values, query strings, and trailing-slash
variants.

## Redirect, canonical, and discovery contract

These rules are the release contract for the Worker, static build, and tests:

- The canonical origin is `https://erenshor.compendiums.org`. Every canonical
  URL, `og:url`, JSON-LD URL/`@id`, sitemap URL, robots output, and generated
  wiki/Sheets map URL uses it. The legacy origin is transport compatibility,
  not a canonical or backlink destination.
- A legacy request whose path is exactly `/<mapKey>`, with `mapKey` an exact
  case-sensitive key from `Object.keys(MAPS)`, receives a `301` to
  `https://erenshor.compendiums.org/maps/<mapKey>`. Do not lowercase,
  decode/re-encode, or otherwise rewrite the key. Preserve the query string
  byte-for-byte, including encoded values, `sel`, `layers`, `marker`, and
  view/debug state. Verify the existing trailing-slash policy explicitly; do
  not introduce a second canonical spelling.
- A legacy real HTML document other than `/map` receives a `301` to the same
  path on the new host. This includes `/`, `/zone-maps`, `/adventure-guide`,
  `/mod`, `/spreadsheet`, and already-migrated `/maps/<key>` pages. It does not
  include static files, runtime resources, the legacy token, unknown paths, or
  reserved `/zones/{slug}` paths.
- Legacy `/map` is a direct `200`, not a redirect: its HTML may be the shared
  build, but its canonical metadata must be the cross-domain URL
  `https://erenshor.compendiums.org/map`. It is absent from sitemaps and
  generated/internal links, and it must not emit `noindex`. The new host's
  `/map` remains a directly usable `200` world-map page with the same canonical
  URL.
- New-host zone pages are canonical only at `/maps/<exact-mapKey>`. The route
  registry, sitemap, JSON-LD breadcrumbs, and internal links all use that
  spelling. Verify the trailing-slash rule rather than relying on Wrangler or
  the static adapter to normalize it.
- The legacy Google verification path remains a direct `200` with the expected
  token body and `text/html` content type. The new Search Console Domain
  property uses DNS verification and requires no new static file. Keep the
  legacy token unchanged while the old property remains in transition.
- No redirect claims to preserve a URL fragment. Preserve query strings only.

## Tasks

### Task 1: URL restructure (ship with the domain migration so URLs churn once)

**Repository route, SEO, and link preparation (before any cutover)**

- [x] Move the prerendered zone route from `src/maps/src/routes/[mapName]/` to
  `src/maps/src/routes/maps/[mapName]/`, carrying both `+page.ts` and
  `+page.svelte` forward. Keep `entries()` sourced from `Object.keys(MAPS)`;
  preserve exact, case-sensitive map keys and the deliberate unknown-route
  `404` behavior from the static adapter.
- [x] Update `src/maps/src/routes/maps/[mapName]/+page.svelte` so the `Seo`
  caller, zone `zoneMapJsonLd` URL, and breadcrumb path use
  `/maps/${mapName}`. Check every path passed to `Seo.svelte`; it remains the
  shared emitter for canonical, `og:url`, OG image, and JSON-LD tags.
- [x] Update `src/maps/src/lib/seo/jsonld.ts` so `zoneMapJsonLd` constructs
  `/maps/<zoneKey>`, and update
  `src/maps/src/routes/sitemap.xml/+server.ts` so `zoneRoutes` emits
  `/maps/<key>` while `/map`, `/zone-maps`, `/adventure-guide`, `/mod`, and
  `/spreadsheet` remain unchanged. Keep `/map` out of sitemap routes.
- [x] Fix discovered internal-link surfaces: make the zone card link in
  `src/maps/src/routes/(app)/zone-maps/+page.svelte` an explicit
  `/maps/${mapName}` (not a relative `${mapName}`), and change the Stowaway
  example in `src/maps/src/routes/(app)/mod/+page.svelte` to
  `/maps/Stowaway`. Search the rest of `src/maps` for root-slug links and
  migrate every map-page link without changing the separate `/map` world-map
  path.
- [x] Update focused assertions in
  `src/maps/src/routes/sitemap.xml/sitemap.test.ts` (absolute custom-origin
  prefix plus `/maps/<key>` route shape) and
  `src/maps/src/lib/seo/site.test.ts` (new origin and zone path while
  retaining query/hash stripping behavior). Add a Worker/redirect-matrix test
  for both hosts covering exact keys, query preservation, runtime resources,
  the legacy token, case variants, reserved paths, canonical metadata,
  no-`noindex` `/map`, and unknown-path `404` behavior.
- [x] Change both independent origin sources: set `SITE_URL` in
  `src/maps/src/lib/seo/site.ts` to
  `https://erenshor.compendiums.org`, and set the default
  `MapsConfig.base_url` in `src/erenshor/infrastructure/config/schema.py` to
  the same origin. Verify Sheets `map_marker_url` keeps its
  `/map?sel=marker:<stable_key>` path and that wiki/Sheets generation no
  longer receives the old host.

**Maintained references and compatibility surfaces**

- [x] Update the embedded in-game/mod origin and allowlist in
  `src/mods/InteractiveMapCompanion/src/Overlay/MapOverlay.cs` and
  `BrowserManager.cs` so newly built companions permit the new origin while
  retaining the legacy origin needed by shipped DLLs. Update its `README.md`
  and `thunderstore/README.md` links, including the GIF asset and `/map`
  selector examples. Do not make this migration depend on releasing a new
  companion DLL; do not use user-agent sniffing in the Worker.
- [x] Update `src/mods/AdventureGuide/vault/README.md` absolute map image and
  marker/navigation assets, the root `README.md`, and the old-host reference
  in `docs/architecture-analysis.md`.
- [x] Prepare both wiki map-link implementations without prematurely forcing the
  broader Cargo/Lua cutover: update the future Lua-backed Character and Zone
  modules/templates plus their tests, and keep the production-compatible direct
  `Template:MapLink` source on the canonical origin. Preserve `/map` selector
  parameters; full Cargo ownership remains gated by the wiki cutover plans.

### Task 2: Shared Worker and static-build preparation (repository work)

- [x] Convert `src/maps/wrangler.jsonc` to the single retained Worker
  configuration: `name: "erenshor-maps"`, `workers_dev: true`, one Worker
  entrypoint, `assets.directory: "./build"`, `assets.binding: "ASSETS"`, and
  `assets.run_worker_first` enabled. Bind the custom domain
  `erenshor.compendiums.org` through its custom-domain route while keeping the
  workers.dev route. Do not add a second config, entrypoint, or deployment
  target.
- [x] Add the Worker entrypoint (in the existing `src/maps` source layout) to
  dispatch by hostname and path according to the matrix above, then delegate
  eligible requests to `env.ASSETS.fetch(request)`. Ensure `/map` and all
  legacy runtime resources stay direct `200` responses; perform HTML redirects,
  exact root-map-key redirects, token serving, and deliberate `404`s before
  asset fallback. The implementation must not inspect `User-Agent`.
- [x] Keep one shared static build for both hosts. Ensure the Worker entrypoint
  and `ASSETS` binding do not create host-specific copies, rewrite resource
  origins, or redirect service-worker/data requests. Verify `/service-worker.js`,
  `__data.json`, Svelte assets, SQLite, tiles, images, fonts, and other
  non-HTML runtime resources are same-origin `200` on the legacy host.
- [x] Close the build-freshness gap: `.build-info.json` currently hashes code,
  selected config/data, mods, and tiles but not all Worker/Wrangler
  infrastructure inputs. Include the Worker entrypoint, Wrangler config,
  route/SEO inputs, and every production input that can affect the deployed
  asset or response behavior, or add an equivalent invalidation precondition.
  Require a clean `maps build` after route, SEO, data, or Worker-config edits
  and immediately before deployment; a previously valid build is insufficient.
- [x] Reconcile the Wrangler package and lockfile versions
  (`src/maps/package.json` declares `^4.59.2` while `pnpm-lock.yaml` resolves
  `4.54.0`). Pin a deliberate reviewed version and lock it so the single
  Worker deploy uses a reproducible CLI.
- [x] Confirm the new Search Console Domain property uses DNS verification and
  requires no new static artifact. Keep the existing legacy verification file
  and Worker response unchanged while the old property remains in transition.

### Task 3: Manual Cloudflare, GSC, wiki, and external-link gates

These are release gates, not repository-code substitutes. No deployment is
authorized until each applicable checkbox is explicitly completed by the
responsible operator.

- [x] Confirm Cloudflare account/API-token access, the correct account and
  `compendiums.org` zone, permission to attach custom domains, and the
  existing `erenshor-maps` Worker and workers.dev route. Certificate and DNS
  readiness remain deployment gates below.
- [x] In Google Search Console, confirm the DNS-verified custom-domain property
  exists under the same owner account. Keep access to the old property and
  legacy token until redirect and indexing verification is complete. Do not
  run Change of Address yet.
- [x] Confirm wiki-admin ownership of `Template:MapLink` and its transclusions,
  permission to deploy the Lua/template/testcase changes, and the maintainer
  who can update the Steam guide and other externally maintained links. These
  are release gates, not assumptions encoded in repository code.

### Task 4: Ordered deployment and maintained-link cutover

- [x] Build from a clean checkout/input set with the new route, origins, links,
  existing legacy token, lockfile, Worker entrypoint, Wrangler config, and
  freshness inputs.
  Run maps freshness and authentication preconditions against the one
  explicitly selected Worker configuration. Record build provenance and the
  prior Worker version for rollback.
- [x] Deploy the retained `erenshor-maps` Worker with its shared build while
  keeping `workers_dev: true`; attach/activate the custom-domain route only
  after Cloudflare reports certificate and DNS readiness. There is no separate
  redirect deployment. Do not proceed while the custom host serves an old
  build or an unintended workers.dev origin.
- [x] Verify the new host before changing any external backlink: load `/`,
  `/map`, a representative `/maps/<exact-key>`, `/zone-maps`,
  `/adventure-guide`, `/mod`, `/spreadsheet`, representative static assets,
  and sitemap/robots endpoints over HTTPS. Inspect canonical, `og:url`,
  JSON-LD, and sitemap origins; confirm no root-zone links, old-host outputs,
  or mixed-origin runtime requests.
- [x] Verify the legacy host from the same Worker before external cutover:
  load `/map` and its service worker, `__data.json`, Svelte assets, SQLite,
  tiles, images, fonts, and representative other runtime resources as direct
  same-origin `200`s; verify old token `200`; verify exact root-key and
  same-path HTML `301`s; and verify unknown/reserved paths are `404`s.
- [x] After both hosts passed verification, submit the new-host sitemap from the
  DNS-verified GSC property and complete Change of Address from the old property
  to the new property. Keep the old property and legacy token accessible during
  the transition and monitor indexing/redirect errors.
- [x] Cut over production wiki map backlinks without forcing the unfinished
  Cargo/Lua template migration: retain the direct `Template:MapLink`
  implementation, point character and zone map links at the custom origin, and
  verify representative character, zone, and direct MapLink renders. Update the
  Steam guide and other externally maintained links after the wiki. Repository-
  controlled mod, Adventure Guide, README, architecture, and compendiums.org
  links already use the canonical origin.

### Task 5: Verification and rollback gates

- [x] Run a final two-host matrix: new-host application documents and
  `/maps/<key>` are `200`; legacy `/map` and every documented runtime resource
  are same-origin `200`; exact case-sensitive root `MAPS` keys alone redirect
  to `/maps/<key>`; encoded selector/query strings survive unchanged;
  same-path HTML redirects preserve casing and query; legacy token is direct
  `200`; `/guide`, `/zones/*`, malformed/case-variant keys, unknown paths, and
  unknown assets are deliberate `404`s; no redirect loops exist; and no
  destination points back to the legacy host.
- [x] Re-run the new-host surface check after wiki and external-link updates:
  canonical/OG/JSON-LD/sitemap/robots use the custom origin; representative
  prerendered maps use `/maps/<key>` canonicals; generated wiki and Sheets URLs
  use the new `MapsConfig.base_url`; BrowserManager allows the new host while
  retaining the legacy companion source; and representative internal, mod,
  documentation, wiki, and compendiums.org links resolve.
- [x] Custom-domain activation, certificate, and DNS verification remained
  healthy through cutover, so the pre-GSC rollback path was not triggered.
- [x] Both host-routing matrices passed after the final deployment: queries and
  the legacy token remain intact, overlay resources stay same-origin, and no
  redirect loop or rollback trigger was observed.
- [x] GSC, wiki, Steam, and other controlled backlink gates completed; no
  external-gate pause was required. The legacy token and old-host overlay
  resources remain available for the transition.

## Risks and release gates

- **Legacy companion compatibility:** shipped DLLs reject full-document
  navigation to another host and hardcode the workers.dev `/map` URL. The
  legacy `/map` document plus service worker, `__data.json`, Svelte assets,
  SQLite, tiles, images, fonts, and all other runtime resources must remain
  same-origin `200`s. Host-aware routing, not user-agent sniffing, is the
  mitigation.
- **Static-resource allowlist drift:** redirecting every legacy request can
  break overlays or turn unknown paths into misleading pages. Keep an explicit
  runtime-resource/static allowlist, test it against the shared build, and
  return `404` for unknown and reserved paths.
- **Stale build inputs:** Worker config and entrypoint changes can evade the
  current `.build-info.json` inputs. Hash every deployed behavior input and
  require a clean build immediately before deployment.
- **Exact case-sensitive zone keys:** `MAPS` keys are the only root redirect
  allowlist. Lowercasing, decoding, or guessing a slug can create wrong
  redirects; tests must cover camel-case keys, variants, encodings, and
  trailing-slash cases.
- **Custom-domain readiness:** Cloudflare account, route, certificate, and DNS
  permissions can block the release. Keep workers.dev serving the known-good
  version until the custom host is healthy.
- **SEO split-brain:** `SITE_URL` and `MapsConfig.base_url` are independent.
  Both sources, every canonical/JSON-LD/sitemap/robots surface, and controlled
  links must be inspected for one canonical origin before Change of Address.
  Legacy `/map` is canonicalized cross-domain but remains indexable: it is not
  in sitemaps/internal links and must not use `noindex`.
- **External-admin dependencies:** GSC property access, Change of Address,
  wiki template deployment, Steam guide ownership, and other
  maintained links are manual gates. Keep each explicit and preserve the old
  verification/compatibility paths until all are green.
- **Wrangler lock drift:** package and lockfile versions currently differ. A
  version change during cutover can alter config or deploy behavior; reconcile
  and review the lock before deploying the retained Worker.

### Task 6: Independent backlog (not migration work)

- **Deferred:** a low-value `404` `noindex` page (spec I3) would need an adapter
  fallback plus Wrangler `not_found_handling`; it remains limited to deliberate
  404 documents and must never affect legacy `/map`.
- **Deferred to its own draft spec:** the crawlable textual content layer at
  `/zones/{slug}` remains separate from interactive `/maps/{slug}`.

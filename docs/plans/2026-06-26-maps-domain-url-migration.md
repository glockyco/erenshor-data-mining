---
title: Maps Domain Migration & URL Restructure
type: plan
status: active
created: 2026-06-26
parent: 2026-07-09-erenshor-planning-overview
---

# Maps Domain Migration & URL Restructure

This plan owns the one coordinated release that moves the maps site to
`erenshor.compendiums.org` and moves interactive zone pages to
`/maps/{slug}`. The migration has not begun: production still uses the
`erenshor-maps.wowmuch1.workers.dev` origin, the production Worker is still
named `erenshor-maps`, and root-level zone routes are still the repository
source of truth. Complete repository preparation and manual gates before any
production deployment. The independent backlog at the end is not part of this
cutover.

## Decisions (locked)

- **Domain: `erenshor.compendiums.org`.** We own `compendiums.org`; the sister
  project uses `ancient-kingdoms.compendiums.org`. `erenshor.compendiums.org` is
  shorter than `erenshor-maps.compendiums.org` and fits the whole site (maps,
  spreadsheet, mods, Adventure Guide), not maps alone. Pointing the subdomain at
  the Worker is Cloudflare config (a custom-domain route), not a registration.
- **Interactive zone maps move to `/maps/{slug}`.** `/zones/{slug}` stays
  reserved for the future textual reference layer. Do the URL move with the
  domain migration so URLs change only once.
- **Complement the wiki, don't replicate it.** The wiki's enemy and zone pages
  cross-link to our map and drive most of its traffic, so repointing that map-
  link template is the highest-value backlink task in the migration.
- **Dropped, will not do:** `Dataset` JSON-LD, per-page OG images (spec I5), the
  external-link `rel` audit (spec N5), and the optional `@graph` consolidation
  (spec I4).

## Redirect and canonical contract

These rules are the release contract for both Worker code and its tests:

- The new canonical origin is `https://erenshor.compendiums.org`. Every
  canonical URL, `og:url`, JSON-LD URL/`@id`, sitemap URL, robots output, and
  generated wiki/Sheets map URL must use it. The legacy origin is transport
  only, not a canonical or backlink destination.
- A request on the legacy host whose path is exactly `/<mapKey>`, where
  `mapKey` is an exact, case-sensitive key from `Object.keys(MAPS)`, receives a
  `301` to `https://erenshor.compendiums.org/maps/<mapKey>`. Preserve the query
  string byte-for-byte (including encoded values, `sel`, `layers`, `marker`, and
  view/debug state). Do not lowercase, decode/re-encode, or otherwise rewrite a
  key. Preserve the existing trailing-slash policy; do not invent a second
  canonical spelling.
- The legacy Worker returns `301` to the same path on the new origin for `/`,
  `/map`, `/zone-maps`, `/adventure-guide`, `/mod`, `/spreadsheet`, and files
  present in the deployed static manifest (including the `/maps/`, `/items/`,
  `/tiles/`, `/mods/`, and `/icons/` asset prefixes plus named root assets),
  preserving the complete query string and path casing. The manifest-backed
  allowlist must not become a wildcard for unknown paths. It must not translate
  `/zones/{slug}`: that prefix is reserved for a future textual layer.
- Unknown paths, `/guide`, reserved `/zones/{slug}` paths, and root-looking
  strings that are not exact `MAPS` keys are not sent to the home page or a
  guessed map. Return a deliberate `404` (or the explicitly tested static
  fallback) and keep this behavior identical for case variants and malformed
  encodings. HTTP requests do not carry fragments, so no redirect may claim to
  preserve a URL fragment.
- The legacy Google verification path (the current
  `/google279cf61d0b725839.html` token path) is served directly by the legacy
  Worker with the expected token body, `200`, and `text/html` content type; it
  is not redirected. The new property's token is served from the new host's
  static assets.
- New-host zone pages are canonical only at `/maps/<exact-mapKey>`. The route
  registry, sitemap, JSON-LD breadcrumbs, and internal links all use that
  spelling. Verify the trailing-slash rule explicitly rather than relying on
  Wrangler or the static adapter to normalize it.

## Tasks

### Task 1: URL restructure (ship with the domain migration so URLs churn once)

#### Repository route, SEO, and link preparation (before any cutover)

- [ ] Move the prerendered zone route from `src/maps/src/routes/[mapName]/` to
  `src/maps/src/routes/maps/[mapName]/`, carrying both `+page.ts` and
  `+page.svelte` forward. Keep `entries()` sourced from `Object.keys(MAPS)` and
  preserve exact, case-sensitive map keys; retain the deliberate unknown-route
  404 behavior from the static adapter.
- [ ] Update `src/maps/src/routes/maps/[mapName]/+page.svelte` so the `Seo`
  caller, zone `zoneMapJsonLd` URL, and breadcrumb path use
  `/maps/${mapName}`. Check every path passed to `Seo.svelte`; the component
  remains the shared emitter for canonical, `og:url`, OG image, and JSON-LD
  tags.
- [ ] Update `src/maps/src/lib/seo/jsonld.ts` so `zoneMapJsonLd` constructs
  `/maps/<zoneKey>`, and update
  `src/maps/src/routes/sitemap.xml/+server.ts` so `zoneRoutes` emits
  `/maps/<key>` while `/map`, `/zone-maps`, `/adventure-guide`, `/mod`, and
  `/spreadsheet` remain unchanged.
- [ ] Fix the discovered internal-link surfaces: make the zone card link in
  `src/maps/src/routes/(app)/zone-maps/+page.svelte` an explicit
  `/maps/${mapName}` (not a relative `${mapName}`), and change the Stowaway
  example in `src/maps/src/routes/(app)/mod/+page.svelte` to `/maps/Stowaway`.
  Search the rest of `src/maps` for root-slug links and migrate every map-page
  link without changing the separate `/map` world-map path.
- [ ] Update focused assertions in
  `src/maps/src/routes/sitemap.xml/sitemap.test.ts` (absolute custom-origin
  prefix plus `/maps/<key>` route shape) and
  `src/maps/src/lib/seo/site.test.ts` (new origin and zone path while
  retaining query/hash stripping behavior). Add a redirect-matrix test for
  exact known keys, query preservation, static paths, the legacy token, case
  variants, reserved paths, and unknown-path `404` behavior.
- [ ] Change both independent origin sources: set `SITE_URL` in
  `src/maps/src/lib/seo/site.ts` to `https://erenshor.compendiums.org`, and set
  the default `MapsConfig.base_url` in
  `src/erenshor/infrastructure/config/schema.py` to the same origin. Verify
  that Sheets `map_marker_url` keeps its `/map?sel=marker:<stable_key>` path
  and that wiki/Sheets generation no longer receives the old host.

#### Maintained references and compatibility surfaces

- [ ] Update the embedded in-game/mod origin and allowlist in
  `src/mods/InteractiveMapCompanion/src/Overlay/MapOverlay.cs` and
  `BrowserManager.cs`; permit the new origin and explicitly decide whether the
  legacy origin is allowed only during the transition. Update its
  `README.md` and `thunderstore/README.md` links, including the GIF asset and
  `/map` selector examples.
- [ ] Update `src/mods/AdventureGuide/vault/README.md` absolute map image and
  marker/navigation assets, the root `README.md`, and the old-host reference in
  `docs/architecture-analysis.md`.
- [ ] Update the repo-owned wiki MapLink surface as one atomic set:
  `wiki/modules/Erenshor/Character.lua`, `wiki/modules/Erenshor/Zone.lua`,
  `wiki/templates/Character.wiki`, `wiki/templates/Template_MapLink.txt`, and
  `wiki/modules/Erenshor/Zone/testcases.lua`. Preserve selector parameters and
  update the expected URL strings. Confirm the `Template:MapLink` ownership
  gate and its approximately 40 transclusions before requesting wiki admin
  deployment.

### Task 2: Domain migration (C1 — blocked on a go-ahead; no registration needed)

#### Repository infrastructure preparation (after route prep, before manual gates)

- [ ] Split production and redirect infrastructure explicitly. Rename the
  production Worker from `erenshor-maps` to an available name such as
  `erenshor-maps-site`; set `workers_dev: false`, bind the production static
  assets to the `erenshor.compendiums.org` custom domain, and keep its asset
  directory on the fresh `src/maps/build` output.
- [ ] Add `src/maps/redirect-worker.ts` and the separate
  `src/maps/wrangler.redirect.jsonc` config (kept distinct from production
  `wrangler.jsonc`) for a redirect-only Worker that keeps the name
  `erenshor-maps` for the legacy `erenshor-maps.wowmuch1.workers.dev` host. It
  must implement the redirect and token contract above and must not share the
  production static-assets deployment target. Keep production and redirect config files selectable
  without editing one another.
- [ ] Make deploy target selection explicit in
  `src/erenshor/cli/commands/maps.py`: production deploy and redirect deploy
  must pass the intended Wrangler config/project (for example, an explicit
  `--config`) rather than relying on whichever `wrangler.jsonc` happens to be
  the working-directory default. Update dry-run output and preconditions to
  name the selected Worker/config and reject an ambiguous target; preserve a
  separate command path for the redirect Worker.
- [ ] Close the build-freshness gap: `.build-info.json` currently hashes code,
  selected config/data, mods, and tiles but not Wrangler infrastructure config.
  Include every production input that can affect the deployed asset/config, or
  add an equivalent precondition that invalidates the artifact after those
  files change. Regardless of implementation, require a clean `maps build`
  after all route, SEO, data, and production-config edits and before production
  deploy; a previously valid build is not sufficient.
- [ ] Reconcile the Wrangler package/lockfile versions before deployment
  (`src/maps/package.json` declares `^4.59.2` while `pnpm-lock.yaml` resolves
  `4.54.0`). Pin a deliberate version and lock it so production and redirect
  deploys use the reviewed, reproducible CLI.
- [ ] Obtain the new property's Google token through the manual GSC gate below,
  then replace the old static verification artifact with that exact token in
  the new-host build. Keep the legacy token available to the redirect Worker;
  never fabricate a token or leave a placeholder.

#### Manual Cloudflare and external-admin gates (no repository checkbox substitutes)

- [ ] Confirm Cloudflare account/API-token access, the correct account and
  `compendiums.org` zone, permission to create custom domains, certificate/DNS
  readiness for `erenshor.compendiums.org`, and availability of the renamed
  production Worker name. Resolve any existing `erenshor-maps-site` collision
  before touching the old Worker.
- [ ] In Google Search Console, create the new custom-domain property, obtain
  its verification token, and provide that token for the repository static
  file. Keep access to the old property and its legacy token until redirect
  verification is complete. Do not run Change of Address yet.
- [ ] Confirm wiki admin ownership for `Template:MapLink` and its transclusions,
  and permission to deploy the Lua/template/testcase changes. Confirm the
  maintainer who can update the Steam guide and any other externally maintained
  links. These are release gates, not assumptions encoded in repository code.

#### Ordered deployment: custom domain first, redirect second

- [ ] Build from a clean checkout/input set with the new route, origins, links,
  token, lockfile, and infrastructure-hash inputs; run the maps freshness and
  authentication preconditions against the explicitly selected production
  config. Record the build provenance used for rollback.
- [ ] Deploy the renamed production Worker with its custom-domain binding
  **before** deploying any redirect Worker. Confirm Cloudflare reports the
  custom domain active and its certificate/DNS is healthy; do not proceed while
  the new host is serving an old build or a workers.dev origin.
- [ ] Verify the new host before changing the legacy host: load `/`, `/map`, a
  representative `/maps/<exact-key>`, `/zone-maps`, `/adventure-guide`,
  `/mod`, `/spreadsheet`, representative static assets, and the sitemap/robots
  endpoints over HTTPS. Inspect canonical, `og:url`, JSON-LD, and sitemap
  origins and confirm there are no root-zone links or mixed old-host outputs.
- [ ] Only after the custom-domain checks pass, deploy the separate
  `erenshor-maps` redirect Worker using its explicit redirect config. Verify
  representative known-root redirects, static-path redirects, query and
  trailing-slash behavior, unknown/reserved-path `404`s, no redirect loops, and
  direct `200` serving of the legacy GSC token.

#### GSC, wiki, Steam, and maintained-link cutover

- [ ] After both hosts pass verification, verify the new GSC property with its
  token, submit the new-host sitemap, and run Change of Address from the old
  property to the new property. Keep the old token route and old property
  accessible for the transition and monitor indexing/redirect errors.
- [ ] Deploy the repo-owned wiki MapLink/Lua/template update first among
  controlled backlinks, preserving `/map` selector behavior and checking a
  character link, a zone link, and a generated zone page. Then update the
  Steam guide and other externally maintained links. Repository-controlled mod,
  Adventure Guide, README, and architecture links must already point to the new
  origin before this step.

#### Verification and rollback gates

- [ ] Run a final redirect matrix against the deployed legacy host: exact
  case-sensitive `MAPS` keys map only to `/maps/<key>`; encoded selector/query
  strings survive unchanged; `/map`, static assets, and the documented app
  paths retain their paths; `/guide`, `/zones/*`, malformed/case-variant keys,
  and unknown paths do not redirect to home or a guessed map; the legacy token
  remains a direct `200`; and no destination points back to the legacy host.
- [ ] Re-run the new-host surface check after wiki and external-link updates:
  canonical/OG/JSON-LD/sitemap/robots all use the custom origin, every
  prerendered map has exactly one `/maps/<key>` canonical, generated wiki and
  Sheets URLs use the new `MapsConfig.base_url`, BrowserManager allows the new
  host, and representative internal/mod/docs links resolve.
- [ ] If custom-domain deployment or certificate verification fails, stop
  before redirect deployment; restore the recorded prior production Worker
  version/config and its legacy binding, and remove or disable the unverified
  custom-domain binding. Do not run Change of Address or update external links.
- [ ] If the redirect Worker misroutes, drops queries, breaks the token, or
  loops, roll back that Worker independently to the last known redirect config
  (or temporarily restore the recorded prior legacy-host production binding),
  keep the verified custom host isolated, and defer GSC/link cutover until the
  matrix passes again. Preserve the prior production build and both Wrangler
  configs as rollback artifacts.

## Risks and release gates

- **Worker-name collision:** the old name must remain available for the
  redirect Worker while the production Worker is renamed. Cloudflare account,
  zone, name, and custom-domain checks are blocking gates; never let an
  ambiguous CLI target deploy.
- **Stale-build hashing gap:** Wrangler config is not currently part of
  `.build-info.json`; an apparently fresh artifact can contain old deployment
  assumptions. Include the config in freshness inputs and require a clean build
  immediately before production deployment.
- **Unknown/static path behavior:** a catch-all redirect can turn typos,
  `/guide`, reserved `/zones/{slug}`, or unknown assets into misleading map/home
  pages. The exact known-static/known-zone/unknown-404 matrix above is a release
  gate, including encoded and trailing-slash cases.
- **Exact case-sensitive zone keys:** `MAPS` keys are the allowlist. Lowercasing,
  decoding, or guessing a slug can create wrong redirects or 404s; tests must
  cover representative camel-case keys and case variants.
- **Allowlist breakage:** `BrowserManager` can reject the new origin even when
  ordinary browsers work. Update and exercise the allowlist, and specify the
  legacy-origin transition policy before publishing the mod.
- **SEO split-brain:** changing only `SITE_URL` leaves wiki/Sheets outputs on
  the old host because `MapsConfig.base_url` is independent. Both sources,
  every canonical/JSON-LD/sitemap surface, and controlled links must be
  inspected for a single origin before Change of Address.
- **External admin dependencies:** Cloudflare certificate/DNS and Worker
  permissions, GSC token/property access, wiki template deployment, and Steam
  guide ownership can block an otherwise complete repository change. Keep each
  manual gate explicit and preserve the old verification/redirect path until
  all are green.
- **Wrangler lock drift:** the package and lockfile currently resolve different
  Wrangler versions. A version change during cutover can alter config or deploy
  behavior; reconcile and review the lock before either Worker is deployed.

### Task 3: Backlog (independent of the migration)

- [ ] (low value) 404 `noindex` page (spec I3): needs an adapter `fallback` plus
  a Wrangler `not_found_handling` change to actually be served. Do not block the
  domain/URL cutover on it.
- [ ] (future, own spec) Crawlable textual content layer at
  `/zones/{slug}`. It remains separate from the interactive `/maps/{slug}`
  route and must not be folded into this migration.

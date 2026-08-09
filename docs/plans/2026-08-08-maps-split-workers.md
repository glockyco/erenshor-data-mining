---
title: Split Canonical and Legacy Erenshor Map Workers
type: plan
status: draft
created: 2026-08-08
parent: 2026-06-26-maps-domain-url-migration
superseded_by:
archived:
---

# Split Canonical and Legacy Erenshor Map Workers

**Goal:** Stop canonical static traffic on `erenshor.compendiums.org` from
invoking JavaScript while preserving the complete same-origin contract required
by shipped InteractiveMapCompanion versions at
`erenshor-maps.wowmuch1.workers.dev`.

**Scope:** Split the current dual-host `erenshor-maps` deployment into a
canonical static-first Worker and a retained legacy compatibility Worker, teach
the repository-owned maps deploy command to publish both from one build, migrate
the custom domain without interrupting the legacy hostname, and verify the
result through Cloudflare configuration, live request tails, and both browser
surfaces.

**Non-goals:** Do not change map URLs, canonical metadata, companion protocols,
the service worker's offline tile policy, generated assets, or the contents of
the static build. The eager service-worker precache remains a separate
performance concern. This plan removes its Worker-invocation multiplier without
changing its offline behavior.
`erenshor-logs` is an unrelated service and remains unchanged.

## Why this is necessary

Cloudflare account analytics for the rolling window from 2026-08-07 18:20 UTC
to 2026-08-08 18:20 UTC reported 461,676 Worker invocations. `erenshor-maps`
produced 460,069 of them, or 99.652 percent. It also produced 460,043
subrequests and zero errors. The deployed version has:

```json
{
  "assets": {
    "raw_run_worker_first": true,
    "serve_directly": false,
    "html_handling": "auto-trailing-slash",
    "not_found_handling": "none"
  }
}
```

The canonical-host branch of `src/maps/src/worker.ts` immediately calls
`env.ASSETS.fetch(request)`. Every canonical HTML, JavaScript, stylesheet, font,
database, image, and tile request therefore invokes the Worker only to issue one
asset-binding subrequest.

A 120-second live tail captured 608 canonical requests. The sample contained
512 tile requests, 85 Svelte assets, 6 service-worker requests, 2 HTML requests,
2 SQLite requests, and 1 item image. Of those, 604 returned `304 Not Modified`.
The 512 tile requests were two complete service-worker install waves. Each wave
fetched the tile manifest and the 255 tiles listed at zoom levels `-4` through
`-1`. Direct asset serving will keep those HTTP requests but prevent them from
becoming Worker invocations.

Cloudflare serves a matching asset before invoking a Worker unless
`assets.run_worker_first` says otherwise. It also supports a path array for the
few routes that must run the Worker first. References:

- <https://developers.cloudflare.com/workers/static-assets/routing/worker-script/>
- <https://developers.cloudflare.com/workers/static-assets/billing-and-limitations/>
- <https://developers.cloudflare.com/workers/configuration/routing/custom-domains/>

## Ancient Kingdoms precedent

`ancient-kingdoms-mods/website` already uses the service split this plan adopts:

| Service | Public entry | Asset policy | Responsibility |
| --- | --- | --- | --- |
| `ancient-kingdoms-compendium-site` | `ancient-kingdoms.compendiums.org` | Static assets served directly, `workers_dev = false` | Canonical application |
| `ancient-kingdoms-compendium` | `ancient-kingdoms-compendium.wowmuch1.workers.dev` | No asset bundle | Legacy redirects, verification token, and two proxied favicons |

Its default `wrangler.toml` owns the canonical site. Its
`wrangler.redirect.toml` retains the old Worker name because that name determines
the permanent `workers.dev` hostname.

Erenshor needs the same service boundary with one important difference. Ancient
Kingdoms can redirect almost every legacy request. Erenshor cannot. Shipped
companion DLLs hardcode the legacy `/map` document and reject full-document
navigation to another host. The legacy Worker must therefore retain the shared
asset bundle and serve `/map`, its service worker, Svelte runtime, SQLite files,
tiles, images, icons, and fonts as same-origin responses. The split is canonical
site versus compatibility site, not canonical site versus redirect-only shim.

## Target topology

```mermaid
flowchart LR
    C[erenshor.compendiums.org] --> S[erenshor-maps-site]
    S --> SA[shared build assets\nasset-first]
    S --> API[/api/game-version Worker handler]

    L[erenshor-maps.wowmuch1.workers.dev] --> W[erenshor-maps]
    W --> LA[same shared build assets\nWorker-first compatibility routing]
    W --> R[legacy redirects and aliases]
```

### Canonical service: `erenshor-maps-site`

- Own `erenshor.compendiums.org` as a Custom Domain.
- Set `workers_dev` to `false`.
- Upload `./build` through the `ASSETS` binding.
- Set `assets.run_worker_first` to the selective array
  `["/api/game-version"]`, not `true`. Measured against real `workerd`, this is
  behaviourally identical to omitting the setting, except that it prevents a
  static file from ever shadowing the dynamic route.
- Keep `html_handling = "auto-trailing-slash"` and
  `not_found_handling = "none"` initially. This preserves the current asset
  matching and deliberate 404 behavior. A custom static 404 can be considered
  separately.
- Handle `/api/game-version` with the existing `handleGameVersion` function.
- Delegate any unexpected invocation to `ASSETS.fetch` so unmatched paths retain
  the current 404 response instead of acquiring a new fallback.
- Contain no hostname-dependent redirect or compatibility logic.

A matching canonical asset must bypass the Worker. `/api/game-version` must
invoke it even if a file with that name is accidentally introduced later.
Unknown asset misses may still invoke the Worker and return an asset 404. They
are not the source of the measured volume and retaining that behavior keeps this
cutover narrow.

### Legacy service: `erenshor-maps`

- Retain the exact service name so
  `erenshor-maps.wowmuch1.workers.dev` cannot change.
- Keep `workers_dev = true`.
- Upload the same `./build` directory through its own `ASSETS` binding.
- Keep `assets.run_worker_first = true`, because hostname and response-content
  decisions are the purpose of this compatibility Worker.
- Preserve the current host-aware handler, including its transparent canonical
  branch. The branch is normally unreachable after cutover but makes the
  existing service a valid immediate rollback target for the custom domain.
- Keep the legacy Google verification token response unchanged.
- Keep `/map` and `/map/` on the legacy origin.
- Keep all runtime assets on the legacy origin.
- Keep exact, case-sensitive root map-key redirects.
- Keep real legacy HTML redirects, sitemap redirect behavior, query strings,
  and deliberate 404s unchanged.
- Keep `/api/game-version` available on the legacy origin.

Duplicating the asset deployment is intentional. It avoids making shipped mods
dependent on a Worker-to-Worker proxy, preserves the current availability and
response semantics, and guarantees that a rollback can reattach the custom
domain to `erenshor-maps` without rebuilding or changing code. Both deployments
consume one repository build, so there remains one source artifact even though
Cloudflare registers it with two services.

## Response contract

The split is complete only if this matrix remains true:

| Host and request | Required result | Worker invocation |
| --- | --- | --- |
| Canonical existing HTML or `/maps/{exact-key}` | Shared build response, normally `200` | No |
| Canonical `/map` | Shared world-map document, `200` | No |
| Canonical `/map/`, `/maps/{key}/` | Same-origin relative `307` to the non-slash path, then `200` | No |
| Canonical runtime asset | Shared asset response, including normal `304` handling | No |
| Canonical `/api/game-version` | Existing JSON contract and cache headers | Yes, `erenshor-maps-site` only |
| Canonical unknown, malformed, case-variant, or reserved path | Deliberate `404` | Allowed on asset miss |
| Legacy `/map` | Same-origin world-map document, `200` | Yes, `erenshor-maps` |
| Legacy `/map/` | Same-origin relative `307` to `/map`, never cross-origin | Yes, `erenshor-maps` |
| Legacy runtime asset required by `/map` | Same-origin asset response, never a cross-origin redirect | Yes, `erenshor-maps` |
| Legacy exact root `/<mapKey>` | `301` to canonical `/maps/<mapKey>`, exact case and query preserved | Yes |
| Legacy other real HTML document | `301` to the same canonical path and query | Yes |
| Legacy `/sitemap.xml` | Existing canonical redirect | Yes |
| Legacy Google verification path | Existing token body, `200 text/html` | Yes |
| Legacy `/api/game-version` | Existing JSON contract and cache headers | Yes |
| Legacy unknown or reserved path | Deliberate `404`, not a guessed redirect | Yes |

No branch may inspect `User-Agent`. Redirects preserve path casing and the
complete query string. Browser fragments remain outside HTTP and are not part of
the contract.

The trailing-slash `307` is produced by Cloudflare's asset layer from
`html_handling: "auto-trailing-slash"`, not by our code. It was measured on both
hosts today. Because both services keep that same setting, the behavior is
unchanged by this split. Do not "fix" it during implementation and do not assert
a bare `200` for a trailing-slash HTML path.

## Verified before planning (2026-08-08)

These were open assumptions. Each was checked directly rather than inferred.

| Question | Result | Consequence |
| --- | --- | --- |
| Does the pinned wrangler 4.59.2 accept `run_worker_first` as an array? | Yes. Its `config-schema.json` types it as `anyOf: [string[], boolean]` with negative-rule support | Selective canonical routing is available without upgrading wrangler |
| What does wrangler do when a Custom Domain already belongs to another Worker? | With a TTY it prints the owning service and asks to repoint, and aborts the domain step if declined. Without a TTY it silently sets `override_existing_origin` and `override_existing_dns_record` | The takeover is a normal supported path, but unattended runs reassign production routing with no prompt |
| Does deploying the legacy config with no routes detach its Custom Domain? | No. `triggersDeploy` only calls `publishCustomDomains` when `customDomainsOnly.length > 0` | Detachment happens solely through the site deploy's takeover, so the site-then-legacy order is mandatory |
| Can two Workers hold the same asset bundle? | Yes. Asset limits are per Worker version: 25 MiB per file, and 20,000 files on Free against 100,000 on Paid | Duplication is safe here, and the largest asset, `/db/erenshor.sqlite` at 9,666,560 bytes, is well under the file ceiling |
| Is the account on the Workers Paid plan? | Yes, confirmed by the account owner. The subscriptions endpoint is not readable through this token, but the plan status is not in doubt | The 100,000 file asset ceiling applies, and the Free-tier `429` caveat on `run_worker_first` does not apply |
| Do trailing-slash HTML paths really return `200`? | No. `/map/`, `/maps/Stowaway/`, and legacy `/zone-maps/` each return a same-origin relative `307` | The response contract above was corrected. The earlier prose was wrong, the existing Vitest suite was not, because it mocks the asset binding |

### Local `workerd` routing spike

Docs are ambiguous about whether the navigation-request optimisation suppresses
the Worker when `not_found_handling` is `"none"`. Rather than guess, the four
candidate policies were run against real `workerd` through `wrangler dev --local`
on wrangler 4.59.2, using this project's exact `compatibility_date` of
`2025-06-01`, `html_handling`, and `not_found_handling`. The scratch project
lived outside the repository and has been torn down.

Nine probes per policy, counting how many reached the Worker:

| Policy | Worker invocations out of 9 | `/api/game-version` | Static assets | Asset miss |
| --- | --- | --- | --- | --- |
| `run_worker_first: true`, today | 9 | Worker | Worker, then asset binding | Worker |
| omitted, the documented default | 4 | Worker | Asset layer only | Worker |
| `run_worker_first: false` | 4 | Worker | Asset layer only | Worker |
| `run_worker_first: ["/api/game-version"]` | 4 | Worker | Asset layer only | Worker |

Findings:

- The navigation-request concern was unfounded. `/api/game-version` reached the
  Worker with and without `Sec-Fetch-Mode: navigate` under every asset-first
  policy. No compatibility flag change is needed.
- Omitting the setting, setting it to `false`, and using the selective array are
  behaviourally identical across all nine probes, including status codes and
  `Location` headers. Asset-first is therefore a pure invocation change, not a
  response change.
- Asset misses still reach the Worker under asset-first, so the deliberate `404`
  path is preserved exactly.
- The worker-first control reproduced today's pathology at 9 of 9, which
  validates that the harness measured the intended thing.

One policy difference did appear, and it decides the design. With a static file
present at `assets/api/game-version`, asset-first served that file and the Worker
was never invoked, silently returning stale JSON. Under
`run_worker_first: ["/api/game-version"]` the Worker still won and returned the
live payload.

The canonical service is therefore a static site with exactly one dynamic route,
and the selective array is the Cloudflare-native way to say so. It is kept for
that reason, not as redundancy. It costs no extra invocations, since that path
invokes the Worker under every policy, and it makes a future prerendered
`/api/*` route incapable of silently shadowing the endpoint. The Free-tier `429`
caveat attached to `run_worker_first` does not apply to a Paid account.

### Deploy-machine verification

Run on the MacBook Air that performs the real deploys, against its checkout at
`~/Projects/Erenshor`, using its own `node_modules` and its existing `./build`.
Only `wrangler deploy --dry-run` was used, so nothing was uploaded. The scratch
configs and the scratch entrypoint were deleted afterwards and
`git status --porcelain` returned to its exact five-line pre-spike baseline.

| Check | Result |
| --- | --- |
| Canonical config compiles | Yes. `Total Upload: 3.22 KiB / gzip: 1.45 KiB`, one `env.ASSETS` binding |
| Legacy config compiles | Yes. `Total Upload: 46.00 KiB / gzip: 6.17 KiB`, one `env.ASSETS` binding |
| `run_worker_first` array accepted | Yes, by the wrangler that machine actually runs |
| Is that field really validated? | Yes. A negative control produced `The field "assets.run_worker_first" should be an array of strings or a boolean, but got 42`, so acceptance is meaningful rather than silently ignored |
| Wrangler version on the deploy machine | `4.59.2` at the time of the spike. The repository has since been bumped to `4.120.0`, so that checkout is behind and needs `git pull` plus `pnpm install` before the cutover |
| Does the array survive the version bump? | Yes. Accepted by 4.54.0 and 4.59.2 by schema, and by 4.120.0 in a real dry-run of the committed configs |
| Build asset count | 7,381 files, far below both the 20,000 Free and 100,000 Paid ceilings |
| Largest assets | `db/erenshor.sqlite` 9.2 MB, `map.html` 7.2 MB, `map/__data.json` 6.9 MB, all under the 25 MiB per-file limit |
| `$lib` alias resolution under wrangler | Works. Both entrypoints import `$lib/...` and bundled cleanly from `src/maps` |

The canonical bundle being 3.22 KiB against the legacy 46.00 KiB is a useful
signal in itself. The canonical service carries only the dynamic endpoint, while
the map registry and redirect logic stay in the compatibility service where they
belong.

The `$lib` result matters for implementation order. Both configs must live in
`src/maps`, because alias resolution comes from that directory's tsconfig. Do not
relocate either Wrangler config elsewhere in the tree.

### Captured production baseline

Measured with single read-only requests on 2026-08-08, before any change:

| Host | Path | Status | Notable |
| --- | --- | --- | --- |
| Canonical | `/map` | 200 | `text/html` |
| Canonical | `/map/` | 307 | `Location: /map` |
| Canonical | `/maps/Stowaway` | 200 | `text/html` |
| Canonical | `/Stowaway` | 404 | null body, root keys are not canonical |
| Canonical | `/service-worker.js` | 200 | `text/javascript`, weak ETag |
| Canonical | `/db/erenshor.sqlite` | 200 | 9,666,560 bytes, strong ETag |
| Canonical | `/api/game-version` | 200 | `application/json` |
| Canonical | `/sitemap.xml` | 200 | `application/xml` |
| Canonical | unknown path, `/zones/{key}` | 404 | null body |
| Legacy | `/map` | 200 | same-origin document |
| Legacy | `/map/` | 307 | `Location: /map`, same-origin |
| Legacy | `/service-worker.js`, `/db/erenshor.sqlite` | 200 | byte-identical ETags to canonical |
| Legacy | `/Stowaway?sel=marker%3Aspawn%3Aa%20b` | 301 | query preserved byte-for-byte |
| Legacy | `/stowaway` | 404 | case-sensitive, no guessing |
| Legacy | `/zone-maps`, `/sitemap.xml` | 301 | canonical same-path redirect |
| Legacy | `/google279cf61d0b725839.html` | 200 | `text/html` token |
| Legacy | `/api/game-version` | 200 | `application/json` |

Re-running this exact set after each gate is the fastest regression check. The
canonical and legacy ETags for shared assets match today and must still match
after the split, because both services deploy the same build.

## Files and ownership

| Action | File | Responsibility |
| --- | --- | --- |
| Create | `src/maps/src/site-worker.ts` | Canonical API handler and asset-miss fallback only |
| Rename | `src/maps/src/worker.ts` → `src/maps/src/legacy-worker.ts` | Existing dual-host compatibility handler and rollback path |
| Rename | `src/maps/src/worker.test.ts` → `src/maps/src/legacy-worker.test.ts` | Existing legacy route matrix |
| Create | `src/maps/src/site-worker.test.ts` | Canonical API and fallback behavior |
| Create | `src/maps/src/worker-config.test.ts` | Executable two-service topology contract |
| Rewrite | `src/maps/wrangler.jsonc` | Canonical `erenshor-maps-site` configuration |
| Create | `src/maps/wrangler.legacy.jsonc` | Retained `erenshor-maps` compatibility configuration |
| Modify | `src/erenshor/cli/commands/maps.py` | Explicit site, legacy, and all-target deployment |
| Modify | `tests/unit/cli/commands/test_maps.py` | Deployment order, targeting, dry-run, and partial-failure contracts |
| Modify | `src/maps/README.md` | Operator-facing topology and canonical CLI commands |
| Modify | `.agent/skills/interactive-map/SKILL.md` | Map hosting architecture and verification facts |
| Modify | `.agent/skills/refreshing-game-data/SKILL.md` | Replace the stale single-target deployment statement |
| Modify | `AGENTS.md` | Clarify that one maps deploy publishes two Worker services from one build |
| Modify | `docs/plans/archive/2026-06-26-maps-domain-url-migration.md` | Add a supersession note without rewriting the historical plan |

The Wrangler JSONC files should be reduced to the actual deployed settings. Keep
them valid strict JSON despite the `.jsonc` suffix so the topology test can parse
them without adding a JSONC parser dependency.

## Planned commits

1. **`refactor(map): split canonical and legacy worker handlers`**
   - Rename the existing handler and test together through the language server.
   - Add the narrow canonical handler and its behavioral tests.
   - Preserve the complete existing legacy test matrix.

2. **`chore(map): define canonical and legacy worker services`**
   - Turn the default Wrangler config into `erenshor-maps-site`.
   - Add the retained-name legacy config with the same asset directory.
   - Add the topology contract test.
   - Validate both configurations with Wrangler dry runs.

3. **`refactor(cli): deploy both map worker services`**
   - Add explicit deployment targets and deterministic ordering.
   - Extend CLI tests for all success and failure states.
   - Keep build and deploy separate. Deploy must continue to use the existing
     stamped build and must never rebuild.

4. **`docs(map): document split worker operations`**
   - Update repository instructions, maps README, and both affected skills.
   - Mark only the old plan's one-Worker decision as superseded by this plan.
   - Leave its URL, SEO, and compatibility decisions intact.

Do not combine the commits. Each is independently reviewable and the first
three have distinct rollback boundaries.

## Implementation tasks

**Status (2026-08-09):** complete. All four commits are merged, CI is green
across every leaf, and the two-gate cutover has been executed and verified in
production. See the cutover record below. The only outstanding item is reading
the 24-hour analytics window described under post-cutover acceptance.

### Task 1: Separate the entrypoints without changing legacy behavior

- [x] Rename `worker.ts` and `worker.test.ts` to their `legacy-worker` names with
      LSP-aware file renames so imports follow the move.
- [x] Keep `LEGACY_HOST`, `CANONICAL_HOST`, the GSC token, exact map-key lookup,
      content-type redirect decision, and all existing exports in the legacy
      entrypoint.
- [x] Keep the canonical-host transparent asset branch in the legacy entrypoint.
      Document that it is the custom-domain rollback path, not normal steady
      state.
- [x] Add `site-worker.ts` as a single default export with the routing inlined
      in `fetch`. Match `GAME_VERSION_PATH` exactly, call the existing
      `handleGameVersion`, and delegate every other invocation to the asset
      binding. Do not mirror the legacy file's exported `handleRequest` wrapper.
      That indirection exists in the legacy entrypoint as an established test
      seam, whereas here it would be a one-line wrapper the repository's
      tiny-function rule rejects. Canonical tests exercise `worker.fetch`
      directly. This exact shape compiled on the deploy machine at 3.22 KiB.
- [x] Keep bindings structural and local to each entrypoint. Do not introduce a
      framework abstraction for two small handlers.
- [x] Move the existing route tests without weakening them.
- [x] Add canonical tests proving the API handler does not consult assets, an
      unexpected path delegates unchanged to assets, and the default export uses
      the same handler.

### Task 2: Encode the service split in Wrangler

- [x] Change `wrangler.jsonc` to `name = "erenshor-maps-site"`,
      `main = "./src/site-worker.ts"`, `workers_dev = false`, and retain only the
      `erenshor.compendiums.org` Custom Domain.
- [x] Configure the canonical asset binding with the shared `./build` directory,
      selective `run_worker_first = ["/api/game-version"]`, current HTML
      handling, and current not-found handling.
- [x] Add `wrangler.legacy.jsonc` with `name = "erenshor-maps"`,
      `main = "./src/legacy-worker.ts"`, `workers_dev = true`, no custom-domain
      route, the same asset directory, and `run_worker_first = true`.
- [x] Keep observability enabled for both services so the cutover can be proven
      with separate live tails.
- [x] Add a topology test that parses both strict-JSON configs and asserts the
      service names, entrypoints, `workers_dev` ownership, custom-domain
      ownership, shared asset directory, and opposite Worker-first policies.
- [x] Assert in the topology test that the canonical config lists
      `/api/game-version` in `run_worker_first`. The measured failure mode is a
      static file at that path silently shadowing the endpoint, so this is a
      correctness assertion rather than a style preference.
- [x] Run Wrangler's dry-run compilation for each config. A JSON parse test alone
      does not prove either entrypoint bundles.

### Task 3: Make the canonical CLI own both deployments

- [x] Add a typed `--target` option to `uv run erenshor maps deploy` with
      `all`, `site`, and `legacy`. Default to `all`.
- [x] Map `site` to `wrangler deploy --config wrangler.jsonc` and `legacy` to
      `wrangler deploy --config wrangler.legacy.jsonc`. Continue running through
      the maps directory with the existing Cloudflare precondition.
- [x] For `all`, deploy `site` first and `legacy` second. This follows the Ancient
      Kingdoms safety rule: establish and verify the new custom-domain owner
      before altering the retained-name legacy service.
- [x] Stop immediately when the site deployment fails. Do not touch the legacy
      service.
- [x] If the site succeeds and legacy fails, print that the canonical service is
      already live and give the exact resumable command
      `uv run erenshor maps deploy --target legacy`.
- [x] Keep deploy a pure upload. It must not call checks, prebuild generators, or
      Vite, and both targets must consume the same already-stamped build.
- [x] Make global dry-run append Wrangler's `--dry-run` flag and compile each
      selected target without uploading it. Print the exact ordered commands.
- [x] Extend the CLI tests for site-only, legacy-only, all-target order, first
      failure, second failure with the recovery hint, and Wrangler dry-run
      commands.

### Task 4: Update durable operational documentation

- [x] Replace every statement that `maps deploy` publishes one Wrangler target.
- [x] Document that the default config is canonical and the legacy config retains
      the permanent Worker name.
- [x] Add a compact topology section to the interactive-map skill.
- [x] Keep all user-facing build and deploy instructions on
      `uv run erenshor maps build` and `uv run erenshor maps deploy`. Do not teach
      raw Wrangler commands as the normal workflow.
- [x] Add a dated note to the archived domain-migration plan stating that this
      plan supersedes only its single-Worker deployment decision. The legacy
      runtime and route matrices remain authoritative.

## Pre-cutover verification

Run these before any shared Cloudflare deployment:

1. `uv run erenshor maps check`
2. `uv run pytest tests/unit/cli/commands/test_maps.py -q`
3. `uv run erenshor test ci`
4. `uv run erenshor maps build`
5. On the MacBook Air, run `uv run erenshor --dry-run maps deploy --target all`.
   Confirm Wrangler compiles both intended entrypoints in site-then-legacy order
   and points each at the same fresh build without uploading either service. The
   scratch equivalents of both configs already compiled there, so a failure here
   means the committed configs drifted from what was proven.
6. `uv run erenshor maps preview` and exercise `/map`, one `/maps/{key}` page,
   the SQLite file, a representative tile, the service worker, and
   `/api/game-version` locally.

On the MacBook Air, `git pull` and run `pnpm install` before the cutover. Its
checkout predates both this work and the Wrangler bump to `4.120.0`, so without
that step it would deploy old code with an old toolchain.

Before cutover, record through the Cloudflare API:

- the current custom-domain record ID, certificate ID, and service name.
- the active `erenshor-maps` deployment and version IDs.
- `workers.dev` and preview enablement.
- the current script runtime asset settings.
- the status, content type, redirect location, and ETag for representative paths
  on both hosts.

This snapshot is rollback evidence. Do not delete any old version or service.

## Cutover sequence

Cutover requires explicit authorization because it changes shared production
routing.

### Gate 1: Deploy and verify the new canonical owner

1. Run `uv run erenshor maps deploy --target site` from an interactive terminal
   on the MacBook Air, the machine that owns the existing deploys and whose
   checkout lives at `~/Projects/Erenshor`.
   The CLI inherits stdio, so wrangler will detect a TTY and prompt with
   `Custom Domains already exist for these domains: erenshor.compendiums.org
   (used as a domain for "erenshor-maps"). Update them to point to this script
   instead?`. Answer yes deliberately. Declining aborts only the domain step and
   leaves the current owner in place. Never run this gate from CI or with piped
   output, because wrangler then repoints production routing with no prompt.
2. Confirm through `GET /accounts/{account}/workers/domains` that
   `erenshor.compendiums.org` now maps to `erenshor-maps-site`, with the existing
   domain and certificate IDs retained by Cloudflare's domain attachment.
3. Confirm the deployed version reports direct asset serving and selective
   Worker-first routing only for `/api/game-version`.
4. Exercise the canonical smoke matrix below.
5. Do not alter `erenshor-maps` until every canonical check passes. During this
   gate its existing version continues serving the legacy `workers.dev` origin.

Cloudflare's Custom Domain attachment is the routing boundary. If the site
deployment fails before attachment, the old service remains the owner. If it
attaches but fails smoke verification, execute the rollback immediately.

### Gate 2: Convert the retained service to legacy-only triggers

1. Run `uv run erenshor maps deploy --target legacy`.
2. Confirm `erenshor-maps.wowmuch1.workers.dev` remains enabled.
3. Confirm `erenshor-maps` has no custom domain and
   `erenshor.compendiums.org` still maps to `erenshor-maps-site`.
4. Exercise the full legacy smoke matrix below, including an actual browser
   service-worker registration.
5. Run `uv run erenshor --dry-run maps deploy --target all` and confirm the
   normal future path compiles site followed by legacy without uploading.

## Production smoke matrix

### Canonical host

- [x] `/`, `/map`, and one exact `/maps/{key}` return `200` with canonical-host
      metadata.
- [x] `/map/` and `/maps/{key}/` still return the same-origin relative `307`
      recorded in the baseline, not a `200` and not a cross-origin redirect.
- [x] `/service-worker.js`, one hashed `/_app/immutable` file, one SQLite file,
      one tile, one image, and one font return their expected content types.
- [x] Conditional requests retain valid ETag and `304` behavior.
- [x] `/api/game-version` returns the existing JSON schema and cache headers.
- [x] An unknown path, wrong-case root key, and `/zones/{key}` return `404`.
- [x] A real browser loads `/map`, initializes the map, installs the service
      worker, and reports no console or failed-network errors.

Open a live tail on `erenshor-maps-site`, then request the static paths and the
API path under controlled conditions. The API request must appear. Matching
static asset requests must not appear. This is the direct proof that the change
fixed the invocation path.

### Legacy host

- [x] `/map` remains a same-origin `200` document and does not navigate to the
      custom domain.
- [x] `/map/` remains a same-origin relative `307` to `/map`. A cross-origin
      redirect here breaks shipped companion overlays.
- [x] The service worker, Svelte runtime, SQLite file, representative tiles,
      images, icons, and fonts remain same-origin successful responses.
- [x] The service worker registers under the legacy origin and completes its
      current offline-cache install without a cross-origin or scope error.
- [x] One exact mixed-case root map key redirects to canonical `/maps/{key}` and
      preserves an encoded query byte-for-byte.
- [x] Wrong-case, trailing-slash, unknown, malformed, and reserved paths retain
      their current 404 behavior.
- [x] A real non-`/map` HTML route redirects to the same canonical path and query.
- [x] `/sitemap.xml` and the Google verification token retain their current
      special behavior.
- [x] `/api/game-version` retains its existing JSON behavior.

A live tail on `erenshor-maps` should show these legacy requests. Those
invocations are intentional compatibility work.

## Rollback

Rollback never disables or renames the retained `erenshor-maps` service.

### Canonical failure before the legacy deployment

Reattach `erenshor.compendiums.org` to `erenshor-maps` through Cloudflare's
Custom Domain API or dashboard. The old combined version is still deployed and
has not changed. Confirm the domain record reports `service = "erenshor-maps"`,
then rerun the original dual-host smoke matrix.

### Canonical failure after the legacy deployment

Reattach the custom domain to `erenshor-maps`. The new legacy entrypoint retains
the canonical-host transparent asset branch and the complete asset bundle
specifically so this rollback still works. If its code is implicated, deploy the
recorded pre-cutover `erenshor-maps` version before reattaching.

### Legacy-only failure

Leave `erenshor-maps-site` and the canonical domain in place. Redeploy the
recorded pre-cutover version of `erenshor-maps` or retry
`uv run erenshor maps deploy --target legacy`. No canonical rollback is needed.

Do not delete `erenshor-maps-site`, old versions, domain records, or certificates
during the stabilization window. Rollback changes only the Custom Domain's
service attachment and, if necessary, the active Worker version.

## Cutover record (2026-08-09)

Executed from the MacBook Air. Both gates succeeded and no rollback was needed.

| Item | Value |
| --- | --- |
| Gate 1, canonical | `erenshor-maps-site` version `f9e7865c-8a59-4dd3-8392-00231d407b11`, 6,790 assets uploaded |
| Domain takeover | Wrangler prompted `erenshor.compendiums.org (used as a domain for "erenshor-maps"). Update them to point to this script instead?` and was answered yes |
| Domain record | ID `8a8254cb46d6f1b791657ed2db270fb00f434831` and cert `c45c2c19-db5e-4eb2-82d1-0578c8e1afe7` were both retained, only `service` changed |
| Gate 2, legacy | `erenshor-maps` version `3d8d0503-ed5a-49ba-806c-c00104ab403e`, 102 changed assets against 7,279 already uploaded |
| Pre-cutover legacy version, for rollback | `42ada1ac-8af3-4871-a02e-c9d0f3f5cd6b`, deployment `72ab2e78-f552-481a-b6e6-9207f0bce76d` |
| Canonical runtime after cutover | `serve_directly: true`, `static_routing.user_worker: ["/api/game-version"]` |
| Legacy runtime after cutover | `serve_directly: false`, `raw_run_worker_first: true`, workers.dev still enabled |

Live-tail proof on `erenshor-maps-site`: requesting `/map`, `/maps/Stowaway`,
`/service-worker.js`, `/tiles/tiles-manifest.json`, `/db/erenshor.sqlite`, and
`/sitemap.xml` produced no Worker invocation. Only `/api/game-version` did.

Both smoke matrices matched the pre-cutover baseline, including the
trailing-slash `307`s, byte-for-byte legacy query preservation, and identical
ETags across the two services for shared assets. In a real browser the canonical
`/map` rendered with an activated service worker and zero console or network
errors, and the legacy `/map` stayed same-origin, kept its cross-domain
canonical tag, and completed its 255-tile offline install.

Per-minute invocations for `erenshor-maps` fell from several hundred to over a
thousand per minute before 18:58 UTC to zero in most minutes afterwards. The one
post-cutover spike of 599 was this session's own legacy browser check, which is
the expected cost of a worker-first host performing the tile precache.

Two caveats for whoever reads the dashboard next:

- Invocations for the new service currently land under `__unknown__` in
  `workersInvocationsAdaptive`. A controlled burst of 12 `/api/game-version`
  requests appeared as `__unknown__: 11`, so the script-name dimension has not
  propagated yet. Re-check attribution before drawing conclusions.
- The Air pins Python `3.14.7` through `.python-version`, but its Homebrew `uv`
  cannot download that build, and the project only requires `>=3.13`. The
  deploy was run with `uv run -p 3.13`. Either upgrade `uv` there or relax the
  pin, otherwise the next deploy hits the same wall.

## Post-cutover acceptance

Immediately after cutover:

- Both production smoke matrices pass.
- Cloudflare lists `erenshor-maps-site` as the sole owner of
  `erenshor.compendiums.org`.
- Cloudflare lists `erenshor-maps` with `workers.dev` enabled and no custom
  domain.
- `erenshor-maps-site` reports direct asset serving with selective
  Worker-first routing.
- `erenshor-maps` reports Worker-first asset handling and continues to serve old
  mods.

After one complete 24-hour window:

- Attribute invocations by script through `workersInvocationsAdaptive`.
- `erenshor-maps-site` invocations should correspond to `/api/game-version` and
  genuine asset misses, not ordinary static assets.
- `erenshor-maps` invocations should correspond only to legacy-host traffic.
- Compare against the recorded baseline of 460,069 `erenshor-maps` invocations
  and 460,043 subrequests. Report exact new counts rather than an estimated
  reduction.
- Do not use Total Requests as the success metric. The service-worker tile
  precache remains and still counts as HTTP traffic. The contract is that those
  canonical asset requests no longer invoke a Worker.

## Risks and controls

| Risk | Control |
| --- | --- |
| Renaming the retained service breaks shipped mods | Never rename `erenshor-maps`. The new name belongs only to the canonical service. |
| Legacy `/map` loses same-origin assets | Legacy service keeps its own binding to the identical build and its current Worker-first handler. |
| Two deployments drift | Build once, stamp once, deploy both from the same directory. CLI owns deterministic order and resumable targeting. |
| Custom-domain cutover fails | Existing service remains untouched until the site deployment. Record IDs and active versions first. Reattach the domain to roll back. |
| Canonical static requests still invoke code | Topology test, deployed runtime inspection, and controlled live-tail proof all check this independently. |
| Future maintainer reintroduces one Worker | Config contract test and updated skills encode hostname ownership and Worker-first policy. |
| Service-worker request volume remains high | Explicit non-goal. Measure separately after invocation cutover and plan lazy caching only if desired. |

## Completion condition

This plan is complete only when the code and documentation commits are merged,
the explicitly authorized two-gate cutover succeeds, both browser surfaces pass,
and a full post-cutover analytics window proves that canonical static assets no
longer appear as Worker invocations. Completing repository changes without the
Cloudflare routing and live-tail evidence is not completion.

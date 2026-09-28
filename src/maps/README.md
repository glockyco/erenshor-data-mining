# Erenshor Community Tools

Community tools website for Erenshor. Includes interactive maps with spawn
points, NPCs, live player position, guide tools, and reference data.

Deployed to Cloudflare Workers with static assets from the SvelteKit build.

## Hosting topology

One build is deployed to two Cloudflare Worker services:

| Config | Service | Hostname | Asset policy |
| --- | --- | --- | --- |
| `wrangler.jsonc` | `erenshor-maps-site` | `erenshor.compendiums.org` | Assets served directly. Only `/api/game-version` invokes the Worker. |
| `wrangler.legacy.jsonc` | `erenshor-maps` | `erenshor-maps.wowmuch1.workers.dev` | Worker runs first, because routing depends on the hostname. |

The legacy service exists because shipped InteractiveMapCompanion versions
hardcode the legacy `/map` document and refuse to navigate to another host, so
that document and every runtime resource it loads must stay same-origin. It
carries its own copy of the same build for that reason.

The Worker name `erenshor-maps` must not change. workers.dev hostnames are
derived from it, and renaming it would break those shipped mods.

## Tech Stack

- SvelteKit
- deck.gl for map rendering
- sql.js reading the clean SQLite database at build time
- Cloudflare Workers static assets

## Prerequisites

- `uv` for the Python CLI
- `pnpm install` in the repository workspace
- A clean variant database from `uv run erenshor extract build`

## Commands

Use the CLI for all website workflows:

```bash
uv run erenshor maps --help
uv run erenshor maps dev      # Dev server on the selected variant database
uv run erenshor maps build    # Verify, build, and stamp provenance
uv run erenshor maps preview  # Preview an existing fresh build
uv run erenshor maps deploy   # Deploy an existing fresh build to both services
uv run erenshor maps deploy --target site    # Canonical service only
uv run erenshor maps deploy --target legacy  # Compatibility service only
uv run erenshor maps check  # Lint, type-check, and run fixture-backed unit tests
uv run erenshor test maps   # Add the fixture-backed browser smoke test
```

Do not use `pnpm dev` directly. The CLI passes the selected variant database to
the site through `ERENSHOR_MAPS_DATABASE_PATH` while `maps dev` or `maps build`
runs. The Vitest phase creates a temporary deterministic SQLite fixture.

`test maps` also runs the Playwright smoke test in `tests/e2e/`.
`scripts/serve-fixture-site.mjs` builds the site from the same fixture into
temporary directories and serves it. The test loads `/`, `/map`, and
`/maps/Stowaway` in Chromium and fails on a page error, a failed same-origin
request, missing popup content, the legacy overlay layers query, or a missing
published database. Install the browser once per machine with
`pnpm --dir src/maps exec playwright install chromium`. Run the test alone with
`pnpm --dir src/maps run test:e2e`.

## Data Flow

The build reads the clean database (`erenshor-{variant}.sqlite`, built by
`erenshor extract build`) from `ERENSHOR_MAPS_DATABASE_PATH`. The map reads
spawn points, characters, zones, and other entity data from this database. The
prerendered route `src/routes/db/erenshor.sqlite/` publishes an unchanged copy
at `/db/erenshor.sqlite`. A `.sqlite` file under `static/` stops `maps build`
and `maps dev`, because it would collide with that route.

Live entity positions come from the InteractiveMapCompanion BepInEx mod via
WebSocket.

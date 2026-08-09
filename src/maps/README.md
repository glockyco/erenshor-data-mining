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
- sql.js reading the static SQLite database from `static/db/`
- Cloudflare Workers static assets

## Prerequisites

- `uv` for the Python CLI
- `pnpm install` in the repository workspace
- A clean variant database from `uv run erenshor extract build`

## Commands

Use the CLI for all website workflows:

```bash
uv run erenshor maps --help
uv run erenshor maps dev      # Dev server; symlinks the variant DB
uv run erenshor maps build    # Verify, build, and stamp provenance
uv run erenshor maps preview  # Preview an existing fresh build
uv run erenshor maps deploy   # Deploy an existing fresh build to both services
uv run erenshor maps deploy --target site    # Canonical service only
uv run erenshor maps deploy --target legacy  # Compatibility service only
uv run erenshor maps check  # Lint, type-check, and run fixture-backed unit tests
uv run erenshor test maps   # Add a temporary fixture-backed prerender smoke
```

Do not use `pnpm dev` directly. The CLI manages the database symlink for dev and
copies the canonical clean database into `static/db/` during build. The Vitest
phase creates a temporary deterministic SQLite fixture and does not read
`static/db/erenshor.sqlite`. The `test maps` prerender smoke writes to a temporary
build directory and proves that `/`, `/map`, and `/maps/Stowaway` render from the
same fixture.

## Data Flow

The clean database (`erenshor-{variant}.sqlite`, built by `erenshor extract
build`) is copied to `static/db/erenshor.sqlite` during `maps build`. The map
reads spawn points, characters, zones, and other entity data from this database.

Live entity positions come from the InteractiveMapCompanion BepInEx mod via
WebSocket.

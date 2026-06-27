# Erenshor Community Tools

Community tools website for Erenshor. Includes interactive maps with spawn
points, NPCs, live player position, companion mod downloads, guide tools, and
reference data.

Deployed to Cloudflare Workers with static assets from the SvelteKit build.

## Tech Stack

- SvelteKit
- deck.gl for map rendering
- sql.js reading the static SQLite database from `static/db/`
- Cloudflare Workers static assets

## Prerequisites

- `uv` for the Python CLI
- `pnpm install` in the repository workspace
- `dotnet` plus `uv run erenshor mod setup` before maps builds that publish mods
- A clean variant database from `uv run erenshor extract build`

## Commands

Use the CLI for all website workflows:

```bash
uv run erenshor maps --help
uv run erenshor maps dev      # Dev server; symlinks the variant DB
uv run erenshor maps build    # Verify, publish mods, build, stamp provenance
uv run erenshor maps preview  # Preview an existing fresh build
uv run erenshor maps deploy   # Deploy an existing fresh build
```

Do not use `pnpm dev` directly. The CLI manages the database symlink for dev and
copies the canonical clean database into `static/db/` during build.

## Data Flow

The clean database (`erenshor-{variant}.sqlite`, built by `erenshor extract
build`) is copied to `static/db/erenshor.sqlite` during `maps build`. The map
reads spawn points, characters, zones, and other entity data from this database.

Live entity positions come from the InteractiveMapCompanion BepInEx mod via
WebSocket.

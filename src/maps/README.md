# Erenshor Interactive Maps

Interactive map website for Erenshor. Displays zone maps with spawn points, NPCs, and live player position (via the InteractiveMapCompanion mod).

Deployed to Cloudflare Workers.

## Tech Stack

- SvelteKit
- deck.gl (map rendering)
- Cloudflare Workers + D1 (hosting and data)

## Development

```bash
uv run erenshor maps dev            # Dev server at localhost:5173
uv run erenshor maps preview        # Preview production build
uv run erenshor maps build --force  # Production build
uv run erenshor maps deploy         # Deploy to Cloudflare
```

Do not use `npm run dev` or `pnpm dev` directly -- the CLI handles database setup and environment configuration.

## Data Flow

The clean database (`erenshor-main.sqlite`, built by `erenshor extract build`) is copied to `static/db/` during `maps build`. The map reads spawn points, characters, zones, and other entity data from this database.

Live entity positions come from the InteractiveMapCompanion BepInEx mod via WebSocket.

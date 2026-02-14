# Interactive Map Companion

Ever alt-tab to check the wiki for an NPC location while your SimPlayer party
waits patiently? Now you don't have to guess what's where - see everything alive
in your zone on a real-time interactive map, right in your browser.

**Interactive Map Companion** broadcasts live entity positions from your game to
the [interactive world map](https://erenshor-maps.wowmuch1.workers.dev/map),
turning it into a second-screen companion for exploration, combat, and
navigation.

![Live tracking demo](https://erenshor-maps.wowmuch1.workers.dev/world-map-companion.gif)

## What it tracks

- **Your character** — live position and facing direction
- **SimPlayers** — party members and other SimPlayers in the zone
- **NPCs** — quest givers, merchants, and other friendly NPCs
- **Enemies** — all hostile mobs currently alive
- **Pets** — companion pets

All tracking updates in real-time (10 Hz by default).

## Privacy

All data stays on your machine. The mod runs a local WebSocket server that your
browser connects to directly - nothing is sent to any external server.

## Quick Start

Requires [BepInEx 5](https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/).

1. Install BepInEx if you haven't already
2. Copy the `InteractiveMapCompanion/` folder (containing
   `InteractiveMapCompanion.dll`, `Fleck.dll`, and `Newtonsoft.Json.dll`)
   into `BepInEx/plugins/`
3. Launch the game and log in with a character
4. Open the [interactive world map](https://erenshor-maps.wowmuch1.workers.dev/map)
5. Toggle **Enable Live Mode** in the sidebar

### Reducing Clutter

To hide static markers and only see live entities, disable the regular enemy and
NPC layers through the sidebar, or use this direct link:
[map with static markers hidden](https://erenshor-maps.wowmuch1.workers.dev/map?layers=-sp%2C-spr%2C-spu%2C-npc)

## Configuration

The config file is generated on first run at
`BepInEx/config/wow-much.interactive-map-companion.cfg`:

### Server

| Setting | Default | Description |
|---------|---------|-------------|
| `Port` | `18584` | WebSocket server port |
| `UpdateInterval` | `100` | Broadcast interval in ms (100 = 10 Hz) |

### Logging

| Setting | Default | Description |
|---------|---------|-------------|
| `WebSocketLogLevel` | `Warning` | `Debug` / `Info` / `Warning` / `Error` |
| `ModLogLevel` | `Info` | `Debug` / `Info` / `Warning` / `Error` |

## Technical Details

The mod runs a lightweight WebSocket server on `localhost:18584`. Your browser
connects directly to this local server - the map website's JavaScript acts as
the client. The protocol uses JSON messages for handshake, state updates, and
zone changes.

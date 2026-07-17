# Interactive Map Companion

Native dual-loader mod for Erenshor that broadcasts real-time game state to the
interactive map website via WebSocket, and optionally renders the map as an
in-game overlay. The BepInEx build is distributed on Thunderstore as
`WoW_Much/InteractiveMapCompanion`. The native Lunaris build is distributed
through the Erenshor Vault.

## Local build and distribution

Set up references once, then select the native loader explicitly:

```bash
uv run erenshor mod setup
uv run erenshor mod build --mod interactive-map-companion --loader bepinex
uv run erenshor mod deploy --mod interactive-map-companion --loader bepinex
uv run erenshor mod build --mod interactive-map-companion --loader lunaris
uv run erenshor mod deploy --mod interactive-map-companion --loader lunaris
```

BepInEx deployment follows `thunderstore.toml` and installs the DLL under
`<game>/BepInEx/plugins/InteractiveMapCompanion/`. Lunaris deploys to
`<game>/plugins`. Each deploy also activates its loader. Exit the game before
switching, then restart before testing. The canonical local Thunderstore check
packages all four public mods without uploading:

```bash
uv run erenshor mod thunderstore --dry-run
```

A real upload requires exactly one `--mod interactive-map-companion` and a
non-placeholder `TCLI_AUTH_TOKEN`. There is no GitHub release automation.
Prepare the Lunaris artifact for manual Vault upload with
`uv run erenshor mod vault --mod interactive-map-companion`.


- **Live Entity Tracking**: Broadcasts positions of your character, SimPlayers,
  NPCs, enemies, and pets in real-time
- **In-Game Overlay**: Press `M` to show/hide the interactive map inside the
  game window (requires Steam, configurable)
- **WebSocket Server**: Lightweight WebSocket server running on `localhost:18585`
- **Configurable Updates**: Adjustable broadcast interval (default: 100ms / 10 Hz)
- **Configurable Logging**: Control verbosity of console output
- **Roadmap**: Spawn tracking, third-party markers, and bidirectional
  communication

## Installation

Choose the package for the loader you use. Install the BepInEx build from
Thunderstore or the native Lunaris build from the Erenshor Vault. Do not copy a
DLL built for one loader into the other loader's plugin directory.

For a manual BepInEx installation:

1. Install [BepInEx 5](https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/).
2. Copy the `InteractiveMapCompanion/` package folder into
   `BepInEx/plugins/`. Keep the DLL inside that folder.
3. Launch the game. The mod starts automatically.

For Lunaris, install Interactive Map Companion through the in-game Vault
browser. Loader-provided dependencies are not bundled with the Lunaris DLL.

## Usage

### Browser / Second Screen

1. Start Erenshor with the mod installed
2. Open the [Interactive Map](https://erenshor.compendiums.org/map)
3. Enable Live Mode in the map settings
4. Your position will appear on the map in real-time

### In-Game Overlay

With Steam running (always the case for Erenshor), the overlay starts
automatically. Press `M` to toggle it. The overlay renders the full interactive
map website inside the game using Steam's built-in Chromium browser, so the
WebSocket connection to `localhost:18585` works exactly as in the browser.

### Second Screen (Phone/Tablet)

To use the map on another device on your local network:

1. Find your PC's local IP address (e.g., `192.168.1.50`)
2. On your phone, open the map and go to connection settings
3. Enter `ws://192.168.1.50:18585` as the server address
4. Connect and enable Live Mode

## Configuration

Each loader exposes the same settings through its native config system.
BepInEx writes `BepInEx/config/wow-much.interactive-map-companion.cfg`.
Lunaris exposes the settings through its in-game config UI.

### Server Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `Port` | Integer | `18585` | WebSocket server port |
| `UpdateInterval` | Integer | `100` | Broadcast interval in milliseconds (100ms = 10 Hz) |

### Overlay Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `EnableOverlay` | Boolean | `true` | Show the in-game map overlay |
| `ToggleKey` | KeyCode | `M` | Key to show/hide the overlay |
| `AnchorX` | Float | `-1` | Horizontal anchor (0 = left, 1 = right). `-1` auto-computes on first run. |
| `AnchorY` | Float | `-1` | Vertical anchor (0 = bottom, 1 = top). `-1` auto-computes on first run. |
| `Width` | Integer | `0` | Overlay width in pixels. `0` auto-computes as 80% of screen width. |
| `Height` | Integer | `0` | Overlay height in pixels. `0` auto-computes as 80% of screen height. |
| `ResetToDefaults` | Boolean | `false` | Set to `true` to reset size and position to auto-computed defaults on next launch. |

### Logging Settings

Control console output verbosity:

| Setting | Type | Default | Options |
|---------|------|---------|---------|
| `WebSocketLogLevel` | Enum | `Warning` | `Debug`, `Info`, `Warning`, `Error` |
| `ModLogLevel` | Enum | `Info` | `Debug`, `Info`, `Warning`, `Error` |

## Development

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical details.

```bash
# Copy game and both loader references for compilation
uv run erenshor mod setup

# Build and deploy the native BepInEx target
uv run erenshor mod build --mod interactive-map-companion --loader bepinex
uv run erenshor mod deploy --mod interactive-map-companion --loader bepinex

# Build and deploy the native Lunaris target
uv run erenshor mod build --mod interactive-map-companion --loader lunaris
uv run erenshor mod deploy --mod interactive-map-companion --loader lunaris

# Launch the selected game installation
uv run erenshor -V playtest mod launch
```

## WebSocket Protocol

The mod uses a JSON-based WebSocket protocol. All messages use camelCase naming
for JavaScript compatibility.

### Message Types

**Handshake** (sent on connection):
```json
{
  "type": "handshake",
  "protocolVersion": "0.2.0",
  "modVersion": "2026.2.19.0",
  "zone": "Elderstone",
  "capabilities": ["entities"]
}
```

**State Update** (broadcast every UpdateInterval):
```json
{
  "type": "stateUpdate",
  "zone": "Elderstone",
  "timestamp": 1768645811226,
  "entities": [{
    "id": 993814,
    "entityType": "player",
    "name": "YourCharacterName",
    "position": [-13.88, -2.97, -15.58],
    "rotation": 86.15
  }]
}
```

**Zone Change** (sent when player changes zones):
```json
{
  "type": "zoneChange",
  "previousZone": "Elderstone",
  "zone": "Azure",
  "timestamp": 1768645811226
}
```

## Troubleshooting

### Mod Not Loading

1. Run `uv run erenshor -V playtest mod status` and confirm the intended loader
   is active.
2. For BepInEx, inspect `BepInEx/LogOutput.log` and confirm the DLL is under
   `BepInEx/plugins/InteractiveMapCompanion/`.
3. For Lunaris, inspect the in-game log UI and confirm the DLL is in the game's
   top-level `plugins/` directory.
4. Restart the game after changing or switching loaders.

### Overlay Not Appearing
1. The overlay requires the game to be launched through Steam
2. Check the active loader's log for `[Overlay]` lines — initialization errors
   are logged
3. Confirm `EnableOverlay = true` in the active loader's config UI or file
4. Try toggling with `M` (or your configured key) while in-game (not on the
   main menu)

### WebSocket Connection Failed
1. Verify the game is running with mod loaded
2. Check port 18585 is not blocked by firewall
3. Enable debug logging through the active loader's config UI or file
4. Check the active loader's log for errors

### Player Marker Not Appearing
1. Ensure "Live Mode" is enabled on the map
2. Check browser DevTools console for WebSocket messages
3. Verify you're in a mapped zone
4. Enable debug logging to see broadcast messages

## License

MIT License — see repository root for details.

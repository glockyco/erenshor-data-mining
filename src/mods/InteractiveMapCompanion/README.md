# Interactive Map Companion

BepInEx mod for Erenshor that broadcasts real-time game state to the interactive
map website via WebSocket, and optionally renders the map as an in-game overlay.

## Features

- **Live Entity Tracking**: Broadcasts positions of your character, SimPlayers,
  NPCs, enemies, and pets in real-time
- **In-Game Overlay**: Press `M` to show/hide the interactive map inside the
  game window (requires Steam, configurable)
- **WebSocket Server**: Lightweight WebSocket server running on `localhost:18585`
- **Configurable Updates**: Adjustable broadcast interval (default: 100ms / 10 Hz)
- **Configurable Logging**: Control verbosity of console output
- **Future Features**: Spawn tracking, third-party markers, bidirectional
  communication (configurable, coming soon)

## Installation

1. Install [BepInEx 5.4.20 or newer](https://github.com/BepInEx/BepInEx/releases)
   to your Erenshor installation
2. Download the latest release of InteractiveMapCompanion
3. Extract `InteractiveMapCompanion.dll` to `BepInEx/plugins/`
4. Launch the game — the mod will start automatically

**Note**: All dependencies are merged into the single DLL. No additional files needed.

## Usage

### Browser / Second Screen

1. Start Erenshor with the mod installed
2. Open the [Interactive Map](https://erenshor-maps.wowmuch1.workers.dev/map)
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

The mod can be configured via:
`BepInEx/config/wow-much.interactive-map-companion.cfg`

This file is automatically created the first time you run the game with the mod
installed.

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
| `AnchorX` | Float | `0.5` | Horizontal anchor (0 = left, 1 = right). Auto-computed on first run. |
| `AnchorY` | Float | `0.5` | Vertical anchor (0 = bottom, 1 = top). Auto-computed on first run. |
| `Width` | Integer | *(auto)* | Overlay width in pixels. Auto-computed as 90% of screen width on first run. |
| `Height` | Integer | *(auto)* | Overlay height in pixels. Auto-computed as 90% of screen height on first run. |
| `ResetToDefaults` | Boolean | `false` | Set to `true` to reset size and position to auto-computed defaults on next launch. |

### Feature Toggles (Future)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `EnableSpawnTracking` | Boolean | `true` | Track enemy deaths and broadcast respawn timers (future feature) |
| `EnableThirdPartyMarkers` | Boolean | `true` | Allow other mods to register custom markers (future feature) |
| `EnableBidirectional` | Boolean | `true` | Accept messages from clients for waypoints, pings (future feature) |

### Logging Settings

Control console output verbosity:

| Setting | Type | Default | Options |
|---------|------|---------|---------|
| `WebSocketLogLevel` | Enum | `Warning` | `Debug`, `Info`, `Warning`, `Error` |
| `ModLogLevel` | Enum | `Info` | `Debug`, `Info`, `Warning`, `Error` |

## Development

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical details.

```bash
# Copy game DLLs for compilation
uv run erenshor mod setup

# Build the mod
uv run erenshor mod build

# Build and deploy to BepInEx plugins
uv run erenshor mod deploy

# Launch the game
uv run erenshor mod launch
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
1. Check BepInEx console for errors
2. Verify BepInEx version is 5.4.20 or newer
3. Ensure DLL is in `BepInEx/plugins/` (not in a subdirectory)

### Overlay Not Appearing
1. The overlay requires the game to be launched through Steam
2. Check BepInEx log for `[Overlay]` lines — initialization errors are logged
3. Confirm `EnableOverlay = true` in the config file
4. Try toggling with `M` (or your configured key) while in-game (not on the
   main menu)

### WebSocket Connection Failed
1. Verify the game is running with mod loaded
2. Check port 18585 is not blocked by firewall
3. Enable debug logging: set `WebSocketLogLevel=Debug` in config
4. Check BepInEx console for errors

### Player Marker Not Appearing
1. Ensure "Live Mode" is enabled on the map
2. Check browser DevTools console for WebSocket messages
3. Verify you're in a mapped zone
4. Enable debug logging to see broadcast messages

## License

MIT License — see repository root for details.

# InteractiveMapCompanion

BepInEx mod that broadcasts real-time game state to the
[Erenshor Interactive Map](https://erenshor.pages.dev/) via WebSocket.

## Features

- Live player position tracking on the world map
- Track all characters in current zone (simplayers, NPCs, enemies)
- Respawn timer tracking for spawn points
- Third-party marker API for other mods
- Bidirectional communication (waypoints, pings)

## Installation

1. Install [BepInEx 5.x](https://github.com/BepInEx/BepInEx) to your Erenshor installation
2. Copy `InteractiveMapCompanion.dll` to `BepInEx/plugins/`
3. Copy `Fleck.dll` to `BepInEx/plugins/`
4. Launch the game

## Usage

1. Start Erenshor with the mod installed
2. Open the [Interactive Map](https://erenshor.pages.dev/map)
3. Enable Live Mode in the map settings
4. Your position will appear on the map in real-time

### Second Screen (Phone/Tablet)

To use the map on another device on your local network:

1. Find your PC's local IP address (e.g., `192.168.1.50`)
2. On your phone, open the map and go to connection settings
3. Enter `ws://192.168.1.50:18584` as the server address
4. Connect and enable Live Mode

## Configuration

Configuration is in `BepInEx/config/com.erenshor.interactivemap.cfg`:

| Setting | Default | Description |
|---------|---------|-------------|
| Port | 18584 | WebSocket server port |
| UpdateInterval | 100 | Broadcast interval in milliseconds |
| EnableSpawnTracking | true | Track respawn timers |
| EnableThirdPartyMarkers | true | Accept third-party marker registrations |
| EnableBidirectional | true | Accept client messages |

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

## Third-Party API

Other mods can register custom markers:

```csharp
// Find the API (soft dependency)
var mapCompanion = BepInEx.Bootstrap.Chainloader.PluginInfos
    .GetValueOrDefault("com.erenshor.interactivemap");
var api = mapCompanion?.Instance as IMarkerAPI;

// Register a marker
api?.RegisterMarker(new MarkerDefinition
{
    Id = "my-marker-1",
    Source = "MyMod",
    Type = "waypoint",
    Position = new Vector3(100, 10, 200),
    Zone = "Stowaway",
    Label = "My Custom Marker"
});
```

See [docs/REQUIREMENTS.md](docs/REQUIREMENTS.md) for full API documentation.

## License

MIT License - see repository root for details.

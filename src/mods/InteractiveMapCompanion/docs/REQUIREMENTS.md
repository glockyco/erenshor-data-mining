# InteractiveMapCompanion Requirements

## Overview

BepInEx mod that broadcasts real-time game state to the Interactive Map website
via WebSocket. Enables live entity tracking, spawn monitoring, and bidirectional
communication for navigation features.

## Goals

1. **Live Entity Tracking**: Show all characters in current zone on map
2. **Spawn Intelligence**: Track enemy deaths and broadcast respawn timers
3. **Extensibility**: Allow other mods to register custom markers
4. **Bidirectional Communication**: Support waypoints, pings, commands from map
5. **Multi-Client Support**: Enable "second screen" usage (phone on LAN)

## Non-Goals

- Historical data / breadcrumb trails
- Player stats display (health/mana)
- Cloud-based synchronization

---

## Entity Tracking

### Tracked Entities

Track all GameObjects with `Character` component in current zone:

| Type | Identification | Extra Data |
|------|----------------|------------|
| `player` | `transform.name == "Player"` | - |
| `simplayer` | Has `SimPlayer` component | - |
| `pet` | `Master != null` or `SummonedByPlayer` | - |
| `npc_friendly` | NPC with friendly faction | - |
| `npc_enemy` | NPC with hostile faction | level, rarity, spawnPointId |

**Not tracked**: Mining nodes, treasure chests (static, don't need live updates)

### Entity Data

For each entity:
- `id`: Instance ID (unique within session)
- `entityType`: Classification (see above)
- `name`: Display name
- `position`: `[x, y, z]` zone-local coordinates
- `rotation`: Facing direction in degrees
- `zone`: Current scene name

Enemy-specific:
- `level`: Enemy level
- `rarity`: `common`, `rare`, or `unique`
- `spawnPointId`: Associated spawn point (if determinable)

### Update Frequency

- Configurable interval (default: 100ms)
- Full state updates (not deltas)
- Batched: all entities in single message

---

## Spawn Point Tracking

### Death Events

When tracked enemy dies:
- Capture spawn point ID (if linkable)
- Calculate respawn time from game data
- Broadcast `spawn_death` message

### Respawn Timers

- Include active timers in state broadcasts
- Broadcast `spawn_respawn` when enemy respawns
- Auto-cleanup expired timers

---

## Third-Party Marker API

### C# API

```csharp
IMarkerAPI.RegisterMarker(MarkerDefinition marker)
IMarkerAPI.UpdateMarker(string id, MarkerUpdate update)
IMarkerAPI.RemoveMarker(string id)
IMarkerAPI.RemoveMarkersBySource(string source)
```

### MarkerDefinition

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `id` | string | Yes | Unique within source |
| `source` | string | Yes | Source mod identifier |
| `type` | string | Yes | Marker type for styling |
| `position` | Vector3 | Yes | Zone-local coordinates |
| `zone` | string | Yes | Zone name |
| `category` | string | No | For filtering |
| `rotation` | float | No | Degrees |
| `label` | string | No | Display label |
| `icon` | string | No | Icon identifier |
| `color` | string | No | Hex color |
| `metadata` | object | No | Arbitrary data for tooltips |
| `isStatic` | bool | No | Hint: doesn't move (default: false) |

### Discovery

BepInEx soft dependency pattern - other mods can optionally use API if installed.

---

## Bidirectional Communication

### Client → Server Messages

| Type | Description |
|------|-------------|
| `set_waypoint` | Set navigation waypoint |
| `clear_waypoint` | Clear current waypoint |
| `ping_location` | Ping location (broadcast to all) |
| `request_path` | Request pathfinding (future) |
| `execute_command` | Execute game command (future, requires cheat mode) |

### Server Responses

- Acknowledgments for waypoint operations
- Pings broadcast to all clients
- Path results for pathfinding requests
- Command results with success/failure

---

## WebSocket Server

- **Port**: Configurable, default 18584
- **Bind**: `0.0.0.0` (all interfaces for LAN access)
- **Protocol**: JSON messages with `type` field
- **Clients**: Multiple simultaneous connections supported

### JSON Naming Convention

- **Property names**: camelCase (`protocolVersion`, `entityType`, `spawnPointId`)
- **Enum/type values**: lowercase with underscores (`npc_friendly`, `set_waypoint`)

### Handshake

On connection, server sends:
```json
{
  "type": "handshake",
  "protocolVersion": "0.1.0",
  "modVersion": "0.1.0",
  "zone": "CurrentZone",
  "capabilities": ["entities", "spawns", "markers", "bidirectional"]
}
```

---

## Configuration (BepInEx)

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `Port` | int | 18584 | WebSocket server port |
| `UpdateInterval` | int | 100 | Broadcast interval (ms) |
| `EnableSpawnTracking` | bool | true | Track respawn timers |
| `EnableThirdPartyMarkers` | bool | true | Accept marker registrations |
| `EnableBidirectional` | bool | true | Accept client messages |

---

## Frontend Requirements

### Connection

- Configurable server address (default: `ws://localhost:18584`)
- Connection states: disconnected, connecting, connected, reconnecting
- Automatic reconnection at fixed interval (no exponential backoff)
- Protocol version validation on handshake

### Live Entity Display

- Separate layer above static markers
- Distinct icons per entity type
- Player marker most prominent
- Rotation indicator for facing direction
- Smooth position interpolation

### Auto-Follow Mode

- Toggle to center map on player
- Smooth animations
- Disable on manual pan, easy re-enable
- Works across zone boundaries (world map)

### Zone Changes

- Clear old zone entities when player changes zones
- Only current zone has live entity markers

### Respawn Timers

- Overlay at spawn point location
- Countdown display
- Enemy name and rarity
- Auto-remove on respawn

### Waypoints & Pings

- Right-click/long-press to set waypoint
- Prominent waypoint display
- Animated ping indicators

### Connection UI

- Status indicator (connected/disconnected)
- Live mode toggle
- Custom server address input (for LAN)
- Unobtrusive for non-mod users

---

## Quality Requirements

### Reliability

- Never crash the game
- Graceful error handling
- Handle missing game objects

### Performance

- No noticeable frame drops
- Throttled broadcasts
- Efficient serialization

### Maintainability

- DI for composition
- Generic + adapter pattern for testability
- XML documentation for public APIs

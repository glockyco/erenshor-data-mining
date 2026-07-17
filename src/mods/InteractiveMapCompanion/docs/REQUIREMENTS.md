# Interactive Map Companion Requirements

## Current product contract

Interactive Map Companion is a native BepInEx and Lunaris mod that broadcasts
live characters in the current scene to the interactive map website. Both native
entrypoints must expose the same observable protocol, configuration defaults,
overlay behavior, and cleanup semantics.

Current capabilities:

1. **Live entity tracking** — broadcast the player, SimPlayers, pets, friendly
   NPCs, and hostile NPCs.
2. **Multi-client WebSocket server** — support a local browser, another device on
   the LAN, and the in-game overlay at the same time.
3. **Zone transitions** — tell clients to clear the previous scene and begin
   consuming state for the new scene.
4. **In-game overlay** — show the interactive map through Steam HTML Surface and
   toggle it with a configurable key.
5. **Loader parity** — BepInEx and Lunaris use one shared runtime and differ only
   in native entrypoint, config, and logger adapters.

The handshake advertises only `entities`. Spawn monitoring, third-party markers,
and bidirectional navigation are future scope and must not be advertised before
their handlers and payloads exist.

## Entity tracking

### Classification

Track live `Character` instances in the current scene, except static mining nodes
and treasure chests.

| Protocol type | Identification |
| --- | --- |
| `player` | `GameData.PlayerControl.Myself` |
| `pet` | `Character.Master != null` |
| `simplayer` | Has a `SimPlayer` component |
| `npc_enemy` | Aggressive to player factions or non-positive world-faction standing |
| `npc_friendly` | Any other tracked character |

Classification precedence is player, pet, SimPlayer, then NPC hostility. This
ensures a summoned or mastered character remains a pet even when it also has
other character components.

### Entity payload

Each entity contains:

| Field | Type | Presence | Meaning |
| --- | --- | --- | --- |
| `id` | integer | always | Unity instance ID for the current process |
| `entityType` | string | always | One classification value from the table above |
| `name` | string | always | Stats display name, falling back to object name |
| `position` | three-number array | always | Scene-local Unity `[x, y, z]` coordinates |
| `rotation` | number | always | Normalized Y-axis rotation in `[0, 360)` |
| `level` | integer | when stats exist | Character level |
| `rarity` | string | hostile NPC only | `common` or `boss` |
| `characterClass` | string | player and SimPlayers when available | Class display name |
| `owner` | string | pets | Master's display name, or `Unknown` |

The entity does not carry a zone or spawn-point ID. The enclosing state message
supplies the zone. Rare and unique spawn classification is not available without
spawn context.

### Update behavior

- Update interval is configurable and defaults to `100` ms.
- Each `stateUpdate` contains a complete entity snapshot, not deltas.
- No entity scan or serialization runs when no clients are connected.
- Scene load immediately updates the active zone and attempts a fresh state
  broadcast.

## WebSocket server

- **Bind address:** `ws://0.0.0.0:<Port>` for local and LAN clients.
- **Default port:** `18585`.
- **Clients:** multiple simultaneous connections.
- **Format:** compact JSON with camelCase property names and omitted null fields.
- **Lifecycle:** start once, reject connections racing shutdown, close all clients
  on stop, and release the port on disposal.
- **Inbound messages:** log at debug level and otherwise ignore them.

Connection and send failures must be logged without crashing the game. Failed or
unavailable clients are removed from the active client set.

## Protocol

Protocol version `0.x.y` remains pre-stable. Clients should report version
mismatches rather than assuming unsupported fields or message types.

### `handshake`

Sent once when a client connects:

```json
{
  "type": "handshake",
  "protocolVersion": "0.2.0",
  "modVersion": "2026.7.17.0",
  "zone": "CurrentZone",
  "capabilities": ["entities"]
}
```

`modVersion` is generated at build time. The example is illustrative and not a
pinned release.

### `stateUpdate`

Sent at the configured interval while clients are connected:

```json
{
  "type": "stateUpdate",
  "zone": "CurrentZone",
  "timestamp": 1768645811226,
  "entities": []
}
```

`timestamp` is Unix time in milliseconds.

### `zoneChange`

Sent when a loaded scene replaces a previously known scene:

```json
{
  "type": "zoneChange",
  "previousZone": "OldZone",
  "zone": "NewZone",
  "timestamp": 1768645811226
}
```

Clients must clear entities from `previousZone` before rendering the next state.

## Configuration

Both loaders expose the same settings through their native configuration system.

| Setting | Type | Default | Description |
| --- | --- | --- | --- |
| `Port` | integer | `18585` | WebSocket server port |
| `UpdateInterval` | integer | `100` | State broadcast interval in milliseconds |
| `WebSocketLogLevel` | enum | `Warning` | Fleck log verbosity |
| `ModLogLevel` | enum | `Info` | Mod log verbosity |
| `EnableOverlay` | boolean | `true` | Enable the Steam HTML overlay |
| `ToggleKey` | keybind | `M` | Show or hide the overlay |
| `AnchorX` | number | `-1` | Horizontal anchor, with `-1` for automatic |
| `AnchorY` | number | `-1` | Vertical anchor, with `-1` for automatic |
| `Width` | integer | `0` | Width in pixels, with `0` for automatic |
| `Height` | integer | `0` | Height in pixels, with `0` for automatic |
| `ResetToDefaults` | boolean | `false` | Reset overlay geometry on the next launch |

## Frontend contract

- Default server URL is `ws://localhost:18585`.
- Connection states cover disconnected, connecting, connected, and reconnecting.
- Reconnection uses a fixed interval.
- Live entities render above static map markers.
- Player position and facing remain visually distinct.
- Zone changes remove stale entities from the previous scene.
- Manual pan may disable auto-follow, which remains easy to re-enable.
- The map remains fully usable when the mod is absent or live mode is disabled.

## Explicit future scope

The following concepts may be designed later, but they are not current protocol
or API commitments:

- `spawn_death` and `spawn_respawn` events or respawn timers;
- a third-party marker registration API;
- `set_waypoint`, `clear_waypoint`, `ping_location`, pathfinding, or command
  messages; and
- capabilities named `spawns`, `markers`, or `bidirectional`.

Adding any of these requires the server implementation, serializer coverage,
frontend consumer, protocol documentation, and an advertised handshake
capability in the same change.

## Quality requirements

- Loader adapters must contain no duplicated game behavior.
- Runtime startup and cleanup must be idempotent.
- `OnDestroy()` must stop broadcasts, close the server, destroy overlay state,
  unsubscribe scene events, unpatch Harmony, and clear patch statics.
- Public protocol and loader-neutral logic must remain testable without running
  Unity where practical.
- JSON payload tests must defend message names, camelCase fields, null omission,
  and current capabilities.

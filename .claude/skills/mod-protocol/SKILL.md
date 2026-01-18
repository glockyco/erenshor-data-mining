---
name: mod-protocol
description: WebSocket protocol for InteractiveMapCompanion. Use when implementing message types, serialization, or client/server communication.
---

# InteractiveMapCompanion Protocol

Quick reference for the WebSocket protocol. Full specification in
`src/mods/InteractiveMapCompanion/docs/REQUIREMENTS.md`.

## Key Decisions

- **Protocol version**: `0.1.0` (0.x = breaking changes expected)
- **Port**: 18585 (configurable)
- **Bind**: `0.0.0.0` (all interfaces for LAN access)
- **Format**: JSON with `type` field, camelCase naming
- **Coordinates**: Zone-local Unity coords `[x, y, z]`, client transforms to map

## Message Types

**Server → Client**:
- `handshake` - On connect: protocol version, mod version, current zone
- `state` - Periodic full state (entities, respawnTimers, markers)
- `zone_change` - Player changed zones
- `spawn_death` / `spawn_respawn` - Respawn timer events
- `marker_add` / `marker_update` / `marker_remove` - Third-party markers

**Client → Server**:
- `set_waypoint` / `clear_waypoint` - Navigation waypoints
- `ping_location` - Broadcast ping to all clients
- `request_path` - Pathfinding request (future)
- `execute_command` - Game commands (requires cheat mode, future)

## Entity Types

```
player, simplayer, pet, npc_friendly, npc_enemy
```

Enemy-specific fields: `level`, `rarity` (common/rare/unique), `spawnPointId`

## Serialization Conventions

- `System.Text.Json` with `JsonNamingPolicy.CamelCase`
- Timestamps: Unix milliseconds
- Omit null fields: `JsonIgnoreCondition.WhenWritingNull`
- Positions: `[x, y, z]` arrays

## Adding New Message Types

1. Add C# record in `Protocol/Messages.cs`
2. Add to `MessageSerializer` switch
3. Update REQUIREMENTS.md protocol section
4. Implement handler (server or client side)
5. Update this skill if it's a major addition

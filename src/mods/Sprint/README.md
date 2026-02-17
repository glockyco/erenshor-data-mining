# Sprint Mod

Clean, focused sprinting mod for Erenshor. Hold or toggle a key to run faster.

## Features

- **Configurable sprint key** (default: Left Shift)
- **Toggle or hold mode** (user preference)
- **Multiplicative speed boost** (default: 1.5x, range 1.0x - 10.0x)
- **Respects game mechanics** (status effects, roots, stuns, snares)

## Architecture

### Components

**SprintConfig** (`Config/SprintConfig.cs`)
- BepInEx configuration management
- Four config sections: Controls, Speed, Logging
- Range validation for speed multiplier (1.0 - 10.0)

**SprintManager** (`Core/SprintManager.cs`)
- MonoBehaviour for per-frame input handling
- Sprint state machine (idle/active)
- Caches player Stats reference
- Provides `IsSprintActive(Stats)` query for patches

**CalcStatsPatch** (`Patches/CalcStatsPatch.cs`)
- Harmony postfix on `Stats.CalcStats()`
- Applies multiplicative speed bonus when sprint is active
- Only affects player character
- Respects game's minimum speed cap (2.0)

**Plugin** (`Plugin.cs`)
- Main entry point
- Initializes configuration
- Wires up components
- Applies Harmony patches

### How It Works

1. **Input Handling**: `SprintManager.Update()` checks for sprint key input every frame
   - Toggle mode: Tap to toggle sprint on/off
   - Hold mode: Sprint active while key is held

2. **Speed Application**: `CalcStatsPatch.CalcStats_Postfix()` runs after vanilla stats calculation
   - Checks if sprint is active for the player
   - Multiplies `actualRunSpeed` by configured multiplier
   - Maintains game's minimum speed cap (2.0)

3. **Why Both Update() and Harmony Patch?**
   - Update() is needed for input (Unity's Input.GetKey must be called per frame)
   - Harmony patch ensures sprint applies whenever stats recalculate (equipment changes, buffs, etc.)
   - Prevents sprint from being overwritten by vanilla calculations

### Compatibility

**Works With:**
- All speed buffs/debuffs (multiplies total speed including status effects)
- Rooted/Stunned/Feared states (movement system handles these)
- Retreat mechanic (speed cap applied before sprint)
- Other mods (clean Harmony patching)

**Implementation Notes:**
- Only patches `Stats.CalcStats()` - minimal surface area
- No modification of game's core movement logic
- Thread-safe (all operations on Unity main thread)

## Building

```bash
# Copy game DLLs to lib/ directory (first time only)
uv run erenshor mod setup

# Build the mod (generates version from git)
uv run erenshor mod build --mod sprint

# Build and deploy to BepInEx plugins (for local testing)
uv run erenshor mod deploy --mod sprint

# Build and publish to website download directory
uv run erenshor mod publish

# Build and publish to Thunderstore
uv run erenshor mod thunderstore --mod sprint
```

## Testing

1. Build and deploy: `uv run erenshor mod deploy --mod sprint`
2. Launch game: `uv run erenshor mod launch`
3. Check BepInEx console for load messages
4. Test toggle vs hold mode
5. Test different speed multipliers
6. Verify compatibility with speed buffs/debuffs

## Configuration

Config file generated at: `BepInEx/config/wow-much.sprint.cfg`

```ini
[Controls]
SprintKey = LeftShift
ToggleMode = false

[Speed]
SprintMultiplier = 1.5

[Logging]
LogLevel = Info
```

See `thunderstore/README.md` for user-facing documentation.

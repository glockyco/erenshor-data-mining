# Justice for F7

Press F7 for truly clean screenshots.
Extends the F7 "Hide UI" key to also hide world-space UI elements.

## What it hides

The game's F7 key toggles the screen-space Canvas and Compass. This mod
additionally hides:

- **Nameplates** — NPC, SimPlayer, and player name text
- **Damage numbers** — floating damage and heal popups
- **Target rings** — the selection ring under targeted characters
- **XP orbs** — XP orb particles
- **Cast bars** — NPC and SimPlayer cast bars above nameplates
- **Loot prompts** — floating text above lootable corpses
- **Other world text** — any remaining world-space text

All elements are restored when you press F7 again.

## Configuration

Each element category can be independently toggled in the BepInEx
config file at `BepInEx/config/wow-much.justice-for-f7.cfg`:

```ini
[General]
## Master switch. When false, F7 behaves as vanilla.
Enabled = true

## Enable debug logging. Set to false to silence all mod log output.
EnableLogging = true

## Frames between re-scans while UI is hidden (0 = disable re-scan).
RescanInterval = 30

[Elements]
HideNameplates = true
HideDamageNumbers = true
HideTargetRings = true
HideXPOrbs = true
HideCastBars = true
HideOtherWorldText = true
```

## Installation

Requires [BepInEx 5](https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/).

1. Install BepInEx if you haven't already
2. Place `JusticeForF7.dll` in `BepInEx/plugins/`
3. Launch the game — config file is generated on first run

## Changelog

### 2026.217.0
- Fixed character names and zones being hidden on character selection screen

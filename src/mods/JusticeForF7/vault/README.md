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

Each element category can be independently toggled in the in-game Lunaris
config UI:

```
[General]
Enabled         = true   # Master switch. When false, F7 behaves as vanilla.
EnableLogging   = true   # Set to false to silence all mod log output.
RescanInterval  = 30     # Frames between re-scans while UI is hidden (0 = disable re-scan).

[Elements]
HideNameplates       = true
HideDamageNumbers    = true
HideTargetRings      = true
HideXPOrbs           = true
HideCastBars         = true
HideOtherWorldText   = true
```

## Installation

Install through Lunaris — open the in-game mod browser and grab Justice for F7 from the Erenshor Vault.

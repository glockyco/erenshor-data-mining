# Sprint

Ever feel like your character's jogging through molasses while trying to reach that distant quest marker? Not anymore.

**Sprint** adds a simple sprint key to run faster. Hold Shift (or any key you want) and go.

## What it does

Press and hold your sprint key to run faster. That's it. No cooldowns, no stamina system, no complications.

The speed multiplier stacks with existing buffs and debuffs - if you've got Flight of Foot active, sprinting makes you even faster. If you're snared, sprint still helps (but you're still slower than normal).

## Installation

Requires [BepInEx 5](https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/).

1. Install BepInEx if you haven't already
2. Place `Sprint.dll` in `BepInEx/plugins/`
3. Launch the game

## Configuration

Edit `BepInEx/config/wow-much.sprint.cfg` after first run:

```ini
[Controls]
SprintKey = LeftShift        # Any key works
ToggleMode = false           # true = tap to toggle, false = hold

[Speed]
SprintMultiplier = 1.5       # 1.0 to 10.0 - go wild
```

Want Mouse4? Set `SprintKey = Mouse4`.  
Want toggle instead of hold? Set `ToggleMode = true`.  
Want ludicrous speed? Set `SprintMultiplier = 10.0`.

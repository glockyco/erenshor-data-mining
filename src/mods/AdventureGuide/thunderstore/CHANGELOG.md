# Changelog

## v2026.1008.0

- More item sources: rare drops from any enemy, torn map pieces from fishing, treasure map chests and items you get by using another item. Mining, fishing and ground-pickup sources work again.
- After you read a treasure map, the arrow leads to the dig spot, then back to your quest once you dig.
- Smarter arrow: it prefers vendors and NPCs who hand over an item, heads for the nearest zone, and no longer swaps a nearby NPC for a creature farther away.
- Reliquary furniture counts as a quest target or source only once you have built it, and the guide names what to build.
- Levels make more sense: NPCs you only talk to, chests and objects show their area's level, and Reliquary steps show 16 for the Fiend guarding the hall.
- New setting World Markers.ShowAllRespawnTimers: respawn timers at every spawn point, not just quest targets.
- More reliable markers: no dead markers over living NPCs, no lingering respawn timers or corpse markers, and quest markers over NPCs whose in-game name differs from the guide's.
- Progress fixes: whole stacks and items received with bags closed count, completed quests stay completed, arena and feeding progress is accurate, and a new character no longer inherits a deleted one's quests.
- Typing in the search box no longer triggers hotkeys, Escape closes the journal again, UI scale stays in range, and the guide runs smoother.
- Quests you can't get are gone from the quest list.

## v2026.718.0

- Fix error spam in the log after returning to the main menu.

## v2026.717.0

- Hide the navigation arrow, ground path, and world markers while Hide UI mode (F7) is active.

## v2026.713.0

- Add Planar March quest data.
- Update NPC and item locations.
- Untrack completed quests more reliably.
- Keep the Untrack button available on completed quests.
- Suppress incorrect respawn markers on quest-gated and scripted spawns.
- Fix a crash on game exit.

## v2026.327.2

- Fixed mod not working if HideManagerGameObject is not set in BepInEx config

## v2026.327.1

- Fixed compatibility issue when installed via Thunderstore (assembly conflict with Unity's built-in types)

## v2026.327.0

- Added keyboard shortcut to toggle the ground path on/off (default: P, configurable in settings)
- Tracker window hides automatically when covered by native game UI panels
- Ground path now connects directly from your position to the target without floating gaps
- Ground path dashes remain stable as you walk — only the short endpoint segments adjust, reducing visual noise
- Navigation path and arrow diamond now render at a consistent height above terrain

## v2026.326.1

- Updated mod icon

## v2026.326.0

- Initial release: 170+ quests with step-by-step walkthroughs, GPS navigation arrow, ground path, floating world markers, and quest tracker

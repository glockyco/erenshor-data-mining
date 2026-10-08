# Changelog

## v2026.1008.0

- List world drops from any enemy as item sources, with the drop chance.
- List torn map pieces from fishing, treasure map chests, and items you get by using another item as sources.
- Rank vendors and NPCs who hand over an item above random drops at a similar level.
- Fix the arrow and markers for mining nodes, fishing spots, and ground pickups.
- Lead the arrow to the dig spot after you read a treasure map, then back to your quest once you dig.
- Lead the arrow to the nearest zone with the top source when no source is in your zone.
- Keep the arrow on a nearby vendor or quest NPC instead of switching to a creature farther away.
- Stop the arrow and loot markers from pointing at a corpse you already looted.
- Fix several navigation bugs, such as losing the target after a relog.
- Add World Markers.ShowAllRespawnTimers to show respawn timers at every spawn point, not just quest targets.
- Show quest markers over NPCs whose in-game name differs from the guide's, such as Gloopa and Catnip.
- Fix world markers that showed living NPCs as dead or left stray respawn timers.
- Use Reliquary furniture as a quest target or source only once it is built, and name the piece to build.
- Show the area's level for chests and for NPCs you only talk to.
- Fix quest item counts for stacks and for items received while bags are closed.
- Keep completed quests completed when a quest giver offers them again.
- Remove six unused Reliquary portal quests and two quests you can't get.
- Save tracked quests and tracker settings immediately.
- Keep the quest list's filter and sort order on Lunaris after a restart or reload.
- Stop the search box from triggering game hotkeys.
- Let Escape close the game's journal again.
- Improve performance and reduce memory use.

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

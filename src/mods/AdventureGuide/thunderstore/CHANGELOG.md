# Changelog

## v2026.1007.0

- Add the ShowAllRespawnTimers world marker setting. It shows a respawn timer at every spawn point in the zone whose creature died, not only where an active quest needs the NPC.
- Stop flashing respawn timers over quest NPCs while a zone loads.
- Stop showing respawn timers for spawns that a completed quest has ended for good.
- Keep quest markers on quest NPCs while their boss encounter runs.
- Show respawn timers of an hour or more as hours, minutes, and seconds.
- Keep the current time on night-only markers up to date.
- Fix world markers showing living NPCs as dead after the current zone reloads, for example when you respawn or recall inside your bind zone.
- Reduce memory churn and stutter: the guide window, the quest tracker, navigation, and world markers no longer create garbage every frame or on every NPC death.
- Fix quest tracker rows sometimes ignoring a click while the distance to the quest updated.
- Fix texture and material leaks in the world marker fonts and the ground path, and keep less font atlas data in memory.

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

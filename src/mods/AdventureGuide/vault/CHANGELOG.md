# Changelog

## v2026.1008.0

- New setting World Markers.ShowAllRespawnTimers: respawn timers over every dead creature's spawn, not just quest targets.
- Mining, fishing and ground-pickup sources work again: the arrow leads to them, and needed deposits and pickups get markers. Fishing steps point to a zone with the right water.
- When an item's sources are all in other zones, the arrow picks the nearest one.
- The arrow no longer swaps a nearby vendor or quest NPC for a creature farther away.
- Navigation fixes: correct zone exit after returning to a zone, travel steps that finish on arrival, continuing with the main quest after a sub-quest, first-person and drone view, and keeping your target through a relog.
- Tracked quests are saved immediately, and tracker setting changes apply at once instead of being reset on exit.
- New characters no longer inherit tracked quests, navigation or encounter progress from a deleted character in the same save slot.
- Quest item counts include whole stacks and items received with bags closed; kill and talk steps no longer show item counts.
- Completed quests no longer come back as active when a quest giver offers them again.
- Quest markers show over NPCs whose in-game name differs from the guide's, such as the Vithean chests, Gloopa and Catnip.
- World markers no longer show living NPCs as dead after a respawn or recall in the same zone, and no longer flash or linger as respawn timers where they shouldn't.
- Arena and Malaroth feeding progress ignores unrelated gladiators and resets when you leave the zone.
- Typing in the guide's search box no longer triggers game hotkeys, and Escape closes the game's journal again.
- UI scale is limited to 0.5–4 (-1 stays automatic), spacing follows it, and window layout reset works for closed windows.
- Smoother performance and lower memory use.

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

## v2026.618.1

- Fix world markers causing a NullReferenceException on the playtest version of
  the game.

## v2026.618.0

- First Erenshor Vault release (Lunaris-native build).
- 170+ quests with step-by-step walkthroughs and inline item sources.
- GPS navigation arrow with cross-zone routing and an optional ground path.
- Floating world markers with live respawn and night-spawn timers.
- Quest tracker overlay with proximity, level, and alphabetical sorting.

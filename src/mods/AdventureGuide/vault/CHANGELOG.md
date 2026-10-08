# Changelog

## v2026.1008.0

### New

- New setting World Markers.ShowAllRespawnTimers: shows a respawn timer over every dead creature's spawn in the zone, not only over the ones your quests need.
- Quest markers now appear over the mineral deposits and ground pickups your quests need. A mined deposit shows when it grows back.

### Navigation

- Mining and fishing steps get directions again, and ground pickups get them too. Mining and pickup steps lead to the spot; fishing steps lead to a zone with the right water, and the tracker shows "Fishing" instead of a distance.
- When everything you need is in other zones, the arrow heads for the nearest zone that has it instead of the first one on the guide's list.
- The arrow no longer gives up on a nearby vendor or quest NPC for a creature farther away a few seconds after you start.
- Entering a zone where your target also lives points you to the one in that zone.
- Leaving a zone and coming back points you to the right exit again.
- Travel steps keep pointing at their destination until you arrive, instead of sending you back out when you get there.
- After you finish a quest that another quest needs first, navigation carries on with that other quest.
- The guide keeps what you were following when you log out to character select and back in, and when a step can only point you to a zone.
- When a creature you need is dead, the arrow points to where it comes back soonest, now also for creatures with several variants.
- The arrow only detours to a corpse or chest that holds the item for your current step, stops pointing at loot you already took, and notices chests that come back with their corpses when you return to a zone.
- The arrow points the right way in first-person and drone view.
- A zone with no known way there no longer makes the game stutter while you follow it.
- Locked zone exits that need no quest say "Route locked" instead of an empty requirement.

### Quest tracker and quest progress

- Tracked quests are saved the moment you change them, so a crash no longer loses them.
- Changes to the Tracker.AutoTrack and Tracker.SortMode settings take effect at once and are no longer undone when you close the game.
- The tracker stays visible after you go back to character select and log in again.
- Item counts include every item in a stack: 18 Ancient Bones in one stack count as 18.
- Items you receive while your bags are closed count toward your quests right away.
- Kill and talk steps no longer show an item count such as "(0/2)".
- Asking a quest giver about a quest you already have or have finished no longer marks it active or tracks it again.
- Creatures that survive a killing blow, for example through Undying or Universal Will, no longer count as killed or get a respawn timer.

### World markers

- Quest markers appear over quest NPCs whose in-game name differs from the guide's, such as the Vithean chests, Gloopa, the Braxonian Planar Guards, and Catnip.
- Living NPCs no longer show as dead after the zone reloads, for example when you respawn or recall inside your bind zone.
- Markers update when night-only creatures leave at dawn and when a boss encounter resets.
- Quest markers stay on quest NPCs while their boss encounter runs.
- Two quests waiting on the same spawn show one respawn timer instead of two overlapping ones.
- Respawn timers no longer flash over quest NPCs while a zone loads, and no longer appear for spawns that a finished quest has removed for good.
- Respawn timers of an hour or more show hours, minutes and seconds, and night-only markers keep showing the current time.
- Turning the guide's world markers off and on no longer leaves the game's own quest markers missing or doubled.

### Arena and Malaroth feeding

- Gladiators wandering Vitheo's Plane of Valor no longer count as arena rounds or kills.
- Leaving the zone ends the current arena round or feeding, as it does in the game; the next fee starts a fresh count.
- Paying the arena fee right at the edge of the entrance starts the round in the guide.

### Windows and controls

- Typing in the guide's search box no longer triggers game hotkeys.
- Escape closes the game's own journal again while the guide replaces the quest log.
- The General.UiScale setting stays between 0.5 and 4, so a typo can't make the windows unusable, and -1 (automatic) stays automatic.
- Spacing in the guide window grows and shrinks with the UI scale.
- General.ResetWindowLayout also resets windows that are closed when you use it.
- Clicks on tracker rows and on "To (zone)" entries no longer get lost while distances update or the list re-sorts.
- If one guide window hits an error, the other windows keep working and the game's text colors stay as they were.

### Performance

- Less stutter: the guide no longer creates throwaway data every frame, so the game pauses to clean up memory far less often (about 2 instead of 10 times a minute in our tests).
- Lower memory use: fixed memory leaks while the game starts, on every UI scale change, and when markers or the ground path shut down. The guide also needs less memory to load its quest data.
- A window error that repeats every frame is written to the log once, then once a minute, instead of flooding it.

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

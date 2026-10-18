# Changelog

## v2026.1017.0

- Lead the arrow to what unlocks a locked quest target, such as a key, an item, another quest, or a furnished Reliquary room, and show the steps on the way.
- Treat targets behind locked doors as reachable only once you hold the key or have it on your keyring.
- Reach targets that only one entrance leads to, such as Occuphage through the Stowaway's Step lighthouse.
- List Bread, Water, Brackfruit Juice, Luminstone, Citrine Stone, and Star Stone as one source from any enemy with common drops instead of hundreds of enemies.
- Reduce memory use while navigating and updating quest markers.
- Show compact source choices with fishing hours, local chances and combat preparation.
- Keep a chosen source while following its prerequisites.
- Show the dialogue keyword when an NPC hands over an item.
- Check stored portal stones and runes, and show where to place them on the planning table.
- Follow crafting recipes to missing ingredients without losing the original quest.
- Skip the Reliquary claiming fight on accounts that already claimed it.
- Take the active Reliquary return portal back to the current character's saved destination.
- Close the guide with Escape without opening the game menu.
- Count repeated quest items together and keep alternative turn-ins separate.
- Keep item-read quest guidance working with alternative turn-ins.
- Keep navigation guidance in the tracker while browsing other quests.
- Keep the original quest visible while following its prerequisites.
- Keep source actions, locations, levels and chances compact.
- Group repeated sources without hiding their access requirements.
- Fix Guide loading on Lunaris.
- Clarify which mold a crafting source uses.
- Show repeated recipe ingredients with their total quantity.
- Avoid repeating item-use instructions beside their chances.
- Resume the recipe after gathering a chosen ingredient.
- Keep recipe ingredient markers and tracker order accurate until the full amount is gathered.
- Show repeated navigation instructions only once.
- Estimate quest levels from the easier complete alternative without skipping required steps.
- Keep encounter requirements visible when navigating to a prerequisite fight.
- Keep locked-door and quest requirements on item source locations.
- Explain which fee, feed or figurine summons arena fights, Malaroth feeding-site bosses and chessboard pieces, and lead the arrow there.
- Remove the separate arena round and Malaroth feeding-site entries from the quest list.

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
- Add World Markers.ShowBossRespawnTimers and World Markers.ShowEliteRespawnTimers to show respawn timers only where bosses or elites can spawn.
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

## v2026.618.1

- Fix world markers causing a NullReferenceException on the playtest version of
  the game.

## v2026.618.0

- First Erenshor Vault release (Lunaris-native build).
- 170+ quests with step-by-step walkthroughs and inline item sources.
- GPS navigation arrow with cross-zone routing and an optional ground path.
- Floating world markers with live respawn and night-spawn timers.
- Quest tracker overlay with proximity, level, and alphabetical sorting.

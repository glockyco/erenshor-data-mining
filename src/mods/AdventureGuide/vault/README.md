# Adventure Guide

Adventure Guide adds quest walkthroughs, item-source lookup and navigation to Erenshor. Use it to follow quest objectives, find missing items and track your next action without leaving the game.

[Read about Adventure Guide](https://erenshor.compendiums.org/adventure-guide).

<img src="https://erenshor.compendiums.org/adventure-guide-window.webp" alt="Quest window with walkthroughs and navigation buttons" style="max-width:100%;height:auto" />
The guide shows quest objectives, item counts and navigation actions.

## Install

Open Lunaris's in-game mod browser and install Adventure Guide from the Erenshor Vault. Enable the mod before using it.

This is the Lunaris build. Use the Thunderstore release instead if you run BepInEx. Do not move a BepInEx DLL into Lunaris's plugin directory.

## Follow quest objectives

Open the guide and select a quest to read who to talk to, what to say and which items to collect. Item counts update from your inventory. Level estimates on quests and steps help you choose what to attempt next. Browsing another quest does not change the action you are tracking.

`General.ReplaceQuestLog` is off by default. Turn it on if you want J to open Adventure Guide instead of the game's quest log.

## Navigate to an objective or item source

<img src="https://erenshor.compendiums.org/adventure-guide-nav.webp" alt="Navigation arrow and ground path guiding to target" style="max-width:100%;height:auto" />
The navigation arrow and optional ground path lead toward the selected target.

Click an objective's NAV button to follow a source. The arrow guides you across zone connections to the target. `Navigation.ShowArrow` is on by default. The ground path starts off, controlled by `Navigation.ShowGroundPath`, and you can toggle it with P.

Use "Choose a source" to select another way to obtain an item or follow missing crafting materials. Sources include drops, vendors, mining, fishing, crafting, quest rewards and items obtained by using another item. A quest reward can open its walkthrough inline. Locked sources show the requirements you still need.

Rare world drops and treasure map chests have no fixed source location. After you read a treasure map, navigation can lead you to its dig site.

## Find quest NPCs and check respawn times

<img src="https://erenshor.compendiums.org/adventure-guide-markers.webp" alt="World markers above NPCs showing quest state and respawn timers" style="max-width:100%;height:auto" />
Markers identify quest targets and show respawn or night-spawn information.

World markers identify quest givers, turn-in targets and enemies needed for objectives. `World Markers.Enabled` is on by default. A quest target's marker shows its respawn timer after it dies. Night-only spawns show their spawn window and the current game time.

The optional timer settings are off by default:

- `World Markers.ShowAllRespawnTimers` shows timers at every spawn point, not only quest targets.
- `World Markers.ShowBossRespawnTimers` shows timers where a boss can spawn, including rare spawns.
- `World Markers.ShowEliteRespawnTimers` shows timers where an elite can spawn, including rare spawns.

## Track your next action

The tracker keeps the selected quest and next action visible while you play. `Tracker.Enabled` and `Tracker.AutoTrack` are on by default, so newly accepted quests are tracked automatically. Press K to show or hide the tracker. Guide state is saved per character so you can return to your tracked action later.

## Default keys

| Key | Action |
| --- | --- |
| L | Open or close Adventure Guide |
| K | Show or hide the quest tracker |
| P | Toggle the ground path |

## Configure the guide

Use the in-game Lunaris config UI for the full settings list, including key bindings, UI scale and tracker appearance.

The guide saves settings and per-character guide state in its loader configuration. It saves window layout under the game's `plugins/config/adventureguide/` directory.

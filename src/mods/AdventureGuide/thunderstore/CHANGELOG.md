# Changelog

## Unreleased

- Quest-locked NPCs now show which quest unlocks them on their map marker instead of "Re-enter zone to respawn"
- Fixed completed prerequisites still showing as required in the tracker
- Fixed The Angler's Ring incorrectly listing Stowaway's Step as an unlock reward
- Meet the Fisherman now shows The Angler's Ring as a prerequisite
- Fixed quest "The Great Willow's Branch" showing no guide data
- Quests without complete guide data now show partial steps instead of "No guide data available"
- Fixed long step descriptions running off the edge of the panel instead of wrapping

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

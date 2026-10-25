# Justice for F7

Justice for F7 extends Erenshor's F7 "Hide UI" action to hide nameplates, target indicators, health bars and other UI drawn in the game world. Use it when you want screenshots without those elements.

## Install

This package requires [BepInEx 5](https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/). Install it with your Thunderstore mod manager, or copy the package's `JusticeForF7/` folder into the game's `BepInEx/plugins/` directory. Keep `JusticeForF7.dll` inside that folder, then launch the game.

This is the BepInEx build. Use the Erenshor Vault release instead if you run Lunaris.

## Hide world UI

Press F7 to hide the game's UI and the world-space elements covered by the mod. Press F7 again to show them. `General.Enabled` is on by default. Turn it off if you want F7 to behave as it does without the mod.

### Nameplates, health bars and target indicators

`Elements.HideNameplates` is on by default. It hides NPC, SimPlayer and player names, the target arrow above a character and character health bars. `Elements.HideTargetRings` is also on by default and hides the selection ring under your target.

### Damage numbers and XP orbs

`Elements.HideDamageNumbers` is on by default and hides floating damage and healing numbers. `Elements.HideXPOrbs` is on by default and hides XP orb particles. New popups and orbs are suppressed while the UI is hidden.

### Cast bars and other world text

`Elements.HideCastBars` is on by default and hides NPC and SimPlayer cast bars above nameplates. `Elements.HideOtherWorldText` is on by default and hides remaining world-space text, including loot prompts above corpses.

Turn off a category's setting if you want to keep those elements visible when you press F7.

## Keep newly appearing UI hidden

The mod checks for newly appearing world UI while F7 has the UI hidden. `General.RescanInterval` controls that check and defaults to once every 30 frames. Set it to 0 to turn periodic checks off.

## Default keys

- F7 hides or shows UI using the game's existing key binding.

## Configure Justice for F7

After the first launch, edit `BepInEx/config/wow-much.justice-for-f7.cfg`, or use [BepInEx Configuration Manager](https://github.com/BepInEx/BepInEx.ConfigurationManager) in-game. Use the generated file's descriptions for the full settings list.

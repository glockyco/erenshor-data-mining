# Sprint

Sprint adds a configurable sprint key to Erenshor. Use it to move your character faster while exploring, either by holding a key or toggling sprint on and off.

## Install

This package requires [BepInEx 5](https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/). Install it with your Thunderstore mod manager, or copy the package's `Sprint/` folder into the game's `BepInEx/plugins/` directory. Keep `Sprint.dll` inside that folder, then launch the game.

This is the BepInEx build. Use the Erenshor Vault release instead if you run Lunaris.

## Run faster

Hold your sprint key to increase your character's run speed. Sprint affects only your character and adds no stamina cost or cooldown. `General.Enabled` is on by default. Turn it off to disable sprint without removing the mod.

`Settings.SprintMultiplier` sets the speed increase. Its default is 1.5, which makes you run 50% faster. It applies after movement buffs and debuffs, so Flight of Foot increases the speed you sprint from and a snare reduces it.

## Hold or toggle sprint

`Controls.ToggleMode` is off by default, so you sprint only while holding the key. Turn it on to tap the key once to start sprinting and again to stop. Change `Controls.SprintKey` if you want a different binding.

## Default keys

- Left Shift activates sprint.

## Configure Sprint

After the first launch, edit `BepInEx/config/wow-much.sprint.cfg`, or use [BepInEx Configuration Manager](https://github.com/BepInEx/BepInEx.ConfigurationManager) in-game. Use the generated file's descriptions for the full settings list and allowed values.

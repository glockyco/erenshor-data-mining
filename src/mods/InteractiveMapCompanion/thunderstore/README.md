# Interactive Map Companion

Interactive Map Companion shows your live Erenshor position, SimPlayers, NPCs, enemies and pets on the interactive world map. Use it in a browser, on a second screen or in the optional in-game map overlay.

[Open the interactive map](https://erenshor.compendiums.org/map).

![Live tracking demo](https://erenshor.compendiums.org/world-map-companion.gif)
Live entities appear on the map as you move through the zone.

## Install

This package requires [BepInEx 5](https://thunderstore.io/c/erenshor/p/BepInEx/BepInExPack/). Install it with your Thunderstore mod manager, or copy the package's `InteractiveMapCompanion/` folder into the game's `BepInEx/plugins/` directory. Keep the DLL inside that folder, then launch the game.

This is the BepInEx build. Use the Erenshor Vault release instead if you run Lunaris.

## Connect the map

1. Launch Erenshor and log in with a character.
2. Open the [interactive map](https://erenshor.compendiums.org/map).
3. Enable Live Mode in the map sidebar.

## See live characters in your zone

The map tracks:

- Your character's position and facing direction.
- SimPlayers, including your party and others in the zone.
- Friendly NPCs, including quest givers and merchants.
- Living enemies.
- Companion pets.

Markers move as the game state changes. `Server.UpdateInterval` controls how often the mod sends updates. Its default is 100 milliseconds, or ten updates per second.

## Reduce map clutter

To show live entities without the static enemy and NPC markers, disable those layers in the sidebar. You can also open the [map with static markers hidden](https://erenshor.compendiums.org/map?layers=-sp%2C-spr%2C-spu%2C-npc).

## Use the in-game overlay

Launch the game through Steam to use the map inside the game window. `Overlay.EnableOverlay` is on by default. Press M to show or hide the overlay, or change `Overlay.ToggleKey` to use another key. You can adjust its size and position through the overlay settings.

## Use a second screen

For another device on your local network, enable `Server.AllowLanConnections` in the mod settings and restart the game. Enter your game computer's local IP address and configured WebSocket port in that device's map connection settings. Keep firewall access restricted to a trusted network because enabling LAN connections makes the server listen on all network interfaces.

## Default keys

- M shows or hides the in-game map overlay.

## Connection and settings

The mod streams game state directly to connected map clients through a WebSocket server. It listens only on loopback unless you enable LAN connections. Do not expose its port to the internet. The mod does not upload the stream to the map's hosting server.

After the first launch, edit `BepInEx/config/wow-much.interactive-map-companion.cfg`, or use [BepInEx Configuration Manager](https://github.com/BepInEx/BepInEx.ConfigurationManager) in-game. Use the generated file's descriptions for the full settings list. Match the map's connection address to `Server.Port` if you change it.

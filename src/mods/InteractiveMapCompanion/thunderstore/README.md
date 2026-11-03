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
3. Choose **Live** at the top right of the map, then **Connect to Erenshor on this PC**.

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

Launch the game through Steam to use the map inside the game window. `Overlay.EnableOverlay` is on by default. Press M to show or hide the overlay, or change `Overlay.ToggleKey` to use another key. You can adjust its size and position through the overlay settings. The overlay opens the map with **Live** on.

## Show the map on a phone or another PC

On the game PC, choose **Live** on the map, then **Show on another device**. Scan the code it shows with a phone camera, or open the address it shows in a browser on another PC. The device needs to be on the same network as the game PC. It reconnects by itself whenever the game runs, until you choose **Stop sharing**, which also stops older codes and addresses from working.

When Windows asks whether Erenshor may use the network, allow it on private networks. If no device connects, check that both devices use the same Wi-Fi rather than a guest network, and that Windows treats that network as private.

The live data goes from your game PC straight to the other device, encrypted. erenshor.compendiums.org only serves the map page.

## Default keys

- M shows or hides the in-game map overlay.

## Connection and settings

The mod streams game state directly to connected map clients through a WebSocket server that listens only on this PC. The mod does not upload the stream to the map's hosting server.

After the first launch, edit `BepInEx/config/wow-much.interactive-map-companion.cfg`, or use [BepInEx Configuration Manager](https://github.com/BepInEx/BepInEx.ConfigurationManager) in-game. Use the generated file's descriptions for the full settings list. Keep `Server.Port` at its default, because the map connects only to that port. Sharing uses the next port, over UDP and TCP.

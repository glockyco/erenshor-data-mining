# Interactive Map Companion

Interactive Map Companion shows your live Erenshor position, SimPlayers, NPCs, enemies and pets on the interactive world map. Use it in a browser, on a second screen or in the optional in-game map overlay.

[Open the interactive map](https://erenshor.compendiums.org/map).

## Install

Open Lunaris's in-game mod browser and install Interactive Map Companion from the Erenshor Vault. Enable the mod before using it.

This is the Lunaris build. Use the Thunderstore release instead if you run BepInEx.

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

For another device on your local network, enter your game computer's local IP address and the configured WebSocket port in the map's connection settings. For example, if the computer is `192.168.1.50` and you have not changed `Server.Port`, connect to `ws://192.168.1.50:18585`. Keep access restricted to a trusted network.

## Default keys

- M shows or hides the in-game map overlay.

## Connection and settings

The mod streams game state directly to connected map clients through a WebSocket server. The server listens on all network interfaces, so other devices can connect if your firewall permits them. Do not expose its port to the internet. The mod does not upload the stream to the map's hosting server.

Use the in-game Lunaris config UI for the full settings list, including the connection, overlay and logging options. Match the map's connection address to `Server.Port` if you change it.

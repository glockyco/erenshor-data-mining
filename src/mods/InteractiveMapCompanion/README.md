# Interactive Map Companion

Interactive Map Companion shows your live Erenshor position, SimPlayers, NPCs, enemies and pets on the interactive world map. Use it in a browser, on a second screen or in the optional in-game map overlay.

[Open the interactive map](https://erenshor.compendiums.org/map).

## Install and connect

Choose the release for your loader:

- [BepInEx installation and settings](thunderstore/README.md).
- [Lunaris installation and settings](vault/README.md).

Launch Erenshor and log in with a character. Open the map and enable Live Mode in its sidebar. For the in-game overlay, launch through Steam and press M to show or hide it with the initial key setting.

Configure the connection, overlay and logging through your loader's settings. Match the map's connection address to the configured server port if you change it.

## Game-state streaming

The mod streams game state directly to connected map clients through a WebSocket server. The server listens on all network interfaces, so other devices can connect if your firewall permits them. Keep access restricted to a trusted network and do not expose the port to the internet. The mod does not upload the stream to the map's hosting server.

## Build and deploy

Follow the [repository setup](../../../README.md#setup) first. From the repository root, with the game closed:

```sh
uv run erenshor mod setup
uv run erenshor mod build --mod interactive-map-companion --loader bepinex
uv run erenshor mod deploy --mod interactive-map-companion --loader bepinex
```

Use `--loader lunaris` instead for the Lunaris build. Deployment installs the selected artifact and activates its loader. Restart the game after deployment. Do not put one loader's DLL into the other loader's plugin directory.

## Development and releases

[src/InteractiveMapRuntime.cs](src/InteractiveMapRuntime.cs) holds the shared lifecycle. [src/Protocol](src/Protocol) defines the live messages. [src/Server](src/Server) implements WebSocket transport, and [src/Overlay](src/Overlay) handles the Steam browser overlay.

The [mod-development guide](../../../.agent/skills/mod-development/SKILL.md) covers local development. The [mod-pipeline guide](../../../.agent/skills/mod-pipeline/SKILL.md) covers packaging and publishing. Run checks through the repository's `erenshor test` commands, as described in the [repository README](../../../README.md#working-on-it).

If the mod does not load, check the active loader's logs and restart after switching loaders. If the map does not connect, check Live Mode, the configured connection address and firewall access.

## License

[MIT](../../../LICENSE).

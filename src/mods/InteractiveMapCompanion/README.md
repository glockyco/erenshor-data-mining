# Interactive Map Companion

Interactive Map Companion shows your live Erenshor position, SimPlayers, NPCs, enemies and pets on the interactive world map. Use it in a browser, on a second screen or in the optional in-game map overlay.

[Open the interactive map](https://erenshor.compendiums.org/map).

## Install and connect

Choose the release for your loader:

- [BepInEx installation and settings](thunderstore/README.md).
- [Lunaris installation and settings](vault/README.md).

Launch Erenshor and log in with a character. Open the map, choose **Live**, then **Connect to Erenshor on this PC**. For the in-game overlay, launch through Steam and press M to show or hide it with the initial key setting. The loader READMEs above also explain how to show the map on a phone or another PC.

Configure the connection, overlay and logging through your loader's settings. Keep `Server.Port` at its default, because the map connects only to that port. Sharing uses the next port, over UDP and TCP.

## Game-state streaming

The mod streams game state directly to the map on this PC through a WebSocket server that listens only on this PC. While sharing is on, other devices on the same network receive the same messages over WebRTC data channels on the next port. The mod does not upload the stream to the map's hosting server.

## Build and deploy

Follow the [repository setup](../../../README.md#setup) first. From the repository root, with the game closed:

```sh
uv run erenshor mod setup
uv run erenshor mod build --mod interactive-map-companion --loader bepinex
uv run erenshor mod deploy --mod interactive-map-companion --loader bepinex
```

Use `--loader lunaris` instead for the Lunaris build. Deployment installs the selected artifact and activates its loader. Restart the game after deployment. Do not put one loader's DLL into the other loader's plugin directory.

## Development and releases

[src/InteractiveMapRuntime.cs](src/InteractiveMapRuntime.cs) holds the shared lifecycle. [src/Protocol](src/Protocol) defines the live messages. [src/Server](src/Server) implements the WebSocket transport and sharing with other devices, with WebRTC in [src/Server/WebRtc](src/Server/WebRtc), and [src/Overlay](src/Overlay) handles the Steam browser overlay.

The [mod-development guide](../../../.agent/skills/mod-development/SKILL.md) covers local development. The [mod-pipeline guide](../../../.agent/skills/mod-pipeline/SKILL.md) covers packaging and publishing. Run checks through the repository's `erenshor test` commands, as described in the [repository README](../../../README.md#working-on-it).

If the mod does not load, check the active loader's logs and restart after switching loaders. If the map does not connect, check that **Live** is on and that `Server.Port` has its default. If another device does not connect, check the firewall and the network as the loader READMEs describe.

## License

[MIT](../../../LICENSE).

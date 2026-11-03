# Proposal

## Why

Players want the live map on a second PC or a phone while they play, and today the map only reaches a game on the same PC. Browsers block plain WebSockets from erenshor.compendiums.org to another device on the network in Safari and Firefox, and only an HTTPS page can keep a phone's screen on, so the route is WebRTC with one-way pairing, which a prototype proved in the running game (`.tmp/decisions/second-screen-5.md`).

## What Changes

- The companion mod gains a WebRTC endpoint for devices on the same network: ICE-lite answers, DTLS 1.2 on BouncyCastle and an SCTP data channel carrying the existing protocol messages. It is off until the player turns on Show on another device, and the setting, ICE credentials and certificate persist across restarts.
- The mod serves a small HTTP page at its network address that forwards a typed address to the map with the pairing values.
- The protocol lets the map on the game PC turn sharing on and off and receive the pairing link and viewer count. **BREAKING** for the map only in that the mod now reads one inbound message type.
- The map replaces the sidebar Live Mode section with a Live button and panel (demo video on first visit, Connect, pairing QR code and address, viewer count, Stop sharing), connects over WebRTC from a pairing link, follows the character on a connected phone with a status chip, and keeps the screen on.
- The in-game overlay opens the map with Live on.
- `Server.AllowLanConnections` is removed: nothing listens on the network for the WebSocket any more.
- READMEs and the /mod page describe second devices and the new privacy statement (data stays on the player's network).

## Capabilities

### New Capabilities
- `live-map-sharing`: how the companion mod and the map carry live game state to the game PC and to other devices on the same network, including pairing, consent and the map's Live controls.

### Modified Capabilities

## Impact

- `src/mods/InteractiveMapCompanion` (server, protocol, config, overlay URL, READMEs, packaging: DLL grows to about 5.6 MB with BouncyCastle).
- `src/maps` (live transport, Live button and panel, phone view, /mod page).
- Releases: a map deploy and a mod release, each after approval; then the reply to Coda314.

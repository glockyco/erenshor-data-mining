# Tasks

## 1. Mod: sharing endpoint

- [x] 1.1 Persist sharing setting, ICE credentials and certificate in both loader configs; remove `Server.AllowLanConnections` and bind the WebSocket to loopback only
- [x] 1.2 Start and stop the WebRTC server and HTTP redirect from the setting; rotate credentials on stop; cap viewers at 8; drop the prototype's always-on wiring and password log
- [x] 1.3 Unit tests for the ICE-lite responder, SCTP fragmentation, SACK and retransmission, and the redirect page
- [x] 1.4 Commit: feat(map-companion): share the live map with devices on the same network

## 2. Protocol 0.3.0

- [x] 2.1 Add `sharing` to the local handshake, `sharingChanged`, and the loopback-only `setSharing` in `Messages.cs` and `types.ts`, with protocol behavior tests
- [x] 2.2 Update `skill://mod-development` protocol section (binding, inbound message)
- [x] 2.3 Commit: feat(map-companion): let the local map control sharing

## 3. Map

- [x] 3.1 WebRTC transport from a pairing link, stored per device and retried on load
- [x] 3.2 Live button and panel replacing the sidebar section, first-visit video, Connect, Show on another device with QR code and address, viewers, Stop sharing
- [x] 3.3 Connected-phone view: follow, chip, screen wake lock with switch
- [x] 3.4 Overlay opens the map with Live on (mod `MapSite.OverlayUrl`)
- [x] 3.5 Player-visible wording through compare-options
- [x] 3.6 Commit: feat(map): show the live map on other devices

## 4. Documentation

- [x] 4.1 Mod READMEs (root, Thunderstore, Vault) and /mod page: second devices, firewall, privacy statement
- [x] 4.2 Commit: docs(map-companion): describe second devices

## 5. Verification

- [ ] 5.1 Running game: Chromium, Firefox and WebKit at phone size connect from a pairing link and a typed address; restart reconnects; Stop sharing disconnects; main-thread cost under 1 ms with three viewers
- [ ] 5.2 Lunaris build runs in the game
- [ ] 5.3 Ask for a test on a real Windows PC and phone
- [ ] 5.4 Ask before the map deploy and the mod release; then reply to Coda314

# Design

## Context

See proposal.md. The prototype on this branch (`src/mods/InteractiveMapCompanion/src/Server/WebRtc/`) proved the transport in Erenshor under CrossOver with Chromium 156, Firefox 157 and WebKit 27.2. It always listens and logs its ICE password; both go.

## Goals / Non-Goals

**Goals:** one route for every browser on the same network; no prompt except Chrome's future local-network question; reconnect without rescanning.

**Non-Goals:** other networks or mobile data, any server of ours, encryption the site cannot read (data never touches the site), Lunaris-specific UI.

## Decisions

- **Ownership.** The mod owns the WebRTC endpoint, the sharing setting and pairing values (loader config: `Sharing.Enabled`, `Sharing.IceUfrag`, `Sharing.IcePassword`, `Sharing.Certificate` as PEM). The map owns the Live UI and the transport choice. The protocol (`Protocol/Messages.cs` and `src/maps/src/lib/map/live/types.ts`) is the only boundary between them and changes in one commit on both sides.
- **Protocol 0.3.0.** Handshake gains `sharing: { enabled, link, address, viewers }` when the client is local. The mod reads one inbound type, `setSharing { enabled }`, only from loopback clients. `sharingChanged` is broadcast to local clients on change and viewer count change. Remote viewers never receive `sharing`.
- **Pairing link.** `https://erenshor.compendiums.org/map#live=<ip>:<port>.<ufrag>.<pwd>.<fingerprint hex>`; the fragment never reaches the site. The map stores the last link per device and retries it on load.
- **Ports.** WebSocket stays on `Server.Port` (loopback). WebRTC UDP and the HTTP redirect use `Server.Port + 1` (UDP and TCP), so the firewall question names one app and the address a player types is short.
- **Threads.** Receive thread per server, one handshake/receive thread and one send thread per viewer; the main thread only enqueues (prototype measured 0.07 ms). Max 8 viewers.
- **Failure handling.** A session that fails DTLS or goes quiet 30 s is disposed alone; socket bind failure turns sharing off and reports `sharing.error` to the map panel; turning sharing off disposes all sessions and rotates credentials. Nothing persists until the setting write succeeds.
- **Map transport.** `LiveConnection` gets a transport interface with the existing loopback WebSocket and a WebRTC transport that builds the ICE-lite offer from the link; message handling stays shared.
- **SCTP.** Keep the minimal association: ordered, reliable, fragmentation, timer retransmission, SACK gap handling. Add unit tests against captured browser packets.

## Risks / Trade-offs

- Real Windows and real phones are untested until verification; Windows Firewall may block UDP if the player declines its question, so the panel says what to check when no device connects within 20 s.
- Chrome plans local-network permission for WebRTC; the panel's note about the browser's question covers it.
- A 5.6 MB DLL. Accepted for one route everywhere.
- Rollback: the map keeps the loopback transport working with mod 0.2.0; the mod release is independent of the map deploy order because remote viewers need both.

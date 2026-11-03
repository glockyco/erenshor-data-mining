# Design

## Context

See proposal.md. The prototype on this branch (`src/mods/InteractiveMapCompanion/src/Server/WebRtc/`) proved the transport in Erenshor under CrossOver with Chromium 156, Firefox 157 and WebKit 27.2. It always listened and logged its ICE password. Both are gone.

## Goals / Non-Goals

**Goals:** one route for every browser on the same network; no prompt except Chrome's future local-network question; reconnect without rescanning.

**Non-Goals:** other networks or mobile data, any server of ours, encryption the site cannot read (data never touches the site), Lunaris-specific UI.

## Decisions

- **Ownership.** The mod owns the WebRTC endpoint, the sharing setting and pairing values (loader config: `Sharing.Enabled`, and `Sharing.Identity` with the ICE credentials, certificate and key on one line, hidden from the settings screens). The map owns the Live UI and the transport choice. The protocol (`Protocol/Messages.cs` and `src/maps/src/lib/map/live/types.ts`) is the only boundary between them and changes in one commit on both sides.
- **Protocol 0.3.0.** Handshake gains `sharing: { enabled, viewers, port, address, link, error }` for a trusted local client. `sharingChanged` carries the same object to trusted local clients when sharing turns on or off, fails, or the viewer count changes. The mod reads one inbound type, `setSharing { enabled }`, only from trusted local clients. A client is trusted when its WebSocket `Origin` is erenshor.compendiums.org or an `http://localhost` or `http://127.0.0.1` dev server, because any web page the player opens can reach the loopback WebSocket and must neither turn on sharing nor read the pairing link. Remote viewers never receive `sharing`.
- **Pairing link.** `https://erenshor.compendiums.org/map#live=<ip>:<port>.<ufrag>.<pwd>.<fingerprint hex>`. The fragment never reaches the site. The map stores the last link per device and retries it on load.
- **Ports.** WebSocket stays on `Server.Port` (loopback). WebRTC UDP and the HTTP redirect use `Server.Port + 1` (UDP and TCP), so the firewall question names one app and the address a player types is short.
- **Threads.** Receive thread per server, one handshake/receive thread and one send thread per viewer. The main thread only enqueues (prototype measured 0.07 ms). Max 8 viewers.
- **Failure handling.** A session that fails DTLS or goes quiet 30 s is disposed alone. A socket bind failure turns sharing off and reports `sharing.error` (`portUnavailable`) to the map panel. Turning sharing off disposes all sessions and rotates credentials. Sharing changes and messages to local clients run on the main thread, so viewer-count changes from session threads are queued for `Tick`.
- **Map transport.** `LiveConnection` gets a transport interface with the existing loopback WebSocket and a WebRTC transport that builds the ICE-lite offer from the link. Message handling stays shared.
- **SCTP.** Keep the minimal association: ordered, reliable, fragmentation, timer retransmission, SACK gap handling. Unit tests play the browser's side with packets built per RFC 4960, and the ICE tests use the RFC 5769 sample request.

## Risks / Trade-offs

- Real Windows and real phones are untested until verification; Windows Firewall may block UDP if the player declines its question, so the panel says what to check when no device connects within 20 s.
- Chrome plans local-network permission for WebRTC; the panel's note about the browser's question covers it.
- A 5.6 MB DLL. Accepted for one route everywhere.
- Rollback: the map keeps the loopback transport working with mod 0.2.0; the mod release is independent of the map deploy order because remote viewers need both.

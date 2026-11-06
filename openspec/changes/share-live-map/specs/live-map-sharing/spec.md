# Spec Delta

## Purpose
Carry the companion mod's live game state to the map on the game PC and to other devices on the same network, with explicit consent from the player.

## ADDED Requirements

### Requirement: Local live connection
The mod SHALL accept map connections from the same PC only, and SHALL NOT listen for the WebSocket on other network interfaces.

#### Scenario: Another device tries the WebSocket port
- **WHEN** a device on the network connects to the game PC's WebSocket port
- **THEN** the connection is refused

### Requirement: Sharing is opt-in and remembered
The mod SHALL accept connections from other devices only while the player has turned on sharing, SHALL remember that choice and its pairing values across game restarts, and SHALL stop accepting them and change the pairing values when the player stops sharing. Only the map itself SHALL see the pairing values or turn sharing on or off.

#### Scenario: Fresh install
- **WHEN** the mod starts for the first time
- **THEN** no port is open to the network

#### Scenario: Restart while sharing
- **WHEN** the player restarts the game with sharing on
- **THEN** a device paired before the restart reconnects without scanning again, as long as the game PC's address is unchanged

#### Scenario: Stop sharing
- **WHEN** the player chooses Stop sharing
- **THEN** every other device disconnects and the old pairing link no longer connects

#### Scenario: Another web page on the game PC
- **WHEN** a web page other than the map connects to the mod's local WebSocket
- **THEN** it receives no pairing link and cannot turn sharing on

### Requirement: One-way pairing from erenshor.compendiums.org
A device SHALL connect from the HTTPS map using only the pairing link's address, port, ICE credentials and certificate fingerprint, without sending anything to the game before connecting, and SHALL receive the same messages as a local connection: a handshake first, then state updates and zone changes.

#### Scenario: Phone scans the QR code
- **WHEN** a phone on the same network opens the pairing link in Chrome, Firefox or Safari
- **THEN** the map connects without a browser prompt in Firefox and Safari and shows the character following live

#### Scenario: Wrong credentials
- **WHEN** a device sends connection checks without the pairing link's ICE password
- **THEN** the game does not answer and no session starts

### Requirement: Typed address
The game PC SHALL serve, while sharing is on, a page at its network address that sends the browser to the map with the pairing values.

#### Scenario: Second PC types the address
- **WHEN** a player types the address shown under Live into another PC's browser
- **THEN** that browser opens erenshor.compendiums.org connected to the game

### Requirement: Game performance
Sending to other devices SHALL NOT encrypt or send on the game's main thread, and a viewer that falls behind SHALL skip updates rather than queue them.

#### Scenario: Three viewers
- **WHEN** three devices are connected
- **THEN** a broadcast costs the main thread under 1 ms

### Requirement: Live controls on the map
The map SHALL offer Live from a button on the map on every screen size. The panel SHALL show what Live does with the demo video on a first visit, a Connect action, and once connected the character and zone, Follow, and Show on another device with a QR code, the typed address and the number of connected devices. The quiet action beside the panel title SHALL read "Turn off Live" on the game PC and "Disconnect" on a phone.

#### Scenario: Connected phone
- **WHEN** a phone connects through a pairing link
- **THEN** the map follows the character, shows the character and zone in a chip, and keeps the screen on while connected with a switch to turn that off

#### Scenario: In-game overlay
- **WHEN** the player opens the in-game overlay
- **THEN** the map is already live
